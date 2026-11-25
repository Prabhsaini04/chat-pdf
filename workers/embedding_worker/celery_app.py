"""Celery entrypoint for the worker-embed pool (BGE-small embedding
generation, ENG-CPD-010). See document_processor/celery_app.py for the
no-duplicated-business-logic rule this follows."""

from celery import Celery

from app.config import settings

celery_app = Celery("embedding_worker", broker=settings.redis_url, backend=settings.redis_url)

# Task registration happens in ENG-CPD-010.
