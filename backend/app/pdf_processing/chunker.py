"""Text chunking — ENG-CPD-009.

Strategy: page-aligned chunks.  Each PDF page becomes one or more chunks so
that every chunk carries a single, authoritative page_number for citation
(ADR-CPD-001: page-bounded chunking with page_number/chunk_index per chunk).

For pages longer than MAX_CHARS we split on paragraph boundaries (double
newline) first, then on sentence-end punctuation, keeping chunks within the
target size range to avoid feeding the embedding model excessively long inputs
while preserving the page → citation mapping.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.pdf_processing.extractor import PageText

MAX_CHARS = 1_000   # soft upper bound per chunk
MIN_CHARS = 50      # discard chunks shorter than this (mostly whitespace/headers)


@dataclass
class TextChunk:
    page_number: int
    chunk_index: int
    text: str
    extraction_method: str


def chunk_pages(pages: list[PageText]) -> list[TextChunk]:
    """Convert a list of PageText objects into a flat list of TextChunk objects."""
    result: list[TextChunk] = []
    global_index = 0

    for page in pages:
        if not page.text:
            continue

        segments = _split_page(page.text)
        for segment in segments:
            if len(segment) < MIN_CHARS:
                continue
            result.append(
                TextChunk(
                    page_number=page.page_number,
                    chunk_index=global_index,
                    text=segment,
                    extraction_method=page.extraction_method,
                )
            )
            global_index += 1

    return result


def _split_page(text: str) -> list[str]:
    """Split a single page's text into chunks of at most MAX_CHARS characters,
    preferring paragraph and sentence boundaries."""
    if len(text) <= MAX_CHARS:
        return [text.strip()]

    # Try paragraph splits first (blank line = double newline)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= MAX_CHARS:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # Para itself might be over MAX_CHARS
            if len(para) > MAX_CHARS:
                chunks.extend(_split_on_sentences(para))
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks or [text[:MAX_CHARS]]


def _split_on_sentences(text: str) -> list[str]:
    """Crude sentence splitter for very long paragraphs."""
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= MAX_CHARS:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            current = s[:MAX_CHARS]
    if current:
        chunks.append(current)
    return chunks
