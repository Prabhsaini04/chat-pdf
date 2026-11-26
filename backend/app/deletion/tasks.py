"""Scheduled hard-delete worker — ENG-CPD-014.

Runs periodically (via Celery Beat) to hard-delete documents whose
hard_delete_at timestamp has passed.  Uses SELECT ... FOR UPDATE + a
'purging' status guard to prevent the restore-vs-purge race (REQ-006/EC-14-c).

Registered to the worker-io queue (file I/O: shutil.rmtree).
"""

from __future__ import annotations

import logging

from app.workers.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.deletion.tasks.hard_delete_expired_documents")
def hard_delete_expired_documents() -> int:
    """Claim and hard-delete all documents past their hard_delete_at deadline.
    Returns the count of documents deleted.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.config import settings
    from app.db import SessionLocal
    from app.deletion.service import _delete_files_and_records
    from app.documents.models import Document

    db = SessionLocal()
    deleted = 0
    try:
        now = datetime.now(UTC)

        # Claim eligible rows atomically to prevent concurrent worker runs
        # from double-deleting (SKIP LOCKED — safe to miss a row, we'll get
        # it on the next run; preferable to blocking on a row another worker
        # already holds).
        rows = db.execute(
            select(Document)
            .where(
                Document.hard_delete_at <= now,
                Document.soft_deleted_at.isnot(None),
                Document.status != "purging",
            )
            .with_for_update(skip_locked=True)
            .limit(50)
        ).scalars().all()

        for doc in rows:
            doc.status = "purging"
            db.flush()

            try:
                _delete_files_and_records(db, doc, settings.storage_root)
                deleted += 1
            except Exception:
                logger.exception("hard_delete_expired_documents: failed for %s", doc.id)
                db.rollback()

    finally:
        db.close()

    logger.info("hard_delete_expired_documents: deleted %d documents", deleted)
    return deleted
