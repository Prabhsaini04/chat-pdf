"""Celery-beat entrypoint for the scheduled hard-delete/purge worker
(ENG-CPD-014). Race-prevention mechanism (SELECT ... FOR UPDATE + 'purging'
status guard + SKIP LOCKED + reclaim timeout) is designed in
ENG-CPD-014-deletion-worker.md and implemented in that task, not here."""

from celery import Celery

from app.config import settings

celery_app = Celery("deletion_worker", broker=settings.redis_url, backend=settings.redis_url)

# Task registration happens in ENG-CPD-014.
