"""Database connection and schema migrations.

DATABASE_URL points at Postgres in production (Neon). Without it the app uses a
local SQLite file, which is fine for development but is wiped on every Render
deploy, so accounts stay switched off until it's set (see services/auth.py).

The schema is managed by Alembic (backend/migrations) and brought up to date on
every startup, so code and tables can't drift apart after a deploy.
"""
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, delete, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip() or "sqlite:///./local.db"
    # Neon and most hosts hand out postgres:// or postgresql:// URLs; use the psycopg 3 driver.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url()
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    _connect_args = {"check_same_thread": False}
else:
    _connect_args = {
        # Neon's pooled endpoint (PgBouncer, transaction mode) can't keep server-side
        # prepared statements between transactions; turning them off makes both the
        # pooled and the direct connection string safe to use.
        "prepare_threshold": None,
        # A paused Neon database takes a moment to wake; don't hang forever if it can't.
        "connect_timeout": 15,
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    # Neon closes idle connections and pauses idle databases: check each one before use.
    pool_pre_ping=not _is_sqlite,
    pool_recycle=300,
    pool_size=5,
    max_overflow=5,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _alembic_config():
    from alembic.config import Config
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def migrate() -> None:
    """Bring the schema up to date. Safe to run on every startup."""
    from alembic import command
    cfg = _alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = set(inspect(conn).get_table_names())
        if "alembic_version" not in tables and "users" in tables:
            # Created before migrations existed (by create_all): record it as the first version.
            command.stamp(cfg, "0001")
        command.upgrade(cfg, "head")


def cleanup() -> None:
    """Drop expired login codes and sessions, and advice records past their retention date."""
    from app.db.tables import AuthSession, OtpCode, utcnow
    from app.services.advice_log import purge_expired
    now = utcnow()
    with SessionLocal() as db:
        db.execute(delete(OtpCode).where(OtpCode.created_at < now - timedelta(days=1)))
        db.execute(delete(AuthSession).where(AuthSession.expires_at < now))
        db.commit()
        purge_expired(db)


def init_db() -> None:
    from app.db import tables  # noqa: F401  (registers the tables)
    migrate()
    try:
        cleanup()
    except Exception:  # housekeeping must never stop the app from starting
        logger.exception("Startup cleanup failed")


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
