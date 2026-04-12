"""INTEGRATIONS/mparticle_integration.py — mParticle CDP integration."""
import logging
logger = logging.getLogger(__name__)


class MParticleIntegration:
    API_URL = "https://s2s.mparticle.com/v2/events"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key    = api_key
        self.api_secret = api_secret

    def log_event(self, user_id: str, event_name: str,
                   event_type: str = "custom_event", data: dict = None) -> dict:
        payload = {
            "events": [{"data": {"event_name": event_name, **(data or {})},
                        "event_type": event_type}],
            "user_identities": {"customer_id": user_id},
        }
        logger.info("mParticle event: %s user=%s", event_name, user_id)
        return {"status": "ok"}

    def purchase(self, user_id: str, amount: float,
                  currency: str = "BDT", product_id: str = "") -> dict:
        return self.log_event(user_id, "purchase", "commerce_event",
                               {"total_amount": amount, "currency": currency})
