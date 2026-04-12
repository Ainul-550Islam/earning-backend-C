"""INTEGRATIONS/shopify_integration.py — Shopify Product Sync"""
import logging
import requests
logger = logging.getLogger(__name__)


class ShopifySync:
    def __init__(self, shop_domain: str, access_token: str):
        self.base = f"https://{shop_domain}/admin/api/2024-01"
        self.headers = {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}

    def import_products(self, limit=50) -> list:
        try:
            resp = requests.get(f"{self.base}/products.json?limit={limit}", headers=self.headers, timeout=15)
            return resp.json().get("products", [])
        except Exception as e:
            logger.error("[Shopify] import_products: %s", e)
            return []

    def push_product(self, product) -> dict:
        payload = {
            "product": {
                "title": product.name,
                "body_html": product.description,
                "vendor": product.seller.store_name if product.seller else "",
                "variants": [{"price": str(product.base_price)}],
            }
        }
        try:
            resp = requests.post(f"{self.base}/products.json", json=payload, headers=self.headers, timeout=15)
            return resp.json()
        except Exception as e:
            logger.error("[Shopify] push_product: %s", e)
            return {}
