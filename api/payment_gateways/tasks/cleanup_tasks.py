# tasks/cleanup_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def cleanup_old_webhook_logs():
    """Delete webhook logs older than 90 days."""
    from api.payment_gateways.models.core import PaymentGatewayWebhookLog
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=90)
    deleted, _ = PaymentGatewayWebhookLog.objects.filter(
        created_at__lte=cutoff, processed=True
    ).delete()
    logger.info(f'Cleaned {deleted} old webhook logs')
    return {'deleted': deleted}

@shared_task
def cleanup_health_logs():
    """Delete gateway health logs older than 30 days."""
    from api.payment_gateways.models.gateway_config import GatewayHealthLog
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = GatewayHealthLog.objects.filter(checked_at__lte=cutoff).delete()
    logger.info(f'Cleaned {deleted} gateway health logs')
    return {'deleted': deleted}

@shared_task
def cleanup_expired_deposits():
    """Permanently remove expired deposit requests older than 30 days."""
    from api.payment_gateways.models.deposit import DepositRequest
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = DepositRequest.objects.filter(
        status__in=['expired', 'cancelled'],
        created_at__lte=cutoff
    ).delete()
    logger.info(f'Cleaned {deleted} expired deposits')
    return {'deleted': deleted}

@shared_task
def cleanup_old_callbacks():
    """Remove processed callbacks older than 60 days."""
    from api.payment_gateways.models.deposit import DepositCallback
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=60)
    deleted, _ = DepositCallback.objects.filter(
        processed=True, created_at__lte=cutoff
    ).delete()
    logger.info(f'Cleaned {deleted} old deposit callbacks')
    return {'deleted': deleted}
