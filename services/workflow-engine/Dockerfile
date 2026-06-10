# syntax=docker/dockerfile:1.7
# ---------- builder ----------
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
# Install build deps for asyncpg / cryptography wheels, then purge in same layer
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --user --no-cache-dir .

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH=/home/wf/.local/bin:$PATH
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin wf
WORKDIR /app
COPY --from=builder /root/.local /home/wf/.local
COPY --chown=wf:wf . /app
USER wf
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys;\
        sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=2).status == 200 else sys.exit(1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
