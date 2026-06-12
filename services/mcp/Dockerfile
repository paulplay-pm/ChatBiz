# syntax=docker/dockerfile:1.7
# ---------- builder ----------
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --user --no-cache-dir .

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH=/home/mcp/.local/bin:$PATH
RUN useradd --create-home --uid 10003 --shell /usr/sbin/nologin mcp
WORKDIR /app
COPY --from=builder /root/.local /home/mcp/.local
COPY --chown=mcp:mcp . /app
USER mcp
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status==200 else sys.exit(1)"]
CMD ["python", "-m", "app.main"]