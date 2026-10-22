# /retro

Mine past OpenCode sessions for `` (default: this project) and turn them into
a dated retro document, so lessons live in files instead of memory. The mining
is read-only; the only writes are digest files in the temp dir and the retro
document under docs/.

Use the script, never inline SQL in the shell: it handles the database paths,
the UTF-8 stdout reconfiguration (Windows cp1252 breaks otherwise), and exits
non-zero when nothing matches, so a silent empty retro is impossible.

## Steps

1. **Digest.** The user may give a since-date; otherwise default to the last
   30 days.

   ```bash
   uv run --project apps/api python scripts/retro/retro_digest.py \
     --project-dir . --since <YYYY-MM-DD> --out "$TEMP/opencode"
   ```

   Note the printed count and the child-session index. Zero sessions = stop
   and tell the user, do not invent.

2. **Read** every digest file it printed, plus the closers. Skim child titles
   for repeated subagent loops.

3. **Write** `docs/retro-<year>-<month>.md` with exactly these sections:
   Method, Timeline, Decisions, Stuck loops, Learnings -> artifacts, Honest
   limits. Every claim must trace to a prompt or closer line in a digest.
   Cite session slugs. If the corpus of prompts does not support a claim, it
   does not go in.

4. **Propose conversions.** One candidate artifact per repeated loop: a skill
   for behavioural rules, a command for workflows, a document for one-offs.
   List them; do not create any without the user's approval.

5. **Commit** the retro document. Leave digest files in temp — they are
   disposable and regenerable.
