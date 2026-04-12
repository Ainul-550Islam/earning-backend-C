#!/usr/bin/env python
# api/publisher_tools/scripts/detect_fraud.py
"""
Detect Fraud — Automated fraud detection pipeline।
Bot traffic, click fraud, impression fraud detect করে।
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def scan_recent_traffic_logs(hours: int = 24):
    """Recent traffic logs scan করে fraud detect করে।"""
    from api.publisher_tools.models import TrafficSafetyLog
    from api.publisher_tools.fraud_prevention.quality_score import get_risk_level
    start = timezone.now() - timedelta(hours=hours)
    logs = TrafficSafetyLog.objects.filter(
        detected_at__gte=start, action_taken="pending", is_false_positive=False,
    ).select_related("publisher")
    processed = 0
    auto_blocked = 0
    for log in logs:
        try:
            if log.fraud_score >= 80:
                log.action_taken = "blocked"
                log.save(update_fields=["action_taken", "updated_at"])
                auto_blocked += 1
            elif log.fraud_score >= 60:
                log.action_taken = "flagged"
                log.save(update_fields=["action_taken", "updated_at"])
            processed += 1
        except Exception as e:
            logger.error(f"Fraud log processing error: {e}")
    print(f"✅ Fraud logs: {processed} processed, {auto_blocked} auto-blocked")
    return {"processed": processed, "auto_blocked": auto_blocked}


def detect_click_farms():
    """Click farm patterns detect করে।"""
    from api.publisher_tools.models import TrafficSafetyLog
    from django.db.models import Count
    start = timezone.now() - timedelta(hours=24)
    suspicious_ips = list(
        TrafficSafetyLog.objects.filter(
            detected_at__gte=start,
            traffic_type="click_fraud",
            is_false_positive=False,
        ).values("ip_address").annotate(count=Count("id")).filter(count__gte=10).order_by("-count")[:50]
    )
    blocked = 0
    for ip_data in suspicious_ips:
        if not ip_data.get("ip_address"):
            continue
        try:
            from api.publisher_tools.fraud_prevention.ip_blacklist import block_ip
            block_ip(ip_data["ip_address"], f"Click farm detected: {ip_data['count']} events", fraud_score=90, hours=48)
            blocked += 1
        except Exception as e:
            logger.error(f"IP block error [{ip_data['ip_address']}]: {e}")
    print(f"✅ Click farm detection: {len(suspicious_ips)} suspicious IPs, {blocked} blocked")
    return {"suspicious": len(suspicious_ips), "blocked": blocked}


def detect_device_farms():
    """Device farm patterns detect করে।"""
    from api.publisher_tools.models import TrafficSafetyLog
    from django.db.models import Count, Q
    start = timezone.now() - timedelta(hours=24)
    device_logs = TrafficSafetyLog.objects.filter(
        detected_at__gte=start,
        traffic_type__in=["device_farm", "emulator"],
        is_false_positive=False,
        action_taken="pending",
    )
    flagged = device_logs.update(action_taken="flagged", severity="high")
    print(f"✅ Device farm detection: {flagged} logs flagged")
    return {"flagged": flagged}


def calculate_revenue_impact():
    """Today-এর fraud revenue impact calculate করে।"""
    from api.publisher_tools.models import TrafficSafetyLog
    today = timezone.now().date()
    from django.db.models import Sum
    agg = TrafficSafetyLog.objects.filter(
        detected_at__date=today, is_false_positive=False,
    ).aggregate(
        at_risk=Sum("revenue_at_risk"), deducted=Sum("revenue_deducted"),
    )
    impact = {
        "revenue_at_risk_today": float(agg.get("at_risk") or 0),
        "revenue_deducted_today":float(agg.get("deducted") or 0),
        "date":                  str(today),
    }
    print(f"✅ Revenue impact: ${impact['revenue_at_risk_today']:.4f} at risk, ${impact['revenue_deducted_today']:.4f} deducted")
    return impact


def run():
    print(f"🔄 Fraud detection started at {timezone.now()}")
    return {
        "traffic_scan":   scan_recent_traffic_logs(),
        "click_farms":    detect_click_farms(),
        "device_farms":   detect_device_farms(),
        "revenue_impact": calculate_revenue_impact(),
        "completed_at":   timezone.now().isoformat(),
    }

if __name__ == "__main__":
    run()
