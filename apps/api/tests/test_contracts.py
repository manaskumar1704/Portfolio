"""The frontend contract, pinned.

`apps/web/src/lib/api/types.ts` is the source of truth for what the frontend
expects. The fixtures in `lib/api` are typed against it, so when these schemas
drift the frontend breaks at build time in a way no Python test would catch.

This reads the TypeScript and compares names, so a rename on either side fails
here rather than in the browser. It is a name check, not a type check: enough to
catch drift, not enough to become a TypeScript parser.

## What replaced the event models

Phase 3 documented the SSE wire format with seven Pydantic models that nothing
used and that drifted — `DraftEvent` had no `expires_at`, `DoneEvent` had no
`text_length`. A model that is never validated and is missing fields reads as
the contract while being wrong.

`test_every_emitted_event_is_declared_by_the_frontend` replaces them, and it is
live in a way they never were: it reads the event names straight out of the
source that emits them. Adding an event to `chat.py` without adding it to
`types.ts` fails here.
"""

import re
from pathlib import Path

import pytest

from app.schemas.portfolio import Contact, Project

WEB_SRC = Path(__file__).resolve().parents[2] / "web/src"
TYPES_TS = WEB_SRC / "lib/api/types.ts"

# The emitter side, and the frontend's own copy of the list.
EMITTERS = (
    WEB_SRC.parents[1] / "api/app/services/chat.py",
    WEB_SRC.parents[1] / "api/app/api/chat.py",
)

# `unknown` is the frontend's own escape hatch: an event name it does not know
# becomes this rather than throwing. It is not emitted by the backend.
FRONTEND_ONLY = {"unknown"}


def _ts_fields(type_name: str) -> list[str]:
    """Field names declared for `export type <type_name> = { ... }`."""
    text = TYPES_TS.read_text(encoding="utf-8")
    match = re.search(
        rf"export type {type_name} = \{{(.*?)\}}",
        text,
        re.DOTALL,
    )
    assert match, f"{type_name} not found in {TYPES_TS}"
    return re.findall(r"^\s*(\w+)\??:", match.group(1), re.MULTILINE)


@pytest.mark.parametrize(
    ("model", "type_name"),
    [(Contact, "Contact"), (Project, "Project")],
)
def test_schema_matches_typescript(model: type, type_name: str) -> None:
    assert sorted(model.model_fields) == sorted(_ts_fields(type_name))


def test_project_status_literals_match() -> None:
    """The three statuses are a closed set on both sides, not a free string."""
    text = TYPES_TS.read_text(encoding="utf-8")
    match = re.search(r"export type ProjectStatus =([^;]+);", text)
    assert match, "ProjectStatus not found"
    # A TypeScript union of string literals: "a" | "b" | "c".
    ts_values = set(re.findall(r'"(\w+)"', match.group(1)))
    py_values = set(Project.model_fields["status"].annotation.__args__)
    assert py_values == ts_values


def _emitted_event_names() -> set[str]:
    """Every event name the backend actually emits.

    Read from the source rather than from a list, which is the entire point: a
    new `StreamEvent("thing", ...)` in `chat.py` shows up here without anyone
    editing a test.
    """
    pattern = re.compile(r'StreamEvent\(\s*\n?\s*"(\w+)"')
    found: set[str] = set()
    for path in EMITTERS:
        found |= set(pattern.findall(path.read_text(encoding="utf-8")))
    return found


def _declared_event_kinds() -> set[str]:
    """Every `kind` in the frontend's `ChatEvent` union.

    Matches on `kind: "name"` anywhere in the union rather than trying to split
    it on `;` — the union spans multiple lines and one member is itself a
    multi-line object literal, so a terminator-based split stops early.
    """
    text = TYPES_TS.read_text(encoding="utf-8")
    start = text.index("export type ChatEvent =")
    # The union ends at the next `export type` at column zero.
    end = text.index("\nexport ", start + 1)
    return set(re.findall(r'kind:\s*"(\w+)"', text[start:end]))


def test_the_backend_emits_at_least_one_event() -> None:
    """Guards the regex in the test below.

    A pattern that matches nothing would make the drift test pass vacuously —
    exactly the failure mode that let the seven unused event models sit here
    claiming to be the contract.
    """
    assert len(_emitted_event_names()) >= 8, _emitted_event_names()


def test_every_emitted_event_is_declared_by_the_frontend() -> None:
    """The live replacement for the deleted event models."""
    emitted = _emitted_event_names()
    declared = _declared_event_kinds() - FRONTEND_ONLY

    assert emitted == declared, (
        f"the backend emits {sorted(emitted)} but the frontend declares {sorted(declared)}. "
        "An event the frontend has no branch for is dropped on the floor."
    )


def test_the_frontend_declares_no_event_the_backend_never_sends() -> None:
    """The other direction.

    A kind the frontend handles but the backend never emits is usually a rename
    that was applied to one side only — which is how `DraftEvent` ended up
    without `expires_at` and nobody noticed for two phases.
    """
    declared = _declared_event_kinds() - FRONTEND_ONLY
    emitted = _emitted_event_names()

    assert not (declared - emitted), f"frontend-only event kinds: {sorted(declared - emitted)}"


def test_the_draft_event_carries_the_approval_token() -> None:
    """The load-bearing field, and the one whose absence is silent.

    Without it the approve button is rendered and does nothing, and no test
    fails — the 403 arrives at runtime from a visitor's browser.
    """
    text = TYPES_TS.read_text(encoding="utf-8")
    draft = text[text.index('kind: "draft"') :]
    draft = draft[: draft.index("\n  |")]

    assert "approvalToken" in draft, "the draft event lost its approval token"
    assert "approval_token" not in draft, "the frontend must use the camelCase spelling"
    assert "senderEmail: string" in draft, "the draft event names the visitor's address senderEmail (decision 6)"
    assert "email: string" not in draft, "the old short name must not survive in the event"


# `done` is the only multi-field event both emitters build by hand, and fields
# arrive or disappear by editing a dict literal, not by renaming a key. So the
# name-level check above is not enough for it: pin the exact field set.
DONE_FIELDS = {"sources", "text_length", "sources_verified"}


def test_every_done_emission_carries_the_full_field_set() -> None:
    """Both emitters, pinned to the same dict shape.

    The fallback exists for the request that dies mid-stream; if it drifted from
    the service's shape, an interrupted answer would decode differently from a
    complete one and only in that case. `[^}]*?` holds because neither emission
    has a nested brace.
    """
    for path in EMITTERS:
        match = re.search(
            r'StreamEvent\(\s*"done",\s*\{([^}]*?)\}\s*,?\s*\)',
            path.read_text(encoding="utf-8"),
        )
        assert match is not None, f"no done emission found in {path}"
        keys = set(re.findall(r'"(\w+)":', match.group(1)))
        assert keys == DONE_FIELDS, f"{path.name} emits {sorted(keys)}"


# The `draft` event gets the same treatment as `done`: it is built by hand in a
# dict literal, and decision 6 renamed exactly one key at the wire — the visitor
# address. The emitter is the side that must not quietly revert to `email`.
DRAFT_FIELDS = {"id", "name", "sender_email", "body", "approval_token", "expires_at"}


def test_every_draft_emission_carries_the_full_field_set() -> None:
    """Whoever emits a draft event spells the address sender_email.

    The tool *result* keeps `email` — the model-facing argument, unchanged —
    while the event the browser sees renames. Both spellings therefore exist in
    `services/chat.py` and only one of them is wrong inside a `StreamEvent`.
    """
    found = False
    for path in EMITTERS:
        source = path.read_text(encoding="utf-8")
        for payload in re.findall(
            r'StreamEvent\(\s*"draft",\s*\{([^}]*?)\}\s*,?\s*\)', source
        ):
            found = True
            keys = set(re.findall(r'"(\w+)":', payload))
            assert keys == DRAFT_FIELDS, f"{path.name} emits {sorted(keys)}"

    assert found, "no draft emission found in any emitter"


def test_the_frontend_declares_sources_verified_as_a_boolean() -> None:
    """The badge's contract field: declared once, spelled camelCase, bool."""
    text = TYPES_TS.read_text(encoding="utf-8")
    done = text[text.index('kind: "done"') : text.index("\n  |", text.index('kind: "done"'))]

    assert "sourcesVerified" in done
    assert "sources_verified" not in done, "the frontend must use the camelCase spelling"
    assert "boolean" in done
