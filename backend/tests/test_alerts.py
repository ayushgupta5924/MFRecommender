"""Portfolio alerts: only real changes, at most monthly, with a working unsubscribe."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db.tables import Portfolio, User, utcnow
from app.services import alerts
from app.services import nav as navs
from app.services.rankings_store import store
from app.services.review import Reviewer
from main import app
from tests.test_review import histories, holding

DATA = store.get()
TOP = DATA["buckets"]["flexi_cap"]["funds"][0]["code"]
BOTTOM = DATA["buckets"]["flexi_cap"]["funds"][-1]["code"]
reviewer = Reviewer(fetch_histories=histories())


@pytest.fixture
def investor():
    with SessionLocal() as db:
        user = User(email=f"alerts{utcnow().timestamp()}@example.com", full_name="Asha Rao", alerts_enabled=True)
        db.add(user)
        db.commit()
        db.add(Portfolio(user_id=user.id, holdings=[holding(TOP), holding(BOTTOM)]))
        db.commit()
        yield user.id


def run(dry_run=False):
    sent = []
    with SessionLocal() as db:
        counts = alerts.run(db, reviewer, lambda *a, **k: sent.append((a, k)), utcnow(), dry_run=dry_run)
    return counts, sent


def portfolio(user_id):
    db = SessionLocal()
    return db, db.query(Portfolio).filter_by(user_id=user_id).one()


def test_first_run_only_remembers_ratings(investor):
    counts, sent = run()
    assert counts["baselined"] >= 1 and not [s for s in sent if "Asha" in s[0][2]]
    db, p = portfolio(investor)
    assert p.alert_snapshot == {TOP: "in_form", BOTTOM: "out_of_form"}
    db.close()


def test_a_change_sends_one_email_then_waits_a_month(investor):
    run()                                                    # baseline
    db, p = portfolio(investor)
    p.alert_snapshot = {TOP: "in_form", BOTTOM: "on_track"}  # as if it was on track last month
    db.commit(); db.close()

    _, sent = run()
    mine = [s for s in sent if s[0][0].startswith("alerts")]
    assert len(mine) == 1
    (to, subject, html, text), kwargs = mine[0]
    assert "is now out of form" in subject
    assert "On track" in html and "Out of form" in html and "Stop these emails" in html
    assert kwargs["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    db, p = portfolio(investor)
    assert p.alert_snapshot[BOTTOM] == "out_of_form" and p.alerted_at is not None
    p.alert_snapshot = {TOP: "on_track", BOTTOM: "out_of_form"}   # another change straight away
    db.commit(); db.close()
    counts, sent = run()
    assert counts["too_soon"] >= 1 and not [s for s in sent if s[0][0].startswith("alerts")]

    db, p = portfolio(investor)
    p.alerted_at = utcnow() - timedelta(days=alerts.MIN_DAYS_BETWEEN + 1)
    db.commit(); db.close()
    _, sent = run()
    assert len([s for s in sent if s[0][0].startswith("alerts")]) == 1


def test_unsubscribe_link_and_account_switch(investor):
    client = TestClient(app)
    bad = client.get("/api/alerts/unsubscribe", params={"u": investor, "t": "wrong"})
    assert bad.status_code == 400
    good = client.post("/api/alerts/unsubscribe", params={"u": investor, "t": alerts.unsubscribe_token(investor)})
    assert good.status_code == 200 and "won't get" in good.text
    with SessionLocal() as db:
        assert db.get(User, investor).alerts_enabled is False


def test_scheduled_endpoint_needs_the_token(monkeypatch):
    monkeypatch.setattr(navs, "histories", histories())
    monkeypatch.setattr(navs, "latest_nav", lambda code: (100.0, "2026-10-23"))
    client = TestClient(app)
    assert client.post("/api/internal/alerts/run").status_code == 404
    monkeypatch.setenv("ALERTS_TOKEN", "s3cret")
    assert client.post("/api/internal/alerts/run", headers={"X-Alerts-Token": "nope"}).status_code == 404
    r = client.post("/api/internal/alerts/run", params={"dry_run": True}, headers={"X-Alerts-Token": "s3cret"})
    assert r.status_code == 200 and "checked" in r.json()
