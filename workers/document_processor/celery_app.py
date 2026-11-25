"""Celery entrypoint for the worker-io pool (PDF extraction + OCR fallback,
ENG-CPD-009). Tasks call into backend/app's modules for actual logic — this
module must not duplicate business logic (implementation plan §8)."""

from celery import Celery

from app.config import settings

celery_app = Celery("document_processor", broker=settings.redis_url, backend=settings.redis_url)

# Task registration happens in ENG-CPD-009.
