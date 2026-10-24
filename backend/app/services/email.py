"""Sends email through Resend (https://resend.com): login codes and portfolio alerts.

Set RESEND_API_KEY and EMAIL_FROM (an address on a domain verified in Resend,
e.g. "MF Advisor <no-reply@yourdomain.in>"). For local development only,
EMAIL_DEV_MODE=1 logs emails instead of sending them.
"""
import html
import logging
import os
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
BRAND = os.getenv("BRAND_NAME", "MF Advisor")
SITE_URL = os.getenv("SITE_URL", "https://mf-recommender.vercel.app").rstrip("/")


class EmailNotConfigured(RuntimeError):
    pass


def send_email(to: str, subject: str, html_body: str, text_body: str,
               headers: Optional[Dict[str, str]] = None) -> None:
    api_key, sender = os.getenv("RESEND_API_KEY"), os.getenv("EMAIL_FROM")
    if not (api_key and sender):
        if os.getenv("EMAIL_DEV_MODE") == "1":
            logger.warning("EMAIL_DEV_MODE: email to %s: %s\n%s", to, subject, text_body)
            return
        raise EmailNotConfigured("Email sending is not set up yet.")
    payload = {"from": sender, "to": [to], "subject": subject, "html": html_body, "text": text_body}
    if headers:
        payload["headers"] = headers
    resp = requests.post(RESEND_URL, headers={"Authorization": f"Bearer {api_key}"}, json=payload, timeout=15)
    if resp.status_code >= 300:
        logger.error("Resend rejected the email (%s): %s", resp.status_code, resp.text[:300])
        raise RuntimeError("Could not send the email.")


def _otp_body(code: str, purpose: str, minutes: int) -> str:
    action = "finish creating your account" if purpose == "signup" else "log in"
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:420px;margin:auto;color:#222">
  <h2 style="color:#1976d2;margin-bottom:4px">{html.escape(BRAND)}</h2>
  <p>Use this code to {action}:</p>
  <p style="font-size:32px;font-weight:800;letter-spacing:6px;margin:16px 0">{code}</p>
  <p style="color:#666;font-size:13px">It expires in {minutes} minutes. If you didn't ask for it, you can ignore
  this email. We will never ask you to share this code.</p>
</div>"""


def send_welcome(to: str, name: str) -> None:
    """Sent once at sign-up. SEBI asks advisers to share the Investor Charter as part of onboarding."""
    first = html.escape(name.split()[0])
    charter = f"{SITE_URL}/investor-charter"
    body = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:auto;color:#222">
  <h2 style="color:#1976d2;margin-bottom:4px">{html.escape(BRAND)}</h2>
  <p>Hi {first}, your account is ready.</p>
  <p>Before you act on any advice from us, please read our
     <a href="{charter}" style="color:#1976d2;font-weight:600">Investor Charter</a>. It sets out what we do for you,
     your rights as an investor, and how to raise a complaint, as prescribed by SEBI.</p>
  <p style="color:#666;font-size:13px">Mutual fund investments are subject to market risks. Read all scheme-related
     documents carefully.</p>
</div>"""
    text = (f"Hi {name.split()[0]}, your {BRAND} account is ready.\n\nBefore you act on any advice from us, please "
            f"read our Investor Charter: {charter}\nIt sets out what we do for you, your rights as an investor, and how "
            "to raise a complaint, as prescribed by SEBI.")
    send_email(to, f"Welcome to {BRAND}: your Investor Charter", body, text)


def send_otp(to: str, code: str, purpose: str, minutes: int) -> None:
    send_email(to, f"{code} is your {BRAND} code", _otp_body(code, purpose, minutes),
               f"Your {BRAND} code is {code}. It expires in {minutes} minutes.")
