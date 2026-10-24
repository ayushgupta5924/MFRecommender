"""Consent: required at sign-up and before holdings are stored, recorded with the notice version; alerts are opt-in."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.db.tables import Portfolio, User
from app.routes import auth as auth_routes
from app.services import auth
from app.services import nav as navs
from main import app
from tests.test_review import histories, logged_in_client


def test_signup_needs_consent_and_records_it(monkeypatch):
    codes = {}
    monkeypatch.setattr(auth_routes, "send_otp", lambda to, code, purpose, minutes: codes.update({to: code}))
    auth._ip_hits.clear()
    client = TestClient(app)
    r = client.post("/api/auth/signup/start", json={"full_name": "No Consent", "email": "noconsent@example.com"})
    assert r.status_code == 422 and "Privacy Notice" in r.json()["detail"]

    client.post("/api/auth/signup/start", json={"full_name": "Yes Consent", "email": "yes@example.com", "consent": True})
    r = client.post("/api/auth/verify", json={"email": "yes@example.com", "code": codes["yes@example.com"],
                                              "purpose": "signup", "consent": True})
    assert r.status_code == 200 and r.json()["alerts_enabled"] is False      # alerts are off until opted in
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "yes@example.com")).one()
        assert user.consented_at is not None and user.consent_version == auth.PRIVACY_VERSION


def test_holdings_need_consent_and_alerts_are_opt_in(monkeypatch):
    monkeypatch.setattr(navs, "histories", histories())
    monkeypatch.setattr(navs, "latest_nav", lambda code: (100.0, "2026-10-23"))
    client = logged_in_client(monkeypatch, "consent-import@example.com")
    code = client.get("/api/funds/search", params={"q": "parag parikh flexi"}).json()[0]["code"]

    r = client.post("/api/review/holdings", json={"code": code, "value": 10_000})
    assert r.status_code == 422 and "agree" in r.json()["detail"]
    r = client.post("/api/review/upload", files={"file": ("cas.pdf", b"%PDF-1.7", "application/pdf")},
                    data={"password": "x"})
    assert r.status_code == 422 and "agree" in r.json()["detail"]

    assert client.post("/api/review/holdings", json={"code": code, "value": 10_000, "consent": True}).status_code == 200
    assert client.get("/api/auth/me").json()["alerts_enabled"] is False
    client.post("/api/review/holdings", json={"code": code, "value": 5_000, "consent": True, "alerts": True})
    assert client.get("/api/auth/me").json()["alerts_enabled"] is True
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "consent-import@example.com")).one()
        p = db.scalars(select(Portfolio).where(Portfolio.user_id == user.id)).one()
        assert p.consented_at is not None and p.consent_version == auth.PRIVACY_VERSION


def test_invest_links_are_neutral():
    plan = TestClient(app).post("/api/portfolio", json={
        "life_stage": "peak_earning", "goal": "wealth_creation", "risk_tolerance": "high",
        "monthly_budget": 20000, "horizon_years": 12}).json()
    assert all(f["investment_url"] == "https://www.mfcentral.com/" for f in plan["funds"])
    assert all(f["isin"] and f["isin"].startswith("INF") for f in plan["funds"])
