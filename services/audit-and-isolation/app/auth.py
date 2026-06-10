"""Service-token authentication against the credential service.

Every inbound ``/v1/chat/completions`` request must carry an
``Authorization: Bearer <token>`` header. The gateway does **not**
verify the token locally — it forwards it to the credential
service's ``/v1/auth/verify`` endpoint and gets back the
``service_id`` (which is then written to ``audit_log.user_id``).

Why forward rather than verify locally? Because the credential
service is the single source of truth for which services are
allowed to call the gateway. Rotating a service's permission there
takes effect immediately, with no need to redeploy the gateway
just to refresh a public key.

Failure modes:

* **No ``Authorization`` header / wrong scheme** → 401. The
  gateway never reads the request body in this case (we want the
  ``detail`` to be visible to the caller, not the body).
* **Credential service unreachable / network error** → 503. The
  service is on the data-isolation egress path; if it's down the
  gateway cannot enforce token validity, so we fail closed.
* **Credential service returned non-200** → 401. The service's
  contract is binary (200 = valid, anything else = invalid); we
  do not parse the upstream body, we just propagate 401.

The token itself is **never** logged, persisted, or written to
the audit log. The audit log records ``service_id`` (a stable
identifier) but not the token. This matches the
"主密钥 / 凭证明文 MUST NOT 入 commit / log / audit" rule from
``CLAUDE.md``.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import Header, HTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)


async def verify_service_token(
    authorization: str | None = Header(default=None),
) -> str:
    """Verify the caller's service token; return its ``service_id``.

    The header is a FastAPI ``Header`` dependency so FastAPI's
    OpenAPI schema generation picks it up; the dependency returns
    the verified ``service_id`` (a plain string) and the chat
    endpoint stores it as the request's user identifier.

    Raises:

    * ``HTTPException(401)`` — missing / wrong-scheme header, or
      the credential service rejected the token.
    * ``HTTPException(503)`` — the credential service is
      unreachable (network error, timeout, DNS failure).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="missing Authorization: Bearer <token>"
        )
    token = authorization.removeprefix("Bearer ")
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{settings.credential_service_url}/v1/auth/verify",
                json={"token": token, "audience": "audit-and-isolation"},
            )
        except httpx.HTTPError as e:
            logger.error(f"credential service unreachable for token verify: {e}")
            raise HTTPException(status_code=503, detail="credential service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="invalid service token")
    data = resp.json()
    return data["service_id"]


__all__ = ["verify_service_token"]
