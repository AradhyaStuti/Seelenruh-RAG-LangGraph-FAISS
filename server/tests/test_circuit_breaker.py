"""Tests for ai.circuit_breaker — CLOSED/OPEN/HALF_OPEN transitions,
call_timeout enforcement, and call_stream() protection."""
import asyncio
import time

import pytest

from ai.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError


# ── helpers ──────────────────────────────────────────────────────────────────

async def _ok():
    return "ok"


async def _fail():
    raise ValueError("boom")


async def _slow():
    await asyncio.sleep(10)


async def _stream_ok():
    for word in ["hello", " ", "world"]:
        yield word


async def _stream_fail():
    raise RuntimeError("stream error")
    yield  # make it a generator


# ── CLOSED → OPEN ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_closed_on_success():
    cb = CircuitBreaker("test", failure_threshold=2, reset_timeout=1.0, call_timeout=5.0)
    result = await cb.call(_ok)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_opens_after_threshold():
    cb = CircuitBreaker("test", failure_threshold=2, reset_timeout=60.0, call_timeout=5.0)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail)
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_fast_fails():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=60.0, call_timeout=5.0)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        await cb.call(_ok)


# ── OPEN → HALF_OPEN → CLOSED ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_half_open_after_reset():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05, call_timeout=5.0)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb.state == CircuitState.OPEN
    await asyncio.sleep(0.1)
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_closes():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05, call_timeout=5.0)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    await asyncio.sleep(0.1)
    result = await cb.call(_ok)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_reopens():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05, call_timeout=5.0)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    await asyncio.sleep(0.1)
    assert cb.state == CircuitState.HALF_OPEN
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb.state == CircuitState.OPEN


# ── call_timeout ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_timeout_triggers_failure():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=60.0, call_timeout=0.05)
    with pytest.raises(TimeoutError):
        await cb.call(_slow)
    assert cb._failures == 1


# ── call_stream ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_stream_yields_tokens():
    cb = CircuitBreaker("test", failure_threshold=2, reset_timeout=60.0, call_timeout=5.0)
    tokens = []
    async for t in cb.call_stream(_stream_ok):
        tokens.append(t)
    assert tokens == ["hello", " ", "world"]
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_call_stream_failure_increments_counter():
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout=60.0, call_timeout=5.0)
    with pytest.raises(RuntimeError):
        async for _ in cb.call_stream(_stream_fail):
            pass
    assert cb._failures == 1


@pytest.mark.asyncio
async def test_call_stream_open_raises():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=60.0, call_timeout=5.0)
    with pytest.raises(RuntimeError):
        async for _ in cb.call_stream(_stream_fail):
            pass
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        async for _ in cb.call_stream(_stream_ok):
            pass


# ── status() ─────────────────────────────────────────────────────────────────

def test_status_dict():
    cb = CircuitBreaker("groq", failure_threshold=3, reset_timeout=30.0, call_timeout=20.0)
    s = cb.status()
    assert s["name"] == "groq"
    assert s["state"] == "closed"
    assert s["failures"] == 0
