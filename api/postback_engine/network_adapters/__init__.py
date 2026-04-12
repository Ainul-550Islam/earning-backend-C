"""network_adapters — CPA network field mapping and status normalisation."""
from .adapters import get_adapter, ADAPTER_REGISTRY
from .base_adapter import BaseNetworkAdapter
from .cpalead_adapter import CPALeadAdapter
from .adgate_adapter import AdGateAdapter
from .offerwall_adapter import (
    OfferwallAdapter, OfferToroAdapter, AdGemAdapter,
    TapjoyAdapter, RevenueWallAdapter, AdscendAdapter,
)
