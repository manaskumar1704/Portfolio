"""Retrieval eval: the golden set over the fixture corpus.

Offline and fast — no model calls except the local embedding, no LLM. This is
the layer where a regression shows up as a *retrieval* miss rather than as a
downstream phrasing difference, which is precisely what a golden set is for.

## The two graded behaviours

- **Supported questions land on the right file.** The graded claim is the
  tool's own: `search_portfolio` returns up to `DEFAULT_LIMIT` chunks and the
  right file must be among them. Top-4 membership, not rank 1 — the model gets
  all four and cites what it used.
- **Off-topic questions return nothing.** `found: false` is the contract the
  system prompt teaches the model to treat as "say you do not know". The RRF
  gate (`MIN_RRF_SCORE`) is what makes that possible; these cases are the ones
  the gate was measured on.

Known near-misses, documented and deliberately excluded from the golden set:
paraphrases with no shared vocabulary ("which company did he work at first?")
score below the gate. They are the corpus's *known* recall limit, recorded in
`app/services/rag.py` and in the decisions log, not acceptable eval cases —
putting them here as passes would heat the gate.
"""

import pytest

from app.core.config import get_settings
from app.db import pool
from app.services import rag

pytestmark = [
    pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set"),
]


@pytest.fixture
async def ready_db():
    await pool.setup(get_settings())
    try:
        yield pool
    finally:
        await pool.teardown()


@pytest.fixture
def settings():
    return get_settings()


# (question, the file(s) that answering it depends on)
#
# The wordings are deliberately lean. Lexical retrieval is AND semantics: one
# query word the corpus does not carry (e.g. adding "rate" to a question about
# click-through) empties the lexical leg, and then dense-only RRF scores
# 1/61 = 0.0164, under the gate. So a question not in the corpus's own
# vocabulary can honestly score `found: false` — the known near misses are
# documented beside `MIN_RRF_SCORE`, and this set pins the corpus-literal
# phrasings a visitor could reasonably type rather than every conceivable
# paraphrase.
ON_TOPIC = [
    ("what is his email address?", ["contact.md"]),
    # The persona's name, from the other side: the site says "Manas", the docs
    # say "Wren Ashby". contact.md carries the bridge sentence, so a query that
    # includes the name still lands on the file that holds the fact — the
    # phrasing a visitor types most often is after all the one the corpus never
    # spells out otherwise.
    ("what is manas's email address?", ["contact.md"]),
    ("current company and designation", ["naukri-snapshot.md"]),
    ("professional data engineer certificate", ["certifications.md"]),
    ("query plan into a diff tool", ["projects.md"]),
    ("click-through top ten results", ["resume.md"]),
    ("where is he based?", ["contact.md"]),
    ("what is on his linkedin profile?", ["linkedin-snapshot.md"]),
    ("what does he say about working style?", ["about.md"]),
]

# Questions nothing in the corpus answers. The right behaviour is empty.
OFF_TOPIC = [
    "what is his favourite pasta recipe?",
    "does he play chess competitively?",
    "which football team does he support?",
    "what is his opinion on electric scooters?",
    "can you book him a meeting next tuesday?",
]


async def _paths(query: str, settings, limit: int = rag.DEFAULT_LIMIT) -> list[str]:
    return [chunk.source_path for chunk in await rag.search(query, settings, limit=limit)]


@pytest.mark.parametrize(("question", "expected_files"), ON_TOPIC)
async def test_supported_questions_retrieve_the_right_document(
    question, expected_files, ready_db, settings
) -> None:
    paths = await _paths(question, settings)

    assert paths, f"'{question}' retrieved nothing"
    assert set(expected_files) & set(paths), (
        f"'{question}' retrieved {paths}; expected one of {expected_files}"
    )


@pytest.mark.parametrize("question", OFF_TOPIC)
async def test_off_topic_questions_retrieve_nothing(question, ready_db, settings) -> None:
    paths = await _paths(question, settings)

    assert paths == [], f"'{question}' retrieved {paths} from a corpus about a nobody"
