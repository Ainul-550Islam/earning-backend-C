"""
webhook_manager/webhook_subscriber.py
───────────────────────────────────────
Manages webhook subscriptions — which events a URL should receive.
Provides Django-signal-based dispatch for registered webhook endpoints.
"""
from __future__ import annotations
import logging
from ..signals import (
    conversion_created, postback_rewarded, postback_rejected,
    fraud_detected, postback_duplicate,
)
from ..constants import (
    WEBHOOK_EVENT_CONVERSION, WEBHOOK_EVENT_CONVERSION_REJECT,
    WEBHOOK_EVENT_FRAUD, WEBHOOK_EVENT_REWARD,
)

logger = logging.getLogger(__name__)


class WebhookSubscriber:
    """
    Connects Django signals → webhook delivery pipeline.
    Call setup() once at app startup (in apps.py ready()).
    """

    def setup(self) -> None:
        """Wire up signal handlers for webhook dispatch."""
        conversion_created.connect(self._on_conversion_created, weak=False)
        postback_rejected.connect(self._on_postback_rejected, weak=False)
        fraud_detected.connect(self._on_fraud_detected, weak=False)

    def _on_conversion_created(self, sender, conversion, **kwargs):
        """Dispatch conversion.completed webhook."""
        try:
            from .webhook_dispatcher import dispatch_conversion_webhooks
            dispatch_conversion_webhooks(conversion)
        except Exception as exc:
            logger.warning("WebhookSubscriber: conversion webhook failed: %s", exc)

    def _on_postback_rejected(self, sender, raw_log, reason, **kwargs):
        """Dispatch conversion.rejected webhook for high-value rejections."""
        try:
            if not raw_log or not raw_log.network:
                return
            from .webhook_delivery import webhook_delivery
            from .webhook_registry import webhook_registry
            endpoints = webhook_registry.get_endpoints_for_event(
                raw_log.network, WEBHOOK_EVENT_CONVERSION_REJECT
            )
            if endpoints:
                payload = {
                    "event": WEBHOOK_EVENT_CONVERSION_REJECT,
                    "lead_id": raw_log.lead_id,
                    "offer_id": raw_log.offer_id,
                    "network": raw_log.network.network_key,
                    "rejection_reason": reason,
                }
                for endpoint in endpoints:
                    webhook_delivery.deliver(endpoint["url"], payload, endpoint.get("secret", ""))
        except Exception as exc:
            logger.warning("WebhookSubscriber: rejection webhook failed: %s", exc)

    def _on_fraud_detected(self, sender, fraud_log, **kwargs):
        """Dispatch fraud.detected webhook."""
        try:
            if not fraud_log or not fraud_log.network:
                return
            from .webhook_delivery import webhook_delivery
            from .webhook_registry import webhook_registry
            endpoints = webhook_registry.get_endpoints_for_event(
                fraud_log.network, WEBHOOK_EVENT_FRAUD
            )
            for endpoint in endpoints:
                payload = {
                    "event": WEBHOOK_EVENT_FRAUD,
                    "fraud_type": fraud_log.fraud_type,
                    "fraud_score": fraud_log.fraud_score,
                    "source_ip": fraud_log.source_ip,
                    "network": fraud_log.network.network_key if fraud_log.network else "",
                }
                webhook_delivery.deliver(endpoint["url"], payload, endpoint.get("secret", ""))
        except Exception as exc:
            logger.warning("WebhookSubscriber: fraud webhook failed: %s", exc)


webhook_subscriber = WebhookSubscriber()
