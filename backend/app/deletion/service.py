"""Soft-delete, restore, and hard-delete logic — ENG-CPD-014.

Implements the OQ-13 policy (Option A — 30-day recoverable deletion):
  - Soft delete:  sets soft_deleted_at = now, hard_delete_at = now + 30d.
  - Restore:      clears both timestamps while document is in days 1–29.
  - Immediate purge: user-initiated permanent delete, no waiting.
  - Hard delete:  worker job, fires when hard_delete_at is in the past.

Race condition (REQ-006/EC-14-c): restore vs. purge at the 30-day boundary.
Guard: SELECT ... FOR UPDATE + optimistic status check inside the same
transaction.  If the purge worker already holds the row lock, the restore
raises 409.  If the restore wins the lock, it clears hard_delete_at before
the purge worker can claim the row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conversations.models import Conversation, Message
from app.documents.models import Document
from app.embeddings.models import Chunk

SOFT_DELETE_WINDOW_DAYS = 30


def soft_delete_document(
    db: Session, document_id: uuid.UUID, account_id: uuid.UUID
) -> Document:
    doc = db.execute(
        select(Document)
        .where(Document.id == document_id, Document.account_id == account_id)
        .with_for_update()
    ).scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.soft_deleted_at is not None:
        raise HTTPException(status_code=409, detail="Document is already deleted.")

    now = datetime.now(UTC)
    doc.soft_deleted_at = now
    doc.hard_delete_at = now + timedelta(days=SOFT_DELETE_WINDOW_DAYS)
    doc.status = "soft_deleted"
    db.commit()
    db.refresh(doc)
    return doc


def restore_document(
    db: Session, document_id: uuid.UUID, account_id: uuid.UUID
) -> Document:
    doc = db.execute(
        select(Document)
        .where(Document.id == document_id, Document.account_id == account_id)
        .with_for_update()
    ).scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.soft_deleted_at is None:
        raise HTTPException(status_code=409, detail="Document is not deleted.")
    if doc.status == "purging":
        raise HTTPException(
            status_code=409,
            detail="Document is being permanently deleted and cannot be restored.",
        )

    now = datetime.now(UTC)
    if doc.hard_delete_at and doc.hard_delete_at <= now:
        raise HTTPException(
            status_code=410,
            detail="The 30-day recovery window has closed. This document cannot be restored.",
        )

    doc.soft_deleted_at = None
    doc.hard_delete_at = None
    doc.status = "ready"
    db.commit()
    db.refresh(doc)
    return doc


def immediate_purge_document(
    db: Session, document_id: uuid.UUID, account_id: uuid.UUID, storage_root: str
) -> None:
    """User-initiated permanent delete — skips the 30-day window (REQ-006)."""
    doc = db.execute(
        select(Document)
        .where(Document.id == document_id, Document.account_id == account_id)
        .with_for_update()
    ).scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    _delete_files_and_records(db, doc, storage_root)


def _delete_files_and_records(db: Session, doc: Document, storage_root: str) -> None:
    """Delete storage files and all associated DB rows.  Called from both
    immediate purge and the scheduled hard-delete worker.
    """
    import shutil

    doc_dir = Path(storage_root) / str(doc.account_id) / str(doc.id)

    # DB records first (cascade: chunks → messages via conversation)
    conv = db.execute(
        select(Conversation).where(Conversation.document_id == doc.id)
    ).scalar_one_or_none()
    if conv:
        db.execute(
            Message.__table__.delete().where(Message.conversation_id == conv.id)
        )
        db.delete(conv)

    db.execute(Chunk.__table__.delete().where(Chunk.document_id == doc.id))
    db.delete(doc)
    db.commit()

    # Remove files after the DB commit (if DB fails, files are orphaned but not lost)
    if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)
