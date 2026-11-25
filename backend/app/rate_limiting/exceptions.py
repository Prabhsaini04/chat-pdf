class RateLimitExceeded(Exception):
    """Raised when a per-account rate or concurrency limit is hit.

    `retry_after` is a hint in seconds (not a guarantee — provisional thresholds
    pending ENG-CPD-020 Locust benchmark data).
    """

    def __init__(self, retry_after: int, detail: str = "Rate limit exceeded") -> None:
        self.retry_after = retry_after
        self.detail = detail
        super().__init__(detail)
