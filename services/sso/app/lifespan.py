"""V6a SSO service: lifespan — DB engine + Redis client + RSA 密钥 load/generate.

启动时:
1. 读 WECHAT_* env(缺失时 wechat client 不可用,initiate 返 503)
2. 读 POSTGRES_DSN + 创建 async engine + sessionmaker
3. 读 REDIS_URL + 创建 async Redis client(存 CSRF state)
4. RSA 私钥 load_or_generate(首次启动 generate 2048-bit + 持久化)
5. 写 startup banner 到 log

所有资源挂到 app.state,endpoints 通过 Request.app.state 访问。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as redis_async
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .jwt_utils import load_or_generate_keypair
from .wechat import WeChatClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """V6a SSO 启动 + 关闭。"""
    # 1. 企微 client(env 缺失时 corp_id 空,后续 initiate 返 503)
    app.state.wechat = WeChatClient(
        corp_id=os.getenv("WECHAT_CORP_ID", ""),
        agent_id=os.getenv("WECHAT_AGENT_ID", ""),
        corp_secret=os.getenv("WECHAT_SECRET", ""),
        redirect_uri=os.getenv(
            "WECHAT_REDIRECT_URI", "http://localhost:5173/portal/sso-callback"
        ),
    )

    # 2. Postgres async engine(复用 chatbiz-postgres)
    dsn = os.getenv(
        "POSTGRES_DSN",
        "postgresql+asyncpg://chatbiz:chatbiz@chatbiz-postgres:5432/chatbiz",
    )
    engine = create_async_engine(dsn, echo=False, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker

    # 3. Redis(CSRF state 存)
    redis_url = os.getenv("REDIS_URL", "redis://chatbiz-redis:6379/0")
    app.state.redis = redis_async.from_url(redis_url, decode_responses=True)

    # 4. RSA 私钥 load_or_generate
    private_path = Path(os.getenv("JWT_PRIVATE_KEY_PATH", "~/.sso/secrets/jwt_private.pem")).expanduser()
    public_path = Path(os.getenv("JWT_PUBLIC_KEY_PATH", "~/.sso/secrets/jwt_public.pem")).expanduser()
    private_key, public_key = load_or_generate_keypair(private_path, public_path)
    app.state.rsa_private = private_key
    app.state.rsa_public = public_key

    logger.info("V6a chatbiz-sso lifespan started")
    yield
    # 关闭
    await engine.dispose()
    await app.state.redis.aclose()
    logger.info("V6a chatbiz-sso lifespan stopped")
