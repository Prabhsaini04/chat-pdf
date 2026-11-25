from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.health import router as health_router

app = FastAPI(title="chat-pdf API")

app.include_router(health_router)
app.include_router(auth_router)

# Remaining domain routers (documents, conversations, ...) are added by
# their own tasks (ENG-CPD-008/012/...).
