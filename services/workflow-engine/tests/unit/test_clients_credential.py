"""Unit tests for app/clients/credential.py — respx mock httpx."""
import pytest
import respx
from httpx import Response
from app.clients.credential import CredentialClient
from app.errors.classes import SecurityError


@pytest.mark.asyncio
@respx.mock
async def test_check_access_returns_true_on_200():
    respx.get("http://credential-test:8000/v1/credentials/c1/access").mock(
        return_value=Response(200, json={"allowed": True})
    )
    c = CredentialClient()
    try:
        assert await c.check_access("c1", "u1") is True
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_check_access_returns_false_on_403():
    respx.get("http://credential-test:8000/v1/credentials/c1/access").mock(return_value=Response(403))
    c = CredentialClient()
    try:
        assert await c.check_access("c1", "u1") is False
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_check_access_raises_security_error_on_404():
    respx.get("http://credential-test:8000/v1/credentials/c1/access").mock(return_value=Response(404))
    c = CredentialClient()
    try:
        with pytest.raises(SecurityError, match="凭证 c1 不存在"):
            await c.check_access("c1", "u1")
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_check_access_raises_on_500():
    respx.get("http://credential-test:8000/v1/credentials/c1/access").mock(return_value=Response(500))
    c = CredentialClient()
    try:
        with pytest.raises(Exception):  # HTTPStatusError
            await c.check_access("c1", "u1")
    finally:
        await c.aclose()
