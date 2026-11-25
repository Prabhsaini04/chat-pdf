from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import SESSION_COOKIE_NAME, get_current_account
from app.auth.exceptions import AccountLockedError, DuplicateEmailError, InvalidCredentialsError
from app.auth.models import Account
from app.auth.schemas import AccountOut, LoginRequest, SignupRequest, SignupResponse
from app.auth.service import authenticate, revoke_session, signup
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=SignupResponse)
def signup_route(body: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    try:
        account = signup(db, body.email, body.password)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None
    return SignupResponse(account_id=account.id)


@router.post("/login", status_code=status.HTTP_200_OK)
def login_route(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> dict:
    user_agent = request.headers.get("user-agent")
    try:
        session = authenticate(db, body.email, body.password, user_agent)
    except (InvalidCredentialsError, AccountLockedError):
        # Same generic response for "no such account", "wrong password",
        # and "locked out" — no distinguishing detail, per acceptance
        # criteria (avoids giving an attacker a free oracle for which case
        # occurred).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        ) from None
    _set_session_cookie(response, session.id)
    return {"status": "ok"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_route(
    request: Request,
    response: Response,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> None:
    revoke_session(db, request.state.session_token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=AccountOut)
def me_route(account: Account = Depends(get_current_account)) -> AccountOut:
    return AccountOut(account_id=account.id, email=account.email)
