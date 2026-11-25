"""PDF text extraction — ENG-CPD-009 (direct) and ENG-CPD-018 (OCR fallback).

Strategy per ADR-CPD-001:
  1. Try direct text extraction with PyMuPDF (fast, preserves layout).
  2. If a page yields no usable text (< MIN_CHARS), fall back to Tesseract OCR
     for that page (scanned/image-only PDFs — REQ-002/OQ-6).
  3. If OCR also yields nothing, the page is marked empty; the document is still
     processed (the other pages may have text).

Returns a list of PageText objects, one per PDF page, with the extraction
method recorded so it can be stored in the Chunk.extraction_method field.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_CHARS_FOR_DIRECT = 20  # below this, treat the page as image-only


@dataclass
class PageText:
    page_number: int    # 1-indexed, matching the citation requirement
    text: str
    extraction_method: str  # "direct" | "ocr" | "empty"


def extract_pages(pdf_path: str) -> list[PageText]:
    """Extract text from every page of the PDF at `pdf_path`.
    Returns one PageText per page (empty pages included, with extraction_method="empty").
    Raises ValueError if the file cannot be opened as a PDF.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError("PyMuPDF (pymupdf) is not installed.") from e

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Cannot open PDF: {e}") from e

    results: list[PageText] = []
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_number = page_index + 1

        text = page.get_text().strip()
        if len(text) >= MIN_CHARS_FOR_DIRECT:
            results.append(PageText(page_number, text, "direct"))
            continue

        # Try OCR for this page
        ocr_text = _ocr_page(page)
        if ocr_text:
            results.append(PageText(page_number, ocr_text, "ocr"))
        else:
            results.append(PageText(page_number, "", "empty"))

    doc.close()
    return results


def _ocr_page(page: object) -> str:  # page is a fitz.Page
    """Rasterize the page and run Tesseract OCR on it.
    Returns the extracted text, or empty string on failure/unavailability.
    """
    try:
        import fitz
        import pytesseract
        from PIL import Image

        mat = fitz.Matrix(2.0, 2.0)  # 2× zoom → ~144 DPI, good for OCR
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return pytesseract.image_to_string(img).strip()
    except Exception:
        # Tesseract not installed, image conversion failed, etc. — treat as empty.
        return ""
