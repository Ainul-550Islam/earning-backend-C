"""
webhook_manager/custom_webhook.py
───────────────────────────────────
Custom webhook builder for sending arbitrary event payloads.
Allows admin-defined webhooks with custom payloads and templates.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any, Dict, Optional
from .webhook_delivery import webhook_delivery
from .webhook_retry import webhook_retry

logger = logging.getLogger(__name__)


class CustomWebhook:
    """
    Build and send custom webhook payloads with template support.
    Allows customising the JSON body structure per webhook endpoint.
    """

    def send(
        self,
        url: str,
        event: str,
        data: Dict[str, Any],
        secret: str = "",
        template: Optional[str] = None,
        conversion_id: str = "",
    ) -> bool:
        """
        Send a custom webhook.
        If template is provided, it's a JSON template with {field} placeholders.
        """
        if template:
            payload = self._render_template(template, data)
        else:
            payload = {"event": event, **data}

        success = webhook_delivery.deliver(url, payload, secret=secret)
        if not success and conversion_id:
            webhook_retry.schedule(
                conversion_id=conversion_id,
                url=url,
                error=f"Delivery failed for event={event}",
                attempt=1,
            )
        return success

    def _render_template(self, template: str, data: dict) -> dict:
        """
        Render a JSON template string with {field} placeholders.
        Falls back to raw data if template parsing fails.
        """
        try:
            rendered = template
            for key, value in data.items():
                rendered = rendered.replace(f"{{{key}}}", str(value))
            return json.loads(rendered)
        except Exception as exc:
            logger.warning("CustomWebhook template render failed: %s", exc)
            return data

    def build_zapier_payload(self, event: str, conversion) -> dict:
        """Build a Zapier-compatible payload from a Conversion."""
        return {
            "event": event,
            "id": str(conversion.id),
            "offer_id": conversion.offer_id,
            "user_id": str(conversion.user_id),
            "payout_usd": float(conversion.actual_payout),
            "points": conversion.points_awarded,
            "currency": conversion.currency,
            "network": conversion.network.network_key,
            "converted_at": conversion.converted_at.isoformat(),
            "status": conversion.status,
        }

    def build_make_payload(self, event: str, conversion) -> dict:
        """Build a Make.com (Integromat) compatible payload."""
        return {
            "type": event,
            "data": {
                "conversion": {
                    "id": str(conversion.id),
                    "offer": conversion.offer_id,
                    "revenue": float(conversion.actual_payout),
                    "points": conversion.points_awarded,
                    "user": str(conversion.user_id),
                    "network": conversion.network.network_key,
                    "timestamp": conversion.converted_at.isoformat(),
                }
            }
        }


custom_webhook = CustomWebhook()
