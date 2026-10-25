"""Fetch mutual fund holdings by PAN, read-only, from MF Central through smallcase Gateway (services/mfc.py).

1. POST /pan/start: we open a smallcase transaction pre-filled with the PAN and mobile/email, and hand the browser
   what it needs to show smallcase's window, where the investor enters MF Central's OTP.
2. smallcase posts the holdings to POST /pan/webhook (signed). We keep the fund-level part until it's picked up.
3. The browser calls POST /pan/status every few seconds; once the holdings are in, it gets the review (an account's
   portfolio is updated, a guest's holdings go back to their browser) and they're cleared from here.
"""
import hashlib
import hmac
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.tables import PanFetch, Portfolio, User, utcnow
from app.routes.review import (
    CONSENT_MESSAGE, GUEST_CONSENT_MESSAGE, _guest_review, _portfolio, _record_consent, _review,
)
from app.services import mfc
from app.services.auth import optional_user

logger = logging.getLogger(__name__)
router = APIRouter()
client = mfc.GatewayClient()

UNAVAILABLE = "Fetching by PAN isn't available yet. Upload your statement or add funds by hand."
UNREACHABLE = "We couldn't reach MF Central just now. Try again in a minute, or upload your statement instead."
NOTHING_FOUND = ("We didn't find any mutual funds with units for this PAN. Upload your statement or add funds by "
                 "hand instead.")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _enabled() -> None:
    if not mfc.mfc_enabled():
        raise HTTPException(404, UNAVAILABLE)


class StartIn(BaseModel):
    pan: str = Field(..., pattern=r"^[A-Za-z]{5}\d{4}[A-Za-z]$")
    mobile: Optional[str] = Field(None, pattern=r"^[6-9]\d{9}$")
    email: Optional[str] = Field(None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    consent: bool = False
    alerts: Optional[bool] = None

    @model_validator(mode="after")
    def _contact(self):
        if not (self.mobile or self.email):
            raise ValueError("Enter the mobile number or email registered with your funds.")
        return self


@router.post("/pan/start")
def start(body: StartIn, db: Session = Depends(get_db), user: Optional[User] = Depends(optional_user)):
    _enabled()
    if not body.consent:
        raise HTTPException(422, CONSENT_MESSAGE if user else GUEST_CONSENT_MESSAGE)
    try:
        txn = client.create_transaction(body.pan.upper(), body.mobile, None if body.mobile else body.email)
    except mfc.MFCError:
        logger.exception("smallcase transaction failed")
        raise HTTPException(502, UNREACHABLE)
    key = None if user else secrets.token_urlsafe(24)
    db.add(PanFetch(transaction_id=txn["transactionId"], user_id=user.id if user else None,
                    guest_key_hash=_hash(key) if key else None, status="waiting"))
    if user and body.alerts is not None:
        user.alerts_enabled = body.alerts
    db.commit()
    # The PAN, mobile and email aren't kept: smallcase and MF Central have them, and we don't need them again.
    return {"id": txn["transactionId"], "key": key, "gateway": mfc.gateway_name(), "token": mfc.guest_token(),
            "sdk": mfc.SDK_URL}


@router.post("/pan/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    _enabled()
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Expected JSON")
    if not isinstance(payload, dict) or not mfc.checksum_ok(payload):
        raise HTTPException(401, "Bad checksum")
    row = db.scalars(select(PanFetch).where(PanFetch.transaction_id == str(payload.get("transactionId")))).first()
    if not row or row.status not in ("waiting", "failed"):
        return {"ok": True}                    # not ours, expired, or already delivered
    message = mfc.failure(payload)
    if message:
        row.status, row.error = "failed", message
    else:
        holdings, warnings = mfc.parse_payload(payload)
        if holdings:
            row.status, row.holdings, row.warnings = "ready", holdings, warnings
            row.statement, row.error = mfc.statement_range(payload), None
        else:
            row.status, row.error = "failed", NOTHING_FOUND
    db.commit()
    return {"ok": True}


class StatusIn(BaseModel):
    id: str = Field(..., max_length=64)
    key: Optional[str] = Field(None, max_length=64)


def _fetch_for(body: StatusIn, db: Session, user: Optional[User]) -> PanFetch:
    row = db.scalars(select(PanFetch).where(PanFetch.transaction_id == body.id)).first()
    mine = row and ((row.user_id is not None and user is not None and row.user_id == user.id)
                    or (row.guest_key_hash and body.key and hmac.compare_digest(row.guest_key_hash, _hash(body.key))))
    if not row or not mine:
        raise HTTPException(404, "We couldn't find that request. Please start again.")
    return row


@router.post("/pan/status")
def status(body: StatusIn, db: Session = Depends(get_db), user: Optional[User] = Depends(optional_user)):
    _enabled()
    row = _fetch_for(body, db, user)
    if row.status in ("waiting", "done"):
        return {"status": row.status}
    if row.status == "failed":
        return {"status": "failed", "message": row.error}

    holdings, statement, warnings = row.holdings or [], row.statement or {}, row.warnings or []
    # Handed over once, then gone from here.
    row.status, row.holdings, row.statement, row.warnings = "done", None, None, None
    if user:
        p = _portfolio(db, user) or Portfolio(user_id=user.id, holdings=[])
        manual = [h for h in (p.holdings or []) if h["source"] == "manual"]
        # Like a new statement: replaces earlier imports, keeps funds added by hand.
        p.holdings = holdings + manual
        p.statement_from, p.statement_to, p.statement_type = statement.get("from"), statement.get("to"), statement.get("type")
        p.updated_at = utcnow()
        _record_consent(p, user, None)
        db.add(p)
        db.commit()
        return {"status": "done", "review": {**_review(db, user, p), "fetch_warnings": warnings}}
    db.commit()
    out = _guest_review(db, holdings)
    return {"status": "done", **out, "statement": statement, "fetch_warnings": warnings}
