# Evals

The golden sets for the things the site claims to do. They are pytest, run
through the apps/api project so the app package and its models resolve:

```bash
uv run --project apps/api pytest evals                     # retrieval + (if keys) live answers
uv run --project apps/api pytest evals -m "not slow"       # skip the NLI download
uv run --project apps/api pytest evals\test_groundedness_nli.py   # the slow NLI harness
```

`evals/conftest.py` puts `apps/api` on `sys.path` and loads its `.env`, so the
same checkout runs everything without source edits. Existing environment
variables win over the `.env`, which is what CI does.

| File | Costs | Needs |
|---|---|---|
| `test_retrieval.py` | ~25 s | `DATABASE_URL` with the **fixture corpus** loaded (`apps/api`: `uv run python -m ingest.fixtures`) |
| `test_answers_live.py` | minutes (live model) | + `GEMINI_API_KEY` |
| `test_groundedness_nli.py` | `slow` marker; ~83 MB download once, then ~2 s | nothing else |

## What each file decides, and the honest edges

- **Retrieval** pins the gate's real trade: on-topic questions written with the
  corpus's own vocabulary find their file, off-topic ones find nothing. The
  documented near-misses (paraphrases with no common words with the corpus)
  are deliberately **not** in the set — they are the recall limit recorded in
  `app/services/rag.py`, not passing cases.
- **Answers** grade behaviour, not prose: substring facts, membership checks
  on cited paths, refusal markers, and hard prohibitions (the injected
  instruction's fake password must never appear in any answer; a draft must
  carry no token anywhere).
- **NLI** exists to document a ceiling offline, not to gate the badge: with
  single-sentence premises the harness discriminates (entailment for
  paraphrases, contradiction for contradicted facts), and arithmetic
  restatements stay neutral — the measured reason the verified badge stays
  dark in production (ADR 0009) and the reason an NLI check belongs to the
  JobFinder service (ADR 0008) rather than this repo's request path.

The CI evals job (checkpoint 5) runs the full three files with the secrets it
needs; the API image never contains this directory or the downloaded NLI
model.
