"""Latest NAVs and NAV histories for any scheme, from mfapi.in, cached in memory.

Reviews need prices for every plan and option an investor holds (Regular,
IDCW, sectoral funds...), not just the Direct-Growth funds we rank.
"""
import concurrent.futures
import threading
import time
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from app.services.metrics import cagr, to_series
from app.services.ranking import mfapi_points

MFAPI_URL = "https://api.mfapi.in/mf/{code}"
MFAPI_LATEST_URL = "https://api.mfapi.in/mf/{code}/latest"
TIMEOUT = 30            # long-running funds have 15+ years of daily NAVs to download
ATTEMPTS = 2
CACHE_SECONDS = 6 * 3600
HEADERS = {"User-Agent": "mf-advisor-review/1.0"}

_cache: Dict[str, Tuple[float, List[Tuple[str, float]]]] = {}
_lock = threading.Lock()


def _history(code: str) -> List[Tuple[str, float]]:
    """[(iso_date, nav), ...] oldest first; empty if mfapi has nothing."""
    now = time.time()
    with _lock:
        hit = _cache.get(code)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    points = _fetch(MFAPI_URL.format(code=code))
    with _lock:
        # Don't cache failures for long, so a blip doesn't stick for hours.
        _cache[code] = (now if points else now - CACHE_SECONDS + 300, points)
    return points


def _fetch(url: str) -> List[Tuple[str, float]]:
    for _ in range(ATTEMPTS):
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            if resp.status_code == 200:
                return sorted(mfapi_points(resp.json()))
        except (requests.RequestException, ValueError):
            pass
    return []


def latest_nav(code: str) -> Optional[Tuple[float, str]]:
    """Today's NAV without downloading the whole history (cached history first, if we have it)."""
    with _lock:
        hit = _cache.get(code)
    if hit and hit[1] and time.time() - hit[0] < CACHE_SECONDS:
        return latest(hit[1])
    return latest(_fetch(MFAPI_LATEST_URL.format(code=code))) or latest(_history(code))


def histories(codes: Iterable[str]) -> Dict[str, List[Tuple[str, float]]]:
    codes = sorted({c for c in codes if c})
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(codes, pool.map(_history, codes)))


def latest(points: List[Tuple[str, float]]) -> Optional[Tuple[float, str]]:
    return (points[-1][1], points[-1][0]) if points else None


def one_year_return(points: List[Tuple[str, float]]) -> Optional[float]:
    dates, navs = to_series(points)
    return cagr(dates, navs, 1) if len(dates) > 1 else None
