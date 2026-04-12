"""
PAYMENT_SETTLEMENT/settlement_report.py — Financial Settlement Reports
"""
from django.db.models import Sum, Count
from api.marketplace.models import SellerPayout, OrderItem, EscrowHolding


def generate_settlement_summary(tenant, from_date, to_date) -> dict:
    payouts = SellerPayout.objects.filter(tenant=tenant, created_at__date__range=[from_date, to_date])
    items = OrderItem.objects.filter(tenant=tenant, order__created_at__date__range=[from_date, to_date])
    agg = items.aggregate(gross=Sum("subtotal"), commission=Sum("commission_amount"), seller_net=Sum("seller_net"))
    return {
        "period":              f"{from_date} – {to_date}",
        "gross_revenue":       str(agg["gross"] or 0),
        "platform_commission": str(agg["commission"] or 0),
        "total_seller_net":    str(agg["seller_net"] or 0),
        "payouts_initiated":   str(payouts.aggregate(t=Sum("amount"))["t"] or 0),
        "payouts_completed":   str(payouts.filter(status="completed").aggregate(t=Sum("amount"))["t"] or 0),
        "payouts_pending":     str(payouts.filter(status="pending").aggregate(t=Sum("amount"))["t"] or 0),
        "total_orders":        items.values("order").distinct().count(),
    }


def generate_seller_settlement(seller, from_date, to_date) -> dict:
    items = OrderItem.objects.filter(seller=seller, order__created_at__date__range=[from_date, to_date])
    agg = items.aggregate(gross=Sum("subtotal"), commission=Sum("commission_amount"), net=Sum("seller_net"))
    return {
        "seller":         seller.store_name,
        "period":         f"{from_date} – {to_date}",
        "gross_sales":    str(agg["gross"] or 0),
        "commission":     str(agg["commission"] or 0),
        "net_earned":     str(agg["net"] or 0),
        "order_count":    items.values("order").distinct().count(),
    }
