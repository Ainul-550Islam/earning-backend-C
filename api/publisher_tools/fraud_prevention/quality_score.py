# api/publisher_tools/fraud_prevention/quality_score.py
"""Quality Score — Traffic quality scoring for publishers and sites."""
from typing import Dict
from datetime import timedelta


def calculate_publisher_quality_score(publisher) -> Dict:
    """Publisher-এর overall traffic quality score।"""
    from api.publisher_tools.models import TrafficSafetyLog, PublisherEarning
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone
    start = timezone.now().date() - timedelta(days=30)
    ivt_logs = TrafficSafetyLog.objects.filter(publisher=publisher, detected_at__date__gte=start, is_false_positive=False)
    earnings  = PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
    total_impressions = earnings.aggregate(t=Sum("impressions")).get("t") or 0
    ivt_impressions   = ivt_logs.aggregate(t=Sum("affected_impressions")).get("t") or 0
    ivt_rate = float(ivt_impressions) / max(total_impressions, 1) * 100
    high_severity = ivt_logs.filter(severity__in=["high","critical"]).count()
    score = 100
    score -= min(50, ivt_rate * 2)
    score -= min(30, high_severity * 5)
    if publisher.is_kyc_verified:
        score += 5
    return {
        "publisher_id":    publisher.publisher_id,
        "quality_score":   max(0, min(100, round(score))),
        "ivt_rate_30d":    round(ivt_rate, 2),
        "ivt_events_30d":  ivt_logs.count(),
        "high_severity":   high_severity,
        "total_impressions_30d": total_impressions,
        "grade": "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D",
    }


def calculate_composite_fraud_score(ua_score: int, ip_score: int, velocity_score: int = 0, device_score: int = 0) -> int:
    weighted = ua_score * 0.25 + ip_score * 0.30 + velocity_score * 0.25 + device_score * 0.20
    return min(100, round(weighted))


def get_risk_level(score: int) -> str:
    if score >= 80: return "critical"
    if score >= 60: return "high"
    if score >= 40: return "medium"
    return "low"
