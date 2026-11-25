from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery(
    "chat_pdf",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.pdf_processing.tasks",
        "app.deletion.tasks",
    ],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.pdf_processing.tasks.*": {"queue": "worker-io"},
        "app.deletion.tasks.*": {"queue": "worker-io"},
    },
    beat_schedule={
        # Run hard-delete every 6 hours — cadence is generous since
        # hard_delete_at is a 30-day window; exact timing is not critical.
        "hard-delete-expired-documents": {
            "task": "app.deletion.tasks.hard_delete_expired_documents",
            "schedule": crontab(minute=0, hour="*/6"),
        },
    },
)
