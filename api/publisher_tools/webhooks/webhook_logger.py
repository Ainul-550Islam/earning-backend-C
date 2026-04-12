# api/publisher_tools/webhooks/webhook_logger.py
"""
Webhook Logger — Webhook delivery logging, retry management, analytics।
সব webhook delivery attempt-এর detailed audit trail।
"""
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List, Optional
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def log_delivery_attempt(webhook, event_type: str, payload: Dict, response_code: int = None,
                          response_body: str = "", response_time_ms: int = 0,
                          success: bool = False, error: str = "") -> 'WebhookDeliveryLog':
    """
    Webhook delivery attempt log করে।
    সব attempts — success ও failure দুটোই record হয়।
    """
    from .webhook_manager import WebhookDeliveryLog
    import uuid
    log = WebhookDeliveryLog.objects.create(
        webhook=webhook,
        event_type=event_type,
        payload=payload,
        status="success" if success else "failed",
        http_status_code=response_code,
        response_body=response_body[:2000] if response_body else "",
        response_time_ms=response_time_ms,
        error_message=error[:1000] if error else "",
        delivered_at=timezone.now() if success else None,
        max_attempts=webhook.max_retries,
    )
    return log


def get_webhook_delivery_stats(publisher, days: int = 30) -> Dict:
    """
    Publisher-এর webhook delivery stats।
    Success rate, avg response time, top events।
    """
    from .webhook_manager import WebhookDeliveryLog, PublisherWebhook
    start = timezone.now() - timedelta(days=days)
    webhooks = PublisherWebhook.objects.filter(publisher=publisher)
    logs = WebhookDeliveryLog.objects.filter(webhook__in=webhooks, created_at__gte=start)
    total      = logs.count()
    success    = logs.filter(status="success").count()
    failed     = logs.filter(status="failed").count()
    abandoned  = logs.filter(status="abandoned").count()
    avg_rt_ms  = logs.filter(status="success").aggregate(avg=Avg("response_time_ms")).get("avg") or 0
    # By event type
    by_event = list(
        logs.values("event_type")
        .annotate(count=Count("id"), success=Count("id", filter=Q(status="success")))
        .order_by("-count")[:10]
    )
    # Slowest webhooks
    slow = list(
        logs.filter(response_time_ms__gt=3000)
        .values("event_type", "http_status_code", "response_time_ms")
        .order_by("-response_time_ms")[:5]
    )
    return {
        "publisher_id":    publisher.publisher_id,
        "period_days":     days,
        "total_deliveries":total,
        "successful":      success,
        "failed":          failed,
        "abandoned":       abandoned,
        "success_rate":    round(success / total * 100, 2) if total > 0 else 0,
        "avg_response_ms": round(avg_rt_ms, 2),
        "by_event_type":   by_event,
        "slow_deliveries": slow,
        "active_webhooks": webhooks.filter(status="active").count(),
        "paused_webhooks": webhooks.filter(status__in=["paused", "failed"]).count(),
    }


def get_failed_deliveries(publisher, limit: int = 50) -> List[Dict]:
    """
    Failed webhook deliveries list করে।
    Retry করার জন্য।
    """
    from .webhook_manager import WebhookDeliveryLog, PublisherWebhook
    webhooks = PublisherWebhook.objects.filter(publisher=publisher)
    failed = WebhookDeliveryLog.objects.filter(
        webhook__in=webhooks,
        status__in=["failed", "retrying"],
    ).select_related("webhook").order_by("-created_at")[:limit]
    return [
        {
            "delivery_id":    str(log.delivery_id),
            "event_type":     log.event_type,
            "endpoint_url":   log.webhook.endpoint_url,
            "status":         log.status,
            "attempt_count":  log.attempt_count,
            "max_attempts":   log.max_attempts,
            "http_status":    log.http_status_code,
            "error":          log.error_message[:200] if log.error_message else "",
            "next_retry":     log.next_retry_at.isoformat() if log.next_retry_at else None,
            "created_at":     log.created_at.isoformat(),
        }
        for log in failed
    ]


def retry_failed_deliveries(publisher) -> Dict:
    """
    Failed webhook deliveries retry করে।
    next_retry_at <= now এমনগুলো retry হয়।
    """
    from .webhook_manager import WebhookDeliveryLog, send_webhook_event, PublisherWebhook
    import json
    now = timezone.now()
    webhooks = PublisherWebhook.objects.filter(publisher=publisher, is_active=True)
    due_retries = WebhookDeliveryLog.objects.filter(
        webhook__in=webhooks,
        status="retrying",
        next_retry_at__lte=now,
        attempt_count__lt=3,
    ).select_related("webhook")[:20]
    success_count = 0
    fail_count = 0
    for log in due_retries:
        try:
            import requests
            import time
            webhook = log.webhook
            payload_str = json.dumps(log.payload, default=str)
            headers = webhook.build_request_headers(payload_str, log.event_type)
            start_t = time.time()
            response = requests.post(
                webhook.endpoint_url, data=payload_str, headers=headers,
                timeout=webhook.timeout_seconds,
            )
            elapsed = int((time.time() - start_t) * 1000)
            if 200 <= response.status_code < 300:
                log.status = "success"
                log.delivered_at = now
                log.http_status_code = response.status_code
                log.response_time_ms = elapsed
                log.save()
                webhook.record_delivery(success=True, response_code=response.status_code)
                success_count += 1
            else:
                log.attempt_count += 1
                if log.attempt_count >= log.max_attempts:
                    log.status = "abandoned"
                else:
                    log.schedule_retry(log.attempt_count + 1)
                log.save()
                webhook.record_delivery(success=False, response_code=response.status_code)
                fail_count += 1
        except Exception as e:
            log.attempt_count += 1
            log.error_message = str(e)[:500]
            if log.attempt_count >= log.max_attempts:
                log.status = "abandoned"
            else:
                log.schedule_retry(log.attempt_count + 1)
            log.save()
            fail_count += 1
    return {
        "retried": len(due_retries),
        "success": success_count,
        "failed":  fail_count,
        "retried_at": now.isoformat(),
    }


def cleanup_old_logs(days: int = 30) -> Dict:
    """
    Old webhook delivery logs cleanup করে।
    Successful deliveries 30 days পর delete হয়।
    """
    from .webhook_manager import WebhookDeliveryLog
    cutoff = timezone.now() - timedelta(days=days)
    deleted_success, _ = WebhookDeliveryLog.objects.filter(
        created_at__lt=cutoff,
        status="success",
    ).delete()
    deleted_abandoned, _ = WebhookDeliveryLog.objects.filter(
        created_at__lt=cutoff,
        status="abandoned",
    ).delete()
    total_deleted = deleted_success + deleted_abandoned
    logger.info(f"Webhook log cleanup: {total_deleted} records deleted")
    return {
        "deleted_successful":  deleted_success,
        "deleted_abandoned":   deleted_abandoned,
        "total_deleted":       total_deleted,
        "cutoff_date":         cutoff.isoformat(),
    }


def get_webhook_health_report(publisher) -> Dict:
    """
    Publisher-এর webhook health check।
    Active webhooks ও endpoint reachability।
    """
    from .webhook_manager import PublisherWebhook
    webhooks = list(PublisherWebhook.objects.filter(publisher=publisher))
    report = {
        "publisher_id": publisher.publisher_id,
        "total":        len(webhooks),
        "active":       sum(1 for w in webhooks if w.status == "active"),
        "failed":       sum(1 for w in webhooks if w.status == "failed"),
        "paused":       sum(1 for w in webhooks if w.status == "paused"),
        "webhooks":     [],
    }
    for w in webhooks:
        report["webhooks"].append({
            "id":                str(w.id),
            "name":              w.name,
            "endpoint_url":      w.endpoint_url,
            "status":            w.status,
            "success_rate":      w.success_rate,
            "total_deliveries":  w.total_deliveries,
            "consecutive_failures": w.consecutive_failures,
            "last_success":      w.last_success_at.isoformat() if w.last_success_at else None,
            "last_failure":      w.last_failure_at.isoformat() if w.last_failure_at else None,
            "subscribed_events": w.subscribed_events if not w.subscribe_all else ["ALL"],
        })
    overall_health = (
        "healthy"   if report["active"] > 0 and report["failed"] == 0 else
        "degraded"  if report["failed"] < report["total"] else
        "critical"  if report["failed"] == report["total"] else
        "unconfigured"
    )
    report["overall_health"] = overall_health
    return report


def purge_webhook_logs(publisher, older_than_days: int = 90) -> int:
    """
    Publisher-এর old webhook logs purge করে।
    GDPR compliance বা storage management-এর জন্য।
    """
    from .webhook_manager import WebhookDeliveryLog, PublisherWebhook
    webhooks = PublisherWebhook.objects.filter(publisher=publisher)
    cutoff = timezone.now() - timedelta(days=older_than_days)
    deleted_count, _ = WebhookDeliveryLog.objects.filter(
        webhook__in=webhooks,
        created_at__lt=cutoff,
    ).delete()
    logger.info(f"Purged {deleted_count} webhook logs for publisher {publisher.publisher_id}")
    return deleted_count
