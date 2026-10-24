"""Email one-time-code authentication and cookie sessions.

Codes are 6 digits, stored only as an HMAC, valid for 10 minutes and for 5
guesses. Sessions are random tokens stored hashed; the browser holds the token
in an HttpOnly cookie, so page scripts can never read it.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.tables import AuthSession, OtpCode, User, utcnow

logger = logging.getLogger(__name__)

OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 30
MAX_CODES_PER_EMAIL_PER_HOUR = 5
MAX_CODES_PER_IP_PER_HOUR = 20
SESSION_DAYS = 30
COOKIE_NAME = "mfa_session"

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")

_SECRET = os.getenv("AUTH_SECRET")
if not _SECRET:
    # Fine locally; in production codes would stop verifying after every restart.
    logger.warning("AUTH_SECRET is not set; using a random one for this process.")
    _SECRET = secrets.token_hex(32)


def auth_error(status: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status, detail=detail)


def normalise_email(email: str) -> str:
    email = (email or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise auth_error(422, "Enter a valid email address.")
    return email


def _hash(value: str) -> str:
    return hmac.new(_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


# ── Rate limiting by IP (in memory; per-email limits live in the database) ──

_ip_hits: dict = defaultdict(deque)
_ip_lock = threading.Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def _check_ip(ip: str) -> None:
    now = time.time()
    with _ip_lock:
        hits = _ip_hits[ip]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= MAX_CODES_PER_IP_PER_HOUR:
            raise auth_error(429, "Too many codes requested from this network. Try again in an hour.")
        hits.append(now)


# ── One-time codes ──────────────────────────────────────────────────────────

def issue_code(db: Session, email: str, purpose: str, ip: str, full_name: Optional[str] = None) -> str:
    """Create a code, enforcing the resend cooldown and hourly limits. Returns the plain code to send."""
    now = utcnow()
    last = db.scalars(select(OtpCode).where(OtpCode.email == email)
                      .order_by(OtpCode.created_at.desc()).limit(1)).first()
    if last and (now - last.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
        wait = RESEND_COOLDOWN_SECONDS - int((now - last.created_at).total_seconds())
        raise auth_error(429, f"Please wait {wait} seconds before requesting another code.")
    recent = db.scalar(select(func.count()).select_from(OtpCode)
                       .where(OtpCode.email == email, OtpCode.created_at > now - timedelta(hours=1)))
    if recent >= MAX_CODES_PER_EMAIL_PER_HOUR:
        raise auth_error(429, "Too many codes requested for this email. Try again in an hour.")
    _check_ip(ip)

    # Old rows are only needed for the hourly limit; a new code also retires any earlier one.
    db.execute(delete(OtpCode).where(OtpCode.email == email, OtpCode.created_at <= now - timedelta(hours=1)))
    for old in db.scalars(select(OtpCode).where(OtpCode.email == email, OtpCode.used_at.is_(None))):
        old.expires_at = now
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(OtpCode(email=email, purpose=purpose, code_hash=_hash(f"{email}:{code}"), full_name=full_name,
                   created_at=now, expires_at=now + timedelta(minutes=OTP_MINUTES)))
    db.commit()
    return code


def verify_code(db: Session, email: str, purpose: str, code: str) -> OtpCode:
    now = utcnow()
    otp = db.scalars(select(OtpCode).where(OtpCode.email == email, OtpCode.purpose == purpose,
                                           OtpCode.used_at.is_(None))
                     .order_by(OtpCode.created_at.desc()).limit(1)).first()
    if otp is None or otp.expires_at <= now:
        raise auth_error(400, "This code has expired. Request a new one.")
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        raise auth_error(400, "Too many wrong attempts. Request a new code.")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, _hash(f"{email}:{(code or '').strip()}")):
        db.commit()
        left = OTP_MAX_ATTEMPTS - otp.attempts
        raise auth_error(400, f"That code is incorrect. {left} attempt{'s' if left != 1 else ''} left."
                         if left else "Too many wrong attempts. Request a new code.")
    otp.used_at = now
    db.commit()
    return otp


# ── Sessions ────────────────────────────────────────────────────────────────

def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(AuthSession(user_id=user.id, token_hash=_hash(token), created_at=now,
                       expires_at=now + timedelta(days=SESSION_DAYS)))
    user.last_login_at = now
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at < now))
    db.commit()
    return token


def end_session(db: Session, token: Optional[str]) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash(token)))
        db.commit()


def cookie_settings() -> dict:
    # The local dev server is plain http, where browsers drop Secure cookies; set COOKIE_SECURE=0 there.
    secure = os.getenv("COOKIE_SECURE", "1") != "0"
    return {"key": COOKIE_NAME, "httponly": True, "secure": secure, "samesite": "lax", "path": "/"}


def optional_user(db: Session = Depends(get_db),
                  token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME)) -> Optional[User]:
    if not token:
        return None
    session = db.scalars(select(AuthSession).where(AuthSession.token_hash == _hash(token))).first()
    if session is None or session.expires_at <= utcnow():
        return None
    return db.get(User, session.user_id)


def current_user(user: Optional[User] = Depends(optional_user)) -> User:
    if user is None:
        raise auth_error(401, "Please log in to continue.")
    return user
