"""receivers.py – Signal handlers for the postback module."""
import logging

logger = logging.getLogger(__name__)


def on_postback_received(sender, instance, **kwargs):
    logger.info(
        "Postback received: id=%s network=%s ip=%s",
        instance.pk, instance.network.network_key, instance.source_ip,
    )


def on_postback_rejected(sender, instance, reason=None, **kwargs):
    logger.warning(
        "Postback rejected: id=%s network=%s reason=%s",
        instance.pk, instance.network.network_key, reason,
    )


def on_postback_rewarded(sender, instance, points=0, **kwargs):
    logger.info(
        "Postback rewarded: id=%s user=%s points=%d",
        instance.pk,
        instance.resolved_user.pk if instance.resolved_user else "N/A",
        points,
    )


def on_postback_duplicate(sender, instance, **kwargs):
    logger.info(
        "Postback duplicate: id=%s lead_id=%s network=%s",
        instance.pk, instance.lead_id, instance.network.network_key,
    )


def on_postback_failed(sender, instance, error="", **kwargs):
    logger.error(
        "Postback failed: id=%s network=%s error=%s (retries=%d)",
        instance.pk, instance.network.network_key, error, instance.retry_count,
    )
