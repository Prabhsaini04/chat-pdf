"""Single import point so `Base.metadata` has every table registered —
used by Alembic's `env.py` and by tests that need the full schema.
Confirms the implementation plan §3's flagged "does env.py-across-folder
-boundary work cleanly" question: yes, by importing through the `app`
package rather than duplicating table definitions in `database/`."""

from app.auth.models import Account, AccountSession, AuthEvent
from app.conversations.models import Conversation, Message
from app.db import Base
from app.documents.models import Document
from app.embeddings.models import Chunk

__all__ = [
    "Base",
    "Account",
    "AccountSession",
    "AuthEvent",
    "Document",
    "Chunk",
    "Conversation",
    "Message",
]
