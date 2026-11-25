FROM python:3.11-slim AS base

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
