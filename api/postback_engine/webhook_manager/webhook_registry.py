"""
webhook_manager/webhook_registry.py
─────────────────────────────────────
Central registry of webhook endpoints subscribed to postback events.
Stores in DB (with Redis cache) which URLs to notify for which events.
"""
from __future__ import annotations
import logging
from typing import List, Optional
from django.core.cache import cache
from ..constants import WEBHOOK_EVENT_CONVERSION, WEBHOOK_EVENT_FRAUD

logger = logging.getLogger(__name__)
_REGISTRY_CACHE_KEY = "pe:webhook:registry:{network_id}:{event}"
_REGISTRY_TTL = 300


class WebhookRegistry:
    """
    Manages webhook endpoint registrations.
    Endpoints are stored in AdNetworkConfig.metadata['webhooks'].
    """

    def get_endpoints_for_event(self, network, event: str) -> List[dict]:
        """Return list of webhook endpoint configs for a network + event."""
        cache_key = _REGISTRY_CACHE_KEY.format(
            network_id=str(getattr(network, "id", "")),
            event=event,
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        metadata = getattr(network, "metadata", {}) or {}
        webhooks = metadata.get("webhooks", [])
        endpoints = [
            wh for wh in webhooks
            if wh.get("url") and (
                wh.get("events") is None  # subscribe to all events
                or event in (wh.get("events") or [])
            )
        ]
        cache.set(cache_key, endpoints, timeout=_REGISTRY_TTL)
        return endpoints

    def register(self, network, url: str, events: List[str] = None, secret: str = "") -> None:
        """Add a webhook endpoint to a network's registry."""
        metadata = getattr(network, "metadata", {}) or {}
        webhooks = metadata.get("webhooks", [])

        # Remove existing entry for same URL
        webhooks = [w for w in webhooks if w.get("url") != url]
        webhooks.append({
            "url": url,
            "events": events,
            "secret": secret,
            "active": True,
        })
        metadata["webhooks"] = webhooks
        network.metadata = metadata
        network.save(update_fields=["metadata"])
        self._invalidate_cache(network)

    def unregister(self, network, url: str) -> None:
        """Remove a webhook endpoint from a network's registry."""
        metadata = getattr(network, "metadata", {}) or {}
        webhooks = [w for w in metadata.get("webhooks", []) if w.get("url") != url]
        metadata["webhooks"] = webhooks
        network.metadata = metadata
        network.save(update_fields=["metadata"])
        self._invalidate_cache(network)

    def _invalidate_cache(self, network) -> None:
        network_id = str(getattr(network, "id", ""))
        for event in [WEBHOOK_EVENT_CONVERSION, WEBHOOK_EVENT_FRAUD, "*"]:
            cache.delete(_REGISTRY_CACHE_KEY.format(network_id=network_id, event=event))


webhook_registry = WebhookRegistry()
