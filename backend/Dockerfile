FROM python:3.11-slim AS base

WORKDIR /app

# System deps: tesseract for OCR (ENG-CPD-018), poppler-utils is not needed
# since PyMuPDF bundles its own PDF renderer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data/documents /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /data/documents /home/appuser/.cache

COPY pyproject.toml ./
# Install core + ML extras so app and worker images share one Dockerfile.
RUN pip install --no-cache-dir ".[ml]"

COPY app ./app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
