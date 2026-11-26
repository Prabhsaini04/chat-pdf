import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.models import Chunk


def search_chunks(
    db: Session,
    account_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
    document_id: uuid.UUID | None = None,
) -> list[Chunk]:
    """Tenant-scoped top-k pgvector similarity search.

    The `account_id` filter is applied in the SQL query itself (a WHERE clause
    evaluated before the vector ordering/limit), not as a post-filter — this is
    the specific mechanism SECURITY/THREAT-chat-pdf-mvp.md §2 requires, proven
    by ENG-CPD-006's isolation tests.

    Optional `document_id` further scopes results to a single document
    (required for the ask-question endpoint — REQ-005: no cross-document leakage).
    """
    stmt = select(Chunk).where(Chunk.account_id == account_id)
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
    stmt = stmt.order_by(Chunk.embedding.cosine_distance(query_embedding)).limit(top_k)
    return list(db.execute(stmt).scalars().all())
