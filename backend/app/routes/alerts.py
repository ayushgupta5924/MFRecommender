"""Portfolio alert endpoints: the scheduled run, one-click unsubscribe, and the account switch."""
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.tables import User, utcnow
from app.services import alerts
from app.services.auth import accounts_enabled, current_user
from app.services.email import send_email
from app.services.review import Reviewer

router = APIRouter()
reviewer = Reviewer()


@router.post("/internal/alerts/run")
def run_alerts(dry_run: bool = False, x_alerts_token: str = Header(default=""), db: Session = Depends(get_db)):
    """Called by the scheduled GitHub Action with the shared ALERTS_TOKEN."""
    expected = os.getenv("ALERTS_TOKEN", "")
    if not expected or not hmac.compare_digest(expected, x_alerts_token):
        raise HTTPException(404, "Not found")
    if not accounts_enabled():
        return {"skipped": "accounts are not enabled"}
    return alerts.run(db, reviewer, send_email, utcnow(), dry_run=dry_run)


_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title></head><body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f0f2f5;
margin:0;padding:60px 16px;text-align:center;color:#222"><div style="max-width:420px;margin:auto;background:#fff;
border-radius:14px;padding:28px"><div style="font-size:40px">{icon}</div><h2>{title}</h2><p style="color:#555">{text}</p>
<p><a href="{site}/account" style="color:#1976d2;font-weight:600">Manage alerts in your account</a></p></div></body></html>"""


def _unsubscribe(u: int, t: str, db: Session) -> HTMLResponse:
    user = db.get(User, u)
    if not user or not alerts.valid_unsubscribe(u, t):
        return HTMLResponse(_PAGE.format(icon="⚠️", title="This link isn't valid", site=alerts.SITE_URL,
                                         text="It may be incomplete. You can turn alerts off from your account."),
                            status_code=400)
    user.alerts_enabled = False
    db.commit()
    return HTMLResponse(_PAGE.format(icon="✅", title="You won't get portfolio alerts any more", site=alerts.SITE_URL,
                                     text="You can switch them back on from your account at any time."))


@router.get("/alerts/unsubscribe", response_class=HTMLResponse)
def unsubscribe_link(u: int = Query(...), t: str = Query(""), db: Session = Depends(get_db)):
    return _unsubscribe(u, t, db)


@router.post("/alerts/unsubscribe", response_class=HTMLResponse)
def unsubscribe_one_click(u: int = Query(...), t: str = Query(""), db: Session = Depends(get_db)):
    """RFC 8058 one-click unsubscribe, used by Gmail's and Outlook's own unsubscribe buttons."""
    return _unsubscribe(u, t, db)


class AlertSetting(BaseModel):
    enabled: bool


@router.put("/account/alerts")
def set_alerts(body: AlertSetting, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.alerts_enabled = body.enabled
    db.commit()
    return {"alerts_enabled": user.alerts_enabled}
