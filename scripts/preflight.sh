#!/usr/bin/env bash
#
# preflight.sh — everything that can be checked before deploying.
#
#   ./scripts/preflight.sh              check against apps/api/.env (local)
#   ./scripts/preflight.sh --prod       strict: fail on anything a deploy needs
#   ./scripts/preflight.sh --live      use real provider keys for the SSE smoke
#   ./scripts/preflight.sh --fast      skip Docker build and container boot
#
# NEVER PRINTS A SECRET VALUE. The variable report shows the name, the length and
# a verdict. That is enough to act on and not enough to leak from a screenshot.
#
# Exit codes: 0 all good, 1 something failed, 2 only warnings.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"

PROD=0
LIVE=0
FAST=0
for arg in "$@"; do
  case "$arg" in
    --prod) PROD=1 ;;
    --live) LIVE=1 ;;
    --fast) FAST=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

# ── output helpers ───────────────────────────────────────────────────────────
if [ -t 1 ]; then
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
else
  RED=""; GREEN=""; YELLOW=""; DIM=""; BOLD=""; OFF=""
fi

FAILURES=0
WARNINGS=0

step()  { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$OFF"; }
ok()    { printf '  %sOK%s   %s\n' "$GREEN" "$OFF" "$1"; }
bad()   { printf '  %sFAIL%s %s\n' "$RED" "$OFF" "$1"; FAILURES=$((FAILURES + 1)); }
warn()  { printf '  %sWARN%s %s\n' "$YELLOW" "$OFF" "$1"; WARNINGS=$((WARNINGS + 1)); }
note()  { printf '  %s%s%s\n' "$DIM" "$1" "$OFF"; }

cd "$API_DIR" || exit 1

# The docker stages below interpolate shell variables. The Python stages
# (report, tests, alembic, corpus census) load .env through Settings, but bash
# never reads .env on its own. Sourcing .env directly does not work either:
# the file carries a UTF-8 BOM and Neon URLs contain raw ? and & characters
# that bash would interpret as operators. So the values the container needs
# are exported through Settings itself, shlex-quoted so the eval is safe —
# and no value is ever printed.
ENV_VARS="$(uv run python - 2>/dev/null <<'PY'
from shlex import quote

from app.core.config import get_settings

s = get_settings()
for name in ("database_url", "ip_hash_salt", "llm_provider", "gemini_api_key",
             "gemini_model", "groq_api_key", "groq_model"):
    print(f"{name.upper()}={quote(str(getattr(s, name)))}")
PY
)"
if [ -n "$ENV_VARS" ]; then
  set -a
  eval "$ENV_VARS"
  set +a
fi

# ═══ 1. Environment report ═══════════════════════════════════════════════════
#
# Derived from the Settings class rather than a list in this file, so it cannot
# drift. The Python below only ever prints name / length / verdict.
step "Environment"

ENV_REPORT="$(uv run python - <<'PY' 2>/dev/null
from app.core.config import Settings

# What each variable is for, so the report is readable without the template.
WHY = {
    "DATABASE_URL": "Neon POOLED url (-pooler host)",
    "SYNC_DATABASE_URL": "Neon DIRECT url, for Alembic",
    "GEMINI_API_KEY": "Google AI Studio key",
    "GROQ_API_KEY": "Groq key, 429 fallback (optional)",
    "GITHUB_TOKEN": "fine-grained PAT, public repos read-only",
    "GITHUB_OWNER": "repo allowlist boundary",
    "GITHUB_PINS": "which repos to demo",
    "RESEND_API_KEY": "Resend key",
    "CONTACT_NOTIFY_EMAIL": "where notifications are delivered",
    "RESEND_FROM": "the From: address",
    "IP_HASH_SALT": "salted hash of visitor IPs",
    "TRUSTED_PROXY_CIDRS": "who may set X-Forwarded-For",
    "PROBE_TOKEN": "temporary bearer for the header probe",
    "CORS_ORIGINS": "allowed browser origins",
    "EMBEDDING_DIMENSIONS": "must equal the vector column",
    "OMP_NUM_THREADS": "ONNX thread cap",
    "APP_ENV": "production turns on the boot checks",
    "LANGFUSE_PUBLIC_KEY": "Langfuse tracing public key (optional)",
    "LANGFUSE_SECRET_KEY": "Langfuse tracing secret key (optional)",
}

# Blocks in --prod. Mirrors Settings.production_problems().
BLOCKING = {
    "DATABASE_URL", "SYNC_DATABASE_URL", "GEMINI_API_KEY",
    "CORS_ORIGINS", "IP_HASH_SALT", "RESEND_API_KEY", "CONTACT_NOTIFY_EMAIL",
}
OPTIONAL = {"GROQ_API_KEY", "GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_PINS", "PROBE_TOKEN",
            "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"}

s = Settings()
placeholder = str(s.ip_hash_salt).lower().startswith("change")

print(f"{'VARIABLE':24} {'STATE':12} {'LEN':>5}  NOTE")
for name in sorted(set(WHY) | BLOCKING | OPTIONAL):
    # Settings fields are lower_case; the environment and this report are
    # UPPER_CASE. `getattr(s, "DATABASE_URL")` returns "" and every row says
    # MISSING, which looks like an empty environment rather than a broken report.
    value = getattr(s, name.lower(), "")
    if isinstance(value, list):
        value = ",".join(value)
    value = "" if value is None else str(value)
    state = "set" if value else "MISSING"
    if value and len(value) < 16 and name in {"IP_HASH_SALT", "PROBE_TOKEN"}:
        state = "PLACEHOLDER"
    if name == "IP_HASH_SALT" and placeholder:
        state = "PLACEHOLDER"
    print(f"{name:24} {state:12} {len(value):>5}  {WHY.get(name, '')}")

print()
print(f"TRUSTED_PROXY_CIDRS is {'SET' if s.trusted_proxy_cidrs else 'EMPTY'}"
      f"  ({len(s.trusted_proxy_cidrs)} entr{'y' if len(s.trusted_proxy_cidrs) == 1 else 'ies'})")
print(f"RESEND_FROM is {s.resend_from}"
      f"{'  <- reaches only you until a domain is verified' if s.resend_from == 'onboarding@resend.dev' else ''}")
print(f"APP_ENV is {s.app_env!r}  {'(production checks ON)' if s.is_production else '(production checks OFF)'}")

if s.is_production:
    print()
    if s.production_problems():
        for p in s.production_problems():
            print(f"BLOCKING {p}")
    else:
        print("BLOCKING none")
    for w in s.production_warnings():
        print(f"WARNING  {w}")
PY
)"

if [ -z "$ENV_REPORT" ]; then
  bad "could not read Settings. Is uv sync done?"
else
  echo "$ENV_REPORT"
  if [ "$PROD" -eq 1 ]; then
    while IFS= read -r line; do
      case "$line" in
        BLOCKING\ *) bad "${line#BLOCKING }" ;;
        WARNING\ *)  warn "${line#WARNING  }" ;;
      esac
    done <<< "$ENV_REPORT"
  else
    while IFS= read -r line; do
      case "$line" in
        BLOCKING\ *) warn "${line#BLOCKING } (not --prod)" ;;
        WARNING\ *)  warn "${line#WARNING  }" ;;
      esac
    done <<< "$ENV_REPORT"
  fi
fi

# ═══ 2. Lint ════════════════════════════════════════════════════════════════
step "Lint"
if uvx ruff check . --output-format concise >/dev/null 2>&1; then ok "ruff check"
else bad "ruff check"; uvx ruff check . --output-format concise 2>&1 | head -20; fi
if uvx ruff format --check . >/dev/null 2>&1; then ok "ruff format"
else bad "ruff format --check"; uvx ruff format --check . 2>&1 | head -10; fi

# ═══ 3. Tests ═══════════════════════════════════════════════════════════════
step "Tests"
if uv run pytest -q 2>&1 | tail -3 | tee /tmp/preflight-tests.txt | grep -qE '^[0-9]+ passed'; then
  ok "$(tail -1 /tmp/preflight-tests.txt)"
else
  bad "pytest"
  cat /tmp/preflight-tests.txt
  note "Neon's free tier suspends after 5 idle minutes; a TimeoutError here is"
  note "usually the compute waking, not a code failure. Re-run before panicking."
fi

# ═══ 4. Schema drift ═════════════════════════════════════════════════════════
step "Alembic"
if uv run alembic check >/dev/null 2>&1; then
  ok "no model/schema drift"
else
  bad "alembic check reported drift (models and migrations disagree)"
  uv run alembic check 2>&1 | tail -8
fi

# ═══ 5. Docker build ═════════════════════════════════════════════════════════
if [ "$FAST" -eq 0 ]; then
  step "Docker build"
  if docker build -t portfolio-api:preflight . >/tmp/preflight-build.txt 2>&1; then
    ok "image built"
  else
    bad "docker build failed"
    tail -25 /tmp/preflight-build.txt
  fi

  # ═══ 6. Cold start under the free-tier limits ═══════════════════════════════
  step "Container at Render free limits (512 MB, 0.1 CPU)"

  PORT=8137
  docker rm -f preflight-api >/dev/null 2>&1
  # APPROVE_LIMIT_PER_HOUR is raised only inside this throwaway container: the
  # lifecycle smoke below spends three approval attempts against the same
  # in-process limiter bucket, and the default of 3 would 429 the third. The
  # production default in render.yaml stays untouched.
  #
  # Provider keys enter the container ONLY in --live mode. In the default mode
  # nothing is ever sent to a provider: the app refuses to build an LLM client
  # without a key (by design, see build_llm_client), so the SSE stage below
  # skips rather than shipping a guaranteed failure.
  CONTAINER_ENV=(-e "DATABASE_URL=${DATABASE_URL:-}" -e "IP_HASH_SALT=${IP_HASH_SALT:-}" -e "APPROVE_LIMIT_PER_HOUR=${APPROVE_LIMIT_PER_HOUR:-6}")
  if [ "$LIVE" -eq 1 ]; then
    CONTAINER_ENV+=(-e "APP_ENV=local" -e "LLM_PROVIDER=${LLM_PROVIDER:-gemini}" \
      -e "GEMINI_API_KEY=${GEMINI_API_KEY:-}" -e "GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.5-flash-lite}" \
      -e "GROQ_API_KEY=${GROQ_API_KEY:-}" -e "GROQ_MODEL=${GROQ_MODEL:-openai/gpt-oss-120b}")
  fi
  if docker run -d --name preflight-api \
       --memory=512m --cpus=0.1 -p "$PORT:8000" \
       "${CONTAINER_ENV[@]}" \
       portfolio-api:preflight >/dev/null 2>&1; then

    # The boot sweep runs alembic-free work against Postgres; give it room, but
    # not forever. A suspended Neon compute can take a few seconds to wake.
    UP=0
    for _ in $(seq 1 60); do
      if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then UP=1; break; fi
      sleep 1
    done

    if [ "$UP" -eq 1 ]; then
      ok "/health answered"
      if curl -fsS "http://127.0.0.1:$PORT/health" | grep -q '"status":"ok"'; then
        ok "/health reports ok and does not touch the database"
      else
        bad "/health returned an unexpected body"
      fi
      curl -fsS "http://127.0.0.1:$PORT/ready" >/dev/null 2>&1 \
        && ok "/ready answered (database reachable)" \
        || warn "/ready did not answer; DATABASE_URL may be unset here"
    else
      bad "container never became healthy. Its logs:"
      docker logs --tail 30 preflight-api 2>&1
    fi

    # Memory. Measured, not assumed: the embedding model is the ceiling.
    RSS_KB=$(docker stats --no-stream --format '{{.MemUsage}}' preflight-api 2>/dev/null \
             | cut -d/ -f1 | tr -d ' ' | grep -oE '^[0-9]+' || echo 0)
    if [ "${RSS_KB:-0}" -gt 0 ] 2>/dev/null; then
      RSS_MB=$((RSS_KB / 1024))
      if [ "$RSS_MB" -gt 450 ]; then
        bad "memory ${RSS_MB} MB of 512 MB — too close to the ceiling"
      else
        ok "memory ${RSS_MB} MB of 512 MB"
      fi
    else
      note "could not read container memory (docker stats unavailable)"
    fi

    # ═══ 7. SSE smoke ═════════════════════════════════════════════════════════
    step "SSE /chat smoke test"
    if [ "$LIVE" -eq 1 ]; then
      note "using your real provider key — this sends one question to the provider"
      SMOKE="What can you tell me about the person this portfolio describes?"
    else
      note "SKIPPED without --live: the app, by design, refuses to build an LLM"
      note "client without a key, so there is no keyless stream to verify."
      note "Run ./scripts/preflight.sh --live once to exercise the /chat path."
    fi

    if [ "$LIVE" -eq 1 ]; then
    SSE_OUT=$(curl -sS -N -X POST "http://127.0.0.1:$PORT/chat" \
      -H 'Content-Type: application/json' \
      -d "{\"message\":\"$SMOKE\"}" 2>&1)

    if grep -q 'event: done' <<< "$SSE_OUT"; then
      ok "stream completed with a done frame"
    else
      bad "no done frame in the stream"
      head -6 <<< "$SSE_OUT" | sed 's/^/       /'
    fi
    if grep -q 'text/event-stream' <<< "$SSE_OUT" || grep -q '^event:' <<< "$SSE_OUT"; then
      ok "framed as SSE"
    else
      warn "response did not look like SSE"
    fi
    fi

    # ═══ 8. Draft + approve shape (no mail is sent) ═══════════════════════════
    step "draft + approve contract"
    if [ -n "${SSE_OUT:-}" ] && grep -q 'approval_token' <<< "$SSE_OUT"; then
      note "a draft event carried an approval token — check it is not in any log"
    fi
    RESP=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
      "http://127.0.0.1:$PORT/messages/999999999/send" \
      -H 'Content-Type: application/json' -d '{"token":"not-a-real-token"}' 2>&1)
    if [ "$RESP" = "403" ]; then
      ok "a bogus approval is refused with 403 and sends nothing"
    else
      warn "expected 403 for a bogus approval, got $RESP"
    fi

    # ═══ 9. Contact lifecycle: create → edit → cancel (no mail) ═══════════════
    step "contact lifecycle smoke (create, edit, cancel; no mail is sent)"
    BASE="http://127.0.0.1:$PORT"

    CREATE=$(curl -sS -w '\n%{http_code}' -X POST "$BASE/messages/drafts" \
      -H 'Content-Type: application/json' \
      -d '{"name":"Preflight Smoke","sender_email":"preflight@example.invalid","body":"A preflight lifecycle draft. It is edited, then cancelled; nothing is ever sent."}' 2>&1)

    CREATE_CODE=$(tail -n1 <<<"$CREATE")
    CREATE_BODY=$(head -n -1 <<<"$CREATE")

    if [ "$CREATE_CODE" = "201" ]; then
      ok "a fixture draft was recorded (201); it expires on its own"
    else
      bad "expected 201 recording the draft, got $CREATE_CODE"
      head -3 <<<"$CREATE_BODY" | sed 's/^/        /'
    fi

    # The token is read host-side and printed nowhere — same rule as the
    # variable report: a length and a verdict, never a value.
    LIFECYCLE=$(uv run python -c 'import json,sys
try:
    d = json.load(sys.stdin)
    print(d.get("id", ""), d.get("token", ""))
except Exception:
    print("", "")' <<<"$CREATE_BODY")

    DRAFT_ID=$(cut -d' ' -f1 <<<"$LIFECYCLE")
    TOKEN=$(cut -d' ' -f2 <<<"$LIFECYCLE")

    if [ -n "$TOKEN" ] && [ "$DRAFT_ID" != "" ]; then
      ok "the response carried a draft id and a token (token shown nowhere)"
    else
      bad "the create response was missing an id or a token"
    fi

    if [ -n "$TOKEN" ]; then
      EDIT=$(curl -sS -o /dev/null -w '%{http_code}' -X PATCH \
        "$BASE/messages/$DRAFT_ID" \
        -H 'Content-Type: application/json' \
        -d "{\"token\":\"$TOKEN\",\"body\":\"Edited by the preflight smoke. Still nothing sent.\"}" 2>&1)
      if [ "$EDIT" = "200" ]; then
        ok "the draft was edited in place (200)"
      else
        bad "expected 200 editing the draft, got $EDIT"
      fi

      CANCEL=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
        "$BASE/messages/$DRAFT_ID/cancel" \
        -H 'Content-Type: application/json' \
        -d "{\"token\":\"$TOKEN\"}" 2>&1)
      if [ "$CANCEL" = "200" ]; then
        ok "the draft was withdrawn (200); no mail went anywhere"
      else
        bad "expected 200 cancelling the draft, got $CANCEL"
      fi

      # One-shot by construction: the token was spent by the cancel above.
      REPLAY=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
        "$BASE/messages/$DRAFT_ID/cancel" \
        -H 'Content-Type: application/json' \
        -d "{\"token\":\"$TOKEN\"}" 2>&1)
      if [ "$REPLAY" = "403" ]; then
        ok "a replayed cancel is refused (403); the capability died with its use"
      else
        warn "expected 403 replaying the cancel, got $REPLAY"
      fi
    fi

    # ═══ 10. Probe route must be closed ═══════════════════════════════════════
    PROBE=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/_probe/headers" 2>&1)
    if [ "$PROBE" = "404" ]; then
      ok "the header probe is closed (404)"
    else
      warn "the probe route answered $PROBE. If PROBE_TOKEN is set in production,"
      warn "remove it and delete app/api/probe.py once TRUSTED_PROXY_CIDRS is set."
    fi

    docker rm -f preflight-api >/dev/null 2>&1
  else
    bad "could not start the container"
    tail -20 /tmp/preflight-build.txt 2>/dev/null
  fi
else
  step "Docker"
  warn "skipped (--fast)"
fi

# ═══ 11. Corpus ═════════════════════════════════════════════════════════════
step "Corpus"
CHUNKS=$(uv run python - <<'PY' 2>/dev/null
import asyncio
from sqlalchemy import text
from app.core.config import get_settings
from app.db import pool

async def main():
    await pool.setup(get_settings())
    try:
        async with pool.session_scope() as s:
            print((await s.execute(text("SELECT count(*) FROM chunks"))).scalar_one())
    finally:
        await pool.teardown()

try:
    asyncio.run(main())
except Exception:
    print("unknown")
PY
)

case "$CHUNKS" in
  ''|unknown) warn "could not count chunks (no DATABASE_URL, or the schema is not migrated yet)" ;;
  0)
    warn "the corpus is EMPTY. The agent will answer from nothing."
    note ""
    note "This is expected — the corpus is filled last. When you have it, run:"
    note ""
    note "    uv run python -m ingest.run --prune"
    note ""
    note "That reads CORPUS_DIR, chunks it, embeds and upserts. It writes to"
    note "whatever DATABASE_URL points at, so run it against production LAST and"
    note "only once. See docs/DEPLOY.md, final step."
    ;;
  *) ok "$CHUNKS chunks in the database" ;;
esac

# ═══ Summary ════════════════════════════════════════════════════════════════
printf '\n%s%s%s\n' "$BOLD" "────────────────────────────────────────" "$OFF"
if [ "$FAILURES" -gt 0 ]; then
  printf '%s%d failed%s, %d warning(s)\n' "$RED" "$FAILURES" "$OFF" "$WARNINGS"
  exit 1
elif [ "$WARNINGS" -gt 0 ]; then
  printf '%sall checks passed%s, %d warning(s)\n' "$YELLOW" "$OFF" "$WARNINGS"
  exit 2
else
  printf '%sall checks passed%s\n' "$GREEN" "$OFF"
  exit 0
fi