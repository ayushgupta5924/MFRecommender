"""Turns raw NAV histories into the ranked fund universe the API serves.

Every fund is scored against the other funds in its own bucket, once per
investor profile, so a conservative investor sees funds that held up best in
falls while an aggressive one sees funds with the strongest long-run returns.
"""
import re
from datetime import datetime, timezone
from statistics import median
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.services.amfi import Scheme
from app.services.catalog import BUCKETS
from app.services.metrics import cagr, fund_metrics, percentile_ranks, to_series

SCHEMA_VERSION = 2

# Metric -> (higher is better?) and per-profile weights. Weights sum to 1.
METRIC_DIRECTION = {
    "cagr_3y": True,
    "cagr_5y": True,
    "rolling_median": True,
    "rolling_p10": True,
    "volatility": False,
    "max_drawdown": True,      # stored as negative, so closer to 0 is better
    "sortino": True,
    "years_history": True,
}
PROFILE_WEIGHTS = {
    "conservative": {"cagr_3y": .10, "cagr_5y": .10, "rolling_median": .15, "rolling_p10": .15,
                     "volatility": .15, "max_drawdown": .20, "sortino": .10, "years_history": .05},
    "balanced":     {"cagr_3y": .15, "cagr_5y": .15, "rolling_median": .20, "rolling_p10": .10,
                     "volatility": .10, "max_drawdown": .10, "sortino": .15, "years_history": .05},
    "aggressive":   {"cagr_3y": .20, "cagr_5y": .20, "rolling_median": .25, "rolling_p10": .05,
                     "volatility": .05, "max_drawdown": .05, "sortino": .15, "years_history": .05},
}

_ACRONYMS = {"SBI", "HDFC", "ICICI", "UTI", "DSP", "PSU", "ELSS", "BSE", "NSE", "LIC", "MF", "HSBC",
             "PGIM", "ITI", "IDBI", "BNP", "IDFC", "JM", "NJ", "ONE", "BOI", "SDL"}


def tidy_name(name: str) -> str:
    """AMFI sometimes lists names in all caps; make those readable."""
    name = re.sub(r"\s+", " ", name).strip()
    if name.upper() != name:
        return name
    words = []
    for w in name.split(" "):
        words.append(w if w in _ACRONYMS else w.capitalize())
    return " ".join(words)


def mfapi_points(payload: dict) -> List[Tuple[str, float]]:
    """mfapi.in returns [{'date': 'dd-mm-yyyy', 'nav': '12.3'}, ...] newest first."""
    points = []
    for row in payload.get("data") or []:
        try:
            d, m, y = row["date"].split("-")
            points.append((f"{y}-{m}-{d}", float(row["nav"])))
        except (KeyError, ValueError, AttributeError):
            continue
    return points


def _round(v: Optional[float], digits: int = 5) -> Optional[float]:
    if v is None or not np.isfinite(v):
        return None
    return round(float(v), digits)


def estimate_risk_free(liquid_returns: List[float], default: float = 0.065) -> float:
    """Liquid funds' median 1-year return is a good live proxy for the short-term rate."""
    vals = [v for v in liquid_returns if v is not None]
    if len(vals) < 5:
        return default
    return float(min(max(median(vals), 0.03), 0.09))


def build_rankings(schemes: List[Scheme], histories: Dict[str, List[Tuple[str, float]]], nav_file_date: str) -> dict:
    series = {}
    for s in schemes:
        dates, navs = to_series(histories.get(s.code, []))
        if len(dates) >= 2:
            series[s.code] = (dates, navs)

    # Pass 1: risk-free rate from liquid funds.
    liquid = [cagr(*series[s.code], 1) for s in schemes if s.bucket == "liquid" and s.code in series]
    risk_free = estimate_risk_free(liquid)

    # Pass 2: metrics for every fund with enough history for its bucket.
    by_bucket: Dict[str, List[dict]] = {k: [] for k in BUCKETS}
    for s in schemes:
        if s.code not in series:
            continue
        bucket = BUCKETS[s.bucket]
        dates, navs = series[s.code]
        rolling_years = 3 if bucket.min_years >= 3 else 1
        m = fund_metrics(dates, navs, risk_free, rolling_years)
        if m["years_history"] < bucket.min_years:
            continue
        # Use AMFI's same-day NAV when mfapi lags behind.
        latest_nav, latest_date = s.nav, s.nav_date.isoformat()
        by_bucket[s.bucket].append({
            "code": s.code,
            "name": tidy_name(s.name),
            "amc": s.amc,
            "category": s.category,
            "nav": latest_nav,
            "nav_date": latest_date,
            "rolling_years": rolling_years,
            **m,
        })

    buckets_out = {}
    for key, funds in by_bucket.items():
        if not funds:
            buckets_out[key] = {"stats": {"count": 0}, "funds": []}
            continue
        ranks = {metric: percentile_ranks([f[metric] for f in funds], higher)
                 for metric, higher in METRIC_DIRECTION.items()}
        for i, f in enumerate(funds):
            f["scores"] = {
                profile: round(100 * sum(w * ranks[metric][i] for metric, w in weights.items()), 2)
                for profile, weights in PROFILE_WEIGHTS.items()
            }
        funds.sort(key=lambda f: f["scores"]["balanced"], reverse=True)

        def med(metric):
            vals = [f[metric] for f in funds if f[metric] is not None]
            return _round(median(vals)) if vals else None

        stats = {"count": len(funds)}
        for metric in ("cagr_1y", "cagr_3y", "cagr_5y", "cagr_10y", "volatility", "max_drawdown",
                       "rolling_median", "rolling_p10"):
            stats[f"median_{metric}"] = med(metric)

        buckets_out[key] = {
            "stats": stats,
            "funds": [{k: (_round(v) if isinstance(v, float) else v) for k, v in f.items()} for f in funds],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "nav_date": nav_file_date,
        "risk_free_rate": round(risk_free, 5),
        "sources": ["AMFI NAVAll (scheme universe and categories)", "mfapi.in (NAV history)"],
        "buckets": buckets_out,
    }
