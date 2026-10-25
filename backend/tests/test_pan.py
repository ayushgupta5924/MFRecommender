"""Fetch by PAN: parsing smallcase's MF holdings webhook and the start -> webhook -> status flow.
No network: smallcase is faked."""
import base64
import hashlib
import hmac
import json
import secrets

import pytest
from fastapi.testclient import TestClient

from app.routes import pan as pan_routes
from app.services import mfc
from app.services import nav as navs
from app.services.rankings_store import scheme_map
from main import app
from tests.test_review import histories, logged_in_client

PPFAS = "122639"
ISIN = scheme_map.schemes()[PPFAS]["isins"][0]
KEYS = {"SMALLCASE_GATEWAY_NAME": "testgw", "SMALLCASE_API_SECRET": "api-secret", "SMALLCASE_JWT_SECRET": "jwt-secret"}


def sign(payload: dict) -> dict:
    msg = f"{payload['timestamp']}{payload['transactionId']}".encode()
    return {**payload, "checksum": hmac.new(b"api-secret", msg, hashlib.sha256).hexdigest()}


def webhook(txn_id="TRX_1", units=120.5):
    """The shape of smallcase's "cas detail" MF holdings webhook, with the personal parts it also carries."""
    t = {"isin": ISIN, "folioNumber": "123", "scheme": "Parag Parikh Flexi Cap Fund - Direct Growth"}
    return sign({
        "fromDate": "1-Jan-1986", "toDate": "7-Dec-2025 ", "snapshotDate": "2025-12-07T12:21:04.934Z",
        "transactionId": txn_id, "gateway": "testgw", "timestamp": "2025-12-07T12:22:00.000Z",
        "summary": {"schemeDetails": [
            {"isin": ISIN, "scheme": "Parag Parikh Flexi Cap Fund - Direct Growth", "amc": "PPFAS Mutual Fund",
             "units": units, "nav": 85.12, "currentValue": units * 85.12,
             "analytics": {"investedValue": 7000.0},
             "folios": [{"folioNumber": "123", "units": units, "lastNavDate": "05-DEC-2025",
                         "email": "x@example.com", "mobile": "9876543210", "investorName": "A Person"}]},
            {"isin": "INF000GONE01", "scheme": "Closed Fund", "units": 0, "folios": []},
        ]},
        "transactions": [
            {**t, "transactionDate": "2024-01-09T18:30:00.000Z", "trxnAmount": 5000, "trxnUnits": 100.5,
             "analytics": {"transactionType": "DEPOSIT", "transactionStatus": "SUCCESS",
                           "transactionDescription": "PURCHASE"}},
            {**t, "transactionDate": "2025-02-09T18:30:00.000Z", "trxnAmount": 2000, "trxnUnits": 30,
             "analytics": {"transactionType": "DEPOSIT", "transactionStatus": "SUCCESS",
                           "transactionDescription": "SIP"}},
            {**t, "transactionDate": "2025-05-31T18:30:00.000Z", "trxnAmount": -900, "trxnUnits": -10,
             "analytics": {"exited": False, "transactionType": "NA"}},
            {**t, "transactionDate": "2025-06-01T18:30:00.000Z", "trxnDescription": "Address Updated from KRA Data",
             "trxnAmount": 0, "trxnUnits": 0, "analytics": {"transactionType": "NA"}},
            {**t, "transactionDate": "2025-06-02T18:30:00.000Z", "trxnAmount": 50, "trxnUnits": 1,
             "analytics": {"transactionType": "REJECTED DEPOSIT", "transactionDescription": "PURCHASE"}},
        ],
        "userInfo": {"pan": "ABCDE1234F", "name": "A Person", "address": "Somewhere", "bankAccounts": []},
    })


# ── Parsing ──────────────────────────────────────────────────────────────────

def test_parses_holdings_with_ist_dates_and_cas_style_transactions():
    holdings, warnings = mfc.parse_payload(webhook())
    assert warnings == []
    [h] = holdings                                       # the zero-unit scheme is skipped
    assert (h["source"], h["code"], h["units"], h["cas_nav"], h["cost"]) == ("pan", PPFAS, 120.5, 85.12, 7000.0)
    assert h["cas_nav_date"] == "2025-12-05"
    # 18:30 UTC the day before is midnight IST; address changes and rejected purchases are dropped.
    assert h["txns"] == [["2024-01-10", "PURCHASE", 5000.0, 100.5], ["2025-02-10", "PURCHASE_SIP", 2000.0, 30.0],
                         ["2025-06-01", "REDEMPTION", -900.0, -10.0]]
    assert h["open_units"] == 0.0


def test_no_personal_data_survives_parsing():
    holdings, _ = mfc.parse_payload(webhook())
    text = json.dumps(holdings)
    for secret in ("ABCDE1234F", "A Person", "9876543210", "x@example.com", "Somewhere"):
        assert secret not in text


def test_units_older_than_the_transactions_make_the_holding_partial():
    [h] = mfc.parse_payload(webhook(units=150))[0]
    assert h["open_units"] == pytest.approx(29.5)


def test_checksum_and_guest_token(monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    payload = webhook()
    assert mfc.checksum_ok(payload)
    assert not mfc.checksum_ok({**payload, "transactionId": "TRX_OTHER"})
    assert not mfc.checksum_ok({k: v for k, v in payload.items() if k != "checksum"})
    header, body, sig = mfc.guest_token(now=1000).split(".")
    claims = json.loads(base64.urlsafe_b64decode(body + "=="))
    assert claims == {"guest": True, "exp": 1000 + mfc.TOKEN_SECONDS}
    expected = hmac.new(b"jwt-secret", f"{header}.{body}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(sig + "==") == expected


# ── Flow ─────────────────────────────────────────────────────────────────────

class FakeGateway:
    def __init__(self):
        self.sent = []

    def create_transaction(self, pan, phone, email):
        self.sent.append({"pan": pan, "phone": phone, "email": email})
        # Unique across tests: they share one database.
        return {"transactionId": f"TRX_{secrets.token_hex(8)}", "expireAt": "2030-01-01T00:00:00.000Z"}


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeGateway()
    monkeypatch.setattr(pan_routes, "client", fake)
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(navs, "histories", histories())
    monkeypatch.setattr(navs, "latest_nav", lambda code: (100.0, "2026-10-23"))
    return fake


def test_switched_off_without_smallcase_keys(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    client = TestClient(app)
    assert client.get("/api/health").json()["pan_enabled"] is False
    assert client.post("/api/pan/start", json={"pan": "ABCDE1234F", "mobile": "9876543210",
                                               "consent": True}).status_code == 404


def test_guest_flow_start_then_webhook_then_review(gateway):
    client = TestClient(app)
    assert client.get("/api/health").json()["pan_enabled"] is True
    assert client.post("/api/pan/start", json={"pan": "ABCDE1234F", "mobile": "9876543210"}).status_code == 422
    assert client.post("/api/pan/start", json={"pan": "ABC", "mobile": "9876543210", "consent": True}).status_code == 422
    assert client.post("/api/pan/start", json={"pan": "ABCDE1234F", "consent": True}).status_code == 422

    start = client.post("/api/pan/start", json={"pan": "abcde1234f", "mobile": "9876543210", "consent": True}).json()
    assert gateway.sent[-1] == {"pan": "ABCDE1234F", "phone": "9876543210", "email": None}
    assert start["gateway"] == "testgw" and start["token"].count(".") == 2 and start["key"]
    assert start["sdk"].startswith("https://gateway.smallcase.com/")
    ask = {"id": start["id"], "key": start["key"]}

    assert client.post("/api/pan/status", json={"id": start["id"], "key": "wrong"}).status_code == 404
    assert client.post("/api/pan/status", json=ask).json() == {"status": "waiting"}
    # Unsigned or wrongly signed webhooks are refused.
    assert client.post("/api/pan/webhook", json={**webhook(start["id"]), "checksum": "0" * 64}).status_code == 401
    assert client.post("/api/pan/webhook", json=webhook(start["id"])).status_code == 200

    done = client.post("/api/pan/status", json=ask).json()
    assert done["status"] == "done" and done["statement"]["type"] == "MF Central"
    assert done["statement"]["to"] == "2025-12-07"
    assert done["holdings"][0]["source"] == "pan" and done["review"]["holdings"][0]["code"] == PPFAS
    # Handed over once and cleared from the server.
    assert client.post("/api/pan/status", json=ask).json() == {"status": "done"}
    # A replayed webhook doesn't bring the holdings back.
    client.post("/api/pan/webhook", json=webhook(start["id"]))
    assert client.post("/api/pan/status", json=ask).json() == {"status": "done"}
    # The guest review endpoint accepts them back, as it does CAS holdings.
    again = client.post("/api/review/guest", json={"consent": True, "holdings": done["holdings"]})
    assert again.status_code == 200, again.text


def test_mf_central_errors_reach_the_investor(gateway):
    client = TestClient(app)
    start = client.post("/api/pan/start", json={"pan": "ABCDE1234F", "email": "me@example.com", "consent": True}).json()
    assert gateway.sent[-1]["email"] == "me@example.com" and gateway.sent[-1]["phone"] is None
    failed = sign({"transactionId": start["id"], "timestamp": "2025-01-01T12:00:00.000Z",
                   "error": {"value": True, "message": "mfc_timeout", "code": 2003}})
    assert client.post("/api/pan/webhook", json=failed).status_code == 200
    r = client.post("/api/pan/status", json={"id": start["id"], "key": start["key"]}).json()
    assert r["status"] == "failed" and "in time" in r["message"]


def test_account_flow_saves_the_portfolio_and_keeps_funds_added_by_hand(gateway, monkeypatch):
    client = logged_in_client(monkeypatch, "pan@example.com")
    monkeypatch.setattr(pan_routes, "client", gateway)
    client.post("/api/review/holdings", json={"code": "118955", "value": 10_000, "consent": True})
    start = client.post("/api/pan/start", json={"pan": "ABCDE1234F", "mobile": "9876543210", "consent": True}).json()
    assert start["key"] is None                          # an account's own session identifies it
    TestClient(app).post("/api/pan/webhook", json=webhook(start["id"]))
    # Someone else (no session, no key) can't collect it.
    assert TestClient(app).post("/api/pan/status", json={"id": start["id"]}).status_code == 404
    done = client.post("/api/pan/status", json={"id": start["id"]}).json()
    assert done["status"] == "done"
    assert {h["code"] for h in done["review"]["holdings"]} == {PPFAS, "118955"}
    assert done["review"]["statement"]["type"] == "MF Central"
    assert {h["code"] for h in client.get("/api/review/holdings").json()} == {PPFAS, "118955"}
