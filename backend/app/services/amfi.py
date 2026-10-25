"""Parser for AMFI's daily NAV file (https://www.amfiindia.com/spages/NAVAll.txt).

The file lists every scheme under "<type> Schemes(<category>)" headers and AMC
name lines, followed by rows of:
    code;isin_growth;isin_reinvest;name;plan;option;nav;date
"""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, Iterator, List, Optional

from app.services.catalog import bucket_for

NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

_HEADER_RE = re.compile(r"^(Open Ended|Close Ended|Interval Fund) Schemes\s*\((.*)\)\s*$")


@dataclass
class Scheme:
    code: str
    name: str
    amc: str
    category: str
    bucket: str
    nav: float
    nav_date: date


def _is_direct(plan: str, name: str) -> bool:
    return "direct" in plan.lower() or ("direct" in name.lower() and not plan.strip())


def _is_growth(option: str, name: str) -> bool:
    text = (option or name).lower()
    return "growth" in text and "idcw" not in text and "dividend" not in text


def _parse_date(value: str) -> Optional[date]:
    for fmt in ("%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def iter_open_ended(lines: Iterable[str]) -> Iterator[dict]:
    """Every open-ended scheme row, with the category and AMC it was listed under."""
    scheme_type = category = amc = None
    for raw in lines:
        line = raw.strip().lstrip("﻿")
        if not line:
            continue
        header = _HEADER_RE.match(line)
        if header:
            scheme_type, category = header.group(1), header.group(2).strip()
            continue
        parts = line.split(";")
        if len(parts) < 8:
            amc = line
            continue
        if parts[0] == "Scheme Code" or scheme_type != "Open Ended":
            continue
        code, isin_growth, isin_reinvest, name, plan, option, nav, nav_date = (p.strip() for p in parts[:8])
        yield {"code": code, "isins": [i for i in (isin_growth, isin_reinvest) if i.startswith("INF")],
               "name": name, "plan": plan, "option": option, "nav": nav, "nav_date": nav_date,
               "category": category or "", "amc": amc or ""}


def parse_navall(lines: Iterable[str], max_age_days: int = 7) -> List[Scheme]:
    """Return open-ended, Direct, Growth schemes that map to a bucket and have a fresh NAV.

    Freshness is measured against the newest NAV date in the file, so a stale
    file still yields a consistent universe.
    """
    rows = []
    for row in iter_open_ended(lines):
        code, name, plan, option, nav, nav_date = (row[k] for k in ("code", "name", "plan", "option", "nav", "nav_date"))
        category, amc = row["category"], row["amc"]
        if not (_is_direct(plan, name) and _is_growth(option, name)):
            continue
        bucket = bucket_for(category, name)
        parsed_date = _parse_date(nav_date)
        try:
            nav_value = float(nav)
        except ValueError:
            continue
        if bucket is None or parsed_date is None or nav_value <= 0:
            continue
        rows.append(Scheme(code, name, amc, category, bucket.key, nav_value, parsed_date))

    if not rows:
        return []
    reference = reference_nav_date(rows)
    return [r for r in rows if abs((reference - r.nav_date).days) <= max_age_days]


def reference_nav_date(rows: List[Scheme]) -> date:
    """The NAV date most schemes share. Some liquid funds publish next-day NAVs, so max() would overshoot."""
    return Counter(r.nav_date for r in rows).most_common(1)[0][0]


# Words that tell plans and options of one scheme apart; removing them leaves the scheme's own name.
_PLAN_WORDS_RE = re.compile(
    r"\b(direct|regular|plan|option|growth|idcw|dividend|payout|re-?investment|reinvest|bonus|"
    r"income distribution cum capital withdrawal|of|daily|weekly|fortnightly|monthly|quarterly|"
    r"half[- ]yearly|annual|yearly)\b", re.IGNORECASE)


def base_name(name: str) -> str:
    text = _PLAN_WORDS_RE.sub(" ", name.lower())
    text = re.sub(r"[()\-–_/,.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_scheme_map(lines: Iterable[str]) -> Dict[str, dict]:
    """code -> scheme details, including the Direct-Growth code of the same scheme where one exists.

    Investors often hold Regular plans or IDCW options, which we never rank
    directly; this lets a review rate them through their Direct-Growth twin.
    """
    rows = list(iter_open_ended(lines))
    direct_growth: Dict[tuple, List[str]] = {}
    for r in rows:
        if _is_direct(r["plan"], r["name"]) and _is_growth(r["option"], r["name"]):
            direct_growth.setdefault((r["amc"], base_name(r["name"])), []).append(r["code"])
    names = {r["code"]: r["name"] for r in rows}

    out = {}
    for r in rows:
        direct = _is_direct(r["plan"], r["name"])
        growth = _is_growth(r["option"], r["name"])
        if direct and growth:
            twin = r["code"]
        else:
            matches = direct_growth.get((r["amc"], base_name(r["name"])), [])
            twin = matches[0] if len(matches) == 1 else None    # ambiguous names stay unmapped
        bucket = bucket_for(r["category"], names[twin]) if twin else None
        out[r["code"]] = {
            "name": r["name"], "amc": r["amc"], "category": r["category"], "isins": r["isins"],
            "direct": direct, "growth": growth, "twin": twin, "bucket": bucket.key if bucket else None,
        }
    return out


def index_fund_rows(lines: Iterable[str]) -> List[dict]:
    """Open-ended index funds, for picking benchmark stand-ins (catalog.benchmark_funds)."""
    return [{"code": r["code"], "name": r["name"],
             "direct_growth": _is_direct(r["plan"], r["name"]) and _is_growth(r["option"], r["name"])}
            for r in iter_open_ended(lines) if "index fund" in r["name"].lower()]
