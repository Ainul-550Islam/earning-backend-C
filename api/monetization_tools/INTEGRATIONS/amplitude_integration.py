"""INTEGRATIONS/amplitude_integration.py — Amplitude analytics."""
import logging
logger = logging.getLogger(__name__)


class AmplitudeIntegration:
    URL = "https://api2.amplitude.com/2/httpapi"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def track(self, user_id: str, event_type: str,
               event_properties: dict = None, user_properties: dict = None) -> dict:
        payload = {
            "api_key": self.api_key,
            "events":  [{
                "user_id":          user_id,
                "event_type":       event_type,
                "event_properties": event_properties or {},
                "user_properties":  user_properties or {},
            }],
        }
        logger.info("Amplitude track: %s user=%s", event_type, user_id)
        return {"status": "sent", "event": event_type}

    def revenue(self, user_id: str, amount: float, product_id: str = ""):
        return self.track(user_id, "Revenue", {"revenue": amount, "productId": product_id})
