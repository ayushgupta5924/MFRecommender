"""Database tables.

We keep only what the features need: no PAN, address, phone or statement PDF is
ever stored. Holdings are kept so a review can be re-run against fresh data.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    # Naive UTC so SQLite and Postgres compare the same way.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Email when a held fund's rating changes. Off until the investor opts in; one click in any alert turns it off.
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Consent to the privacy notice at sign-up: when, and which version of the notice.
    consented_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consent_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    purpose: Mapped[str] = mapped_column(String(10))            # "signup" | "login"
    code_hash: Mapped[str] = mapped_column(String(64))
    full_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)   # signup only
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuthSession(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Portfolio(Base):
    """One imported portfolio per user. Holdings are a JSON list (see services/holdings.py)."""
    __tablename__ = "portfolios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    holdings: Mapped[list] = mapped_column(JSON, default=list)
    statement_from: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    statement_to: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    statement_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)   # DETAILED | SUMMARY
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    # Ratings ({scheme code: status}) as of the last alert, so the next one reports only what changed.
    alert_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    alerted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Consent to storing holdings and transactions, given with the latest import.
    consented_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consent_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class SavedPlan(Base):
    __tablename__ = "saved_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    profile: Mapped[dict] = mapped_column(JSON)      # the questionnaire answers sent to /api/portfolio
    result: Mapped[dict] = mapped_column(JSON)       # the plan returned at the time
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AARequest(Base):
    """A one-time Account Aggregator consent we asked for (services/aa.py).

    Only ids and progress: no mobile number, and the fetched holdings go to the guest's browser or the
    account's portfolio, never here. A guest proves the request is theirs with a key only their browser has.
    """
    __tablename__ = "aa_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(12))           # consent | data | done | failed
    data_from: Mapped[str] = mapped_column(String(30))
    data_to: Mapped[str] = mapped_column(String(30))
    error: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PanFetch(Base):
    """A fetch of holdings by PAN from MF Central through smallcase Gateway (services/mfc.py).

    No PAN, phone or email. smallcase's webhook leaves the parsed fund-level holdings here only until the
    investor's browser picks them up (then they're cleared), or for a day at most. A guest proves the fetch is
    theirs with a key only their browser has.
    """
    __tablename__ = "pan_fetches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(12))           # waiting | ready | done | failed
    holdings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    statement: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    warnings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AdviceRecord(Base):
    """Every plan and portfolio review we show, kept for the SEBI retention period.

    SEBI requires investment advisers to keep records of risk profiling, suitability
    and the advice given, including interactions with prospective clients before
    onboarding. Records outlive account deletion until retain_until; the client's name
    and email are copied in so they stay identifiable after the account is gone.
    Plans for visitors who aren't logged in are kept without any identity.
    """
    __tablename__ = "advice_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)   # no FK: survives deletion
    client_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    client_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(10))                 # "plan" | "review"
    inputs: Mapped[dict] = mapped_column(JSON)
    advice: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64))
    methodology_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    data_as_of: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    retain_until: Mapped[datetime] = mapped_column(DateTime, index=True)
