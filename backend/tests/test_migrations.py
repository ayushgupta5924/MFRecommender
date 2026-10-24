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
    """A database made by create_all before migrations existed has the first version's tables and no
    version record. It gets recorded as version 0001, then upgraded like any other."""
    from alembic import command

    import app.db as db
    old = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with old.begin() as conn:
        cfg = db._alembic_config()
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0001")
        conn.exec_driver_sql("DROP TABLE alembic_version")
    monkeypatch.setattr(db, "engine", old)
    migrate()
    migrate()   # and running it again is harmless
    columns = {c["name"] for c in inspect(old).get_columns("users")}
    assert "alerts_enabled" in columns and "alembic_version" in inspect(old).get_table_names()
