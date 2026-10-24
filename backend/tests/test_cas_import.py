"""CAS import: what we take from casparser's output, and the messages for statements we can't use.

No real investor's statement is used. Most tests build casparser's output objects directly; the last one reads
tests/fixtures/sample_cas.pdf end to end, a statement in CAMS's detailed layout with an invented investor and
real funds priced at their real daily NAVs (rebuild it with tests/fixtures/make_sample_cas.py).
"""
from datetime import date
from decimal import Decimal

import casparser
import pytest
from casparser.exceptions import IncorrectPasswordError
from casparser.types import CASData, Folio, InvestorInfo, Scheme, SchemeValuation, StatementPeriod, TransactionData

from app.services import holdings as hold
from app.services.rankings_store import scheme_map

SCHEMES = scheme_map.schemes()
DIRECT = "122639"                                                     # Parag Parikh Flexi Cap, Direct Growth
REGULAR = next(c for c, s in SCHEMES.items() if s["twin"] == DIRECT and not s["direct"] and s["growth"])
PDF = b"%PDF-1.7 fake"


def txn(d, kind, amount, units):
    return TransactionData(date=d, description=kind, amount=Decimal(str(amount)) if amount is not None else None,
                           units=Decimal(str(units)) if units is not None else None, nav=None, balance=None, type=kind)


def scheme(code, isin, units, txns, open_units=0, amfi=True):
    return Scheme(scheme=SCHEMES[code]["name"] + " - Growth", rta_code="X1", rta="CAMS", isin=isin,
                  amfi=code if amfi else None, open=Decimal(open_units), close=Decimal(str(units)),
                  close_calculated=Decimal(str(units)),
                  valuation=SchemeValuation(date=date(2026, 10, 23), nav=Decimal("80.5"), cost=Decimal("150000"),
                                            value=Decimal(str(units * 80.5))),
                  transactions=txns)


def statement():
    regular_isin = SCHEMES[REGULAR]["isins"][0]
    return CASData(
        statement_period=StatementPeriod(**{"from": "01-Jan-2018", "to": "23-Oct-2026"}),
        investor_info=InvestorInfo(name="TEST INVESTOR", email="t@example.com", address="1 Test Road", mobile="9999999999"),
        cas_type="DETAILED", file_type="CAMS",
        folios=[Folio(folio="12345678/90", amc="PPFAS Mutual Fund", PAN="ABCDE1234F", KYC="OK", PANKYC="OK", schemes=[
            # Regular plan found by ISIN only (no AMFI code on the statement).
            scheme(REGULAR, regular_isin, 1500.0, [
                txn(date(2022, 1, 5), "PURCHASE_SIP", 50000, 1000),
                txn(date(2023, 1, 5), "PURCHASE_SIP", 50000, 800),
                txn(date(2024, 6, 1), "REDEMPTION", -25000, -300),
                txn(date(2024, 6, 1), "STT_TAX", 1, None),
            ], amfi=False),
            # Fully redeemed: must be skipped.
            scheme(DIRECT, SCHEMES[DIRECT]["isins"][0], 0, [txn(date(2021, 1, 1), "PURCHASE", 10000, 200)]),
        ])],
    )


@pytest.fixture
def fake_reader(monkeypatch):
    def install(result=None, error=None):
        def read(pdf, password, **kwargs):
            if error:
                raise error
            return result
        monkeypatch.setattr(casparser, "read_cas_pdf", read)
    return install


def test_statement_becomes_holdings_without_personal_data(fake_reader):
    fake_reader(statement())
    parsed = hold.parse_cas(PDF, "ABCDE1234F")
    assert parsed["statement_type"] == "DETAILED" and parsed["statement_to"] == "23-Oct-2026"
    assert len(parsed["holdings"]) == 1                      # the redeemed scheme is dropped
    h = parsed["holdings"][0]
    assert h["code"] == REGULAR and h["units"] == 1500.0 and h["cost"] == 150000.0
    assert h["txns"][0] == ["2022-01-05", "PURCHASE_SIP", 50000.0, 1000.0]
    assert ["2024-06-01", "REDEMPTION", -25000.0, -300.0] in h["txns"]
    # Nothing identifying the investor survives.
    flat = repr(parsed)
    for secret in ("ABCDE1234F", "TEST INVESTOR", "t@example.com", "9999999999", "1 Test Road", "12345678"):
        assert secret not in flat


def test_imported_statement_reviews_end_to_end(fake_reader):
    from app.services.review import Reviewer
    from tests.test_review import TODAY, histories
    fake_reader(statement())
    review = Reviewer(fetch_histories=histories()).review(hold.parse_cas(PDF, "x")["holdings"], today=TODAY)
    row = review["holdings"][0]
    assert row["plan"] == "Regular" and row["rating"]["status"] != "not_rated"
    # FIFO: 300 of the first 1,000 units are sold, leaving 35,000 of that lot plus the 50,000 lot.
    assert row["invested"] == pytest.approx(85000)
    assert row["xirr"] is not None and row["lt_gain"] is not None


@pytest.mark.parametrize("error,message", [
    (IncorrectPasswordError("bad"), "Wrong password"),
    (casparser.exceptions.CASParseError("garbled"), "couldn't read this statement"),
])
def test_clear_messages_for_bad_statements(fake_reader, error, message):
    fake_reader(error=error)
    with pytest.raises(hold.StatementError, match=message):
        hold.parse_cas(PDF, "x")


def test_depository_statement_is_refused(fake_reader):
    fake_reader(object())                                    # NSDL/CDSL results have no folios
    with pytest.raises(hold.StatementError, match="NSDL/CDSL"):
        hold.parse_cas(PDF, "x")


def test_sample_statement_pdf_end_to_end():
    import json
    from pathlib import Path

    from app.services.review import Reviewer

    fixtures = Path(__file__).parent / "fixtures"
    expected = json.loads((fixtures / "sample_cas_expected.json").read_text(encoding="utf-8"))
    parsed = hold.parse_cas((fixtures / "sample_cas.pdf").read_bytes(), "")
    assert parsed["warnings"] == [] and parsed["statement_to"] == "23-Oct-2026"
    by_code = {h["code"]: h for h in parsed["holdings"]}
    assert set(by_code) == {f["code"] for f in expected["funds"]}
    for f in expected["funds"]:
        h = by_code[f["code"]]
        assert h["units"] == pytest.approx(float(f["units"]), abs=1e-3)
        assert h["cost"] == pytest.approx(float(f["cost"]), abs=0.01)
        assert h["isin"] == f["isin"] and len(h["txns"]) == f["transactions"]
    assert expected["pan"] not in json.dumps(parsed)          # identity fields are never kept

    # Price every fund at its statement NAV and check the review's XIRR against an independent calculation.
    as_of = date(2026, 10, 23)
    navs = {f["code"]: float(f["nav"]) for f in expected["funds"]}
    reviewer = Reviewer(fetch_histories=lambda codes: {c: [(as_of.isoformat(), navs.get(c, 1.0))] for c in codes})
    review = reviewer.review(parsed["holdings"], today=as_of)

    def xirr(flows):
        def npv(r):
            return sum(a / (1 + r) ** ((d - flows[0][0]).days / 365) for d, a in flows)
        lo, hi = -0.99, 5.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if npv(lo) * npv(mid) <= 0 else (mid, hi)
        return mid

    rows = {h["code"]: h for h in review["holdings"]}
    for f in expected["funds"]:
        value = float(f["units"]) * navs[f["code"]]
        flows = sorted([(date.fromisoformat(d), -float(a)) for d, a in f["flows"]] + [(as_of, value)])
        assert rows[f["code"]]["value"] == pytest.approx(value, abs=0.05)
        assert rows[f["code"]]["xirr"] == pytest.approx(xirr(flows), abs=1e-4)
