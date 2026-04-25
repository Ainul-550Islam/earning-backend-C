# tasks/reconciliation_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import date, timedelta
logger = get_task_logger(__name__)

@shared_task
def nightly_reconciliation():
    """Nightly: reconcile all gateways for yesterday."""
    from api.payment_gateways.models.core import PaymentGateway
    from api.payment_gateways.services.ReconciliationService import ReconciliationService
    yesterday = date.today() - timedelta(days=1)
    svc       = ReconciliationService()
    results   = {}
    for gw in PaymentGateway.objects.filter(status='active'):
        try:
            results[gw.name] = svc.reconcile(gw.name, yesterday)
        except Exception as e:
            results[gw.name] = {'error': str(e)}
            logger.error(f'Reconciliation failed for {gw.name}: {e}')
    logger.info(f'Nightly reconciliation done: {results}')
    return results

@shared_task
def reconcile_gateway(gateway_name: str, date_str: str):
    """Manual reconciliation trigger for specific gateway and date."""
    from api.payment_gateways.services.ReconciliationService import ReconciliationService
    from datetime import datetime
    target = datetime.strptime(date_str, '%Y-%m-%d').date()
    return ReconciliationService().reconcile(gateway_name, target)
