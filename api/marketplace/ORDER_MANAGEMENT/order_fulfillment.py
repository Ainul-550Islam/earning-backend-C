"""ORDER_MANAGEMENT/order_fulfillment.py — Order Fulfillment Pipeline"""
from api.marketplace.models import Order, OrderItem
from api.marketplace.enums import OrderStatus
from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import deduct


def fulfill_order(order: Order, fulfilled_by=None) -> bool:
    """Mark all items fulfilled and deduct inventory."""
    for item in order.items.filter(variant__isnull=False):
        deduct(item.variant_id, item.quantity)
        item.item_status = OrderStatus.PROCESSING
        item.save(update_fields=["item_status"])
    order.status = OrderStatus.PROCESSING
    order.save(update_fields=["status"])
    return True


def partial_fulfill(order: Order, item_ids: list) -> bool:
    """Partially fulfill specific order items."""
    for item in order.items.filter(pk__in=item_ids, variant__isnull=False):
        deduct(item.variant_id, item.quantity)
        item.item_status = OrderStatus.PROCESSING
        item.save(update_fields=["item_status"])
    return True


def get_pending_fulfillments(seller):
    return OrderItem.objects.filter(
        seller=seller,
        item_status__in=[OrderStatus.CONFIRMED, OrderStatus.PROCESSING],
        order__is_paid=True,
    ).select_related("order", "variant__product").order_by("order__created_at")
