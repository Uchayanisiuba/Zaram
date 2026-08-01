# backend/tests/test_retry_policy.py
"""Unit tests for the RetryPolicy."""
from __future__ import annotations

import time

import pytest

from core.retry_policy import (
    RetryPolicy,
    RetryPolicyBuilder,
    RetryResult,
    NO_RETRY,
    DEFAULT_RETRY,
    AGGRESSIVE_RETRY,
)
from core.contracts import TaskCancelledError


class TestRetryPolicy:
    def test_no_retry_policy(self):
        policy = RetryPolicy(max_retries=0)
        assert policy.max_retries == 0
        result = policy.should_retry(0, ConnectionError("test"))
        assert result.should_retry is False
        assert result.reason == "max_retries_exceeded"

    def test_should_retry_within_limit(self):
        policy = RetryPolicy(max_retries=3)
        result = policy.should_retry(0, ConnectionError("test"))
        assert result.should_retry is True
        assert result.delay > 0

    def test_should_not_retry_non_retryable(self):
        policy = RetryPolicy(max_retries=3)
        result = policy.should_retry(0, ValueError("bad value"))
        assert result.should_retry is False
        assert result.reason == "non_retryable_error"

    def test_should_not_retry_cancelled(self):
        policy = RetryPolicy(max_retries=3)
        result = policy.should_retry(0, TaskCancelledError("cancelled"))
        assert result.should_retry is False
        assert result.reason == "cancelled"

    def test_exponential_backoff(self):
        policy = RetryPolicy(max_retries=5, base_delay=0.1, backoff_factor=2.0, jitter=False)
        delay_0 = policy.get_delay(0)
        delay_1 = policy.get_delay(1)
        delay_2 = policy.get_delay(2)
        assert delay_0 == pytest.approx(0.1)
        assert delay_1 == pytest.approx(0.2)
        assert delay_2 == pytest.approx(0.4)

    def test_max_delay_cap(self):
        policy = RetryPolicy(max_retries=10, base_delay=1.0, max_delay=2.0, backoff_factor=2.0, jitter=False)
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 2.0  # capped

    def test_jitter(self):
        policy = RetryPolicy(max_retries=3, base_delay=1.0, jitter=True)
        delay = policy.get_delay(0)
        assert 0.5 <= delay <= 1.0

    def test_no_jitter(self):
        policy = RetryPolicy(max_retries=3, base_delay=1.0, jitter=False)
        delay = policy.get_delay(0)
        assert delay == 1.0

    def test_custom_retryable_exceptions(self):
        class CustomError(Exception):
            pass

        policy = RetryPolicy(max_retries=3, retryable_exceptions=(CustomError,))
        result = policy.should_retry(0, CustomError("custom"))
        assert result.should_retry is True

        result = policy.should_retry(0, ConnectionError("conn"))
        assert result.should_retry is False

    def test_execute_with_retry_success(self):
        policy = RetryPolicy(max_retries=3, base_delay=0.01, jitter=False)
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "success"

        result = policy.execute_with_retry(flaky_func)
        assert result == "success"
        assert call_count == 3

    def test_execute_with_retry_exhausted(self):
        policy = RetryPolicy(max_retries=2, base_delay=0.01, jitter=False)
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("always fails")

        with pytest.raises(ConnectionError):
            policy.execute_with_retry(always_fail)
        assert call_count == 3  # initial + 2 retries

    def test_execute_with_retry_non_retryable(self):
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("non-retryable")

        with pytest.raises(ValueError):
            policy.execute_with_retry(always_fail)
        assert call_count == 1  # no retries


class TestRetryPolicyBuilder:
    def test_build_default(self):
        policy = RetryPolicyBuilder().build()
        assert policy.max_retries == 3
        assert policy.base_delay == 0.1
        assert policy.jitter is True

    def test_build_custom(self):
        policy = (
            RetryPolicyBuilder()
            .with_max_retries(5)
            .with_delays(0.5, 10.0)
            .with_backoff(3.0)
            .without_jitter()
            .build()
        )
        assert policy.max_retries == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 10.0
        assert policy.backoff_factor == 3.0
        assert policy.jitter is False

    def test_build_with_custom_exceptions(self):
        class MyError(Exception):
            pass

        policy = (
            RetryPolicyBuilder()
            .with_retryable(MyError)
            .build()
        )
        assert MyError in policy.retryable_exceptions


class TestPrebuiltPolicies:
    def test_no_retry(self):
        assert NO_RETRY.max_retries == 0

    def test_default_retry(self):
        assert DEFAULT_RETRY.max_retries == 3

    def test_aggressive_retry(self):
        assert AGGRESSIVE_RETRY.max_retries == 5
