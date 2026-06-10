"""Client for the credential service.

The credential service owns the user→credential ACL: which user can
use which API key / OAuth token for which LLM provider. The workflow
engine must call ``check_access`` *before* binding a credential to a
node execution — a node that uses a credential the caller doesn't
have access to is a security violation, not a runtime error.

The status-code contract:

* ``200`` → user has access (caller may proceed).
* ``403`` → user does **not** have access (caller must surface
  ``SecurityError`` / 403 to the API client).
* ``404`` → the credential itself does not exist. We raise
  ``SecurityError`` because from the caller's perspective "credential
  does not exist" and "user cannot use this credential" are both
  security-domain failures and must not leak existence information
  to the API client.
* Any other status → propagated via ``raise_for_status()`` as
  ``httpx.HTTPStatusError``.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.errors.classes import SecurityError


class CredentialClient:
    """Client for credential service: check user access to credentials."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            s = get_settings()
            self._client = httpx.AsyncClient(
                base_url=s.credential_service_url,
                timeout=httpx.Timeout(10.0, connect=3.0),
                headers={"X-Service-Token": s.workflow_engine_service_token},
            )
        return self._client

    async def check_access(self, credential_id: str, user_id: str) -> bool:
        """Return True if user has access, False otherwise.

        Raises ``SecurityError`` (our custom class) on 404 (credential
        does not exist) — see module docstring for why we collapse
        404 into the security domain.
        """
        c = await self._get_client()
        r = await c.get(
            f"/v1/credentials/{credential_id}/access",
            params={"user_id": user_id},
        )
        if r.status_code == 200:
            return True
        if r.status_code == 403:
            return False
        if r.status_code == 404:
            raise SecurityError(f"凭证 {credential_id} 不存在")
        r.raise_for_status()
        return False

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


__all__ = ["CredentialClient"]
