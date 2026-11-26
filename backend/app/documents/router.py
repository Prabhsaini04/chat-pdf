import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.auth.models import Account
from app.config import settings
from app.db import get_db
from app.documents.models import Document
from app.documents.schemas import (
    DocumentListResponse,
    DocumentOut,
    DocumentUploadResponse,
)
from app.documents.service import (
    get_document_or_404,
    list_documents,
    validate_and_store_file,
)
from app.rate_limiting.dependencies import check_upload_rate_limit

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=202, response_model=DocumentUploadResponse)
def upload_document(
    file: UploadFile = File(...),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
    _rate: None = Depends(check_upload_rate_limit),
) -> DocumentUploadResponse:
    """Upload a PDF and begin async processing.  Returns 202; poll
    GET /documents/{id} for status transitions (uploading→processing→ready/failed)."""
    doc_id = uuid.uuid4()

    size, storage_key = validate_and_store_file(
        file,
        settings.storage_root,
        account.id,
        doc_id,
        settings.max_upload_bytes,
    )

    doc = Document(
        id=doc_id,
        account_id=account.id,
        storage_key=storage_key,
        original_filename=(file.filename or "upload.pdf")[:255],
        size_bytes=size,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Dispatch to worker-io queue — import inside function to avoid loading
    # Celery at module-load time in environments where Redis is not available.
    from app.pdf_processing.tasks import process_document

    process_document.delay(str(doc.id))

    return DocumentUploadResponse(document_id=doc.id, status="processing")


@router.get("", response_model=DocumentListResponse)
def list_documents_endpoint(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    docs = list_documents(db, account.id)
    return DocumentListResponse(documents=[DocumentOut.model_validate(d) for d in docs])


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> DocumentOut:
    doc = get_document_or_404(db, document_id, account.id)
    return DocumentOut.model_validate(doc)
