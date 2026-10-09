"""Local embeddings via fastembed (ONNX).

Two facts about the model shape everything here, and both were checked against
the installed fastembed rather than assumed:

**`query_embed` does not add the BGE query instruction.** Measured on
`BAAI/bge-small-en-v1.5`, `query_embed("x")` returns byte-identical vectors to
`embed("x")`, while `embed("Represent this sentence for searching relevant
passages: x")` returns something different. The prefix is applied manually below.
Trusting `query_embed` here would have been a silent retrieval-quality loss with
no error to trace it from.

**Output is L2-normalised already** (measured norm 1.0000001), which is what makes
`<=>` cosine distance correct against rows stored by this same code.

## Why fastembed and not sentence-transformers

sentence-transformers pulls in PyTorch, which is roughly 800 MB of wheel and
several hundred MB of resident memory. Render free gives 512 MB total for the
container. ONNX is ~67 MB and needs no autograd runtime. That was the whole
decision.

## Why one worker thread

ONNX defaults to one thread per core. On a 2-core Render box that is two threads
fighting for the 0.1 CPU the free tier allots, which makes every embedding slower
than running it on one. `OMP_NUM_THREADS=1` is set in `.env` for the same reason.
"""

import asyncio
from collections.abc import Sequence
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

# BGE's instruction for the query side only. The model card is explicit: this
# goes on queries, never on passages. Applied by hand because fastembed's
# `query_embed` does not do it.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_model: Any = None


def get_model(model_name: str) -> Any:
    """Load the ONNX model once, on first use.

    Lazy because loading costs ~1.5s and ~120 MB. If it happened at import, every
    process start would pay it — including the ingest batch job, the test suite,
    and any command that only wants settings.
    """
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        log.info("loading embedding model", extra={"model": model_name})
        _model = TextEmbedding(model_name=model_name, threads=1)
        log.info("embedding model ready")
    return _model


def reset_model() -> None:
    """Drop the cached model. Tests use this."""
    global _model
    _model = None


def is_bge(model_name: str) -> bool:
    return model_name.lower().startswith("baai/bge")


def embed_documents(texts: Sequence[str], settings: Settings) -> list[list[float]]:
    """Embed corpus passages. No query instruction, per the model card."""
    if not texts:
        return []
    model = get_model(settings.embedding_model)
    return [list(map(float, vector)) for vector in model.embed(list(texts))]


def embed_query(text: str, settings: Settings) -> list[float]:
    """Embed one query, with the BGE instruction when the model wants it.

    Async because this is called from inside a streaming request: ONNX holds the
    CPU for tens of milliseconds per call, and doing that on the event loop would
    stall every other visitor's stream.
    """
    payload = BGE_QUERY_INSTRUCTION + text if is_bge(settings.embedding_model) else text
    model = get_model(settings.embedding_model)
    return [list(map(float, vector)) for vector in model.embed([payload])][0]


async def embed_query_async(text: str, settings: Settings) -> list[float]:
    """`embed_query` off the event loop."""
    return await asyncio.to_thread(embed_query, text, settings)


async def embed_documents_async(texts: Sequence[str], settings: Settings) -> list[list[float]]:
    """`embed_documents` off the event loop."""
    return await asyncio.to_thread(embed_documents, texts, settings)


def assert_dimension(vector: Sequence[float], settings: Settings) -> None:
    """Fail loudly on a model that does not match the schema.

    A 768-dimension vector against a `vector(384)` column raises at insert time
    with a message about dimensions rather than about models. This says the actual
    cause, in the place where the mistake was made.
    """
    actual = len(vector)
    if actual != settings.embedding_dimensions:
        raise ValueError(
            f"{settings.embedding_model} produced {actual} dimensions but the "
            f"schema declares {settings.embedding_dimensions}. Either the model "
            f"setting or the migration is wrong, and the corpus must be re-ingested "
            f"after fixing it."
        )


def is_zero_vector(vector: Sequence[float], tolerance: float = 1e-8) -> bool:
    """Whether an embedding carries no direction at all.

    Cosine distance against a zero vector is NaN, which does not sort — it
    poisons the ranking for every row it touches. An empty chunk is the obvious way
    to produce one, so the ingest refuses to store them.
    """
    return all(abs(component) <= tolerance for component in vector)
