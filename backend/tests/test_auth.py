"""Sign-up and login by emailed code, sessions, saved plans and account deletion."""
import pytest
from fastapi.testclient import TestClient

from app.routes import auth as auth_routes
from app.services import auth
from main import app

sent = {}


@pytest.fixture(autouse=True)
def capture_codes(monkeypatch):
    sent.clear()
    monkeypatch.setattr(auth_routes, "send_otp", lambda to, code, purpose, minutes: sent.update({to: code}))
    monkeypatch.setattr(auth, "RESEND_COOLDOWN_SECONDS", 0)
    auth._ip_hits.clear()


def signup(client, email="asha@example.com", name="Asha Rao"):
    r = client.post("/api/auth/signup/start", json={"full_name": name, "email": email})
    assert r.status_code == 200, r.text
    r = client.post("/api/auth/verify", json={"email": email, "code": sent[email.strip().lower()], "purpose": "signup"})
    assert r.status_code == 200, r.text
    return r.json()


def test_signup_login_logout():
    client = TestClient(app)
    user = signup(client, "Asha@Example.com ")
    assert user["email"] == "asha@example.com" and user["full_name"] == "Asha Rao"
    assert client.get("/api/auth/me").json()["email"] == "asha@example.com"
    assert "mfa_session" in client.cookies

    # Can't sign up twice with the same email.
    assert client.post("/api/auth/signup/start", json={"full_name": "X Y", "email": "asha@example.com"}).status_code == 409

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    assert client.post("/api/auth/login/start", json={"email": "asha@example.com"}).status_code == 200
    r = client.post("/api/auth/verify", json={"email": "asha@example.com", "code": sent["asha@example.com"],
                                              "purpose": "login"})
    assert r.status_code == 200 and client.get("/api/auth/me").status_code == 200


def test_login_needs_an_account_and_a_valid_email():
    client = TestClient(app)
    assert client.post("/api/auth/login/start", json={"email": "nobody@example.com"}).status_code == 404
    assert client.post("/api/auth/login/start", json={"email": "not-an-email"}).status_code == 422


def test_wrong_codes_are_limited_and_codes_are_single_use():
    client = TestClient(app)
    signup(client, "ravi@example.com", "Ravi K")
    client.post("/api/auth/logout")
    client.post("/api/auth/login/start", json={"email": "ravi@example.com"})
    good = sent["ravi@example.com"]
    bad = "000000" if good != "000000" else "111111"
    for left in (4, 3, 2, 1):
        r = client.post("/api/auth/verify", json={"email": "ravi@example.com", "code": bad, "purpose": "login"})
        assert r.status_code == 400 and f"{left} attempt" in r.json()["detail"]
    client.post("/api/auth/verify", json={"email": "ravi@example.com", "code": bad, "purpose": "login"})
    # Five wrong guesses burn the code, even the right one no longer works.
    r = client.post("/api/auth/verify", json={"email": "ravi@example.com", "code": good, "purpose": "login"})
    assert r.status_code == 400

    client.post("/api/auth/login/start", json={"email": "ravi@example.com"})
    code = sent["ravi@example.com"]
    assert client.post("/api/auth/verify", json={"email": "ravi@example.com", "code": code,
                                                 "purpose": "login"}).status_code == 200
    assert client.post("/api/auth/verify", json={"email": "ravi@example.com", "code": code,
                                                 "purpose": "login"}).status_code == 400


def test_resend_cooldown_and_hourly_limit(monkeypatch):
    client = TestClient(app)
    signup(client, "meera@example.com", "Meera S")
    monkeypatch.setattr(auth, "RESEND_COOLDOWN_SECONDS", 30)
    r = client.post("/api/auth/login/start", json={"email": "meera@example.com"})
    assert r.status_code == 429 and "wait" in r.json()["detail"]
    monkeypatch.setattr(auth, "RESEND_COOLDOWN_SECONDS", 0)
    codes = [client.post("/api/auth/login/start", json={"email": "meera@example.com"}).status_code for _ in range(6)]
    assert 429 in codes


def test_new_code_replaces_the_old_one():
    client = TestClient(app)
    signup(client, "dev@example.com", "Dev P")
    client.post("/api/auth/logout")
    client.post("/api/auth/login/start", json={"email": "dev@example.com"})
    first = sent["dev@example.com"]
    client.post("/api/auth/login/start", json={"email": "dev@example.com"})
    if first != sent["dev@example.com"]:
        assert client.post("/api/auth/verify", json={"email": "dev@example.com", "code": first,
                                                     "purpose": "login"}).status_code == 400


def test_email_not_configured_is_a_clear_error(monkeypatch):
    monkeypatch.undo()   # use the real sender, which has no API key in tests
    auth._ip_hits.clear()
    client = TestClient(app)
    r = client.post("/api/auth/signup/start", json={"full_name": "No Mail", "email": "nomail@example.com"})
    assert r.status_code == 503


def test_saved_plans_and_account_deletion():
    client = TestClient(app)
    assert client.get("/api/plans").status_code == 401
    signup(client, "plans@example.com", "Plan User")
    profile = {"life_stage": "peak_earning", "goal": "wealth_creation", "risk_tolerance": "high",
               "monthly_budget": 20000, "horizon_years": 12}
    result = client.post("/api/portfolio", json=profile).json()
    saved = client.post("/api/plans", json={"profile": profile, "result": result}).json()
    assert saved["name"] == result["portfolio_name"]
    assert [p["id"] for p in client.get("/api/plans").json()] == [saved["id"]]
    assert client.get(f"/api/plans/{saved['id']}").json()["result"]["funds"]

    # Another user can't see it.
    other = TestClient(app)
    signup(other, "other@example.com", "Other User")
    assert other.get(f"/api/plans/{saved['id']}").status_code == 404

    assert client.delete("/api/account").json()["deleted"]
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login/start", json={"email": "plans@example.com"}).status_code == 404


def test_api_responses_are_not_cacheable():
    assert TestClient(app).get("/api/health").headers["cache-control"] == "no-store"
