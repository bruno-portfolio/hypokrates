"""Constantes do módulo OpenTargets."""

from __future__ import annotations

from hypokrates.constants import OPENTARGETS_GRAPHQL_URL

GRAPHQL_URL = OPENTARGETS_GRAPHQL_URL

# GraphQL queries
SEARCH_DRUG_QUERY = """
query SearchDrug($name: String!) {
  search(queryString: $name, entityNames: ["drug"], page: {size: 1, index: 0}) {
    hits {
      id
      name
      entity
    }
  }
}
"""

DRUG_ADVERSE_EVENTS_QUERY = """
query DrugAdverseEvents($chemblId: String!) {
  drug(chemblId: $chemblId) {
    name
    adverseEvents {
      count
      criticalValue
      rows {
        name
        count
        logLR
        meddraCode
      }
    }
  }
}
"""
