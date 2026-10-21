# 0006 — Sending is a route, not a tool

Phase 6. The send route, the client IP, and retention. One decision governs the
whole phase, and it was already made in 0005 — this records how it turned out in
code, and the three places where the obvious implementation was wrong.

## The tool never sees the token

`draft_message` returns `approval_token` in its result. That is a change from
phase 5, and it looks like a regression until you follow the path: the browser
has to receive the token somehow, and the tool result is the only object that
contains it.

So the chat loop pops the key before building the `ToolResult` the model reads,
and emits it as a separate `draft` event that the router forwards as structured
data. Two copies of one dict, one of which the loop is forbidden to put in a
prompt.

This is the load-bearing part of the design, and it is worth stating what breaks
if the `pop` is deleted: a visitor who can get `draft_message` called on their
behalf — trivially, by asking for it in plain English — reads the token out of
the tool result the model then quotes back at them, and approves their own
message without the owner's involvement. The two-phase design collapses into one
phase and nothing errors.

The assertion is structural, not behavioural, because a behavioural test would
need a model. `test_no_send_in_p6.py` checks that the loop mentions the token and
emits a `draft` event, and `test_the_confirmation_given_to_the_model_has_no_token`
checks the prose path.

## Three checks, one message

Token, IP, and expiry. A wrong token, a wrong IP, and an unknown message id all
return 403 with byte-identical bodies.

The alternative is more helpful to nobody. A 403 saying "wrong IP, but this id
exists" confirms an id an attacker guessed, which turns the route into an oracle
for enumerating drafts. The message does name the likely cause — a visitor who
switched from wifi to mobile deserves to be told that — but it names it without
confirming anything.

The rate limiter runs *before* the token check. Checking the token first means
every request with a forged token reaches the database, which is a free
denial-of-service on the one endpoint that matters. The comparison itself is
`hmac.compare_digest`, because `==` on digests leaks length and prefix through
timing.

## Where the obvious implementation was wrong

Three of these are the kind of mistake that has no symptom. Nothing errors,
nothing logs an error, the feature appears to work.

### `X-Forwarded-For` must not be trusted because it is usually right

Honouring the header unconditionally works perfectly on a real deployment. The
IP check passes, mail arrives, and the only observable effect is that any visitor
can claim any address. There is no failure to notice.

So the header is only consulted when the socket peer is in
`TRUSTED_PROXY_CIDRS`. From anyone else it is discarded and the socket address is
used, which cannot be forged. A forwarded value claiming a private, loopback, or
reserved address is refused even from a trusted peer — otherwise a header that
says `127.0.0.1` forges the "same network" appearance the whole IP factor
depends on.

The default trust list is empty, which means "trust nobody" and breaks approval
for everyone until it is populated. That is the correct direction to fail. The
list is filled from observed headers by the probe route in 6.4, not from a guess
about what Render's CIDRs are.

### IPv6 normalises to its /64, and that has a real cost

A visitor's IPv6 address rotates within their /64 for privacy. Comparing it
exactly would fail on a harmless rotation and reject a legitimate approval.

So IPv6 truncates to /64 and IPv4 stays whole at /32, which is its entire
address. The cost: a carrier that assigns a *new* /64 mid-session fails the
check, and there is no way to keep both "stable" and "exact". That is why the
refusal explains itself rather than returning a bare 403.

What is stored is `sha256(salt + normalised_address)`. The salt is what makes the
digest un-reversible by brute force over the IPv4 space, which is small enough
to enumerate; a salt under 16 characters is refused rather than silently
producing something weak. Losing the salt makes every outstanding draft
unapprovable, which is the intended failure mode — drafts are abandoned, never
sent by someone else.

### `/chat` was rate limiting the proxy, not the visitor

Not part of the send design, found while wiring it up. The chat limiter keyed on
`request.client.host`, which behind Render is Render's own proxy address for
every request on the internet. One person asking the burst number of questions
locked out every other visitor.

It fails quietly for the same reason as the forwarded-header bug: the limiter
works, it just works on the wrong key. `/chat` now uses the same
`client_ip()` helper the send route does, for the same reason.

## Retention has no cron, and says so

Render free has no scheduled jobs. Neon's free tier has no cron extension.
GitHub Actions disables scheduled workflows on public repositories after 60 days
of inactivity — and a keep-alive cron that silently stops is worse than no cron,
because it is indistinguishable from a working one.

So retention runs on container boot and on one request in fifty, guarded by a
Postgres advisory lock so only one process sweeps. `/chat` already holds a
connection, so the marginal cost is one indexed `DELETE` on a table that is
nearly always empty, started as a task and never awaited.

**The honest consequence: when a site has no traffic, nothing sweeps.** Stale
drafts persist until the next visitor. They are inert rows holding a salted
digest rather than a readable address, so the risk is bounded — but this is
retention-by-laziness, not retention-by-policy, and the module docstring says so
rather than implying a guarantee that does not exist.

A Neon cron or an authenticated sweep endpoint closes it properly.

## The daily cap is a row, not a counter

`INSERT INTO send_counters (day, count) VALUES (:day, 1) ON CONFLICT (day) DO
UPDATE SET count = send_counters.count + 1 WHERE send_counters.count < :cap
RETURNING count`

The `WHERE` inside `DO UPDATE` is what makes this a cap rather than a counter: at
the cap the update matches nothing, no row returns, and the caller refuses. No
read-then-write, no transaction, no lock.

In the database rather than in process because Render spins down. Ten sends
before a sleep and ten after would be twenty, and the owner's free tier allows
100 a day. The application caps at 70.

This has a consequence for the tests that was not obvious: the suite spends the
owner's real daily budget, because the counter is a real row in a real table,
which is the point of it. The tests reset it per run, which is the closest a test
can get to a new day without waiting for one.

## Sending is atomic

`UPDATE messages SET status = 'sending' WHERE id = :id AND status = 'pending'
RETURNING ...`

Two concurrent approvals both evaluate the WHERE clause; the row lock means
exactly one sees `pending` still true. The loser updates zero rows.

Checking the status first and then updating is the version that breaks: both
requests read `pending`, both update, both send. The window is small and it is
still a window.

`sending` is an intermediate state rather than going straight to `sent`, because
the provider call sits between the two. Without it, a crash during the send
leaves a row that looks forever pending, with no way to tell whether the mail
went out — which is the one question that matters if a visitor disputes it.
`reap_stale_sends` resolves those to `failed`; a send that never completed
cannot be retried safely either, so that is the honest terminal state.

A replay of an already-sent draft returns 403 rather than 409, and that surprises
people who expect the status check to fire. Sending clears the row's IP hash
immediately, so by the time a replay arrives there is nothing to match the
request against and it is refused at the IP step, before the status is consulted.
Both refusals are equally safe. 409 is for the concurrent case, where both
requests still hold a matching hash.

## Migration order: additive first

`origin_ip` becomes nullable rather than dropped. The previous image is still
looking for that column, and a rollback must not fail on a schema the new release
changed. Dropping it is a later migration, once the new code has run in
production.

`sending` is added to the status enum in the same release because the atomic
claim needs it. `ALTER TYPE ... ADD VALUE` cannot run in a transaction block
before Postgres 12, so the type is guarded rather than recreated wholesale.

## What is still missing, deliberately

**No domain verification.** `RESEND_FROM` is `onboarding@resend.dev`, which
delivers only to the account's own address. The smoke test works and switching
is an environment variable, not a code change. Until then a recruiter cannot
receive anything, which is the thing to fix first.

**`TRUSTED_PROXY_CIDRS` is empty.** Safe by default, unusable in practice. Filled
from observed headers by the probe route in 6.4.

**No automated deploy watcher.** GitHub's scheduled workflows die after 60 days
on a public repo, so keeping a Render free instance awake needs something
outside GitHub. An external free monitor plus warm-on-visit is the plan.

**`IP_HASH_SALT` in `.env` is a placeholder.** Generate a real one before
production: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.