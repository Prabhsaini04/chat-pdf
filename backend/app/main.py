from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.conversations.router import router as conversations_router
from app.deletion.router import router as deletion_router
from app.documents.router import router as documents_router
from app.health import router as health_router
from app.rate_limiting.exceptions import RateLimitExceeded

app = FastAPI(title="chat-pdf API")

# CORS — allows the React dev server (Vite default: 5173) and the
# production Nginx-served frontend to reach the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": exc.detail},
        headers={"Retry-After": str(exc.retry_after)},
    )


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(deletion_router)
