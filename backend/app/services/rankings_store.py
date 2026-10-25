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
from typing import Callable, Dict, Optional

import requests

from app.services.ranking import SCHEMA_VERSION

logger = logging.getLogger(__name__)

BUNDLED_PATH = Path(__file__).resolve().parents[1] / "data" / "rankings.json"
REFRESH_SECONDS = int(os.getenv("RANKINGS_REFRESH_SECONDS", str(6 * 3600)))


class RankingsStore:
    def __init__(self, path: Path = BUNDLED_PATH, url: Optional[str] = None):
        self.path = path
        self.url = url if url is not None else os.getenv("RANKINGS_URL", "")
        self.name = "Rankings"
        self._data: Optional[dict] = None
        self._loaded_at = 0.0
        self._lock = threading.Lock()
        self._refreshing = False

    def _valid(self, data: dict) -> bool:
        return isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION and bool(data.get("buckets"))

    def _newer(self, data: dict) -> bool:
        return data.get("nav_date", "") >= (self._data or {}).get("nav_date", "")

    def _load_bundled(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not self._valid(data):
            raise RuntimeError(f"{self.path} is not a valid {self.name.lower()} file")
        # With a remote URL, treat the bundled copy as stale so the first request pulls the latest.
        self._data, self._loaded_at = data, (0.0 if self.url else time.time())

    def _refresh_remote(self) -> None:
        try:
            resp = requests.get(self.url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if self._valid(data) and self._newer(data):
                self._data = data
                logger.info("%s refreshed from remote", self.name)
        except Exception as e:
            logger.warning("%s refresh failed, keeping current data: %s", self.name, e)
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
            assert self._data is not None
            return self._data


class SchemeMapStore(RankingsStore):
    """Every open-ended scheme (any plan or option) and its Direct-Growth twin; built nightly with the rankings."""

    def __init__(self):
        rankings_url = os.getenv("RANKINGS_URL", "")
        super().__init__(BUNDLED_PATH.with_name("scheme_map.json"),
                         rankings_url.replace("rankings.json", "scheme_map.json") if rankings_url else "")
        self.name = "Scheme map"
        self._isin_index: Dict[str, str] = {}
        self._indexed: Optional[dict] = None

    def _valid(self, data: dict) -> bool:
        return isinstance(data, dict) and data.get("schema_version") == 1 and bool(data.get("schemes"))

    def _newer(self, data: dict) -> bool:
        return data.get("generated_at", "") >= (self._data or {}).get("generated_at", "")

    def schemes(self) -> Dict[str, dict]:
        return self.get()["schemes"]

    def code_for_isin(self, isin: str) -> Optional[str]:
        data = self.get()
        if self._indexed is not data:
            self._isin_index = {i: code for code, s in data["schemes"].items() for i in s["isins"]}
            self._indexed = data
        return self._isin_index.get(isin)

    def isin(self, code: str) -> Optional[str]:
        isins = self.schemes().get(code, {}).get("isins") or []
        return isins[0] if isins else None

    def fund_page_url(self, code: str) -> Optional[str]:
        isin = self.isin(code)
        return FUND_PAGE_URL.format(isin=isin) if isin else None


class HoldingsStore(RankingsStore):
    """Each Direct-Growth scheme's disclosed stock holdings ([isin, company, % of AUM]); refreshed weekly."""

    EMPTY = {"schema_version": 1, "generated_at": "", "portfolio_date": None, "holdings": {}}

    def __init__(self):
        rankings_url = os.getenv("RANKINGS_URL", "")
        super().__init__(BUNDLED_PATH.with_name("holdings.json"),
                         rankings_url.replace("rankings.json", "holdings.json") if rankings_url else "")
        self.name = "Holdings"

    def _valid(self, data: dict) -> bool:
        return isinstance(data, dict) and data.get("schema_version") == 1 and isinstance(data.get("holdings"), dict)

    def _newer(self, data: dict) -> bool:
        return data.get("generated_at", "") >= (self._data or {}).get("generated_at", "")

    def _load_bundled(self) -> None:
        # Optional data: without the file, reviews simply skip stock-level overlap.
        try:
            super()._load_bundled()
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning("No holdings data: %s", e)
            self._data, self._loaded_at = self.EMPTY, (0.0 if self.url else time.time())

    def of(self, code: str) -> list:
        return self.get()["holdings"].get(code) or []


class RankHistoryStore(HoldingsStore):
    """Each ranked fund's weekly position in its category (services/rank_history.py); updated nightly."""

    EMPTY = {"schema_version": 1, "generated_at": "", "funds": {}}

    def __init__(self):
        rankings_url = os.getenv("RANKINGS_URL", "")
        RankingsStore.__init__(self, BUNDLED_PATH.with_name("rank_history.json"),
                               rankings_url.replace("rankings.json", "rank_history.json") if rankings_url else "")
        self.name = "Rank history"

    def _valid(self, data: dict) -> bool:
        return isinstance(data, dict) and data.get("schema_version") == 1 and isinstance(data.get("funds"), dict)

    def of(self, code: str) -> list:
        return self.get()["funds"].get(code) or []


# A neutral page with the fund's facts (NAV, expense ratio, holdings, fund manager), addressed by ISIN so the link
# always lands on the right fund. Coin lists every fund house's Direct plans.
FUND_PAGE_URL = "https://coin.zerodha.com/mf/fund/{isin}"

store = RankingsStore()
scheme_map = SchemeMapStore()
holdings = HoldingsStore()
rank_history = RankHistoryStore()
