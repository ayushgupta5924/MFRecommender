"""Read-only mutual fund holdings by PAN, from MF Central (CAMS + KFintech) through smallcase Gateway.

The investor enters their PAN and the mobile number (or email) registered with their funds. MF Central sends an
OTP there, inside smallcase's own window on our page, so only someone with that phone or inbox can fetch the
data. smallcase then posts the holdings to our webhook. We keep fund-level data only: the payload's userInfo
(name, PAN, address, bank accounts) and folio contact details are dropped, and the PAN itself is never stored.

Switched on by SMALLCASE_GATEWAY_NAME, SMALLCASE_API_SECRET and SMALLCASE_JWT_SECRET (from smallcase's
onboarding). The webhook address, {SITE_URL}/api/pan/webhook, has to be registered with smallcase.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import requests

from app.services.holdings import MIN_UNITS, new_id, resolve_code
from app.services.rankings_store import scheme_map

logger = logging.getLogger(__name__)

API_URL = "https://gatewayapi.smallcase.com"
SDK_URL = "https://gateway.smallcase.com/scdk/2.0.0/scdk.js"
TIMEOUT = 20
TOKEN_SECONDS = 30 * 60
IST = timedelta(hours=5, minutes=30)
# smallcase's transactionDescription -> the transaction types parse_cas produces.
KINDS = {
    "PURCHASE": "PURCHASE", "SIP": "PURCHASE_SIP", "SWITCH IN": "SWITCH_IN",
    "REDEMPTION": "REDEMPTION", "SWP": "REDEMPTION", "SWITCH OUT": "SWITCH_OUT",
}
ERRORS = {
    "mfc_timeout": "MF Central didn't send your holdings in time. Please try again in a few minutes.",
    "mfc_bad_response": "MF Central sent back something we couldn't read. Please try again, or upload your statement.",
}


def _env(key: str) -> str:
    return os.getenv(key, "").strip()


def mfc_enabled() -> bool:
    return all(_env(k) for k in ("SMALLCASE_GATEWAY_NAME", "SMALLCASE_API_SECRET", "SMALLCASE_JWT_SECRET"))


def gateway_name() -> str:
    return _env("SMALLCASE_GATEWAY_NAME")


class MFCError(Exception):
    """smallcase couldn't be reached or refused a request."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def guest_token(now: Optional[float] = None) -> str:
    """The HS256 JWT smallcase expects for a guest (no linked broker account), for the SDK and the API."""
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"guest": True, "exp": int((now or time.time()) + TOKEN_SECONDS)},
                              separators=(",", ":")).encode())
    sig = hmac.new(_env("SMALLCASE_JWT_SECRET").encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(sig)}"


def checksum_ok(payload: dict) -> bool:
    """MF holdings webhooks are signed with HMAC-SHA256(timestamp + transactionId, API secret)."""
    given = payload.get("checksum")
    if not isinstance(given, str):
        return False
    msg = f"{payload.get('timestamp', '')}{payload.get('transactionId', '')}".encode()
    expected = hmac.new(_env("SMALLCASE_API_SECRET").encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)


class GatewayClient:
    def __init__(self, http: Optional[requests.Session] = None):
        self.http = http or requests.Session()

    def create_transaction(self, pan: str, phone: Optional[str], email: Optional[str]) -> dict:
        """{transactionId, expireAt}. PAN and phone/email only pre-fill smallcase's form; MF Central's OTP decides."""
        config = {"pan": pan, "flow": "wealth", **({"phone": phone} if phone else {"email": email})}
        url = f"{(_env('SMALLCASE_API_URL') or API_URL).rstrip('/')}/gateway/{gateway_name()}/transaction"
        try:
            r = self.http.post(url, timeout=TIMEOUT, json={"intent": "MF_HOLDINGS_IMPORT", "assetConfig": config},
                               headers={"x-gateway-secret": _env("SMALLCASE_API_SECRET"),
                                        "x-gateway-authtoken": guest_token()})
        except requests.RequestException as e:
            raise MFCError(f"create transaction: {e}") from e
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400 or not body.get("success"):
            # Don't log the request: it has the PAN.
            raise MFCError(f"create transaction failed ({r.status_code}): {body.get('errors') or r.text[:200]}")
        return body["data"]


# ── Webhook payload → holdings ──────────────────────────────────────────────

def _num(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else None
    except ValueError:
        return None


def _day(v) -> Optional[str]:
    """ISO date. smallcase sends midnight IST as UTC ("2020-08-11T18:30:00.000Z" is 12 Aug) or "12-DEC-2022"."""
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return (datetime.strptime(s, fmt) + IST).date().isoformat()
        except ValueError:
            pass
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.title() if "-" in s[:3] else s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _txn(t: dict) -> Optional[list]:
    """[iso date, type, amount, units] as parse_cas produces them: money in and units bought are positive."""
    a = t.get("analytics") or {}
    if str(a.get("transactionStatus") or "").upper() == "VOID" or \
            str(a.get("transactionType") or "").upper() == "REJECTED DEPOSIT":
        return None
    day, units, amount = _day(t.get("transactionDate")), _num(t.get("trxnUnits")), _num(t.get("trxnAmount"))
    if not day or not units:
        return None                                   # address changes, nominee updates, reversed purchases
    desc = str(a.get("transactionDescription") or "").upper()
    if desc == "DIVIDEND":
        kind = "DIVIDEND_REINVEST"
    else:
        kind = KINDS.get(desc) or ("PURCHASE" if units > 0 else "REDEMPTION")
    sign = -1 if kind in ("REDEMPTION", "SWITCH_OUT") else 1
    return [day, kind, sign * abs(amount) if amount is not None else None, sign * abs(units)]


def parse_payload(payload: dict) -> Tuple[List[dict], List[str]]:
    """Holdings (services/holdings.py format, source "pan") from an MF holdings webhook, and warnings."""
    summary = payload.get("summary") or {}
    by_isin = defaultdict(list)
    for t in payload.get("transactions") or []:
        if isinstance(t, dict) and t.get("isin"):
            by_isin[t["isin"]].append(t)
    schemes = scheme_map.schemes()
    holdings: List[dict] = []
    warnings: List[str] = []
    for s in summary.get("schemeDetails") or []:
        folios = [f for f in s.get("folios") or [] if isinstance(f, dict)]
        units = _num(s.get("units"))
        if units is None:
            units = sum(_num(f.get("units")) or 0.0 for f in folios)
        if units < MIN_UNITS:
            continue
        isin = s.get("isin")
        code = resolve_code(None, isin)
        known = schemes.get(code or "")
        mine = sorted((x for x in (_txn(t) for t in by_isin.get(isin, [])) if x), key=lambda x: x[0])
        explained = sum(x[3] for x in mine)
        invested = _num((s.get("analytics") or {}).get("investedValue"))
        nav_dates = [d for d in (_day(f.get("lastNavDate")) for f in folios) if d]
        holdings.append({
            "id": new_id(),
            "source": "pan",
            "code": code,
            "isin": isin,
            "name": known["name"] if known else (s.get("scheme") or "Unknown scheme"),
            "amc": known["amc"] if known else s.get("amc"),
            "units": round(units, 4),
            "cost": round(invested, 2) if invested is not None else None,
            "cas_nav": _num(s.get("nav")),
            "cas_nav_date": max(nav_dates) if nav_dates else None,
            # Units bought before the transactions we were sent: their cost and dates are unknown.
            "open_units": round(max(units - explained, 0.0), 4) if mine else 0.0,
            "txns": mine,
        })
        if not code:
            warnings.append(f"We couldn't match {s.get('scheme') or isin} to a fund we track, so it isn't rated.")
    return holdings, warnings


def statement_range(payload: dict) -> dict:
    return {"from": _day(payload.get("fromDate")), "to": _day(payload.get("toDate"))
            or _day(payload.get("snapshotDate")), "type": "MF Central"}


def failure(payload: dict) -> Optional[str]:
    """The investor-facing message when the webhook reports an error, else None."""
    err = payload.get("error")
    if not (isinstance(err, dict) and err.get("value")):
        return None
    return ERRORS.get(str(err.get("message")), "MF Central couldn't share your holdings. Please try again, or "
                                                 "upload your statement instead.")
