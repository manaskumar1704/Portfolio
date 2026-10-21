# 0002 — Postgres access, migrations, and the vector index

Phase 2 of the backend plan, decisions 2, 3 and 4 in the session's decision
log. This file records three choices that are load-bearing for the free tier
and one that is quietly dangerous.

## SQLAlchemy 2.0 async, not raw asyncpg, not SQLModel

SQLAlchemy's async layer is two things worth having: a connection pool that
knows about Neon's suspension, and a session transaction boundary. Both are
load-bearing here, and both are a day of work to build by hand.

Raw asyncpg was rejected because it means hand-rolling sessions, pooling and
transaction handling — which is most of what a framework is for. SQLModel was
rejected because it fuses the models to FastAPI, and phase 7's MCP server has
to import the same services from outside any web framework. That import is the
one architectural rule this project cares about most, and SQLModel works
against it.

## Alembic, not `CREATE TABLE IF NOT EXISTS`

Four consumers of the schema: the app, the ingest script, the MCP server, and
phase 8's evals. The one that matters is rollback. `IF NOT EXISTS` cannot
express "drop the column you added last week", and the migration that does get
written is the one nobody rehearses. Alembic's autogenerate handles the boring
80%; the remaining 20% is where the interesting comments are.

Alembic uses its own `SYNC_DATABASE_URL` against the **direct** host, not the
pooler. Two reasons, both practical: DDL through PgBouncer's transaction pooler
can be misrouted mid-transaction, and migrations run once, so a single
connection is all they need.

## `lakebase_ann`, not `ivfflat` or `hnsw`

The installed `neon-postgres` skill prescribes
`CREATE EXTENSION lakebase_vector CASCADE`, which installs pgvector and adds
Neon's `lakebase_ann` index access method. Using it because the local
documentation says to, and because it is the option Neon tunes and supports.

`vector_cosine_ops` pairs with the `<=>` distance operator used in the
retrieval query. An operator class and an operator that disagree is the
quiet-wrong-answer bug: the query still runs, still returns rows, and just
returns worse matches than it should.

## The index lives in the metadata, not only in the migration

The ANN index and the two plain indexes are declared on the models as well as
being created in the migration. This is not tidiness. `alembic check` compares
the live database against the metadata, and an index present in one but not the
other makes it propose `remove_index`. Run `alembic revision --autogenerate`
on a quiet afternoon and that becomes a real migration, applied by accident.

CI runs `alembic check` for exactly this reason: the failure mode of
model/schema drift is a deployment writing to a column that does not exist.

## Connection strings are rewritten for asyncpg

Neon's console hands out `?sslmode=require&channel_binding=require`.
SQLAlchemy splits the query string into keyword arguments and passes them to
`asyncpg.connect()`, which knows neither name, so every connection fails with
`TypeError: connect() got an unexpected keyword argument`. Raw asyncpg is happy
with the original string because it parses the query string itself — a path
that is not available through SQLAlchemy.

`normalize_async_url` therefore rewrites `sslmode` to `ssl` and drops
`channel_binding`, which asyncpg negotiates on its own when TLS is required.
The synchronous URL is deliberately left alone: psycopg understands both names,
and rewriting it would discard a security setting for no benefit.

## Known limits, recorded rather than fixed

`pool_size=5` with `max_overflow=0` means a sixth concurrent query waits for a
connection. That is fine for a portfolio with one visitor, and it is the right
answer inside 512 MB. It becomes the wrong answer if this ever serves real
traffic, at which point the limiter in phase 6 should move to shared state and
the pool should grow.

`pool_recycle=600` keeps connections inside Neon's idle window, but a suspension
that lands mid-request still kills a connection. `pool_pre_ping` handles the
common case; the uncommon one surfaces as a 503 from `/ready`, which is the
correct thing to see.

**`ponytail: in-process rate limiting, `max_overflow=0`, `top-4` retrieval with
no reranker.`** Move the limiter to a Neon table and grow the pool when this
runs more than one instance or more than a handful of concurrent visitors.