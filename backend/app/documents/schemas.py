import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    status: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    status: str
    page_count: int | None = None
    size_bytes: int
    extraction_method: str | None = None
    failure_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]
