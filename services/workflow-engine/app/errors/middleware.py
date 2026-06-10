"""FastAPI exception handlers — map typed ChatBiz errors to {error_class, error_message} JSON."""
from fastapi import Request
from fastapi.responses import JSONResponse
from app.errors.classes import (
    ChatBizError, SecurityError, UserError, WorkflowRuntimeError,
)
import logging, uuid
log = logging.getLogger(__name__)


async def chatbiz_error_handler(request: Request, exc: ChatBizError):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    log.warning(f"ChatBiz error {exc.error_class} [{request_id}]: {exc.message}")
    status = 422 if exc.error_class == "user" else (403 if exc.error_class == "security" else 502)
    return JSONResponse(
        status_code=status,
        content={"error_class": exc.error_class, "error_message": exc.message, "request_id": request_id},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    log.exception(f"Unhandled error [{request_id}]")
    return JSONResponse(
        status_code=500,
        content={"error_class": "internal", "error_message": "internal server error", "request_id": request_id},
    )
