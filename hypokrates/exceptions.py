"""Hierarquia de exceções do hypokrates."""

from __future__ import annotations


class HypokratesError(Exception):
    """Exceção base para todas as operações do hypokrates."""


class SourceUnavailableError(HypokratesError):
    """Fonte de dados temporariamente indisponível."""

    def __init__(self, source: str, detail: str = "") -> None:
        self.source = source
        self.detail = detail
        msg = f"Fonte indisponível: {source}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class NetworkError(HypokratesError):
    """Erro de rede (timeout, DNS, connection refused)."""

    def __init__(self, url: str, detail: str = "") -> None:
        self.url = url
        self.detail = detail
        msg = f"Erro de rede: {url}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class RateLimitError(HypokratesError):
    """Rate limit atingido para uma fonte."""

    def __init__(self, source: str, retry_after: float | None = None) -> None:
        self.source = source
        self.retry_after = retry_after
        msg = f"Rate limit atingido: {source}"
        if retry_after is not None:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)


class ParseError(HypokratesError):
    """Erro ao parsear resposta de uma fonte."""

    def __init__(self, source: str, detail: str = "") -> None:
        self.source = source
        self.detail = detail
        msg = f"Erro de parsing: {source}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class ValidationError(HypokratesError):
    """Erro de validação de input do usuário."""


class CacheError(HypokratesError):
    """Erro na camada de cache."""


class ConfigurationError(HypokratesError):
    """Erro de configuração."""
