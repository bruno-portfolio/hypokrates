"""Testes para hypokrates.sync — wrapper síncrono funciona em ambos os code paths."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.cross.models import HypothesisResult
from hypokrates.exceptions import NetworkError
from hypokrates.faers.models import FAERSResult
from hypokrates.pubmed.models import PubMedSearchResult
from hypokrates.sync import faers


class TestSyncWrapper:
    """Sync wrapper funciona em ambos os code paths."""

    @respx.mock
    def test_sync_adverse_events(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        result = faers.adverse_events("propofol", use_cache=False)
        assert len(result.reports) == 3

    @respx.mock
    def test_sync_top_events(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        result = faers.top_events("propofol", use_cache=False)
        assert len(result.events) == 10

    @respx.mock
    def test_sync_compare(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        results = faers.compare(["propofol", "ketamine"], use_cache=False)
        assert "propofol" in results
        assert "ketamine" in results

    @respx.mock
    def test_sync_preserves_result_type(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """Retorno é FAERSResult, não coroutine."""
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        result = faers.adverse_events("propofol", use_cache=False)
        assert isinstance(result, FAERSResult)

    @respx.mock
    def test_sync_propagates_exceptions(self) -> None:
        """Exceção async → exceção sync."""
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises((httpx.ConnectError, NetworkError)):
            faers.adverse_events("propofol", use_cache=False)


class TestSyncPubMed:
    """Sync wrapper para PubMed."""

    @respx.mock
    def test_sync_count_papers(self) -> None:
        configure(cache_enabled=False)
        respx.get(
            url__startswith="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "esearchresult": {
                        "count": "42",
                        "idlist": [],
                        "querytranslation": "test",
                    }
                },
            )
        )
        from hypokrates.sync import pubmed

        result = pubmed.count_papers("propofol", "bradycardia", use_cache=False)
        assert isinstance(result, PubMedSearchResult)
        assert result.total_count == 42

    @respx.mock
    def test_sync_search_papers(self) -> None:
        configure(cache_enabled=False)
        respx.get(
            url__startswith="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "esearchresult": {
                        "count": "1",
                        "idlist": ["111"],
                        "querytranslation": "test",
                    }
                },
            )
        )
        efetch_xml = """<?xml version="1.0" ?>
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>111</PMID>
              <Article>
                <Journal><Title>J</Title>
                  <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
                </Journal>
                <ArticleTitle>Test</ArticleTitle>
                <AuthorList CompleteYN="N"/>
              </Article>
            </MedlineCitation>
          </PubmedArticle>
        </PubmedArticleSet>"""
        respx.get(
            url__startswith="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        ).mock(return_value=httpx.Response(200, text=efetch_xml))
        from hypokrates.sync import pubmed

        result = pubmed.search_papers("propofol", "bradycardia", limit=1, use_cache=False)
        assert isinstance(result, PubMedSearchResult)
        assert len(result.articles) == 1


class TestSyncCross:
    """Sync wrapper para Cross."""

    @respx.mock
    def test_sync_hypothesis(self) -> None:
        configure(cache_enabled=False)
        # Mock FAERS (4 fetch_total calls)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"results": {"total": 100}},
                    "results": [],
                },
            )
        )
        # Mock PubMed esearch
        respx.get(
            url__startswith="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "esearchresult": {
                        "count": "0",
                        "idlist": [],
                    }
                },
            )
        )
        from hypokrates.sync import cross

        result = cross.hypothesis("propofol", "PRIS", use_cache=False)
        assert isinstance(result, HypothesisResult)


class TestSyncDailyMed:
    """Sync wrapper para DailyMed."""

    @respx.mock
    def test_sync_label_events(self) -> None:
        configure(cache_enabled=False)
        respx.get(
            url__startswith="https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
        ).mock(return_value=httpx.Response(200, json={"data": [], "metadata": {}}))
        from hypokrates.sync import dailymed

        result = dailymed.label_events("propofol", use_cache=False)
        assert result.drug == "propofol"
        assert result.events == []


class TestSyncTrials:
    """Sync wrapper para Trials."""

    @respx.mock
    @patch("hypokrates.trials.client._HAS_CURL_CFFI", False)
    def test_sync_search_trials(self) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://clinicaltrials.gov/api/v2/studies").mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "studies": []})
        )
        from hypokrates.sync import trials

        result = trials.search_trials("propofol", "hypotension", use_cache=False)
        assert result.total_count == 0
        assert result.trials == []
