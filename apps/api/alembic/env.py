"""Alembic environment.

Two things here are not boilerplate:

The URL comes from `SYNC_DATABASE_URL`, not `DATABASE_URL`, and the direct
host rather than the `-pooler` one. Alembic runs DDL, and DDL through PgBouncer's
transaction pooler can be dropped or misrouted mid-transaction. It also runs
once, so a single connection is all it needs.

`render_as_batch` is on because SQLite is the local test database, and SQLite
cannot ALTER a column in place. Without it, adding a nullable column works on
Neon and fails in tests.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
if not settings.sync_database_url:
    raise RuntimeError(
        "SYNC_DATABASE_URL is not set. Alembic needs the direct (non-pooler) "
        "Neon host with a sync driver; see .env.example."
    )

config.set_main_option("sqlalchemy.url", settings.sync_database_url)

# The metadata Alembic compares the database against.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting. Useful for reviewing a migration."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # Without this, a changed server_default is invisible to autogenerate
            # and to `alembic check`. That is how `messages.status` came to have
            # a Python-side default and no database one, and every non-ORM writer
            # then hit a NOT NULL violation.
            compare_server_default=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
