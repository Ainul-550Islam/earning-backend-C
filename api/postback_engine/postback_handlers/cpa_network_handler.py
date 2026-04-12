"""
postback_handlers/cpa_network_handler.py
─────────────────────────────────────────
Concrete handler for generic CPA networks.
Subclassed by CPALead, AdGate, OfferToro, etc.
"""
from __future__ import annotations

from .base_handler import BasePostbackHandler, PostbackContext
from ..network_adapters.adapters import get_adapter


class CPANetworkHandler(BasePostbackHandler):
    """
    Concrete handler for any CPA network.
    Instantiated with a network_key and the correct adapter is auto-selected.

    Usage:
        handler = CPANetworkHandler("cpalead")
        result  = handler.execute(raw_payload, method, ...)
    """

    def __init__(self, network_key: str):
        self._network_key = network_key
        self._adapter = get_adapter(network_key)

    @property
    def network_key(self) -> str:
        return self._network_key

    def get_adapter(self):
        return self._adapter


class CPALeadHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("cpalead")


class AdGateHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("adgate")


class OfferToroHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("offertoro")


class AdscendHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("adscend")


class RevenueWallHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("revenuewall")


class AppLovinHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("applovin")


class UnityAdsHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("unity")


class IronSourceHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("ironsource")


class AdMobHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("admob")


class FacebookHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("facebook")


class GoogleHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("google")


class TikTokHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("tiktok")


class ImpactHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("impact")


class CakeHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("cake")


class HasOffersHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("hasoffers")


class EverflowHandler(CPANetworkHandler):
    def __init__(self):
        super().__init__("everflow")


# ── Handler Registry ───────────────────────────────────────────────────────────

HANDLER_REGISTRY: dict[str, type[CPANetworkHandler]] = {
    "cpalead":     CPALeadHandler,
    "adgate":      AdGateHandler,
    "offertoro":   OfferToroHandler,
    "adscend":     AdscendHandler,
    "revenuewall": RevenueWallHandler,
    "applovin":    AppLovinHandler,
    "unity":       UnityAdsHandler,
    "ironsource":  IronSourceHandler,
    "admob":       AdMobHandler,
    "facebook":    FacebookHandler,
    "google":      GoogleHandler,
    "tiktok":      TikTokHandler,
    "impact":      ImpactHandler,
    "cake":        CakeHandler,
    "hasoffers":   HasOffersHandler,
    "everflow":    EverflowHandler,
}


def get_handler(network_key: str) -> BasePostbackHandler:
    """
    Return the appropriate handler for a network_key.
    Falls back to generic CPANetworkHandler if not in registry.
    """
    handler_cls = HANDLER_REGISTRY.get(network_key)
    if handler_cls:
        return handler_cls()
    return CPANetworkHandler(network_key)
