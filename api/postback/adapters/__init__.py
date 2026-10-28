"""
postback/adapters/

Network-specific adapters that translate raw postback payloads into the
standard internal field format.

Each adapter is responsible ONLY for:
  • Mapping network-specific param names to standard field names.
  • Extracting and normalising CPAlead / other network-specific fields.
  • Returning a dict with standardised keys.

Adapters do NOT touch the database, send signals, or call external services.
"""
from .base import BasePostbackAdapter
from .cpalead import CPALeadAdapter
from .generic import GenericAdapter
from .registry import AdapterRegistry, get_adapter
from .networks import ALL_NETWORK_ADAPTERS

from .wallet_bridge import credit_wallet_for_postback, debit_wallet_for_reversal

__all__ = [
    "BasePostbackAdapter",
    "CPALeadAdapter",
    "GenericAdapter",
    "AdapterRegistry",
    "get_adapter",
    "ALL_NETWORK_ADAPTERS",
    "credit_wallet_for_postback",
    "debit_wallet_for_reversal",
]
