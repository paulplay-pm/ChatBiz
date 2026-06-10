"""ASGI entrypoint for the credential-management service.

Wires the FastAPI application:

* ``lifespan`` — loads the master key + DB engine + Redis client,
  aborts with ``sys.exit(1)`` if the master key is missing per spec
  §主密钥缺失.
* CORS — permissive defaults; production deployments tighten this via
  an environment variable list.
* Global exception handlers — map every domain exception from
  ``app.services`` / ``app.permissions`` / ``app.rate_limit`` to the
  correct HTTP status with a stable JSON body.
* ``/healthz`` — 200 iff the DB is reachable (used by k8s readiness).

Routers register at ``/api/v1/credentials`` per spec.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.lifespan import lifespan
from app.permissions import PermissionDeniedError
from app.rate_limit import RateLimitExceededError
from app.routers import credentials as credentials_router
from app.services import (
    CredentialExpiredError,
    CredentialNotFoundError,
    WorkspaceMismatchError,
)

logger = logging.getLogger(__name__)


def _err(message: str, code: str) -> dict[str, Any]:
    """Stable error envelope shared by every handler."""
    return {"error": {"code": code, "message": message}}


def create_app() -> FastAPI:
    """Application factory.

    A factory (rather than a module-level singleton) keeps test
    isolation easy: each test that wants a fresh app calls
    ``create_app()`` and overrides dependencies on its private
    instance. Production uses ``app = create_app()`` below for
    ``uvicorn app.main:app``.
    """
    app = FastAPI(
        title="ChatBiz Credential Management",
        version="0.1.0",
        lifespan=lifespan,
    )

    cors_origins = [
        o.strip()
        for o in os.environ.get("CREDENTIAL_CORS_ORIGINS", "*").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(credentials_router.router)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/healthz")
    async def healthz(request: Request) -> dict[str, str]:
        """200 if a trivial ``SELECT 1`` round-trips through the engine."""
        engine = request.app.state.engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------

    @app.exception_handler(CredentialNotFoundError)
    async def _not_found(_request: Request, exc: CredentialNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_err(str(exc), "credential_not_found"),
        )

    @app.exception_handler(CredentialExpiredError)
    async def _expired(_request: Request, exc: CredentialExpiredError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_410_GONE,
            content=_err(str(exc), "credential_expired"),
        )

    @app.exception_handler(WorkspaceMismatchError)
    async def _ws_mismatch(_request: Request, exc: WorkspaceMismatchError) -> JSONResponse:
        # We deliberately surface a 403 (not 404) for workspace mismatch:
        # the credential id exists, the caller just lacks access. Hiding
        # the existence under a 404 would defeat audit-log correlation.
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_err(str(exc), "workspace_mismatch"),
        )

    @app.exception_handler(PermissionDeniedError)
    async def _perm(_request: Request, exc: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_err(str(exc), "permission_denied"),
        )

    @app.exception_handler(RateLimitExceededError)
    async def _ratelimit(
        _request: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=_err(str(exc), "rate_limit_exceeded"),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    return app


# Production entrypoint. Tests build their own app via ``create_app()``.
app = create_app()


__all__ = ["app", "create_app"]
