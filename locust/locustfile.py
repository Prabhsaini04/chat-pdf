"""ENG-CPD-007 — Locust load scenario for rate-limit and concurrency testing.

Confirmed tool: Locust (Human Owner, 2026-11-25; ENG-CPD-000-implementation-plan.md §9).

Purpose
-------
Two tasks designed to exercise ENG-CPD-007's rate-limit mechanism under
sustained/concurrent load, and to feed ENG-CPD-020's concurrency sweep
(which produces the validated threshold numbers that replace the PROVISIONAL
placeholders in `rate_limiting/dependencies.py`).

Usage
-----
Run against a live stack (docker compose up from infrastructure/):

    locust -f locust/locustfile.py --host http://localhost:8000 \\
        --users 10 --spawn-rate 2 --run-time 60s --headless

Endpoints targeted
------------------
- POST /auth/signup   — creates a unique account per virtual user
- POST /auth/login    — obtains a session cookie
- POST /documents     — upload rate-limit target (ENG-CPD-008, not yet built)
- POST /documents/{id}/questions  — concurrency-limit target (ENG-CPD-011,
                                      not yet built)

NOTE: the document upload and question endpoints do not exist yet (ENG-CPD-008/011).
The tasks below are STUBS that will return 404 until those tasks are merged.
They are written now so ENG-CPD-020 can run them against the real pipeline
without needing to revisit this file. Each stub logs the response code, so
running this scenario pre-ENG-CPD-008/011 produces "404" evidence that the
stubs are wired but the endpoints don't exist yet — not a test failure.

Threshold validation target
---------------------------
A scenario is considered to validate ENG-CPD-007's thresholds when:
  - Sustained load at USERS concurrent virtual users produces 429s on the
    rate-limited endpoints at the expected rate.
  - The 95th-percentile answer latency measured here is ≤ ~90s (REQ-003).
  - 429 responses carry a `Retry-After` header with the provisional value.

The numeric thresholds themselves (QUESTION_MAX_CONCURRENT, UPLOAD_RATE_LIMIT)
are PROVISIONAL until ENG-CPD-020 runs this scenario and reports back.
"""

import uuid

from locust import HttpUser, between, task


class ChatPdfUser(HttpUser):
    wait_time = between(1, 5)

    # Set by on_start; shared state within a single virtual user.
    session_cookie: str | None = None
    document_id: str | None = None

    def on_start(self) -> None:
        """Sign up and log in once per virtual user."""
        email = f"loadtest-{uuid.uuid4()}@example.invalid"
        password = "correct-horse-battery-staple"

        resp = self.client.post(
            "/auth/signup",
            json={"email": email, "password": password},
            name="/auth/signup",
        )
        if resp.status_code != 201:
            # signup failed — virtual user has nothing to do.
            return

        resp = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
            name="/auth/login",
        )
        if resp.status_code != 200:
            return
        # Session cookie is set by the server; httpx/requests propagates it.
        # Store it explicitly in case we need to clear it on logout.
        self.session_cookie = resp.cookies.get("session_id")

    @task(1)
    def upload_document(self) -> None:
        """POST /documents — exercises the per-account upload rate limit.

        STUB: endpoint not yet built (ENG-CPD-008). Will return 404 until
        that task merges. The 404 is recorded in Locust's stats, not treated
        as a Locust failure, so this scenario stays green even pre-ENG-CPD-008.

        Target behavior once the endpoint exists:
          - Requests within the UPLOAD_RATE_LIMIT window → 200/202.
          - Requests beyond the limit → 429 with Retry-After header.
        """
        # Minimal 1-byte fake PDF — real validation happens in ENG-CPD-008.
        resp = self.client.post(
            "/documents",
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            name="/documents [upload]",
        )
        # 404 expected until ENG-CPD-008 merges; 429 expected under load
        # once it does.  Any other 5xx is a genuine signal.
        if resp.status_code not in (200, 202, 404, 429):
            resp.failure(f"Unexpected status {resp.status_code}")

    @task(3)
    def ask_question(self) -> None:
        """POST /documents/{id}/questions — exercises the per-account
        concurrency limit (QUESTION_MAX_CONCURRENT = 1, PROVISIONAL).

        STUB: endpoint not yet built (ENG-CPD-011). Will return 404 until
        that task merges.

        Target behavior once the endpoint exists:
          - First in-flight question per account → 200 (after ~90s).
          - Second concurrent question from the same account → 429 with
            message "You already have a question in progress."
        """
        doc_id = self.document_id or str(uuid.uuid4())
        resp = self.client.post(
            f"/documents/{doc_id}/questions",
            json={"question": "What are the main topics covered in this document?"},
            name="/documents/{id}/questions [ask]",
        )
        if resp.status_code not in (200, 404, 409, 429):
            resp.failure(f"Unexpected status {resp.status_code}")
