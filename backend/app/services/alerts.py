"""Portfolio alerts: email investors when a fund they hold changes rating.

A scheduled job (see .github/workflows/portfolio-alerts.yml) calls the API every
week. For each investor with alerts on, the portfolio is reviewed against that
night's rankings and compared with the ratings at their last alert. An email
goes out only if something changed, and at most once every MIN_DAYS_BETWEEN
days, so a missed or repeated run never means a missed or duplicate email.
"""
import hashlib
import hmac
import html
import logging
import os
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tables import Portfolio, SavedPlan, User
from app.services.email import BRAND, SITE_URL
from app.services.review import STATUSES, Reviewer, _fmt

logger = logging.getLogger(__name__)

MIN_DAYS_BETWEEN = 25
RANK = ["in_form", "on_track", "off_track", "out_of_form"]
COLORS = {"in_form": ("#e8f5e9", "#2e7d32"), "on_track": ("#e3f2fd", "#1565c0"),
          "off_track": ("#fff3e0", "#e65100"), "out_of_form": ("#ffebee", "#c62828")}


# ── Unsubscribe links ───────────────────────────────────────────────────────

def _secret() -> bytes:
    return (os.getenv("AUTH_SECRET") or "dev-only-secret").encode()


def unsubscribe_token(user_id: int) -> str:
    return hmac.new(_secret(), f"unsubscribe:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def valid_unsubscribe(user_id: int, token: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(user_id), token or "")


def unsubscribe_url(user_id: int) -> str:
    return f"{SITE_URL}/api/alerts/unsubscribe?u={user_id}&t={unsubscribe_token(user_id)}"


# ── What changed ────────────────────────────────────────────────────────────

def ratings(review: dict) -> Dict[str, str]:
    return {h["code"]: h["rating"]["status"] for h in review.get("holdings", [])}


def changes(snapshot: Dict[str, str], review: dict) -> List[dict]:
    """Rated funds whose rating differs from the snapshot, worst news first."""
    out = []
    for h in review.get("holdings", []):
        old, new = snapshot.get(h["code"]), h["rating"]["status"]
        if old in RANK and new in RANK and old != new:
            out.append({**h, "old": old, "new": new, "worse": RANK.index(new) > RANK.index(old)})
    out.sort(key=lambda c: (not c["worse"], -RANK.index(c["new"])))
    return out


# ── Email ───────────────────────────────────────────────────────────────────

def _chip(status: str) -> str:
    bg, fg = COLORS[status]
    return (f'<span style="background:{bg};color:{fg};font-weight:700;font-size:12px;padding:3px 9px;'
            f'border-radius:10px;white-space:nowrap">{STATUSES[status][0]}</span>')


def render(user: User, review: dict, changed: List[dict]) -> tuple:
    """(subject, html, text) for one investor's alert."""
    first = html.escape(user.full_name.split()[0])
    worse = sum(c["worse"] for c in changed)
    n = len(changed)
    subject = (f"{n} of your funds changed rating" if n > 1 else f"{changed[0]['name']} is now rated "
               f"{STATUSES[changed[0]['new']][0]}")
    s = review["summary"]
    good = review["health"].get("good_pct")
    link = f"{SITE_URL}/review"
    unsub = unsubscribe_url(user.id)

    cards = []
    for c in changed:
        alt = c["alternatives"][0] if c.get("alternatives") else None
        alt_line = (f'<div style="font-size:13px;color:#555;margin-top:6px">A better-ranked {html.escape(c["category"])} '
                    f'fund: <b>{html.escape(alt["name"])}</b> (#{alt["rank"]} of {alt["rank_of"]})</div>') if alt else ""
        cards.append(f"""
      <div style="border:1px solid #eee;border-left:4px solid {COLORS[c['new']][1]};border-radius:10px;padding:12px 14px;margin:0 0 12px">
        <div style="font-weight:700;font-size:15px;color:#222">{html.escape(c['name'])}</div>
        <div style="font-size:12px;color:#888;margin:2px 0 8px">{html.escape(c['category'])} · {_fmt(c['value'])}</div>
        <div>{_chip(c['old'])} <span style="color:#999;padding:0 4px">→</span> {_chip(c['new'])}</div>
        <div style="font-size:13px;color:#333;margin-top:8px">{html.escape(c['rating'].get('reason', ''))}
          <b>{html.escape(c['action']['text'])}</b></div>{alt_line}
      </div>""")

    health_line = (f"{good:.0f}% of your rated money is in funds in the top half of their category."
                   if good is not None else "")
    intro = (f"{n} of your funds changed rating since we last wrote"
             + (f", {worse} for the worse." if worse else ", all for the better.")
             if n > 1 else f"One of your funds changed rating since we last wrote.")

    body = f"""\
<div style="background:#f0f2f5;padding:24px 12px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
  <div style="max-width:560px;margin:auto;background:#fff;border-radius:14px;overflow:hidden">
    <div style="background:#1976d2;color:#fff;padding:18px 22px">
      <div style="font-size:18px;font-weight:800">💼 {html.escape(BRAND)}</div>
      <div style="font-size:13px;opacity:.85">Your portfolio check</div>
    </div>
    <div style="padding:22px">
      <p style="margin:0 0 14px;font-size:15px;color:#222">Hi {first},</p>
      <p style="margin:0 0 18px;font-size:15px;color:#333">{intro} Ratings compare each fund with every other fund in
        its category on long-run returns, consistency and how far it fell in bad markets.</p>
      {''.join(cards)}
      <div style="background:#f5f9ff;border-radius:10px;padding:12px 14px;margin:6px 0 18px;font-size:13px;color:#333">
        <b>Your portfolio:</b> {_fmt(s['value'])}{f" · XIRR {s['xirr'] * 100:.1f}% a year" if s.get('xirr') is not None else ""}
        <br>{health_line}
      </div>
      <div style="text-align:center;margin:8px 0 6px">
        <a href="{link}" style="background:#1976d2;color:#fff;text-decoration:none;font-weight:700;padding:12px 26px;border-radius:10px;display:inline-block">See your full review</a>
      </div>
      <p style="font-size:12px;color:#888;margin:18px 0 0">A rating change on its own isn't a reason to sell: check exit load
        and capital gains tax first, and consider moving new SIPs before existing units.</p>
    </div>
    <div style="border-top:1px solid #eee;padding:14px 22px;font-size:11px;color:#999;line-height:1.5">
      You're getting this because you imported your portfolio into {html.escape(BRAND)} and alerts are on.
      <a href="{unsub}" style="color:#888">Stop these emails</a>.<br>
      Mutual fund investments are subject to market risks. Read all scheme-related documents carefully.
      Past performance does not guarantee future returns.
    </div>
  </div>
</div>"""

    lines = [f"Hi {user.full_name.split()[0]},", "", intro, ""]
    for c in changed:
        lines += [f"- {c['name']}: {STATUSES[c['old']][0]} -> {STATUSES[c['new']][0]}. {c['action']['text']}"]
    lines += ["", f"Your portfolio: {_fmt(s['value'])}. {health_line}", f"See your full review: {link}", "",
              f"Stop these emails: {unsub}"]
    return subject, body, "\n".join(lines)


# ── Job ─────────────────────────────────────────────────────────────────────

def _target(db: Session, user_id: int) -> Optional[dict]:
    plan = db.scalars(select(SavedPlan).where(SavedPlan.user_id == user_id)
                      .order_by(SavedPlan.created_at.desc()).limit(1)).first()
    return {"name": plan.name, "asset_mix": plan.result.get("asset_mix")} if plan else None


def run(db: Session, reviewer: Reviewer, send: Callable[..., None], now: datetime, dry_run: bool = False) -> dict:
    counts = {"checked": 0, "baselined": 0, "unchanged": 0, "too_soon": 0, "sent": 0, "failed": 0}
    rows = db.execute(select(User, Portfolio).join(Portfolio, Portfolio.user_id == User.id)
                      .where(User.alerts_enabled.is_(True))).all()
    for user, p in rows:
        if not p.holdings:
            continue
        counts["checked"] += 1
        try:
            review = reviewer.review(p.holdings, _target(db, user.id))
        except Exception:
            logger.exception("Alert review failed for user %s", user.id)
            counts["failed"] += 1
            continue
        current = ratings(review)
        if p.alert_snapshot is None:
            # First run for this portfolio: remember today's ratings and compare from here on.
            p.alert_snapshot = current
            counts["baselined"] += 1
            db.commit()
            continue
        changed = changes(p.alert_snapshot, review)
        # Funds bought or sold since the last alert join or leave the comparison quietly.
        p.alert_snapshot = {code: p.alert_snapshot.get(code, status) for code, status in current.items()}
        if not changed:
            counts["unchanged"] += 1
            db.commit()
            continue
        if p.alerted_at and now - p.alerted_at < timedelta(days=MIN_DAYS_BETWEEN):
            counts["too_soon"] += 1
            db.commit()
            continue
        subject, body, text = render(user, review, changed)
        if dry_run:
            counts["sent"] += 1
            db.rollback()
            continue
        try:
            unsub = unsubscribe_url(user.id)
            send(user.email, subject, body, text,
                 headers={"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})
        except Exception:
            logger.exception("Alert email failed for user %s", user.id)
            counts["failed"] += 1
            db.rollback()
            continue
        p.alert_snapshot, p.alerted_at = current, now
        db.commit()
        counts["sent"] += 1
    return counts
