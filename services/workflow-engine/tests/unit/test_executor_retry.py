"""Unit tests for app/executor/retry.py — indexed-backoff retry helper."""
import pytest
from app.errors.classes import UserError, SecurityError
from app.executor.retry import with_retry


@pytest.mark.asyncio
async def test_with_retry_success_first_try():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    assert await with_retry(fn) == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_with_retry_runtime_eventually_succeeds():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("transient")
        return "ok"

    assert await with_retry(fn, retry_count=2) == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_with_retry_runtime_exhausted_raises_last():
    async def fn():
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError, match="always fails"):
        await with_retry(fn, retry_count=2)


@pytest.mark.asyncio
async def test_with_retry_user_error_no_retry():
    calls = []

    async def fn():
        calls.append(1)
        raise UserError("bad input")

    with pytest.raises(UserError, match="bad input"):
        await with_retry(fn, retry_count=3)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_with_retry_security_error_no_retry():
    calls = []

    async def fn():
        calls.append(1)
        raise SecurityError("denied")

    with pytest.raises(SecurityError, match="denied"):
        await with_retry(fn, retry_count=3)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_with_retry_default_retry_count_is_1():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("x")
        return "ok"

    assert await with_retry(fn) == "ok"  # default retry_count=1
    assert len(calls) == 2
