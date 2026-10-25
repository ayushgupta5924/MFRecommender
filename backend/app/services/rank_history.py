"""Each ranked fund's position in its category over time, for the rank trend on fund pages.

One point per fund per week (the week's latest ranking wins), kept for two years, in
app/data/rank_history.json:
    {"schema_version": 1, "generated_at": "...", "funds": {code: [[iso_date, rank, rank_of, bucket], ...]}}
The nightly rankings job adds today's ranks (scripts/build_rankings.py).
"""
from datetime import date, timedelta
from typing import Dict, List, Optional

KEEP_DAYS = 2 * 365 + 7
EMPTY = {"schema_version": 1, "generated_at": "", "funds": {}}


def _week(d: str) -> tuple:
    return date.fromisoformat(d).isocalendar()[:2]


def record(history: Optional[dict], rankings: dict, day: Optional[str] = None) -> dict:
    """History with today's ranks added. Pure: returns a new dict."""
    day = day or rankings.get("nav_date") or date.today().isoformat()
    cutoff = (date.fromisoformat(day) - timedelta(days=KEEP_DAYS)).isoformat()
    funds: Dict[str, List[list]] = {code: [p for p in pts if p[0] >= cutoff]
                                    for code, pts in ((history or EMPTY).get("funds") or {}).items()}
    for bucket, b in rankings["buckets"].items():
        ranked = b.get("funds") or []
        for i, f in enumerate(ranked):
            pts = funds.setdefault(f["code"], [])
            point = [day, i + 1, len(ranked), bucket]
            if pts and _week(pts[-1][0]) == _week(day):
                if pts[-1][0] <= day:
                    pts[-1] = point
            else:
                pts.append(point)
                pts.sort(key=lambda p: p[0])
    return {"schema_version": 1, "generated_at": day, "funds": {c: p for c, p in funds.items() if p}}


def quartile(rank: int, rank_of: int) -> str:
    """Same cut-offs as review.rate_fund."""
    share = (rank - 1) / (rank_of - 1) if rank_of > 1 else 0.0
    return ("in_form" if share < 0.25 else "on_track" if share < 0.5
            else "off_track" if share < 0.75 else "out_of_form")
