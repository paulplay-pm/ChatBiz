"""V6a SSO service: 本地 user upsert from 企微 userid.

upsert_sso_user: 首次创建 + 后续更新 last_login_at
get_user_by_id: refresh 续期用
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SsoUser


async def upsert_sso_user(
    session: AsyncSession,
    corp_external_id: str,
    name: str,
    email: Optional[str] = None,
    idp_kind: str = "wechat",
) -> SsoUser:
    """V6a V0 企微 upsert: by corp_external_id(openid)。"""
    result = await session.execute(
        select(SsoUser).where(SsoUser.corp_external_id == corp_external_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = SsoUser(
            corp_external_id=corp_external_id,
            idp_kind=idp_kind,
            name=name,
            email=email,
            role="user",
            last_login_at=datetime.utcnow(),
        )
        session.add(user)
        await session.flush()
    else:
        # 更新名字 / 邮箱 / last_login_at
        if name:
            user.name = name
        if email:
            user.email = email
        user.last_login_at = datetime.utcnow()
        await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[SsoUser]:
    result = await session.execute(select(SsoUser).where(SsoUser.id == user_id))
    return result.scalar_one_or_none()
