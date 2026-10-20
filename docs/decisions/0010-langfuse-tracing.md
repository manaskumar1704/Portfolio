# 0010 — Langfuse, OpenTelemetry-based, behind existing settings, dark by default

Checkpoint 5, per the plan ("Langfuse (`langfuse==5.0.3`, OpenTelemetry-based)
behind the settings that already exist; no-op when keys are absent") and
AGENTS's rule that a dependency lands only after its ADR.

## The decision

`langfuse==5.0.3` is the observability dependency for the API. It is wired
behind the `langfuse_*` settings that have existed since phase 8
(`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` — empty by
default, a working cloud host default), and it records **no telemetry unless
both keys are set**. When absent, the app behaves exactly as before: no
network, no background threads with work to do, no extra latency.

## What is traced, and what is never traced

Traced per chat turn, because those are the facts an incident report needs:

- timing (turn wall-clock, provider call duration),
- token usage as reported by the provider response,
- tool outcomes (name, ok/error class, duration),
- whether sources were present in the final `done` frame.

Never traced: message text in either direction, draft bodies, approval tokens
(plaintext or hash), API keys, visitor IP hashes, or anything from the email
paths. The draft lifecycle's capability tokens are the crown jewels and stay
out of every third-party system by design (ADR 0006).

## Why OpenTelemetry-based

The `langfuse` Python SDK v5 sits on OTel spans. That matters for the exit
ramp: if Langfuse ever stops fitting, the spans already exist and any OTel
endpoint can consume them (self-hosted or another SaaS), so the tracing seam
is not hostage to one vendor. It also means the exporter degrades to
no-op — a disabled exporter emits nothing.

## Runtime cost on Render free

The tracer is initialised lazily inside the settings-guarded `if`, once, at
first chat turn. Free-tier RAM is the shared 512 MB budget; the client is
bytes-level small and flushes on a batch interval over the already-scheduled
event loop. Nothing is imported at module import time when keys are absent,
so the no-op path costs an import of the settings only.

## The upgrade paths

1. If Langfuse is not adopted, delete `app/core/tracing.py` and the settings
   — the chat loop has one call site.
2. If deeper provider tracing is wanted (prompt/completion payloads), that is
   a deliberate decision to send message text to a third party, and it needs
   its own ADR reversing the "never traced" list above.
