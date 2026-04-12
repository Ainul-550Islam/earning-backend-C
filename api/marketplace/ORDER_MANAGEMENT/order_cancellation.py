"""
ORDER_MANAGEMENT/order_cancellation.py — Order Cancellation Management
"""
from __future__ import annotations
from django.db import transaction
from django.utils import timezone
from api.marketplace.models import Order, OrderItem, OrderTracking
from api.marketplace.enums import OrderStatus, TrackingEvent


CANCELLABLE_STATUSES = [OrderStatus.PENDING, OrderStatus.CONFIRMED]

CANCELLATION_REASONS = [
    "changed_mind",
    "found_cheaper",
    "wrong_item_ordered",
    "payment_issue",
    "delivery_too_long",
    "out_of_stock",
    "seller_requested",
    "admin_action",
    "other",
]


def can_cancel(order: Order) -> dict:
    if order.status not in CANCELLABLE_STATUSES:
        return {"can_cancel": False, "reason": f"Cannot cancel order in '{order.status}' status"}
    if order.is_paid and order.status == OrderStatus.CONFIRMED:
        return {"can_cancel": True, "requires_refund": True, "reason": "Cancellation will trigger refund"}
    return {"can_cancel": True, "requires_refund": False, "reason": ""}


@transaction.atomic
def cancel_order(order: Order, reason: str, cancelled_by=None, is_seller: bool = False) -> dict:
    """
    Cancel an order with full stock release and optional refund.
    Returns: {"success": bool, "refund_initiated": bool, "message": str}
    """
    check = can_cancel(order)
    if not check["can_cancel"]:
        return {"success": False, "refund_initiated": False, "message": check["reason"]}

    # Release reserved inventory
    items_released = _release_inventory(order)

    # Cancel order
    order.status             = OrderStatus.CANCELLED
    order.cancelled_at       = timezone.now()
    order.cancellation_reason= reason
    order.save(update_fields=["status","cancelled_at","cancellation_reason"])

    # Add tracking event
    actor_label = "seller" if is_seller else ("admin" if cancelled_by and getattr(cancelled_by,"is_staff",False) else "buyer")
    OrderTracking.objects.create(
        tenant=order.tenant, order=order,
        event=TrackingEvent.ORDER_PLACED,   # reuse event for logging
        description=f"Order cancelled by {actor_label}. Reason: {reason}",
        created_by=cancelled_by,
    )

    # Initiate refund if paid
    refund_initiated = False
    if order.is_paid and check.get("requires_refund"):
        refund_initiated = _initiate_cancellation_refund(order)

    return {
        "success":          True,
        "refund_initiated": refund_initiated,
        "items_released":   items_released,
        "message":          "Order cancelled successfully.",
    }


@transaction.atomic
def cancel_and_release_stock(order: Order, reason: str = "") -> bool:
    """Legacy helper — cancel and release stock."""
    if order.status in (OrderStatus.CANCELLED, OrderStatus.DELIVERED, OrderStatus.REFUNDED):
        return False
    _release_inventory(order)
    order.cancel(reason)
    return True


def bulk_cancel(order_numbers: list, reason: str, admin_user) -> dict:
    """Bulk cancel multiple orders."""
    results = {"cancelled": 0, "failed": 0, "errors": []}
    for number in order_numbers:
        try:
            order = Order.objects.get(order_number=number)
            result = cancel_order(order, reason, admin_user)
            if result["success"]:
                results["cancelled"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({"order": number, "error": result["message"]})
        except Order.DoesNotExist:
            results["failed"] += 1
            results["errors"].append({"order": number, "error": "Not found"})
    return results


def get_cancellation_stats(tenant) -> dict:
    from django.db.models import Count
    qs = Order.objects.filter(tenant=tenant, status=OrderStatus.CANCELLED)
    total = Order.objects.filter(tenant=tenant).count()
    return {
        "total_cancelled":     qs.count(),
        "cancellation_rate":   round(qs.count() / max(1, total) * 100, 1),
        "by_reason":           dict(
            qs.values("cancellation_reason")
            .annotate(c=Count("id"))
            .values_list("cancellation_reason","c")
        ),
    }


def _release_inventory(order: Order) -> int:
    from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import release_reservation
    released = 0
    for item in order.items.filter(variant__isnull=False):
        try:
            release_reservation(item.variant_id, item.quantity)
            released += 1
        except Exception:
            pass
    return released


def _initiate_cancellation_refund(order: Order) -> bool:
    from api.marketplace.models import RefundRequest
    from api.marketplace.enums import RefundReason, RefundStatus
    try:
        for item in order.items.all():
            RefundRequest.objects.get_or_create(
                order_item=item,
                defaults={
                    "tenant":           order.tenant,
                    "user":             order.user,
                    "reason":           RefundReason.OTHER,
                    "description":      f"Cancellation refund for order {order.order_number}",
                    "amount_requested": item.subtotal,
                    "status":           RefundStatus.APPROVED,
                }
            )
        return True
    except Exception:
        return False
