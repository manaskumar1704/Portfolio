# 0011 — Per-IP daily send cap, and the day a salted digest is kept

Checkpoint 5 (plan decision 5): a hard second gate on how much mail any one
visitor connection can cause, complementing the global `daily_send_cap`.

## The decision

`ip_send_counters(day, ip_hash, count)`. Before a send proceeds, the row
for (today UTC, the draft's `ip_hash`) is atomically bumped with the same
`INSERT … ON CONFLICT … DO UPDATE … WHERE count < :cap` statement shape
`send_counters` uses; a failed send releases its reservation, mirroring
`release_daily_send()`. Default cap: 2 sends per IP per UTC day
(`IP_DAILY_SEND_CAP`). Retention deletes rows past midnight — the table is
an anti-abuse counter, never a log.

## The tradeoff, stated

Every send counter needs to group by *something* that identifies the actor.
For 24 hours after a visitor's most recent send, the row holds a salted
SHA-256 of their IP — the same digest `messages.ip_hash` carries, under the
same salt (ADR 0006). It cannot be reversed offline to an address without the
salt, and it is deleted as soon as its day is over. The alternative — hashing
sent *content* or requiring an account for contact — costs more freedom than
the digest does. The abuse it stops is real: without it, one connection can
exhaust the global cap for everyone and the owner wakes to an inboxful. Two
genuine sends per day per network is above every legitimate use in sight.

## Ordering with the global cap

Reserve per-IP first, then global: the local gate is cheap and rejects the
commonest flood with no shared-counter write. On a provider failure, all
reservations taken are released, so an outage burns no one's budget.

## The upgrade paths

1. If abuse arrives that rotates IPs faster than the cap bites, the next step
   is a per-IP draft-creation gate (`create` currently shares the approvals
   limiter) — a limiter change, not a schema one.
2. If retention wants the counters gone sooner, shorten the delete predicate;
   nothing else reads the table.
