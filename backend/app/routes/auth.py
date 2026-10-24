"""Sign up, log in and account endpoints. Login is always by an emailed one-time code."""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.tables import AuthSession, OtpCode, Portfolio, SavedPlan, User
from app.services import auth
from app.services.email import EmailNotConfigured, send_otp

logger = logging.getLogger(__name__)
router = APIRouter()


class SignupStart(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    email: str


class LoginStart(BaseModel):
    email: str


class Verify(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)
    purpose: Literal["signup", "login"]


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, full_name=user.full_name)


def _send(db: Session, request: Request, email: str, purpose: str, full_name: Optional[str] = None) -> dict:
    code = auth.issue_code(db, email, purpose, auth.client_ip(request), full_name)
    try:
        send_otp(email, code, purpose, auth.OTP_MINUTES)
    except EmailNotConfigured:
        raise HTTPException(503, "Email login isn't available yet. Please try again later.")
    except Exception:
        logger.exception("Sending the %s code failed", purpose)
        raise HTTPException(502, "We couldn't send the email. Check the address and try again.")
    return {"sent": True, "email": email, "expires_in_minutes": auth.OTP_MINUTES,
            "resend_after_seconds": auth.RESEND_COOLDOWN_SECONDS}


@router.post("/auth/signup/start")
def signup_start(body: SignupStart, request: Request, db: Session = Depends(get_db)):
    email = auth.normalise_email(body.email)
    name = " ".join(body.full_name.split())
    if len(name) < 2:
        raise HTTPException(422, "Enter your full name.")
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(409, "An account with this email already exists. Log in instead.")
    return _send(db, request, email, "signup", name)


@router.post("/auth/login/start")
def login_start(body: LoginStart, request: Request, db: Session = Depends(get_db)):
    email = auth.normalise_email(body.email)
    if not db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(404, "No account uses this email. Create one instead.")
    return _send(db, request, email, "login")


@router.post("/auth/verify", response_model=UserOut)
def verify(body: Verify, response: Response, db: Session = Depends(get_db)):
    email = auth.normalise_email(body.email)
    otp = auth.verify_code(db, email, body.purpose, body.code)
    user = db.scalars(select(User).where(User.email == email)).first()
    if body.purpose == "signup":
        if user is None:
            user = User(email=email, full_name=otp.full_name or email.split("@")[0])
            db.add(user)
            db.commit()
    elif user is None:
        raise HTTPException(404, "No account uses this email. Create one instead.")
    token = auth.create_session(db, user)
    response.set_cookie(value=token, max_age=auth.SESSION_DAYS * 86400, **auth.cookie_settings())
    return _user_out(user)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(auth.current_user)):
    return _user_out(user)


@router.post("/auth/logout")
def logout(response: Response, db: Session = Depends(get_db),
           token: Optional[str] = Cookie(default=None, alias=auth.COOKIE_NAME)):
    auth.end_session(db, token)
    settings = auth.cookie_settings()
    response.delete_cookie(settings["key"], path="/", secure=settings["secure"], httponly=True, samesite="lax")
    return {"ok": True}


@router.delete("/account")
def delete_account(response: Response, user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    """Permanently delete the account and everything stored for it."""
    for table in (SavedPlan, Portfolio, AuthSession):
        db.execute(delete(table).where(table.user_id == user.id))
    db.execute(delete(OtpCode).where(OtpCode.email == user.email))
    db.delete(user)
    db.commit()
    settings = auth.cookie_settings()
    response.delete_cookie(settings["key"], path="/", secure=settings["secure"], httponly=True, samesite="lax")
    return {"deleted": True}
