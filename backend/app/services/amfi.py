"""Parser for AMFI's daily NAV file (https://www.amfiindia.com/spages/NAVAll.txt).

The file lists every scheme under "<type> Schemes(<category>)" headers and AMC
name lines, followed by rows of:
    code;isin_growth;isin_reinvest;name;plan;option;nav;date
"""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional

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


def parse_navall(lines: Iterable[str], max_age_days: int = 7) -> List[Scheme]:
    """Return open-ended, Direct, Growth schemes that map to a bucket and have a fresh NAV.

    Freshness is measured against the newest NAV date in the file, so a stale
    file still yields a consistent universe.
    """
    rows = []
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
        code, _, _, name, plan, option, nav, nav_date = (p.strip() for p in parts[:8])
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
        rows.append(Scheme(code, name, amc or "", category, bucket.key, nav_value, parsed_date))

    if not rows:
        return []
    reference = reference_nav_date(rows)
    return [r for r in rows if abs((reference - r.nav_date).days) <= max_age_days]


def reference_nav_date(rows: List[Scheme]) -> date:
    """The NAV date most schemes share. Some liquid funds publish next-day NAVs, so max() would overshoot."""
    return Counter(r.nav_date for r in rows).most_common(1)[0][0]
