"""Alembic environment: uses the app's own engine, so migrations always hit the same database as the API."""
from alembic import context

from app.db import Base, engine
from app.db import tables  # noqa: F401  (registers the tables on Base.metadata)


def run() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return
    with engine.begin() as conn:
        _migrate(conn)


def _migrate(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        # SQLite can't alter columns in place; batch mode copies the table instead.
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run()
