"""INTEGRATIONS/woocommerce_integration.py — WooCommerce REST API Sync"""
import logging
import requests
logger = logging.getLogger(__name__)


class WooCommerceSync:
    def __init__(self, site_url: str, consumer_key: str, consumer_secret: str):
        self.base = f"{site_url}/wp-json/wc/v3"
        self.auth = (consumer_key, consumer_secret)

    def get_products(self, per_page=20) -> list:
        try:
            resp = requests.get(f"{self.base}/products", auth=self.auth,
                                params={"per_page": per_page}, timeout=15)
            return resp.json()
        except Exception as e:
            logger.error("[WooCommerce] get_products: %s", e)
            return []

    def sync_orders(self) -> list:
        try:
            resp = requests.get(f"{self.base}/orders", auth=self.auth,
                                params={"per_page": 50, "status": "processing"}, timeout=15)
            return resp.json()
        except Exception as e:
            logger.error("[WooCommerce] sync_orders: %s", e)
            return []
