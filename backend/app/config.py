from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment only (no hardcoded
    secrets/URLs — CODING_STANDARDS.md). Values here are dev-only
    placeholders per ENG-CPD-002; the production secrets mechanism is a
    separate, not-yet-decided task (ENG-CPD-017).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://chatpdf:chatpdf@postgres:5432/chatpdf"
    redis_url: str = "redis://redis:6379/0"
    ollama_base_url: str = "http://ollama:11434"
    storage_root: str = "/data/documents"

    # Auth (ADR-CPD-003). Exact values are ASSUMPTIONs carried from that
    # design, not final product requirements — adjustable via env without a
    # code change, flagged in ENG-CPD-003/005 for Security/product
    # confirmation.
    session_ttl_days: int = 7
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    max_failed_login_attempts: int = 5
    lockout_window_minutes: int = 15

    # Celery workers (ENG-CPD-008/009/010)
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # Storage (ENG-CPD-008). Path: {storage_root}/{account_id}/{document_id}/
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MB per REQ-001

    # Retrieval (ENG-CPD-011)
    retrieval_top_k: int = 5

    # LLM (ENG-CPD-011). Timeout generous to accommodate ~90s CPU-only inference.
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: int = 120


settings = Settings()
