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
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file(_API_ROOT / ".env")
