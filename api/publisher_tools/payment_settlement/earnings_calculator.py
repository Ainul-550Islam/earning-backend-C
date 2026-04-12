# api/publisher_tools/payment_settlement/earnings_calculator.py
"""Earnings Calculator — Revenue calculation pipeline."""
from decimal import Decimal
from datetime import date
from calendar import monthrange
from typing import Dict
from django.db.models import Sum


def calculate_monthly_earnings(publisher, year: int, month: int) -> Dict:
    """Publisher-এর monthly earnings calculate করে।"""
    from api.publisher_tools.models import PublisherEarning
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end   = date(year, month, last_day)
    agg = PublisherEarning.objects.filter(
        publisher=publisher, date__range=[start, end], status__in=["confirmed","finalized"],
    ).aggregate(
        gross=Sum("gross_revenue"), publisher=Sum("publisher_revenue"),
        impressions=Sum("impressions"), clicks=Sum("clicks"),
        ivt=Sum("invalid_traffic_deduction"),
    )
    publisher_rev = Decimal(str(agg.get("publisher") or 0))
    ivt_ded = Decimal(str(agg.get("ivt") or 0))
    net = max(Decimal("0"), publisher_rev - ivt_ded)
    return {
        "year": year, "month": month,
        "gross_revenue":    float(agg.get("gross") or 0),
        "publisher_revenue":float(publisher_rev),
        "ivt_deduction":    float(ivt_ded),
        "net_earnings":     float(net),
        "impressions":      agg.get("impressions") or 0,
        "clicks":           agg.get("clicks") or 0,
    }


def calculate_daily_earnings(publisher, report_date: date) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    agg = PublisherEarning.objects.filter(publisher=publisher, date=report_date).aggregate(
        gross=Sum("gross_revenue"), publisher=Sum("publisher_revenue"),
        impressions=Sum("impressions"), ivt=Sum("invalid_traffic_deduction"),
    )
    return {
        "date": str(report_date),
        "gross_revenue": float(agg.get("gross") or 0),
        "publisher_revenue": float(agg.get("publisher") or 0),
        "ivt_deduction": float(agg.get("ivt") or 0),
        "net_earnings": float(max(Decimal("0"), Decimal(str(agg.get("publisher") or 0)) - Decimal(str(agg.get("ivt") or 0)))),
        "impressions": agg.get("impressions") or 0,
    }


def apply_revenue_adjustment(publisher, amount: Decimal, reason: str, adjusted_by=None) -> None:
    """Revenue adjustment apply করে।"""
    from api.publisher_tools.models import PublisherEarning
    from django.utils import timezone
    PublisherEarning.objects.create(
        publisher=publisher, granularity="daily", date=timezone.now().date(),
        earning_type="display", gross_revenue=amount, publisher_revenue=amount,
        adjustment_amount=amount, adjustment_reason=reason, status="adjusted",
        impressions=0, clicks=0, ad_requests=0,
    )
