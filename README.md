# chat-pdf

Upload a PDF, ask questions about it, get answers grounded in the
document's content with page-level citations.

Self-hosted stack: FastAPI, React + Vite, PostgreSQL + pgvector, Celery +
Redis, Ollama (Qwen2.5), PyMuPDF, Tesseract OCR, BGE-small-en-v1.5.

Requirements, architecture, ADRs, threat model, and test plans for this
project are maintained in the AI-ENGINEERING-TEAM org repo under
`07-Projects/chat-pdf/` — see `docs/README.md` for the full list. This repo
is the implementation only.

See `docs/local-dev.md` to run this locally.

**Status:** scaffolding (ENG-CPD-001) — no application features implemented
yet.
