import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

SESSION_TOKEN_BYTES = 32  # per ADR-CPD-003: secrets.token_urlsafe(32), not hand-rolled crypto

# A real, validly-encoded argon2id hash of a fixed dummy password — computed
# once at import time, used by the login path when no account exists so a
# constant-shape verify still runs (partial timing-side-channel mitigation,
# ENG-CPD-005's accepted residual risk). Must be a real hash: argon2 raises
# on a malformed/placeholder string instead of just returning False.
_DUMMY_HASH = PasswordHasher().hash("dummy-password-for-constant-time-verify")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def verify_dummy_password(password: str) -> None:
    """Call on the 'no such account' login path so the response shape/timing
    doesn't trivially differ from a real wrong-password attempt."""
    verify_password(password, _DUMMY_HASH)


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)
