"""Digest past OpenCode sessions into text files, for writing a retro.

Read-only: opens the local OpenCode SQLite database, finds the project that
owns --project-dir, and writes one digest file per parent session created on
or after --since, plus prints a child-session index. Each digest holds every
user prompt and the last assistant messages — the material a retro is written
from. Exit codes: 2 = database or project not found, 1 = zero matching
sessions, 0 = digests written.

    uv run --project apps/api python scripts/retro/retro_digest.py \
        --project-dir . --since 2026-10-05 --out "$TEMP/opencode"
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
MAX_USER_SHOWN = 40      # user prompts kept per session
MAX_CHARS = 2500         # per quoted message
ASSISTANT_CLOSERS = 2    # last assistant messages kept per session


def fmt(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Digest OpenCode sessions for a project.")
    p.add_argument("--project-dir", required=True, help="directory whose sessions to mine")
    p.add_argument("--since", required=True, help="sessions created on/after YYYY-MM-DD")
    p.add_argument("--out", required=True, help="directory to write digest files into")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="path to opencode.db")
    return p.parse_args()


def find_project(con: sqlite3.Connection, project_dir: Path) -> str:
    want = str(project_dir.resolve()).replace("\\", "/").rstrip("/").lower()
    for pid, worktree in con.execute("SELECT id, worktree FROM project"):
        if worktree and worktree.replace("\\", "/").rstrip("/").lower() == want:
            return pid
    for pid, directory in con.execute("SELECT project_id, directory FROM project_directory"):
        if directory and directory.replace("\\", "/").rstrip("/").lower() == want:
            return pid
    print(f"no project in the database matches {project_dir}", file=sys.stderr)
    raise SystemExit(2)


def msg_text(data: str) -> str:
    try:
        return json.loads(data).get("text", "")
    except json.JSONDecodeError:
        return str(data)


def digest_session(con: sqlite3.Connection, row: tuple) -> str:
    sid, slug, title, t_created, t_updated = row
    msgs = con.execute(
        "SELECT type, time_created, data FROM session_message"
        " WHERE session_id = ? ORDER BY seq",
        (sid,),
    ).fetchall()
    counts: dict[str, int] = {}
    for mtype, _, _ in msgs:
        counts[mtype] = counts.get(mtype, 0) + 1
    lines = [
        f"SESSION {sid} ({slug}) — {title}",
        "=" * 72,
        f"span: {fmt(t_created)} -> {fmt(t_updated)} UTC",
        f"message types: {counts}",
    ]
    shown = 0
    for mtype, mtime, data in msgs:
        if mtype == "user":
            shown += 1
            if shown <= MAX_USER_SHOWN:
                lines.append(f"\n--- user {shown} @ {fmt(mtime)} ---\n{msg_text(data)[:MAX_CHARS]}")
    n_users = shown
    closers = [m for m in msgs if m[0] == "assistant"][-ASSISTANT_CLOSERS:]
    for _, mtime, data in closers:
        text = msg_text(data)
        if text:
            lines.append(f"\n--- assistant closer @ {fmt(mtime)} ---\n{text[:MAX_CHARS]}")
    if n_users > MAX_USER_SHOWN:
        lines.insert(3, f"NOTE: {n_users - MAX_USER_SHOWN} user prompts hidden by the {MAX_USER_SHOWN} cap")
    return "\n".join(lines)


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if not args.db.exists():
        print(f"database not found: {args.db}", file=sys.stderr)
        return 2
    cutoff = int(datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp() * 1000)
    try:
        con = sqlite3.connect(f"file:{args.db.as_posix().replace(' ', '%20')}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        con = sqlite3.connect(args.db)  # still treated as read-only by this script
    pid = find_project(con, Path(args.project_dir))
    sessions = con.execute(
        "SELECT id, slug, title, time_created, time_updated FROM session_v2"
        " WHERE project_id = ? AND time_created >= ? AND parent_id IS NULL"
        " ORDER BY time_created",
        (pid, cutoff),
    ).fetchall()
    if not sessions:
        print(f"no sessions for {args.project_dir} since {args.since}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(sessions)} sessions -> {args.out}")
    for row in sessions:
        (out / f"{row[1]}.txt").write_text(digest_session(con, row), encoding="utf-8")
        print(f"  {row[1]}.txt   {fmt(row[3])}   {row[2]}")
    kids = con.execute(
        "SELECT title, parent_id, time_created FROM session_v2"
        " WHERE project_id = ? AND time_created >= ? AND parent_id IS NOT NULL"
        " ORDER BY time_created",
        (pid, cutoff),
    ).fetchall()
    print(f"\n{len(kids)} child sessions (subagent work, titles only):")
    for title, parent, tc in kids:
        print(f"  {fmt(tc)} | {title} | parent {parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
