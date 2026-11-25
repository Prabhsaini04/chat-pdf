from app.models import Base

EXPECTED_TABLES = {
    "accounts",
    "sessions",
    "auth_events",
    "documents",
    "chunks",
    "conversations",
    "messages",
}


def test_all_tables_registered_on_shared_metadata():
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_tenant_tables_have_account_id_column():
    tenant_scoped = EXPECTED_TABLES - {"accounts"}
    for table_name in tenant_scoped:
        table = Base.metadata.tables[table_name]
        assert "account_id" in table.columns, (
            f"{table_name} must denormalize account_id for direct tenant"
            " filtering (threat-model mitigation, implementation plan §3)"
        )


def test_documents_has_soft_delete_fields():
    table = Base.metadata.tables["documents"]
    assert "soft_deleted_at" in table.columns
    assert "hard_delete_at" in table.columns


def test_chunk_embedding_dimension_matches_bge_small():
    from app.embeddings.models import EMBEDDING_DIM

    assert EMBEDDING_DIM == 384
