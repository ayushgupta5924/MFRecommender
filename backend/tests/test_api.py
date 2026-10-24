import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402

client = TestClient(app)
PROFILE = {"life_stage": "just_started", "goal": "wealth_creation", "risk_tolerance": "high",
           "monthly_budget": 10000, "horizon_years": 10}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["funds_ranked"] > 100


def test_portfolio_endpoint():
    r = client.post("/api/portfolio", json=PROFILE)
    assert r.status_code == 200
    body = r.json()
    assert body["funds"] and body["projections"]["expected"]["corpus"] > 0
    assert all(f["investment_url"] == "https://www.mfcentral.com/" for f in body["funds"])


def test_legacy_recommend_endpoint():
    r = client.post("/api/recommend", json=PROFILE)
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_validation_errors_are_422():
    assert client.post("/api/portfolio", json={**PROFILE, "monthly_budget": 100}).status_code == 422
    assert client.post("/api/portfolio", json={**PROFILE, "horizon_years": 99}).status_code == 422
    assert client.post("/api/portfolio", json={k: v for k, v in PROFILE.items() if k != "monthly_budget"}).status_code == 422
