"""Testes para hypokrates.scan.clusters."""

from __future__ import annotations

from hypokrates.scan.clusters import (
    DEFAULT_CLUSTER,
    SEMANTIC_CLUSTERS,
    cluster_events,
    get_cluster,
)


class TestGetCluster:
    """Testes para get_cluster()."""

    def test_known_term(self) -> None:
        assert get_cluster("BRADYCARDIA") == "Cardiovascular"

    def test_psychiatric_term(self) -> None:
        assert get_cluster("INSOMNIA") == "Psychiatric"

    def test_endocrine_term(self) -> None:
        assert get_cluster("HYPERGLYCAEMIA") == "Endocrine/Metabolic"

    def test_unknown_term(self) -> None:
        assert get_cluster("SOME UNKNOWN TERM") == DEFAULT_CLUSTER

    def test_case_insensitive(self) -> None:
        assert get_cluster("bradycardia") == "Cardiovascular"

    def test_case_insensitive_mixed(self) -> None:
        assert get_cluster("Insomnia") == "Psychiatric"

    def test_musculoskeletal(self) -> None:
        assert get_cluster("OSTEONECROSIS") == "Musculoskeletal"

    def test_hepatic(self) -> None:
        assert get_cluster("HEPATOTOXICITY") == "Hepatic"

    def test_renal(self) -> None:
        assert get_cluster("RENAL FAILURE") == "Renal"

    def test_respiratory(self) -> None:
        assert get_cluster("RESPIRATORY DEPRESSION") == "Respiratory"

    def test_haematologic(self) -> None:
        assert get_cluster("THROMBOCYTOPENIA") == "Haematologic"

    def test_dermatologic(self) -> None:
        assert get_cluster("STEVENS-JOHNSON SYNDROME") == "Dermatologic"

    def test_gastrointestinal(self) -> None:
        assert get_cluster("PANCREATITIS") == "Gastrointestinal"

    def test_neurologic(self) -> None:
        assert get_cluster("SEIZURE") == "Neurologic"

    def test_immune_infection(self) -> None:
        assert get_cluster("ANAPHYLAXIS") == "Immune/Infection"

    def test_ophthalmic(self) -> None:
        assert get_cluster("GLAUCOMA") == "Ophthalmic"

    def test_whitespace_stripped(self) -> None:
        assert get_cluster("  BRADYCARDIA  ") == "Cardiovascular"

    def test_empty_string(self) -> None:
        assert get_cluster("") == DEFAULT_CLUSTER


class TestClusterEvents:
    """Testes para cluster_events()."""

    def test_basic_clustering(self) -> None:
        events = ["BRADYCARDIA", "INSOMNIA", "HYPERGLYCAEMIA", "UNKNOWN THING"]
        result = cluster_events(events)
        assert "Cardiovascular" in result
        assert "Psychiatric" in result
        assert "Endocrine/Metabolic" in result
        assert DEFAULT_CLUSTER in result

    def test_empty_list(self) -> None:
        assert cluster_events([]) == {}

    def test_all_same_cluster(self) -> None:
        events = ["BRADYCARDIA", "TACHYCARDIA", "HYPOTENSION"]
        result = cluster_events(events)
        assert len(result) == 1
        assert "Cardiovascular" in result
        assert len(result["Cardiovascular"]) == 3

    def test_preserves_event_names(self) -> None:
        events = ["bradycardia", "INSOMNIA"]
        result = cluster_events(events)
        assert result["Cardiovascular"] == ["bradycardia"]
        assert result["Psychiatric"] == ["INSOMNIA"]

    def test_multiple_per_cluster(self) -> None:
        events = ["SEIZURE", "DIZZINESS", "HEADACHE"]
        result = cluster_events(events)
        assert "Neurologic" in result
        assert len(result["Neurologic"]) == 3

    def test_all_unknown(self) -> None:
        events = ["FOO", "BAR", "BAZ"]
        result = cluster_events(events)
        assert len(result) == 1
        assert DEFAULT_CLUSTER in result
        assert len(result[DEFAULT_CLUSTER]) == 3


class TestSemanticClustersIntegrity:
    """Testes de integridade do dicionário SEMANTIC_CLUSTERS."""

    def test_no_duplicate_terms(self) -> None:
        """Cada termo deve pertencer a no máximo um cluster."""
        seen: dict[str, str] = {}
        for cluster_name, terms in SEMANTIC_CLUSTERS.items():
            for term in terms:
                upper = term.upper()
                assert upper not in seen, f"{term} in both {seen[upper]} and {cluster_name}"
                seen[upper] = cluster_name

    def test_all_clusters_non_empty(self) -> None:
        for cluster_name, terms in SEMANTIC_CLUSTERS.items():
            assert len(terms) > 0, f"Cluster {cluster_name} is empty"

    def test_all_terms_uppercase(self) -> None:
        """Termos no dicionário devem estar em uppercase."""
        for cluster_name, terms in SEMANTIC_CLUSTERS.items():
            for term in terms:
                assert term == term.upper(), (
                    f"Term '{term}' in cluster '{cluster_name}' is not uppercase"
                )

    def test_minimum_cluster_count(self) -> None:
        """Deve haver pelo menos 10 clusters definidos."""
        assert len(SEMANTIC_CLUSTERS) >= 10

    def test_default_cluster_value(self) -> None:
        assert DEFAULT_CLUSTER == "Other"
