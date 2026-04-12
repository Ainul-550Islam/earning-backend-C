"""
receivers.py – Signal receivers for Postback Engine.
"""
import logging

from django.dispatch import receiver

from .signals import (
    postback_received, postback_rewarded, postback_rejected,
    postback_duplicate, postback_failed,
    conversion_created, fraud_detected, fraud_auto_blocked,
    click_tracked, reward_dispatched, reward_failed,
)

logger = logging.getLogger(__name__)


@receiver(postback_received)
def on_postback_received(sender, raw_log, **kwargs):
    logger.debug("Signal: postback_received raw_log=%s network=%s",
                 raw_log.id, raw_log.network_id)


@receiver(postback_rewarded)
def on_postback_rewarded(sender, raw_log, conversion, **kwargs):
    """Send async webhook notification on successful conversion."""
    from .tasks import send_webhook_notification
    send_webhook_notification.apply_async(
        args=[str(conversion.id)], countdown=2
    )


@receiver(postback_rejected)
def on_postback_rejected(sender, raw_log, reason, exc, **kwargs):
    logger.info(
        "Signal: postback_rejected raw_log=%s reason=%s",
        raw_log.id, reason,
    )


@receiver(postback_failed)
def on_postback_failed(sender, raw_log, exc, **kwargs):
    logger.error(
        "Signal: postback_failed raw_log=%s error=%s",
        raw_log.id, exc,
    )


@receiver(conversion_created)
def on_conversion_created(sender, conversion, **kwargs):
    """Update analytics counters on conversion creation."""
    logger.info(
        "Signal: conversion_created id=%s user=%s offer=%s payout=%s",
        conversion.id, conversion.user_id,
        conversion.offer_id, conversion.actual_payout,
    )


@receiver(fraud_detected)
def on_fraud_detected(sender, fraud_log, raw_log, **kwargs):
    logger.warning(
        "Signal: fraud_detected type=%s score=%.1f ip=%s",
        fraud_log.fraud_type, fraud_log.fraud_score, fraud_log.source_ip,
    )


@receiver(fraud_auto_blocked)
def on_fraud_auto_blocked(sender, ip, reason, **kwargs):
    logger.warning("Signal: fraud_auto_blocked ip=%s reason=%s", ip, reason)


@receiver(click_tracked)
def on_click_tracked(sender, click_log, **kwargs):
    """Async: run device fingerprinting & geo enrichment."""
    from .tasks import process_click_task
    process_click_task.apply_async(args=[str(click_log.id)], countdown=0)
