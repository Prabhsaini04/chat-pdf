"""Embedding generation — ENG-CPD-010.

Model: BAAI/bge-small-en-v1.5 (384-dim, confirmed in ADR-CPD-001).
The model is downloaded from HuggingFace on first use and cached under
HF_HOME (see infrastructure/docker-compose.yml for the cache volume).

The module-level singleton avoids reloading the model on every request/task.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _ST

_model: _ST | None = None
MODEL_NAME = "BAAI/bge-small-en-v1.5"


def _get_model() -> _ST:
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install the [ml] extra: pip install 'chat-pdf-backend[ml]'"
            ) from e
        _model = SentenceTransformer(MODEL_NAME)
    return _model


class EmbeddingService:
    """Thin wrapper around the BGE-small model for the rest of the codebase."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = _get_model()
        # normalize_embeddings=True makes cosine distance equivalent to dot product.
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
