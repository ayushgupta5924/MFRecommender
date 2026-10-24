"""Performance and risk metrics computed from a fund's NAV history.

All returns are annualised (CAGR) and measured by calendar date, not by row
count, because NAVs are only published on business days.
"""
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

DAYS_PER_YEAR = 365.25


def to_series(points: Sequence[Tuple[str, float]]) -> Tuple[np.ndarray, np.ndarray]:
    """Convert [(YYYY-MM-DD, nav), ...] into sorted (dates, navs) arrays, dropping bad rows."""
    dates, navs = [], []
    for d, v in points:
        try:
            value = float(v)
        except (TypeError, ValueError):
            continue
        if value > 0:
            dates.append(d)
            navs.append(value)
    if not dates:
        return np.array([], dtype="datetime64[D]"), np.array([])
    d = np.array(dates, dtype="datetime64[D]")
    n = np.array(navs, dtype=float)
    order = np.argsort(d, kind="stable")
    d, n = d[order], n[order]
    # Keep the last value for any duplicated date.
    keep = np.append(d[1:] != d[:-1], True)
    return d[keep], n[keep]


def _value_on_or_before(dates: np.ndarray, navs: np.ndarray, when: np.datetime64) -> Optional[Tuple[np.datetime64, float]]:
    i = int(np.searchsorted(dates, when, side="right")) - 1
    if i < 0:
        return None
    return dates[i], navs[i]


def cagr(dates: np.ndarray, navs: np.ndarray, years: float) -> Optional[float]:
    """Annualised return over the last `years`; None if history is too short."""
    if len(dates) < 2:
        return None
    end_date, end_nav = dates[-1], navs[-1]
    target = end_date - np.timedelta64(int(round(years * DAYS_PER_YEAR)), "D")
    # Allow a week of slack for holidays around the start date.
    if dates[0] > target + np.timedelta64(7, "D"):
        return None
    start = _value_on_or_before(dates, navs, target) or (dates[0], navs[0])
    days = (end_date - start[0]).astype(int)
    if days <= 0:
        return None
    return (end_nav / start[1]) ** (DAYS_PER_YEAR / days) - 1


def month_end_series(dates: np.ndarray, navs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    months = dates.astype("datetime64[M]")
    last_in_month = np.append(months[1:] != months[:-1], True)
    return months[last_in_month], navs[last_in_month]


def max_drawdown(navs: np.ndarray) -> Optional[float]:
    """Largest peak-to-trough fall, as a negative fraction (e.g. -0.32)."""
    if len(navs) < 2:
        return None
    peaks = np.maximum.accumulate(navs)
    return float(np.min(navs / peaks - 1))


def rolling_cagr(month_navs: np.ndarray, window_months: int) -> np.ndarray:
    if len(month_navs) <= window_months:
        return np.array([])
    ratio = month_navs[window_months:] / month_navs[:-window_months]
    return ratio ** (12 / window_months) - 1


def fund_metrics(dates: np.ndarray, navs: np.ndarray, risk_free: float, rolling_years: int) -> Dict[str, Optional[float]]:
    """Compute every metric the ranking uses. Fractions, not percentages."""
    out: Dict[str, Optional[float]] = {
        "cagr_1y": cagr(dates, navs, 1),
        "cagr_3y": cagr(dates, navs, 3),
        "cagr_5y": cagr(dates, navs, 5),
        "cagr_10y": cagr(dates, navs, 10),
        "years_history": float((dates[-1] - dates[0]).astype(int) / DAYS_PER_YEAR) if len(dates) > 1 else 0.0,
    }

    # Risk is judged on the most recent 5 years so old regimes don't dominate.
    recent_start = dates[-1] - np.timedelta64(int(5 * DAYS_PER_YEAR), "D")
    recent = dates >= recent_start
    out["max_drawdown"] = max_drawdown(navs[recent])

    _, m_navs = month_end_series(dates, navs)
    m_recent = m_navs[-61:]
    monthly = m_recent[1:] / m_recent[:-1] - 1 if len(m_recent) > 1 else np.array([])
    if len(monthly) >= 12:
        out["volatility"] = float(np.std(monthly, ddof=1) * np.sqrt(12))
        excess = monthly - risk_free / 12
        downside = np.sqrt(np.mean(np.minimum(excess, 0) ** 2)) * np.sqrt(12)
        annual_excess = float(np.mean(monthly) * 12 - risk_free)
        out["sortino"] = annual_excess / downside if downside > 1e-9 else None
    else:
        out["volatility"] = None
        out["sortino"] = None

    # Rolling returns over the last 10 years show how consistent a fund has been.
    rolls = rolling_cagr(m_navs[-121:], rolling_years * 12)
    if len(rolls) >= 6:
        out["rolling_median"] = float(np.median(rolls))
        out["rolling_p10"] = float(np.percentile(rolls, 10))
        out["rolling_positive"] = float(np.mean(rolls > 0))
    else:
        out["rolling_median"] = out["rolling_p10"] = out["rolling_positive"] = None
    return out


def relative_metrics(dates: np.ndarray, navs: np.ndarray, b_dates: np.ndarray, b_navs: np.ndarray,
                     min_months: int = 36) -> Dict[str, Optional[float]]:
    """How a fund did against its benchmark over the months both have NAVs (at most the last 5 years).

    excess_return: annualised return above the benchmark.
    up_capture / down_capture: the fund's average month as a share of the benchmark's, in rising and in falling
        months. 0.8 down capture means it fell 80% as much as the market in bad months; lower is better.
    beat_rate: share of rolling 3-year periods (up to the last 10 years) in which the fund beat the benchmark.
    """
    out: Dict[str, Optional[float]] = {"excess_return": None, "up_capture": None, "down_capture": None,
                                       "beat_rate": None}
    if len(dates) < 2 or len(b_dates) < 2:
        return out
    fm, fv = month_end_series(dates, navs)
    bm, bv = month_end_series(b_dates, b_navs)
    common, fi, bi = np.intersect1d(fm, bm, return_indices=True)
    fv, bv = fv[fi], bv[bi]

    recent_f, recent_b = fv[-61:], bv[-61:]
    f_r = recent_f[1:] / recent_f[:-1] - 1
    b_r = recent_b[1:] / recent_b[:-1] - 1
    if len(f_r) >= min_months:
        years = len(f_r) / 12
        out["excess_return"] = float((recent_f[-1] / recent_f[0]) ** (1 / years) - (recent_b[-1] / recent_b[0]) ** (1 / years))
        up, down = b_r > 0, b_r < 0
        if up.sum() >= 6:
            out["up_capture"] = float(np.mean(f_r[up]) / np.mean(b_r[up]))
        if down.sum() >= 6:
            out["down_capture"] = float(np.mean(f_r[down]) / np.mean(b_r[down]))

    f_roll = rolling_cagr(fv[-121:], 36)
    b_roll = rolling_cagr(bv[-121:], 36)
    if len(f_roll) >= 6:
        out["beat_rate"] = float(np.mean(f_roll > b_roll))
    return out


def percentile_ranks(values: List[Optional[float]], higher_is_better: bool, missing: float = 0.35) -> List[float]:
    """Rank each value within the list as 0..1 (1 = best). Missing values get `missing`."""
    present = [(i, v) for i, v in enumerate(values) if v is not None and np.isfinite(v)]
    ranks = [missing] * len(values)
    if len(present) == 1:
        ranks[present[0][0]] = 1.0
        return ranks
    if not present:
        return ranks
    vals = np.array([v for _, v in present], dtype=float)
    if not higher_is_better:
        vals = -vals
    # Average rank for ties, scaled to 0..1.
    order = vals.argsort()
    r = np.empty(len(vals))
    r[order] = np.arange(len(vals), dtype=float)
    for v in np.unique(vals):
        mask = vals == v
        r[mask] = r[mask].mean()
    r /= len(vals) - 1
    for (i, _), score in zip(present, r):
        ranks[i] = float(score)
    return ranks
