import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Base


@pytest.fixture(scope="session")
def db_engine():
    """Auth/session tests need a real Postgres (sessions/accounts are
    DB-backed per ADR-CPD-003) — SQLite can't stand in (UUID/pgvector
    types). Set TEST_DATABASE_URL to a real Postgres instance to run these;
    otherwise they're skipped rather than silently reported as passing."""
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL not set — no test database available")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(engine)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"could not reach/initialize test database: {exc}")
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    session_local = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = session_local()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    # TestClient talks to the app over plain http (no TLS test server), so a
    # cookie set with Secure=True would never be sent back by a real
    # browser/HTTP client either — this is production-correct behavior, not
    # a bug, but it means the test environment needs the same relaxation a
    # real non-TLS local-dev deployment would need. Never relax this for the
    # app's own default (app/config.py keeps cookie_secure=True).
    monkeypatch.setattr(settings, "cookie_secure", False)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
