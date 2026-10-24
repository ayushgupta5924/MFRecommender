"""Holds the ranked fund universe in memory.

The file bundled at app/data/rankings.json is refreshed daily by a scheduled
GitHub Action. If RANKINGS_URL is set (e.g. the raw GitHub URL of that file),
the API also pulls the latest copy in the background every few hours, so the
data stays fresh without a redeploy.
"""
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

import requests

from app.services.ranking import SCHEMA_VERSION

logger = logging.getLogger(__name__)

BUNDLED_PATH = Path(__file__).resolve().parents[1] / "data" / "rankings.json"
REFRESH_SECONDS = int(os.getenv("RANKINGS_REFRESH_SECONDS", str(6 * 3600)))


class RankingsStore:
    def __init__(self, path: Path = BUNDLED_PATH, url: Optional[str] = None):
        self.path = path
        self.url = url if url is not None else os.getenv("RANKINGS_URL", "")
        self._data: Optional[dict] = None
        self._loaded_at = 0.0
        self._lock = threading.Lock()
        self._refreshing = False

    def _valid(self, data: dict) -> bool:
        return isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION and bool(data.get("buckets"))

    def _load_bundled(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not self._valid(data):
            raise RuntimeError(f"{self.path} is not a schema v{SCHEMA_VERSION} rankings file")
        # With a remote URL, treat the bundled copy as stale so the first request pulls the latest.
        self._data, self._loaded_at = data, (0.0 if self.url else time.time())

    def _refresh_remote(self) -> None:
        try:
            resp = requests.get(self.url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if self._valid(data) and data.get("nav_date", "") >= (self._data or {}).get("nav_date", ""):
                self._data = data
                logger.info("Rankings refreshed from remote (NAV date %s)", data.get("nav_date"))
        except Exception as e:
            logger.warning("Rankings refresh failed, keeping current data: %s", e)
        finally:
            self._loaded_at = time.time()
            self._refreshing = False

    def get(self) -> dict:
        with self._lock:
            if self._data is None:
                self._load_bundled()
            stale = time.time() - self._loaded_at > REFRESH_SECONDS
            if self.url and stale and not self._refreshing:
                self._refreshing = True
                threading.Thread(target=self._refresh_remote, daemon=True).start()
            return self._data


store = RankingsStore()
