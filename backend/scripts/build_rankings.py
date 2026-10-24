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
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.amfi import NAVALL_URL, build_scheme_map, parse_navall, reference_nav_date  # noqa: E402
from app.services.catalog import BUCKETS  # noqa: E402
from app.services.ranking import build_rankings, mfapi_points  # noqa: E402

MFAPI_URL = "https://api.mfapi.in/mf/{code}"
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "rankings.json"
SCHEME_MAP_OUTPUT = OUTPUT.with_name("scheme_map.json")
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

    histories = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_history, s.code, args.cache_dir) for s in schemes]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            code, payload = fut.result()
            if payload:
                histories[code] = mfapi_points(payload)
            if i % 100 == 0:
                print(f"  fetched {i}/{len(schemes)}")
    print(f"mfapi: histories for {len(histories)}/{len(schemes)} schemes")

    rankings = build_rankings(schemes, histories, nav_date)

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
