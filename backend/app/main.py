from fastapi import FastAPI

from app.health import router as health_router

app = FastAPI(title="chat-pdf API")

app.include_router(health_router)

# Domain routers (auth, documents, conversations, ...) are added by their
# own tasks (ENG-CPD-005/008/012/...), not here — this is scaffolding only
# (ENG-CPD-001).
