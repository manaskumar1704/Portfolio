"""Retrieval, against the live database and the fixture corpus.

Integration tests, because the question "does this corpus retrieve the right
chunk" cannot be answered by a mock — the whole point is the ranking that comes
out of Postgres, the embedding model, and the fusion.

Fixture facts, deliberately absurd so a wrong answer is obvious. Anything
retrieving Lantern Analytics for a pasta recipe is failing.
"""

import pytest

from app.core.config import get_settings
from app.db import pool
from app.services import rag

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set"),
]


@pytest.fixture
async def ready_db():
    await pool.setup(get_settings())
    try:
        yield pool
    finally:
        await pool.teardown()


@pytest.fixture(scope="module")
def settings():
    return get_settings()


async def top(query: str, settings, limit: int = 4) -> str | None:
    hits = await rag.search(query, settings, limit=limit)
    return hits[0].source_path if hits else None


# --- Precision: the right file wins -----------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("what certifications does he have?", "certifications.md"),
        ("where is he based?", "contact.md"),
        ("what is his email?", "contact.md"),
        ("what does Harbour do?", "projects.md"),
        ("what did he do at Cardinal Health?", "resume.md"),
    ],
)
async def test_on_topic_questions_find_the_right_file(ready_db, settings, query, expected) -> None:
    assert await top(query, settings) == expected


@pytest.mark.parametrize(
    "query",
    [
        "what is his favourite colour?",
        "how tall is the Eiffel Tower?",
        "recommend a good pasta recipe",
        "who won the 2019 world cup?",
        "what is the capital of Australia?",
        "explain quantum entanglement",
        "what is his star sign?",
    ],
)
async def test_off_topic_questions_return_nothing(ready_db, settings, query) -> None:
    """The property hybrid retrieval bought.

    Dense-only retrieval could not do this: measured before the change, off-topic
    questions scored *closer* than on-topic ones. Returning nothing is what lets
    the agent say "I don't know" rather than answering from the least-bad chunk.
    """
    assert await rag.search(query, settings) == []


# --- Behaviour ---------------------------------------------------------------


async def test_empty_query_short_circuits(ready_db, settings) -> None:
    assert await rag.search("   ", settings) == []


async def test_odd_punctuation_does_not_raise(ready_db, settings) -> None:
    """`websearch_to_tsquery` is chosen precisely so this cannot 500."""
    assert await rag.search('what about "quoted" & <odd> chars?', settings) is not None


async def test_limit_is_respected(ready_db, settings) -> None:
    assert len(await rag.search("experience and projects", settings, limit=2)) <= 2


async def test_results_carry_their_source(ready_db, settings) -> None:
    """Citation needs the source path on every hit, not just the first."""
    hits = await rag.search("what is his email?", settings)

    assert hits
    assert all(hit.source_path.endswith(".md") for hit in hits)


async def test_lexical_only_question_is_still_found(ready_db, settings) -> None:
    """ "What is his email?" has no semantic overlap with the contact file.

    This is the case dense retrieval failed and the reason the lexical retriever
    exists, so it is pinned as a test rather than left to a comment.
    """
    hits = await rag.search("wren.ashby@example.invalid", settings)

    assert any("contact" in hit.source_path for hit in hits)


# --- Formatting --------------------------------------------------------------


def test_format_results_when_empty() -> None:
    formatted = rag.format_results([])

    assert formatted["found"] is False
    assert formatted["sources"] == []
    assert "do not know" in formatted["note"]


def test_format_results_delimits_blocks() -> None:
    """Retrieved text is data, not instructions. The delimiter is the hint."""
    chunks = [
        rag.RetrievedChunk("resume.md", "Experience", "text", 0.4, 0.03),
        rag.RetrievedChunk("projects.md", "Harbour", "more", 0.5, 0.02),
    ]

    formatted = rag.format_results(chunks)

    assert formatted["found"] is True
    assert formatted["sources"] == ["resume.md", "projects.md"]
    assert "<<<END>>>" in formatted["text"]
    assert "[1] source: resume.md" in formatted["text"]


def test_format_results_omits_the_distance_when_scoring_by_rank() -> None:
    """Rank fusion is the score now; a raw cosine distance would mislead."""
    chunk = rag.RetrievedChunk("a.md", "h", "c", 0.42, 0.03)

    assert "distance" not in chunk.to_dict()
    assert chunk.to_dict()["score"] == 0.03


async def test_rrf_gate_rejects_single_retriever_agreement(ready_db, settings) -> None:
    """k=60 puts one retriever at 0.0164 and both at 0.0328.

    The gate is what makes "found: false" mean the corpus had nothing, rather than
    that the least-bad chunk scored below an arbitrary number.
    """
    hits = await rag.search("what certifications does he have?", settings)

    assert hits
    assert all(hit.rrf_score >= rag.MIN_RRF_SCORE for hit in hits)
