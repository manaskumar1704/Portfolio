"""Load the fictional corpus (`corpus/_test`) into the configured database.

`discover()` refuses underscore directories, and deliberately so: its guard
exists because `--dir corpus/_test` once put a fictional person's résumé into a
live database. The evaluation suites still need fixtures to assert against, so
loading has its own batch entry point here rather than re-opening that hole.

## Why this is safe where `--dir` is not

There is no directory flag to get wrong. The directory comes from the same
`CORPUS_DIR` the real corpus uses, with the literal `_test` leaf appended, and
nothing here can return anything else. The file list is handed to
`run_ingest(files=…)` — the explicit-list door `run.py` already had — so the
walk is all this file adds, and `discover` and its guard stay exactly as strict
as they were.

## Which database

Separation is by database, not by table: the dev/test branch holds **only**
fixtures, production holds **only** the real corpus. Pruning therefore happens
on every load — the fixture set is the whole corpus of its database, so a chunk
whose file has been deleted is stale, not historical.

```bash
uv run python -m ingest.fixtures    # load (or refresh) the fixtures
```
"""

import asyncio
from pathlib import Path

from .run import PROSE_FILENAMES, _is_excluded, run_ingest


def fixture_directory(corpus_dir: str) -> Path:
    """`corpus/_test`, derived from the configured corpus root.

    There is no directory flag to get wrong, which is the whole safety story:
    this function can only ever return a path whose leaf is `_test`. Pointing
    `CORPUS_DIR` at a real corpus checkout is fine — the loader appends `_test`.
    The reading-directly-instead case (`CORPUS_DIR` already ending `_test`) is
    respected rather than double-appended.
    """
    root = Path(corpus_dir)
    directory = root / "_test" if root.name != "_test" else root

    if not directory.exists():
        # `CORPUS_DIR` is written relative to a cwd nobody fixed in stone: the
        # ingest docs say `cd apps/api`, some values read from the repo root.
        # Prefer the literal value; fall back to the same path from the repo
        # root, which is where `corpus/` actually is in this checkout. A wrong
        # guess reads as "no fixtures", never as ingested fiction.
        candidate = Path(__file__).resolve().parents[3] / directory
        if candidate.exists():
            directory = candidate

    return directory


def list_fixture_files(directory: Path) -> list[Path]:
    """Every markdown file in the fixture directory, README prose excluded.

    Same two exclusions `discover` applies — underscore-prefixed directories
    stay out, and `README.md`/`INDEX.md` are documentation about the corpus.
    A fixture README once outranked the corpus for "what is his email?" because
    it quoted the fictional address; prose about the corpus is not corpus.
    """
    return sorted(
        p
        for p in directory.rglob("*.md")
        if not any(_is_excluded(part) for part in p.relative_to(directory).parts)
        and p.name not in PROSE_FILENAMES
    )


def main() -> int:
    from app.core.config import get_settings

    directory = fixture_directory(get_settings().corpus_dir)
    files = list_fixture_files(directory)
    if not files:
        raise SystemExit(f"no fixture files under {directory}")

    asyncio.run(run_ingest(directory, do_prune=True, files=files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
