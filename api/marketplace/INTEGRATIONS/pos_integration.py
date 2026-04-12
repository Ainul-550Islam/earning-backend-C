"""
INTEGRATIONS/pos_integration.py — POS (Point of Sale) Integration
Allows offline brick-and-mortar stores to sync with marketplace inventory.
"""
import logging
import requests

logger = logging.getLogger(__name__)


class POSSyncService:
    def __init__(self, pos_endpoint: str, api_key: str, seller, tenant):
        self.endpoint = pos_endpoint
        self.headers  = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.seller   = seller
        self.tenant   = tenant

    def pull_pos_sales(self) -> list:
        """Pull completed POS transactions to create marketplace orders."""
        try:
            resp = requests.get(f"{self.endpoint}/transactions", headers=self.headers, timeout=10)
            return resp.json().get("transactions", [])
        except Exception as e:
            logger.error("[POS] pull_sales error: %s", e)
            return []

    def push_inventory_update(self, sku: str, quantity: int) -> bool:
        """Push inventory changes to POS after online sale."""
        try:
            resp = requests.put(
                f"{self.endpoint}/inventory/{sku}",
                json={"quantity": quantity},
                headers=self.headers, timeout=10,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error("[POS] push_inventory error: %s", e)
            return False

    def sync_product_catalog(self, products: list) -> dict:
        """Push all active products to POS terminal."""
        payload = [
            {"sku": p.get("sku"), "name": p.get("name"), "price": p.get("price"), "stock": p.get("stock")}
            for p in products
        ]
        try:
            resp = requests.post(
                f"{self.endpoint}/catalog/sync",
                json={"products": payload},
                headers=self.headers, timeout=30,
            )
            return resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_order_from_pos(self, pos_transaction: dict):
        """Convert a POS transaction to a marketplace Order for unified reporting."""
        from api.marketplace.models import Order
        from api.marketplace.enums import OrderStatus
        return Order.objects.create(
            tenant=self.tenant,
            user=None,
            shipping_name=pos_transaction.get("customer_name","Walk-in Customer"),
            shipping_phone=pos_transaction.get("phone",""),
            shipping_address="In-store",
            shipping_city="In-store",
            total_price=pos_transaction.get("total", 0),
            payment_method=pos_transaction.get("payment_method","cash"),
            is_paid=True,
            status=OrderStatus.DELIVERED,
            notes=f"POS transaction #{pos_transaction.get('id','')}",
        )
