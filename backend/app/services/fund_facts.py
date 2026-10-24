"""Facts about each fund beyond its NAV: expense ratio, size, fund managers and what it holds.

Sources
  * Kuvera's public fund data (api.kuvera.in): expense ratio, AUM, fund managers and the monthly portfolio
    each fund house discloses. Its robots.txt allows crawling with a 10-second delay, which we respect.
  * AMFI's quarterly average AUM per scheme (amfiindia.com): the official fund size, used to check Kuvera's
    figures and to fill gaps.

Everything here is optional to the rankings: when a source fails, the previous snapshot is used while it is
recent, and after that the affected scores fall back to neutral rather than guessing.
"""
import re
import time
from datetime import date
from statistics import median
from typing import Callable, Dict, Iterable, List, Optional

FACTS_SCHEMA_VERSION = 1
HOLDINGS_SCHEMA_VERSION = 1

KUVERA_LIST_URL = "https://api.kuvera.in/mf/api/v4/fund_schemes/list.json"
KUVERA_SCHEMES_URL = "https://api.kuvera.in/mf/api/v5/fund_schemes/{codes}.json"
KUVERA_HOLDINGS_URL = "https://api.kuvera.in/mf/api/v5/fund_portfolio_holdings/{codes}.json"
KUVERA_BATCH = 100
KUVERA_DELAY_SECONDS = 10            # Crawl-delay in kuvera.in/robots.txt

AMFI_AAUM_URL = "https://www.amfiindia.com/api/average-aum-schemewise?strType=Categorywise&MF_ID=0"

REFRESH_DAYS = 7                     # facts change monthly; fetching weekly keeps the load on the sources light
MAX_AGE_DAYS = 60                    # older than this, a snapshot is too stale to score funds on

CASH_RE = re.compile(r"treps|tri-?party|repo|net current|net receivable|cash|margin|call money|"
                     r"current assets|liquid", re.IGNORECASE)
HIGH_GRADE_RE = re.compile(r"\bAAA|A1\+|\bSOV|sovereign", re.IGNORECASE)


def _num(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ── Kuvera ──────────────────────────────────────────────────────────────────

def kuvera_direct_growth_codes(listing: dict) -> List[str]:
    """Kuvera codes of every Direct plan's growth option, from the nested category -> fund house -> plans list."""
    codes = []
    for categories in listing.values():
        for houses in (categories or {}).values():
            for plans in (houses or {}).values():
                for p in plans or []:
                    if p.get("re") == "Z" and "direct" in (p.get("n") or "").lower() and p.get("c"):
                        codes.append(p["c"])
    return sorted(set(codes))


def summarise_holdings(rows: List[dict]) -> Optional[dict]:
    """Portfolio shape from one fund's disclosed holdings: size of the equity book, concentration, cash, credit."""
    rows = [r for r in rows or [] if _num(r.get("percentage_to_aum")) is not None]
    if not rows:
        return None
    pdate = max(r.get("portfolio_date") or "" for r in rows) or None
    rows = [r for r in rows if (r.get("portfolio_date") or None) == pdate]

    equity = sorted((r for r in rows if (r.get("security_asset_class") or "").lower().startswith("equity")),
                    key=lambda r: -_num(r["percentage_to_aum"]))
    cash = [r for r in rows if not (r.get("security_asset_class") or "").lower().startswith("equity")
            and CASH_RE.search(f"{r.get('company_name') or ''} {r.get('security_name') or ''}")]
    rated = [r for r in rows if r.get("credit_rating")]
    low_grade = [r for r in rated if not HIGH_GRADE_RE.search(r["credit_rating"])]
    total = sum(_num(r["percentage_to_aum"]) for r in rows)
    if not 80 <= total <= 120:      # a partial or garbled disclosure tells us nothing reliable
        return None

    def pct(rs):
        return round(sum(_num(r["percentage_to_aum"]) for r in rs), 2)

    return {
        "portfolio_date": pdate,
        "stocks": len(equity),
        "equity_pct": pct(equity),
        "top10_pct": pct(equity[:10]) if equity else None,
        "cash_pct": pct(cash),
        "low_grade_pct": pct(low_grade) if rated else None,
        "holdings": [[r.get("holding_isin") or "", (r.get("company_name") or "").strip(),
                      round(_num(r["percentage_to_aum"]), 3)] for r in equity],
    }


def _managers(value) -> List[str]:
    return [m.strip() for m in re.split(r"[;,]|\band\b", value or "") if m.strip()]


def kuvera_facts(get_json: Callable[[str], object], isin_to_code: Dict[str, str], wanted: Iterable[str],
                 sleep: Callable[[float], None] = time.sleep) -> Dict[str, dict]:
    """AMFI code -> facts for the wanted schemes. get_json(url) returns parsed JSON or raises."""
    wanted = set(wanted)
    codes = kuvera_direct_growth_codes(get_json(KUVERA_LIST_URL))
    by_amfi: Dict[str, dict] = {}
    kuvera_of: Dict[str, str] = {}
    for i in range(0, len(codes), KUVERA_BATCH):
        sleep(KUVERA_DELAY_SECONDS)
        for s in get_json(KUVERA_SCHEMES_URL.format(codes="|".join(codes[i:i + KUVERA_BATCH]))) or []:
            amfi = isin_to_code.get(s.get("ISIN") or "")
            if amfi not in wanted:
                continue
            aum = _num(s.get("aum"))
            by_amfi[amfi] = {
                "ter": _num(s.get("expense_ratio")),
                "ter_date": s.get("expense_ratio_date"),
                "aum_cr": round(aum / 10, 1) if aum else None,      # Kuvera reports AUM in ₹10 lakh units
                "managers": _managers(s.get("fund_manager")),
                "turnover": _num(s.get("portfolio_turnover")),
            }
            kuvera_of[s["code"]] = amfi

    holding_codes = sorted(kuvera_of)
    for i in range(0, len(holding_codes), KUVERA_BATCH):
        sleep(KUVERA_DELAY_SECONDS)
        batch = get_json(KUVERA_HOLDINGS_URL.format(codes="|".join(holding_codes[i:i + KUVERA_BATCH]))) or {}
        for kcode, rows in batch.items():
            if kcode in kuvera_of and isinstance(rows, list):
                summary = summarise_holdings(rows)
                if summary:
                    by_amfi[kuvera_of[kcode]].update(summary)
    return by_amfi


# ── AMFI average AUM ────────────────────────────────────────────────────────

def amfi_scheme_aum(get_json: Callable[[str], object], scheme_map: Dict[str, dict]) -> Dict[str, float]:
    """Direct-Growth AMFI code -> the whole scheme's average AUM in ₹ crore (every plan and option added up)."""
    years = get_json(AMFI_AAUM_URL)["data"]
    fy = years[0]["id"]
    periods = get_json(f"{AMFI_AAUM_URL}&fyId={fy}")["data"]["periods"]
    data = get_json(f"{AMFI_AAUM_URL}&fyId={fy}&periodId={periods[0]['id']}")["data"]
    totals: Dict[str, float] = {}
    for group in data:
        for s in group.get("schemes") or []:
            code = str(s.get("AMFI_Code") or "")
            twin = (scheme_map.get(code) or {}).get("twin")
            aum = s.get("AverageAumForTheMonth") or {}
            lakh = sum(_num(v) or 0 for v in aum.values())
            if twin and lakh:
                totals[twin] = totals.get(twin, 0.0) + lakh / 100
    return {k: round(v, 1) for k, v in totals.items()}


def reconcile_aum(facts: Dict[str, dict], amfi: Dict[str, float]) -> str:
    """Prefer Kuvera's month-end AUM when it agrees with AMFI's in scale; otherwise use AMFI's. Returns the source."""
    pairs = [(f["aum_cr"], amfi[c]) for c, f in facts.items() if f.get("aum_cr") and amfi.get(c)]
    trusted = len(pairs) >= 50 and 0.6 <= median(k / a for k, a in pairs) <= 1.6
    for code, f in facts.items():
        if not trusted or not f.get("aum_cr"):
            f["aum_cr"] = amfi.get(code)
    for code, aum in amfi.items():
        facts.setdefault(code, {}).setdefault("aum_cr", aum)
    return "kuvera" if trusted else "amfi"


# ── Fund manager history ────────────────────────────────────────────────────

def update_managers(seen: Dict[str, Dict[str, str]], facts: Dict[str, dict], today: str) -> None:
    """Remember the first date we saw each manager on each fund, so later changes can be dated.

    Managers already there when tracking began carry the baseline date: we don't know how long before that they
    started.
    """
    for code, f in facts.items():
        names = f.get("managers") or []
        if not names:
            continue
        known = seen.setdefault(code, {})
        for n in names:
            known.setdefault(n, today)


def manager_info(seen: Dict[str, str], current: List[str], baseline: str, today: date) -> dict:
    """Newest current manager's start (as far as we know) and whether the team changed in the last year."""
    starts = [seen.get(n) for n in current if seen.get(n)]
    if not starts:
        return {"manager_since": None, "manager_changed": None}
    newest = max(starts)
    changed = newest > baseline and (today - date.fromisoformat(newest)).days <= 365
    return {"manager_since": None if newest == baseline else newest, "manager_changed": changed}


# ── Size ────────────────────────────────────────────────────────────────────

# Beyond these sizes (₹ crore) a fund can't take meaningful positions in the smaller companies its category is
# meant to own: a stock doubling barely moves a NAV spread over hundreds of holdings, and large funds struggle to
# buy or sell small stocks without moving the price. Score falls as capacity / AUM above the threshold.
CAPACITY_CR = {"small_cap": 15_000, "mid_cap": 35_000, "large_mid": 50_000, "flexi_cap": 75_000, "elss": 40_000}
# Below these, a fund risks being merged or closed, tends to charge more, and a few large investors leaving can
# force it to sell. Score falls linearly to 0 at a fifth of the threshold.
MIN_AUM_CR = {"equity": 500, "hybrid": 500, "debt": 1_000}


def size_fit(aum_cr: Optional[float], bucket: str, sleeve: str) -> Optional[float]:
    """0..1, 1 = a comfortable size for the category. None when the size is unknown."""
    if not aum_cr:
        return None
    small = MIN_AUM_CR[sleeve]
    if aum_cr < small:
        return round(max(0.0, (aum_cr - small / 5) / (small - small / 5)), 3)
    cap = CAPACITY_CR.get(bucket)
    if cap and aum_cr > cap:
        return round(cap / aum_cr, 3)
    return 1.0


def size_note(f: dict, bucket: str, sleeve: str, label: str) -> Optional[str]:
    """One plain sentence on the fund's size when it matters, else None."""
    aum = f.get("aum_cr")
    if not aum:
        return None
    amount = f"₹{aum:,.0f} crore"
    cap = CAPACITY_CR.get(bucket)
    if cap and aum > cap:
        spread = f" across {f['stocks']} stocks" if f.get("stocks") else ""
        return (f"At {amount} it is large for a {label} fund: money spread{spread} means one company doing well "
                f"moves its NAV little, and buying or selling smaller stocks is harder.")
    if aum < MIN_AUM_CR[sleeve]:
        return f"At {amount} it is small, so a few large investors leaving could force it to sell."
    return None


def is_fresh(snapshot: Optional[dict], today: date, days: int) -> bool:
    try:
        return (today - date.fromisoformat(snapshot["fetched_at"][:10])).days < days
    except (TypeError, KeyError, ValueError):
        return False
