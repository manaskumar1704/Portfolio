"""Response models for the read-only portfolio endpoints.

These mirror `apps/web/src/lib/api/types.ts` field for field. The frontend is
running on fixtures today and swaps to these without touching a component, so
a rename here is a rename there. If you change one, change both, and the test
in `tests/test_contracts.py` will tell you.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ProjectStatus = Literal["completed", "running", "soon"]


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: ProjectStatus
    label: str
    meta: str
    desc: str
    stack: str


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    github: str
    linkedin: str
    note: str


class FsDir(BaseModel):
    """A directory in the browsable corpus. Mirrors the `FsDir` union arm."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["dir"] = "dir"
    children: dict[str, "FsNode"]


class FsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["file"] = "file"
    body: str


FsNode = FsDir | FsFile

# Resolved once so `children: dict[str, FsNode]` above can refer to itself.
FsDir.model_rebuild()
