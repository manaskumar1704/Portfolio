"""Connector seam: the fixture classes satisfy their Protocols, and the shapers
turn every failure shape into data.

The point is the contract, not the service: when the real HTTP implementations
are written they will feed the same shapers, so whatever behaviour a test pins
here — a timeout is a verdict that says unsupported, a non-200 is never a
raise, a flood of hits is capped — is behaviour the wire path inherits or must
visibly change.
"""

import pytest

from app.services.connectors import (
    HIT_COUNT_MAX,
    HIT_TEXT_MAX_CHARS,
    NOTE_MAX_CHARS,
    FixtureJobFinder,
    FixtureThirdBrain,
    JobFinderConnector,
    ThirdBrainConnector,
    shape_hits,
    shape_verdict,
)


# --- The Protocols are satisfied by the fixtures ------------------------------


def test_the_fixture_connectors_satisfy_their_protocols() -> None:
    """The swap Claim: replacing the fixture class cannot break call sites that
    were written against the Protocol. `runtime_checkable` pins the shape."""
    assert isinstance(FixtureJobFinder(), JobFinderConnector)
    assert isinstance(FixtureThirdBrain(), ThirdBrainConnector)


# --- The fixture replies are labelled and capped ------------------------------


async def test_the_fixture_verdict_names_its_provider() -> None:
    verdict = await FixtureJobFinder().verify_grounding("an answer", ["a snippet"])

    assert verdict.supported is True
    assert verdict.provider == "jobfinder"
    assert "fixture" in verdict.note


async def test_fixture_hits_are_labelled() -> None:
    reply = await FixtureThirdBrain().search("anything")

    assert reply.error is None
    assert reply.hits
    for hit in reply.hits:
        assert hit.source == "thirdbrain"
        assert 0 < len(hit.text) <= HIT_TEXT_MAX_CHARS


async def test_the_search_limit_is_respected() -> None:
    whole = await FixtureThirdBrain().search("anything")
    capped = await FixtureThirdBrain().search("anything", limit=1)

    assert capped.hits == whole.hits[:1]


async def test_a_zero_limit_means_no_hits() -> None:
    reply = await FixtureThirdBrain().search("anything", limit=0)

    assert reply.hits == ()
    assert reply.error is None


# --- Every failure shape is data ---------------------------------------------


async def test_a_timeout_is_a_verdict_that_says_unsupported() -> None:
    verdict = shape_verdict("jobfinder", failure="the service timed out after 30 seconds")

    assert verdict.supported is False
    assert verdict.provider == "jobfinder"
    assert "timed out" in verdict.note
    assert len(verdict.note) <= NOTE_MAX_CHARS


async def test_a_non_200_is_never_a_raise() -> None:
    verdict = shape_verdict("jobfinder", failure="the service answered with HTTP 503")

    assert verdict.supported is False
    assert "HTTP 503" in verdict.note


async def test_malformed_json_never_counts_as_support() -> None:
    """A `supported` that is not a boolean is worthless, however confident it sounds."""
    for payload in ({"supported": "certain"}, {"supported": None}, ["not even a dict"], None):
        verdict = shape_verdict("jobfinder", payload)
        assert verdict.supported is False


async def test_a_waffle_note_with_a_real_verdict_survives() -> None:
    """Where the service did answer, its words — capped — are the note."""
    verdict = shape_verdict(
        "jobfinder", {"supported": True, "note": "x" * (NOTE_MAX_CHARS + 50)}
    )

    assert verdict.supported is True
    assert "[truncated, " in verdict.note
    assert verdict.note.endswith("characters total]")


async def test_a_search_failure_is_an_empty_list_with_a_reason() -> None:
    reply = shape_hits("thirdbrain", failure="connection reset by peer")

    assert reply.hits == ()
    assert reply.error is not None
    assert "connection reset" in reply.error


async def test_a_malformed_search_reply_is_never_halfness() -> None:
    """A list whose middle entry is garbage is refused whole, not cut in half."""
    payload = [
        {"label": "ok.md", "text": "fine so far"},
        {"label": None, "text": 42},
    ]

    reply = shape_hits("thirdbrain", payload)

    assert reply.hits == ()
    assert "malformed" in (reply.error or "")


async def test_a_flood_of_hits_is_capped() -> None:
    payload = [
        {"label": "note.md", "text": "long" * (HIT_TEXT_MAX_CHARS // 2)}
    ] * (HIT_COUNT_MAX * 8)

    reply = shape_hits("thirdbrain", payload)

    assert len(reply.hits) == HIT_COUNT_MAX
    for hit in reply.hits:
        # The body is capped; the marker that says the cap happened follows it,
        # in the same convention `clean_readme` uses.
        body, marker = hit.text.rsplit("\n[truncated, ", 1)
        assert len(body) == HIT_TEXT_MAX_CHARS
        assert marker.endswith("characters total]")
        assert hit.source == "thirdbrain"
