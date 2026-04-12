"""
INTEGRATIONS/erp_integration.py — ERP System Integration
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ERPBase:
    def push_order(self, order_data: dict) -> dict:
        raise NotImplementedError

    def pull_inventory(self, sku_list: list) -> dict:
        raise NotImplementedError

    def push_invoice(self, invoice_data: dict) -> dict:
        raise NotImplementedError


class OdooERP(ERPBase):
    """Integration with Odoo ERP via XML-RPC."""

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url  = url
        self.db   = db
        self.uid  = None
        self._auth(username, password)

    def _auth(self, username: str, password: str):
        try:
            import xmlrpc.client
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, username, password, {})
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
            self.password = password
        except Exception as e:
            logger.error("[ERP] Odoo auth failed: %s", e)

    def push_order(self, order_data: dict) -> dict:
        if not self.uid:
            return {"error": "Not authenticated"}
        try:
            self.models.execute_kw(
                self.db, self.uid, self.password,
                "sale.order", "create", [order_data],
            )
            return {"success": True}
        except Exception as e:
            logger.error("[ERP] Odoo push_order error: %s", e)
            return {"error": str(e)}

    def pull_inventory(self, sku_list: list) -> dict:
        if not self.uid:
            return {}
        try:
            products = self.models.execute_kw(
                self.db, self.uid, self.password,
                "product.product", "search_read",
                [[["default_code", "in", sku_list]]],
                {"fields": ["default_code", "qty_available"]},
            )
            return {p["default_code"]: p["qty_available"] for p in products}
        except Exception as e:
            logger.error("[ERP] Odoo pull_inventory error: %s", e)
            return {}

    def push_invoice(self, invoice_data: dict) -> dict:
        return {"message": "Invoice push not yet implemented"}


def get_erp() -> ERPBase:
    erp_config = getattr(settings, "ERP_CONFIG", {})
    if not erp_config:
        return None
    erp_type = erp_config.get("type", "odoo")
    if erp_type == "odoo":
        return OdooERP(
            url=erp_config["url"], db=erp_config["db"],
            username=erp_config["username"], password=erp_config["password"],
        )
    return None


def sync_order_to_erp(order):
    erp = get_erp()
    if not erp:
        return
    from api.marketplace.ORDER_MANAGEMENT.order_invoice import generate_invoice_data
    data = generate_invoice_data(order)
    try:
        erp.push_order(data)
        logger.info("[ERP] Order %s synced to ERP", order.order_number)
    except Exception as e:
        logger.error("[ERP] sync_order_to_erp error: %s", e)
