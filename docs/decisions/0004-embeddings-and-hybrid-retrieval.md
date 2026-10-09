# 0004 — Local embeddings, hybrid retrieval, and the corpus

Phase 4. Four decisions, three of which were settled by measurement after the
obvious approach turned out not to work.

## fastembed, and why not sentence-transformers

Render free gives 512 MB. sentence-transformers pulls in PyTorch — roughly 800 MB
of wheel and several hundred MB of resident memory. fastembed's ONNX path is 67 MB
of model with no autograd runtime, which is the entire decision.

Measured inside the actual container with `--memory=512m --cpus=0.1`:

| | |
|---|---|
| Idle RSS, model not loaded | 62 MB |
| Peak RSS, model loaded and embedding | **267 MB** |
| Time for one query embedding | 1.4 s at 0.1 CPU |

That headroom is why there is no reranker. A cross-encoder would be a second
model in a box that already uses half its memory.

`OMP_NUM_THREADS=1` is not a default to copy — ONNX spawns a thread per core, and
on a 2-core box that is two threads fighting over the 0.1 CPU the free tier
allots. It made every embedding slower than running it on one.

## The query instruction, applied by hand

`BAAI/bge-small-en-v1.5` was trained with an instruction on the query side only:
`Represent this sentence for searching relevant passages: `. The model card is
explicit that it must never go on a passage.

Measured on the installed fastembed 0.9:

```
query_embed("x")  ==  embed("x")                      # identical vectors
embed(PREFIX + "x")                                 # different vectors
```

`query_embed` does not add it. Trusting the method name would have been a silent
retrieval-quality loss with no error anywhere to trace it from. So the prefix is
applied by hand, and a test asserts both halves: that the prefix changes the
vector, and that fastembed's `query_embed` still does not add it.

## Hybrid retrieval, because dense alone could not say "no"

The plan assumed dense-only retrieval with a distance threshold, which is the
common shape. Measured against the fixture corpus, it does not work:

| | best-match cosine distance |
|---|---|
| 10 on-topic questions | 0.315 – 0.537 |
| 8 off-topic questions | 0.406 – 0.600 |

**The ranges overlap.** No threshold separates them, so `search_portfolio` could
never honestly return `found: false`. The worst it could do was hand the model the
least-bad chunk, which is how a portfolio chatbot ends up discussing someone's
favourite colour with total confidence.

The clearest single case: "what is his email?" has almost no semantic overlap
with the contact document — and the exact string is sitting in it. Dense retrieval
cannot see that. Lexical retrieval finds it immediately.

So retrieval is now two retrievers fused with Reciprocal Rank Fusion: dense over
`embedding <=> :vec`, lexical over a generated `body_tsv`, combined as
`1/(k+rank)` each. RRF rather than a weighted score sum because cosine distance
and a lexical rank are not on comparable scales — only order is comparable.

After the change, on the same fixture corpus:

- **7 of 7** off-topic questions return nothing.
- **7 of 10** on-topic questions are answered.

The three misses are paraphrases with no shared vocabulary — "which company did
he work at first?" against a document that says "Data Engineer, 2017 to 2019".
The confidence gate (`rrf_score >= 0.02`, meaning both retrievers agreed) is set
so that those three miss rather than the corpus admitting noise. That trade is
stated rather than tuned away, and phase 8's evals re-measure it on the real
corpus, which is where the number that matters comes from.

## `ts_rank_cd`, not BM25 — a deviation from the skill

The `neon-postgres` hybrid-search reference prescribes BM25 via
`CREATE EXTENSION lakebase_bm25`. This project has an extension allowlist and the
attempt failed:

```
InsufficientPrivilege: extension "lakebase_bm25" is not in the allowed
extensions list
```

`ts_rank_cd` is built into every Postgres, needs no extension, and is fine at this
corpus size. BM25 would score better on a large corpus. The upgrade path is one
operator in the lexical CTE, taken when the corpus passes a few hundred chunks and
the evals show lexical misses.

## The corpus is not written here

The real corpus lives in the user's own repository and arrives via `CORPUS_DIR`.
Nothing in `apps/api` invents résumé content. `corpus/_test/` holds a fictional
person with absurd facts — a chunk ranking "Lantern Analytics" for a question
about pasta is unmistakably a bug, where a plausible wrong answer would not be.
Every file says FIXTURE at the top, and `_`-prefixed directories are skipped by
the ingest so fixtures can never be ingested alongside the real corpus.

## PDFs: two silent failures, both checked

A PDF converter produces Markdown that looks fine and retrieves badly in exactly
two ways. Lost headings mean the whole résumé becomes one unlabelled chunk and
every citation is empty. Hyphenated line breaks ("manage-\nment") make a word
unmatchable by any question about it.

`ingest/from_pdf.py` checks both and exits non-zero. The heading check is fatal
because the consequence is total. The hyphen check is a warning because
`ingest/chunk.py` rejoins those anyway — but it reports the count, because a
document full of them is a document whose paragraphs may be mangled elsewhere
too.

## Known limits, recorded rather than fixed

**`ponytail: `ts_rank_cd` not BM25, RRF k=60 fixed, no reranker, top-4 retrieval,
ONNX with a single thread.`** Each is a knob with a trigger: a few hundred chunks
and lexical misses for BM25; eval recall under 0.8 for the RRF constant and the
top-4; 512 MB is no longer the constraint for a reranker.