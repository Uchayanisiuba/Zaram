"""Token bucket rate limiter for API providers."""

from __future__ import annotations

import asyncio
import time
from typing import Optional


class TokenBucketRateLimiter:
    """Token bucket rate limiter for controlling request rates."""
    
    def __init__(self, rate_per_minute: int, burst: Optional[int] = None):
        self.rate_per_minute = rate_per_minute
        self.burst = burst or rate_per_minute
        self._tokens = float(self.burst)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary."""
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                
                # Wait for next token
                wait_time = (tokens - self._tokens) * (60.0 / self.rate_per_minute)
                await asyncio.sleep(wait_time)
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * (self.rate_per_minute / 60.0))
        self._last_update = now
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False
    
    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        self._refill()
        return self._tokens
    
    def reset(self) -> None:
        """Reset the bucket to full."""
        self._tokens = float(self.burst)
        self._last_update = time.monotonic()