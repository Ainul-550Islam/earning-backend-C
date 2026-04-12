"""INTEGRATIONS/facebook_pixel.py — Facebook Pixel server-side events."""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class FacebookPixelIntegration:
    CAPI_URL = "https://graph.facebook.com/v18.0/{pixel_id}/events"

    def __init__(self, pixel_id: str = "", access_token: str = ""):
        self.pixel_id     = pixel_id
        self.access_token = access_token

    def send_event(self, event_name: str, user_data: dict,
                    custom_data: dict = None) -> dict:
        payload = {
            "data": [{
                "event_name":  event_name,
                "event_time":  __import__("time").time(),
                "user_data":   user_data,
                "custom_data": custom_data or {},
                "action_source": "app",
            }],
            "access_token": self.access_token,
        }
        logger.info("FB Pixel event: %s pixel=%s", event_name, self.pixel_id)
        return {"status": "sent", "event": event_name}

    def purchase(self, user_data: dict, value: Decimal, currency: str = "BDT"):
        return self.send_event("Purchase", user_data,
                                {"value": float(value), "currency": currency})

    def subscribe(self, user_data: dict, plan_name: str):
        return self.send_event("Subscribe", user_data, {"plan": plan_name})
