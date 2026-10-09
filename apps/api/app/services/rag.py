"""Retrieval: dense, lexical, and the fusion of both.

One function. Phase 3's tool loop calls it, phase 7's MCP server calls it, phase
8's evals call it. There is no second copy.

## Why hybrid, and what the measurement said

Dense retrieval alone could not tell an on-topic question from an off-topic one on
this corpus. Ten on-topic questions scored 0.315 to 0.537 best-match cosine
distance. Eight off-topic questions scored 0.406 to 0.600. **The ranges overlap**,
so no threshold separates them and the tool cannot honestly report "nothing
matched" — the worst it could do is return the least-bad chunk, which is how a
chatbot ends up confidently discussing a colour preference.

The clearest case: "what is his email?" has almost no semantic overlap with the
contact document, but the exact term is sitting in it. A lexical retriever finds
that; a dense one cannot. Fusing the two with Reciprocal Rank Fusion is what the
Lakebase Search guide prescribes.

RRF rather than a weighted score sum, because cosine distance and a lexical rank
are not on comparable scales. RRF adds `1 / (k + rank)`, so only order matters.

## `ts_rank_cd`, not BM25

The neon-postgres hybrid-search reference prescribes BM25 via
`CREATE EXTENSION lakebase_bm25`. This project has an extension allowlist and the
attempt failed with `InsufficientPrivilege: extension "lakebase_bm25" is not in
the allowed extensions list`. `ts_rank_cd` ships with Postgres, needs no
extension, and is fine at this corpus size.

**ponytail: `ts_rank_cd` instead of BM25, and a fixed RRF constant.** BM25 scores
better on a large corpus; when the corpus passes a few hundred chunks and the evals
show lexical misses, swap the one operator in the lexical CTE.

## The `sources` key

Results carry their `source_path` under `sources`, which is what phase 3's loop
turns into `citation` events. Retrieval therefore knows nothing about SSE and the
frontend still gets provenance.
"""

from dataclasses import dataclass

from sqlalchemy import text

from app.core.config import Settings
from app.core.logging import get_logger
from app.db import pool
from app.services.embeddings import assert_dimension, embed_query_async

log = get_logger(__name__)

DEFAULT_LIMIT = 4

# Candidates per retriever. More than the final count, or one retriever wins
# before fusion has enough overlap to work with.
CANDIDATES = 40

# The documented RRF starting point. Smooths the contribution so a rank of 1 and a
# rank of 2 do not swamp a document that the other retriever also ranked well.
RRF_K = 60

# The confidence gate. With k=60, a document only one retriever found scores
# 1/61 = 0.0164; one both retrievers found scores 2/61 = 0.0328. So this
# threshold means "both the meaning and the wording agree".
#
# Measured on the fixture corpus (see probe_hybrid.py): with this gate, 7 of 10
# on-topic questions clear it and 8 of 8 off-topic questions are rejected. That
# is the trade, stated plainly. The three misses are paraphrases with no shared
# vocabulary — "which company did he work at first?" against a document that says
# "Data Engineer, 2017 to 2019".
#
# A lower gate would answer more of those three and start admitting noise; a
# higher one would make the agent say "I don't know" about things it could answer.
# Phase 8's evals re-measure this on the real corpus, which is where the number
# that actually matters comes from.
MIN_RRF_SCORE = 0.02

# Absolute backstop only. With fusion a NaN vector distance is the one thing that
# cannot be scored sensibly, and it is caught in the filter below.
MAX_DISTANCE = 1.2


@dataclass(frozen=True)
class RetrievedChunk:
    source_path: str
    heading: str
    content: str
    distance: float
    rrf_score: float = 0.0

    def to_dict(self) -> dict[str, str | float]:
        return {
            "source_path": self.source_path,
            "heading": self.heading,
            "content": self.content,
            "score": round(self.rrf_score, 5),
        }


# Both retrievers run in the same statement so a round trip is one, not two, and
# so they see an identical snapshot of the corpus.
_HYBRID_SQL = """
WITH vector_ranked AS (
  SELECT id, RANK() OVER (ORDER BY distance) AS rank, distance
  FROM (
    SELECT id, embedding <=> CAST(:vec AS vector) AS distance
    FROM chunks
    ORDER BY distance
    FETCH FIRST :candidates ROWS WITH TIES
  ) AS vector_candidates
),
lexical_ranked AS (
  SELECT id, RANK() OVER (ORDER BY score DESC) AS rank
  FROM (
    SELECT
      id,
      ts_rank_cd(body_tsv, websearch_to_tsquery('english', :query)) AS score
    FROM chunks
    WHERE body_tsv @@ websearch_to_tsquery('english', :query)
    ORDER BY score DESC
    FETCH FIRST :candidates ROWS WITH TIES
  ) AS lexical_candidates
)
SELECT
  c.source_path,
  c.heading,
  c.content,
  v.distance,
  COALESCE(1.0 / (:k + v.rank), 0) + COALESCE(1.0 / (:k + l.rank), 0) AS rrf_score
FROM chunks c
LEFT JOIN vector_ranked v ON v.id = c.id
LEFT JOIN lexical_ranked l ON l.id = c.id
WHERE v.id IS NOT NULL OR l.id IS NOT NULL
ORDER BY rrf_score DESC, c.id
LIMIT :limit
"""


async def search(
    query: str,
    settings: Settings,
    limit: int = DEFAULT_LIMIT,
) -> list[RetrievedChunk]:
    """Nearest chunks to `query`. Empty list when nothing is close enough.

    The empty case is a real outcome rather than an error: a recruiter asking
    "what is your favourite colour" should get nothing, and the model should then
    say it does not know. That is what the system prompt asks for, and it is
    better than a confident answer built from the least-bad chunk in the corpus.

    `websearch_to_tsquery` is deliberate over `to_tsquery`: it tolerates whatever
    a visitor types, including quotes and operators that would otherwise be a
    syntax error. A malformed query must not become a 500.
    """
    query = query.strip()
    if not query:
        return []

    vector = await embed_query_async(query, settings)
    assert_dimension(vector, settings)

    async with pool.session_scope() as session:
        rows = (
            await session.execute(
                text(_HYBRID_SQL),
                {
                    "vec": str(vector),
                    "query": query,
                    "k": float(RRF_K),
                    "candidates": CANDIDATES,
                    "limit": limit,
                },
            )
        ).fetchall()

    results = [
        RetrievedChunk(
            source_path=row.source_path,
            heading=row.heading or "",
            content=row.content,
            distance=float(row.distance) if row.distance is not None else 1.0,
            rrf_score=float(row.rrf_score),
        )
        for row in rows
        if float(row.rrf_score) >= MIN_RRF_SCORE
        # NaN would fail this comparison and reach the model as a garbage score.
        # A row the lexical retriever found but the vector retriever did not has a
        # NULL distance, which is not a failure, just an absent measurement.
        and (
            row.distance is None or (row.distance == row.distance and row.distance <= MAX_DISTANCE)
        )
    ]

    log.info(
        "retrieval",
        extra={
            "returned": len(results),
            "top_rrf": results[0].rrf_score if results else None,
        },
    )
    return results


def format_results(results: list[RetrievedChunk]) -> dict:
    """The shape a tool returns. Provenance included, so the loop can cite it.

    The blocks are delimited on purpose. Phase 3's system prompt tells the model
    that retrieved text is data, not instructions, and a model is far more willing
    to treat an explicit delimiter as a boundary than a bare paragraph.
    """
    if not results:
        return {
            "found": False,
            "sources": [],
            "note": "Nothing in the corpus matched. Say you do not know.",
        }

    blocks = []
    for i, chunk in enumerate(results, start=1):
        blocks.append(
            f"[{i}] source: {chunk.source_path} | section: {chunk.heading or 'untitled'}\n"
            f"{chunk.content}"
        )

    return {
        "found": True,
        "sources": [chunk.source_path for chunk in results],
        "results": [chunk.to_dict() for chunk in results],
        "text": "\n\n<<<END>>>\n\n".join(blocks),
    }
