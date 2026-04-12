"""VENDOR_TOOLS/shipping_label_bulk.py — Bulk Shipping Label Generation"""
import logging
logger = logging.getLogger(__name__)


def generate_labels_for_seller(seller, order_ids: list) -> list:
    """
    Generate shipping labels for multiple orders.
    In production: integrate with Steadfast/Pathao API.
    """
    from api.marketplace.models import Order
    orders = Order.objects.filter(pk__in=order_ids, items__seller=seller).distinct()
    labels = []
    for order in orders:
        label = {
            "order_number": order.order_number,
            "recipient_name": order.shipping_name,
            "phone": order.shipping_phone,
            "address": order.shipping_address,
            "city": order.shipping_city,
            "cod_amount": str(order.total_price) if not order.is_paid else "0",
            "label_data": f"LABEL-{order.order_number}",   # In prod: PDF/QR from courier API
        }
        labels.append(label)
        logger.info("[LabelGen] Generated label for %s", order.order_number)
    return labels
