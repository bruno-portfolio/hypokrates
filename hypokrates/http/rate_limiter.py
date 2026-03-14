"""Rate limiter per-source usando semáforo + delay."""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar


class RateLimiter:
    """Rate limiter baseado em semáforo com delay mínimo entre requests.

    Garante no máximo ``max_per_minute`` requests por minuto para uma fonte.
    Thread-safe via asyncio.Semaphore.
    """

    _instances: ClassVar[dict[str, RateLimiter]] = {}

    def __init__(self, source: str, max_per_minute: int) -> None:
        self._source = source
        self._max_per_minute = max_per_minute
        self._min_interval = 60.0 / max_per_minute
        self._semaphore = asyncio.Semaphore(1)
        self._last_request: float = 0.0

    @classmethod
    def for_source(cls, source: str, max_per_minute: int) -> RateLimiter:
        """Retorna (ou cria) rate limiter singleton para uma fonte."""
        if source not in cls._instances:
            cls._instances[source] = cls(source, max_per_minute)
        return cls._instances[source]

    @classmethod
    def reset_all(cls) -> None:
        """Reseta todos os rate limiters (usado em testes)."""
        cls._instances.clear()

    async def acquire(self) -> None:
        """Aguarda até que seja seguro fazer um request.

        Reserva o slot dentro do semáforo (rápido), mas dorme fora dele.
        Isso permite que requests concorrentes agendem seus slots sem
        bloquear uns aos outros no semáforo.
        """
        wait = 0.0
        async with self._semaphore:
            now = time.monotonic()
            elapsed = now - self._last_request
            wait = max(0.0, self._min_interval - elapsed)
            # Reserva o slot imediatamente (antes de dormir)
            self._last_request = now + wait

        # Dorme FORA do semáforo — outras tasks podem reservar seus slots
        if wait > 0:
            await asyncio.sleep(wait)
