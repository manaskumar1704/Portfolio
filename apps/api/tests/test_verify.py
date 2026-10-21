"""Source verification: the interface's no-wire default, and the path check.

The default-False test lives in `test_chat_loop.py` next to the loop that
emits the field; this file owns `CorpusPathVerifier`, which is an integration
test by nature — "does the query resolve against the live schema" is the thing
a mock cannot answer.
"""

import pytest

from app.core.config import get_settings
from app.db import pool
from app.services import verify
from app.services.verify import CorpusPathVerifier, SourceVerifier

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set"),
]


def test_the_path_verifier_satisfies_the_protocol() -> None:
    """Type-level: the check that ships can sit behind the same seam as the
    future NLI service (ADR 0008)."""
    assert isinstance(CorpusPathVerifier(), SourceVerifier)


async def test_a_path_that_was_ingested_verifies(ready_db) -> None:
    """A real ingested path is the only thing that earns True from this check."""
    async with pool.session_scope() as session:
        from sqlalchemy import text

        known = (
            await session.execute(
                text("SELECT DISTINCT source_path FROM chunks ORDER BY source_path LIMIT 1")
            )
        ).scalar_one()

    verdict = await CorpusPathVerifier().verify("an answer", [known])

    assert verdict.verified is True
    assert verdict.checker == "corpus_path"


async def test_a_path_that_was_never_ingested_is_refused(ready_db) -> None:
    verdict = await CorpusPathVerifier().verify("an answer", ["corpus/imagination.md"])

    assert verdict.verified is False
    assert "not in the corpus" in verdict.note


async def test_no_citations_is_a_refusal_not_an_error(ready_db) -> None:
    """An answer that cited nothing cannot be verified by a path check."""
    verdict = await CorpusPathVerifier().verify("an answer", [])

    assert verdict.verified is False
    assert "no sources" in verdict.note


async def test_the_query_failing_fails_closed(ready_db, monkeypatch) -> None:
    """The verifier contract: results, never raises, even when the pool breaks."""

    class BrokenPool:
        def session_scope(self):  # matches pool.session_scope's signature
            raise RuntimeError("pool is closed")

    # Point the module's pool binding at a broken one; monkeypatch restores the
    # real engine afterwards. The real engine is untouched.
    monkeypatch.setattr(verify, "pool", BrokenPool())

    verdict = await CorpusPathVerifier().verify("an answer", ["resume.md"])

    assert verdict.verified is False
    assert "failed" in verdict.note
