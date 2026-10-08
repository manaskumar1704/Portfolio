"""The frontend contract, pinned.

`apps/web/src/lib/api/types.ts` is the source of truth for what the frontend
expects. The fixtures in `lib/api` are typed against it, so when these schemas
drift the frontend breaks at build time in a way no Python test would catch.

This reads the TypeScript and compares field names, so a rename on either side
fails here rather than in the browser. It is a name check, not a type check:
enough to catch drift, not enough to become a TypeScript parser.
"""

import re
from pathlib import Path

import pytest

from app.schemas.chat import ChatReply
from app.schemas.portfolio import Contact, Project

TYPES_TS = Path(__file__).resolve().parents[2] / "web/src/lib/api/types.ts"


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
    [(ChatReply, "ChatReply"), (Contact, "Contact"), (Project, "Project")],
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
