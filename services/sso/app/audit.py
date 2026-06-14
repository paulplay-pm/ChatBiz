"""V6a SSO service: 审计埋点(eng-review Quality #3 4 错误边界).

write_audit_event: 4 错误类(security / user / runtime / internal)写 sso_audit
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import SsoAudit


async def write_audit_event(
    session: AsyncSession,
    event_type: str,
    user_id: Optional[int] = None,
    error_class: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """V6a 写 1 行 sso_audit。"""
    audit = SsoAudit(
        user_id=user_id,
        event_type=event_type,
        error_class=error_class,
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    session.add(audit)
    await session.flush()
