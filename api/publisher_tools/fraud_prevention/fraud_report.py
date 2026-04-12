# api/publisher_tools/fraud_prevention/fraud_report.py
"""Fraud Report — Comprehensive fraud analysis reports."""
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List
from django.db.models import Sum, Count, Avg
from django.utils import timezone


def generate_fraud_report(publisher, days: int = 30) -> Dict:
    """Publisher-এর comprehensive fraud report।"""
    from api.publisher_tools.models import TrafficSafetyLog, PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    logs = TrafficSafetyLog.objects.filter(publisher=publisher, detected_at__date__gte=start, is_false_positive=False)
    agg = logs.aggregate(
        total=Count("id"), avg_score=Avg("fraud_score"),
        revenue_at_risk=Sum("revenue_at_risk"), deducted=Sum("revenue_deducted"),
    )
    by_type = list(logs.values("traffic_type").annotate(count=Count("id"), revenue=Sum("revenue_at_risk")).order_by("-count"))
    by_severity = list(logs.values("severity").annotate(count=Count("id")).order_by("severity"))
    earnings_agg = PublisherEarning.objects.filter(publisher=publisher, date__gte=start).aggregate(
        impressions=Sum("impressions"), revenue=Sum("publisher_revenue"),
    )
    total_impressions = earnings_agg.get("impressions") or 0
    affected_impressions = logs.aggregate(t=Sum("affected_impressions")).get("t") or 0
    ivt_rate = round(float(affected_impressions) / max(total_impressions, 1) * 100, 2)
    return {
        "publisher_id":   publisher.publisher_id,
        "period_days":    days,
        "summary": {
            "total_ivt_events":    agg.get("total") or 0,
            "avg_fraud_score":     round(float(agg.get("avg_score") or 0), 2),
            "revenue_at_risk_usd": float(agg.get("revenue_at_risk") or 0),
            "revenue_deducted_usd":float(agg.get("deducted") or 0),
            "ivt_rate_pct":        ivt_rate,
            "affected_impressions":affected_impressions,
            "total_impressions":   total_impressions,
        },
        "by_type":     by_type,
        "by_severity": by_severity,
        "top_ips":     list(logs.exclude(ip_address="").values("ip_address").annotate(count=Count("id")).order_by("-count")[:10]),
        "risk_level":  "critical" if ivt_rate >= 40 else "high" if ivt_rate >= 20 else "medium" if ivt_rate >= 10 else "low",
    }


def generate_platform_fraud_report(days: int = 30) -> Dict:
    """Platform-wide fraud report (admin only)。"""
    from api.publisher_tools.models import TrafficSafetyLog
    start = timezone.now().date() - timedelta(days=days)
    logs = TrafficSafetyLog.objects.filter(detected_at__date__gte=start, is_false_positive=False)
    return {
        "period_days":  days,
        "total_events": logs.count(),
        "by_type":      list(logs.values("traffic_type").annotate(count=Count("id")).order_by("-count")[:10]),
        "by_severity":  list(logs.values("severity").annotate(count=Count("id"))),
        "publishers_affected": logs.values("publisher").distinct().count(),
        "revenue_deducted":    float(logs.aggregate(t=Sum("revenue_deducted")).get("t") or 0),
    }
