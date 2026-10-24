"""Sends one-time login codes by email through Resend (https://resend.com).

Set RESEND_API_KEY and EMAIL_FROM (an address on a domain verified in Resend,
e.g. "MF Advisor <no-reply@yourdomain.in>"). For local development only,
EMAIL_DEV_MODE=1 prints codes to the server log instead of sending them.
"""
import html
import logging
import os

import requests

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
BRAND = os.getenv("BRAND_NAME", "MF Advisor")


class EmailNotConfigured(RuntimeError):
    pass


def _body(code: str, purpose: str, minutes: int) -> str:
    action = "finish creating your account" if purpose == "signup" else "log in"
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:420px;margin:auto;color:#222">
  <h2 style="color:#1976d2;margin-bottom:4px">{html.escape(BRAND)}</h2>
  <p>Use this code to {action}:</p>
  <p style="font-size:32px;font-weight:800;letter-spacing:6px;margin:16px 0">{code}</p>
  <p style="color:#666;font-size:13px">It expires in {minutes} minutes. If you didn't ask for it, you can ignore
  this email. We will never ask you to share this code.</p>
</div>"""


def send_otp(to: str, code: str, purpose: str, minutes: int) -> None:
    api_key, sender = os.getenv("RESEND_API_KEY"), os.getenv("EMAIL_FROM")
    if not (api_key and sender):
        if os.getenv("EMAIL_DEV_MODE") == "1":
            logger.warning("EMAIL_DEV_MODE: %s code for %s is %s", purpose, to, code)
            return
        raise EmailNotConfigured("Email sending is not set up yet.")
    resp = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": sender,
            "to": [to],
            "subject": f"{code} is your {BRAND} code",
            "html": _body(code, purpose, minutes),
            "text": f"Your {BRAND} code is {code}. It expires in {minutes} minutes.",
        },
        timeout=15,
    )
    if resp.status_code >= 300:
        logger.error("Resend rejected the email (%s): %s", resp.status_code, resp.text[:300])
        raise RuntimeError("Could not send the email.")
