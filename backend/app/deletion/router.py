"""Deletion endpoints — ENG-CPD-014."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.auth.models import Account
from app.config import settings
from app.db import get_db
from app.deletion.service import (
    immediate_purge_document,
    restore_document,
    soft_delete_document,
)
from app.documents.schemas import DocumentOut

router = APIRouter(tags=["deletion"])


@router.delete("/documents/{document_id}", status_code=200, response_model=DocumentOut)
def delete_document(
    document_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Soft-delete a document (moves it to trash, recoverable for 30 days)."""
    doc = soft_delete_document(db, document_id, account.id)
    return DocumentOut.model_validate(doc)


@router.post("/documents/{document_id}/restore", status_code=200, response_model=DocumentOut)
def restore_document_endpoint(
    document_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Restore a soft-deleted document within the 30-day window."""
    doc = restore_document(db, document_id, account.id)
    return DocumentOut.model_validate(doc)


@router.delete("/documents/{document_id}/purge", status_code=204)
def purge_document(
    document_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> None:
    """Immediately and permanently delete a document (skips the 30-day window).
    Requires a separate explicit call — REQ-006's distinct second confirmation step
    is enforced by the frontend, which must call this endpoint separately from
    the soft-delete.
    """
    immediate_purge_document(db, document_id, account.id, settings.storage_root)
