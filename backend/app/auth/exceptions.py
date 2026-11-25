class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    """Covers both 'no such account' and 'wrong password' — the router
    always maps this to the same generic response (no enumeration,
    ENG-CPD-005 acceptance criteria)."""


class AccountLockedError(Exception):
    """Too many recent failed attempts against this account."""
