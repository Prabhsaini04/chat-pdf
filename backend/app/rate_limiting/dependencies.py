"""FastAPI dependencies for rate limiting (ENG-CPD-007).

PROVISIONAL thresholds — marked explicitly. All numbers below are
engineering placeholders pending ENG-CPD-020's Locust concurrency sweep
against the real pipeline. Do not read these as benchmark-validated figures.
"""

import uuid

import redis
from fastapi import Depends

from app.auth.dependencies import get_current_account
from app.auth.models import Account
from app.config import settings
from app.rate_limiting.limiter import (
    ConcurrencyLimiter,
    RateLimit,
    SlidingWindowRateLimiter,
)


def get_redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def get_sliding_limiter(r: redis.Redis = Depends(get_redis_client)) -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(r)


def get_concurrency_limiter(
    r: redis.Redis = Depends(get_redis_client),
) -> ConcurrencyLimiter:
    # PROVISIONAL timeout: 180s = 2× the ~90s answer latency target, so a
    # crash/missed release does not permanently block future questions.
    return ConcurrencyLimiter(r, timeout_seconds=180)


# ---------------------------------------------------------------------------
# PROVISIONAL rate-limit thresholds
# (ENG-CPD-020 replaces these with benchmark-derived values)
# ---------------------------------------------------------------------------

# PROVISIONAL: 1 in-flight question per account at a time.
# Given ~90s CPU-only latency (REQ-003/OQ-9), two simultaneous questions
# from the same account almost certainly indicate a double-submit or an
# automation abuse rather than intentional concurrent use. Keeps the
# worker-llm queue from being monopolised by a single account.
QUESTION_MAX_CONCURRENT = 1  # PROVISIONAL — pending ENG-CPD-020

# PROVISIONAL: 10 uploads per hour per account.
# Upload is I/O-bound (worker-io, not worker-llm), so the threshold is
# more generous than the question limit. Chosen as a reasonable ceiling
# for a single human user; adjust once load data exists.
UPLOAD_RATE_LIMIT = RateLimit(max_requests=10, window_seconds=3600)  # PROVISIONAL


def check_upload_rate_limit(
    account: Account = Depends(get_current_account),
    limiter: SlidingWindowRateLimiter = Depends(get_sliding_limiter),
) -> None:
    """FastAPI dependency — apply to `POST /documents`."""
    limiter.check(f"rl:upload:{account.id}", UPLOAD_RATE_LIMIT)


def _question_concurrency_key(account_id: uuid.UUID) -> str:
    return f"cl:question:{account_id}"


def check_question_concurrency(
    account: Account = Depends(get_current_account),
    limiter: ConcurrencyLimiter = Depends(get_concurrency_limiter),
) -> None:
    """FastAPI dependency — apply to `POST /documents/{id}/questions`.

    Usage: ENG-CPD-011 applies this as a Depends(); on route exit (normal or
    error) it must call `release_question_concurrency(account.id, limiter)`.
    The route should use a try/finally around the actual work, e.g.:

        @router.post("/documents/{document_id}/questions")
        def ask_question(
            ...,
            _: None = Depends(check_question_concurrency),
            limiter: ConcurrencyLimiter = Depends(get_concurrency_limiter),
            account: Account = Depends(get_current_account),
        ):
            try:
                # ... LLM call ...
            finally:
                limiter.release(_question_concurrency_key(account.id))
    """
    limiter.acquire(_question_concurrency_key(account.id), QUESTION_MAX_CONCURRENT)
