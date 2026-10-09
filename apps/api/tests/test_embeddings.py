"""Embedding behaviour that does not need the database.

These run the real ONNX model, so they are slower than the rest of the suite and
they are marked. What they check is the part that cannot be tested with a fake:
whether the model agrees with the schema, and whether the query instruction is
actually applied. Both were found to be wrong by measurement, not by reading.
"""

import pytest

from app.core.config import get_settings
from app.services.embeddings import (
    BGE_QUERY_INSTRUCTION,
    assert_dimension,
    embed_documents,
    embed_query,
    is_bge,
    is_zero_vector,
)

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def settings():
    return get_settings()


def test_document_embeddings_are_unit_length(settings) -> None:
    """Cosine distance is only correct against normalised vectors."""
    import math

    vector = embed_documents(["a passage about search ranking"], settings)[0]

    norm = math.sqrt(sum(component * component for component in vector))
    assert norm == pytest.approx(1.0, abs=1e-4)


def test_documents_produce_the_declared_dimension(settings) -> None:
    vector = embed_documents(["anything"], settings)[0]

    assert len(vector) == settings.embedding_dimensions == 384


def test_queries_use_the_instruction_and_documents_do_not(settings) -> None:
    """The one that matters most, and the one that was silently wrong.

    Measured on this model: `fastembed`'s `query_embed` returns byte-identical
    vectors to `embed`, so the instruction has to be added by hand. If this test
    ever fails, the two sides are being embedded the same way and retrieval
    quality drops with no error anywhere.
    """

    from app.services.embeddings import get_model

    model = get_model(settings.embedding_model)
    query = "what did they work on?"
    vectors = list(model.embed([query, BGE_QUERY_INSTRUCTION + query]))

    plain, prefixed = vectors[0], vectors[1]
    assert plain != pytest.approx(prefixed, abs=1e-6), "prefix is not changing the vector"

    # And our own query path must match the prefixed side.
    assert embed_query(query, settings) == pytest.approx(prefixed, abs=1e-5)


def test_fastembed_query_embed_does_not_add_the_instruction(settings) -> None:
    """The behaviour this module works around, pinned so it cannot change quietly."""
    from app.services.embeddings import get_model

    model = get_model(settings.embedding_model)
    query = "a query about latency"

    via_query_embed = list(model.query_embed([query]))[0]
    via_embed = list(model.embed([query]))[0]

    assert list(map(float, via_query_embed)) == pytest.approx(list(map(float, via_embed)), abs=1e-6)


def test_semantically_related_text_is_closer_than_unrelated(settings) -> None:
    """A smoke test that the model loaded and is doing something useful."""

    query = embed_query("which company did they work at first?", settings)
    corpus = embed_documents(
        [
            "Wren worked at Tidewater Analytics as their first engineering role.",
            "Tidewater Analytics was Wren's first job, 2017 to 2019.",
            "The recipe calls for two cups of flour and a pinch of salt.",
        ],
        settings,
    )

    def distance(a, b) -> float:
        return 1 - sum(x * y for x, y in zip(a, b, strict=True))

    relevant = min(distance(query, corpus[0]), distance(query, corpus[1]))
    unrelated = distance(query, corpus[2])

    assert relevant < unrelated


def test_empty_input_produces_no_embeddings(settings) -> None:
    assert embed_documents([], settings) == []


def test_dimension_mismatch_is_named_clearly(settings) -> None:
    """The error should mention the model, not just the number."""
    with pytest.raises(ValueError, match="bge-small"):
        assert_dimension([0.1] * 768, settings)


def test_matching_dimension_passes(settings) -> None:
    assert assert_dimension([0.1] * 384, settings) is None


def test_zero_vectors_are_detected() -> None:
    """Cosine distance against one is NaN, which does not sort."""
    assert is_zero_vector([0.0] * 384) is True
    assert is_zero_vector([0.0] * 383 + [1e-12]) is True
    assert is_zero_vector([0.1] * 384) is False


def test_is_bge_only_matches_bge() -> None:
    assert is_bge("BAAI/bge-small-en-v1.5") is True
    assert is_bge("baai/bge-base-en") is True
    assert is_bge("sentence-transformers/all-MiniLM-L6-v2") is False
