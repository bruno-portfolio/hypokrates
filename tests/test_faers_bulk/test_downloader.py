"""Testes para faers_bulk/downloader.py — list_available_quarters."""

from __future__ import annotations

from hypokrates.faers_bulk.downloader import list_available_quarters


class TestListAvailableQuarters:
    """Testes de lista de quarters disponíveis."""

    def test_returns_list(self) -> None:
        """Retorna lista de tuplas."""
        quarters = list_available_quarters()
        assert isinstance(quarters, list)
        assert len(quarters) > 0

    def test_starts_at_min_year(self) -> None:
        """Primeiro quarter começa em 2014."""
        quarters = list_available_quarters()
        assert quarters[0] == (2014, 1)

    def test_custom_min_year(self) -> None:
        """Pode customizar ano mínimo."""
        quarters = list_available_quarters(min_year=2020)
        assert quarters[0] == (2020, 1)

    def test_quarters_are_1_to_4(self) -> None:
        """Todos os quarters são 1-4."""
        quarters = list_available_quarters()
        for _year, q in quarters:
            assert 1 <= q <= 4

    def test_chronological_order(self) -> None:
        """Quarters em ordem cronológica."""
        quarters = list_available_quarters()
        for i in range(1, len(quarters)):
            prev = quarters[i - 1]
            curr = quarters[i]
            assert (curr[0], curr[1]) > (prev[0], prev[1])
