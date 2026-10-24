"""Rebuild app/data/rankings.json from AMFI + mfapi.in.

Run from the backend directory:
    python -m scripts.build_rankings
    python -m scripts.build_rankings --cache-dir /tmp/mf-cache   # reuse downloads while developing

Exits non-zero (leaving the existing file untouched) if the data looks incomplete,
so a bad upstream day never replaces good rankings.
"""
import argparse
import concurrent.futures
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import fund_facts as ff  # noqa: E402
from app.services.amfi import NAVALL_URL, build_scheme_map, index_fund_rows, parse_navall, reference_nav_date  # noqa: E402
from app.services.catalog import BUCKETS, benchmark_funds  # noqa: E402
from app.services.ranking import build_rankings, mfapi_points  # noqa: E402

MFAPI_URL = "https://api.mfapi.in/mf/{code}"
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "rankings.json"
SCHEME_MAP_OUTPUT = OUTPUT.with_name("scheme_map.json")
FACTS_OUTPUT = OUTPUT.with_name("fund_facts.json")
HOLDINGS_OUTPUT = OUTPUT.with_name("holdings.json")
MIN_FACTS_COVERAGE = 0.6        # share of ranked schemes a facts refresh must cover to replace the last one
MIN_SCHEMES_IN_MAP = 3000
MIN_FUNDS_PER_BUCKET = 5
HEADERS = {"User-Agent": "mf-advisor-rankings/2.0"}


def get(url: str, timeout: int = 60, attempts: int = 4) -> requests.Response:
    for attempt in range(attempts):
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS)
            if resp.status_code == 200:
                return resp
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url}")


def fetch_history(code: str, cache_dir: Path = None):
    cache_file = cache_dir / f"{code}.json" if cache_dir else None
    if cache_file and cache_file.exists():
        return code, json.loads(cache_file.read_text(encoding="utf-8"))
    try:
        payload = get(MFAPI_URL.format(code=code), timeout=30).json()
    except Exception as e:  # one bad fund must not sink the run
        print(f"  ! {code}: {e}", file=sys.stderr)
        return code, None
    if cache_file:
        cache_file.write_text(json.dumps(payload), encoding="utf-8")
    return code, payload


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def refresh_facts(schemes, scheme_map: dict, facts_path: Path, holdings_path: Path, force: bool = False):
    """Fund facts for scoring: refreshed weekly, the last good snapshot kept when a source fails.

    Returns the snapshot to score with, or None when there is none recent enough.
    """
    today = date.today()
    old = read_json(facts_path)
    if old and old.get("schema_version") != ff.FACTS_SCHEMA_VERSION:
        old = None
    if old and not force and ff.is_fresh(old, today, ff.REFRESH_DAYS):
        print(f"Fund facts from {old['fetched_at'][:10]} are recent; not refetching.")
        return old

    wanted = {code for code, s in scheme_map.items() if s["direct"] and s["growth"]}
    isin_to_code = {i: code for code in wanted for i in scheme_map[code]["isins"]}
    get_json = lambda url: get(url, timeout=120).json()  # noqa: E731
    try:
        facts = ff.kuvera_facts(get_json, isin_to_code, wanted)
    except Exception as e:
        print(f"  ! Kuvera fund facts failed: {e}", file=sys.stderr)
        facts = {}
    try:
        aum_source = ff.reconcile_aum(facts, ff.amfi_scheme_aum(get_json, scheme_map))
    except Exception as e:
        print(f"  ! AMFI AUM failed: {e}", file=sys.stderr)
        aum_source = "kuvera"

    ranked = {s.code for s in schemes}
    covered = sum(1 for c in ranked if (facts.get(c) or {}).get("ter") is not None)
    if covered < MIN_FACTS_COVERAGE * len(ranked):
        print(f"Fund facts cover only {covered}/{len(ranked)} schemes; keeping the previous snapshot.", file=sys.stderr)
        return old if old and ff.is_fresh(old, today, ff.MAX_AGE_DAYS) else None

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    seen = (old or {}).get("managers_seen", {})
    baseline = (old or {}).get("baseline") or today.isoformat()
    ff.update_managers(seen, facts, today.isoformat())
    holdings = {c: f.pop("holdings") for c, f in facts.items() if f.get("holdings")}
    snapshot = {"schema_version": ff.FACTS_SCHEMA_VERSION, "fetched_at": stamp, "aum_source": aum_source,
                "baseline": baseline, "facts": facts, "managers_seen": seen}
    write_json(facts_path, snapshot)
    dates = sorted(f.get("portfolio_date") or "" for f in facts.values() if f.get("portfolio_date"))
    write_json(holdings_path, {"schema_version": ff.HOLDINGS_SCHEMA_VERSION, "generated_at": stamp,
                               "portfolio_date": dates[len(dates) // 2] if dates else None, "holdings": holdings})
    print(f"Fund facts for {len(facts)} schemes ({covered}/{len(ranked)} ranked), AUM from {aum_source}; "
          f"portfolios for {len(holdings)}.")
    return snapshot


def update_scheme_map(lines, path: Path) -> None:
    """Rewrite the scheme map only when schemes changed, so the nightly commit stays small."""
    schemes = build_scheme_map(lines)
    if len(schemes) < MIN_SCHEMES_IN_MAP:
        print(f"Only {len(schemes)} schemes in the map; keeping the existing file.", file=sys.stderr)
        return
    if path.exists():
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("schemes") == schemes:
                print("Scheme map unchanged.")
                return
        except ValueError:
            pass
    generated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json(path, {"schema_version": 1, "generated_at": generated, "schemes": schemes})
    print(f"Wrote {len(schemes)} schemes to {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, help="Directory to cache downloads in (development only)")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh-facts", action="store_true", help="Refetch fund facts even if recent")
    parser.add_argument("--skip-facts", action="store_true", help="Rank on NAV data only (development)")
    args = parser.parse_args()

    if args.cache_dir:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        navall_cache = args.cache_dir / "NAVAll.txt"
        if navall_cache.exists():
            text = navall_cache.read_text(encoding="utf-8", errors="replace")
        else:
            text = get(NAVALL_URL).content.decode("utf-8", errors="replace")
            navall_cache.write_text(text, encoding="utf-8")
    else:
        text = get(NAVALL_URL).content.decode("utf-8", errors="replace")

    update_scheme_map(text.splitlines(), args.output.with_name(SCHEME_MAP_OUTPUT.name))

    schemes = parse_navall(text.splitlines())
    if len(schemes) < 300:
        print(f"Only {len(schemes)} schemes parsed from AMFI; refusing to continue.", file=sys.stderr)
        return 1
    nav_date = reference_nav_date(schemes).isoformat()
    print(f"AMFI: {len(schemes)} eligible Direct-Growth schemes, NAV date {nav_date}")

    index_codes = benchmark_funds(index_fund_rows(text.splitlines()))
    print(f"Benchmarks: {index_codes}")

    histories = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        codes = [s.code for s in schemes] + sorted(set(index_codes.values()) - {s.code for s in schemes})
        futures = [pool.submit(fetch_history, code, args.cache_dir) for code in codes]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            code, payload = fut.result()
            if payload:
                histories[code] = mfapi_points(payload)
            if i % 100 == 0:
                print(f"  fetched {i}/{len(schemes)}")
    print(f"mfapi: histories for {len(histories)}/{len(schemes)} schemes")

    facts = None
    if not args.skip_facts:
        scheme_map = (read_json(args.output.with_name(SCHEME_MAP_OUTPUT.name)) or {}).get("schemes") or {}
        facts = refresh_facts(schemes, scheme_map, args.output.with_name(FACTS_OUTPUT.name),
                              args.output.with_name(HOLDINGS_OUTPUT.name), args.refresh_facts)
    rankings = build_rankings(schemes, histories, nav_date, index_codes, facts)

    thin = [k for k, b in rankings["buckets"].items() if len(b["funds"]) < MIN_FUNDS_PER_BUCKET]
    if thin:
        print(f"Too few ranked funds in: {', '.join(thin)}; refusing to overwrite.", file=sys.stderr)
        return 1

    write_json(args.output, rankings)
    total = sum(len(b["funds"]) for b in rankings["buckets"].values())
    print(f"Wrote {total} ranked funds across {len(BUCKETS)} buckets to {args.output} "
          f"(risk-free {rankings['risk_free_rate']:.2%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
