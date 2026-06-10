# syntax=docker/dockerfile:1.7
# ----------------------------------------------------------------------------
# credential-management service
# Multi-stage build: builder installs deps into a user prefix, runtime stage
# ships only the slim base + non-root user + source.
# `app/main:app` does not exist yet (Task 5); the image will build, but the
# default CMD will fail at `docker run` time until the FastAPI app is wired in.
# ----------------------------------------------------------------------------

# ---------- builder ---------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install build deps for any wheels that need compiling (e.g. cryptography
# on uncommon arches). Keep this layer small by copying requirements first.
COPY requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt


# ---------- runtime ---------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/credential/.local/bin:$PATH

# Create a non-root user. `--create-home` gives us $HOME for the
# `pip install --user` prefix shipped from the builder.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin credential

WORKDIR /app

# Copy the pip user-site (built in the builder stage) into the new user's
# $HOME, then chown the working tree to the non-root user.
COPY --from=builder /root/.local /home/credential/.local
COPY --chown=credential:credential . /app

USER credential

EXPOSE 8000

# Healthcheck is wired by docker-compose (depends_on: service_healthy).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; \
        sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else sys.exit(1)"]

# NOTE: `app.main:app` is created in Task 5. Until then the container will
# start uvicorn but fail with `ModuleNotFoundError: No module named 'app'`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
