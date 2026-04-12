"""ORDER_MANAGEMENT/order_refund.py — Order Refund Request Helpers"""
from api.marketplace.models import RefundRequest, OrderItem
from api.marketplace.enums import RefundStatus


def pending_refunds(seller):
    return RefundRequest.objects.filter(
        order_item__seller=seller,
        status__in=[RefundStatus.REQUESTED, RefundStatus.UNDER_REVIEW],
    ).select_related("order_item__order", "user")


def refund_history(user):
    return RefundRequest.objects.filter(user=user).order_by("-created_at")


def refund_stats(tenant) -> dict:
    from django.db.models import Count, Sum
    qs = RefundRequest.objects.filter(tenant=tenant)
    return {
        "total_requested": qs.count(),
        "approved": qs.filter(status=RefundStatus.APPROVED).count(),
        "pending": qs.filter(status=RefundStatus.REQUESTED).count(),
        "total_amount": str(qs.filter(status=RefundStatus.PROCESSED).aggregate(
            t=Sum("amount_approved"))["t"] or 0),
    }
