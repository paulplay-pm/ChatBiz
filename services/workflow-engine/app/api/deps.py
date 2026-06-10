"""Shared FastAPI dependencies for the workflow-engine HTTP layer.

Currently this module owns the ``get_user_id`` dependency used by every
router to resolve the caller identity. The dependency accepts either:

1. ``Authorization: Bearer <jwt>`` — preferred (production / canvas UI).
   Decoded without signature verification in MVP (token issued by the
   trusted internal IAM/Keycloak). The ``sub`` claim becomes the
   ``user_id``. ``exp`` is still verified, so expired tokens are 401.
2. ``X-User-Id`` header — dev fallback for local scripts and ad-hoc
   curl-style calls.

Production deployments (V1.0+) MUST configure a JWT secret and switch
to ``verify_signature=True``; the upgrade point is the single
``jwt.decode`` call below.
"""
from __future__ import annotations

from fastapi import Header, HTTPException

import jwt
from jwt import PyJWTError


async def get_user_id(
    authorization: str | None = Header(None, alias="Authorization"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
) -> str:
    """Resolve ``user_id`` from request, preferring JWT Bearer token.

    Priority:
      1. ``Authorization: Bearer <jwt>`` — decode (signature NOT verified
         in MVP, but ``exp`` IS verified). The ``sub`` claim is returned.
      2. ``X-User-Id`` header — dev mode fallback.
      3. Neither — 401 with structured ``error_class=security`` body.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            # MVP: do not verify signature (token issued by trusted
            # internal IAM). TODO V1.0: configure JWT_SECRET and set
            # verify_signature=True.
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True},
            )
            sub = payload.get("sub")
            if sub:
                return str(sub)
            raise HTTPException(
                status_code=401,
                detail={
                    "error_class": "security",
                    "error_message": "JWT missing 'sub' claim",
                },
            )
        except PyJWTError as e:
            raise HTTPException(
                status_code=401,
                detail={
                    "error_class": "security",
                    "error_message": f"invalid JWT: {e}",
                },
            )

    if x_user_id:
        return x_user_id

    raise HTTPException(
        status_code=401,
        detail={
            "error_class": "security",
            "error_message": "缺少 Authorization Bearer 或 X-User-Id header",
        },
    )


__all__ = ["get_user_id"]
