import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.models import Chunk


def search_chunks(
    db: Session, account_id: uuid.UUID, query_embedding: list[float], top_k: int = 5
) -> list[Chunk]:
    """Tenant-scoped top-k pgvector similarity search — the exact mechanism
    SECURITY/THREAT-chat-pdf-mvp.md §2 requires: the `account_id` filter is
    applied **in the SQL query itself** (a `WHERE` clause evaluated before
    the vector ordering/limit), not as a post-filter over an unscoped
    result set. ENG-CPD-011 builds the full ask-question endpoint on top of
    this (or a design that keeps this same pre-filter property) — this is
    deliberately minimal, scoped only to what ENG-CPD-006's isolation test
    needs to exist and prove against, not a complete retrieval service.
    """
    stmt = (
        select(Chunk)
        .where(Chunk.account_id == account_id)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return list(db.execute(stmt).scalars().all())
