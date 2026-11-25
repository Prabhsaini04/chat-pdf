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


settings = Settings()
