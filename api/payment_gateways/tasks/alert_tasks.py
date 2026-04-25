# tasks/alert_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def check_failure_rate_alerts():
    """Alert if gateway failure rate exceeds threshold."""
    from api.payment_gateways.models.reconciliation import PaymentAnalytics
    from django.utils import timezone
    THRESHOLD = 0.30  # 30% failure rate

    today    = timezone.now().date()
    high_fail = PaymentAnalytics.objects.filter(date=today, failure_rate__gte=THRESHOLD)
    for a in high_fail:
        logger.warning(f'HIGH FAILURE RATE: {a.gateway.name} = {float(a.failure_rate)*100:.1f}%')
        _send_failure_alert(a.gateway.name, float(a.failure_rate))
    return {'alerts': high_fail.count()}

def _send_failure_alert(gateway: str, rate: float):
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(
            f'[ALERT] {gateway} failure rate {rate*100:.1f}%',
            f'Gateway {gateway} has failure rate {rate*100:.1f}% — investigate immediately.',
            settings.DEFAULT_FROM_EMAIL,
            [getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)],
        )
    except Exception: pass

@shared_task
def credential_expiry_reminder():
    """Remind about expiring API credentials."""
    from api.payment_gateways.models.gateway_config import GatewayCredential
    from django.utils import timezone
    from datetime import timedelta

    expiring = GatewayCredential.objects.filter(
        expires_at__lte=timezone.now() + timedelta(days=30),
        expires_at__gte=timezone.now(),
        is_active=True,
    )
    for cred in expiring:
        days_left = (cred.expires_at - timezone.now()).days
        logger.warning(f'Credential expiring: {cred.gateway.name} in {days_left} days')
    return {'expiring': expiring.count()}

@shared_task
def cleanup_old_logs():
    """Delete old webhook logs and health logs."""
    from api.payment_gateways.models.core import PaymentGatewayWebhookLog
    from api.payment_gateways.models.gateway_config import GatewayHealthLog
    from django.utils import timezone
    from datetime import timedelta

    cutoff  = timezone.now() - timedelta(days=90)
    wh_del  = PaymentGatewayWebhookLog.objects.filter(created_at__lte=cutoff, processed=True).delete()
    hl_del  = GatewayHealthLog.objects.filter(checked_at__lte=cutoff).delete()
    logger.info(f'Cleanup: {wh_del[0]} webhook logs, {hl_del[0]} health logs deleted')
    return {'webhook_logs': wh_del[0], 'health_logs': hl_del[0]}
