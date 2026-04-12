#!/usr/bin/env python
# api/publisher_tools/scripts/health_check.py
"""
Health Check — System health monitoring ও alerting।
সব critical systems check করে।
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def check_database_health():
    """Database connection ও query performance check করে।"""
    import time
    from api.publisher_tools.models import Publisher
    try:
        start = time.time()
        count = Publisher.objects.filter(status="active").count()
        elapsed_ms = int((time.time() - start) * 1000)
        status = "healthy" if elapsed_ms < 100 else "slow" if elapsed_ms < 1000 else "critical"
        print(f"  DB: {status} ({elapsed_ms}ms) — {count} active publishers")
        return {"status": status, "response_ms": elapsed_ms, "active_publishers": count}
    except Exception as e:
        print(f"  DB: ERROR — {e}")
        return {"status": "error", "error": str(e)}


def check_cache_health():
    """Cache (Redis) connection check করে।"""
    import time
    from django.core.cache import cache
    try:
        start = time.time()
        cache.set("health_check", "ok", 10)
        value = cache.get("health_check")
        elapsed_ms = int((time.time() - start) * 1000)
        status = "healthy" if value == "ok" else "degraded"
        print(f"  Cache: {status} ({elapsed_ms}ms)")
        return {"status": status, "response_ms": elapsed_ms}
    except Exception as e:
        print(f"  Cache: ERROR — {e}")
        return {"status": "error", "error": str(e)}


def check_pending_tasks():
    """Pending tasks ও backlogs check করে।"""
    from api.publisher_tools.models import TrafficSafetyLog, PublisherInvoice
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    pending_ivt      = TrafficSafetyLog.objects.filter(action_taken="pending").count()
    pending_invoices = PublisherInvoice.objects.filter(status="draft").count()
    pending_payouts  = PayoutRequest.objects.filter(status="pending").count()
    overdue_invoices = PublisherInvoice.objects.filter(status="issued", due_date__lt=timezone.now().date()).count()
    print(f"  Pending IVT: {pending_ivt}, Pending invoices: {pending_invoices}, Pending payouts: {pending_payouts}, Overdue: {overdue_invoices}")
    return {
        "pending_ivt_actions": pending_ivt,
        "pending_invoices":    pending_invoices,
        "pending_payouts":     pending_payouts,
        "overdue_invoices":    overdue_invoices,
        "has_backlogs":        any([pending_ivt > 100, pending_invoices > 50, overdue_invoices > 0]),
    }


def check_webhook_health():
    """Webhook delivery health check করে।"""
    from api.publisher_tools.webhooks.webhook_manager import PublisherWebhook, WebhookDeliveryLog
    total_webhooks   = PublisherWebhook.objects.filter(is_active=True).count()
    failed_webhooks  = PublisherWebhook.objects.filter(status="failed").count()
    pending_retries  = WebhookDeliveryLog.objects.filter(status="retrying").count()
    print(f"  Webhooks: {total_webhooks} active, {failed_webhooks} failed, {pending_retries} pending retries")
    return {
        "active_webhooks": total_webhooks,
        "failed_webhooks": failed_webhooks,
        "pending_retries": pending_retries,
        "status": "critical" if failed_webhooks > 10 else "degraded" if failed_webhooks > 0 else "healthy",
    }


def check_publisher_quality():
    """Publisher quality metrics check করে।"""
    from api.publisher_tools.models import Publisher, SiteQualityMetric
    today = timezone.now().date()
    quality_alerts = SiteQualityMetric.objects.filter(date=today, has_alerts=True).count()
    malware_sites  = SiteQualityMetric.objects.filter(date=today, malware_detected=True).count()
    print(f"  Quality: {quality_alerts} sites with alerts, {malware_sites} malware detected")
    return {
        "quality_alerts_today": quality_alerts,
        "malware_detected":     malware_sites,
        "status": "critical" if malware_sites > 0 else "degraded" if quality_alerts > 5 else "healthy",
    }


def run():
    print(f"🏥 Health Check — {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    results = {
        "timestamp":    timezone.now().isoformat(),
        "database":     check_database_health(),
        "cache":        check_cache_health(),
        "pending_tasks":check_pending_tasks(),
        "webhooks":     check_webhook_health(),
        "quality":      check_publisher_quality(),
    }
    # Overall status
    statuses = [v.get("status", "unknown") for v in results.values() if isinstance(v, dict)]
    overall = "critical" if "critical" in statuses or "error" in statuses else "degraded" if "degraded" in statuses else "healthy"
    results["overall_status"] = overall
    print(f"{'✅' if overall == 'healthy' else '⚠️' if overall == 'degraded' else '🔴'} Overall: {overall.upper()}")
    return results

if __name__ == "__main__":
    run()
