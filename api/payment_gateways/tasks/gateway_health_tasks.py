# tasks/gateway_health_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=1)
def check_all_gateways(self):
    """Every 5 min: ping all gateways and update health status."""
    from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
    results = GatewayHealthService().check_all()
    down    = [g for g, r in results.items() if r.get('status') in ('down','error')]
    if down:
        check_gateway_alerts.delay(down)
    logger.info(f'Health check: {len(results)} gateways checked, {len(down)} down')
    return results

@shared_task
def check_gateway_alerts(down_gateways: list):
    """Alert admin when gateways go down."""
    from django.core.mail import send_mail
    from django.conf import settings
    if not down_gateways:
        return
    subject = f'[ALERT] {len(down_gateways)} payment gateway(s) DOWN'
    body    = f'Down gateways: {", ".join(down_gateways)}\n\nCheck immediately.'
    admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [admin_email])
    except Exception as e:
        logger.error(f'Alert email failed: {e}')
