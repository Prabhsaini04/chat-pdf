# docs/

Requirements, architecture decisions, threat model, and test plans for this
project live in the governance repo, not here:

- `07-Projects/chat-pdf/REQUIREMENTS.md`
- `07-Projects/chat-pdf/ARCHITECTURE.md`
- `07-Projects/chat-pdf/DECISIONS/` (ADRs)
- `07-Projects/chat-pdf/SECURITY/THREAT-chat-pdf-mvp.md`
- `07-Projects/chat-pdf/DEVELOPMENT/` (task records, including the
  implementation plan)

This file does not restate their content. If a link here and the governance
repo ever disagree, the governance repo wins.

See `local-dev.md` for how to run this repo locally, and
`secrets-management.md` for the secrets-handling requirement and what's
actually in place (dev-only `.env` pattern; production mechanism still
undecided, see `07-Projects/chat-pdf/DEVOPS/DEPLOYMENT_ARCHITECTURE.md`).
