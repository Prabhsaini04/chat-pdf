from fastapi import APIRouter, Response
from sqlalchemy import create_engine, text

from app.config import settings

router = APIRouter()


def _check_database() -> bool:
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_redis() -> bool:
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        return bool(client.ping())
    except Exception:
        return False


def _check_ollama() -> bool:
    try:
        import httpx

        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


@router.get("/health")
def health(response: Response) -> dict:
    checks = {
        "database": _check_database(),
        "redis": _check_redis(),
        "ollama": _check_ollama(),
    }
    ok = all(checks.values())
    response.status_code = 200 if ok else 503
    return {"status": "ok" if ok else "degraded", "checks": checks}
