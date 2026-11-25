# Secrets management (ENG-CPD-002)

Implements Constitution #6 and the org's
`05-Security/SECRETS_MANAGEMENT.md` for this repo. This document states the
requirement and records what is actually in place today — it does not
invent a production mechanism (that decision is still open, see below).

## Current state: local development only

- Local development configuration is read from environment variables via
  `backend/app/config.py` (`pydantic-settings`), sourced from a `.env` file
  in `backend/`.
- `backend/.env` is **git-ignored** (`.gitignore`'s `.env` / `.env.*.local`
  entries, added by the org sync). It is never committed.
- `backend/.env.example` is committed and holds **placeholder values only**
  — dev-only credentials for the local Docker Compose stack (e.g.
  `chatpdf:chatpdf` for the local Postgres container), not real secrets.
  `app/config.py`'s field defaults mirror the same placeholders, for the
  same reason: convenience for local dev against the Compose stack in
  `infrastructure/docker-compose.yml`, never a value meant to reach a
  shared or production environment.
- No secret, API key, connection string, or credential is committed to any
  branch, baked into a container image layer (`backend/Dockerfile`,
  `frontend/Dockerfile`), or written to logs.
- CI (`.github/workflows/ci.yml`): the only jobs that exist so far
  (`lint-backend`, `lint-frontend`) need no secrets at all. Per
  `DEVOPS/DEPLOYMENT_ARCHITECTURE.md` §5.5, once a job needs a real
  credential (e.g. the Harbor push credential), it belongs in GitHub
  Actions' own encrypted secrets — never a literal in a workflow file.

## What this explicitly does NOT cover: production

**The `.env` / env-var pattern above is local-development-only. It is not
an acceptable production secrets mechanism** per
`05-Security/SECRETS_MANAGEMENT.md` ("Cloud/shared environments: an
approved secret store... Local development: a `.env` file... This pattern
is local-only — shared environments use the secret store above").

This project has no cloud provider (self-hosted, on-prem —
`PROJECT_CONTEXT.md`), so the org's named default (Azure Key Vault) does
not apply as-is. **Which self-hosted secrets mechanism this project uses in
staging/production is still an open decision — not made here, and not
assumed.** `DEVOPS/DEPLOYMENT_ARCHITECTURE.md` and the threat model both
name the candidates (HashiCorp Vault, Docker Compose secrets, SOPS) without
choosing one; that decision belongs to devops-architect/CTO (ENG-CPD-017 in
the implementation plan), is blocked on it, and is out of this task's scope.

Until that decision is made, no real credential (a production database
password, an inter-service auth token, a Harbor robot-account token, etc.)
may be introduced anywhere in this repo — doing so before a real secrets
mechanism exists would mean it has nowhere safe to live.

## Rotation

Not applicable yet — no real secret exists in this project. Once the
production mechanism (ENG-CPD-017) is chosen and real credentials exist,
rotation must not require a code change (secrets referenced by name/path
from the store, not hardcoded), per `05-Security/SECRETS_MANAGEMENT.md`.

## If a secret is ever found committed

Treat it as a security incident per `05-Security/SECURITY_INCIDENT_RESPONSE.md`:
rotate immediately (assume compromised), then clean history, then confirm
no unauthorized use.
