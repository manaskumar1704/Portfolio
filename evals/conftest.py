"""Evals bootstrap: put `apps/api` on the path and load its environment.

The evals run from the repo root (`uv run --project apps/api pytest evals`),
which means the app's own `.env` is not discovered by `pydantic-settings` — it
resolves `env_file` relative to the process cwd. Loading it here is what makes
`DATABASE_URL` and `GEMINI_API_KEY` reach `get_settings()`. Existing environment
variables always win, so CI can inject secrets instead.
"""

import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(_API_ROOT))


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    # utf-8-sig, not utf-8: a BOM on the file's first line would otherwise
    # become part of the first key's name.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        # Mirror python-dotenv's parser, which pydantic-settings uses to load
        # this same file for the API suite: a quoted value reads to its
        # closing quote; a bare value ends at the first whitespace-preceded
        # '#', so inline comments survive the API suite but must be dropped
        # here too (DAILY_SEND_CAP=70   # ...100/day once failed int parsing).
        v = value.strip()
        if v[:1] in ('"', "'"):
            end = v.find(v[0], 1)
            v = v[1:end] if end > 0 else v[1:]
        elif " #" in v:
            v = v.split(" #", 1)[0].strip()
        os.environ.setdefault(key.strip(), v)


_load_env_file(_API_ROOT / ".env")
