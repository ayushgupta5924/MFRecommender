"""Public fund research: every ranked category, and a page for any open-ended scheme.

General information, the same for every visitor (not advice to anyone in particular): ratings and ranks
from the nightly rankings, NAV history from mfapi.in, rank history from services/rank_history.py.
"""
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Path

from app.services import nav as navs
from app.services.catalog import BUCKETS
from app.services.metrics import cagr, to_series
from app.services.rank_history import quartile
from app.services.rankings_store import holdings, rank_history, scheme_map, store
from app.services.review import rate_fund

router = APIRouter()
CHART_POINTS = 400
TOP_HOLDINGS = 10
PEERS = 5
LIST_FIELDS = ("cagr_1y", "cagr_3y", "cagr_5y", "max_drawdown", "ter", "aum_cr", "years_history")


def _row(f: dict, i: int, n: int) -> dict:
    return {"code": f["code"], "name": f["name"], "amc": f["amc"], "rank": i + 1, "rank_of": n,
            "status": quartile(i + 1, n), **{k: f.get(k) for k in LIST_FIELDS}}


@router.get("/funds/categories")
def categories():
    data = store.get()
    return {"as_of": data.get("nav_date"), "categories": [
        {"key": k, "label": b.label, "sleeve": b.sleeve, "risk_level": b.risk_level, "role": b.role,
         "count": len(data["buckets"].get(k, {}).get("funds", []))}
        for k, b in BUCKETS.items()]}


@router.get("/funds/category/{bucket}")
def category(bucket: str = Path(..., max_length=40)):
    if bucket not in BUCKETS:
        raise HTTPException(404, "We don't rank that category.")
    data = store.get()
    b = data["buckets"].get(bucket, {})
    funds = b.get("funds", [])
    meta = BUCKETS[bucket]
    return {"key": bucket, "label": meta.label, "sleeve": meta.sleeve, "risk_level": meta.risk_level,
            "role": meta.role, "benchmark": b.get("benchmark"), "stats": b.get("stats", {}),
            "as_of": data.get("nav_date"), "funds": [_row(f, i, len(funds)) for i, f in enumerate(funds)]}


def _chart(points: List[Tuple[str, float]]) -> List[list]:
    """At most CHART_POINTS evenly spaced [date, nav] points, always ending on the latest NAV."""
    if len(points) <= CHART_POINTS:
        return [list(p) for p in points]
    step = len(points) / CHART_POINTS
    picked = [points[int(i * step)] for i in range(CHART_POINTS)]
    if picked[-1] != points[-1]:
        picked.append(points[-1])
    return [list(p) for p in picked]


def _returns(points: List[Tuple[str, float]]) -> dict:
    dates, values = to_series(points)
    if len(dates) < 2:
        return {}
    out = {f"cagr_{y}y": cagr(dates, values, y) for y in (1, 3, 5, 10)}
    return {k: (round(float(v), 5) if v is not None else None) for k, v in out.items()}


@router.get("/funds/{code}")
def fund(code: str = Path(..., pattern=r"^\d{3,8}$")):
    s = scheme_map.schemes().get(code)
    if not s:
        raise HTTPException(404, "We couldn't find that fund.")
    data = store.get()
    twin, bucket = s.get("twin"), s.get("bucket")
    rating = rate_fund(twin, bucket, data)
    points = navs.histories([code]).get(code, [])
    latest = navs.latest(points)
    ranked = data["buckets"].get(bucket or "", {}).get("funds", [])
    peers = [_row(f, i, len(ranked)) for i, f in enumerate(ranked[:PEERS])]
    is_direct_growth = bool(s.get("direct") and s.get("growth"))
    twin_info: Optional[dict] = None
    if twin and twin != code and twin in scheme_map.schemes():
        twin_info = {"code": twin, "name": scheme_map.schemes()[twin]["name"]}
    return {
        "code": code,
        "name": s["name"],
        "amc": s["amc"],
        "category": s.get("category"),
        "plan": "Direct" if s.get("direct") else "Regular",
        "option": "Growth" if s.get("growth") else "IDCW",
        "isin": scheme_map.isin(code),
        "info_url": scheme_map.fund_page_url(code),
        "bucket": bucket,
        "bucket_label": BUCKETS[bucket].label if bucket in BUCKETS else None,
        "risk_level": BUCKETS[bucket].risk_level if bucket in BUCKETS else None,
        "direct_growth_twin": None if is_direct_growth else twin_info,
        "rating": rating,
        "nav": {"value": latest[0], "date": latest[1]} if latest else None,
        "returns": _returns(points),
        "chart": _chart(points),
        "rank_history": [{"date": d, "rank": r, "rank_of": n, "status": quartile(r, n)}
                         for d, r, n, b in rank_history.of(twin or code) if b == bucket],
        "top_holdings": [{"company": c, "pct": p} for _isin, c, p in holdings.of(twin or code)[:TOP_HOLDINGS]],
        "portfolio_date": holdings.get().get("portfolio_date"),
        "peers": peers,
        "as_of": data.get("nav_date"),
    }
