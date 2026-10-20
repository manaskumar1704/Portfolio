"""The corpus ingest: Markdown in Postgres.

A batch job, not a request handler. Run it from the command line:

```bash
uv run python -m ingest.run                  # real corpus
uv run python -m ingest.fixtures             # fixtures (corpus/_test), by design
```

## Why re-running is safe

Upsert on `(source_path, chunk_index)`, so editing a document updates its chunks
in place rather than adding duplicates. That unique constraint is what makes this
idempotent, and it is why retrieval does not start returning the same text twice
after three edits.

A document that loses a section leaves orphaned chunks behind, because chunk 7 no
longer exists. `run.py --prune` deletes rows whose source file has gone. That is
a separate flag on purpose: pruning on every run would make a mistyped path wipe
the corpus, and the failure would be silent until a recruiter noticed a missing
answer.

## What is refused rather than stored

- **Wrong dimension.** A model setting that disagrees with the migration is a
  configuration error, and it must not be written into the column.
- **Zero vectors.** Cosine distance against one is NaN, which does not sort and
  silently poisons the ranking for every other row.
- **Empty chunks.** They embed to nothing useful and cite as nothing.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db import pool
from app.services.embeddings import (
    assert_dimension,
    embed_documents,
    is_zero_vector,
)

from .chunk import chunk_file

log = get_logger(__name__)

# Directories the ingest never walks. `_test` is fixtures, `_source` holds PDFs,
# and `_converted` is intermediate output from `from_pdf.py`.
#
# This set is documentation, not the guard. `discover` skips anything with a
# leading underscore, so a new `_something` directory is excluded without editing
# this list — the set exists so the three well-known ones are visible to a reader.
SKIP_DIRS = {"_test", "_source", "_converted"}

# Prose about the corpus rather than content from it. `_test/README.md` explains
# what the fixtures are and quotes a sample address; ingesting it made that README
# outrank `contact.md` for the question "what is his email?", which is precisely
# the kind of self-referential noise a corpus must not contain.
PROSE_FILENAMES = {"README.md", "readme.md", "INDEX.md", "index.md"}


def _is_excluded(part: str) -> bool:
    """Whether one path component keeps a file out of the corpus.

    A leading underscore is the convention for "not corpus", which covers
    `SKIP_DIRS` and anything that joins them later. `.git` is the other half.
    """
    return part in SKIP_DIRS or part.startswith("_") or part.startswith(".")


def _directory_is_excluded(directory: Path) -> bool:
    """Whether the corpus root itself is a directory we refuse to ingest.

    **This is the check that was missing, and its absence put 24 chunks of a
    fictional person into a real database.**

    `discover` compared each file's path *relative to the directory it was
    given*. Pointed at `corpus/` that worked: `_test` was a component and was
    skipped. Pointed at `corpus/_test`, `relative_to` produced `about.md`, the
    `_test` component was never examined, and every fixture looked like ordinary
    corpus.

    So the caller could defeat the guard by choosing a different `--dir`, which is
    the one thing the guard exists to prevent. Now the root is checked too, and
    `--dir corpus/_test` discovers nothing rather than quietly loading fiction.
    """
    name = directory.name
    return _is_excluded(name) or directory.resolve().name in SKIP_DIRS


@dataclass
class FileResult:
    path: str
    written: int
    skipped: int


def discover(directory: Path) -> list[Path]:
    """Every markdown file under `directory`, sorted for reproducible runs.

    Skips underscore-prefixed directories and README-style prose. Both are
    deliberate: the first keeps fixtures and PDFs out of a real ingest, the
    second keeps documentation about the corpus from being treated as corpus.

    Returns an empty list if `directory` is itself a directory we refuse to
    ingest. An empty result is loud — the run writes nothing and the preflight
    reports zero chunks — whereas ingesting fiction is quiet.
    """
    if _directory_is_excluded(directory):
        log.warning("refusing to ingest %s: it is not a corpus directory", directory)
        return []

    return sorted(
        p
        for p in directory.rglob("*.md")
        if not any(_is_excluded(part) for part in p.relative_to(directory).parts)
        and p.name not in PROSE_FILENAMES
    )


async def upsert_chunk(
    source_path: str,
    index: int,
    heading: str,
    content: str,
    embedding: list[float],
    token_count: int,
) -> None:
    async with pool.session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO chunks (source_path, chunk_index, heading, content,
                                    embedding, token_count)
                VALUES (:path, :idx, :heading, :content, CAST(:vec AS vector), :tokens)
                ON CONFLICT (source_path, chunk_index) DO UPDATE SET
                    heading = EXCLUDED.heading,
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    token_count = EXCLUDED.token_count,
                    created_at = now()
                """
            ),
            {
                "path": source_path,
                "idx": index,
                "heading": heading,
                "content": content,
                "vec": str(embedding),
                "tokens": token_count,
            },
        )


async def prune(live_paths: set[str]) -> int:
    """Delete chunks whose source file no longer exists."""
    async with pool.session_scope() as session:
        rows = (await session.execute(text("SELECT DISTINCT source_path FROM chunks"))).fetchall()
        stale = [r.source_path for r in rows if r.source_path not in live_paths]

        if not stale:
            return 0
        await session.execute(
            text("DELETE FROM chunks WHERE source_path = ANY(:paths)"),
            {"paths": stale},
        )

    log.info("pruned", extra={"count": len(stale), "paths": stale[:10]})
    return len(stale)


def estimate_tokens(text_body: str) -> int:
    """Rough token count for budgeting a chunk into a prompt.

    Four characters per token is the usual English approximation. Exact enough to
    avoid blowing a context window, and it avoids pulling in a tokenizer for one
    integer. The stored value is a hint for the retrieval layer, not a billing
    figure.
    """
    return max(1, len(text_body) // 4)


async def ingest_file(path: Path, directory: Path) -> FileResult:
    settings = get_settings()
    source_path = path.relative_to(directory).as_posix()

    # The file's own name becomes the fallback heading for any prose that appears
    # before the first `#`, which is usual for a résumé or a snapshot. Reading and
    # chunking is filesystem work, so it goes to a thread.
    chunks = await asyncio.to_thread(
        chunk_file, path, source_heading=path.stem.replace("-", " ").title()
    )
    if not chunks:
        log.warning("no chunks produced", extra={"path": source_path})
        return FileResult(source_path, 0, 0)

    vectors = embed_documents([c.content for c in chunks], settings)

    written = 0
    skipped = 0
    for chunk, vector in zip(chunks, vectors, strict=True):
        try:
            assert_dimension(vector, settings)
        except ValueError:
            # One model mismatch poisons every chunk, so stop rather than write
            # a partial corpus.
            log.error("dimension mismatch; nothing written", extra={"path": source_path})
            raise

        if is_zero_vector(vector):
            log.warning(
                "zero vector, skipping chunk", extra={"path": source_path, "index": chunk.index}
            )
            skipped += 1
            continue

        await upsert_chunk(
            source_path,
            chunk.index,
            chunk.heading,
            chunk.content,
            vector,
            estimate_tokens(chunk.content),
        )
        written += 1

    return FileResult(source_path, written, skipped)


async def run_ingest(
    directory: Path,
    do_prune: bool = False,
    files: list[Path] | None = None,
) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    if not await asyncio.to_thread(directory.exists):
        raise SystemExit(f"corpus directory not found: {directory}")

    # Discovered in `main` when running from the command line, so the blocking
    # `rglob` happens off the event loop. A caller that already has the list
    # (a test, a future watcher) passes it in and skips the walk.
    if files is None:
        files = await asyncio.to_thread(discover, directory)
    if not files:
        raise SystemExit(f"no markdown files under {directory}")

    await pool.setup(settings)
    total = 0
    try:
        async with pool.session_scope() as session:
            run_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO ingest_runs (chunk_count, embedding_model, embedding_dimensions)
                        VALUES (0, :model, :dims) RETURNING id
                        """
                    ),
                    {"model": settings.embedding_model, "dims": settings.embedding_dimensions},
                )
            ).scalar_one()

        for path in files:
            result = await ingest_file(path, directory)
            total += result.written
            log.info(
                "ingested",
                extra={"path": result.path, "written": result.written, "skipped": result.skipped},
            )

        # Pruning compares against the file list from *this* run. A file skipped as
        # prose or as an underscore directory has no rows to prune, so nothing is
        # lost; but rows from a file that used to be ingested and no longer is
        # (a renamed README, say) are removed only when --prune is passed.
        if do_prune:
            live = {p.relative_to(directory).as_posix() for p in files}
            await prune(live)

        async with pool.session_scope() as session:
            await session.execute(
                text("UPDATE ingest_runs SET chunk_count = :n WHERE id = :id"),
                {"n": total, "id": run_id},
            )

        print(f"ingested {total} chunks from {len(files)} files into run {run_id}")
        return total
    finally:
        await pool.teardown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a Markdown corpus into Postgres.")
    parser.add_argument(
        "--dir",
        default=None,
        help="Corpus directory. Defaults to CORPUS_DIR from the environment.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Also delete chunks whose source file no longer exists.",
    )
    args = parser.parse_args()

    settings = get_settings()
    directory = Path(args.dir) if args.dir else Path(settings.corpus_dir)
    # `discover` does blocking filesystem I/O, and `rglob` on a large tree is not
    # instant. The ingest is a batch job with nothing else to do, so a worker
    # thread keeps the concern visible rather than pretending pathlib is async.
    files = asyncio.run(_discover_async(directory))
    asyncio.run(run_ingest(directory, do_prune=args.prune, files=files))
    return 0


async def _discover_async(directory: Path) -> list[Path]:
    return await asyncio.to_thread(discover, directory)


if __name__ == "__main__":
    sys.exit(main())
