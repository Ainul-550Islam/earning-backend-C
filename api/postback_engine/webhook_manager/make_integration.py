"""
webhook_manager/make_integration.py
────────────────────────────────────
Make.com (formerly Integromat) integration for Postback Engine.
Make.com provides visual automation workflows — more powerful than Zapier
for complex multi-step scenarios (loops, routers, aggregators).

Setup in Django settings:
    POSTBACK_ENGINE = {
        "MAKE_WEBHOOK_URLS": {
            "conversion.approved": "https://hook.eu1.make.com/abc123xyz/",
            "conversion.reversed": "https://hook.eu1.make.com/def456uvw/",
            "fraud.detected":      "https://hook.eu1.make.com/ghi789rst/",
            "*": "https://hook.eu1.make.com/all_events/",
        }
    }
"""
from __future__ import annotations
import logging
from typing import Optional
from .webhook_delivery import webhook_delivery

logger = logging.getLogger(__name__)


class MakeIntegration:
    """
    Sends structured event payloads to Make.com (Integromat) webhook triggers.
    Make.com expects the payload in a nested structure for better data mapping.
    """

    def get_webhook_url(self, event: str) -> Optional[str]:
        try:
            from django.conf import settings
            pe_settings = getattr(settings, "POSTBACK_ENGINE", {})
            urls = pe_settings.get("MAKE_WEBHOOK_URLS", {})
            return urls.get(event) or urls.get("*")
        except Exception:
            return None

    def send_conversion(self, conversion) -> bool:
        """Send conversion approved event to Make.com."""
        url = self.get_webhook_url("conversion.approved")
        if not url:
            return False

        # Make.com payload uses nested structure for cleaner scenario mapping
        payload = {
            "event": "conversion.approved",
            "timestamp": conversion.converted_at.isoformat(),
            "conversion": {
                "id":              str(conversion.id),
                "lead_id":         conversion.lead_id or "",
                "click_id":        conversion.click_id or "",
                "offer_id":        conversion.offer_id or "",
                "transaction_id":  conversion.transaction_id or "",
                "payout_usd":      float(conversion.actual_payout),
                "points_awarded":  conversion.points_awarded,
                "currency":        conversion.currency,
                "status":          conversion.status,
                "converted_at":    conversion.converted_at.isoformat(),
                "country":         conversion.country or "",
                "source_ip":       conversion.source_ip or "",
                "time_to_convert_seconds": conversion.time_to_convert_seconds or 0,
            },
            "network": {
                "key":  conversion.network.network_key if conversion.network else "",
                "name": conversion.network.name if conversion.network else "",
            },
            "user": {
                "id":       str(conversion.user_id),
                "email":    getattr(conversion.user, "email", ""),
                "username": getattr(conversion.user, "username", ""),
            },
        }
        success = webhook_delivery.deliver(url, payload)
        logger.debug("Make.com: conversion %s sent=%s", conversion.id, success)
        return success

    def send_reversal(self, conversion, reason: str = "") -> bool:
        """Send conversion reversed event to Make.com."""
        url = self.get_webhook_url("conversion.reversed")
        if not url:
            return False
        payload = {
            "event": "conversion.reversed",
            "timestamp": __import__("django.utils.timezone", fromlist=["timezone"]).timezone.now().isoformat(),
            "conversion": {
                "id":         str(conversion.id),
                "offer_id":   conversion.offer_id or "",
                "network":    conversion.network.network_key if conversion.network else "",
                "payout_usd": float(conversion.actual_payout),
                "reason":     reason,
            },
            "user": {"id": str(conversion.user_id)},
        }
        return webhook_delivery.deliver(url, payload)

    def send_fraud_alert(self, fraud_log) -> bool:
        """Send fraud detection alert to Make.com."""
        url = self.get_webhook_url("fraud.detected")
        if not url:
            return False
        from django.utils import timezone
        payload = {
            "event": "fraud.detected",
            "timestamp": timezone.now().isoformat(),
            "fraud": {
                "id":           str(fraud_log.id),
                "type":         fraud_log.fraud_type,
                "score":        fraud_log.fraud_score,
                "auto_blocked": fraud_log.is_auto_blocked,
                "source_ip":    fraud_log.source_ip or "",
                "detected_at":  fraud_log.detected_at.isoformat(),
            },
            "network": {
                "key": fraud_log.network.network_key if fraud_log.network else "",
            },
        }
        return webhook_delivery.deliver(url, payload)

    def send_custom(self, event: str, data: dict) -> bool:
        """Send a custom event payload to Make.com."""
        url = self.get_webhook_url(event) or self.get_webhook_url("*")
        if not url:
            return False
        from django.utils import timezone
        payload = {
            "event":     event,
            "timestamp": timezone.now().isoformat(),
            "data":      data,
        }
        return webhook_delivery.deliver(url, payload)

    def test_connection(self) -> dict:
        """Test all configured Make.com webhook URLs."""
        try:
            from django.conf import settings
            pe_settings = getattr(settings, "POSTBACK_ENGINE", {})
            urls = pe_settings.get("MAKE_WEBHOOK_URLS", {})
        except Exception:
            urls = {}

        from django.utils import timezone
        results = {}
        for event, url in urls.items():
            if url:
                success = webhook_delivery.deliver(url, {
                    "event":     event,
                    "test":      True,
                    "timestamp": timezone.now().isoformat(),
                    "message":   "Test from PostbackEngine Make.com integration",
                })
                results[event] = success
        return results


# Module-level singleton
make_integration = MakeIntegration()
