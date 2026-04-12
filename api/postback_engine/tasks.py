"""
tasks.py – Celery tasks for Postback Engine.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .constants import (
    MAX_POSTBACK_RETRIES,
    POSTBACK_RETRY_DELAYS,
    POSTBACK_LOG_RETENTION_DAYS,
    CLICK_LOG_RETENTION_DAYS,
    IMPRESSION_RETENTION_DAYS,
)
from .exceptions import PostbackProcessingException

logger = logging.getLogger(__name__)


# ── Core Processing Tasks ─────────────────────────────────────────────────────

@shared_task(
    name="postback_engine.tasks.process_postback",
    bind=True,
    max_retries=MAX_POSTBACK_RETRIES,
    default_retry_delay=30,
    acks_late=True,
)
def process_postback_task(
    self,
    raw_log_id: str,
    *,
    signature: str = "",
    timestamp_str: str = "",
    nonce: str = "",
):
    """
    Async postback processing task.
    Fetches the raw log and runs the full validation pipeline.
    """
    from .models import PostbackRawLog
    from .services import process_postback

    try:
        raw_log = PostbackRawLog.objects.select_related("network").get(pk=raw_log_id)
    except PostbackRawLog.DoesNotExist:
        logger.error("process_postback_task: raw_log_id=%s not found", raw_log_id)
        return {"status": "error", "detail": "Raw log not found"}

    try:
        conversion = process_postback(
            raw_log,
            signature=signature,
            timestamp_str=timestamp_str,
            nonce=nonce,
        )
        return {
            "status": "rewarded" if conversion else "rejected",
            "raw_log_id": raw_log_id,
            "conversion_id": str(conversion.id) if conversion else None,
        }

    except PostbackProcessingException as exc:
        # Exponential backoff retry
        retry_index = min(self.request.retries, len(POSTBACK_RETRY_DELAYS) - 1)
        countdown = POSTBACK_RETRY_DELAYS[retry_index]
        logger.warning(
            "process_postback_task retry #%d for raw_log=%s: %s",
            self.request.retries + 1, raw_log_id, exc,
        )
        raise self.retry(exc=exc, countdown=countdown)

    except Exception as exc:
        logger.exception("process_postback_task fatal error for raw_log=%s", raw_log_id)
        return {"status": "error", "detail": str(exc)}


@shared_task(name="postback_engine.tasks.process_click")
def process_click_task(click_log_id: str):
    """Async click post-processing (device fingerprinting, geo-lookup, fraud check)."""
    from .models import ClickLog
    from .fraud_detection.fraud_detector import scan_click

    try:
        click_log = ClickLog.objects.get(pk=click_log_id)
        scan_click(click_log)
    except ClickLog.DoesNotExist:
        logger.warning("process_click_task: click_log_id=%s not found", click_log_id)
    except Exception as exc:
        logger.exception("process_click_task error for click=%s", click_log_id)


@shared_task(name="postback_engine.tasks.process_conversion")
def process_conversion_task(conversion_id: str):
    """Post-conversion processing: notify downstream webhooks, update analytics."""
    from .models import Conversion
    from .webhook_manager.webhook_dispatcher import dispatch_conversion_webhooks

    try:
        conversion = Conversion.objects.select_related(
            "user", "network", "raw_log"
        ).get(pk=conversion_id)
        dispatch_conversion_webhooks(conversion)
    except Conversion.DoesNotExist:
        logger.warning("process_conversion_task: conversion_id=%s not found", conversion_id)
    except Exception as exc:
        logger.exception("process_conversion_task error for conversion=%s", conversion_id)


# ── Retry Tasks ───────────────────────────────────────────────────────────────

@shared_task(name="postback_engine.tasks.retry_failed_postbacks")
def retry_failed_postbacks():
    """
    Celery beat task: pick up failed postbacks and re-queue them.
    Runs every 5 minutes.
    """
    from .models import PostbackRawLog
    from .enums import PostbackStatus

    due = PostbackRawLog.objects.due_for_retry().select_related("network")
    count = 0
    for raw_log in due:
        if raw_log.retry_count >= MAX_POSTBACK_RETRIES:
            raw_log.status = PostbackStatus.FAILED  # leave as failed (max retries)
            raw_log.save(update_fields=["status"])
            continue
        process_postback_task.apply_async(args=[str(raw_log.id)], countdown=0)
        count += 1

    logger.info("retry_failed_postbacks: queued %d retries", count)
    return {"queued": count}


@shared_task(name="postback_engine.tasks.flush_click_buffer")
def flush_click_buffer():
    """
    Celery beat task: expire old unconverted clicks.
    Runs every 30 minutes.
    """
    from .models import ClickLog
    from .enums import ClickStatus

    expired = ClickLog.objects.expired().update(status=ClickStatus.EXPIRED)
    logger.info("flush_click_buffer: expired %d clicks", expired)
    return {"expired": expired}


# ── Analytics Tasks ───────────────────────────────────────────────────────────

@shared_task(name="postback_engine.tasks.update_hourly_stats")
def update_hourly_stats():
    """
    Celery beat task: compute aggregated hourly stats.
    Runs every 5 minutes.
    """
    from .models import AdNetworkConfig, HourlyStat, PostbackRawLog, ClickLog, Conversion
    from .enums import ConversionStatus, PostbackStatus

    now = timezone.now()
    date = now.date()
    hour = now.hour

    for network in AdNetworkConfig.objects.active():
        # Build time window for this hour
        hour_start = timezone.datetime(
            year=date.year, month=date.month, day=date.day, hour=hour,
            tzinfo=timezone.utc,
        )
        hour_end = hour_start + timedelta(hours=1)

        clicks = ClickLog.objects.filter(
            network=network,
            clicked_at__gte=hour_start,
            clicked_at__lt=hour_end,
        ).count()

        conversions = Conversion.objects.filter(
            network=network,
            converted_at__gte=hour_start,
            converted_at__lt=hour_end,
        )
        conv_count = conversions.count()
        payout_agg = conversions.aggregate(
            total=models.Sum("actual_payout"),
            total_points=models.Sum("points_awarded"),
        )

        rejected = PostbackRawLog.objects.filter(
            network=network,
            received_at__gte=hour_start,
            received_at__lt=hour_end,
            status=PostbackStatus.REJECTED,
        ).count()

        HourlyStat.objects.update_or_create(
            network=network,
            date=date,
            hour=hour,
            defaults={
                "tenant": network.tenant,
                "clicks": clicks,
                "conversions": conv_count,
                "rejected": rejected,
                "payout_usd": payout_agg["total"] or 0,
                "points_awarded": payout_agg["total_points"] or 0,
                "conversion_rate": (conv_count / clicks * 100) if clicks > 0 else 0,
            },
        )

    logger.info("update_hourly_stats: done for %s %02d:00", date, hour)


@shared_task(name="postback_engine.tasks.update_daily_stats")
def update_daily_stats(date_str: str = None):
    """
    Celery beat task: compute aggregated daily NetworkPerformance records.
    Runs once per day at 00:05 UTC.
    """
    from .models import AdNetworkConfig, NetworkPerformance, Conversion, ClickLog, PostbackRawLog
    from .enums import ConversionStatus, PostbackStatus

    target_date = (
        timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
        if date_str
        else (timezone.now() - timedelta(days=1)).date()
    )

    day_start = timezone.datetime.combine(target_date, timezone.datetime.min.time())
    day_start = timezone.make_aware(day_start)
    day_end = day_start + timedelta(days=1)

    for network in AdNetworkConfig.objects.all():
        clicks_qs = ClickLog.objects.filter(
            network=network, clicked_at__gte=day_start, clicked_at__lt=day_end,
        )
        conv_qs = Conversion.objects.filter(
            network=network, converted_at__gte=day_start, converted_at__lt=day_end,
        )

        total_clicks = clicks_qs.count()
        approved = conv_qs.filter(status=ConversionStatus.APPROVED).count()
        rejected_conv = conv_qs.filter(status=ConversionStatus.REJECTED).count()
        payout_agg = conv_qs.aggregate(
            total=models.Sum("actual_payout"),
            total_points=models.Sum("points_awarded"),
        )

        NetworkPerformance.objects.update_or_create(
            network=network,
            date=target_date,
            defaults={
                "tenant": network.tenant,
                "total_clicks": total_clicks,
                "total_conversions": conv_qs.count(),
                "approved_conversions": approved,
                "rejected_conversions": rejected_conv,
                "total_payout_usd": payout_agg["total"] or 0,
                "total_points_awarded": payout_agg["total_points"] or 0,
                "conversion_rate": (approved / total_clicks * 100) if total_clicks > 0 else 0,
                "computed_at": timezone.now(),
            },
        )

    logger.info("update_daily_stats: done for %s", target_date)


# ── Cleanup Tasks ─────────────────────────────────────────────────────────────

@shared_task(name="postback_engine.tasks.cleanup_old_logs")
def cleanup_old_logs():
    """
    Celery beat task: purge old logs past retention window.
    Runs daily at 03:00 UTC.
    """
    from .models import PostbackRawLog, ClickLog, Impression
    from .enums import PostbackStatus

    now = timezone.now()

    # Postback raw logs
    cutoff_postback = now - timedelta(days=POSTBACK_LOG_RETENTION_DAYS)
    deleted_postback, _ = PostbackRawLog.objects.filter(
        received_at__lt=cutoff_postback,
        status__in=[PostbackStatus.REWARDED, PostbackStatus.REJECTED, PostbackStatus.DUPLICATE],
    ).delete()

    # Click logs
    cutoff_click = now - timedelta(days=CLICK_LOG_RETENTION_DAYS)
    deleted_clicks, _ = ClickLog.objects.filter(
        clicked_at__lt=cutoff_click,
    ).delete()

    # Impressions
    cutoff_impression = now - timedelta(days=IMPRESSION_RETENTION_DAYS)
    deleted_impressions, _ = Impression.objects.filter(
        impressed_at__lt=cutoff_impression,
    ).delete()

    result = {
        "deleted_postback_logs": deleted_postback,
        "deleted_click_logs": deleted_clicks,
        "deleted_impressions": deleted_impressions,
    }
    logger.info("cleanup_old_logs: %s", result)
    return result


@shared_task(name="postback_engine.tasks.run_fraud_scan")
def run_fraud_scan():
    """
    Celery beat task: run scheduled fraud detection scan.
    Runs every 15 minutes.
    """
    from .fraud_detection.fraud_detector import run_scheduled_scan
    results = run_scheduled_scan()
    logger.info("run_fraud_scan: %s", results)
    return results


@shared_task(name="postback_engine.tasks.send_webhook_notification")
def send_webhook_notification(conversion_id: str):
    """Send outbound webhook notification for a conversion."""
    from .models import Conversion
    from .webhook_manager.webhook_dispatcher import dispatch_conversion_webhooks
    try:
        conversion = Conversion.objects.get(pk=conversion_id)
        dispatch_conversion_webhooks(conversion)
    except Exception as exc:
        logger.exception("send_webhook_notification error: %s", exc)


# needed for aggregate
from django.db import models


@shared_task(
    name="postback_engine.tasks.retry_wallet_credit",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def retry_wallet_credit_task(self, conversion_id: str, attempt_number: int = 2):
    """
    Celery task: retry a failed wallet credit with exponential backoff.
    Managed by RetryHandler — do not call directly.
    """
    from .postback_handlers.retry_handler import retry_handler
    from .models import Conversion
    from .services import _dispatch_reward

    try:
        conversion = Conversion.objects.select_related("user", "network").get(pk=conversion_id)
    except Conversion.DoesNotExist:
        logger.error("retry_wallet_credit: conversion %s not found", conversion_id)
        return

    if conversion.wallet_credited:
        retry_handler.mark_wallet_retry_success(conversion_id)
        return

    try:
        _dispatch_reward(conversion=conversion, network=conversion.network)
        retry_handler.mark_wallet_retry_success(conversion_id)
        logger.info("retry_wallet_credit: SUCCESS conversion=%s attempt=%d", conversion_id, attempt_number)
    except Exception as exc:
        retry_handler.schedule_wallet_retry(
            conversion=conversion,
            error=str(exc),
            attempt_number=attempt_number,
            exc=exc,
        )
