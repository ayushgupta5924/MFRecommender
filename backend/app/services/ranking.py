"""Turns raw NAV histories into the ranked fund universe the API serves.

Every fund is scored against the other funds in its own bucket, once per
investor profile, so a conservative investor sees funds that held up best in
falls while an aggressive one sees funds with the strongest long-run returns.
"""
import re
from datetime import date, datetime, timezone
from statistics import median
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.services.amfi import Scheme
from app.services.catalog import BENCHMARKS, BUCKETS
from app.services.fund_facts import manager_info, size_fit
from app.services.metrics import cagr, fund_metrics, month_end_series, percentile_ranks, relative_metrics, to_series

SCHEMA_VERSION = 2

# Metric -> higher is better? Past returns alone predict future returns poorly, so they are only part of the score:
#   track record   returns, consistency (rolling returns), risk-adjusted return, falls
#   vs the index   return above the category's index, how often it beat it, how much of the market's falls it took
#   cost           expense ratio: the one drag on returns known in advance
#   size           too big for the stocks its category should own, or too small to be secure (fund_facts.size_fit)
#   credit         debt funds only: share of the portfolio below AAA / A1+ / sovereign
METRIC_DIRECTION = {
    "cagr_3y": True,
    "cagr_5y": True,
    "rolling_median": True,
    "rolling_p10": True,
    "volatility": False,
    "max_drawdown": True,      # stored as negative, so closer to 0 is better
    "sortino": True,
    "years_history": True,
    "excess_return": True,
    "beat_rate": True,
    "down_capture": False,
    "up_capture": True,
    "ter": False,
    "low_grade_pct": False,
}
# Unknown values score as below average for track-record metrics (a gap in history is a warning sign), and as
# neutral for the newer factors, which are unknown when a source is down or don't apply to the category.
MISSING = {m: 0.5 for m in ("excess_return", "beat_rate", "down_capture", "up_capture", "ter", "low_grade_pct")}

# Per-profile weights; each sums to 1 (size_fit is scored separately, see build_rankings).
PROFILE_WEIGHTS = {
    "conservative": {"cagr_3y": .04, "cagr_5y": .05, "rolling_median": .06, "rolling_p10": .09, "sortino": .06,
                     "volatility": .08, "max_drawdown": .10, "years_history": .02,
                     "excess_return": .04, "beat_rate": .07, "down_capture": .10, "up_capture": .00,
                     "ter": .10, "size_fit": .12, "low_grade_pct": .07},
    "balanced":     {"cagr_3y": .05, "cagr_5y": .07, "rolling_median": .09, "rolling_p10": .07, "sortino": .07,
                     "volatility": .05, "max_drawdown": .07, "years_history": .02,
                     "excess_return": .07, "beat_rate": .08, "down_capture": .07, "up_capture": .02,
                     "ter": .10, "size_fit": .12, "low_grade_pct": .05},
    "aggressive":   {"cagr_3y": .07, "cagr_5y": .08, "rolling_median": .11, "rolling_p10": .05, "sortino": .07,
                     "volatility": .03, "max_drawdown": .04, "years_history": .02,
                     "excess_return": .10, "beat_rate": .08, "down_capture": .03, "up_capture": .04,
                     "ter": .10, "size_fit": .12, "low_grade_pct": .06},
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


def estimate_risk_free(liquid_returns: List[Optional[float]], default: float = 0.065) -> float:
    """Liquid funds' median 1-year return is a good live proxy for the short-term rate."""
    vals = [v for v in liquid_returns if v is not None]
    if len(vals) < 5:
        return default
    return float(min(max(median(vals), 0.03), 0.09))


def benchmark_series(parts: List[Tuple[str, float]], index_codes: Dict[str, str],
                     series: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Month-end NAV series for a benchmark, blending several index funds' monthly returns when it has parts."""
    legs = []
    for index, weight in parts:
        code = index_codes.get(index)
        if code not in series:
            return None
        legs.append((weight, *month_end_series(*series[code])))
    months = legs[0][1]
    for _, m, _ in legs[1:]:
        months = np.intersect1d(months, m)
    if len(months) < 2:
        return None
    returns = sum(w * (v[np.isin(m, months)][1:] / v[np.isin(m, months)][:-1] - 1) for w, m, v in legs)
    return months.astype("datetime64[D]"), np.concatenate([[100.0], 100.0 * np.cumprod(1 + returns)])


FACT_FIELDS = ("ter", "ter_date", "aum_cr", "managers", "turnover", "portfolio_date", "stocks", "top10_pct",
               "cash_pct", "low_grade_pct")


def _facts_for(s: Scheme, f: Optional[dict], snapshot: Optional[dict], bucket, today: date) -> dict:
    """The fund's facts plus the derived size and manager scores; every key present, None when unknown."""
    f = f or {}
    out = {k: f.get(k) for k in FACT_FIELDS}
    out["size_fit"] = size_fit(f.get("aum_cr"), bucket.key, bucket.sleeve)
    seen = (snapshot or {}).get("managers_seen", {}).get(s.code, {})
    out.update(manager_info(seen, f.get("managers") or [], (snapshot or {}).get("baseline", ""), today))
    if bucket.sleeve != "debt":
        out["low_grade_pct"] = None
    return out


def build_rankings(schemes: List[Scheme], histories: Dict[str, List[Tuple[str, float]]], nav_file_date: str,
                   index_codes: Optional[Dict[str, str]] = None, facts: Optional[dict] = None,
                   today: Optional[date] = None) -> dict:
    today = today or date.today()
    series: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for code in {s.code for s in schemes} | set((index_codes or {}).values()):
        dates, navs = to_series(histories.get(code, []))
        if len(dates) >= 2:
            series[code] = (dates, navs)
    benchmarks = {key: benchmark_series(parts, index_codes or {}, series)
                  for key, (_, parts) in BENCHMARKS.items()}

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
        m: dict = fund_metrics(dates, navs, risk_free, rolling_years)
        if (m["years_history"] or 0) < bucket.min_years:
            continue
        if s.bucket in BENCHMARKS:
            bench = benchmarks[s.bucket]
            m.update(relative_metrics(dates, navs, *bench) if bench
                     else relative_metrics(dates[:0], navs[:0], dates[:0], navs[:0]))
        m.update(_facts_for(s, (facts or {}).get("facts", {}).get(s.code), facts, bucket, today))
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
        ranks = {metric: percentile_ranks([f.get(metric) for f in funds], higher, MISSING.get(metric, 0.35))
                 for metric, higher in METRIC_DIRECTION.items()}
        # Size is judged against fixed limits, not against the other funds.
        ranks["size_fit"] = [f["size_fit"] if f.get("size_fit") is not None else 0.5 for f in funds]
        for i, f in enumerate(funds):
            f["scores"] = {
                profile: round(100 * sum(w * ranks[metric][i] for metric, w in weights.items()), 2)
                for profile, weights in PROFILE_WEIGHTS.items()
            }
        funds.sort(key=lambda f: f["scores"]["balanced"], reverse=True)

        def med(metric):
            vals = [f[metric] for f in funds if f.get(metric) is not None]
            return _round(median(vals)) if vals else None

        stats: Dict[str, Optional[float]] = {"count": len(funds)}
        for metric in ("cagr_1y", "cagr_3y", "cagr_5y", "cagr_10y", "volatility", "max_drawdown",
                       "rolling_median", "rolling_p10", "ter", "aum_cr", "excess_return", "down_capture"):
            stats[f"median_{metric}"] = med(metric)

        buckets_out[key] = {
            "benchmark": BENCHMARKS[key][0] if key in BENCHMARKS and benchmarks[key] else None,
            "stats": stats,
            "funds": [{k: (_round(v) if isinstance(v, float) else v) for k, v in f.items()} for f in funds],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "nav_date": nav_file_date,
        "risk_free_rate": round(risk_free, 5),
        "sources": ["AMFI NAVAll (scheme universe and categories)", "mfapi.in (NAV history)"]
                   + (["Kuvera (expense ratios, fund managers, portfolios)", "AMFI average AUM (fund size)"]
                      if facts else []),
        "facts_as_of": (facts or {}).get("fetched_at"),
        "benchmark_funds": index_codes or {},
        "buckets": buckets_out,
    }
