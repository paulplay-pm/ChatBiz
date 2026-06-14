"""V6a SSO service: ASGI entrypoint — create_app factory + 4 错误边界 exception handlers.

完全重写 credential main.py:V6a 不需 crypto/notifications/permissions/rate_limit/credentials router。
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .jwt_utils import SecurityError, UserError, WorkflowRuntimeError, InternalError
from .lifespan import lifespan
from .routers import sso as sso_router

logger = logging.getLogger(__name__)


def _err(message: str, code: str) -> dict:
    """4 错误边界稳定 envelope(eng-review Quality #3 锁定)。"""
    return {"error": {"code": code, "message": message}}


def create_app() -> FastAPI:
    app = FastAPI(title="chatbiz-sso", version="0.1.0", lifespan=lifespan)

    # CORS(dev 宽松,prod 收紧)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4 错误边界(eng-review Quality #3)
    @app.exception_handler(SecurityError)
    async def _sec(req: Request, e: SecurityError):
        if "expired" in e.code or "invalid_token" in e.code or "unauthorized" in e.code:
            status = 401
        else:
            status = 403
        return JSONResponse(status_code=status, content=_err(str(e), e.code))

    @app.exception_handler(UserError)
    async def _usr(req: Request, e: UserError):
        return JSONResponse(status_code=400, content=_err(str(e), e.code))

    @app.exception_handler(WorkflowRuntimeError)
    async def _rt(req: Request, e: WorkflowRuntimeError):
        if "timeout" in e.code:
            status = 504
        else:
            status = 502
        return JSONResponse(status_code=status, content=_err(str(e), e.code))

    @app.exception_handler(InternalError)
    async def _int(req: Request, e: InternalError):
        return JSONResponse(status_code=500, content=_err(str(e), e.code))

    app.include_router(sso_router.router)
    return app


# Production entrypoint.
app = create_app()
