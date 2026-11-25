from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.exceptions import AccountLockedError, DuplicateEmailError, InvalidCredentialsError
from app.auth.models import Account, AccountSession, AuthEvent
from app.auth.security import (
    generate_session_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.config import settings


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _log_auth_event(db: Session, account_id, event_type: str) -> None:
    db.add(AuthEvent(account_id=account_id, event_type=event_type))


def signup(db: Session, email: str, password: str) -> Account:
    account = Account(email=email, password_hash=hash_password(password), status="active")
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateEmailError() from exc
    db.commit()
    db.refresh(account)
    return account


def _recent_failed_attempt_count(db: Session, account_id) -> int:
    window_start = _utcnow() - timedelta(minutes=settings.lockout_window_minutes)
    stmt = select(func.count()).where(
        AuthEvent.account_id == account_id,
        AuthEvent.event_type == "login_failure",
        AuthEvent.created_at >= window_start,
    )
    return db.execute(stmt).scalar_one()


def authenticate(db: Session, email: str, password: str, user_agent: str | None) -> AccountSession:
    """Raises InvalidCredentialsError for a nonexistent email, a wrong
    password, or a disabled account — the router maps all of these to the
    same generic response (no "email not found" vs "wrong password"
    distinction, ENG-CPD-005 acceptance criteria)."""
    account = db.execute(select(Account).where(Account.email == email)).scalar_one_or_none()

    if account is None:
        # Dummy hash verify keeps response shape consistent regardless of
        # whether the account exists. This narrows, but does not eliminate,
        # the timing side-channel the ENG-CPD-005 task record flags as an
        # accepted residual risk for MVP.
        verify_dummy_password(password)
        _log_auth_event(db, None, "login_failure")
        db.commit()
        raise InvalidCredentialsError()

    if account.status != "active":
        _log_auth_event(db, account.id, "login_failure")
        db.commit()
        raise InvalidCredentialsError()

    if _recent_failed_attempt_count(db, account.id) >= settings.max_failed_login_attempts:
        raise AccountLockedError()

    if not verify_password(password, account.password_hash):
        _log_auth_event(db, account.id, "login_failure")
        db.commit()
        raise InvalidCredentialsError()

    session = AccountSession(
        id=generate_session_token(),
        account_id=account.id,
        expires_at=_utcnow() + timedelta(days=settings.session_ttl_days),
        user_agent=user_agent,
    )
    db.add(session)
    _log_auth_event(db, account.id, "login_success")
    db.commit()
    db.refresh(session)
    return session


def get_valid_session(db: Session, token: str) -> AccountSession | None:
    session = db.get(AccountSession, token)
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    if session.expires_at <= _utcnow():
        return None
    session.last_seen_at = _utcnow()
    db.commit()
    return session


def revoke_session(db: Session, token: str) -> None:
    session = db.get(AccountSession, token)
    if session is None or session.revoked_at is not None:
        return
    session.revoked_at = _utcnow()
    _log_auth_event(db, session.account_id, "logout")
    db.commit()
