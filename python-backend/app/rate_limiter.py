"""Per-account token bucket rate limiter."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    capacity: float = 10.0
    refill_per_sec: float = 0.5
    tokens: float = field(default=10.0)
    last: float = field(default_factory=time.monotonic)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
            self.last = now

    def try_acquire(self, amount: float = 1.0) -> bool:
        self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def time_until(self, amount: float = 1.0) -> float:
        self._refill()
        if self.tokens >= amount:
            return 0.0
        if self.refill_per_sec <= 0:
            return float("inf")
        return (amount - self.tokens) / self.refill_per_sec


class RateLimiter:
    def __init__(self, capacity: float = 10.0, refill_per_sec: float = 0.5) -> None:
        self._capacity = capacity
        self._refill = refill_per_sec
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _bucket(self, account_id: str) -> TokenBucket:
        bucket = self._buckets.get(account_id)
        if bucket is None:
            bucket = TokenBucket(capacity=self._capacity, refill_per_sec=self._refill)
            self._buckets[account_id] = bucket
        return bucket

    async def acquire(self, account_id: str, amount: float = 1.0) -> None:
        while True:
            async with self._lock:
                bucket = self._bucket(account_id)
                if bucket.try_acquire(amount):
                    return
                wait = bucket.time_until(amount)
            await asyncio.sleep(max(0.01, wait))

    def try_acquire(self, account_id: str, amount: float = 1.0) -> bool:
        return self._bucket(account_id).try_acquire(amount)


rate_limiter = RateLimiter()
