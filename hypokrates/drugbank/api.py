"""API pública do módulo DrugBank — async-first."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from hypokrates.config import get_config
from hypokrates.drugbank.store import DrugBankStore
from hypokrates.exceptions import ConfigurationError

if TYPE_CHECKING:
    from hypokrates.drugbank.models import DrugBankInfo, DrugInteraction

logger = logging.getLogger(__name__)


async def _ensure_loaded() -> DrugBankStore:
    """Garante que o store está carregado, fazendo parse do XML se necessário."""
    store = DrugBankStore.get_instance()
    if store.loaded:
        return store

    config = get_config()
    if config.drugbank_path is None:
        msg = (
            "DrugBank XML path not configured. "
            "Use configure(drugbank_path='/path/to/drugbank.xml') first."
        )
        raise ConfigurationError(msg)

    xml_path = str(config.drugbank_path)
    logger.info("DrugBank store not loaded — parsing XML: %s", xml_path)
    await asyncio.to_thread(store.load_from_xml, xml_path)
    return store


async def drug_info(
    drug_name: str,
    *,
    _store: DrugBankStore | None = None,
) -> DrugBankInfo | None:
    """Busca informações completas de uma droga no DrugBank.

    Args:
        drug_name: Nome da droga (genérico ou sinônimo).
        _store: Store injetado (para testes).

    Returns:
        DrugBankInfo ou None se não encontrado.
    """
    if _store is not None:
        return await asyncio.to_thread(_store.find_drug, drug_name)

    store = await _ensure_loaded()
    return await asyncio.to_thread(store.find_drug, drug_name)


async def drug_interactions(
    drug_name: str,
    *,
    _store: DrugBankStore | None = None,
) -> list[DrugInteraction]:
    """Busca interações droga-droga no DrugBank.

    Args:
        drug_name: Nome da droga.
        _store: Store injetado (para testes).

    Returns:
        Lista de DrugInteraction.
    """
    if _store is not None:
        return await asyncio.to_thread(_store.find_interactions, drug_name)

    store = await _ensure_loaded()
    return await asyncio.to_thread(store.find_interactions, drug_name)


async def drug_mechanism(
    drug_name: str,
    *,
    _store: DrugBankStore | None = None,
) -> str:
    """Retorna mecanismo de ação de uma droga.

    Args:
        drug_name: Nome da droga.
        _store: Store injetado (para testes).

    Returns:
        Texto do mecanismo de ação, ou string vazia se não encontrado.
    """
    info = await drug_info(drug_name, _store=_store)
    if info is None:
        return ""
    return info.mechanism_of_action
