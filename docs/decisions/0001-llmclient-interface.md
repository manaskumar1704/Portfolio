# 0001 — LLM providers sit behind an LLMClient interface

Phase 1 of the backend plan, decision 16 in the session's decision log. This
file exists because AGENTS.md requires a justification before a library enters
the project, and because the provider is the one choice most likely to change.

## Decision

The app depends on one provider SDK — Groq's OpenAI-compatible client — and
talks to it through `app/services/llm.py`, which exposes a single `stream()`
method plus a small message and tool-result vocabulary. A Gemini adapter sits
beside it as a second implementation of the same shape. The model name and the
provider are settings, not code changes.

## Why not LangChain, or Pydantic-AI, or any agent framework

The tool loop this project needs is roughly a hundred lines: send messages with
tool schemas, read back a tool call, run the function, append the result, repeat
until the model answers in prose. A framework replaces that with an
abstraction layer that has to be learned before the mechanism can be debugged,
and it arrives with transitive dependencies that then have to be pinned and
audited on a free-tier hobby project. The user is learning this specific thing;
hiding it behind a framework defeats the purpose of building it.

The honest cost: when tool-calling gets complicated enough to need a state
graph — more than two tools, retries with backoff, parallel fan-out — this
becomes the wrong call. At that point the loop in `chat.py` should be replaced,
not extended, and this ADR should be revisited.

## Why Groq first

Free tier, no card required, and the fastest time-to-first-token of the
no-card providers, which matters when the whole demo is a streaming chat UI.
Its OpenAI-compatible surface means the adapter is thin. Gemini is the
fallback for rate-limit headroom.

Free tiers are rate-limited rather than billed, so the real risk is 429s
showing up in front of a visitor, not cost. The guardrail phase owns that
response; this ADR only fixes where the call is made.

## Consequences

Swapping providers is one environment variable and a new adapter function. It
is also not free: each provider's tool-calling quirks move the adapter, and the
eval set in phase 8 is what tells you a swap did not quietly degrade answers.
That is the reason the evals exist.