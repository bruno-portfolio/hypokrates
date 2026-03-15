"""FAERS Bulk — deduplicação por CASEID a partir de quarterly files ASCII."""

from hypokrates.faers_bulk.api import bulk_signal, bulk_store_status, is_bulk_available
from hypokrates.faers_bulk.constants import RoleCodFilter
from hypokrates.faers_bulk.models import BulkCountResult, BulkStoreStatus, QuarterInfo
from hypokrates.faers_bulk.store import FAERSBulkStore
from hypokrates.faers_bulk.timeline import bulk_signal_timeline

__all__ = [
    "BulkCountResult",
    "BulkStoreStatus",
    "FAERSBulkStore",
    "QuarterInfo",
    "RoleCodFilter",
    "bulk_signal",
    "bulk_signal_timeline",
    "bulk_store_status",
    "is_bulk_available",
]
