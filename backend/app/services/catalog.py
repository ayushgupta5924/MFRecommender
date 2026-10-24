"""Fund buckets the engine allocates to, and how AMFI categories map onto them.

AMFI publishes categories under both the older SEBI names ("Debt Scheme - Short
Duration Fund") and the newer ones ("Income/Debt Oriented Schemes - Short Term
Fund"), so each bucket matches on keywords rather than exact strings.
"""
import re
from dataclasses import dataclass
from typing import Optional, Pattern


@dataclass(frozen=True)
class Bucket:
    key: str
    label: str
    sleeve: str                 # "equity" | "hybrid" | "debt"
    risk_level: str             # shown to the user: "Low" | "Moderate" | "High" | "Very High"
    category_re: Pattern
    min_years: float            # minimum track record to be ranked
    role: str                   # one line on why this bucket is in a portfolio
    name_re: Optional[Pattern] = None
    exclude_category_re: Optional[Pattern] = None
    lock_in_years: int = 0


def _re(pattern: str) -> Pattern:
    return re.compile(pattern, re.IGNORECASE)


BUCKETS = {
    b.key: b for b in [
        # ── Equity ──────────────────────────────────────────────────────────
        Bucket("index_large", "Nifty 50 Index", "equity", "High",
               _re(r"index fund"), 3,
               "Low-cost core holding that simply tracks India's 50 largest companies.",
               name_re=_re(r"^(?!.*\b(next|etf|fof|elss|tax|debt|sdl|gilt)\b).*(nifty\s*50\b(?!\s*(equal|value|quality|alpha|momentum|low|shariah|arbitrage))|sensex)"),
               exclude_category_re=_re(r"debt|hybrid|etf")),
        Bucket("large_cap", "Large Cap", "equity", "High",
               _re(r"(?<!& )\blarge cap fund"), 3,
               "Actively managed large companies for steadier equity growth.",
               exclude_category_re=_re(r"large & mid")),
        Bucket("flexi_cap", "Flexi Cap", "equity", "Very High",
               _re(r"flexi cap"), 3,
               "Fund manager moves freely across large, mid and small companies."),
        Bucket("large_mid", "Large & Mid Cap", "equity", "Very High",
               _re(r"large & mid cap"), 3,
               "At least 35% each in large and mid-sized companies."),
        Bucket("mid_cap", "Mid Cap", "equity", "Very High",
               _re(r"\bmid cap fund"), 3,
               "Mid-sized companies: higher growth potential with deeper falls.",
               exclude_category_re=_re(r"large & mid")),
        Bucket("small_cap", "Small Cap", "equity", "Very High",
               _re(r"small cap"), 3,
               "Smaller companies: the most volatile equity sleeve, for long horizons only."),
        Bucket("elss", "ELSS (Tax Saver)", "equity", "Very High",
               _re(r"\belss\b"), 3,
               "Equity fund with a 3-year lock-in that qualifies for Section 80C (old tax regime).",
               exclude_category_re=_re(r"index"), lock_in_years=3),
        # ── Hybrid ──────────────────────────────────────────────────────────
        Bucket("balanced_advantage", "Balanced Advantage", "hybrid", "Moderate",
               _re(r"balanced advantage|dynamic asset allocation"), 3,
               "Shifts between equity and debt by market valuation to soften falls."),
        Bucket("aggressive_hybrid", "Aggressive Hybrid", "hybrid", "High",
               _re(r"aggressive hybrid"), 3,
               "65-80% equity with a debt cushion."),
        Bucket("multi_asset", "Multi Asset", "hybrid", "High",
               _re(r"multi asset"), 3,
               "Equity, debt and gold in one fund for diversification."),
        Bucket("conservative_hybrid", "Conservative Hybrid", "hybrid", "Moderate",
               _re(r"conservative hybrid"), 3,
               "Mostly debt with a small equity kicker to beat inflation."),
        # ── Debt ────────────────────────────────────────────────────────────
        Bucket("liquid", "Liquid", "debt", "Low",
               _re(r"liquid fund"), 1,
               "Very short-term money market paper; redeemable in about one working day."),
        Bucket("money_market", "Money Market", "debt", "Low",
               _re(r"money market"), 1,
               "Up to 1-year instruments; a step above liquid funds for money needed within 1-2 years."),
        Bucket("short_duration", "Short Duration", "debt", "Low",
               _re(r"short duration fund|short term fund"), 2,
               "1-3 year bonds; suits money needed in 2-4 years.",
               exclude_category_re=_re(r"ultra")),
        Bucket("corporate_bond", "Corporate Bond", "debt", "Low",
               _re(r"corporate bond"), 2,
               "At least 80% in top-rated (AA+ and above) corporate bonds."),
        Bucket("banking_psu", "Banking & PSU", "debt", "Low",
               _re(r"banking (and|&) psu"), 2,
               "Bonds of banks and public sector companies: high credit quality."),
        Bucket("gilt", "Gilt", "debt", "Moderate",
               _re(r"gilt"), 2,
               "Government securities: no credit risk, but prices move with interest rates."),
    ]
}

# Names that indicate a plan we never want to recommend, whatever the category.
EXCLUDED_NAME_RE = _re(
    r"\bidcw\b|dividend|bonus|segregat|\betf\b|fund of funds?|\bfof\b|interval|fixed maturity|\bfmp\b"
    r"|series|close[d]? ended|unclaimed|institutional|retail plan|super institutional"
)


def bucket_for(category: str, name: str) -> Optional[Bucket]:
    """Return the bucket a scheme belongs to, or None if it is out of scope."""
    if EXCLUDED_NAME_RE.search(name):
        return None
    for b in BUCKETS.values():
        if not b.category_re.search(category):
            continue
        if b.exclude_category_re and b.exclude_category_re.search(category):
            continue
        if b.name_re and not b.name_re.search(name):
            continue
        return b
    return None
