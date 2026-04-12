"""
VENDOR_TOOLS/order_management_tool.py — Seller Order Management Dashboard Tool
"""
from __future__ import annotations
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q

logger = logging.getLogger(__name__)


class SellerOrderManager:

    def __init__(self, seller, tenant):
        self.seller = seller
        self.tenant = tenant

    # ── Order listing ─────────────────────────────────────────────────────────
    def get_orders(self, status: str = None, from_date=None, to_date=None,
                   search: str = None, page: int = 1, page_size: int = 20) -> dict:
        from api.marketplace.models import OrderItem, Order
        order_ids = OrderItem.objects.filter(
            seller=self.seller, tenant=self.tenant
        ).values_list("order_id", flat=True).distinct()

        qs = Order.objects.filter(pk__in=order_ids).order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search) |
                Q(shipping_name__icontains=search) |
                Q(shipping_phone__icontains=search)
            )

        total  = qs.count()
        offset = (page - 1) * page_size
        orders = qs[offset: offset + page_size]

        return {
            "total": total,
            "page": page,
            "num_pages": -(-total // page_size),
            "orders": [self._format_order(o) for o in orders],
        }

    def _format_order(self, order) -> dict:
        from api.marketplace.models import OrderItem
        items = OrderItem.objects.filter(order=order, seller=self.seller)
        return {
            "order_number":    order.order_number,
            "status":          order.status,
            "created_at":      order.created_at.strftime("%Y-%m-%d %H:%M"),
            "customer_name":   order.shipping_name,
            "customer_phone":  order.shipping_phone,
            "city":            order.shipping_city,
            "is_paid":         order.is_paid,
            "items":           [{"product": i.product_name, "qty": i.quantity,
                                  "subtotal": str(i.subtotal)} for i in items],
            "seller_earnings": str(sum(i.seller_net for i in items)),
        }

    # ── Order actions ─────────────────────────────────────────────────────────
    @transaction.atomic
    def confirm_order(self, order_number: str) -> dict:
        from api.marketplace.models import Order
        from api.marketplace.enums import OrderStatus
        try:
            order = Order.objects.get(order_number=order_number, tenant=self.tenant)
        except Order.DoesNotExist:
            return {"success": False, "error": "Order not found"}
        if order.status != OrderStatus.PENDING:
            return {"success": False, "error": f"Cannot confirm order in '{order.status}' state"}
        order.status = OrderStatus.CONFIRMED
        order.save(update_fields=["status"])
        from api.marketplace.models import OrderTracking
        from api.marketplace.enums import TrackingEvent
        OrderTracking.objects.create(
            tenant=self.tenant, order=order,
            event=TrackingEvent.SELLER_CONFIRMED,
            description="Order confirmed by seller",
        )
        logger.info("[SellerOrders] Confirmed: %s", order_number)
        return {"success": True, "status": "confirmed"}

    @transaction.atomic
    def mark_shipped(self, order_number: str, courier: str, tracking_no: str) -> dict:
        from api.marketplace.models import Order, OrderTracking
        from api.marketplace.enums import OrderStatus, TrackingEvent
        try:
            order = Order.objects.get(order_number=order_number, tenant=self.tenant)
        except Order.DoesNotExist:
            return {"success": False, "error": "Order not found"}
        order.status = OrderStatus.SHIPPED
        order.save(update_fields=["status"])
        OrderTracking.objects.create(
            tenant=self.tenant, order=order,
            event=TrackingEvent.PICKED_UP,
            description=f"Picked up by {courier}",
            courier_name=courier, tracking_number=tracking_no,
        )
        return {"success": True, "tracking_number": tracking_no}

    # ── Stats ──────────────────────────────────────────────────────────────────
    def dashboard_stats(self, days: int = 30) -> dict:
        from api.marketplace.models import OrderItem
        from api.marketplace.enums import OrderStatus
        since = timezone.now() - timezone.timedelta(days=days)
        items = OrderItem.objects.filter(
            seller=self.seller, tenant=self.tenant,
            created_at__gte=since,
        )
        agg = items.aggregate(
            revenue=Sum("seller_net"),
            orders=Count("order", distinct=True),
            units=Sum("quantity"),
        )
        pending = items.filter(item_status=OrderStatus.PENDING).count()
        return {
            "period_days":   days,
            "total_revenue": str(agg["revenue"] or 0),
            "total_orders":  agg["orders"] or 0,
            "units_sold":    agg["units"] or 0,
            "pending_orders":pending,
        }

    # ── Bulk actions ──────────────────────────────────────────────────────────
    def bulk_confirm(self, order_numbers: list) -> dict:
        results = {"confirmed": 0, "failed": 0}
        for num in order_numbers:
            r = self.confirm_order(num)
            if r["success"]:
                results["confirmed"] += 1
            else:
                results["failed"] += 1
        return results
