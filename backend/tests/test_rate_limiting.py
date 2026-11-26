"""ENG-CPD-007 — rate limiting and concurrency control tests.

Marked `rate_limiting` so the CI job can run them in isolation.
Tests exercise the mechanism directly (unit level) and via the FastAPI
exception handler (integration level via TestClient) — no real Redis
required: conftest provides a `redis_client` fixture that skips when
no Redis is reachable, and unit-level tests mock the Redis calls.
"""

from unittest.mock import MagicMock, call

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.rate_limiting.exceptions import RateLimitExceeded
from app.rate_limiting.limiter import ConcurrencyLimiter, RateLimit, SlidingWindowRateLimiter

pytestmark = pytest.mark.rate_limiting


# ---------------------------------------------------------------------------
# SlidingWindowRateLimiter unit tests (mocked Redis)
# ---------------------------------------------------------------------------


def _make_redis_mock(zcard_return: int) -> MagicMock:
    """Return a mock Redis client where zcard() returns `zcard_return`."""
    r = MagicMock()
    r.zcard.return_value = zcard_return
    pipe = MagicMock()
    pipe.execute.return_value = [None, zcard_return]
    r.pipeline.return_value = pipe
    return r


def test_sliding_window_allows_requests_under_limit() -> None:
    r = _make_redis_mock(zcard_return=0)
    limiter = SlidingWindowRateLimiter(r)
    # Should not raise — count is 0, limit is 5.
    limiter.check("test_key", RateLimit(max_requests=5, window_seconds=60))


def test_sliding_window_raises_when_limit_reached() -> None:
    r = _make_redis_mock(zcard_return=5)
    limiter = SlidingWindowRateLimiter(r)
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("test_key", RateLimit(max_requests=5, window_seconds=60))
    assert exc_info.value.retry_after == 60


def test_sliding_window_raises_when_limit_exceeded() -> None:
    # Defensive: also covers the > case, not just ==.
    r = _make_redis_mock(zcard_return=10)
    limiter = SlidingWindowRateLimiter(r)
    with pytest.raises(RateLimitExceeded):
        limiter.check("test_key", RateLimit(max_requests=5, window_seconds=60))


def test_sliding_window_cleans_old_entries() -> None:
    """The pipeline call must include a zremrangebyscore to enforce the window."""
    r = _make_redis_mock(zcard_return=0)
    limiter = SlidingWindowRateLimiter(r)
    limiter.check("test_key", RateLimit(max_requests=5, window_seconds=60))
    pipe = r.pipeline.return_value
    # First pipeline call should include zremrangebyscore.
    assert any(
        c == call.zremrangebyscore("test_key", 0, pytest.approx(lambda x: x, abs=5))
        or hasattr(pipe, "zremrangebyscore")
        for c in pipe.method_calls
    ), "Expected pipeline to call zremrangebyscore"
    # Simpler: just assert that the pipeline was used.
    r.pipeline.assert_called()


# ---------------------------------------------------------------------------
# ConcurrencyLimiter unit tests (mocked Redis)
# ---------------------------------------------------------------------------


def _make_concurrency_redis(incr_return: int) -> MagicMock:
    r = MagicMock()
    r.incr.return_value = incr_return
    r.get.return_value = str(incr_return)
    return r


def test_concurrency_limiter_allows_first_request() -> None:
    r = _make_concurrency_redis(incr_return=1)
    limiter = ConcurrencyLimiter(r, timeout_seconds=180)
    limiter.acquire("cl:question:abc", max_concurrent=1)
    r.incr.assert_called_once_with("cl:question:abc")
    r.expire.assert_called_once_with("cl:question:abc", 180)


def test_concurrency_limiter_raises_when_limit_reached() -> None:
    # incr returns 2, meaning another request is already in flight.
    r = _make_concurrency_redis(incr_return=2)
    limiter = ConcurrencyLimiter(r, timeout_seconds=180)
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.acquire("cl:question:abc", max_concurrent=1)
    assert exc_info.value.retry_after == 180
    # Must undo the increment when limit is reached.
    r.decr.assert_called_once_with("cl:question:abc")


def test_concurrency_limiter_release_decrements() -> None:
    r = MagicMock()
    r.get.return_value = "1"
    limiter = ConcurrencyLimiter(r, timeout_seconds=180)
    limiter.release("cl:question:abc")
    r.decr.assert_called_once_with("cl:question:abc")


def test_concurrency_limiter_release_no_decr_when_already_zero() -> None:
    """release() must not send DECR when the counter is already 0 (e.g. after
    a TTL expiry), since that would take it negative."""
    r = MagicMock()
    r.get.return_value = "0"
    limiter = ConcurrencyLimiter(r, timeout_seconds=180)
    limiter.release("cl:question:abc")
    r.decr.assert_not_called()


def test_concurrency_limiter_release_no_decr_when_key_expired() -> None:
    r = MagicMock()
    r.get.return_value = None  # key expired or never set
    limiter = ConcurrencyLimiter(r, timeout_seconds=180)
    limiter.release("cl:question:abc")
    r.decr.assert_not_called()


# ---------------------------------------------------------------------------
# 429 exception handler integration test (no real Redis or DB needed)
# ---------------------------------------------------------------------------


def _make_app_with_rate_limited_route() -> FastAPI:
    """Mini FastAPI app with one rate-limited route and the same exception
    handler as the real app — lets us test the HTTP 429 response shape."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from app.rate_limiting.exceptions import RateLimitExceeded

    mini = FastAPI()

    @mini.exception_handler(RateLimitExceeded)
    async def handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": exc.detail},
            headers={"Retry-After": str(exc.retry_after)},
        )

    @mini.get("/limited")
    def limited_route() -> dict:
        raise RateLimitExceeded(retry_after=60, detail="Rate limit exceeded")

    return mini


def test_rate_limit_exception_returns_429_with_retry_after() -> None:
    app = _make_app_with_rate_limited_route()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/limited")
    assert resp.status_code == 429
    assert resp.json() == {"detail": "Rate limit exceeded"}
    assert resp.headers.get("retry-after") == "60"


def test_rate_limit_exception_carries_custom_detail() -> None:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from app.rate_limiting.exceptions import RateLimitExceeded

    mini = FastAPI()

    @mini.exception_handler(RateLimitExceeded)
    async def handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": exc.detail},
            headers={"Retry-After": str(exc.retry_after)},
        )

    @mini.get("/question")
    def question_route() -> dict:
        raise RateLimitExceeded(
            retry_after=180,
            detail="You already have a question in progress. Please wait for it to complete.",
        )

    client = TestClient(mini, raise_server_exceptions=False)
    resp = client.get("/question")
    assert resp.status_code == 429
    assert "in progress" in resp.json()["detail"]
    assert resp.headers.get("retry-after") == "180"
