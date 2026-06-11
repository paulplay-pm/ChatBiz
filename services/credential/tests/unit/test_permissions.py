"""Unit tests for ``app.permissions`` — RBAC permission checks."""

from __future__ import annotations

import pytest

from app.permissions import (
    PermissionDeniedError,
    User,
    check_credential_read,
    check_credential_reveal,
    check_credential_use,
    check_credential_write,
)


def _make_user(
    user_id: str = "u-1",
    is_admin: bool = False,
    roles: list[str] | None = None,
    workspace_id: str = "finance",
) -> User:
    return User(
        user_id=user_id,
        is_admin=is_admin,
        roles=roles or [],
        workspace_id=workspace_id,
    )


class TestCheckCredentialRead:
    def test_read_with_user_id_passes(self) -> None:
        check_credential_read(_make_user(user_id="u-1"))
        # No exception = pass

    def test_read_no_user_id_raises(self) -> None:
        with pytest.raises(PermissionDeniedError, match="authenticated user required"):
            check_credential_read(_make_user(user_id=""))


class TestCheckCredentialUse:
    def test_use_with_user_id_passes(self) -> None:
        check_credential_use(_make_user(user_id="u-1"))

    def test_use_no_user_id_raises(self) -> None:
        with pytest.raises(PermissionDeniedError, match="authenticated user required"):
            check_credential_use(_make_user(user_id=""))


class TestCheckCredentialWrite:
    def test_admin_passes(self) -> None:
        check_credential_write(_make_user(user_id="u-1", is_admin=True))

    def test_credential_admin_role_passes(self) -> None:
        check_credential_write(_make_user(user_id="u-1", roles=["credential_admin"]))

    def test_admin_and_credential_admin_passes(self) -> None:
        check_credential_write(
            _make_user(user_id="u-1", is_admin=True, roles=["credential_admin"])
        )

    def test_regular_user_raises(self) -> None:
        with pytest.raises(PermissionDeniedError, match="credential_write"):
            check_credential_write(_make_user(user_id="u-1"))

    def test_other_role_fails(self) -> None:
        with pytest.raises(PermissionDeniedError, match="credential_write"):
            check_credential_write(_make_user(user_id="u-1", roles=["viewer"]))

    def test_no_user_id_admin_fails(self) -> None:
        """Admin without user_id: write fails (read check would fail first)."""
        check_credential_write(_make_user(user_id="", is_admin=True))


class TestCheckCredentialReveal:
    def test_admin_passes(self) -> None:
        check_credential_reveal(_make_user(user_id="u-1", is_admin=True))

    def test_non_admin_raises(self) -> None:
        with pytest.raises(PermissionDeniedError, match="credential_reveal"):
            check_credential_reveal(_make_user(user_id="u-1"))

    def test_credential_admin_non_superadmin_raises(self) -> None:
        with pytest.raises(PermissionDeniedError, match="credential_reveal"):
            check_credential_reveal(
                _make_user(user_id="u-1", roles=["credential_admin"])
            )


class TestUser:
    def test_user_defaults(self) -> None:
        user = User(user_id="u-1", workspace_id="ws-1")
        assert user.roles == []
        assert user.is_admin is False

    def test_user_extra_field_raises(self) -> None:
        with pytest.raises(Exception):
            User(user_id="u-1", workspace_id="ws-1", bad="field")  # type: ignore[call-arg]


class TestPermissionDeniedError:
    def test_message_stored(self) -> None:
        exc = PermissionDeniedError("no access for you")
        assert exc.message == "no access for you"
        assert str(exc) == "no access for you"
