from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.config import get_settings
from app.errors.middleware import chatbiz_error_handler, generic_exception_handler
from app.errors.classes import ChatBizError
from app.cron.lifespan import lifespan
from app.api.workflows import router as workflows_router
from app.api.validate import router as validate_router
from app.api.run import router as run_router
from app.api.runs import router as runs_router
from app.api.approvals import router as approvals_router
from app.api.nodes import router as nodes_router
from app.api.health import router as health_router

settings = get_settings()

app = FastAPI(
    title="ChatBiz Workflow Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(ChatBizError, chatbiz_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Routers
app.include_router(health_router)
app.include_router(workflows_router)
app.include_router(validate_router)
app.include_router(run_router)
app.include_router(runs_router)
app.include_router(approvals_router)
app.include_router(nodes_router)
