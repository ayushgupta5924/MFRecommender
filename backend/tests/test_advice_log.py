"""Advice records: what is kept, when duplicates are skipped, and that deletion keeps them for the retention period."""
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal, cleanup
from app.db.tables import AdviceRecord, User, utcnow
from app.services import advice_log
from app.services import nav as navs
from main import app
from tests.test_review import histories, logged_in_client

PROFILE = {"life_stage": "peak_earning", "goal": "wealth_creation", "risk_tolerance": "high",
           "capacity_score": 70, "willingness_score": 80, "monthly_budget": 20000, "horizon_years": 12}


def records(**where):
    with SessionLocal() as db:
        q = select(AdviceRecord)
        for k, v in where.items():
            q = q.where(getattr(AdviceRecord, k) == v)
        return db.scalars(q.order_by(AdviceRecord.id)).all()


def test_plans_for_visitors_are_kept_without_identity():
    before = len(records(user_id=None))
    r = TestClient(app).post("/api/portfolio", json={**PROFILE, "monthly_budget": 12345})
    assert r.status_code == 200
    rec = records(user_id=None)[-1]
    assert len(records(user_id=None)) == before + 1
    assert rec.client_email is None and rec.kind == "plan"
    assert rec.inputs["monthly_budget"] == 12345 and rec.inputs["capacity_score"] == 70
    assert rec.advice["funds"] and rec.advice["funds"][0]["reason"]
    assert rec.retain_until - rec.created_at >= timedelta(days=365 * 5)


def test_client_plans_are_kept_once_per_change(monkeypatch):
    client = logged_in_client(monkeypatch, "advice@example.com")
    client.post("/api/portfolio", json=PROFILE)
    client.post("/api/portfolio", json=PROFILE)                     # same advice again: not stored twice
    mine = records(client_email="advice@example.com", kind="plan")
    assert len(mine) == 1 and mine[0].client_name == "Review User"
    client.post("/api/portfolio", json={**PROFILE, "horizon_years": 4})
    assert len(records(client_email="advice@example.com", kind="plan")) == 2


def test_reviews_are_kept_and_survive_account_deletion(monkeypatch):
    monkeypatch.setattr(navs, "histories", histories())
    monkeypatch.setattr(navs, "latest_nav", lambda code: (100.0, "2026-10-23"))
    client = logged_in_client(monkeypatch, "keep@example.com")
    code = client.get("/api/funds/search", params={"q": "parag parikh flexi"}).json()[0]["code"]
    client.post("/api/review/holdings", json={"code": code, "value": 50_000, "consent": True})
    client.get("/api/review")                                       # nothing new to say: not stored again
    reviews = records(client_email="keep@example.com", kind="review")
    assert len(reviews) == 1
    assert reviews[0].advice["holdings"][0]["rating"] and reviews[0].inputs["holdings"][0]["code"] == code

    body = client.delete("/api/account").json()
    assert body["deleted"] and body["advice_records_kept_years"] == advice_log.RETENTION_YEARS
    with SessionLocal() as db:
        assert db.scalars(select(User).where(User.email == "keep@example.com")).first() is None
    kept = records(client_email="keep@example.com")
    assert kept and all(r.client_name == "Review User" for r in kept)


def test_records_are_purged_after_retention():
    with SessionLocal() as db:
        now = utcnow()
        db.add(AdviceRecord(kind="plan", inputs={}, advice={}, fingerprint="old", client_email="old@example.com",
                            created_at=now - timedelta(days=2000), retain_until=now - timedelta(days=1)))
        db.commit()
    cleanup()
    assert records(client_email="old@example.com") == []
