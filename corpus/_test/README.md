# Fixture corpus

**Nothing in here is real.** Wren Ashby is a fictional person. Every employer,
date, metric and address is invented. The email uses `.invalid`, which RFC 2606
reserves and which can never resolve.

These files exist so the retrieval tests have something concrete to assert against.
Absurd facts are deliberate: a chunk ranking "Lantern Analytics" for a question
about pasta is unmistakably a bug, where a plausible-looking wrong answer would
not be.

## Using them

```bash
uv run python -m ingest.fixtures
uv run pytest -m integration tests/test_rag.py
```

`ingest/run.py --dir` refuses this directory on purpose (see its guard): the
fixture loader in `ingest/fixtures.py` is the supported path. It takes no
directory argument — it appends `_test` to `CORPUS_DIR` — so the mistake that
puts fiction into a real corpus is not expressible.

## Pointing at the real corpus

The ingest reads `CORPUS_DIR` from the environment, and `--dir` overrides it. The
real corpus lives in its own repository, so pointing at it is a path:

```
CORPUS_DIR=/path/to/portfolio-corpus uv run python -m ingest.run
```

`ingest/run.py` skips any directory whose name starts with an underscore, so this
folder can never be ingested by accident alongside the real corpus. If you did
mistake one for the other, the rows are distinguishable by `source_path` and
`--prune` clears them.

## Adding a file here

Use real heading levels. The chunker turns `#` and `##` into chunk boundaries and
carries them through as citation labels, so a file with no headings becomes one
unlabelled blob that retrieves badly and cites as nothing.