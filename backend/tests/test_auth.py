import uuid
from datetime import UTC, datetime, timedelta

from app.auth.models import Account, AccountSession
from app.auth.security import hash_password
from app.config import settings

EMAIL = "test@example.com"
PASSWORD = "correct-horse-battery-staple"


def _signup(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/signup", json={"email": email, "password": password})


def test_signup_creates_account(client):
    resp = _signup(client)
    assert resp.status_code == 201
    assert uuid.UUID(resp.json()["account_id"])


def test_signup_duplicate_email_rejected(client):
    _signup(client)
    resp = _signup(client)
    assert resp.status_code == 409


def test_signup_rejects_short_password(client):
    resp = _signup(client, password="short")
    assert resp.status_code == 422


def test_login_success_sets_session_cookie(client):
    _signup(client)
    resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    assert "session_id" in resp.cookies


def test_login_wrong_password_generic_401(client):
    _signup(client)
    resp = client.post("/auth/login", json={"email": EMAIL, "password": "wrong-password"})
    assert resp.status_code == 401


def test_login_nonexistent_email_same_generic_401(client):
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert resp.status_code == 401
    # Same response shape as a wrong password — no "email not found" distinction.
    assert resp.json()["detail"] == "Invalid credentials."


def test_me_requires_session(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_account_after_login(client):
    signup_resp = _signup(client)
    account_id = signup_resp.json()["account_id"]
    client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["account_id"] == account_id
    assert resp.json()["email"] == EMAIL


def test_me_ignores_client_supplied_account_id(client):
    """get_current_account must never be influenced by a client-supplied
    account_id-shaped parameter (ENG-CPD-005 explicit negative test)."""
    signup_resp = _signup(client)
    real_account_id = signup_resp.json()["account_id"]
    client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})

    spoofed = str(uuid.uuid4())
    resp = client.get(f"/auth/me?account_id={spoofed}")

    assert resp.status_code == 200
    assert resp.json()["account_id"] == real_account_id
    assert resp.json()["account_id"] != spoofed


def test_logout_revokes_session(client, db_session):
    _signup(client)
    client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert client.get("/auth/me").status_code == 200

    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == 204

    assert client.get("/auth/me").status_code == 401


def test_expired_session_rejected(client, db_session):
    account = Account(email=EMAIL, password_hash=hash_password(PASSWORD), status="active")
    db_session.add(account)
    db_session.commit()

    expired = AccountSession(
        id="expired-token",
        account_id=account.id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(expired)
    db_session.commit()

    client.cookies.set("session_id", "expired-token")
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_revoked_session_rejected(client, db_session):
    account = Account(email=EMAIL, password_hash=hash_password(PASSWORD), status="active")
    db_session.add(account)
    db_session.commit()

    revoked = AccountSession(
        id="revoked-token",
        account_id=account.id,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=datetime.now(UTC),
    )
    db_session.add(revoked)
    db_session.commit()

    client.cookies.set("session_id", "revoked-token")
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_missing_cookie_rejected(client):
    client.cookies.set("session_id", "not-a-real-token")
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_repeated_failed_logins_lock_out_account(client, monkeypatch):
    monkeypatch.setattr(settings, "max_failed_login_attempts", 2)
    _signup(client)

    for _ in range(2):
        resp = client.post("/auth/login", json={"email": EMAIL, "password": "wrong-password"})
        assert resp.status_code == 401

    # Correct password should now also be rejected — proves this is a
    # lockout, not just repeated wrong-password failures (which would
    # already be 401 regardless of lockout logic).
    resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 401
