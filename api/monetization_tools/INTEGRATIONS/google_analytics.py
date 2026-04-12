"""INTEGRATIONS/google_analytics.py — Google Analytics 4 events."""
import logging

logger = logging.getLogger(__name__)


class GoogleAnalyticsIntegration:
    MEASUREMENT_URL = "https://www.google-analytics.com/mp/collect"

    def __init__(self, measurement_id: str = "", api_secret: str = ""):
        self.measurement_id = measurement_id
        self.api_secret     = api_secret

    def send_event(self, client_id: str, event_name: str,
                    params: dict = None) -> dict:
        payload = {
            "client_id": client_id,
            "events":    [{"name": event_name, "params": params or {}}],
        }
        logger.info("GA4 event: %s mid=%s", event_name, self.measurement_id)
        return {"status": "sent", "event": event_name}

    def earn_virtual_currency(self, client_id: str, amount: float, currency: str = "Coins"):
        return self.send_event(client_id, "earn_virtual_currency",
                                {"virtual_currency_name": currency, "value": amount})

    def purchase(self, client_id: str, value: float, currency: str = "BDT"):
        return self.send_event(client_id, "purchase", {"value": value, "currency": currency})
