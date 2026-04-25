# tasks/withdrawal_processing_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def process_approved_payouts():
    """Process all admin-approved payout requests."""
    from api.payment_gateways.models.core import PayoutRequest
    from api.payment_gateways.services.DepositService import WithdrawalGatewayService

    approved = PayoutRequest.objects.filter(status='approved')
    svc = WithdrawalGatewayService()
    processed = 0
    for payout in approved:
        try:
            svc.execute(payout)
            processed += 1
        except Exception as e:
            logger.error(f'Payout {payout.id} failed: {e}')
    logger.info(f'Processed {processed} payouts')
    return {'processed': processed}

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def retry_failed_payout(self, payout_id: int):
    """Retry a specific failed payout."""
    from api.payment_gateways.models.core import PayoutRequest
    from api.payment_gateways.services.DepositService import WithdrawalGatewayService
    try:
        payout = PayoutRequest.objects.get(id=payout_id)
        WithdrawalGatewayService().execute(payout)
        return {'retried': True}
    except Exception as e:
        self.retry(exc=e)
