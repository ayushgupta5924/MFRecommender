"""Test settings: a throwaway SQLite database, no real emails, and cookies over plain http."""
import os
import sys
import tempfile
from pathlib import Path

_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "0"
os.environ.pop("RESEND_API_KEY", None)
os.environ.pop("EMAIL_DEV_MODE", None)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import init_db  # noqa: E402

init_db()
