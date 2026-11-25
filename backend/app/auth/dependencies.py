from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.models import Account
from app.auth.service import get_valid_session
from app.db import get_db

SESSION_COOKIE_NAME = "session_id"


def get_current_account(request: Request, db: Session = Depends(get_db)) -> Account:
    """The only source of `account_id` for every protected route
    (ENG-CPD-008 onward). Reads the session cookie only — never a request
    body/query/path parameter (threat-model mitigation #1, REQ-007)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = get_valid_session(db, token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    account = db.get(Account, session.account_id)
    if account is None or account.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # Stashed for routes that need the session token itself (e.g. logout),
    # so they don't have to re-read/re-validate the cookie a second time.
    request.state.session_token = session.id

    return account
