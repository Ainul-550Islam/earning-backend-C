"""ORDER_MANAGEMENT/order_item.py — OrderItem helpers"""
from api.marketplace.models import OrderItem


def get_seller_items(seller, status=None):
    qs = OrderItem.objects.filter(seller=seller).select_related("order", "variant__product")
    if status:
        qs = qs.filter(item_status=status)
    return qs.order_by("-created_at")


def item_summary(item: OrderItem) -> dict:
    return {
        "id": item.pk,
        "order": item.order.order_number,
        "product": item.product_name,
        "variant": item.variant_name,
        "qty": item.quantity,
        "unit_price": str(item.unit_price),
        "subtotal": str(item.subtotal),
        "commission": str(item.commission_amount),
        "seller_net": str(item.seller_net),
        "status": item.item_status,
    }
