"""Specification tests for `app/core/tracing.py`.

ADR 0010 is the boundary this module holds: nothing leaves the process unless
keys are configured, and what leaves is shape (counts, durations, class), never
words. The tests below pin both halves offline — a fake recorder stands in for
the exporter, and no test here ever touches a network.
"""

import pytest

from app.core import tracing


class RecordingSpan:
    """A stand-in span: records calls, never talks to anything."""

    def __init__(self, recorder: list, name: str, **kwargs) -> None:
        self.recorder = recorder
        recorder.append(("open", name, kwargs))

    def start_observation(self, name: str = "", **kwargs):
        return RecordingSpan(self.recorder, name, **kwargs)

    def update(self, **kwargs):
        self.recorder.append(("update", kwargs))
        return self

    def end(self):
        self.recorder.append(("end",))
        return self


@pytest.fixture
def no_keys(monkeypatch):
    """The default checkout: no Langfuse keys. The settings fixture in the
    repo's autouse fixture already clears the cache for each test."""
    settings = tracing.get_settings()
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")


@pytest.fixture
def recorder(monkeypatch):
    """Keys are set and the exporter is a recorder. `start_observation`
    results land in a list the assertions read."""
    record: list = []

    class Factory:
        def start_observation(self, name: str = "", **kwargs):
            return RecordingSpan(record, name, **kwargs)

        def flush(self):
            record.append(("flush",))

    settings = tracing.get_settings()
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr(tracing, "_langfuse", lambda: Factory())
    return record


async def test_without_keys_nothing_is_constructed_nothing_is_sent(no_keys) -> None:
    """The no-op path is the release's default: no client, no span, no work."""
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.langfuse_enabled is False

    trace = tracing.TurnTrace()
    assert trace._span is None, "no keys means no span"

    # Every method is a guard on the same None: they must not raise, and there
    # is no other observable effect to assert for a no-op.
    trace.leg(0.1, 12, 34)
    trace.tool("search_portfolio", ok=True, seconds=0.5)
    trace.finish(1, 220)


async def test_an_enabled_turn_records_its_shape(recorder) -> None:
    """Leg usage, tool class, presence counts, one flush — never words."""

    from app.core.config import get_settings

    assert get_settings().langfuse_enabled is True

    trace = tracing.TurnTrace()
    trace.leg(1.234, 120, 45)
    trace.tool("search_portfolio", ok=False, seconds=0.5)
    trace.finish(2, 1370)

    opens = [entry for entry in recorder if entry[0] == "open"]
    names = [entry[1] for entry in opens]
    assert "chat-turn" in names
    assert "provider-leg" in names
    assert "search_portfolio" in names

    # Tokens arrive in the usage details, as ints, as reported by the adapter.
    leg = [entry for entry in opens if entry[1] == "provider-leg"][0]
    assert leg[2]["usage_details"] == {"input": 120, "output": 45}

    # A failed tool is an ERROR-level child of the turn.
    tool = [entry for entry in opens if entry[1] == "search_portfolio"][0]
    assert tool[2]["as_type"] == "tool"
    assert tool[2]["level"] == "ERROR"

    # The finish is presence and length. There is no text field.
    finish = [entry for entry in recorder if entry[0] == "update"]
    assert finish, "the turn span must be updated before it closes"
    metadata = finish[-1][1]["metadata"]
    assert metadata["sources_present"] is True
    assert metadata["sources_count"] == 2
    assert metadata["text_length"] == 1370
    assert "projects.md" not in str(metadata)  # names pass as counts, not lists

    assert ("end",) in recorder
    assert ("flush",) in recorder  # one flush per turn: spin-downs must not eat it


async def test_a_broken_exporter_never_breaks_the_turn(recorder, monkeypatch) -> None:
    """Tracing is a side quest. A raise inside it logs and moves on."""

    def explode(*args, **kwargs):
        raise RuntimeError("exporter is having a day")

    monkeypatch.setattr(tracing, "_langfuse", explode)

    trace = tracing.TurnTrace()
    assert trace._span is None  # construction swallowed it

    # And a span that dies mid-turn does not take the loop down either.
    monkeypatch.setattr(
        tracing, "_langfuse", lambda: type("X", (), {"start_observation": explode})()
    )

    trace2 = tracing.TurnTrace()
    trace2.leg(0.1, 1, 1)
    trace2.tool("x", ok=True, seconds=0.0)
    trace2.finish([], 0)
