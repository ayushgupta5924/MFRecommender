"""Read-only mutual fund holdings through India's Account Aggregator network (Setu's FIU APIs, v2).

The investor approves a one-time consent in the Account Aggregator's own screens. The AA asks for their PAN
there to find their folios, so we never see it. We ask only for holdings and transactions (no profile: name,
PAN, address), fetch once, turn the data into the same holdings the CAS import produces, and revoke the consent.

Switched on by SETU_AA_CLIENT_ID, SETU_AA_CLIENT_SECRET and SETU_AA_PRODUCT_INSTANCE_ID (from Setu's Bridge).
SETU_AA_BASE_URL defaults to Setu's sandbox; set it to https://fiu.setu.co for production.
"""
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

import requests

from app.services.holdings import MIN_UNITS, new_id, resolve_code
from app.services.rankings_store import scheme_map

logger = logging.getLogger(__name__)

SANDBOX_URL = "https://fiu-sandbox.setu.co"
TOKEN_URL = "https://orgservice-prod.setu.co/v1/users/login"
TIMEOUT = 20
HISTORY_YEARS = 10                  # transactions asked for: enough for XIRR and tax lots on most portfolios
# Consent terms. One fetch, then revoked. STORE because an account keeps the holdings for its reviews and alerts.
CONSENT_TERMS = {
    "consentDuration": {"unit": "DAY", "value": 1},
    "fetchType": "ONETIME",
    "consentMode": "STORE",
    "consentTypes": ["SUMMARY", "TRANSACTIONS"],
    "fiTypes": ["MUTUAL_FUNDS"],
    "purpose": {"code": "101", "refUri": "https://api.rebit.org.in/aa/purpose/101.xml",
                "text": "Wealth management service", "category": {"type": "string"}},
    "dataLife": {"unit": "YEAR", "value": 1},
    "frequency": {"unit": "HOUR", "value": 1},
}
# Account statuses that won't change any more within a data session.
SETTLED = {"READY", "DELIVERED", "TIMEOUT", "DENIED"}
HAS_DATA = {"READY", "DELIVERED"}


def _env(key: str) -> str:
    return os.getenv(key, "").strip()


def aa_enabled() -> bool:
    return all(_env(k) for k in ("SETU_AA_CLIENT_ID", "SETU_AA_CLIENT_SECRET", "SETU_AA_PRODUCT_INSTANCE_ID"))


class AAError(Exception):
    """Setu couldn't be reached or refused a request."""


def data_range(today: Optional[date] = None) -> dict:
    now = datetime.combine(today, datetime.min.time(), timezone.utc) if today else datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365 * HISTORY_YEARS)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    return {"from": start.strftime(fmt), "to": now.strftime(fmt)}


class SetuClient:
    def __init__(self, http: Optional[requests.Session] = None):
        self.http = http or requests.Session()
        self._token: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return (_env("SETU_AA_BASE_URL") or SANDBOX_URL).rstrip("/")

    def _login(self) -> str:
        r = self.http.post(_env("SETU_AA_TOKEN_URL") or TOKEN_URL, headers={"client": "bridge"}, timeout=TIMEOUT,
                           json={"clientID": _env("SETU_AA_CLIENT_ID"), "grant_type": "client_credentials",
                                 "secret": _env("SETU_AA_CLIENT_SECRET")})
        if r.status_code >= 400:
            raise AAError(f"Setu login failed ({r.status_code})")
        return r.json()["access_token"]

    def _call(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        # The token's lifetime isn't documented: keep it until Setu answers 401, then log in again once.
        for retry in (False, True):
            with self._lock:
                if not self._token:
                    self._token = self._login()
                token = self._token
            try:
                r = self.http.request(method, self.base_url + path, json=body, timeout=TIMEOUT, headers={
                    "Authorization": f"Bearer {token}", "x-product-instance-id": _env("SETU_AA_PRODUCT_INSTANCE_ID")})
            except requests.RequestException as e:
                raise AAError(f"{method} {path}: {e}") from e
            if r.status_code == 401 and not retry:
                with self._lock:
                    self._token = None
                continue
            if r.status_code >= 400:
                try:
                    err = r.json()
                    detail = err.get("errorMsg") or err.get("errorCode")
                except ValueError:
                    detail = r.text[:200]
                raise AAError(f"{method} {path} failed ({r.status_code}): {detail}")
            return r.json()
        raise AAError(f"{method} {path}: not authorised")

    def create_consent(self, mobile: str, redirect_url: str, rng: dict) -> dict:
        """{id, url, status}: send the investor to `url` to approve."""
        return self._call("POST", "/v2/consents", {
            **CONSENT_TERMS, "vua": mobile, "dataRange": rng, "redirectUrl": redirect_url,
            "context": [{"key": "purposeDescription", "value": "Review your mutual funds and use them in your plan"}],
        })

    def consent(self, consent_id: str) -> dict:
        return self._call("GET", f"/v2/consents/{consent_id}")

    def create_session(self, consent_id: str, rng: dict) -> dict:
        return self._call("POST", "/v2/sessions", {"consentId": consent_id, "dataRange": rng, "format": "json"})

    def session(self, session_id: str) -> dict:
        return self._call("GET", f"/v2/sessions/{session_id}")

    def revoke(self, consent_id: str) -> None:
        self._call("POST", f"/v2/consents/{consent_id}/revoke")


# ── Data session → holdings ─────────────────────────────────────────────────

def _list(v) -> list:
    """AA JSON gives a single object where there is one item and a list where there are several."""
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _num(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else None
    except ValueError:
        return None


def _account_status(a: dict) -> str:
    # Setu's spec, docs and webhooks spell this three ways.
    return str(a.get("FIstatus") or a.get("FIStatus") or a.get("status") or "").upper()


def session_settled(session: dict) -> bool:
    """Every account in the session has answered (data, timeout or denial), or the session is complete."""
    if str(session.get("status")).upper() == "COMPLETED":
        return True
    accounts = [a for f in session.get("fips") or [] for a in f.get("accounts") or []]
    return bool(accounts) and all(_account_status(a) in SETTLED for a in accounts)


def _txn(t: dict) -> Optional[list]:
    """[iso date, type, amount, units] as parse_cas produces them: money in and units bought are positive."""
    day = str(t.get("transactionDate") or t.get("navDate") or "")[:10]
    units, amount = _num(t.get("units")), _num(t.get("amount"))
    if len(day) != 10 or units is None:
        return None
    kind = str(t.get("type") or "").upper()
    if kind == "BUY":
        return [day, "PURCHASE", abs(amount) if amount is not None else None, abs(units)]
    if kind == "SELL":
        return [day, "REDEMPTION", -abs(amount) if amount is not None else None, -abs(units)]
    return [day, "OTHERS", amount, units]


def _same_scheme(t: dict, h: dict) -> bool:
    return any(t.get(k) and t.get(k) == h.get(k) for k in ("isin", "amfiCode", "schemeCode"))


def parse_session(session: dict) -> Tuple[List[dict], List[str]]:
    """Holdings (services/holdings.py format, source "aa") from a completed data session, and warnings."""
    holdings: List[dict] = []
    warnings: List[str] = []
    schemes = scheme_map.schemes()
    for fip in session.get("fips") or []:
        for acc in fip.get("accounts") or []:
            status = _account_status(acc)
            if status not in HAS_DATA:
                if status:
                    warnings.append(f"{fip.get('fipID') or 'A fund registrar'} didn't share an account ({status.lower()}).")
                continue
            data = acc.get("data") or {}
            account = data.get("account") or data          # Setu's sandbox mock has no "account" wrapper
            summary = account.get("summary") or {}
            rows = _list(((summary.get("investment") or {}).get("holdings") or {}).get("holding"))
            txns = [t for t in _list((account.get("transactions") or {}).get("transaction")) if isinstance(t, dict)]
            for h in rows:
                units = _num(h.get("closingUnits"))
                if units is None or units < MIN_UNITS:
                    continue
                code = resolve_code(h.get("amfiCode"), h.get("isin"))
                mine = [x for x in (_txn(t) for t in txns if _same_scheme(t, h)) if x]
                explained = sum(x[3] for x in mine)
                s = schemes.get(code or "")
                holdings.append({
                    "id": new_id(),
                    "source": "aa",
                    "code": code,
                    "isin": h.get("isin"),
                    "name": s["name"] if s else (h.get("isinDescription") or h.get("schemeCode") or "Unknown scheme"),
                    "amc": s["amc"] if s else h.get("amc"),
                    "units": round(units, 4),
                    "cost": None,
                    "cas_nav": _num(h.get("nav")),
                    "cas_nav_date": str(h.get("navDate") or "")[:10] or None,
                    # Units bought before the transactions we were sent: their cost and dates are unknown.
                    "open_units": round(max(units - explained, 0.0), 4) if mine else 0.0,
                    "txns": sorted(mine, key=lambda x: x[0]),
                })
    return holdings, warnings
