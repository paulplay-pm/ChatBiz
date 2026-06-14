"""V6a SSO: 建 3 表(sso_users + sso_sessions + sso_audit)。

Revision ID: 001_init
Revises:
Create Date: 2026-06-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sso_users
    op.create_table(
        "sso_users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("corp_external_id", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("idp_kind", sa.String(16), server_default="wechat", nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("role", sa.String(64), server_default="user", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
    )

    # sso_sessions
    op.create_table(
        "sso_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("sso_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jwt_jti", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
    )

    # sso_audit
    op.create_table(
        "sso_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("sso_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(64), index=True, nullable=False),
        sa.Column("error_class", sa.String(32), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            index=True,
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("sso_audit")
    op.drop_table("sso_sessions")
    op.drop_table("sso_users")
