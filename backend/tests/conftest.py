"""Test settings: a throwaway SQLite database, no real emails, and cookies over plain http."""
import os
import sys
import tempfile
from pathlib import Path

# TEST_DATABASE_URL runs the suite against a real (empty, throwaway) Postgres instead of SQLite.
_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{_db.as_posix()}"
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "0"
os.environ.pop("RESEND_API_KEY", None)
os.environ["EMAIL_DEV_MODE"] = "1"   # accounts on, with SQLite; the sender itself is patched in tests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import init_db  # noqa: E402

init_db()
