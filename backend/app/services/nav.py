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
    try:
        resp = requests.get(MFAPI_URL.format(code=code), timeout=15, headers=HEADERS)
        points = sorted(mfapi_points(resp.json())) if resp.status_code == 200 else []
    except (requests.RequestException, ValueError):
        points = []
    with _lock:
        # Don't cache failures for long, so a blip doesn't stick for hours.
        _cache[code] = (now if points else now - CACHE_SECONDS + 300, points)
    return points


def histories(codes: Iterable[str]) -> Dict[str, List[Tuple[str, float]]]:
    codes = sorted({c for c in codes if c})
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(codes, pool.map(_history, codes)))


def latest(points: List[Tuple[str, float]]) -> Optional[Tuple[float, str]]:
    return (points[-1][1], points[-1][0]) if points else None


def one_year_return(points: List[Tuple[str, float]]) -> Optional[float]:
    dates, navs = to_series(points)
    return cagr(dates, navs, 1) if len(dates) > 1 else None
