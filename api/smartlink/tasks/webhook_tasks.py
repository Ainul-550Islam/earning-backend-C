"""
SmartLink Webhook Tasks
Celery tasks for async webhook delivery and retry processing.
"""
import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.webhook')


@shared_task(name='smartlink.deliver_webhook_event', queue='webhooks',
             max_retries=0, bind=True)
def deliver_webhook_event(self, event: str, publisher_id: int,
                          smartlink_id: int = None, **payload_data):
    """
    Async delivery of a webhook event to all subscribed endpoints.
    Called by signal handlers after conversion/fraud/cap events.
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        publisher = User.objects.get(pk=publisher_id)
        from ..services.webhook.WebhookService import WebhookService
        sent = WebhookService().dispatch(
            event=event,
            publisher=publisher,
            smartlink_id=smartlink_id,
            **payload_data,
        )
        logger.info(f"Webhook event '{event}' dispatched to {sent} endpoints for publisher#{publisher_id}")
        return {'sent': sent}
    except Exception as e:
        logger.error(f"deliver_webhook_event failed: {e}", exc_info=True)
        return {'sent': 0, 'error': str(e)}


@shared_task(name='smartlink.retry_webhook_deliveries', queue='webhooks')
def retry_webhook_deliveries():
    """
    Beat task: retry all RETRYING deliveries whose next_retry_at has passed.
    Schedule: every 2 minutes in CELERY_BEAT_SCHEDULE.
    """
    try:
        from ..services.webhook.WebhookService import WebhookService
        retried = WebhookService().retry_pending()
        logger.info(f"Webhook retry task: retried {retried} deliveries")
        return {'retried': retried}
    except Exception as e:
        logger.error(f"retry_webhook_deliveries failed: {e}")
        return {'retried': 0, 'error': str(e)}


@shared_task(name='smartlink.purge_old_webhook_logs', queue='default')
def purge_old_webhook_logs(days: int = 30):
    """
    Cleanup task: delete delivery logs older than `days` days.
    Schedule: daily in CELERY_BEAT_SCHEDULE.
    """
    from django.utils import timezone
    import datetime
    from api.smartlink.models.webhook import WebhookDeliveryLog
    cutoff = timezone.now() - datetime.timedelta(days=days)
    deleted, _ = WebhookDeliveryLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Purged {deleted} webhook delivery logs older than {days} days")
    return {'deleted': deleted}
