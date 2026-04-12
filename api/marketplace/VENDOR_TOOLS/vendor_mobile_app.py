"""VENDOR_TOOLS/vendor_mobile_app.py — Vendor Mobile App API Helpers"""
from api.marketplace.models import SellerProfile
from api.marketplace.VENDOR_TOOLS.vendor_dashboard import get_dashboard_data
from api.marketplace.VENDOR_TOOLS.order_management_tool import get_seller_orders
from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import get_low_stock_items


def get_mobile_seller_home(seller: SellerProfile) -> dict:
    """All data needed for vendor app home screen in one call."""
    dashboard   = get_dashboard_data(seller)
    low_stock   = get_low_stock_items(seller.tenant, threshold=5)
    pending_qs  = get_seller_orders(seller, status="pending", page=1, page_size=5)

    return {
        "dashboard": dashboard,
        "pending_orders_count": pending_qs["total"],
        "low_stock_alerts": [
            {"sku": i.variant.sku, "name": i.variant.product.name, "qty": i.quantity}
            for i in low_stock[:5]
        ],
        "requires_action": {
            "pending_orders":    pending_qs["total"],
            "low_stock_items":   low_stock.count(),
        },
    }
