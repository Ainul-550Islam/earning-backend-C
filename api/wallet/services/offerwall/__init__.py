# services/offerwall/__init__.py
"""
Offerwall Platform Adapters
"এক কাজের জন্য একটাই মালিক।"
Each platform is owned by exactly one adapter class.
"""
from .base import BaseOfferwallAdapter, ConversionPayload, OfferwallOffer
from .ogads import OGAdsAdapter
from .adgate import AdGateAdapter
from .offertoro import OffertoroAdapter
from .monlix import MonlixAdapter
from .registry import OfferwallRegistry

__all__ = [
    "BaseOfferwallAdapter", "ConversionPayload", "OfferwallOffer",
    "OGAdsAdapter", "AdGateAdapter", "OffertoroAdapter", "MonlixAdapter",
    "OfferwallRegistry",
]
