"""ENG-CPD-006 — cross-tenant isolation, the must-have item from
SECURITY/THREAT-chat-pdf-mvp.md §2. Phased per that task's own record:

  - Account creation goes through the real signup/login flow (ENG-CPD-005),
    not direct DB inserts, so auth + isolation are tested together.
  - Documents/chunks are seeded directly against the schema (ENG-CPD-004),
    since the upload/processing pipeline (ENG-CPD-008/009/010) doesn't
    exist yet — this is explicitly allowed by the task's own phasing note
    ("harness scaffolding... before ENG-CPD-010/011... so the gate is
    already active... the moment retrieval code is first written").
  - The retrieval-isolation tests exercise `app.retrieval.search.search_chunks`
    directly — the real tenant-scoped SQL/vector query, not a mock — which
    is the actual mechanism the threat model is worried about (a broken
    pre-filter), per this task's own "Risks" note.
  - Document-list/detail/conversation-history isolation is tested at the
    query-pattern level (the exact WHERE-clause shape every future endpoint
    must use), since those HTTP endpoints (ENG-CPD-008/012/013) don't exist
    yet either. Re-exercise this at the HTTP layer once they do — tracked
    as a follow-up in the handoff, not silently treated as fully covered.

Every test here is marked `isolation` and is meant to be a required,
non-skippable CI gate (see .github/workflows/ci.yml's `test-backend-isolation`
job) on any PR touching documents/chunks/conversations/auth.
"""

import uuid

import pytest
from sqlalchemy import select

from app.conversations.models import Conversation, Message
from app.documents.models import Document
from app.embeddings.models import EMBEDDING_DIM, Chunk
from app.retrieval.search import search_chunks

pytestmark = pytest.mark.isolation


def _signup_and_get_account_id(
    client, email: str, password: str = "correct-horse-battery-staple"
) -> str:
    resp = client.post("/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()["account_id"]


def _make_embedding(seed: float) -> list[float]:
    # Deliberately near-identical across accounts (see module docstring):
    # a broken/post-filtered query would plausibly return both accounts'
    # chunks for the same top-k search. Only the last component differs by
    # a tiny amount so they aren't bit-for-bit identical vectors.
    return [seed] * (EMBEDDING_DIM - 1) + [seed + 0.0001]


def _seed_document_with_chunk(
    db_session, account_id: uuid.UUID, text: str, embedding: list[float]
) -> Document:
    document = Document(
        account_id=account_id,
        storage_key=f"{account_id}/{uuid.uuid4()}/original.pdf",
        original_filename="contract.pdf",
        size_bytes=1024,
        status="ready",
        page_count=1,
        extraction_method="direct",
    )
    db_session.add(document)
    db_session.flush()

    chunk = Chunk(
        document_id=document.id,
        account_id=account_id,
        page_number=1,
        chunk_index=0,
        extraction_method="direct",
        text=text,
        embedding=embedding,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.fixture()
def two_accounts(client, db_session):
    account_a_id = uuid.UUID(_signup_and_get_account_id(client, "account-a@example.com"))
    account_b_id = uuid.UUID(_signup_and_get_account_id(client, "account-b@example.com"))
    return account_a_id, account_b_id


SHARED_TEXT = "Section 4.2: renewal terms for the annual services contract."


def test_retrieval_never_returns_other_accounts_chunks(client, db_session, two_accounts):
    account_a_id, account_b_id = two_accounts
    embedding_a = _make_embedding(0.1)
    embedding_b = _make_embedding(0.1000001)  # deliberately near-identical to A's

    _seed_document_with_chunk(db_session, account_a_id, SHARED_TEXT, embedding_a)
    _seed_document_with_chunk(db_session, account_b_id, SHARED_TEXT, embedding_b)

    # Sanity check the fixture itself is meaningful: both chunks really do
    # exist and really are near-duplicates, so a broken/post-filtered query
    # would have a real chance of mixing them up — this isn't a trivially
    # passing test.
    all_chunks = db_session.execute(select(Chunk)).scalars().all()
    assert len(all_chunks) == 2
    assert {c.account_id for c in all_chunks} == {account_a_id, account_b_id}

    query_embedding = _make_embedding(0.1)  # matches both equally closely

    results_for_a = search_chunks(db_session, account_a_id, query_embedding, top_k=5)
    assert len(results_for_a) == 1, "expected exactly account A's own chunk, nothing more"
    assert all(c.account_id == account_a_id for c in results_for_a), (
        f"LEAK: search_chunks(account_id={account_a_id}) returned a chunk "
        f"belonging to {[c.account_id for c in results_for_a if c.account_id != account_a_id]}"
    )

    results_for_b = search_chunks(db_session, account_b_id, query_embedding, top_k=5)
    assert len(results_for_b) == 1, "expected exactly account B's own chunk, nothing more"
    assert all(c.account_id == account_b_id for c in results_for_b), (
        f"LEAK: search_chunks(account_id={account_b_id}) returned a chunk "
        f"belonging to {[c.account_id for c in results_for_b if c.account_id != account_b_id]}"
    )


def test_retrieval_respects_top_k_even_with_no_match_in_account(client, db_session, two_accounts):
    """Account B has no documents at all — must get zero results, never a
    fallback into Account A's data."""
    account_a_id, account_b_id = two_accounts
    _seed_document_with_chunk(db_session, account_a_id, SHARED_TEXT, _make_embedding(0.5))

    results_for_b = search_chunks(db_session, account_b_id, _make_embedding(0.5), top_k=5)
    assert results_for_b == []


def test_document_list_query_pattern_scoped_to_account(client, db_session, two_accounts):
    """The exact WHERE-clause shape ENG-CPD-008's `GET /documents` must use.
    Re-exercise at the HTTP layer once that endpoint exists (tracked in the
    handoff) — this proves the query pattern now, not the endpoint."""
    account_a_id, account_b_id = two_accounts
    doc_a = _seed_document_with_chunk(db_session, account_a_id, SHARED_TEXT, _make_embedding(0.2))
    doc_b = _seed_document_with_chunk(db_session, account_b_id, SHARED_TEXT, _make_embedding(0.2))

    docs_for_a = db_session.execute(
        select(Document).where(Document.account_id == account_a_id)
    ).scalars().all()
    assert {d.id for d in docs_for_a} == {doc_a.id}
    assert doc_b.id not in {d.id for d in docs_for_a}


def test_document_detail_query_pattern_uniform_not_found_cross_account(
    client, db_session, two_accounts
):
    """The exact pattern ENG-CPD-008's `GET /documents/{id}` must use:
    `WHERE id = :id AND account_id = :verified_account_id` — a row owned by
    another account must produce the same "no row" result as a
    nonexistent ID (uniform 404 at the HTTP layer, once it exists)."""
    account_a_id, account_b_id = two_accounts
    doc_a = _seed_document_with_chunk(db_session, account_a_id, SHARED_TEXT, _make_embedding(0.3))

    # Account B looking up Account A's real document ID.
    row = db_session.execute(
        select(Document).where(Document.id == doc_a.id, Document.account_id == account_b_id)
    ).scalar_one_or_none()
    assert row is None, "LEAK: account B's query returned account A's document"

    # A nonexistent ID produces the identical "no row" result for account B —
    # proving the two cases are indistinguishable at this layer (no
    # separate "exists but not yours" signal to leak upstream).
    row_nonexistent = db_session.execute(
        select(Document).where(Document.id == uuid.uuid4(), Document.account_id == account_b_id)
    ).scalar_one_or_none()
    assert row_nonexistent is None

    # The owner still gets the real row.
    row_owner = db_session.execute(
        select(Document).where(Document.id == doc_a.id, Document.account_id == account_a_id)
    ).scalar_one_or_none()
    assert row_owner is not None
    assert row_owner.id == doc_a.id


def test_conversation_history_query_pattern_scoped_to_account(client, db_session, two_accounts):
    """The pattern ENG-CPD-012's `GET /documents/{id}/conversation` must
    use — conversations/messages are account-scoped the same way
    documents/chunks are (REQ-004's existing policy, ENG-CPD-000 §3)."""
    account_a_id, account_b_id = two_accounts
    doc_a = _seed_document_with_chunk(db_session, account_a_id, SHARED_TEXT, _make_embedding(0.4))

    conversation = Conversation(document_id=doc_a.id, account_id=account_a_id)
    db_session.add(conversation)
    db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        account_id=account_a_id,
        role="assistant",
        content="Renewal terms are in Section 4.2.",
        citation_pages=[4],
        citation_status="grounded",
    )
    db_session.add(message)
    db_session.commit()

    history_for_b = db_session.execute(
        select(Message).where(
            Message.conversation_id == conversation.id, Message.account_id == account_b_id
        )
    ).scalars().all()
    assert history_for_b == [], (
        "LEAK: account B's scoped query returned account A's conversation history"
    )

    history_for_a = db_session.execute(
        select(Message).where(
            Message.conversation_id == conversation.id, Message.account_id == account_a_id
        )
    ).scalars().all()
    assert len(history_for_a) == 1
    assert history_for_a[0].id == message.id
