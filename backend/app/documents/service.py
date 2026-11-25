import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.models import Document

_PDF_MAGIC = b"%PDF"


def validate_and_store_file(
    upload: UploadFile,
    storage_root: str,
    account_id: uuid.UUID,
    document_id: uuid.UUID,
    max_bytes: int,
) -> tuple[int, str]:
    """Stream-reads the upload, validates it's a PDF and within size limit,
    writes to disk.  Returns (size_bytes, storage_key)."""
    doc_dir = Path(storage_root) / str(account_id) / str(document_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    dest = doc_dir / "original.pdf"

    size = 0
    first_read = True

    try:
        with dest.open("wb") as fh:
            while True:
                chunk = upload.file.read(65_536)
                if not chunk:
                    break
                if first_read:
                    if not chunk[:4].startswith(_PDF_MAGIC):
                        raise HTTPException(
                            status_code=400,
                            detail="Uploaded file is not a valid PDF.",
                        )
                    first_read = False
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
                    )
                fh.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise

    if first_read:
        # Empty file
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    storage_key = f"{account_id}/{document_id}/original.pdf"
    return size, storage_key


def get_document_or_404(
    db: Session, document_id: uuid.UUID, account_id: uuid.UUID
) -> Document:
    """Returns the document if it belongs to the account; raises 404 otherwise.
    Identical result for nonexistent vs. wrong-account ID — REQ-007 uniform 404.
    """
    doc = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.account_id == account_id,
            Document.soft_deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def list_documents(db: Session, account_id: uuid.UUID) -> list[Document]:
    return list(
        db.execute(
            select(Document)
            .where(
                Document.account_id == account_id,
                Document.soft_deleted_at.is_(None),
            )
            .order_by(Document.created_at.desc())
        )
        .scalars()
        .all()
    )
