"""Pydantic v2 schemas for the credential-management service.

These DTOs are the contract between the HTTP layer (Task 5) and the
business service layer (Task 4). They live in their own module so:

* The service layer (``app.services``) can import them without dragging
  in FastAPI.
* The HTTP layer can re-export them as request / response models.
* Tests can validate input parsing without spinning up a router.

Authoritative source for the field set:

* ``openspec/changes/implement-credential-management/specs/credential-management/spec.md``
  §凭证类型实现 (4 types + per-type field set) and §凭证列表分页.
* ``openspec/changes/implement-credential-management/plan.md`` Task 4
  (the per-schema field list).

Design notes:

* ``value`` is always ``SecretStr`` on request models so it does not leak
  into ``repr()`` or ``model_dump()`` (the JSON serialisation deliberately
  excludes secrets by default). On response models the plaintext value
  appears only on the two surfaces that the spec explicitly allows:
  ``CredentialRevealResponse`` (admin reveal API) and
  ``CredentialUseResponse`` (internal use API). Both are plain ``str``
  on the response side because the caller already has the value at that
  point and needs to use it.
* ``CredentialResponse`` deliberately omits ``value`` / ``masked_value``
  so list endpoints never echo (even partial) plaintext.
* ``CredentialDetailResponse`` adds ``masked_value`` (前 4 后 4) for the
  single-credential read endpoint, which the UI uses to confirm the
  caller is looking at the right row.
* Type-specific metadata fields (``client_id`` / ``host`` / etc.) live on
  the create / detail responses but are NOT persisted as separate
  columns in this MVP — the spec keeps the metadata bundled into the
  encrypted blob (see ``CredentialService._encode_value``). Persisting
  them as separate columns is a V1.0+ change.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
    model_validator,
)

from app.models import CredentialType

# ---------------------------------------------------------------------------
# Field constraints (kept as module-level constants so tests can import them
# without duplicating the regex / length numbers).
# ---------------------------------------------------------------------------

#: Per spec §凭证类型实现: value length 1 <= n <= 4096 chars.
MAX_VALUE_LENGTH: int = 4096

#: workspace_id format: kebab/snake-case ASCII slug, 1-64 chars.
WORKSPACE_ID_PATTERN: re.Pattern[str] = re.compile(r"^[a-z0-9_-]{1,64}$")

#: Default page size for list endpoint.
DEFAULT_PAGE_SIZE: int = 20

#: Maximum page size (per spec §凭证列表分页).
MAX_PAGE_SIZE: int = 100


# ---------------------------------------------------------------------------
# Common base
# ---------------------------------------------------------------------------


class _StrictModel(BaseModel):
    """Base config: forbid unknown fields so typos in the API surface fail loudly."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Validators (shared)
# ---------------------------------------------------------------------------


def _validate_workspace_id(value: str) -> str:
    """Reject workspace IDs that don't match the slug pattern."""
    if not WORKSPACE_ID_PATTERN.match(value):
        raise ValueError(
            f"workspace_id must match {WORKSPACE_ID_PATTERN.pattern!r} "
            f"(got {value!r})"
        )
    return value


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------


class CredentialCreateRequest(_StrictModel):
    """Request body for ``POST /api/v1/credentials``.

    The ``value`` field is required for every type; the optional
    ``client_id`` / ``host`` / ... metadata fields are validated as a
    group via ``_check_type_specific_fields`` (oauth2 all-or-nothing,
    api_key forbids extras, etc.).
    """

    name: Annotated[str, Field(min_length=1, max_length=255)]
    type: CredentialType
    value: SecretStr
    workspace_id: Annotated[str, Field(min_length=1, max_length=64)]
    expires_at: datetime | None = None

    # oauth2 fields
    client_id: str | None = None
    client_secret: SecretStr | None = None
    token_url: HttpUrl | None = None
    scope: str | None = None

    # database fields
    host: str | None = None
    port: int | None = None
    db_name: str | None = None

    # smtp fields (``host`` / ``port`` are shared with the database type;
    # smtp adds ``username``).
    username: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def _wsid(cls, v: str) -> str:
        return _validate_workspace_id(v)

    @field_validator("value")
    @classmethod
    def _value_length(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if len(raw) == 0:
            raise ValueError("value must be non-empty")
        if len(raw) > MAX_VALUE_LENGTH:
            raise ValueError(f"value must be <= {MAX_VALUE_LENGTH} chars (got {len(raw)})")
        return v

    @model_validator(mode="after")
    def _check_type_specific_fields(self) -> CredentialCreateRequest:
        """Enforce per-type field presence.

        * ``api_key``  — no type-specific fields allowed.
        * ``oauth2``   — client_id / client_secret / token_url / scope
                         are ALL required (all-or-nothing).
        * ``database`` — host / port / db_name all required.
        * ``smtp``     — host / port / username all required.

        Any cross-type leakage (e.g. setting ``host`` on an ``api_key``
        credential) is rejected so the persisted shape stays
        unambiguous downstream.
        """
        oauth2_fields = ("client_id", "client_secret", "token_url", "scope")
        db_fields = ("host", "port", "db_name")
        smtp_fields = ("host", "port", "username")
        # Union of all type-specific fields; used for negative checks.
        all_extras = set(oauth2_fields) | set(db_fields) | set(smtp_fields)

        if self.type is CredentialType.API_KEY:
            leaked = [f for f in all_extras if getattr(self, f) is not None]
            if leaked:
                raise ValueError(
                    f"api_key credential MUST NOT set type-specific fields: {sorted(leaked)}"
                )
        elif self.type is CredentialType.OAUTH2:
            missing = [f for f in oauth2_fields if getattr(self, f) is None]
            if missing:
                raise ValueError(f"oauth2 credential requires: {missing}")
            forbidden = [f for f in (set(db_fields) | set(smtp_fields)) - set(oauth2_fields)
                         if getattr(self, f) is not None]
            if forbidden:
                raise ValueError(
                    f"oauth2 credential MUST NOT set: {sorted(forbidden)}"
                )
        elif self.type is CredentialType.DATABASE:
            missing = [f for f in db_fields if getattr(self, f) is None]
            if missing:
                raise ValueError(f"database credential requires: {missing}")
            forbidden = [f for f in (set(oauth2_fields) | set(smtp_fields)) - set(db_fields)
                         if getattr(self, f) is not None]
            if forbidden:
                raise ValueError(
                    f"database credential MUST NOT set: {sorted(forbidden)}"
                )
        elif self.type is CredentialType.SMTP:
            missing = [f for f in smtp_fields if getattr(self, f) is None]
            if missing:
                raise ValueError(f"smtp credential requires: {missing}")
            forbidden = [f for f in (set(oauth2_fields) | set(db_fields)) - set(smtp_fields)
                         if getattr(self, f) is not None]
            if forbidden:
                raise ValueError(
                    f"smtp credential MUST NOT set: {sorted(forbidden)}"
                )
        return self


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CredentialResponse(_StrictModel):
    """Slim response: list / create / rotate endpoints.

    Deliberately **no** value or masked_value field — listing endpoints
    must never echo (even partial) plaintext.
    """

    id: str
    name: str
    type: CredentialType
    workspace_id: str
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CredentialDetailResponse(CredentialResponse):
    """Single-credential read: extends ``CredentialResponse`` + masked value."""

    masked_value: str


class CredentialRevealResponse(_StrictModel):
    """Response from ``POST /credentials/{id}/reveal`` — admin only."""

    value: str


class CredentialUseRequest(_StrictModel):
    """Request body for internal ``POST /credentials/{id}/use`` API."""

    cap: Annotated[str, Field(min_length=1, max_length=255)]
    purpose: Annotated[str, Field(min_length=1, max_length=255)]


class CredentialUseResponse(_StrictModel):
    """Response from internal ``use`` API; carries plaintext to caller cap."""

    value: str


class CredentialRotateRequest(_StrictModel):
    """Request body for ``POST /credentials/{id}/rotate``."""

    value: SecretStr
    expires_at: datetime | None = None

    @field_validator("value")
    @classmethod
    def _value_length(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if len(raw) == 0:
            raise ValueError("value must be non-empty")
        if len(raw) > MAX_VALUE_LENGTH:
            raise ValueError(f"value must be <= {MAX_VALUE_LENGTH} chars (got {len(raw)})")
        return v


class CredentialListResponse(_StrictModel):
    """Paginated list response.

    ``items`` carries the slim ``CredentialResponse`` (no masked_value);
    callers wanting masked values fetch individual rows via
    ``GET /credentials/{id}``.
    """

    items: list[CredentialResponse]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Validator helpers exposed for tests
# ---------------------------------------------------------------------------


def validate_page_size(page_size: int) -> int:
    """Reject page_size > MAX_PAGE_SIZE per spec §凭证列表分页."""
    if page_size < 1:
        raise ValueError(f"page_size must be >= 1 (got {page_size})")
    if page_size > MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be <= {MAX_PAGE_SIZE} (got {page_size})")
    return page_size


def validate_page(page: int) -> int:
    """Reject page < 1."""
    if page < 1:
        raise ValueError(f"page must be >= 1 (got {page})")
    return page


# Re-export for downstream type hints; mypy --strict friendly.
__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "MAX_VALUE_LENGTH",
    "WORKSPACE_ID_PATTERN",
    "CredentialCreateRequest",
    "CredentialDetailResponse",
    "CredentialListResponse",
    "CredentialResponse",
    "CredentialRevealResponse",
    "CredentialRotateRequest",
    "CredentialUseRequest",
    "CredentialUseResponse",
    "validate_page",
    "validate_page_size",
]
