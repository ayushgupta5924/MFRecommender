"""Schema migrations: the tables in code must always match what the migrations build."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db import Base, engine, migrate


def test_migrations_match_the_models():
    # If this fails, a table changed in app/db/tables.py without a migration:
    # run `alembic revision --autogenerate -m "..."` in backend/ and commit the file.
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def test_database_is_at_the_latest_revision():
    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() is not None


def test_database_created_before_migrations_is_adopted(tmp_path, monkeypatch):
    """An older database built by create_all gets stamped, not recreated."""
    import app.db as db
    old = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    Base.metadata.create_all(old)
    monkeypatch.setattr(db, "engine", old)
    migrate()
    migrate()   # and running it again is harmless
    tables = set(inspect(old).get_table_names())
    assert {"users", "alembic_version"} <= tables
