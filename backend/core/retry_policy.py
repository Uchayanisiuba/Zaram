# backend/core/retry_policy.py
"""Retry policy with exponential backoff and jitter.

Used by the TaskQueue and ExecutionContext to control retry behaviour
when a capability execution fails transiently.
"""
from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from core.contracts import TaskCancelledError

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


@dataclass
class RetryResult:
    """Outcome of a single retry decision."""
    should_retry: bool
    delay: float
    attempt: int
    reason: str = ""


class RetryPolicy:
    """Configurable retry policy with exponential backoff and optional jitter.

    Parameters
    ----------
    max_retries:
        Maximum number of retry attempts (0 means no retries).
    base_delay:
        Initial backoff delay in seconds.
    max_delay:
        Upper bound on the backoff delay.
    backoff_factor:
        Multiplier applied to the delay after each attempt.
    jitter:
        When True, multiply the delay by a random factor in [0.5, 1.0].
    retryable_exceptions:
        Tuple of exception types that should trigger a retry.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 5.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type[BaseException], ...] = _RETRYABLE_EXCEPTIONS,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def get_delay(self, attempt: int) -> float:
        """Compute the backoff delay for the given attempt (0-indexed)."""
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay *= 0.5 + random.random() * 0.5
        return delay

    def should_retry(self, attempt: int, error: BaseException | None = None) -> RetryResult:
        """Decide whether to retry based on attempt count and error type."""
        if attempt >= self.max_retries:
            return RetryResult(should_retry=False, delay=0.0, attempt=attempt, reason="max_retries_exceeded")

        if error is not None:
            if isinstance(error, TaskCancelledError):
                return RetryResult(should_retry=False, delay=0.0, attempt=attempt, reason="cancelled")
            if not isinstance(error, self.retryable_exceptions):
                return RetryResult(should_retry=False, delay=0.0, attempt=attempt, reason="non_retryable_error")

        delay = self.get_delay(attempt)
        return RetryResult(should_retry=True, delay=delay, attempt=attempt, reason="retry_scheduled")

    def execute_with_retry(
        self,
        func: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> object:
        """Synchronously execute *func* with retry logic.

        Raises the last exception if all retries are exhausted.
        """
        last_error: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except BaseException as exc:
                last_error = exc
                result = self.should_retry(attempt, exc)
                if not result.should_retry:
                    logger.warning(
                        "RetryPolicy: giving up after %d attempts for %s: %s",
                        attempt,
                        getattr(func, "__name__", repr(func)),
                        exc,
                    )
                    raise
                logger.info(
                    "RetryPolicy: retrying attempt %d/%d in %.3fs for %s: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    result.delay,
                    getattr(func, "__name__", repr(func)),
                    exc,
                )
                time.sleep(result.delay)

        assert last_error is not None
        raise last_error


@dataclass
class RetryPolicyBuilder:
    """Fluent builder for RetryPolicy."""
    max_retries: int = 3
    base_delay: float = 0.1
    max_delay: float = 5.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[BaseException], ...] = _RETRYABLE_EXCEPTIONS

    def with_max_retries(self, n: int) -> RetryPolicyBuilder:
        self.max_retries = n
        return self

    def with_delays(self, base: float, max_delay: float) -> RetryPolicyBuilder:
        self.base_delay = base
        self.max_delay = max_delay
        return self

    def with_backoff(self, factor: float) -> RetryPolicyBuilder:
        self.backoff_factor = factor
        return self

    def without_jitter(self) -> RetryPolicyBuilder:
        self.jitter = False
        return self

    def with_retryable(self, *exceptions: type[BaseException]) -> RetryPolicyBuilder:
        self.retryable_exceptions = exceptions
        return self

    def build(self) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            backoff_factor=self.backoff_factor,
            jitter=self.jitter,
            retryable_exceptions=self.retryable_exceptions,
        )


# Pre-built policies
NO_RETRY = RetryPolicy(max_retries=0)
DEFAULT_RETRY = RetryPolicy(max_retries=3, base_delay=0.1, max_delay=5.0)
AGGRESSIVE_RETRY = RetryPolicy(max_retries=5, base_delay=0.05, max_delay=10.0)
