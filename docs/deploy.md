# Keeping a free instance awake

Render's free web service sleeps after 15 minutes of inactivity and the documented
cost of that is a cold start on the next request. Two things make it bearable
here, and one thing that does not work.

## What does not work: a GitHub Actions cron

GitHub disables scheduled workflows on public repositories after 60 days of
inactivity. A keep-alive cron is a scheduled workflow.

The failure mode is the reason this is not a "sure, I'll set it up" item. The job
does not fail loudly when it stops — GitHub disables it, the last successful run
stays green, and the site quietly starts cold-starting again weeks later. A cron
that silently stops is worse than no cron, because it is indistinguishable from a
working one.

## What works: an external monitor

A free uptime monitor (UptimeRobot, cron-job.org, or equivalent) pinging
`GET /health` on a short interval. Two reasons this is the right shape:

- `/health` does not touch the database, so the ping does not hold Neon out of
  scale-to-zero.
- The monitor is outside GitHub, so the 60-day rule does not apply.

Set it to something under 15 minutes. 10 is comfortable.

## Why `/health` and not `/ready`

`/ready` opens a Postgres connection. Every ping would wake Neon's compute, which
is the exact cost scale-to-zero exists to avoid. The two endpoints are split for
this reason and it is worth keeping in mind when adding a third.

## The other half: warm on visit

The monitor keeps the instance awake, but the first real visitor after a deploy
still eats a cold start. Render's own cold start also has to load the embedding
model, which is why that model is baked into the image at build time rather than
downloaded on first use — a download on a cold start is a very visible spinner.

The frontend half is phase 8's business, not this file's: call `/health` when the
page loads and treat the site as `warming` until it answers.

## When it is genuinely wrong to keep it awake

If the portfolio is not being sent traffic, none of this matters. A sleeping
instance costs nothing on the free tier, and a cold start for a visitor who
arrives once a month is a five-second wait they will attribute to the site.

The monitor earns its keep when there is repeat traffic to protect.