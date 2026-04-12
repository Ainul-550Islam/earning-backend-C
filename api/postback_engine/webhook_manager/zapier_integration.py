"""
webhook_manager/zapier_integration.py
───────────────────────────────────────
Zapier webhook integration for Postback Engine.
When a conversion is approved, fires a Zap that can trigger any action in Zapier:
  - Add row to Google Sheets
  - Send Slack notification
  - Create HubSpot contact
  - Send email via Gmail
  - Update Airtable record
  - Trigger any of 5000+ Zapier apps

Setup in Django settings:
    POSTBACK_ENGINE = {
        "ZAPIER_WEBHOOK_URLS": {
            "conversion.approved": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
            "fraud.detected":      "https://hooks.zapier.com/hooks/catch/12345/xyz123/",
        }
    }
"""
from __future__ import annotations
import logging
from typing import Optional
from .webhook_delivery import webhook_delivery
from .webhook_retry import webhook_retry

logger = logging.getLogger(__name__)


class ZapierIntegration:
    """
    Sends structured payloads to Zapier webhook (catch) hooks.
    Zapier auto-parses the JSON and maps fields to its app actions.
    """

    def get_webhook_url(self, event: str) -> Optional[str]:
        """Get Zapier webhook URL for a specific event from settings."""
        try:
            from django.conf import settings
            pe_settings = getattr(settings, "POSTBACK_ENGINE", {})
            urls = pe_settings.get("ZAPIER_WEBHOOK_URLS", {})
            # Try exact event match, then wildcard
            return urls.get(event) or urls.get("*")
        except Exception:
            return None

    def send_conversion(self, conversion) -> bool:
        """
        Send conversion data to Zapier.
        Zapier payload is flat JSON — all fields at top level for easy mapping.
        """
        url = self.get_webhook_url("conversion.approved")
        if not url:
            return False

        payload = {
            # Core identifiers
            "event":          "conversion.approved",
            "conversion_id":  str(conversion.id),
            "lead_id":        conversion.lead_id or "",
            "click_id":       conversion.click_id or "",
            "offer_id":       conversion.offer_id or "",
            "transaction_id": conversion.transaction_id or "",

            # Network info
            "network":        conversion.network.network_key if conversion.network else "",
            "network_name":   conversion.network.name if conversion.network else "",

            # User info
            "user_id":        str(conversion.user_id),
            "user_email":     getattr(conversion.user, "email", ""),
            "username":       getattr(conversion.user, "username", ""),

            # Financial
            "payout_usd":     float(conversion.actual_payout),
            "points_awarded": conversion.points_awarded,
            "currency":       conversion.currency,

            # Timing
            "converted_at":   conversion.converted_at.isoformat(),
            "time_to_convert_seconds": conversion.time_to_convert_seconds or 0,

            # Geo/device
            "country":        conversion.country or "",
            "source_ip":      conversion.source_ip or "",
        }

        success = webhook_delivery.deliver(url, payload)
        if not success:
            logger.warning(
                "Zapier: conversion delivery failed for %s", conversion.id
            )
        else:
            logger.debug("Zapier: conversion %s sent", conversion.id)
        return success

    def send_fraud_alert(self, fraud_log) -> bool:
        """Send fraud detection alert to Zapier."""
        url = self.get_webhook_url("fraud.detected")
        if not url:
            return False

        payload = {
            "event":       "fraud.detected",
            "fraud_id":    str(fraud_log.id),
            "fraud_type":  fraud_log.fraud_type,
            "fraud_score": fraud_log.fraud_score,
            "source_ip":   fraud_log.source_ip or "",
            "network":     fraud_log.network.network_key if fraud_log.network else "",
            "auto_blocked":fraud_log.is_auto_blocked,
            "detected_at": fraud_log.detected_at.isoformat(),
        }
        return webhook_delivery.deliver(url, payload)

    def send_custom(self, event: str, data: dict) -> bool:
        """Send a custom event to Zapier."""
        url = self.get_webhook_url(event) or self.get_webhook_url("*")
        if not url:
            return False
        payload = {"event": event, **data}
        return webhook_delivery.deliver(url, payload)

    def test_connection(self) -> dict:
        """
        Send a test payload to all configured Zapier webhooks.
        Returns dict of {event: success}.
        """
        try:
            from django.conf import settings
            pe_settings = getattr(settings, "POSTBACK_ENGINE", {})
            urls = pe_settings.get("ZAPIER_WEBHOOK_URLS", {})
        except Exception:
            urls = {}

        results = {}
        for event, url in urls.items():
            if url:
                success = webhook_delivery.deliver(url, {
                    "event": event,
                    "test": True,
                    "message": "Test connection from PostbackEngine",
                })
                results[event] = success
        return results


# Module-level singleton
zapier_integration = ZapierIntegration()
