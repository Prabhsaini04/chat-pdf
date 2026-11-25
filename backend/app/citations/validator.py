"""Citation validation — ADR-CPD-002 (deterministic validation).

Validates that every page number cited in the LLM's answer actually exists
in the retrieved chunks.  Returns a citation_status string per ADR-CPD-002's
enumeration:

  grounded         — all cited pages are present in the retrieved context
  partial          — some cited pages are present; at least one is missing
                     (may indicate hallucinated page references)
  ungrounded       — none of the cited pages match the retrieved context, or
                     no citations were produced at all for a non-"not found" answer
  no_relevant_content — the LLM said it could not find the information
"""

from __future__ import annotations

_NOT_FOUND_PHRASE = "could not find relevant information"


def validate_citations(
    cited_pages: list[int],
    available_pages: list[int],
    answer_text: str,
) -> str:
    if _NOT_FOUND_PHRASE.lower() in answer_text.lower():
        return "no_relevant_content"

    if not cited_pages:
        return "ungrounded"

    available_set = set(available_pages)
    matched = [p for p in cited_pages if p in available_set]

    if len(matched) == len(cited_pages):
        return "grounded"
    if matched:
        return "partial"
    return "ungrounded"
