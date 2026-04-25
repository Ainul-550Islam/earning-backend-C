# tasks/webhook_retry_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def retry_failed_webhook(self, log_id: int):
    """Retry a specific failed webhook delivery."""
    from api.payment_gateways.models.core import PaymentGatewayWebhookLog
    try:
        log = PaymentGatewayWebhookLog.objects.get(id=log_id, processed=False)
        from api.payment_gateways.notifications.WebhookNotifier import WebhookNotifier
        notifier = WebhookNotifier()
        notifier.fire(log.payload, log.gateway)
        log.processed = True
        log.save(update_fields=['processed'])
        return {'retried': True, 'log_id': log_id}
    except Exception as e:
        self.retry(exc=e)

@shared_task
def retry_all_failed_webhooks():
    """Batch retry all unprocessed webhooks older than 5 minutes."""
    from api.payment_gateways.models.core import PaymentGatewayWebhookLog
    from django.utils import timezone
    from datetime import timedelta
    stale = PaymentGatewayWebhookLog.objects.filter(
        processed=False, is_valid=True,
        created_at__lte=timezone.now() - timedelta(minutes=5),
        created_at__gte=timezone.now() - timedelta(hours=24),
    )
    queued = 0
    for log in stale[:100]:
        retry_failed_webhook.delay(log.id)
        queued += 1
    logger.info(f'Queued {queued} webhook retries')
    return {'queued': queued}
