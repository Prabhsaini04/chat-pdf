"""Celery entrypoint for the worker-llm pool (Ollama-calling answer
generation, ENG-CPD-011). Kept as its own pool so it can be resourced/
scaled independently of OCR/embedding throughput (DEPLOYMENT_ARCHITECTURE.md
§1)."""

from celery import Celery

from app.config import settings

celery_app = Celery("llm_worker", broker=settings.redis_url, backend=settings.redis_url)

# Task registration happens in ENG-CPD-011.
