# tasks/credential_rotation_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def check_credential_expiry():
    """Check for expiring API credentials and send reminders."""
    from api.payment_gateways.models.gateway_config import GatewayCredential
    from django.utils import timezone
    from datetime import timedelta
    from django.core.mail import send_mail
    from django.conf import settings

    expiry_thresholds = [7, 14, 30]  # Days before expiry to alert
    for days in expiry_thresholds:
        target_date = timezone.now() + timedelta(days=days)
        expiring = GatewayCredential.objects.filter(
            expires_at__date=target_date.date(),
            is_active=True,
        )
        for cred in expiring:
            msg = f'API credential for {cred.gateway.name} expires in {days} days ({cred.expires_at.date()}). Please rotate immediately.'
            logger.warning(msg)
            try:
                send_mail(
                    f'[ACTION REQUIRED] {cred.gateway.name} API key expires in {days} days',
                    msg,
                    settings.DEFAULT_FROM_EMAIL,
                    [getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)],
                )
            except Exception as e:
                logger.error(f'Credential expiry email failed: {e}')
    return {'checked': True}

@shared_task
def verify_all_credentials():
    """Verify all active gateway credentials are working."""
    from api.payment_gateways.models.gateway_config import GatewayCredential
    from api.payment_gateways.services.GatewayHealthService import GatewayHealthService

    health_svc = GatewayHealthService()
    results = {}
    for cred in GatewayCredential.objects.filter(is_active=True):
        result = health_svc.check_single(cred.gateway.name)
        results[cred.gateway.name] = result.get('status')
    return results
