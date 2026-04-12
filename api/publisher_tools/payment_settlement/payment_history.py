# api/publisher_tools/payment_settlement/payment_history.py
"""Payment History — Complete payment transaction history."""
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List
from django.db.models import Sum, Count
from django.utils import timezone


def get_payment_history(publisher, limit: int = 50) -> List[Dict]:
    """Publisher-এর payment history।"""
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    payouts = PayoutRequest.objects.filter(publisher=publisher).select_related("bank_account").order_by("-created_at")[:limit]
    return [
        {
            "request_id":   p.request_id,
            "type":         "payout",
            "amount":       float(p.requested_amount),
            "net_amount":   float(p.net_amount or 0),
            "currency":     "USD",
            "status":       p.status,
            "payment_method": p.bank_account.get_account_type_display() if p.bank_account else "N/A",
            "reference":    p.payment_reference,
            "date":         str(p.created_at.date()),
            "completed":    str(p.completed_at) if p.completed_at else None,
        }
        for p in payouts
    ]


def get_payment_summary(publisher, year: int = None) -> Dict:
    """Annual payment summary।"""
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    from api.publisher_tools.models import PublisherInvoice
    year = year or timezone.now().year
    payouts = PayoutRequest.objects.filter(publisher=publisher, created_at__year=year)
    invoices = PublisherInvoice.objects.filter(publisher=publisher, period_start__year=year)
    paid = payouts.filter(status="completed")
    return {
        "year":              year,
        "total_paid":        float(paid.aggregate(t=Sum("net_amount")).get("t") or 0),
        "total_requested":   float(payouts.aggregate(t=Sum("requested_amount")).get("t") or 0),
        "payout_count":      paid.count(),
        "pending_payouts":   payouts.filter(status="pending").count(),
        "total_invoiced":    float(invoices.aggregate(t=Sum("net_payable")).get("t") or 0),
        "paid_invoices":     invoices.filter(status="paid").count(),
    }


def get_lifetime_payment_stats(publisher) -> Dict:
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    paid = PayoutRequest.objects.filter(publisher=publisher, status="completed")
    return {
        "lifetime_paid":    float(paid.aggregate(t=Sum("net_amount")).get("t") or 0),
        "total_payouts":    paid.count(),
        "avg_payout_size":  float(paid.aggregate(a=Sum("net_amount")).get("a") or 0) / max(paid.count(), 1),
        "largest_payout":   float(max((p.net_amount for p in paid if p.net_amount), default=Decimal("0"))),
        "member_since":     str(publisher.created_at.date()),
    }
