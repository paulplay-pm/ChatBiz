"""V6a SSO service: 3-table ORM models.

- sso_users: 本地 user(upsert by wechat_userid / oidc_sub / saml_nameid)
- sso_sessions: 每签发 1 个 JWT 写 1 行(防 replay + 支持 refresh 撤销)
- sso_audit: eng-review Quality #3 4 错误类埋点
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SsoUser(Base):
    __tablename__ = "sso_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 外部 IdP 唯一 id(企微 userid / OIDC sub / SAML NameID)
    corp_external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # 兼容 3-tier:V0 企微 / V1 OIDC / V2 SAML
    idp_kind: Mapped[str] = mapped_column(String(16), default="wechat")
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(64), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def to_jwt_claims(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "groups": [self.role],
        }


class SsoSession(Base):
    __tablename__ = "sso_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sso_users.id", ondelete="CASCADE"))
    # JWT jti (jose lib 生成)
    jwt_jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # refresh token SHA256(不存明文)
    refresh_token_hash: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SsoAudit(Base):
    __tablename__ = "sso_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sso_users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    # 4 错误类(eng-review Quality #3):security / user / runtime / internal
    error_class: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
