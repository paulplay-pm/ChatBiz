"""7-class exception taxonomy for the audit-and-isolation service.

The gateway maps every error condition a caller can hit (or an
operator will see in logs) onto one of the seven classes below. Each
class is caught at the API boundary (see ``app/api/chat.py``) and
turned into a typed HTTP status + ``ErrorResponse`` envelope.

The classes mirror the *boundary* the error came from, not the
underlying library exception:

* ``PIIDetectorUnavailable`` — internal PII detector raised (regex
  or validator crashed). The gateway's policy is Fail-Open unless
  ``settings.pii_fail_open`` is set to ``False`` (deployable
  override for high-risk tenants).
* ``Upstream5xx`` — upstream LLM provider returned 5xx. Mapped to
  502 Bad Gateway. Retried once inside the LLM client; the second
  attempt's 5xx is what reaches this class.
* ``UpstreamTimeout`` — upstream call exceeded the per-route
  ``timeout_ms``. Mapped to 504.
* ``UpstreamRateLimited`` — upstream returned 429. Mapped to 429.
  The gateway does *not* retry 429s; the caller is expected to
  back off.
* ``CredentialServiceUnavailable`` — credential service unreachable
  or returned 503. Mapped to 503.
* ``RedisUnavailable`` — Redis pool exhausted or call failed. The
  redactor and reverser each have their own Fail-Open paths, so
  this is rare in practice; it surfaces when a hot path needs
  Redis and the local pool is down.
* ``AuthFailed`` — credential service rejected the caller's
  service token (401). Mapped to 401. Distinct from "credential
  service is down" so the gateway can surface the right alert
  metric.

Plus one helper, :func:`error_response`, that builds the body the
FastAPI exception handler returns. Centralising the envelope here
guarantees every error path emits the same shape (the eng-review
report locked the ``{error_class, message, trace_id}`` triple as
the contract; this module is the only place that triple is built).
"""

from __future__ import annotations

import logging

from app.models.common import ErrorResponse

logger = logging.getLogger(__name__)


class PIIDetectorUnavailable(Exception):
    """PII detector raised an unexpected exception during ``detect()``."""


class Upstream5xx(Exception):
    """Upstream LLM provider returned a 5xx response after retry."""


class UpstreamTimeout(Exception):
    """Upstream LLM provider call exceeded the per-route ``timeout_ms``."""


class UpstreamRateLimited(Exception):
    """Upstream LLM provider returned 429."""


class CredentialServiceUnavailable(Exception):
    """Credential service unreachable or returned 503 after retry."""


class RedisUnavailable(Exception):
    """Redis pool exhausted or call failed in a hot path."""


class AuthFailed(Exception):
    """Credential service rejected the caller's service token."""


def error_response(
    status: int, error_class: str, message: str, trace_id: str | None = None
) -> dict:
    """Build a uniform error envelope for FastAPI exception handlers.

    Returns a dict with ``status_code`` (the HTTP status the handler
    will use) and ``body`` (the serialised ``ErrorResponse``). The
    handler should do ``return JSONResponse(**error_response(...))``
    or equivalent.
    """
    return {
        "status_code": status,
        "body": ErrorResponse(
            error_class=error_class, message=message, trace_id=trace_id
        ).model_dump(),
    }


__all__ = [
    "AuthFailed",
    "CredentialServiceUnavailable",
    "PIIDetectorUnavailable",
    "RedisUnavailable",
    "Upstream5xx",
    "UpstreamRateLimited",
    "UpstreamTimeout",
    "error_response",
]
