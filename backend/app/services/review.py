"""Portfolio review: rates every fund an investor holds and checks the portfolio as a whole.

Each fund is rated through its Direct-Growth twin against the other funds in
its category, using the same nightly rankings that build new plans:
    Top 25%         top quarter of its category
    Above average   second quarter
    Below average   third quarter
    Bottom 25%      bottom quarter
Regular plans and IDCW options share their twin's rating, since they hold the
same portfolio; they are flagged separately for cost and tax.

Portfolio checks follow what established review tools look at: asset mix
against the investor's plan, Regular plans, funds that duplicate each other,
too many funds, thematic concentration, IDCW options, and tax on gains.
"""
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from app.services import nav as navs
from app.services.catalog import BUCKETS
from app.services.ranking import tidy_name
from app.services.fund_facts import size_fit, size_note
from app.services.rankings_store import HoldingsStore, RankingsStore, SchemeMapStore
from app.services.rankings_store import holdings as default_holdings
from app.services.rankings_store import scheme_map as default_scheme_map
from app.services.rankings_store import store as default_rankings

STATUSES = {
    "in_form":     ("Top 25%", "Keep investing."),
    "on_track":    ("Above average", "Keep investing."),
    "off_track":   ("Below average", "Hold, and watch it. It's in the bottom half of its category; "
                                 "if it slips to the bottom quarter we'll suggest a switch."),
    "out_of_form": ("Bottom 25%", "Consider moving new SIPs to a better-ranked fund in the same category. "
                                   "Before selling existing units, check exit load and capital gains tax."),
    "not_rated":   ("Not rated", ""),
}
LTCG_EXEMPTION = 125_000           # ₹1.25 lakh of long-term equity gains a year is tax-free
EQUITY_LT_DAYS = 365
ELSS_LOCK_DAYS = 3 * 365
MAX_EQUITY_FUNDS = 6
THEMATIC_LIMIT = 0.20              # share of equity in sectoral / thematic funds before we flag it
DRIFT_LIMIT = 10                   # percentage points of equity away from the saved plan
OVERLAP_LIMIT = 40                 # % of two funds' portfolios in the same stocks before we flag the pair
OVERSIZED_FIT = 0.6                # size_fit below this: the fund is well past what its category can absorb
COSTLY_GAP = 0.4                   # expense ratio this many points above the category median

DEBT_NAME_RE = re.compile(r"\b(sdl|gilt|g-sec|gsec|bond|debt|psu|crisil ibx|t-bill|liquid|money market|"
                          r"target maturity|nifty .*(aaa|psu))", re.IGNORECASE)
GOLD_RE = re.compile(r"\bgold\b|\bsilver\b|precious", re.IGNORECASE)
THEMATIC_RE = re.compile(r"sectoral|thematic", re.IGNORECASE)
INFLOWS = {"PURCHASE", "PURCHASE_SIP", "SWITCH_IN", "SWITCH_IN_MERGER", "GIFT_IN", "REVERSAL"}
OUTFLOWS = {"REDEMPTION", "SWITCH_OUT", "SWITCH_OUT_MERGER", "GIFT_OUT"}


def _fmt(n: float) -> str:
    """Indian-style rupees, short: ₹4.2 L, ₹1.35 Cr."""
    if n is None:
        return "—"
    a = abs(n)
    sign = "-" if n < 0 else ""
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:.1f} L"
    return f"{sign}₹{a:,.0f}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# ── Classification ──────────────────────────────────────────────────────────

def sleeve_for(scheme: dict) -> str:
    """equity | hybrid | debt | other, for any scheme (rated or not)."""
    if scheme.get("bucket"):
        return BUCKETS[scheme["bucket"]].sleeve
    cat, name = scheme["category"].lower(), scheme["name"]
    if GOLD_RE.search(name):
        return "other"
    if "equity scheme" in cat or "elss" in cat:
        return "equity"
    if "hybrid" in cat:
        return "hybrid"
    if any(k in cat for k in ("debt scheme", "income", "liquid", "money market", "gilt")):
        return "debt"
    if "overseas" in cat:
        return "equity"
    if "index" in cat or "etf" in cat:
        return "debt" if DEBT_NAME_RE.search(name) else "equity"
    return "other"


def equity_taxed(scheme: dict, sleeve: str) -> bool:
    """Taxed as equity: at least 65% in Indian shares (equity, ELSS, arbitrage, aggressive hybrid)."""
    cat = scheme["category"].lower()
    if "overseas" in cat:
        return False
    return sleeve == "equity" or "arbitrage" in cat or "aggressive hybrid" in cat


def category_label(scheme: dict) -> str:
    if scheme.get("bucket"):
        return BUCKETS[scheme["bucket"]].label
    cat = scheme["category"]
    return cat.split(" - ", 1)[1].strip() if " - " in cat else cat


# ── Returns and tax lots ────────────────────────────────────────────────────

def xirr(flows: List[Tuple[date, float]]) -> Optional[float]:
    """Annualised return of dated cash flows (negative = money in). None if it can't be solved."""
    flows = [(d, a) for d, a in flows if a]
    if len(flows) < 2 or not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        return None
    t0 = min(d for d, _ in flows)
    years = [((d - t0).days / 365.0, a) for d, a in flows]
    if max(t for t, _ in years) < 1 / 365:
        return None

    def npv(r):
        return sum(a / (1 + r) ** t for t, a in years)

    lo, hi = -0.99, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):        # bisection: slow but never diverges
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-6:
            break
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def open_lots(txns: List[list]) -> List[Tuple[date, float, float]]:
    """Units still held, oldest first, as (bought_on, units, cost) using first-in-first-out."""
    lots: List[List] = []
    for d, kind, amount, units in sorted(txns, key=lambda t: t[0]):
        if not units:
            continue
        day = date.fromisoformat(d[:10])
        if units > 0:
            # Reinvested dividends and bonus units have no fresh cost of their own beyond their value.
            cost = abs(amount) if amount else 0.0
            lots.append([day, units, cost])
        else:
            to_sell = -units
            while to_sell > 1e-6 and lots:
                lot = lots[0]
                take = min(lot[1], to_sell)
                lot[2] -= lot[2] * take / lot[1] if lot[1] else 0
                lot[1] -= take
                to_sell -= take
                if lot[1] <= 1e-6:
                    lots.pop(0)
    return [(d, u, c) for d, u, c in lots if u > 1e-6]


def cash_flows(txns: List[list]) -> List[Tuple[date, float]]:
    flows = []
    for d, kind, amount, _units in txns:
        if amount is None:
            continue
        day = date.fromisoformat(d[:10])
        if kind in INFLOWS or kind in OUTFLOWS:
            flows.append((day, -amount))          # purchases are positive in the CAS: money going in
        elif kind == "DIVIDEND_PAYOUT":
            flows.append((day, abs(amount)))
    return flows


# ── Review ──────────────────────────────────────────────────────────────────

def rate_fund(twin: Optional[str], bucket: Optional[str], data: dict) -> dict:
    """Quartile rating of a Direct-Growth fund within its category's nightly ranking."""
    if not bucket:
        return {"status": "not_rated", "reason": "We don't rate this category yet."}
    funds = data["buckets"].get(bucket, {}).get("funds", [])
    pos = next((i for i, f in enumerate(funds) if f["code"] == twin), None)
    if pos is None:
        years = BUCKETS[bucket].min_years
        return {"status": "not_rated",
                "reason": f"Under {years:g} years of history, too new to rate fairly against its category."}
    n = len(funds)
    share = pos / (n - 1) if n > 1 else 0.0
    status = ("in_form" if share < 0.25 else "on_track" if share < 0.5
              else "off_track" if share < 0.75 else "out_of_form")
    f = funds[pos]
    stats = data["buckets"][bucket]["stats"]
    return {
        "status": status, "rank": pos + 1, "rank_of": n,
        "reason": f"Ranked {pos + 1} of {n} {BUCKETS[bucket].label} funds on returns, consistency, falls, "
                  "costs, fund size and record against its index.",
        "metrics": {k: f.get(k) for k in ("cagr_1y", "cagr_3y", "cagr_5y", "max_drawdown", "volatility",
                                          "rolling_median", "years_history", "ter", "aum_cr", "excess_return",
                                          "beat_rate", "down_capture", "stocks", "top10_pct", "cash_pct",
                                          "managers", "manager_since", "manager_changed")},
        "category": {k: stats.get(f"median_{k}") for k in ("cagr_1y", "cagr_3y", "cagr_5y", "max_drawdown",
                                                              "ter")},
        "benchmark": data["buckets"][bucket].get("benchmark"),
        "size_note": size_note(f, bucket, BUCKETS[bucket].sleeve, BUCKETS[bucket].label.lower()),
        "size_fit": size_fit(f.get("aum_cr"), bucket, BUCKETS[bucket].sleeve),
    }


class Reviewer:
    def __init__(self, rankings: RankingsStore = default_rankings, schemes: SchemeMapStore = default_scheme_map,
                 fetch_histories=None, holdings: HoldingsStore = default_holdings):
        self.rankings = rankings
        self.schemes = schemes
        self.holdings = holdings
        self.fetch_histories = fetch_histories or (lambda codes: navs.histories(codes))

    def _rate(self, twin: Optional[str], bucket: Optional[str], data: dict) -> dict:
        return rate_fund(twin, bucket, data)

    def _alternatives(self, bucket: str, exclude: str, amc: str, data: dict) -> List[dict]:
        funds = data["buckets"].get(bucket, {}).get("funds", [])
        min_years = 5 if BUCKETS[bucket].sleeve != "debt" else 3
        seasoned = [f for f in funds if f["years_history"] >= min_years] or funds
        picks = [f for f in seasoned if f["code"] != exclude and f["amc"] != amc][:3]
        rank = {f["code"]: i + 1 for i, f in enumerate(funds)}
        return [{"code": f["code"], "name": f["name"], "amc": f["amc"], "rank": rank[f["code"]], "rank_of": len(funds),
                 "info_url": self.schemes.fund_page_url(f["code"]),
                 "cagr_3y": f.get("cagr_3y"), "cagr_5y": f.get("cagr_5y"), "max_drawdown": f.get("max_drawdown")}
                for f in picks]

    def review(self, holdings: List[dict], target: Optional[dict] = None, today: Optional[date] = None) -> dict:
        today = today or date.today()
        data = self.rankings.get()
        schemes = self.schemes.schemes()

        # Merge the same scheme held in several folios.
        merged: Dict[str, dict] = {}
        unknown: List[dict] = []
        for h in holdings:
            if not h.get("code") or h["code"] not in schemes:
                unknown.append(h)
                continue
            m = merged.setdefault(h["code"], {"code": h["code"], "ids": [], "units": 0.0, "cost": 0.0,
                                              "cost_known": True, "txns": [], "cas_nav": None,
                                              "cas_nav_date": None, "partial": False, "sources": set()})
            m["ids"].append(h["id"])
            m["sources"].add(h["source"])
            m["units"] += h["units"]
            if h.get("cost") is None:
                m["cost_known"] = False
            else:
                m["cost"] += h["cost"]
            m["txns"] += h.get("txns") or []
            m["partial"] |= (h.get("open_units") or 0) > 0.001 or not h.get("txns")
            m["cas_nav"], m["cas_nav_date"] = h.get("cas_nav") or m["cas_nav"], h.get("cas_nav_date") or m["cas_nav_date"]

        # Prices for every holding, plus Direct twins of Regular plans to measure the cost gap.
        regular_twins = {schemes[c]["twin"] for c in merged
                         if not schemes[c]["direct"] and schemes[c]["twin"]}
        history = self.fetch_histories(list(merged) + list(regular_twins))

        rows = []
        for code, m in merged.items():
            s = schemes[code]
            sleeve = sleeve_for(s)
            last = navs.latest(history.get(code, []))
            price, price_date = last if last else (m["cas_nav"], m["cas_nav_date"])
            value = m["units"] * price if price else None
            rating = self._rate(s["twin"], s["bucket"], data)

            invested = m["cost"] if m["cost_known"] else None
            lt_gain = st_gain = elss_locked = holding_xirr = None
            if not m["partial"] and price:
                lots = open_lots(m["txns"])
                invested = sum(c for _, _, c in lots)
                if equity_taxed(s, sleeve):
                    lt_gain = sum(u * price - c for d, u, c in lots if (today - d).days > EQUITY_LT_DAYS)
                    st_gain = sum(u * price - c for d, u, c in lots if (today - d).days <= EQUITY_LT_DAYS)
                if s["bucket"] == "elss":
                    elss_locked = sum(u * price for d, u, _ in lots if (today - d).days < ELSS_LOCK_DAYS)
                holding_xirr = xirr(cash_flows(m["txns"]) + [(today, m["units"] * price)])

            cost_gap = None
            if not s["direct"] and s["twin"]:
                direct_1y = navs.one_year_return(history.get(s["twin"], []))
                regular_1y = navs.one_year_return(history.get(code, []))
                if direct_1y is not None and regular_1y is not None:
                    cost_gap = max(direct_1y - regular_1y, 0.0)

            label, action = STATUSES[rating["status"]]
            action_type = {"in_form": "continue", "on_track": "continue", "off_track": "watch",
                           "out_of_form": "switch"}.get(rating["status"], "review")
            if rating["status"] == "not_rated":
                action = rating["reason"]
            rows.append({
                "code": code, "ids": m["ids"], "source": "manual" if m["sources"] == {"manual"} else "cas",
                "name": tidy_name(s["name"]).rstrip(". "), "amc": s["amc"], "category": category_label(s), "sleeve": sleeve,
                "plan": "Direct" if s["direct"] else "Regular", "option": "Growth" if s["growth"] else "IDCW",
                "info_url": self.schemes.fund_page_url(code),
                "thematic": bool(THEMATIC_RE.search(s["category"])),
                "units": round(m["units"], 4), "nav": price, "nav_date": price_date,
                "value": round(value, 2) if value is not None else None,
                "invested": round(invested, 2) if invested is not None else None,
                "gain": round(value - invested, 2) if value is not None and invested else None,
                "xirr": holding_xirr, "lt_gain": lt_gain, "st_gain": st_gain, "elss_locked": elss_locked,
                "cost_gap": cost_gap,
                "rating": {**rating, "label": label}, "action": {"type": action_type, "text": action},
                "alternatives": (self._alternatives(s["bucket"], s["twin"], s["amc"], data)
                                 if rating["status"] in ("off_track", "out_of_form") else []),
                "partial": m["partial"], "_flows": cash_flows(m["txns"]) if not m["partial"] else None,
            })

        rows.sort(key=lambda r: -(r["value"] or 0))
        return self._portfolio(rows, unknown, target, today, data)

    def _portfolio(self, rows: List[dict], unknown: List[dict], target: Optional[dict], today: date,
                   data: dict) -> dict:
        valued = [r for r in rows if r["value"] is not None]
        total = sum(r["value"] for r in valued)
        # Gains cover the funds whose purchase cost we know (hand-added funds may not say).
        costed = [r for r in valued if r["invested"] is not None]
        invested = sum(r["invested"] for r in costed) if costed else None
        costed_value = sum(r["value"] for r in costed)

        flows_known = valued and all(r["_flows"] is not None for r in valued)
        portfolio_xirr = (xirr([f for r in valued for f in r["_flows"]] + [(today, total)])
                          if flows_known else None)

        mix = defaultdict(float)
        for r in valued:
            mix[r["sleeve"]] += r["value"]
        allocation = {k: round(100 * mix[k] / total, 1) if total else 0.0 for k in ("equity", "hybrid", "debt", "other")}

        by_status = defaultdict(lambda: {"count": 0, "value": 0.0})
        for r in valued:
            b = by_status[r["rating"]["status"]]
            b["count"] += 1
            b["value"] += r["value"]
        rated_value = sum(v["value"] for k, v in by_status.items() if k != "not_rated")
        good_value = by_status["in_form"]["value"] + by_status["on_track"]["value"]

        stocks, overlaps = self._look_through(valued)
        insights = self._insights(rows, valued, total, allocation, target, by_status, overlaps)

        lt = sum(r["lt_gain"] or 0 for r in valued if r["lt_gain"] is not None)
        st = sum(r["st_gain"] or 0 for r in valued if r["st_gain"] is not None)
        elss = sum(r["elss_locked"] or 0 for r in valued if r["elss_locked"] is not None)
        tax_complete = all(not r["partial"] for r in valued)

        for r in rows:
            r.pop("_flows", None)
        return {
            "as_of": today.isoformat(),
            "rankings_date": data.get("nav_date"),
            "summary": {
                "value": round(total, 2), "invested": round(invested, 2) if invested is not None else None,
                "gain": round(costed_value - invested, 2) if invested else None,
                "gain_pct": round(100 * (costed_value - invested) / invested, 2) if invested else None,
                "xirr": portfolio_xirr, "funds": len(rows), "funds_with_cost": len(costed),
            },
            "health": {
                "good_pct": round(100 * good_value / rated_value, 1) if rated_value else None,
                "rated_pct": round(100 * rated_value / total, 1) if total else None,
                "by_status": {k: {"count": v["count"], "value": round(v["value"], 2)} for k, v in by_status.items()},
            },
            "allocation": allocation,
            "target": target,
            "tax": {"lt_gain": round(lt, 2), "st_gain": round(st, 2), "elss_locked": round(elss, 2),
                    "complete": tax_complete, "ltcg_exemption": LTCG_EXEMPTION},
            "insights": insights,
            "top_stocks": stocks,
            "overlaps": overlaps,
            "holdings": rows,
            "unrecognised": [{"id": h["id"], "name": h.get("name"), "units": h.get("units")} for h in unknown],
        }

    def _look_through(self, valued: List[dict]) -> Tuple[List[dict], List[dict]]:
        """The companies your money is really in, across all funds, and pairs of funds that own the same stocks.

        Uses each fund's latest disclosed portfolio (its Direct-Growth twin's, which is the same portfolio).
        """
        books = {}
        for r in valued:
            twin = (self.schemes.schemes().get(r["code"]) or {}).get("twin")
            rows = self.holdings.of(twin) if twin else []
            if rows:
                books[r["code"]] = {(isin or name): (name, pct) for isin, name, pct in rows}
        equity_money = sum(r["value"] for r in valued if r["code"] in books)
        exposure: Dict[str, list] = {}
        for r in valued:
            for key, (name, pct) in books.get(r["code"], {}).items():
                e = exposure.setdefault(key, [name, 0.0, 0])
                e[1] += r["value"] * pct / 100
                e[2] += 1
        top = sorted(exposure.values(), key=lambda e: -e[1])[:10]
        stocks = [{"name": n, "value": round(v, 2), "pct": round(100 * v / equity_money, 2) if equity_money else None,
                   "funds": k} for n, v, k in top]

        names = {r["code"]: r["name"] for r in valued}
        codes = sorted(books)
        overlaps = []
        for i, a in enumerate(codes):
            for b in codes[i + 1:]:
                common = books[a].keys() & books[b].keys()
                share = sum(min(books[a][k][1], books[b][k][1]) for k in common)
                if share >= 1:
                    overlaps.append({"a": names[a], "b": names[b], "pct": round(share, 1), "common": len(common)})
        overlaps.sort(key=lambda o: -o["pct"])
        return stocks, overlaps[:10]

    def _insights(self, rows, valued, total, allocation, target, by_status, overlaps=()) -> List[dict]:
        out = []
        share = (lambda v: f"{100 * v / total:.0f}%") if total else (lambda v: "—")

        bad = [r for r in valued if r["rating"]["status"] == "out_of_form"]
        if bad:
            value = sum(r["value"] for r in bad)
            out.append({"level": "high", "key": "out_of_form",
                        "title": f"{_plural(len(bad), 'fund')} in the bottom 25% of their category ({share(value)} of your money)",
                        "text": "These are in the bottom quarter of their category on long-run returns, consistency "
                                "and falls: " + ", ".join(r["name"] for r in bad) + ". Consider pointing new SIPs to "
                                "a better-ranked fund in the same category; the fund cards list options."})

        regular = [r for r in valued if r["plan"] == "Regular"]
        if regular:
            value = sum(r["value"] for r in regular)
            gaps = [(r["value"], r["cost_gap"]) for r in regular if r["cost_gap"] is not None]
            gap_text = ""
            if gaps:
                yearly = sum(v * g for v, g in gaps)
                avg = yearly / sum(v for v, _ in gaps)
                gap_text = (f" Over the last year their Direct plans returned about {avg * 100:.1f}% more, "
                            f"roughly {_fmt(yearly)} a year on what you hold now.")
            out.append({"level": "high" if value > 0.25 * total else "medium", "key": "regular_plans",
                        "title": f"{_plural(len(regular), 'fund')} in Regular plans ({_fmt(value)})",
                        "text": "Regular plans pay a distributor commission out of your returns every year; Direct "
                                "plans of the same fund don't." + gap_text + " New SIPs can move to Direct right "
                                "away. Switching existing units counts as selling, so check exit load and tax first."})

        by_cat = defaultdict(list)
        for r in valued:
            if r["sleeve"] in ("equity", "hybrid"):
                by_cat[r["category"]].append(r)
        for cat, rs in by_cat.items():
            if len(rs) < 2:
                continue
            best = min(rs, key=lambda r: r["rating"].get("rank") or 10**6)["name"]
            out.append({"level": "medium" if len(rs) >= 3 else "low", "key": f"duplicate:{cat}",
                        "title": f"{len(rs)} {cat} funds",
                        "text": "Funds in the same category usually own many of the same stocks, so each extra one "
                                f"adds little diversification. {'One or two' if len(rs) >= 3 else 'One'} good fund is "
                                f"usually enough; of yours, {best} ranks highest."})

        heavy = [o for o in overlaps if o["pct"] >= OVERLAP_LIMIT]
        if heavy:
            pairs = "; ".join(f"{o['a']} and {o['b']} ({o['pct']:.0f}%)" for o in heavy[:3])
            out.append({"level": "medium", "key": "overlap",
                        "title": f"{_plural(len(heavy), 'pair')} of funds own largely the same stocks",
                        "text": f"Measured on their latest disclosed portfolios: {pairs}. Money in both is close to "
                                "money in one, with two sets of costs. Consider keeping the better-ranked one."})

        big = [r for r in valued if (r["rating"].get("size_fit") or 1) < OVERSIZED_FIT]
        if big:
            out.append({"level": "medium", "key": "oversized",
                        "title": f"{_plural(len(big), 'fund')} very large for {'its' if len(big) == 1 else 'their'} category",
                        "text": " ".join(r["rating"]["size_note"] for r in big[:2] if r["rating"].get("size_note"))
                                + " Past returns were earned when the fund was smaller; consider a smaller, "
                                  "well-ranked fund in the same category for new money."})

        costly = [r for r in valued if r["plan"] == "Direct"
                  and (r["rating"].get("metrics") or {}).get("ter") is not None
                  and (r["rating"].get("category") or {}).get("ter") is not None
                  and r["rating"]["metrics"]["ter"] - r["rating"]["category"]["ter"] >= COSTLY_GAP]
        if costly:
            out.append({"level": "low", "key": "costly",
                        "title": f"{_plural(len(costly), 'fund')} with high costs for {'its' if len(costly) == 1 else 'their'} category",
                        "text": "; ".join(f"{r['name']} charges {r['rating']['metrics']['ter']:.2f}% a year vs "
                                          f"{r['rating']['category']['ter']:.2f}% typical" for r in costly[:3])
                                + ". Costs are taken every year whatever the fund returns."})

        changed = [r for r in valued if (r["rating"].get("metrics") or {}).get("manager_changed")]
        if changed:
            out.append({"level": "low", "key": "manager_change",
                        "title": f"New fund manager at {_plural(len(changed), 'fund')}",
                        "text": "The past returns of " + ", ".join(r["name"] for r in changed) + " were earned by "
                                "a different team. Keep an eye on them over the next year."})

        equity_funds = [r for r in valued if r["sleeve"] == "equity"]
        if len(equity_funds) > MAX_EQUITY_FUNDS:
            out.append({"level": "medium", "key": "too_many",
                        "title": f"{len(equity_funds)} equity funds",
                        "text": f"Beyond {MAX_EQUITY_FUNDS - 2}–{MAX_EQUITY_FUNDS} equity funds, more funds mostly add "
                                "overlap and paperwork rather than diversification."})

        equity_value = sum(r["value"] for r in equity_funds)
        thematic = sum(r["value"] for r in equity_funds if r["thematic"])
        if equity_value and thematic / equity_value > THEMATIC_LIMIT:
            out.append({"level": "medium", "key": "thematic",
                        "title": f"{100 * thematic / equity_value:.0f}% of your equity is in sector or theme funds",
                        "text": "Sector and theme funds are concentrated bets that can lag for years. Many advisers "
                                f"keep them under {THEMATIC_LIMIT:.0%} of equity."})

        if target and target.get("asset_mix"):
            want = target["asset_mix"].get("equity", 0)
            have = allocation["equity"]
            if abs(have - want) >= DRIFT_LIMIT:
                more = have > want
                out.append({"level": "medium", "key": "drift",
                            "title": f"Equity is {have:.0f}% vs {want:.0f}% in your plan",
                            "text": f"Your saved plan \"{target.get('name')}\" holds {want:.0f}% in equity. You have "
                                    f"{'more' if more else 'less'} than that, which means "
                                    f"{'bigger swings than you signed up for' if more else 'slower growth than planned'}. "
                                    "Directing new SIPs toward the under-weight part is the gentlest way to rebalance."})

        idcw = [r for r in valued if r["option"] == "IDCW"]
        if idcw:
            out.append({"level": "low", "key": "idcw",
                        "title": f"{_plural(len(idcw), 'fund')} in IDCW (dividend) option",
                        "text": "IDCW payouts are taxed at your income-tax slab and stop that money compounding. For "
                                "long-term goals the Growth option of the same fund is usually better."})

        unrated = [r for r in valued if r["rating"]["status"] == "not_rated"]
        if unrated:
            out.append({"level": "low", "key": "unrated",
                        "title": f"{_plural(len(unrated), 'fund')} not rated",
                        "text": "We rate funds against their category once they have enough history, and don't yet "
                                "rate sector, theme, international or some debt categories: "
                                + ", ".join(r["name"] for r in unrated) + "."})

        if any(r["partial"] for r in valued if r["source"] == "cas"):
            out.append({"level": "low", "key": "partial",
                        "title": "Some returns and tax figures are missing",
                        "text": "Your statement doesn't go back to your first investment in some funds, so we can't "
                                "work out their XIRR or tax lots. Request a CAS with the period set to "
                                "\"Since inception\"."})

        out.sort(key=lambda i: ["high", "medium", "low"].index(i["level"]))
        if not any(i["level"] in ("high", "medium") for i in out) and valued:
            out.insert(0, {"level": "good", "key": "healthy", "title": "Your portfolio is in good shape",
                           "text": "No fund is in the bottom 25% of its category and we found nothing major to fix. We re-check it against "
                                   "fresh data every night."})
        return out
