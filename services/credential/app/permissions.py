"""Permission checks for the credential-management service.

This module defines a minimal RBAC model scoped to credential operations.
For MVP the checks are role-string-based (``is_admin`` or
``credential_admin``); the HTTP layer (Task 5) is responsible for
injecting the ``User`` object from request headers / JWT.

Design rationale (from ``design.md`` D12):

* Read + Use: anyone in the workspace may read credential metadata
  and request the plaintext for an internal cap.
* Write (create / rotate / delete): admin or ``credential_admin`` role
  only.
* Reveal (plaintext exposed to an external caller): admin only.

Future iterations (V1.0+) will wire this into the platform's full RBAC
engine; for now we keep it simple and explicit.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# User model (injected by HTTP layer)
# ---------------------------------------------------------------------------


class User(BaseModel):
    """The authenticated user, as understood by the credential service.

    Fields are populated from request headers / JWT by the HTTP layer
    (Task 5). In tests the caller constructs the ``User`` directly.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    roles: list[str] = []
    workspace_id: str
    is_admin: bool = False


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PermissionDeniedError(Exception):
    """Raised when a user lacks the required permission for an operation.

    The HTTP layer (Task 5) maps this to a 403 response.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------


def check_credential_read(user: User) -> None:
    """Anyone in the workspace may read credential metadata.

    The HTTP layer enforces workspace-id matching separately; this check
    only ensures the user is authenticated (which they are if they have
    a ``User`` object). There is no anonymous access in this service.
    """
    if not user.user_id:
        raise PermissionDeniedError("authenticated user required to read credentials")


def check_credential_use(user: User) -> None:
    """Anyone in the workspace may use a credential (internal API).

    ``use`` is the internal API that returns the plaintext value to
    another service cap (workflow engine, knowledge-base sync, etc.).
    It requires workspace membership but not admin privileges.
    """
    if not user.user_id:
        raise PermissionDeniedError("authenticated user required to use credentials")


def check_credential_write(user: User) -> None:
    """Admin or ``credential_admin`` role may write (create / rotate / delete).

    Raises ``PermissionDeniedError`` if the user has neither the
    ``is_admin`` flag nor the ``credential_admin`` role string.
    """
    if user.is_admin:
        return
    if "credential_admin" in user.roles:
        return
    raise PermissionDeniedError(
        f"user {user.user_id} lacks credential_write permission "
        f"(need admin or credential_admin role)"
    )


def check_credential_reveal(user: User) -> None:
    """Only admin may reveal a credential (plaintext via reveal API).

    The reveal API exposes the plaintext value over HTTP to a human
    operator; the spec requires admin-level access plus per-user rate
    limiting (Task 6 HTTP layer).
    """
    if not user.is_admin:
        raise PermissionDeniedError(
            f"user {user.user_id} lacks credential_reveal permission (need admin)"
        )


__all__ = [
    "User",
    "PermissionDeniedError",
    "check_credential_read",
    "check_credential_use",
    "check_credential_write",
    "check_credential_reveal",
]
