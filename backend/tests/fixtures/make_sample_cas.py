"""Build a test CAMS detailed CAS PDF: invented investor, real funds, real daily NAVs (mfapi.in).

Writes sample_cas.pdf and sample_cas_expected.json (units, cost, value, transactions per fund) next to this
script. No real investor: the name, address, contacts and PAN are invented; only the funds and NAVs are real.
Usage (from backend/): python tests/fixtures/make_sample_cas.py [nav-cache-dir]
"""
import json
import random
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import requests

HERE = Path(__file__).parent
CACHE = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "navs"
CACHE.mkdir(parents=True, exist_ok=True)
STATEMENT_TO = date(2026, 10, 23)
STATEMENT_FROM = date(2019, 1, 1)
STAMP = Decimal("0.00005")             # stamp duty on purchases since 1 July 2020

# ── Invented investor (no real person) ─────────────────────────────────────
rng = random.Random(20261025)
FAKE_PAN = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5)) + \
    "".join(rng.choice("0123456789") for _ in range(4)) + rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
INVESTOR = ["Email Id: test.investor@example.com", "TESTA INVESTORKUMARI", "Flat 0, Imaginary Residency",
            "Nowhere Road, Testnagar", "Test City - 000000", "Mobile: +910000000000"]
HOLDER = "Testa Investorkumari"

# ── Real funds, invented transactions ──────────────────────────────────────
FUNDS = [
    {"amc": "Nippon India Mutual Fund", "folio": "4012345678 / 0", "code": "118778", "rta_code": "RMFSCDG",
     "name": "Nippon India Small Cap Fund - Direct Plan Growth Plan - Growth Option", "isin": "INF204K01K15",
     "rta": "CAMS", "sip": (5_000, date(2021, 1, 10), date(2026, 10, 10)),
     "lumps": [], "redeem": [(date(2025, 6, 16), 50_000)]},
    {"amc": "PPFAS Mutual Fund", "folio": "13579246", "code": "122639", "rta_code": "PP001ZG",
     "name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth", "isin": "INF879O01027",
     "rta": "KFINTECH", "sip": (10_000, date(2022, 4, 5), date(2026, 10, 5)), "lumps": [], "redeem": []},
    {"amc": "HDFC Mutual Fund", "folio": "24681357 / 99", "code": "105758", "rta_code": "HMCOGT",
     "name": "HDFC Mid Cap Fund - Regular Plan - Growth", "isin": "INF179K01CR2",
     "rta": "CAMS", "sip": None, "lumps": [(date(2019, 3, 15), 100_000), (date(2020, 4, 7), 50_000)], "redeem": []},
    {"amc": "HDFC Mutual Fund", "folio": "24681357 / 99", "code": "118987", "rta_code": "HCBDG",
     "name": "HDFC Corporate Bond Fund - Direct Plan - Growth Option", "isin": "INF179K01XD8",
     "rta": "CAMS", "sip": None, "lumps": [(date(2023, 8, 1), 200_000)], "redeem": []},
]


def nav_history(code):
    f = CACHE / f"{code}.json"
    if not f.exists():
        f.write_text(requests.get(f"https://api.mfapi.in/mf/{code}", timeout=60).text, encoding="utf-8")
    out = {}
    for row in json.loads(f.read_text(encoding="utf-8"))["data"]:
        d, m, y = row["date"].split("-")
        out[date(int(y), int(m), int(d))] = Decimal(row["nav"])
    return out


def on_or_after(navs, day):
    for i in range(10):
        d = day + timedelta(days=i)
        if d in navs:
            return d, navs[d]
    raise ValueError(f"no NAV near {day}")


def q(x, places="0.001"):
    return x.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def build_transactions(fund):
    navs = nav_history(fund["code"])
    events = []
    if fund["sip"]:
        amount, start, end = fund["sip"]
        d, n = start, 1
        while d <= end:
            events.append(("sip", d, amount, n))
            d = date(d.year + (d.month == 12), d.month % 12 + 1, d.day)
            n += 1
    events += [("lump", d, a, None) for d, a in fund["lumps"]]
    events += [("redeem", d, a, None) for d, a in fund["redeem"]]
    events.sort(key=lambda e: e[1])

    balance, rows, lots = Decimal(0), [], []
    for kind, day, amount, n in events:
        d, nav = on_or_after(navs, day)
        amount = Decimal(amount)
        if kind in ("sip", "lump"):
            stamp = q(amount * STAMP, "0.01") if d >= date(2020, 7, 1) else Decimal(0)
            net = amount - stamp
            units = q(net / nav)
            balance += units
            desc = (f"Systematic Investment Purchase-Instalment No - {n}" if kind == "sip" else "Purchase")
            rows.append((d, desc, net, units, nav, balance))
            if stamp:
                rows.append((d, "*** Stamp Duty ***", stamp, None, None, None))
            lots.append([d, units, net])
        else:
            units = q(amount / nav)
            balance -= units
            rows.append((d, "Redemption", -amount, -units, nav, balance))
            rows.append((d, "*** STT Paid ***", q(amount * Decimal("0.00001"), "0.01"), None, None, None))
            left = units
            while left > 0:
                lot = lots[0]
                take = min(lot[1], left)
                lot[2] -= lot[2] * take / lot[1]
                lot[1] -= take
                left -= take
                if lot[1] <= 0:
                    lots.pop(0)
    last_day, last_nav = max((d, v) for d, v in navs.items() if d <= STATEMENT_TO)
    cost = q(sum(c for _, _, c in lots), "0.01")
    return rows, {"code": fund["code"], "isin": fund["isin"], "units": str(balance), "cost": str(cost),
                  "nav": str(last_nav), "nav_date": last_day.isoformat(),
                  "value": str(q(balance * last_nav, "0.01")), "transactions": len(rows),
                  "flows": [[r[0].isoformat(), str(r[2])] for r in rows if r[3] is not None]}


# ── PDF layout ─────────────────────────────────────────────────────────────

W = {c: w for c, w in zip(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
    [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 +
    [278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
     667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556,
     278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334,
     260, 334, 584])}
SIZE = 7
COL = {"Date": 40, "Transaction": 95, "Amount": 360, "Units": 420, "Price": 480, "Balance": 550}


def width(text, size=SIZE):
    return sum(W.get(c, 556) for c in text) * size / 1000


def money(x):
    """Indian grouping, parentheses for negatives, as CAMS prints."""
    neg = x < 0
    s = f"{abs(x):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(([head] if head else []) + groups + [tail])
    out = f"{whole}.{frac}"
    return f"({out})" if neg else out


def units_str(u):
    s = f"{abs(u):,.3f}"
    return f"({s})" if u < 0 else s


def right(x_right, text):
    return (x_right - width(text), text)


HEADER = [[(COL["Date"], "Date"), (COL["Transaction"], "Transaction"), right(COL["Amount"], "Amount"),
           right(COL["Units"], "Units"), right(COL["Price"], "Price"), right(COL["Balance"], "Unit")],
          [right(COL["Amount"], "(INR)"), right(COL["Price"], "(INR)"), right(COL["Balance"], "Balance")]]


def row_atoms(r):
    d, desc, amt, units, nav, bal = r
    atoms = [(COL["Date"], d.strftime("%d-%b-%Y")), (COL["Transaction"], desc), right(COL["Amount"], money(amt))]
    if units is not None:
        atoms += [right(COL["Units"], units_str(units)), right(COL["Price"], f"{nav:.4f}"),
                  right(COL["Balance"], f"{bal:,.3f}")]
    return atoms


def build_lines(funds_rows):
    lines = []
    last_amc = last_folio = None
    for fund, rows, exp in funds_rows:
        if fund["amc"] != last_amc:
            lines.append([(40, fund["amc"])])
            last_amc, last_folio = fund["amc"], None
        if fund["folio"] != last_folio:
            lines.append([(40, f"Folio No: {fund['folio']}"), (180, f"PAN: {FAKE_PAN}"), (260, "KYC: OK  PAN: OK")])
            lines.append([(40, HOLDER)])
            last_folio = fund["folio"]
        lines.append([(40, f"{fund['rta_code']}-{fund['name']} - ISIN: {fund['isin']}(Advisor: DIRECT) "
                           f"Registrar : {fund['rta']}")])
        lines.append([(40, "Nominee 1: Test Nominee  Nominee 2:  Nominee 3:")])
        lines.append([(40, "Opening Unit Balance: 0.000")])
        lines += [row_atoms(r) for r in rows]
        lines.append([(40, f"Closing Unit Balance: {Decimal(exp['units']):,.3f}"),
                      (190, f"NAV on {date.fromisoformat(exp['nav_date']).strftime('%d-%b-%Y')}: INR {Decimal(exp['nav']):.4f}"),
                      (330, f"Total Cost Value: {money(Decimal(exp['cost']))}"),
                      (430, f"Market Value on {date.fromisoformat(exp['nav_date']).strftime('%d-%b-%Y')}: INR "
                            f"{money(Decimal(exp['value']))}")])
        lines.append([(40, "Entry Load - NIL. Exit Load - as per the scheme information document.")])
    return lines


def pdf_escape(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path, pages):
    objs = []

    def add(body):
        objs.append(body)
        return len(objs)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    pages_id = len(objs) + 1 + 2 * len(pages)            # placeholder index computed below
    page_ids = []
    content_ids = []
    for atoms in pages:
        stream = "".join(f"BT /F1 {size} Tf {x:.2f} {y:.2f} Td ({pdf_escape(t)}) Tj ET\n" for x, y, t, size in atoms)
        data = stream.encode("cp1252")
        content_ids.append(add(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"))
        page_ids.append(add(b""))                        # filled after we know the Pages id
    pages_id = add(b"")
    for pid, cid in zip(page_ids, content_ids):
        objs[pid - 1] = (b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                         b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (pages_id, cid, font))
    objs[pages_id - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % p for p in page_ids), len(page_ids))
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, xref)
    path.write_bytes(bytes(out))


def paginate(lines):
    pages, top = [], 800
    page, y = [], top

    def header_block(page, y):
        for hl in HEADER:
            page += [(x, y, t, SIZE) for x, t in hl]
            y -= 9
        return y - 4

    # Page 1: investor block (left), statement title (right), RTA watermark id.
    for i, t in enumerate(INVESTOR):
        page.append((40, y - 11 * i, t, 8))
    page.append((330, y, "Consolidated Account Statement", 10))
    page.append((330, y - 14, f"{STATEMENT_FROM:%d-%b-%Y} To {STATEMENT_TO:%d-%b-%Y}", 8))
    page.append((330, y - 28, "CAMSCASWS-000000000", 6))
    y -= 11 * len(INVESTOR) + 12
    y = header_block(page, y)
    for line in lines:
        if y < 50:
            pages.append(page)
            page, y = [], top
            y = header_block(page, y)
        page += [(x, y, t, SIZE) for x, t in line]
        y -= 10
    pages.append(page)
    return pages


def main():
    funds_rows, expected = [], {"pan": FAKE_PAN, "statement_to": STATEMENT_TO.isoformat(), "funds": []}
    for f in FUNDS:
        rows, exp = build_transactions(f)
        funds_rows.append((f, rows, exp))
        expected["funds"].append(exp)
    pages = paginate(build_lines(funds_rows))
    write_pdf(HERE / "sample_cas.pdf", pages)
    (HERE / "sample_cas_expected.json").write_text(json.dumps(expected, indent=1), encoding="utf-8")
    print(f"{len(pages)} pages, {sum(e['transactions'] for e in expected['funds'])} rows; fake PAN {FAKE_PAN}")


if __name__ == "__main__":
    main()
