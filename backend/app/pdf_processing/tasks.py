"""Celery task: process a document (extract → chunk → embed → store).

Runs in the worker-io queue (file-I/O bound phase: extraction + DB writes).
Embedding generation is CPU-bound but kept in the same task for simplicity
at MVP; ENG-CPD-010 notes this can be split across worker-io → worker-embed
once queue-depth monitoring (ENG-CPD-016) shows it's a bottleneck.
"""

from __future__ import annotations

import logging

from app.workers.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(
    name="app.pdf_processing.tasks.process_document",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_document(self, document_id: str) -> None:  # noqa: ANN001
    """Extract text, chunk, embed, and persist chunks for `document_id`.
    Updates document.status to 'ready' on success or 'failed' on error.
    """
    from pathlib import Path

    from sqlalchemy import select

    from app.config import settings
    from app.db import SessionLocal
    from app.documents.models import Document
    from app.embeddings.models import Chunk
    from app.embeddings.service import EmbeddingService
    from app.pdf_processing.chunker import chunk_pages
    from app.pdf_processing.extractor import extract_pages

    db = SessionLocal()
    try:
        doc = db.execute(
            select(Document).where(Document.id == document_id)
        ).scalar_one_or_none()

        if doc is None:
            logger.warning("process_document: document %s not found", document_id)
            return

        storage_path = str(
            Path(settings.storage_root) / str(doc.account_id) / str(doc.id) / "original.pdf"
        )

        # --- Extract ---
        pages = extract_pages(storage_path)
        non_empty = [p for p in pages if p.text]

        if not non_empty:
            doc.status = "failed"
            doc.failure_reason = (
                "No readable text found in this document, even after OCR. "
                "It may be a scanned PDF with no recognisable characters."
            )
            db.commit()
            return

        # Determine overall extraction method
        methods = {p.extraction_method for p in non_empty}
        doc.extraction_method = "ocr" if methods == {"ocr"} else (
            "mixed" if len(methods) > 1 else "direct"
        )
        doc.page_count = len(pages)
        db.flush()

        # --- Chunk ---
        text_chunks = chunk_pages(pages)
        if not text_chunks:
            doc.status = "failed"
            doc.failure_reason = "Document parsed but produced no usable text chunks."
            db.commit()
            return

        # --- Embed ---
        embedder = EmbeddingService()
        texts = [c.text for c in text_chunks]
        embeddings = embedder.embed_texts(texts)

        # --- Persist ---
        for _i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings, strict=False)):
            db.add(
                Chunk(
                    document_id=doc.id,
                    account_id=doc.account_id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    extraction_method=chunk.extraction_method,
                    text=chunk.text,
                    embedding=embedding,
                )
            )

        doc.status = "ready"
        db.commit()
        logger.info(
            "process_document: document %s ready (%d chunks)", document_id, len(text_chunks)
        )

    except Exception as exc:
        db.rollback()
        try:
            doc = db.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.failure_reason = "An error occurred during processing. Please try again."
                db.commit()
        except Exception:
            pass
        logger.exception("process_document failed for %s", document_id)
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
