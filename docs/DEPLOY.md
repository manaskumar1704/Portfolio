# Deploying this portfolio

Written for someone doing this for the first time. Every step says where to
click, what to paste, what success looks like, and what to do when it fails.

**Do the steps in order.** Step 12 in particular cannot be skipped or guessed at,
and it cannot be done early.

Nothing in this guide is a secret you should paste into a chat, a commit, or an
issue. Every generated value stays in your dashboard.

---

## Before you start

You need accounts. All of these are free tiers.

| Account | For | Sign up |
|---|---|---|
| **Neon** | The database | https://console.neon.tech |
| **Google AI Studio** | The model that answers questions | https://aistudio.google.com/apikey |
| **Render** | Hosts the API | https://dashboard.render.com |
| **Vercel** | Hosts the frontend | https://vercel.com |
| **Resend** | Sends you the messages | https://resend.com |
| **GitHub** | The repo, and CI | you already have this |

You also need **Docker** running locally, for the preflight in step 1.

---

## Step 1 — Check the code before configuring anything

```bash
git clone <your-repo-url> portfolio
cd portfolio
cd apps/api && uv sync --dev
cd ../.. && ./scripts/preflight.sh --fast
```

> On Windows, run the script from **Git Bash**, not PowerShell.

**Success looks like:**

```
==> Environment
  DATABASE_URL             set            162
==> Lint
  OK   ruff check
  OK   ruff format
==> Tests
  OK   332 passed
==> Alembic
  OK   no model/schema drift
==> Corpus
  WARN the corpus is EMPTY. The agent will answer from nothing.
```

The corpus warning is expected. You fill the corpus in step 18, last.

**If tests fail:** read the last line. `ConnectionDoesNotExistError` or
`TimeoutError` means Neon's free tier suspended itself while you were reading —
run it again. Anything else is a real failure.

**If variables show MISSING:** your `apps/api/.env` is empty. Copy
`.env.example` to `.env` and fill in what you have so far. Re-run as you go.

---

## Step 2 — Create the Neon branches

Neon calls these **branches**. You want two: one you break, one you ship.

1. Sign in to the Neon console.
2. Create a project. Name it `portfolio`. Pick the free tier.
3. Neon gives you a default branch called `main`. **This is production.**
4. Click **Branches** in the sidebar, then **Create branch**. Name it `dev`.

**Why two:** tests delete rows. The integration tests and the retention sweep
both write to whatever `DATABASE_URL` points at. You do not want them doing that
to the data your site is serving.

**Get the connection strings.** Open each branch, then **Connection Details**.

You get two URLs per branch:

| | What it looks like | Used for |
|---|---|---|
| **Pooled** | `ep-xxx-pooler.region.aws.neon.tech` | `DATABASE_URL` |
| **Direct** | `ep-xxx.region.aws.neon.tech` (no `-pooler`) | `SYNC_DATABASE_URL` |

**Use the pooled URL for the app and the direct URL for migrations.** The pooled
one goes through PgBouncer, which multiplexes many visitors onto a few database
connections — that is what keeps a free tier alive. Alembic runs schema changes,
and a connection pool can send a schema change to the wrong database. So
migrations talk to Postgres directly.

**Copy both of the `dev` branch's URLs** into `apps/api/.env`:

```
DATABASE_URL=postgresql://...-pooler.../neondb?sslmode=require&channel_binding=require
SYNC_DATABASE_URL=postgresql://.../neondb?sslmode=require&channel_binding=require
```

Paste the whole string including the `?sslmode=...` part. The app rewrites what
it needs.

**Success looks like:** the preflight shows both URLs as `set`.

---

## Step 3 — Run the migrations on the dev branch

```bash
cd apps/api
uv run alembic upgrade head
uv run alembic check
```

**Success looks like:**

```
INFO  [alembic.runtime.migration] Running upgrade -> c3d4e5f6a7b8
No new upgrade operations detected.
```

**If it fails with a connection error:** `SYNC_DATABASE_URL` is probably pointing
at the pooled host. It must be the direct one.

---

## Step 4 — Generate the two random values

Run these. Each prints a value. Copy it somewhere safe — a password manager, not
a commit and not a chat.

```bash
# The salt that hashes visitor IP addresses
python -c "import secrets; print(secrets.token_urlsafe(32))"

# The temporary token for the header probe in step 12
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

**What they are for:**

- **`IP_HASH_SALT`** makes the stored IP hash impossible to reverse. Without it,
  a visitor's address could be recovered by brute force. Changing it later makes
  every saved draft unapprovable, which is fine — drafts get deleted, not sent.
- **`PROBE_TOKEN`** is used once, in step 12, and then deleted.

Put `IP_HASH_SALT` in `apps/api/.env`. Keep `PROBE_TOKEN` for step 12.

---

## Step 5 — Get the other keys

| Key | Where | Notes |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | Click "Create API key". |
| `GROQ_API_KEY` | https://console.groq.com/keys | Optional. Only used if Gemini rate-limits. |
| `GITHUB_TOKEN` | https://github.com/settings/personal-access-tokens/new | See below. |
| `RESEND_API_KEY` | https://resend.com/api-keys | "API Keys" → "Create API Key". |

**For the GitHub token**, choose **Fine-grained**, not Classic. Set:

- Token name: `portfolio-api`
- Expiration: 90 days (you will get an email before it expires)
- Repository access: "Public repositories (read-only)"

A Classic token can read your entire account if it leaks. A fine-grained one can
only read public repos, which is all this site needs.

Add these to `apps/api/.env`, and run the preflight again.

---

## Step 6 — Push your code

```bash
git add -A
git commit -m "Initial commit"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

**Success looks like:** a green check on GitHub Actions.

---

## Step 7 — Set the GitHub Actions secrets for CI

The `integration` job runs against a real database. It must be the **dev**
branch. **Never put production credentials in GitHub.**

1. On GitHub: **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** twice:
   - `DATABASE_URL` = the **dev** branch's **pooled** URL.
   - `SYNC_DATABASE_URL` = the **dev** branch's **direct** URL.
3. Click the **Variables** tab and add:
   - `RENDER_URL` = leave **empty for now**. You fill this in step 14.

**Why dev and not production:** the integration tests run migrations and delete
rows. Against production that is data loss.

**If CI fails on the integration job:** the secrets are probably swapped — check
that `DATABASE_URL` contains `-pooler`.

---

## Step 8 — Create the Render service

Render reads `render.yaml` from your repo, so most settings fill themselves.

1. Go to https://dashboard.render.com and sign in with GitHub.
2. **New** → **Blueprint**.
3. Choose your repository. Render finds `render.yaml` automatically.
4. Click **Apply**.

Render asks for the values it cannot know. For each marked `sync: false`:

| Variable | Value to paste |
|---|---|
| `DATABASE_URL` | Production `main` branch, **pooled** URL |
| `SYNC_DATABASE_URL` | Production `main` branch, **direct** URL |
| `GEMINI_API_KEY` | from step 5 |
| `GROQ_API_KEY` | from step 5, or leave blank |
| `GITHUB_TOKEN` | from step 5 |
| `GITHUB_OWNER` | your GitHub username, e.g. `manas-dev` |
| `GITHUB_PINS` | repos to demo, comma-separated. Optional. |
| `RESEND_API_KEY` | from step 5 |
| `CONTACT_NOTIFY_EMAIL` | **your own email address** |
| `IP_HASH_SALT` | from step 4 |
| `CORS_ORIGINS` | your Vercel URL. You do not have it yet — see step 15. **Put a placeholder like `https://placeholder.example` for now.** |

**Leave blank:** `PROBE_TOKEN`, `TRUSTED_PROXY_CIDRS`. Step 12 needs the first
one set temporarily.

**Success looks like:** a deploy that goes green, and a URL like
`https://portfolio-api.onrender.com`.

**If the build fails:** open the deploy log. The most common cause is the Docker
build downloading the embedding model slowly. Wait and re-deploy; it succeeds on
a retry.

---

## Step 9 — Check the service is alive

Open `https://portfolio-api.onrender.com/health`. You should see:

```json
{"status":"ok"}
```

**If you see an error page:** the container is still starting, or it crashed.
Open Render → your service → **Logs**.

**If the logs say "Refusing to start in production":** something from step 8 is
missing. The log names the variable.

---

## Step 10 — The production migration

Render's blueprint runs `alembic upgrade head` on every deploy, inside the new
container. So the first successful deploy already migrated production.

**You only need this by hand if step 8's deploy failed:**

```bash
cd apps/api
# Temporarily point DATABASE_URL and SYNC_DATABASE_URL at production
uv run alembic upgrade head
```

**If the migration fails:** the container will not start, and Render keeps serving
the previous deploy. Nothing breaks. A missing `SYNC_DATABASE_URL` is the usual
cause.

---

## Step 11 — Deploy the frontend to Vercel

1. https://vercel.com → **Add New** → **Project** → import your repo.
2. Under **Configure Project**, set:
   - **Root Directory**: `apps/web`  ← this matters. Without it the build fails.
   - **Framework Preset**: Next.js (it should detect this).
3. Click **Deploy**.

**If the build fails:** check the Root Directory. `apps/web` is the value — not
the repository root, and not `apps`.

**Success looks like:** `https://your-project.vercel.app` loads.

---

## Step 12 — Find out which proxies may set the client IP

This is the step people skip, and it cannot be guessed.

**Why it matters.** The approve button checks that you approve from the same
network you wrote the message from. It reads your IP from an `X-Forwarded-For`
header — but only trusts that header when the request arrived from a known proxy.
If the list is empty, the app uses the raw connection address instead. Behind
Render that address is Render's proxy, not yours, so **every approval fails**.

The safe default (empty) is the wrong default for a working site. So we observe
the real value instead of guessing it.

1. In Render: your service → **Environment** → add `PROBE_TOKEN` with the value
   from step 4. Save. Wait for the redeploy (about 3 minutes).
2. Run this, replacing the placeholder:

```bash
curl "https://portfolio-api.onrender.com/_probe/headers?token=PASTE_TOKEN_HERE"
```

3. You get back something like:

```json
{
  "peer": "10.0.1.23",
  "peer_is_ipv6": false,
  "forwarded": "203.0.113.42",
  "currently_resolves_to": "10.0.1.23",
  "trusted_proxy_count": 0
}
```

4. In Render, set `TRUSTED_PROXY_CIDRS` to the **`peer`** value. If `peer` is
   IPv6, write it as a /64: `2606:4700:4700::/64`. If IPv4, as a /32:
   `10.0.1.23/32`. Save.
5. Save `PROBE_TOKEN` as **empty**. Empty is correct.
6. Do step 13 so the probe route is gone from the deployed image.

**Success looks like:** step 17's approve button works.

**If `currently_resolves_to` still shows the peer after setting the CIDRs:** the
CIDR is wrong. Compare it character by character with `peer`.

---

## Step 13 — Delete the probe route

The probe reports what the server sees about your connection. It is fine behind a
token you are about to delete. It is not something to leave on a public site.

```bash
git rm apps/api/app/api/probe.py apps/api/tests/test_probe.py
```

Then remove the two references in `apps/api/app/main.py`: drop `, probe` from the
`from app.api import ...` line, and drop the `app.include_router(probe.router)`
line.

```bash
cd apps/api && uv run pytest -q tests/test_no_send_in_p6.py && cd ../..
git add -A && git commit -m "Remove the header probe route" && git push
```

Render redeploys automatically once CI passes.

**Success looks like:** `/_probe/headers` returns 404 for everyone.

---

## Step 14 — Set the live URL for the keep-alive

1. On GitHub: **Settings** → **Secrets and variables** → **Actions** →
   **Variables** tab.
2. Edit `RENDER_URL` to your real service URL:
   `https://portfolio-api.onrender.com`
3. Optionally add `EXTERNAL_MONITOR_URL` after step 16.

**Success looks like:** the **keep-alive** workflow runs on the Actions tab and
its log says `Awake.`

**If it says "RENDER_URL is not set":** you edited the wrong tab. Variables and
Secrets are separate tabs.

---

## Step 15 — Point the frontend at the API and fix CORS

Two changes that have to agree.

**On Render**, set `CORS_ORIGINS` to your Vercel URL:

```
https://your-project.vercel.app
```

**On Vercel**, project → **Settings** → **Environment Variables**:

- Name: `NEXT_PUBLIC_API_URL`
- Value: `https://portfolio-api.onrender.com`

Set it for **all three** environments: Production, Preview, Development. Vercel
rebuilds when a `NEXT_PUBLIC_` variable changes, so wait for the redeploy.

**This is an exact allowlist. No wildcards.** The app compares whole strings, so
`https://your-project.vercel.app` does not cover
`https://your-project.vercel.app.evil.test` — which is the point.

**To test a preview build:** add that preview's exact URL to `CORS_ORIGINS` on
Render (comma-separated with the production one), redeploy, test, then remove
the preview URL. Preview URLs change on every push, which is why they are not
kept around permanently.

**If the console says "blocked by CORS policy":** the two URLs do not match
exactly. Check for a trailing slash, `www.`, or `http` versus `https`.

---

## Step 16 — Keep it awake

Render's free tier sleeps after 15 minutes of nothing. The next visitor waits.

**The repository already does this:** `.github/workflows/keep-alive.yml` pings
`/health` every 8 minutes, using the `RENDER_URL` variable from step 14.

**The catch, which matters:** GitHub disables scheduled workflows on **public**
repositories after 60 days of inactivity. When it happens the job does not go
red — the last run stays green in the UI and the site quietly starts sleeping
again. Nothing in GitHub can warn you about that, because the thing that would
warn you is the thing that died.

`.github/workflows/watchdog.yml` checks for it weekly. It helps, but it is
scheduled by the same system, so it dies the same way.

**So set up an external monitor.** Both are free:

1. **UptimeRobot** — https://uptimerobot.com
   - Add a monitor, type HTTP(s)
   - URL: `https://portfolio-api.onrender.com/health`
   - Interval: 10 minutes

   *or*

2. **cron-job.org** — https://cron-job.org
   - Create a job, method GET
   - URL: `https://portfolio-api.onrender.com/health`
   - Every 10 minutes

Then record it: GitHub → Actions → Variables → add `EXTERNAL_MONITOR_URL` with
the monitor's dashboard URL. The watchdog stops warning once it is set.

**Success looks like:** the monitor shows a green uptime bar.

---

## Step 17 — Smoke test the live site

Work through these in order. Open the browser's developer console (F12) for the
first three.

| # | Do this | Expect |
|---|---|---|
| 1 | Open your Vercel URL | The site loads, terminal style |
| 2 | Type a question, press Enter | An answer streams in word by word |
| 3 | Console | No red CORS errors |
| 4 | Ask "what projects has he built?" | An answer with a `from resume.md` citation |
| 5 | Open the Render `/health` URL | `{"status":"ok"}` |
| 6 | Write a message to yourself through the chat | A "Ready to send" card appears |
| 7 | Click **Send this message** | "Sent to Manas", and an email arrives |
| 8 | Press it again, or reload and try | A refusal explaining why, no second email |

**If step 4 has no citations:** the corpus is empty. Go to step 18.

**If step 7 fails with "connection changed":** `TRUSTED_PROXY_CIDRS` is still
wrong. Go back to step 12.

**If step 7 works but no email arrives:** check `RESEND_API_KEY` and
`CONTACT_NOTIFY_EMAIL` on Render, and check your spam folder.
`onboarding@resend.dev` only delivers to your own account address, so if you set
it to anything else it will not arrive at all.

---

## Step 18 — Fill the corpus. Last, and once.

The agent answers only from these documents. Until they exist it has nothing to
say beyond what the model already believes — which is exactly what this project
exists to avoid.

1. Put your markdown files in a folder. Put PDFs in a `_source` subfolder
   *inside* it — the underscore is what stops them being treated as corpus.
2. Convert any PDFs to markdown first:

```bash
cd apps/api
uv run python -m ingest.from_pdf --input YOUR_CORPUS/_source/resume.pdf --output YOUR_CORPUS/resume.md
```

3. **Point `DATABASE_URL` and `SYNC_DATABASE_URL` at PRODUCTION** in your local
   `apps/api/.env`. Temporarily. This step writes to production.
4. Run the ingest:

```bash
cd apps/api
uv run python -m ingest.run --prune
```

**Which database this targets:** whatever `DATABASE_URL` points at when you run
it. That is why step 3 exists — this is the only command in the whole project
that writes to production from your laptop.

**`--prune` matters.** It deletes chunks whose source file no longer exists. That
is how the fictional test data currently sitting in the dev database gets cleaned
up, and how a renamed document stops being answered twice.

**Success looks like:**

```
ingested 47 chunks from 9 files in 12.3s
```

**If it says "refusing to ingest":** you pointed `--dir` at a folder whose name
starts with an underscore. Those are fixtures and intermediates, and the app
deliberately refuses to load them.

**If it says 0 files:** your folder is empty, or you are one level too high.

**After it succeeds:** put your dev URLs back into your local `.env`. Better,
delete them and use a separate `.env.dev` for day-to-day work.

---

## Rolling back

### A bad frontend deploy
Vercel → your project → **Deployments** → click the previous successful one →
**Promote to Production**. About 30 seconds, no build.

### A bad API deploy
Render → your service → **Events** → find the last good deploy → **Rollback to
this version**.

The rollback image runs against the current database, which works because every
migration here is additive — nothing was dropped. That is deliberate: see ADR
0006.

### A bad migration
Roll back the code **first**, then decide about the schema. A migration that
added a column is harmless if the older code ignores it. A migration that dropped
one would break the old image, which is why this project does not do both in the
same release.

### Everything, from scratch
1. Render → service → **Suspend**.
2. Neon → production branch → **Restore** to the timestamp before the deploy.
3. Render → service → **Resume**.

---

## The one-page checklist

- [ ] 1. Preflight passes
- [ ] 2. Neon `dev` branch created, both URLs saved
- [ ] 3. Dev branch migrated
- [ ] 4. `IP_HASH_SALT` and `PROBE_TOKEN` generated
- [ ] 5. Gemini, GitHub and Resend keys obtained
- [ ] 6. Code pushed
- [ ] 7. GitHub secrets set to the **dev** branch
- [ ] 8. Render service created, secrets pasted
- [ ] 9. `/health` returns `{"status":"ok"}`
- [ ] 10. Production migrated
- [ ] 11. Frontend deployed, Root Directory `apps/web`
- [ ] 12. Probe run, `TRUSTED_PROXY_CIDRS` filled, `PROBE_TOKEN` cleared
- [ ] 13. Probe route deleted and pushed
- [ ] 14. `RENDER_URL` set on GitHub
- [ ] 15. `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` set
- [ ] 16. External monitor running
- [ ] 17. Smoke test passed, including an email to yourself
- [ ] 18. Corpus ingested with `--prune`