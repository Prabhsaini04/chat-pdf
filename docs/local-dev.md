# Local development

## Backend

```
cd backend
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

## Frontend

```
cd frontend
npm install
npm run dev
```

## Dev stack (Postgres+pgvector, Redis, Ollama)

```
docker compose -f infrastructure/docker-compose.yml up -d
```

The `app` container reads `backend/.env` (copy `backend/.env.example` first
if it doesn't exist yet). These are dev-only placeholder values
(ENG-CPD-002) — not a production secrets mechanism.

## Tests

```
cd backend && pytest
cd frontend && npm run test
```

Load testing (ENG-CPD-007/020) uses Locust — added once those tasks exist.

## Notes

- Workers (`workers/document_processor`, `workers/embedding_worker`,
  `workers/llm_worker`, `workers/deletion_worker`) are scaffolding only at
  this point (ENG-CPD-001) — task registration/business logic lands with
  ENG-CPD-009/010/011/014 respectively.
- `database/` is empty until ENG-CPD-004.
