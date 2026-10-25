"""Fetch mutual fund holdings with the investor's consent through an Account Aggregator (services/aa.py).

1. POST /aa/consent: we ask Setu for a one-time consent and send the investor to the AA's screens to approve.
2. They come back to /review, which calls POST /aa/status every few seconds. Each call moves the request on:
   consent approved -> data session started -> data in -> holdings reviewed, consent revoked.

Setu's webhooks aren't authenticated, so we don't rely on them: the status call asks Setu directly.
"""
import hashlib
import hmac
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.tables import AARequest, Portfolio, User, utcnow
from app.routes.review import (
    CONSENT_MESSAGE, GUEST_CONSENT_MESSAGE, _guest_review, _portfolio, _record_consent, _review,
)
from app.services import aa
from app.services.auth import optional_user
from app.services.email import SITE_URL

logger = logging.getLogger(__name__)
router = APIRouter()
client = aa.SetuClient()

UNAVAILABLE = "Fetching by mobile number isn't available yet. Upload your statement or add funds by hand."
UNREACHABLE = "We couldn't reach the account aggregator. Try again in a minute, or upload your statement instead."
CONSENT_FAILED = {
    "REJECTED": "The consent was declined, so nothing was fetched.",
    "REVOKED": "The consent was withdrawn before we could fetch anything.",
    "EXPIRED": "The consent expired before it was approved. Please start again.",
    "PAUSED": "The consent is paused in your account aggregator app, so nothing was fetched.",
}


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _enabled() -> None:
    if not aa.aa_enabled():
        raise HTTPException(404, UNAVAILABLE)


class ConsentIn(BaseModel):
    mobile: str = Field(..., pattern=r"^[6-9]\d{9}$")
    consent: bool = False
    alerts: Optional[bool] = None


@router.post("/aa/consent")
def start(body: ConsentIn, db: Session = Depends(get_db), user: Optional[User] = Depends(optional_user)):
    _enabled()
    if not body.consent:
        raise HTTPException(422, CONSENT_MESSAGE if user else GUEST_CONSENT_MESSAGE)
    rng = aa.data_range()
    try:
        c = client.create_consent(body.mobile, f"{SITE_URL}/review?aa=1", rng)
    except aa.AAError:
        logger.exception("AA consent request failed")
        raise HTTPException(502, UNREACHABLE)
    key = None if user else secrets.token_urlsafe(24)
    db.add(AARequest(consent_id=c["id"], user_id=user.id if user else None,
                     guest_key_hash=_hash(key) if key else None, status="consent",
                     data_from=rng["from"], data_to=rng["to"]))
    if user and body.alerts is not None:
        user.alerts_enabled = body.alerts
    db.commit()
    # The mobile number isn't kept: the AA has it, and we don't need it again.
    return {"id": c["id"], "url": c["url"], "key": key}


class StatusIn(BaseModel):
    id: str = Field(..., max_length=64)
    key: Optional[str] = Field(None, max_length=64)


def _request_for(body: StatusIn, db: Session, user: Optional[User]) -> AARequest:
    row = db.scalars(select(AARequest).where(AARequest.consent_id == body.id)).first()
    mine = row and ((row.user_id is not None and user is not None and row.user_id == user.id)
                    or (row.guest_key_hash and body.key and hmac.compare_digest(row.guest_key_hash, _hash(body.key))))
    if not row or not mine:
        raise HTTPException(404, "We couldn't find that request. Please start again.")
    return row


def _fail(db: Session, row: AARequest, message: str) -> dict:
    row.status, row.error = "failed", message
    db.commit()
    return {"status": "failed", "message": message}


def _revoke(consent_id: str) -> None:
    try:
        client.revoke(consent_id)
    except aa.AAError:
        # It's one-time and expires within a day anyway; don't fail the import over it.
        logger.warning("Couldn't revoke AA consent %s", consent_id)


@router.post("/aa/status")
def status(body: StatusIn, db: Session = Depends(get_db), user: Optional[User] = Depends(optional_user)):
    _enabled()
    row = _request_for(body, db, user)
    if row.status == "failed":
        return {"status": "failed", "message": row.error}
    if row.status == "done":
        return {"status": "done"}
    rng = {"from": row.data_from, "to": row.data_to}
    try:
        if row.status == "consent":
            state = str(client.consent(row.consent_id).get("status", "")).upper()
            if state in CONSENT_FAILED:
                return _fail(db, row, CONSENT_FAILED[state])
            if state != "ACTIVE":
                return {"status": "waiting", "stage": "consent"}
            session = client.create_session(row.consent_id, rng)
            row.session_id, row.status = session["id"], "data"
            db.commit()
        session = client.session(row.session_id or "")   # set whenever status is "data"
    except aa.AAError:
        logger.exception("AA status check failed")
        return {"status": "waiting", "stage": row.status, "message": UNREACHABLE}

    state = str(session.get("status", "")).upper()
    if state in ("FAILED", "EXPIRED"):
        _revoke(row.consent_id)
        return _fail(db, row, "Your fund registrars didn't send the data in time. Please try again.")
    if not aa.session_settled(session):
        return {"status": "waiting", "stage": "data"}

    holdings, warnings = aa.parse_session(session)
    _revoke(row.consent_id)
    if not holdings:
        return _fail(db, row, "We didn't find any mutual funds with units for this mobile number. Upload your "
                              "statement or add funds by hand instead.")
    statement = {"from": row.data_from[:10], "to": row.data_to[:10], "type": "AA"}
    row.status = "done"
    if user:
        p = _portfolio(db, user) or Portfolio(user_id=user.id, holdings=[])
        manual = [h for h in (p.holdings or []) if h["source"] == "manual"]
        # Like a new statement: replaces earlier imports, keeps funds added by hand.
        p.holdings = holdings + manual
        p.statement_from, p.statement_to, p.statement_type = statement["from"], statement["to"], "AA"
        p.updated_at = utcnow()
        _record_consent(p, user, None)
        db.add(p)
        db.commit()
        return {"status": "done", "review": {**_review(db, user, p), "fetch_warnings": warnings}}
    db.commit()
    out = _guest_review(db, holdings)
    return {"status": "done", **out, "statement": statement, "fetch_warnings": warnings}
