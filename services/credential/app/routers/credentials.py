"""HTTP endpoints for credential CRUD + rotate + reveal + use.

Thin router layer — every endpoint is essentially:

    1. parse request (FastAPI does it from the Pydantic schema)
    2. construct ``CredentialService`` with the current ``AsyncSession``
       + the in-memory master key
    3. call one service method
    4. return the response model

Business logic lives in ``app.services``; SQL lives there too. The
router only knows about HTTP-level concerns: header parsing for the
``User``, RBAC checks, rate-limiting, and translating service-layer
exceptions (handled globally in ``app.main``).

Authentication for MVP is header-based per design.md D12:

* ``X-User-Id``         — opaque user id string
* ``X-User-Workspace``  — workspace_id this request is scoped to
* ``X-User-Roles``      — comma-separated role strings; ``admin``
                          implies ``User.is_admin = True``

Full SSO replaces this in the system-management cap (post-MVP); the
internal API surface remains the same.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CredentialType
from app.permissions import (
    User,
    check_credential_read,
    check_credential_reveal,
    check_credential_use,
    check_credential_write,
)
from app.rate_limit import RedisLike, check_reveal_quota
from app.schemas import (
    DEFAULT_PAGE_SIZE,
    CredentialCreateRequest,
    CredentialDetailResponse,
    CredentialListResponse,
    CredentialResponse,
    CredentialRevealResponse,
    CredentialRotateRequest,
    CredentialUseRequest,
    CredentialUseResponse,
)
from app.services import CredentialService

router = APIRouter(prefix="/api/v1/credentials", tags=["credentials"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a fresh ``AsyncSession`` per request; commit on success.

    Mirrors the FastAPI cookbook pattern for SQLAlchemy 2.x async:
    one session per request, wrapped in a ``begin()`` block so an
    unhandled exception rolls back the transaction (including any
    half-written audit row).
    """
    factory = request.app.state.session_factory
    async with factory() as session:
        async with session.begin():
            yield session


def get_master_key(request: Request) -> bytes:
    """Pull the unwrapped master key out of ``app.state``."""
    key = request.app.state.master_key
    assert isinstance(key, bytes)
    return key


def get_redis(request: Request) -> RedisLike | None:
    """Return the shared Redis client (or ``None`` if disabled)."""
    redis = request.app.state.redis
    return redis  # type: ignore[no-any-return]


def get_current_user(
    x_user_id: str = Header(..., alias="X-User-Id", min_length=1, max_length=64),
    x_user_workspace: str = Header(
        ..., alias="X-User-Workspace", min_length=1, max_length=64
    ),
    x_user_roles: str = Header("", alias="X-User-Roles", max_length=512),
) -> User:
    """Build a ``User`` from request headers (MVP auth).

    ``X-User-Roles`` is a comma-separated list; the well-known role
    ``admin`` toggles ``User.is_admin``. Anything else flows through
    as a plain role string for the permissions module.
    """
    roles = [r.strip() for r in x_user_roles.split(",") if r.strip()]
    return User(
        user_id=x_user_id,
        roles=roles,
        workspace_id=x_user_workspace,
        is_admin="admin" in roles,
    )


def get_service(
    session: AsyncSession = Depends(get_session),
    master_key: bytes = Depends(get_master_key),
) -> CredentialService:
    """Construct a per-request ``CredentialService`` instance."""
    return CredentialService(session=session, master_key=master_key)


# Permission dependencies — these are simple wrappers so each route can
# declare its required permission as a one-liner ``Depends(...)``.
def require_read(user: User = Depends(get_current_user)) -> User:
    check_credential_read(user)
    return user


def require_use(user: User = Depends(get_current_user)) -> User:
    check_credential_use(user)
    return user


def require_write(user: User = Depends(get_current_user)) -> User:
    check_credential_write(user)
    return user


def require_reveal(user: User = Depends(get_current_user)) -> User:
    check_credential_reveal(user)
    return user


async def reveal_rate_limit(
    user: User = Depends(require_reveal),
    redis: RedisLike | None = Depends(get_redis),
) -> None:
    """FastAPI dependency: enforce per-user reveal quota.

    Fails open if no Redis is configured — see ``rate_limit.py`` for
    the rationale.
    """
    if redis is None:
        return
    await check_reveal_quota(redis, user.user_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_credential(
    req: CredentialCreateRequest,
    service: CredentialService = Depends(get_service),
    user: User = Depends(require_write),
) -> CredentialResponse:
    """Create a credential. Requires ``credential_admin`` or admin."""
    return await service.create(req, user_id=user.user_id)


@router.get(
    "",
    response_model=CredentialListResponse,
)
async def list_credentials(
    type: CredentialType | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    service: CredentialService = Depends(get_service),
    user: User = Depends(require_read),
) -> CredentialListResponse:
    """Paginated list scoped to the caller's workspace."""
    return await service.list(
        workspace_id=user.workspace_id,
        type=type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{credential_id}",
    response_model=CredentialDetailResponse,
)
async def get_credential(
    credential_id: str = Path(..., min_length=1, max_length=32),
    service: CredentialService = Depends(get_service),
    user: User = Depends(require_read),
) -> CredentialDetailResponse:
    """Read a single credential (masked value)."""
    return await service.get(credential_id, workspace_id=user.workspace_id)


@router.post(
    "/{credential_id}/rotate",
    response_model=CredentialResponse,
)
async def rotate_credential(
    req: CredentialRotateRequest,
    credential_id: str = Path(..., min_length=1, max_length=32),
    service: CredentialService = Depends(get_service),
    user: User = Depends(require_write),
) -> CredentialResponse:
    """Rotate: write new value, move old → ``previous_*`` for 30 d."""
    return await service.rotate(credential_id, req, user_id=user.user_id)


@router.post(
    "/{credential_id}/reveal",
    response_model=CredentialRevealResponse,
)
async def reveal_credential(
    credential_id: str = Path(..., min_length=1, max_length=32),
    service: CredentialService = Depends(get_service),
    user: User = Depends(require_reveal),
    _rl: None = Depends(reveal_rate_limit),
) -> CredentialRevealResponse:
    """Return plaintext — admin-only, rate-limited 10/min/user."""
    return await service.reveal(credential_id, user_id=user.user_id)


@router.post(
    "/{credential_id}/use",
    response_model=CredentialUseResponse,
)
async def use_credential(
    req: CredentialUseRequest,
    credential_id: str = Path(..., min_length=1, max_length=32),
    service: CredentialService = Depends(get_service),
    user: User = Depends(require_use),
) -> CredentialUseResponse:
    """Internal API: return plaintext to a calling cap (with audit)."""
    return await service.use(
        credential_id,
        req,
        user_id=user.user_id,
        workspace_id=user.workspace_id,
    )


@router.delete(
    "/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_credential(
    credential_id: str = Path(..., min_length=1, max_length=32),
    service: CredentialService = Depends(get_service),
    user: User = Depends(require_write),
) -> Response:
    """Hard-delete the credential. Audit row survives."""
    await service.delete(
        credential_id, workspace_id=user.workspace_id, user_id=user.user_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router", "get_session", "get_current_user", "get_service"]
