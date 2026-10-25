"""Fund research pages and the rank history behind their trend chart. No network: NAVs are faked."""
import pytest
from fastapi.testclient import TestClient

from app.services import nav as navs
from app.services import rank_history
from app.services.rankings_store import scheme_map, store
from main import app
from tests.test_review import histories, regular_twin_of

DATA = store.get()
PPFAS = "122639"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(navs, "histories", histories())
    return TestClient(app)


def test_categories_and_a_ranked_category(client):
    cats = client.get("/api/funds/categories").json()["categories"]
    assert {c["key"] for c in cats} >= {"flexi_cap", "liquid"}
    flexi = client.get("/api/funds/category/flexi_cap").json()
    funds = flexi["funds"]
    assert [f["rank"] for f in funds] == list(range(1, len(funds) + 1))
    assert funds[0]["status"] == "in_form" and funds[-1]["status"] == "out_of_form"
    assert client.get("/api/funds/category/nope").status_code == 404


def test_fund_page_for_a_ranked_fund(client):
    f = client.get(f"/api/funds/{PPFAS}").json()
    assert f["name"] == scheme_map.schemes()[PPFAS]["name"] and f["bucket"] == "flexi_cap"
    assert f["rating"]["status"] in ("in_form", "on_track", "off_track", "out_of_form")
    assert f["chart"] and len(f["chart"]) <= 401 and f["nav"]["value"] > 0
    assert set(f["returns"]) == {"cagr_1y", "cagr_3y", "cagr_5y", "cagr_10y"}
    assert len(f["peers"]) == 5 and f["peers"][0]["rank"] == 1
    assert f["direct_growth_twin"] is None


def test_a_regular_plan_points_to_its_direct_twin(client):
    regular = regular_twin_of(PPFAS)
    f = client.get(f"/api/funds/{regular}").json()
    assert f["plan"] == "Regular" and f["direct_growth_twin"]["code"] == PPFAS
    assert f["rating"]["status"] != "not_rated"            # rated through its Direct-Growth twin


def test_unknown_fund(client):
    assert client.get("/api/funds/99999999").status_code == 404
    assert client.get("/api/funds/abc").status_code == 422
    assert client.get("/api/funds/search?q=parag").status_code == 200   # still the search, not a fund code


def test_rank_history_keeps_one_point_a_week_for_two_years():
    small = {"buckets": {"flexi_cap": {"funds": [{"code": "A"}, {"code": "B"}]}}}
    swapped = {"buckets": {"flexi_cap": {"funds": [{"code": "B"}, {"code": "A"}]}}}
    h = rank_history.record(None, small, "2026-10-19")          # Monday
    h = rank_history.record(h, swapped, "2026-10-23")           # same week: replaces
    assert h["funds"]["A"] == [["2026-10-23", 2, 2, "flexi_cap"]]
    h = rank_history.record(h, small, "2026-10-26")             # next week: adds
    assert [p[0] for p in h["funds"]["A"]] == ["2026-10-23", "2026-10-26"]
    h = rank_history.record(h, small, "2029-01-01")             # over two years later: old points dropped
    assert [p[0] for p in h["funds"]["A"]] == ["2029-01-01"]


def test_quartiles_match_the_review():
    assert [rank_history.quartile(r, 9) for r in (1, 3, 5, 7, 9)] == \
        ["in_form", "on_track", "off_track", "out_of_form", "out_of_form"]
