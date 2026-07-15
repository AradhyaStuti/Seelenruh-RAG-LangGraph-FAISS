"""Per-provider circuit breaker: CLOSED → OPEN (on N failures) → HALF_OPEN (after timeout) → CLOSED."""
import asyncio
import time
from enum import Enum
from typing import Callable, TypeVar, Awaitable
from logger import get_logger

log = get_logger("circuit_breaker")

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Raised when the circuit is OPEN and fast-failing the request."""
    def __init__(self, provider: str):
        super().__init__(f"Circuit OPEN for {provider} — skipping to next provider.")
        self.status = 503  # makes provider._is_fallback_worthy() return True


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
        call_timeout: float = 20.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.call_timeout = call_timeout
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    async def call(self, fn: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute `fn(*args, **kwargs)` with circuit-breaker + timeout protection."""
        async with self._lock:
            current = self.state
            if current == CircuitState.OPEN:
                raise CircuitOpenError(self.name)

        try:
            result = await asyncio.wait_for(fn(*args, **kwargs), timeout=self.call_timeout)
            await self._on_success()
            return result
        except asyncio.TimeoutError:
            await self._on_failure()
            raise TimeoutError(f"{self.name} call timed out after {self.call_timeout}s")
        except CircuitOpenError:
            raise
        except Exception:
            await self._on_failure()
            raise

    async def call_stream(self, fn: Callable, *args, **kwargs):
        """Wrap an async generator with circuit-breaker protection."""
        async with self._lock:
            current = self.state
            if current == CircuitState.OPEN:
                raise CircuitOpenError(self.name)

        first_chunk = True
        try:
            async for chunk in fn(*args, **kwargs):
                if first_chunk:
                    await self._on_success()
                    first_chunk = False
                yield chunk
            if first_chunk:
                # Generator returned without yielding — still counts as success
                await self._on_success()
        except CircuitOpenError:
            raise
        except Exception:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold or self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                log.warning("circuit opened", provider=self.name, failures=self._failures, reset_in=self.reset_timeout)

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failures,
        }


# Module-level singletons — one per LLM provider
groq_breaker = CircuitBreaker("groq",      failure_threshold=3, reset_timeout=30.0,  call_timeout=20.0)
ollama_breaker = CircuitBreaker("ollama",   failure_threshold=2, reset_timeout=60.0,  call_timeout=90.0)
anthropic_breaker = CircuitBreaker("anthropic", failure_threshold=3, reset_timeout=30.0, call_timeout=50.0)
