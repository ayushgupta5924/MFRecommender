"""Turns a CAMS / KFintech Consolidated Account Statement (CAS) into holdings we can review.

A holding is a plain dict so it can be stored as JSON:
    id, source ("cas" | "manual" | "aa" | "pan"), code (AMFI scheme code), isin, name, amc,
    units, cost, cas_nav, cas_nav_date, open_units, txns
where txns is a list of [iso_date, type, amount, units] from the statement.
Only fund-level data is kept; the investor's name, PAN, email, phone and
address on the statement are dropped, and the PDF itself is never saved.
"""
import io
import secrets
from datetime import date
from decimal import Decimal
from typing import Any, List, Optional

from app.services.rankings_store import scheme_map

MAX_PDF_BYTES = 10 * 1024 * 1024
MIN_UNITS = 0.001


class StatementError(ValueError):
    """A problem with the uploaded statement that the investor can fix."""


def new_id() -> str:
    return secrets.token_hex(6)


def _num(v) -> Optional[float]:
    if v is None:
        return None
    return float(v) if isinstance(v, (Decimal, int, float)) else float(str(v).replace(",", ""))


def _iso(d) -> str:
    return d.isoformat() if isinstance(d, date) else str(d)


def resolve_code(amfi: Optional[str], isin: Optional[str]) -> Optional[str]:
    schemes = scheme_map.schemes()
    if amfi and str(amfi) in schemes:
        return str(amfi)
    return scheme_map.code_for_isin(isin) if isin else None


def parse_cas(pdf: bytes, password: str) -> dict:
    if len(pdf) > MAX_PDF_BYTES:
        raise StatementError("That file is too large. A CAS is usually under 2 MB.")
    if not pdf.startswith(b"%PDF"):
        raise StatementError("That doesn't look like a PDF. Upload the CAS PDF you received by email.")

    import casparser
    from casparser.exceptions import CASParseError, IncorrectPasswordError, ParserException

    try:
        # Any: the folios check below tells the mutual fund CAS apart from NSDL/CDSL ones.
        data: Any = casparser.read_cas_pdf(io.BytesIO(pdf), password or "")
    except IncorrectPasswordError:
        raise StatementError("Wrong password. It's the one you chose when requesting the statement "
                             "(often your PAN in capitals).")
    except (CASParseError, ParserException) as e:
        raise StatementError(f"We couldn't read this statement ({e}). Make sure it's a CAMS or KFintech "
                             "Consolidated Account Statement.")
    if not hasattr(data, "folios"):
        raise StatementError("This is a depository (NSDL/CDSL) statement. Upload the mutual fund CAS from "
                             "CAMS or KFintech instead.")

    holdings: List[dict] = []
    for folio in data.folios:
        for s in folio.schemes:
            units = _num(s.close) or 0.0
            if units < MIN_UNITS:
                continue
            code = resolve_code(s.amfi, s.isin)
            txns = [[_iso(t.date), str(getattr(t.type, "value", t.type)), _num(t.amount), _num(t.units)]
                    for t in s.transactions]
            holdings.append({
                "id": new_id(),
                "source": "cas",
                "code": code,
                "isin": s.isin,
                "name": s.scheme,
                "amc": folio.amc,
                "units": round(units, 4),
                "cost": _num(s.valuation.cost),
                "cas_nav": _num(s.valuation.nav),
                "cas_nav_date": _iso(s.valuation.date),
                "open_units": _num(s.open) or 0.0,
                "txns": txns,
            })
    if not holdings:
        raise StatementError("We didn't find any funds with units in this statement.")

    period = data.statement_period
    return {
        "holdings": holdings,
        "statement_from": getattr(period, "from_", None),
        "statement_to": period.to,
        "statement_type": str(getattr(data.cas_type, "value", data.cas_type)),
        "warnings": list(getattr(data, "parse_warnings", []) or []),
    }


def manual_holding(code: str, units: float, invested: Optional[float]) -> dict:
    s = scheme_map.schemes()[code]
    return {
        "id": new_id(),
        "source": "manual",
        "code": code,
        "isin": (s["isins"] or [None])[0],
        "name": s["name"],
        "amc": s["amc"],
        "units": round(units, 4),
        "cost": invested,
        "cas_nav": None,
        "cas_nav_date": None,
        "open_units": 0.0,
        "txns": [],
    }
