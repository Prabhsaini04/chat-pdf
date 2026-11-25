from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.health import router as health_router
from app.rate_limiting.exceptions import RateLimitExceeded

app = FastAPI(title="chat-pdf API")


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": exc.detail},
        headers={"Retry-After": str(exc.retry_after)},
    )


app.include_router(health_router)
app.include_router(auth_router)

# Remaining domain routers (documents, conversations, ...) are added by
# their own tasks (ENG-CPD-008/012/...).
