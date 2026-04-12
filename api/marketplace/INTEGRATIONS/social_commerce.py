"""
INTEGRATIONS/social_commerce.py — Social Commerce (Facebook, Instagram, TikTok Shop)
"""
import logging
import requests

logger = logging.getLogger(__name__)


class FacebookShopSync:
    GRAPH_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str, catalog_id: str):
        self.token      = access_token
        self.catalog_id = catalog_id

    def sync_product(self, product) -> dict:
        item = {
            "id":          str(product.pk),
            "title":       product.name,
            "description": product.description[:9999],
            "availability":"in stock" if product.total_sales >= 0 else "out of stock",
            "condition":   "new",
            "price":       f"{product.effective_price} BDT",
            "link":        f"https://yoursite.com/products/{product.slug}/",
            "image_link":  "",
            "brand":       product.seller.store_name if product.seller else "",
        }
        try:
            resp = requests.post(
                f"{self.GRAPH_URL}/{self.catalog_id}/items_batch",
                params={"access_token": self.token},
                json={"requests": [{"method": "CREATE", "data": item}]},
                timeout=15,
            )
            return resp.json()
        except Exception as e:
            logger.error("[Facebook] sync_product error: %s", e)
            return {"error": str(e)}

    def bulk_sync(self, products: list, batch_size: int = 50) -> dict:
        total, errors = 0, 0
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            for p in batch:
                result = self.sync_product(p)
                if "error" in result:
                    errors += 1
                else:
                    total += 1
        return {"synced": total, "errors": errors}


class InstagramShopSync:
    """Instagram Shopping uses Facebook Catalog — delegate."""
    def __init__(self, access_token: str, catalog_id: str):
        self.fb = FacebookShopSync(access_token, catalog_id)

    def sync_product(self, product):
        return self.fb.sync_product(product)


class TikTokShopSync:
    BASE_URL = "https://open-api.tiktokglobalshop.com"

    def __init__(self, app_key: str, app_secret: str, shop_id: str):
        self.app_key    = app_key
        self.app_secret = app_secret
        self.shop_id    = shop_id

    def sync_product(self, product) -> dict:
        # TikTok Shop API is complex — stub implementation
        logger.info("[TikTok] sync_product %s (stub)", product.name)
        return {"status": "pending", "product_id": product.pk}
