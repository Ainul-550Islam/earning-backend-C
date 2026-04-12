"""INTEGRATIONS/appsflyer_integration.py — AppsFlyer MMP integration."""
import logging
logger = logging.getLogger(__name__)


class AppsFlyerIntegration:
    S2S_URL = "https://api2.appsflyer.com/inappevent/{app_id}"

    def __init__(self, dev_key: str = "", app_id: str = ""):
        self.dev_key = dev_key
        self.app_id  = app_id

    def track_event(self, customer_user_id: str, event_name: str,
                     event_value: dict = None) -> dict:
        payload = {
            "appsflyer_id":      customer_user_id,
            "customer_user_id":  customer_user_id,
            "eventName":         event_name,
            "eventValue":        event_value or {},
        }
        logger.info("AppsFlyer event: %s user=%s", event_name, customer_user_id)
        return {"status": "ok"}

    def track_purchase(self, user_id: str, revenue: float,
                        currency: str = "BDT", product_id: str = "") -> dict:
        return self.track_event(user_id, "af_purchase",
                                 {"af_revenue": revenue, "af_currency": currency,
                                  "af_content_id": product_id})
