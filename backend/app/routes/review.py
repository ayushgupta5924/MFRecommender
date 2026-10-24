"""Portfolio review and saved plans. Everything here needs a logged-in user, except the guest review."""
import logging
from typing import Annotated, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.tables import Portfolio, SavedPlan, User, utcnow
from app.services import advice_log
from app.services import holdings as hold
from app.services import nav as navs
from app.services.auth import PRIVACY_VERSION, current_user
from app.services.ranking import tidy_name
from app.services.rankings_store import scheme_map
from app.services.review import Reviewer

logger = logging.getLogger(__name__)
router = APIRouter()
reviewer = Reviewer()
MAX_SAVED_PLANS = 20
CONSENT_MESSAGE = "Please agree to us storing your fund holdings to review them (see the Privacy Notice)."


def _record_consent(p: Portfolio, user: User, alerts: Optional[bool]) -> None:
    p.consented_at, p.consent_version = utcnow(), PRIVACY_VERSION
    if alerts is not None:
        user.alerts_enabled = alerts


def _portfolio(db: Session, user: User) -> Optional[Portfolio]:
    return db.scalars(select(Portfolio).where(Portfolio.user_id == user.id)).first()


def _target(db: Session, user: User) -> Optional[dict]:
    plan = db.scalars(select(SavedPlan).where(SavedPlan.user_id == user.id)
                      .order_by(SavedPlan.created_at.desc()).limit(1)).first()
    if not plan:
        return None
    r = plan.result
    return {"id": plan.id, "name": plan.name, "asset_mix": r.get("asset_mix"),
            "risk_label": (r.get("risk_profile") or {}).get("label"), "saved_at": plan.created_at.isoformat()}


def _review(db: Session, user: User, p: Portfolio) -> dict:
    result = reviewer.review(p.holdings, _target(db, user))
    result["statement"] = {"from": p.statement_from, "to": p.statement_to, "type": p.statement_type,
                           "updated_at": p.updated_at.isoformat()}
    advice_log.safely(advice_log.record_review, db, user, p.holdings, result)
    return result


# ── Review ──────────────────────────────────────────────────────────────────

@router.get("/review")
def get_review(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _portfolio(db, user)
    if not p or not p.holdings:
        return {"empty": True, "target": _target(db, user)}
    return _review(db, user, p)


@router.post("/review/upload")
async def upload_statement(file: UploadFile = File(...), password: str = Form(""), consent: bool = Form(False),
                           alerts: bool = Form(False), user: User = Depends(current_user),
                           db: Session = Depends(get_db)):
    if not consent:
        raise HTTPException(422, CONSENT_MESSAGE)
    pdf = await file.read(hold.MAX_PDF_BYTES + 1)
    try:
        parsed = hold.parse_cas(pdf, password)
    except hold.StatementError as e:
        raise HTTPException(422, str(e))
    except Exception:
        logger.exception("CAS parsing failed")
        raise HTTPException(422, "We couldn't read this statement. Make sure it's a CAMS or KFintech CAS PDF.")
    finally:
        del pdf

    p = _portfolio(db, user) or Portfolio(user_id=user.id, holdings=[])
    manual = [h for h in (p.holdings or []) if h["source"] == "manual"]
    # A new statement replaces the previous one; funds added by hand stay.
    p.holdings = parsed["holdings"] + manual
    p.statement_from, p.statement_to = parsed["statement_from"], parsed["statement_to"]
    p.statement_type = parsed["statement_type"]
    p.updated_at = utcnow()
    _record_consent(p, user, alerts)
    db.add(p)
    db.commit()
    result = _review(db, user, p)
    result["parse_warnings"] = parsed["warnings"]
    return result


class ManualHolding(BaseModel):
    code: str
    consent: bool = False
    alerts: Optional[bool] = None
    units: Optional[float] = Field(None, gt=0, le=1e9)
    value: Optional[float] = Field(None, gt=0, le=1e11)        # current value in rupees, if units unknown
    invested: Optional[float] = Field(None, ge=0, le=1e11)


@router.post("/review/holdings")
def add_holding(body: ManualHolding, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(422, CONSENT_MESSAGE)
    holding = _manual(body.code, body.units, body.value, body.invested)
    p = _portfolio(db, user) or Portfolio(user_id=user.id, holdings=[])
    p.holdings = (p.holdings or []) + [holding]
    p.updated_at = utcnow()
    _record_consent(p, user, body.alerts)
    db.add(p)
    db.commit()
    return _review(db, user, p)


@router.delete("/review/holdings/{holding_id}")
def remove_holding(holding_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _portfolio(db, user)
    if not p:
        raise HTTPException(404, "No portfolio found.")
    kept = [h for h in p.holdings if h["id"] != holding_id]
    if len(kept) == len(p.holdings):
        raise HTTPException(404, "That holding no longer exists.")
    p.holdings = kept
    p.updated_at = utcnow()
    db.commit()
    return _review(db, user, p) if kept else {"empty": True, "target": _target(db, user)}


@router.delete("/review")
def delete_portfolio(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _portfolio(db, user)
    if p:
        db.delete(p)
        db.commit()
    return {"deleted": True}


# ── Review without an account ───────────────────────────────────────────────
# Nothing is stored apart from the record of advice SEBI requires: the visitor's browser keeps the holdings
# and sends them back with each change.

MAX_GUEST_HOLDINGS = 150
GUEST_CONSENT_MESSAGE = ("Please agree to us reading your fund holdings to review them, and keeping a record of the "
                         "review as SEBI requires (see the Privacy Notice).")


class GuestHolding(BaseModel):
    id: str = Field(..., min_length=1, max_length=24)
    source: Literal["cas", "manual"]
    code: Optional[str] = Field(None, max_length=12)
    isin: Optional[str] = Field(None, max_length=12)
    name: str = Field(..., max_length=200)
    amc: Optional[str] = Field(None, max_length=120)
    units: float = Field(..., gt=0, le=1e10)
    cost: Optional[float] = Field(None, ge=0, le=1e12)
    cas_nav: Optional[float] = Field(None, gt=0, le=1e7)
    cas_nav_date: Optional[str] = Field(None, max_length=10)
    open_units: float = Field(0.0, ge=0, le=1e10)
    # [iso date, type, amount, units], as parse_cas produces them.
    txns: List[Tuple[Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}")], Annotated[str, Field(max_length=40)],
                     Optional[float], Optional[float]]] = Field(default_factory=list, max_length=5000)


class GuestAdd(BaseModel):
    code: str
    units: Optional[float] = Field(None, gt=0, le=1e9)
    value: Optional[float] = Field(None, gt=0, le=1e11)
    invested: Optional[float] = Field(None, ge=0, le=1e11)


class GuestReview(BaseModel):
    consent: bool = False
    holdings: List[GuestHolding] = Field(default_factory=list, max_length=MAX_GUEST_HOLDINGS)
    add: Optional[GuestAdd] = None


def _manual(code: str, units: Optional[float], value: Optional[float], invested: Optional[float]) -> dict:
    if code not in scheme_map.schemes():
        raise HTTPException(404, "We couldn't find that fund.")
    if units is None:
        if value is None:
            raise HTTPException(422, "Enter the number of units or the current value.")
        last = navs.latest(navs.histories([code]).get(code, []))
        if not last:
            raise HTTPException(503, "We couldn't get this fund's latest NAV. Enter units instead.")
        units = value / last[0]
    return hold.manual_holding(code, units, invested)


def _guest_review(db: Session, holdings: List[dict]) -> dict:
    result = reviewer.review(holdings)
    advice_log.safely(advice_log.record_review, db, None, holdings, result)
    return {"review": result, "holdings": holdings}


@router.post("/review/guest/upload")
async def guest_upload(file: UploadFile = File(...), password: str = Form(""), consent: bool = Form(False),
                       db: Session = Depends(get_db)):
    if not consent:
        raise HTTPException(422, GUEST_CONSENT_MESSAGE)
    pdf = await file.read(hold.MAX_PDF_BYTES + 1)
    try:
        parsed = hold.parse_cas(pdf, password)
    except hold.StatementError as e:
        raise HTTPException(422, str(e))
    except Exception:
        logger.exception("CAS parsing failed")
        raise HTTPException(422, "We couldn't read this statement. Make sure it's a CAMS or KFintech CAS PDF.")
    finally:
        del pdf
    out = _guest_review(db, parsed["holdings"])
    out["statement"] = {"from": parsed["statement_from"], "to": parsed["statement_to"],
                        "type": parsed["statement_type"]}
    out["parse_warnings"] = parsed["warnings"]
    return out


@router.post("/review/guest")
def guest_review(body: GuestReview, db: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(422, GUEST_CONSENT_MESSAGE)
    holdings = [h.model_dump() for h in body.holdings]
    for h in holdings:
        h["txns"] = [list(t) for t in h["txns"]]
    if body.add:
        if len(holdings) >= MAX_GUEST_HOLDINGS:
            raise HTTPException(422, f"You can review up to {MAX_GUEST_HOLDINGS} funds at a time.")
        a = body.add
        holdings.append(_manual(a.code, a.units, a.value, a.invested))
    if not holdings:
        raise HTTPException(422, "Add at least one fund to review.")
    return _guest_review(db, holdings)


@router.get("/funds/search")
def search_funds(q: str = Query(..., min_length=2, max_length=80), limit: int = Query(15, ge=1, le=30)):
    """Any open-ended scheme by name, for adding holdings by hand."""
    words = q.lower().split()
    hits = []
    for code, s in scheme_map.schemes().items():
        text = f"{s['name']} {s['amc']}".lower()
        if all(w in text for w in words):
            hits.append((not s["direct"], not s["growth"], s["name"], code, s))
    hits.sort(key=lambda h: h[:3])
    return [{"code": code, "name": tidy_name(s["name"]).rstrip(". "), "amc": s["amc"],
             "plan": "Direct" if s["direct"] else "Regular", "option": "Growth" if s["growth"] else "IDCW",
             "category": s["category"]}
            for *_, code, s in hits[:limit]]


# ── Saved plans ─────────────────────────────────────────────────────────────

class PlanIn(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    profile: dict
    result: dict


def _plan_out(p: SavedPlan, full: bool = False) -> dict:
    r = p.result
    out = {"id": p.id, "name": p.name, "created_at": p.created_at.isoformat(),
           "goal": p.profile.get("goal"), "monthly_investment": r.get("monthly_investment"),
           "horizon_years": r.get("horizon_years"), "asset_mix": r.get("asset_mix"),
           "risk_label": (r.get("risk_profile") or {}).get("label")}
    if full:
        out.update(profile=p.profile, result=r)
    return out


@router.get("/plans")
def list_plans(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plans = db.scalars(select(SavedPlan).where(SavedPlan.user_id == user.id).order_by(SavedPlan.created_at.desc()))
    return [_plan_out(p) for p in plans]


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(SavedPlan, plan_id)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Plan not found.")
    return _plan_out(p, full=True)


@router.post("/plans")
def save_plan(body: PlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.scalars(select(SavedPlan).where(SavedPlan.user_id == user.id)).all()
    if len(existing) >= MAX_SAVED_PLANS:
        raise HTTPException(409, f"You can keep up to {MAX_SAVED_PLANS} plans. Delete one to save another.")
    name = (body.name or body.result.get("portfolio_name") or "My plan").strip()[:120]
    p = SavedPlan(user_id=user.id, name=name, profile=body.profile, result=body.result)
    db.add(p)
    db.commit()
    return _plan_out(p)


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(SavedPlan, plan_id)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Plan not found.")
    db.delete(p)
    db.commit()
    return {"deleted": True}
