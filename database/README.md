# database/

Alembic migrations for the chat-pdf schema (ENG-CPD-004). The models
themselves live in `backend/app/*/models.py` (one SQLAlchemy model module
per owning domain package); `backend/app/models.py` is the single import
point that registers all of them on the shared `Base.metadata`, which
`migrations/env.py` imports across the `database/` ↔ `backend/` folder
boundary.

## Running migrations

```
cd database
alembic -c alembic.ini upgrade head
```

Reads `DATABASE_URL` the same way the backend app does (`app.config.settings`,
env-var-based — see `docs/secrets-management.md`), not a hardcoded URL in
`alembic.ini`.

## Tables (see `backend/app/models.py` for the authoritative definitions)

`accounts`, `sessions`, `auth_events`, `documents`, `chunks` (pgvector,
384-dim — BGE-small-en-v1.5), `conversations`, `messages`. `account_id` is
denormalized onto every tenant-scoped table so isolation never depends on a
join (implementation plan §3).

**Not yet decided here (flagged, not silently resolved):** exact pgvector
index type/parameters (ivfflat vs. hnsw) — left unindexed-beyond-btree for
now; ENG-CPD-010's job once there's real data to benchmark against.
`deletion_events` (ENG-CPD-014) is not in this migration — that task adds
it.
