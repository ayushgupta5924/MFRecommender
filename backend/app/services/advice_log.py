"""Record of the advice we give, kept for SEBI's retention period.

Every plan and every portfolio review shown is stored with its inputs (the risk
profile and answers, or the holdings) and the advice itself (funds, amounts,
ratings, actions and warnings), so it can be produced later for the client, an
auditor or SEBI. Repeat views that show nothing new aren't stored twice.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.tables import AdviceRecord, User, utcnow

logger = logging.getLogger(__name__)

RETENTION_YEARS = int(os.getenv("ADVICE_RETENTION_YEARS", "5"))


def _fingerprint(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _retain_until(now: datetime) -> datetime:
    return now + timedelta(days=round(365.25 * RETENTION_YEARS))


def plan_advice(result: dict) -> dict:
    """The parts of a plan a client acts on, without the long evidence lists."""
    keys = ("portfolio_name", "plan_note", "monthly_investment", "lump_sum", "horizon_years", "target_amount",
            "monthly_sip_required", "goal_status", "asset_mix", "mix_reasons", "risk_profile", "projections",
            "expected_return", "warnings", "methodology_version", "data_as_of")
    out = {k: result.get(k) for k in keys}
    out["funds"] = [{k: f.get(k) for k in ("scheme_code", "scheme_name", "category", "monthly_sip_amount",
                                           "lump_sum_amount", "allocation_percentage", "rank", "rank_of", "reason")}
                    for f in result.get("funds", [])]
    return out


def review_advice(review: dict) -> dict:
    return {
        "summary": review.get("summary"),
        "allocation": review.get("allocation"),
        "target": review.get("target"),
        "holdings": [{
            "code": h["code"], "name": h["name"], "plan": h["plan"], "option": h["option"], "value": h["value"],
            "rating": h["rating"].get("status"), "rank": h["rating"].get("rank"), "rank_of": h["rating"].get("rank_of"),
            "action": h["action"], "alternatives": [a["name"] for a in h.get("alternatives", [])],
        } for h in review.get("holdings", [])],
        "insights": [{"level": i["level"], "title": i["title"], "text": i["text"]} for i in review.get("insights", [])],
    }


def _last(db: Session, user_id: int, kind: str) -> Optional[AdviceRecord]:
    return db.scalars(select(AdviceRecord).where(AdviceRecord.user_id == user_id, AdviceRecord.kind == kind)
                      .order_by(AdviceRecord.created_at.desc(), AdviceRecord.id.desc()).limit(1)).first()


def _save(db: Session, user: Optional[User], kind: str, inputs: dict, advice: dict,
          fingerprint: str, methodology: Optional[str], data_as_of: Optional[str]) -> bool:
    if user is not None:
        last = _last(db, user.id, kind)
        if last is not None and last.fingerprint == fingerprint:
            return False
    now = utcnow()
    db.add(AdviceRecord(
        user_id=user.id if user else None,
        client_name=user.full_name if user else None,
        client_email=user.email if user else None,
        kind=kind, inputs=inputs, advice=advice, fingerprint=fingerprint,
        methodology_version=methodology, data_as_of=data_as_of,
        created_at=now, retain_until=_retain_until(now),
    ))
    db.commit()
    return True


def record_plan(db: Session, user: Optional[User], profile: dict, result: dict) -> bool:
    advice = plan_advice(result)
    return _save(db, user, "plan", profile, advice, _fingerprint(profile, advice),
                 result.get("methodology_version"), result.get("data_as_of"))


def record_review(db: Session, user: Optional[User], holdings: list, review: dict) -> bool:
    inputs = {"holdings": [{"code": h.get("code"), "name": h.get("name"), "units": h.get("units"),
                            "cost": h.get("cost"), "source": h.get("source")} for h in holdings]}
    advice = review_advice(review)
    # Values move with every NAV; only a change in what we tell the client is a new record.
    what_we_said = ([(h["code"], h["rating"], h["action"]["type"]) for h in advice["holdings"]],
                    [i["title"] for i in advice["insights"]])
    return _save(db, user, "review", inputs, advice, _fingerprint(inputs, what_we_said),
                 None, review.get("rankings_date"))


def safely(fn, *args) -> None:
    """Advice is still shown if recording it fails, but the failure is logged loudly for follow-up."""
    try:
        fn(*args)
    except Exception:
        logger.exception("ADVICE RECORD NOT SAVED (%s)", getattr(fn, "__name__", fn))
        try:
            args[0].rollback()
        except Exception:
            pass


def purge_expired(db: Session) -> int:
    result = db.execute(delete(AdviceRecord).where(AdviceRecord.retain_until < utcnow()))
    db.commit()
    return result.rowcount or 0
