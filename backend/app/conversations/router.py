"""Conversation endpoints — ENG-CPD-011 (ask-question) and ENG-CPD-012 (history).

The ask-question endpoint is synchronous: the HTTP connection is held open
while Ollama generates the answer (up to settings.ollama_timeout_seconds).
The ~90s latency target (REQ-003/OQ-9) makes this acceptable for MVP; async
polling can be added later.
"""

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.auth.models import Account
from app.citations.validator import validate_citations
from app.config import settings
from app.conversations.models import Conversation, Message
from app.conversations.schemas import ConversationOut, MessageOut, QuestionRequest
from app.db import get_db
from app.documents.service import get_document_or_404
from app.embeddings.service import EmbeddingService
from app.llm.client import build_context, call_ollama, extract_cited_pages
from app.rate_limiting.dependencies import (
    ConcurrencyLimiter,
    check_question_concurrency,
    get_concurrency_limiter,
)
from app.retrieval.search import search_chunks

router = APIRouter(tags=["conversations"])

_embedder = EmbeddingService()


def _get_or_create_conversation(
    db: Session, document_id: uuid.UUID, account_id: uuid.UUID
) -> Conversation:
    conv = db.execute(
        select(Conversation).where(
            Conversation.document_id == document_id,
            Conversation.account_id == account_id,
        )
    ).scalar_one_or_none()
    if conv is None:
        conv = Conversation(document_id=document_id, account_id=account_id)
        db.add(conv)
        db.flush()
    return conv


@router.post(
    "/documents/{document_id}/questions",
    response_model=MessageOut,
    status_code=200,
)
def ask_question(
    document_id: uuid.UUID,
    request: QuestionRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
    _: None = Depends(check_question_concurrency),
    limiter: ConcurrencyLimiter = Depends(get_concurrency_limiter),
) -> MessageOut:
    """Ask a question about a document.  Blocks until the LLM responds.
    Returns the assistant message with citations (REQ-003).
    """
    try:
        doc = get_document_or_404(db, document_id, account.id)

        if doc.status != "ready":
            raise HTTPException(
                status_code=409,
                detail="Document is still processing. Please wait until it is ready.",
            )

        conv = _get_or_create_conversation(db, document_id, account.id)

        # Store user question
        user_msg = Message(
            conversation_id=conv.id,
            account_id=account.id,
            role="user",
            content=request.question,
            citation_pages=[],
            citation_status="n/a",
        )
        db.add(user_msg)
        db.flush()

        # Embed the question and retrieve relevant chunks
        query_embedding = _embedder.embed_text(request.question)
        chunks = search_chunks(
            db,
            account.id,
            query_embedding,
            top_k=settings.retrieval_top_k,
            document_id=document_id,
        )

        if not chunks:
            answer_text = "I could not find relevant information in this document."
            citation_pages: list[int] = []
            citation_status = "no_relevant_content"
        else:
            context_text, available_pages = build_context(chunks)
            try:
                answer_text = call_ollama(
                    request.question,
                    context_text,
                    settings.ollama_base_url,
                    settings.ollama_model,
                    settings.ollama_timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Could not generate an answer right now. Please try again.",
                ) from exc

            citation_pages = extract_cited_pages(answer_text)
            citation_status = validate_citations(citation_pages, available_pages, answer_text)

        assistant_msg = Message(
            conversation_id=conv.id,
            account_id=account.id,
            role="assistant",
            content=answer_text,
            citation_pages=citation_pages,
            citation_status=citation_status,
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        return MessageOut.model_validate(assistant_msg)

    finally:
        # Always release the concurrency slot — prevents permanent blocking
        # if an exception is raised before the try/finally in the dep fires.
        limiter.release(f"cl:question:{account.id}")


@router.get(
    "/documents/{document_id}/conversation",
    response_model=ConversationOut,
)
def get_conversation(
    document_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> ConversationOut:
    """Return the conversation history for a document (REQ-004).
    Returns an empty message list if no questions have been asked yet.
    """
    get_document_or_404(db, document_id, account.id)  # uniform 404

    conv = db.execute(
        select(Conversation).where(
            Conversation.document_id == document_id,
            Conversation.account_id == account.id,
        )
    ).scalar_one_or_none()

    messages: list[Message] = []
    if conv is not None:
        messages = list(
            db.execute(
                select(Message)
                .where(
                    Message.conversation_id == conv.id,
                    Message.account_id == account.id,
                )
                .order_by(Message.created_at)
            )
            .scalars()
            .all()
        )

    return ConversationOut(
        document_id=document_id,
        messages=[MessageOut.model_validate(m) for m in messages],
    )
