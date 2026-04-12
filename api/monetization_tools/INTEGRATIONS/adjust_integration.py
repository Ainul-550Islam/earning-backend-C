"""INTEGRATIONS/adjust_integration.py — Adjust MMP integration."""
import logging
logger = logging.getLogger(__name__)


class AdjustIntegration:
    S2S_URL = "https://s2s.adjust.com/event"

    def __init__(self, app_token: str = "", environment: str = "production"):
        self.app_token   = app_token
        self.environment = environment

    def track_event(self, event_token: str, adjust_id: str = "",
                     revenue: float = None, currency: str = "BDT") -> dict:
        params = {"app_token": self.app_token, "event_token": event_token,
                  "environment": self.environment, "adjust_id": adjust_id}
        if revenue is not None:
            params["revenue"]  = revenue
            params["currency"] = currency
        logger.info("Adjust event: %s adj_id=%s", event_token, adjust_id)
        return {"status": "sent", "event_token": event_token}

    def track_purchase(self, adjust_id: str, amount: float, currency: str,
                        purchase_token: str = "") -> dict:
        return self.track_event("purchase", adjust_id, amount, currency)
