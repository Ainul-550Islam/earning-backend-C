#!/usr/bin/env python
# api/publisher_tools/scripts/clean_logs.py
"""
Clean Logs — Old log cleanup ও database maintenance।
Disk space ও query performance optimize করে।
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def clean_webhook_delivery_logs(days: int = 30):
    """Old webhook delivery logs cleanup করে।"""
    from api.publisher_tools.webhooks.webhook_logger import cleanup_old_logs
    result = cleanup_old_logs(days)
    print(f"✅ Webhook logs cleaned: {result['total_deleted']} records deleted")
    return result


def clean_old_traffic_safety_logs(days: int = 90):
    """Old IVT logs cleanup করে।"""
    from api.publisher_tools.models import TrafficSafetyLog
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = TrafficSafetyLog.objects.filter(
        detected_at__lt=cutoff,
        is_false_positive=True,
        action_taken__in=["no_action", "flagged"],
    ).delete()
    print(f"✅ Traffic safety logs cleaned: {deleted} records")
    return {"deleted": deleted, "older_than_days": days}


def clean_resolved_fraud_alerts(days: int = 60):
    """Resolved fraud alerts cleanup করে।"""
    from api.publisher_tools.fraud_prevention.fraud_alert import FraudAlert
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = FraudAlert.objects.filter(
        is_resolved=True, resolved_at__lt=cutoff,
    ).delete()
    print(f"✅ Resolved fraud alerts cleaned: {deleted} records")
    return {"deleted": deleted}


def clean_old_performance_snapshots(months: int = 12):
    """Old performance snapshots cleanup করে।"""
    from api.publisher_tools.publisher_management.publisher_performance import PublisherPerformanceSnapshot
    cutoff = timezone.now() - timedelta(days=months * 30)
    deleted, _ = PublisherPerformanceSnapshot.objects.filter(created_at__lt=cutoff).delete()
    print(f"✅ Performance snapshots cleaned: {deleted} records")
    return {"deleted": deleted}


def clean_old_verification_tokens(days: int = 7):
    """Expired verification tokens cleanup করে।"""
    from api.publisher_tools.publisher_management.publisher_verification import PublisherVerification
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = PublisherVerification.objects.filter(
        expires_at__lt=cutoff, status__in=["expired","failed"],
    ).delete()
    print(f"✅ Old verification tokens cleaned: {deleted} records")
    return {"deleted": deleted}


def clean_old_database_records(days: int = 90):
    """Old database_models records cleanup করে।"""
    from api.publisher_tools.database_models.webhook_model import WebhookLogRecord
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = WebhookLogRecord.objects.filter(
        created_at__lt=cutoff, is_processed=True,
    ).delete()
    print(f"✅ Old DB records cleaned: {deleted} records")
    return {"deleted": deleted}


def run():
    print(f"🔄 Log cleanup started at {timezone.now()}")
    return {
        "webhook_logs":    clean_webhook_delivery_logs(days=30),
        "traffic_logs":    clean_old_traffic_safety_logs(days=90),
        "fraud_alerts":    clean_resolved_fraud_alerts(days=60),
        "perf_snapshots":  clean_old_performance_snapshots(months=12),
        "verify_tokens":   clean_old_verification_tokens(days=7),
        "db_records":      clean_old_database_records(days=90),
        "completed_at":    timezone.now().isoformat(),
    }

if __name__ == "__main__":
    run()
