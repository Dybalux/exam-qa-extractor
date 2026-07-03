FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Stage 1: system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-spa libmagic1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Python deps (cached independently of source)
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .          # production-only; skips [dev]

# Stage 3: non-root user (UID 1000)
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 \
        --shell /bin/bash --create-home app

# Stage 4: app code + migrations
COPY --chown=app:app docker/entrypoint.sh /app/docker/entrypoint.sh
COPY --chown=app:app app/            /app/app/
RUN chmod +x /app/docker/entrypoint.sh

# Stage 5: runtime
RUN mkdir -p /app/data/db /app/data/uploads /app/data/backups \
    && chown -R app:app /app/data
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=2).status==200 else 1)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
