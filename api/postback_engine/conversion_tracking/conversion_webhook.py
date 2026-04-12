"""
conversion_tracking/conversion_webhook.py
───────────────────────────────────────────
Outbound S2S conversion webhook sender.
After we approve a conversion, we may need to notify the advertiser/network
via an outbound postback URL (reverse S2S confirmation).
"""
from __future__ import annotations
import logging
from ..models import Conversion

logger = logging.getLogger(__name__)


class ConversionWebhook:

    def send_confirmation(self, conversion: Conversion) -> bool:
        """
        Send outbound S2S confirmation postback to the network.
        Uses the postback_url_template from AdNetworkConfig.
        Returns True on success.
        """
        network = conversion.network
        template = getattr(network, "postback_url_template", "")
        if not template:
            return False

        from ..network_adapters.adapters import get_adapter
        adapter = get_adapter(network.network_key)
        url = adapter.expand_macros(template, {
            "click_id":       conversion.click_id or "",
            "lead_id":        conversion.lead_id or "",
            "offer_id":       conversion.offer_id or "",
            "payout":         str(conversion.actual_payout),
            "currency":       conversion.currency,
            "transaction_id": conversion.transaction_id,
            "status":         "approved",
            "user_id":        str(conversion.user_id),
        })

        try:
            import requests
            resp = requests.get(url, timeout=5)
            success = 200 <= resp.status_code < 300
            logger.info(
                "S2S confirmation: network=%s url=%s status=%d",
                network.network_key, url[:80], resp.status_code,
            )
            return success
        except Exception as exc:
            logger.warning("S2S confirmation failed for conversion=%s: %s", conversion.id, exc)
            return False

    def send_reversal_notification(self, conversion: Conversion, reason: str = "") -> bool:
        """Notify the network when we reverse a conversion (chargeback)."""
        network = conversion.network
        template = getattr(network, "postback_url_template", "")
        if not template:
            return False

        from ..network_adapters.adapters import get_adapter
        adapter = get_adapter(network.network_key)
        url = adapter.expand_macros(template, {
            "click_id":       conversion.click_id or "",
            "offer_id":       conversion.offer_id or "",
            "transaction_id": conversion.transaction_id,
            "status":         "reversed",
            "payout":         "0",
        })

        try:
            import requests
            resp = requests.get(url, timeout=5)
            return 200 <= resp.status_code < 300
        except Exception as exc:
            logger.warning("Reversal notification failed for conversion=%s: %s", conversion.id, exc)
            return False


conversion_webhook = ConversionWebhook()
