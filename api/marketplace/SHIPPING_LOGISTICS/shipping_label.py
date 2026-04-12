"""
SHIPPING_LOGISTICS/shipping_label.py — Shipping Label Generation
"""
from api.marketplace.models import Order


def generate_label_data(order: Order, carrier_name: str = "") -> dict:
    """Returns all data needed to print a shipping label."""
    return {
        "barcode":         order.order_number,
        "order_number":    order.order_number,
        "carrier":         carrier_name,
        "to_name":         order.shipping_name,
        "to_phone":        order.shipping_phone,
        "to_address":      order.shipping_address,
        "to_city":         order.shipping_city,
        "to_district":     order.shipping_district,
        "to_postal":       order.shipping_postal_code,
        "to_country":      order.shipping_country,
        "cod_amount":      str(order.total_price) if order.payment_method == "cod" else "0",
        "is_cod":          order.payment_method == "cod",
        "items_count":     order.items.count(),
        "items_summary":   ", ".join(
            f"{i.product_name} x{i.quantity}" for i in order.items.all()[:3]
        ),
        "weight_grams":    sum(
            (i.variant.weight_grams if i.variant else 200) * i.quantity
            for i in order.items.all()
        ),
        "printed_at":      __import__("django.utils.timezone", fromlist=["timezone"]).timezone.now().isoformat(),
    }


def generate_bulk_labels(orders: list, carrier_name: str = "") -> list:
    return [generate_label_data(order, carrier_name) for order in orders]
