"""
INTEGRATIONS/amazon_integration.py — Amazon Marketplace Integration
Sync products to/from Amazon Seller Central via SP-API.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class AmazonSPAPI:
    """Amazon Selling Partner API integration stub."""

    BASE_URL = "https://sellingpartnerapi-eu.amazon.com"

    def __init__(self, refresh_token: str, client_id: str, client_secret: str):
        self.refresh_token = refresh_token
        self.client_id     = client_id
        self.client_secret = client_secret
        self._access_token = None

    def _get_access_token(self) -> str:
        import requests
        try:
            resp = requests.post(
                "https://api.amazon.com/auth/o2/token",
                data={
                    "grant_type":    "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id":     self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=10,
            )
            self._access_token = resp.json().get("access_token", "")
        except Exception as e:
            logger.error("[Amazon] Token refresh failed: %s", e)
        return self._access_token

    def list_catalog_item(self, asin: str) -> dict:
        import requests
        token = self._access_token or self._get_access_token()
        try:
            resp = requests.get(
                f"{self.BASE_URL}/catalog/2022-04-01/items/{asin}",
                headers={"x-amz-access-token": token},
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_pricing(self, asin: str) -> dict:
        import requests
        token = self._access_token or self._get_access_token()
        try:
            resp = requests.get(
                f"{self.BASE_URL}/products/pricing/v0/price",
                params={"Asins": asin, "MarketplaceId": "A21TJRUUN4KGV"},
                headers={"x-amz-access-token": token},
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


def sync_amazon_prices(tenant, seller) -> dict:
    """Pull competitor prices from Amazon for seller's products."""
    config = getattr(settings, "AMAZON_SP_API", {})
    if not config:
        return {"skipped": True, "reason": "Amazon SP-API not configured"}

    api   = AmazonSPAPI(**config)
    synced = 0
    from api.marketplace.models import Product
    for product in Product.objects.filter(seller=seller, tenant=tenant, status="active").iterator():
        if not product.tags or "asin:" not in product.tags:
            continue
        asin = next((t.split("asin:")[-1] for t in product.tags.split(",") if "asin:" in t), None)
        if asin:
            pricing = api.get_pricing(asin.strip())
            logger.debug("[Amazon] Price for ASIN %s: %s", asin, pricing)
            synced += 1

    return {"synced": synced}
