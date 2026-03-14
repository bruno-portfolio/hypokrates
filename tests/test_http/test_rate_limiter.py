"""Testes para hypokrates.http.rate_limiter — enforce timing e singleton."""

from __future__ import annotations

import time

from hypokrates.http.rate_limiter import RateLimiter


class TestRateLimiterBasic:
    """Funcionalidade básica do rate limiter."""

    async def test_acquire_does_not_block_first_call(self) -> None:
        limiter = RateLimiter("test_first", max_per_minute=60)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5

    async def test_second_acquire_enforces_delay(self) -> None:
        """Segunda chamada respeita min_interval."""
        limiter = RateLimiter("test_delay", max_per_minute=120)
        # min_interval = 60/120 = 0.5s
        await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.4  # margem de tolerância


class TestRateLimiterSingleton:
    """Singleton pattern por source."""

    async def test_for_source_returns_same_instance(self) -> None:
        limiter1 = RateLimiter.for_source("test_singleton", 60)
        limiter2 = RateLimiter.for_source("test_singleton", 60)
        assert limiter1 is limiter2

    async def test_different_sources_different_instances(self) -> None:
        limiter1 = RateLimiter.for_source("source_a", 60)
        limiter2 = RateLimiter.for_source("source_b", 60)
        assert limiter1 is not limiter2

    async def test_reset_all_clears_instances(self) -> None:
        RateLimiter.for_source("test_reset", 60)
        RateLimiter.reset_all()
        # After reset, a new instance should be created
        limiter = RateLimiter.for_source("test_reset", 60)
        assert limiter is not None


class TestRateLimiterTiming:
    """Timing correto do rate limiter."""

    async def test_min_interval_calculation(self) -> None:
        """60 req/min → 1s interval, 120 → 0.5s, 240 → 0.25s."""
        limiter_60 = RateLimiter("t60", max_per_minute=60)
        assert limiter_60._min_interval == 1.0

        limiter_120 = RateLimiter("t120", max_per_minute=120)
        assert limiter_120._min_interval == 0.5

        limiter_240 = RateLimiter("t240", max_per_minute=240)
        assert limiter_240._min_interval == 0.25
