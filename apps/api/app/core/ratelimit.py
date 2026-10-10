"""An in-process token bucket, per client IP.

## What a token bucket is

You get `burst` tokens up front. Each request spends one. They refill at
`per_minute`, continuously rather than all at once. So a visitor can send three
questions quickly and then has to wait, instead of being cut off the moment they
exceed a rate.

That is meaningfully better than a fixed window for this use: recruiter traffic
arrives in bursts. Someone reading a page fires off "what are his projects?" and
"what's his email?" in about four seconds, and a strict window reads that as an
attack.

## Why in memory

Render free runs one instance, so a process-local dict is the whole story — there
is nothing to share state with. Moving to Redis or a Postgres table would be
strictly worse here: another dependency, another free-tier limit, and one more
thing to be down.

**`ponytail: in-process counters, reset on every spin-down.`** That reset is
acceptable, because Render spins the service down after 15 idle minutes and a
limiter that forgets an attacker on a cold container is not the weak link. Move
to a shared store when this runs more than one instance.

## What this does not do

It does not stop a determined attacker with a rotating IP list. It stops an
accidental flood and a bored script, which is what a portfolio actually faces.
Phase 6 adds the per-tool cap that matters more, on `draft_message`.
"""

import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class RateLimiter:
    """A token bucket per key. `key` is a client IP in this codebase."""

    def __init__(
        self,
        per_minute: int | None = None,
        burst: int | None = None,
        per_hour: int | None = None,
    ) -> None:
        """`per_hour` wins over `per_minute` when given.

        It exists because the approval cap is three *per hour*, and
        `per_minute=0.05` is not a number anyone should have to write to say that.

        The bug this replaced: the send route built `RateLimiter()` with no
        arguments, so it read `rate_limit_per_minute` (10/min) and ignored
        `approve_limit_per_hour` completely. The setting existed and did nothing.
        """
        from app.core.config import get_settings

        settings = get_settings()

        if per_hour is not None:
            self._rate = per_hour / 3600.0
        else:
            minutes = per_minute if per_minute is not None else settings.rate_limit_per_minute
            self._rate = minutes / 60.0

        self._burst = float(burst if burst is not None else settings.rate_limit_burst)
        self._buckets: dict[str, _Bucket] = {}
        self._last_sweep = time.monotonic()

    def check(self, key: str) -> tuple[bool, int]:
        """Spend one token. Returns `(allowed, retry_after_seconds)`.

        `retry_after` is 0 when allowed, and always at least 1 when not: a 429
        with `retry-after: 0` invites an immediate retry, which is the opposite
        of what the header is for.
        """
        now = time.monotonic()
        self._maybe_sweep(now)

        bucket = self._buckets.get(key)
        if bucket is None:
            self._buckets[key] = _Bucket(tokens=self._burst - 1, updated_at=now)
            return True, 0

        elapsed = now - bucket.updated_at
        bucket.tokens = min(self._burst, bucket.tokens + elapsed * self._rate)
        bucket.updated_at = now

        if bucket.tokens < 1:
            return False, max(1, int((1 - bucket.tokens) / self._rate) + 1)

        bucket.tokens -= 1
        return True, 0

    def _maybe_sweep(self, now: float) -> None:
        """Drop buckets that have refilled completely.

        Without this the dict grows by one entry per distinct IP forever, which
        on a long-lived container is a slow memory leak driven entirely by
        strangers. Five minutes is well past the refill time at any sane rate.
        """
        if now - self._last_sweep < 300:
            return
        self._last_sweep = now
        self._buckets = {
            key: bucket for key, bucket in self._buckets.items() if now - bucket.updated_at < 300
        }

    def reset(self) -> None:
        """Clear all buckets. Tests use this; nothing else should."""
        self._buckets.clear()
        self._last_sweep = time.monotonic()
