"""V6a SSO service: 4 端点 routers.

- POST /api/v1/auth/sso/wechat/initiate → {authorize_url, state}
- POST /api/v1/auth/sso/wechat/callback → {jwt, refresh, expires_in, user}
- POST /api/v1/auth/sso/refresh → {jwt, expires_in}
- GET  /api/v1/auth/sso/jwks.json → JWKS
- GET  /healthz → 200 iff DB OK
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..audit import write_audit_event
from ..jwt_utils import (
    SecurityError,
    UserError,
    WorkflowRuntimeError,
    encode_jwt,
    get_jwks,
)
from ..user import get_user_by_id, upsert_sso_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/sso")


# --- /initiate ---
@router.post("/wechat/initiate")
async def wechat_initiate(request: Request):
    wechat = request.app.state.wechat
    if not wechat._available:  # noqa: SLF001 (V6a dev 简化)
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "sso.wechat_unavailable",
                    "message": "企微服务未配置",
                }
            },
        )
    # 写 audit(initiate)
    state = secrets.token_urlsafe(16)
    redis = request.app.state.redis
    await redis.setex(f"sso:state:{state}", 300, "1")  # TTL 5min
    db = request.app.state.db_sessionmaker()
    async with db() as session:
        await write_audit_event(session, event_type="initiate")
    return {"authorize_url": wechat.get_authorize_url(state), "state": state}


# --- /callback ---
@router.post("/wechat/callback")
async def wechat_callback(request: Request):
    body = await request.json()
    code = body.get("code")
    state = body.get("state")
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "user.invalid_input", "message": "缺 code/state"}},
        )
    redis = request.app.state.redis
    state_key = f"sso:state:{state}"
    if not await redis.get(state_key):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "security.invalid_state", "message": "state 失配或过期"}},
        )
    await redis.delete(state_key)

    wechat = request.app.state.wechat
    try:
        access_token, openid = await wechat.exchange_code(code)
    except UserError as e:
        raise HTTPException(400, detail={"error": {"code": e.code, "message": str(e)}})
    except WorkflowRuntimeError as e:
        raise HTTPException(502, detail={"error": {"code": e.code, "message": str(e)}})

    try:
        userinfo = await wechat.fetch_userinfo(access_token, openid)
    except WorkflowRuntimeError as e:
        raise HTTPException(502, detail={"error": {"code": e.code, "message": str(e)}})

    # upsert user
    db = request.app.state.db_sessionmaker()
    async with db() as session:
        user = await upsert_sso_user(
            session, corp_external_id=openid, name=userinfo.get("name", "")
        )
        # mint JWT
        private_key = request.app.state.rsa_private
        token, jti, expires_in = encode_jwt(
            private_key, user.id, user.to_jwt_claims()
        )
        # 写 sso_session
        from ..models import SsoSession

        refresh = secrets.token_urlsafe(48)
        session.add(
            SsoSession(
                user_id=user.id,
                jwt_jti=jti,
                refresh_token_hash=hashlib.sha256(refresh.encode()).hexdigest(),
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
        )
        await write_audit_event(
            session, event_type="login_success", user_id=user.id
        )
        await session.commit()

    return {
        "jwt": token,
        "refresh": refresh,
        "expires_in": expires_in,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    }


# --- /refresh ---
@router.post("/refresh")
async def refresh_token(request: Request):
    body = await request.json()
    refresh = body.get("refresh")
    if not refresh:
        raise HTTPException(
            400, detail={"error": {"code": "user.invalid_input", "message": "缺 refresh"}}
        )
    refresh_hash = hashlib.sha256(refresh.encode()).hexdigest()
    db = request.app.state.db_sessionmaker()
    async with db() as session:
        from ..models import SsoSession

        # V6a:SQLAlchemy 2.x 异步惯用写法 — select().where().first() 自动 await
        # 兼容 sync / async session(测试用 sync MM)
        from sqlalchemy import select as sa_select
        result = await session.execute(
            sa_select(SsoSession).where(SsoSession.refresh_token_hash == refresh_hash)
        )
        # Result.first() 在 AsyncSession 返 awaitable;sync session 返 sync
        first = result.first()
        if asyncio.iscoroutine(first):
            row = await first
        else:
            row = first
        if row is None or row.revoked_at is not None or row.expires_at < datetime.utcnow():
            raise HTTPException(
                401, detail={"error": {"code": "security.token_expired", "message": "refresh 失效"}}
            )
        user = await get_user_by_id(session, row.user_id)
        if user is None:
            raise HTTPException(401, detail={"error": {"code": "security.invalid_token", "message": "user 缺失"}})
        token, jti, expires_in = encode_jwt(
            request.app.state.rsa_private, user.id, user.to_jwt_claims()
        )
        # 写新 session
        session.add(
            SsoSession(
                user_id=user.id,
                jwt_jti=jti,
                refresh_token_hash=refresh_hash,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
        )
        await session.commit()
    return {"jwt": token, "expires_in": expires_in}


# --- /jwks.json ---
@router.get("/jwks.json")
async def jwks(request: Request):
    return get_jwks(request.app.state.rsa_public)


# --- /healthz ---
@router.get("/healthz")
async def healthz(request: Request):
    db = request.app.state.db_sessionmaker()
    try:
        async with db() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )
