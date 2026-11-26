"""Ollama API client — ENG-CPD-011.

Sends a prompt+context to Ollama's /api/chat endpoint and returns the
generated text.  Called synchronously from the ask-question HTTP handler
with a generous timeout (settings.ollama_timeout_seconds) to accommodate
~90s CPU-only inference latency (REQ-003/OQ-9).

The system prompt instructs the model to cite page numbers as [Page N] so
the citation validator can extract and verify them.
"""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions about a PDF document.
Answer based ONLY on the provided context.  For every statement in your answer,
cite the page number(s) where the information appears using the format [Page N]
(e.g. "The contract was signed on 1 January 2023 [Page 4].").
If the context does not contain enough information to answer the question,
say "I could not find relevant information in this document." and nothing else.
Do NOT use information outside the provided context.
"""


def build_context(chunks: list) -> tuple[str, list[int]]:
    """Build the context string from retrieved chunks and return the available pages."""
    parts = []
    pages: list[int] = []
    for chunk in chunks:
        if chunk.page_number not in pages:
            pages.append(chunk.page_number)
        parts.append(f"[Page {chunk.page_number}]\n{chunk.text}")
    return "\n\n---\n\n".join(parts), sorted(pages)


def call_ollama(
    question: str,
    context: str,
    base_url: str,
    model: str,
    timeout: int,
) -> str:
    """Call Ollama and return the assistant's response text.
    Raises httpx.HTTPError on network/server errors (caller handles EC-8).
    """
    user_message = f"Context:\n{context}\n\nQuestion: {question}"

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        resp = client.post(
            "/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


def extract_cited_pages(answer_text: str) -> list[int]:
    """Extract page numbers from [Page N] citations in the LLM's answer."""
    return sorted({int(m) for m in re.findall(r"\[Page\s+(\d+)\]", answer_text, re.IGNORECASE)})
