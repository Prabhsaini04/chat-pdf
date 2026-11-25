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


settings = Settings()
