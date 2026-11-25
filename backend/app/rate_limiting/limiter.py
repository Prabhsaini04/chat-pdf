"""Redis-backed rate limiting for ENG-CPD-007.

Two primitives:
  - SlidingWindowRateLimiter  — sliding-window counter using a Redis sorted
    set. Appropriate for per-account upload rate (e.g. 10 uploads / hour).
  - ConcurrencyLimiter        — in-flight counter (INCR / DECR) around a
    Redis key. Appropriate for the question endpoint's "at most 1 in-flight
    question per account" constraint, given ~90s CPU-only answer latency.

All numeric thresholds in this file are PROVISIONAL — pending ENG-CPD-020's
Locust concurrency sweep against the real pipeline. They are stored in
`config.py` / `dependencies.py` as clearly-named constants, not buried here.
"""

import time
import uuid
from dataclasses import dataclass

from redis import Redis

from app.rate_limiting.exceptions import RateLimitExceeded


@dataclass(frozen=True)
class RateLimit:
    max_requests: int   # allowed calls in `window_seconds`
    window_seconds: int


class SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter backed by a Redis sorted set.

    Each call to `check` atomically:
      1. Removes entries older than the window.
      2. Counts remaining entries.
      3. If under the limit, adds a new entry and returns.
      4. If at or over the limit, raises `RateLimitExceeded`.

    Key format: callers supply `key`; suggested shape:
        f"rl:upload:{account_id}"
    """

    def __init__(self, redis_client: Redis) -> None:
        self._r = redis_client

    def check(self, key: str, limit: RateLimit) -> None:
        now = time.time()
        window_start = now - limit.window_seconds
        member = str(uuid.uuid4())

        pipe = self._r.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.execute()

        # Read current count in a second pipeline so the ZADD is conditional.
        count = self._r.zcard(key)
        if count >= limit.max_requests:
            raise RateLimitExceeded(
                retry_after=limit.window_seconds,
                detail="Too many requests — please try again later.",
            )

        pipe2 = self._r.pipeline(transaction=True)
        pipe2.zadd(key, {member: now})
        pipe2.expire(key, limit.window_seconds + 1)
        pipe2.execute()


class ConcurrencyLimiter:
    """In-flight concurrency limiter backed by a Redis counter.

    Increments a counter on `acquire` and decrements it on `release`.
    If the counter would exceed `max_concurrent`, raises `RateLimitExceeded`
    without touching the counter.

    Callers MUST call `release` in a try/finally block; a TTL is set so a
    crash or missed `release` does not permanently block future requests
    (TTL = `timeout_seconds`, which should be longer than the slowest
    expected operation — e.g. 180s for a ~90s question endpoint).

    Key format: suggested shape: f"cl:question:{account_id}"
    """

    def __init__(self, redis_client: Redis, timeout_seconds: int = 180) -> None:
        self._r = redis_client
        self._timeout = timeout_seconds

    def acquire(self, key: str, max_concurrent: int) -> None:
        new_count = self._r.incr(key)
        self._r.expire(key, self._timeout)
        if new_count > max_concurrent:
            # Undo the increment — this account is already at the limit.
            self._r.decr(key)
            raise RateLimitExceeded(
                retry_after=self._timeout,
                detail=(
                    "You already have a question in progress. "
                    "Please wait for it to complete before asking another."
                ),
            )

    def release(self, key: str) -> None:
        # Guard against going below 0 on a double-release or a TTL expiry
        # that already reset the counter.
        current = self._r.get(key)
        if current is not None and int(current) > 0:
            self._r.decr(key)
