"""Unit tests for ``app.schemas`` — Pydantic models + validators."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.models import CredentialType
from app.schemas import (
    MAX_PAGE_SIZE,
    MAX_VALUE_LENGTH,
    WORKSPACE_ID_PATTERN,
    CredentialCreateRequest,
    CredentialDetailResponse,
    CredentialListResponse,
    CredentialResponse,
    CredentialRevealResponse,
    CredentialRotateRequest,
    CredentialUseRequest,
    CredentialUseResponse,
    validate_page,
    validate_page_size,
)


# ---------------------------------------------------------------------------
# CredentialCreateRequest — valid cases
# ---------------------------------------------------------------------------


class TestCredentialCreateRequestValid:
    def test_api_key_minimal(self) -> None:
        req = CredentialCreateRequest(
            name="my-key",
            type=CredentialType.API_KEY,
            value=SecretStr("sk-12345678"),
            workspace_id="finance",
        )
        assert req.name == "my-key"
        assert req.type is CredentialType.API_KEY
        assert req.value.get_secret_value() == "sk-12345678"
        assert req.workspace_id == "finance"
        assert req.expires_at is None

    def test_oauth2_all_fields(self) -> None:
        req = CredentialCreateRequest(
            name="github-oauth",
            type=CredentialType.OAUTH2,
            value=SecretStr("gh-token-123"),
            workspace_id="finance",
            client_id="abc123",
            client_secret=SecretStr("very-secret"),
            token_url="https://github.com/oauth/token",
            scope="repo,read:user",
        )
        assert req.client_id == "abc123"
        assert req.client_secret.get_secret_value() == "very-secret"
        assert str(req.token_url) == "https://github.com/oauth/token"
        assert req.scope == "repo,read:user"

    def test_database_all_fields(self) -> None:
        req = CredentialCreateRequest(
            name="pg-db",
            type=CredentialType.DATABASE,
            value=SecretStr("db-password-123"),
            workspace_id="finance",
            host="localhost",
            port=5432,
            db_name="mydb",
        )
        assert req.host == "localhost"
        assert req.port == 5432
        assert req.db_name == "mydb"

    def test_smtp_all_fields(self) -> None:
        req = CredentialCreateRequest(
            name="smtp-relay",
            type=CredentialType.SMTP,
            value=SecretStr("smtp-pass-1234"),
            workspace_id="finance",
            host="smtp.example.com",
            port=587,
            username="sender",
        )
        assert req.host == "smtp.example.com"
        assert req.port == 587
        assert req.username == "sender"

    def test_workspace_id_kebab_case(self) -> None:
        req = CredentialCreateRequest(
            name="key",
            type=CredentialType.API_KEY,
            value=SecretStr("v"),
            workspace_id="my-workspace-123",
        )
        assert req.workspace_id == "my-workspace-123"

    def test_workspace_id_single_char(self) -> None:
        req = CredentialCreateRequest(
            name="key",
            type=CredentialType.API_KEY,
            value=SecretStr("v"),
            workspace_id="a",
        )
        assert req.workspace_id == "a"

    def test_workspace_id_max_64_chars(self) -> None:
        req = CredentialCreateRequest(
            name="key",
            type=CredentialType.API_KEY,
            value=SecretStr("v"),
            workspace_id="a" * 64,
        )
        assert len(req.workspace_id) == 64

    def test_value_at_max_length(self) -> None:
        req = CredentialCreateRequest(
            name="key",
            type=CredentialType.API_KEY,
            value=SecretStr("x" * MAX_VALUE_LENGTH),
            workspace_id="ws",
        )
        assert len(req.value.get_secret_value()) == MAX_VALUE_LENGTH

    def test_expires_at_set(self) -> None:
        from datetime import datetime, UTC
        dt = datetime(2026, 12, 31, tzinfo=UTC)
        req = CredentialCreateRequest(
            name="key",
            type=CredentialType.API_KEY,
            value=SecretStr("v"),
            workspace_id="ws",
            expires_at=dt,
        )
        assert req.expires_at == dt


# ---------------------------------------------------------------------------
# CredentialCreateRequest — invalid / validation
# ---------------------------------------------------------------------------


class TestCredentialCreateRequestInvalid:
    def test_name_empty_raises(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            CredentialCreateRequest(
                name="",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="ws",
            )

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            CredentialCreateRequest(
                name="x" * 256,
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="ws",
            )

    def test_value_empty_raises(self) -> None:
        with pytest.raises(ValidationError, match="value must be non-empty"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr(""),
                workspace_id="ws",
            )

    def test_value_too_long_raises(self) -> None:
        with pytest.raises(ValidationError, match="value must be <="):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("x" * (MAX_VALUE_LENGTH + 1)),
                workspace_id="ws",
            )

    def test_workspace_id_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="",
            )

    def test_workspace_id_pattern_rejects_uppercase(self) -> None:
        with pytest.raises(ValidationError, match="workspace_id"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="Finance",
            )

    def test_workspace_id_pattern_rejects_spaces(self) -> None:
        with pytest.raises(ValidationError, match="workspace_id"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="my workspace",
            )

    def test_workspace_id_pattern_rejects_special_chars(self) -> None:
        with pytest.raises(ValidationError, match="workspace_id"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="ws!@#",
            )

    def test_workspace_id_too_long_raises(self) -> None:
        with pytest.raises(ValidationError, match="workspace_id"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="a" * 65,
            )

    def test_api_key_with_type_specific_field_raises(self) -> None:
        with pytest.raises(ValidationError, match="MUST NOT set"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="ws",
                host="evil.com",
            )

    def test_api_key_with_client_id_raises(self) -> None:
        with pytest.raises(ValidationError, match="MUST NOT set"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="ws",
                client_id="abc",
            )

    def test_oauth2_missing_client_id_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="oauth2 credential requires"
        ):
            CredentialCreateRequest(
                name="gh",
                type=CredentialType.OAUTH2,
                value=SecretStr("v"),
                workspace_id="ws",
                client_secret=SecretStr("s"),
                token_url="https://example.com/token",
                scope="read",
            )

    def test_oauth2_missing_client_secret_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="oauth2 credential requires"
        ):
            CredentialCreateRequest(
                name="gh",
                type=CredentialType.OAUTH2,
                value=SecretStr("v"),
                workspace_id="ws",
                client_id="abc",
                token_url="https://example.com/token",
                scope="read",
            )

    def test_oauth2_missing_token_url_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="oauth2 credential requires"
        ):
            CredentialCreateRequest(
                name="gh",
                type=CredentialType.OAUTH2,
                value=SecretStr("v"),
                workspace_id="ws",
                client_id="abc",
                client_secret=SecretStr("s"),
                scope="read",
            )

    def test_oauth2_missing_scope_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="oauth2 credential requires"
        ):
            CredentialCreateRequest(
                name="gh",
                type=CredentialType.OAUTH2,
                value=SecretStr("v"),
                workspace_id="ws",
                client_id="abc",
                client_secret=SecretStr("s"),
                token_url="https://example.com/token",
            )

    def test_oauth2_with_database_field_raises(self) -> None:
        with pytest.raises(ValidationError, match="MUST NOT set"):
            CredentialCreateRequest(
                name="gh",
                type=CredentialType.OAUTH2,
                value=SecretStr("v"),
                workspace_id="ws",
                client_id="abc",
                client_secret=SecretStr("s"),
                token_url="https://example.com/token",
                scope="read",
                host="evil.com",
            )

    def test_database_missing_host_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="database credential requires"
        ):
            CredentialCreateRequest(
                name="db",
                type=CredentialType.DATABASE,
                value=SecretStr("v"),
                workspace_id="ws",
                port=5432,
                db_name="mydb",
            )

    def test_database_missing_port_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="database credential requires"
        ):
            CredentialCreateRequest(
                name="db",
                type=CredentialType.DATABASE,
                value=SecretStr("v"),
                workspace_id="ws",
                host="localhost",
                db_name="mydb",
            )

    def test_database_missing_db_name_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="database credential requires"
        ):
            CredentialCreateRequest(
                name="db",
                type=CredentialType.DATABASE,
                value=SecretStr("v"),
                workspace_id="ws",
                host="localhost",
                port=5432,
            )

    def test_database_with_oauth2_field_raises(self) -> None:
        with pytest.raises(ValidationError, match="MUST NOT set"):
            CredentialCreateRequest(
                name="db",
                type=CredentialType.DATABASE,
                value=SecretStr("v"),
                workspace_id="ws",
                host="localhost",
                port=5432,
                db_name="mydb",
                client_id="abc",
            )

    def test_smtp_missing_host_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="smtp credential requires"
        ):
            CredentialCreateRequest(
                name="smtp",
                type=CredentialType.SMTP,
                value=SecretStr("v"),
                workspace_id="ws",
                port=587,
                username="user",
            )

    def test_smtp_missing_port_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="smtp credential requires"
        ):
            CredentialCreateRequest(
                name="smtp",
                type=CredentialType.SMTP,
                value=SecretStr("v"),
                workspace_id="ws",
                host="smtp.example.com",
                username="user",
            )

    def test_smtp_missing_username_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="smtp credential requires"
        ):
            CredentialCreateRequest(
                name="smtp",
                type=CredentialType.SMTP,
                value=SecretStr("v"),
                workspace_id="ws",
                host="smtp.example.com",
                port=587,
            )

    def test_smtp_with_oauth2_field_raises(self) -> None:
        with pytest.raises(ValidationError, match="MUST NOT set"):
            CredentialCreateRequest(
                name="smtp",
                type=CredentialType.SMTP,
                value=SecretStr("v"),
                workspace_id="ws",
                host="smtp.example.com",
                port=587,
                username="user",
                client_id="abc",
            )

    def test_extra_unknown_field_raises(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CredentialCreateRequest(
                name="key",
                type=CredentialType.API_KEY,
                value=SecretStr("v"),
                workspace_id="ws",
                bad_field="oops",
            )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TestResponseModels:
    def test_credential_response_construct(self) -> None:
        from datetime import datetime, UTC
        now = datetime(2026, 6, 1, tzinfo=UTC)
        resp = CredentialResponse(
            id="cred_abc",
            name="my-key",
            type=CredentialType.API_KEY,
            workspace_id="finance",
            expires_at=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == "cred_abc"
        assert resp.name == "my-key"
        assert resp.expires_at is None

    def test_credential_response_no_value_field(self) -> None:
        """CredentialResponse must not accept 'value' or 'masked_value'."""
        from datetime import datetime, UTC
        now = datetime(2026, 1, 1, tzinfo=UTC)
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CredentialResponse(
                id="x", name="x", type=CredentialType.API_KEY,
                workspace_id="ws", expires_at=None,
                created_at=now, updated_at=now,
                value="secret",  # type: ignore[call-arg]
            )

    def test_credential_detail_response_construct(self) -> None:
        from datetime import datetime, UTC
        now = datetime(2026, 6, 1, tzinfo=UTC)
        resp = CredentialDetailResponse(
            id="cred_abc",
            name="my-key",
            type=CredentialType.API_KEY,
            workspace_id="finance",
            expires_at=None,
            created_at=now,
            updated_at=now,
            masked_value="sk-t★★★★CDEF",
        )
        assert resp.masked_value == "sk-t★★★★CDEF"

    def test_credential_reveal_response_construct(self) -> None:
        resp = CredentialRevealResponse(value="plaintext-secret")
        assert resp.value == "plaintext-secret"

    def test_credential_use_request_construct(self) -> None:
        req = CredentialUseRequest(cap="workflow-engine", purpose="paul-monthly-report")
        assert req.cap == "workflow-engine"
        assert req.purpose == "paul-monthly-report"

    def test_credential_use_request_empty_cap_raises(self) -> None:
        with pytest.raises(ValidationError):
            CredentialUseRequest(cap="", purpose="test")

    def test_credential_use_response_construct(self) -> None:
        resp = CredentialUseResponse(value="plaintext-secret")
        assert resp.value == "plaintext-secret"

    def test_credential_rotate_request_construct(self) -> None:
        req = CredentialRotateRequest(value=SecretStr("new-secret-123"))
        assert req.value.get_secret_value() == "new-secret-123"
        assert req.expires_at is None

    def test_credential_rotate_request_empty_value_raises(self) -> None:
        with pytest.raises(ValidationError, match="value must be non-empty"):
            CredentialRotateRequest(value=SecretStr(""))

    def test_credential_rotate_request_value_too_long_raises(self) -> None:
        with pytest.raises(ValidationError, match="value must be <="):
            CredentialRotateRequest(value=SecretStr("x" * (MAX_VALUE_LENGTH + 1)))

    def test_credential_rotate_request_with_expires_at(self) -> None:
        from datetime import datetime, UTC
        dt = datetime(2026, 6, 15, tzinfo=UTC)
        req = CredentialRotateRequest(value=SecretStr("new"), expires_at=dt)
        assert req.expires_at == dt

    def test_credential_list_response_construct(self) -> None:
        from datetime import datetime, UTC
        now = datetime(2026, 6, 1, tzinfo=UTC)
        items = [
            CredentialResponse(
                id="cred_1", name="key1", type=CredentialType.API_KEY,
                workspace_id="ws", expires_at=None, created_at=now, updated_at=now,
            )
        ]
        resp = CredentialListResponse(items=items, total_count=1, page=1, page_size=20)
        assert len(resp.items) == 1
        assert resp.total_count == 1
        assert resp.page == 1
        assert resp.page_size == 20


# ---------------------------------------------------------------------------
# Page validators
# ---------------------------------------------------------------------------


class TestValidatePage:
    def test_valid_page(self) -> None:
        assert validate_page(1) == 1
        assert validate_page(100) == 100

    def test_zero_page_raises(self) -> None:
        with pytest.raises(ValueError, match="page must be >= 1"):
            validate_page(0)

    def test_negative_page_raises(self) -> None:
        with pytest.raises(ValueError, match="page must be >= 1"):
            validate_page(-1)


class TestValidatePageSize:
    def test_valid_page_size(self) -> None:
        assert validate_page_size(1) == 1
        assert validate_page_size(100) == 100

    def test_zero_page_size_raises(self) -> None:
        with pytest.raises(ValueError, match="page_size must be >= 1"):
            validate_page_size(0)

    def test_too_large_page_size_raises(self) -> None:
        with pytest.raises(ValueError, match="page_size must be <="):
            validate_page_size(MAX_PAGE_SIZE + 1)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_workspace_id_pattern_accepts_valid(self) -> None:
        assert WORKSPACE_ID_PATTERN.match("finance")
        assert WORKSPACE_ID_PATTERN.match("my-workspace")
        assert WORKSPACE_ID_PATTERN.match("ws_123")
        assert WORKSPACE_ID_PATTERN.match("a")

    def test_workspace_id_pattern_rejects_invalid(self) -> None:
        assert not WORKSPACE_ID_PATTERN.match("Hello")
        assert not WORKSPACE_ID_PATTERN.match("has space")
        assert not WORKSPACE_ID_PATTERN.match("special!")
        assert not WORKSPACE_ID_PATTERN.match("")
        assert not WORKSPACE_ID_PATTERN.match("a" * 65)

    def test_max_value_length(self) -> None:
        assert MAX_VALUE_LENGTH == 4096

    def test_max_page_size(self) -> None:
        assert MAX_PAGE_SIZE == 100


# ---------------------------------------------------------------------------
# _StrictModel extra forbid
# ---------------------------------------------------------------------------


class TestStrictModelExtraForbid:
    def test_extra_field_on_response_raises(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CredentialRevealResponse(value="ok", extra="bad")  # type: ignore[call-arg]

    def test_extra_field_on_use_response_raises(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            CredentialUseResponse(value="ok", extra="bad")  # type: ignore[call-arg]
