# tasks/deposit_verification_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def verify_pending_deposits():
    """Verify stuck pending deposits via API polling."""
    from api.payment_gateways.models.deposit import DepositRequest
    from django.utils import timezone
    from datetime import timedelta

    stuck = DepositRequest.objects.filter(
        status='pending',
        initiated_at__gte=timezone.now() - timedelta(hours=24),
        initiated_at__lte=timezone.now() - timedelta(minutes=15),
    )
    verified = 0
    for deposit in stuck:
        try:
            from api.payment_gateways.services.PaymentFactory import PaymentFactory
            processor = PaymentFactory.get_processor(deposit.gateway)
            result    = processor.verify_payment(
                deposit.session_key or deposit.gateway_ref,
                reference_id=deposit.reference_id
            )
            if result and getattr(result, 'status', '') == 'completed':
                deposit.status = 'completed'
                deposit.completed_at = timezone.now()
                deposit.save()
                verified += 1
        except Exception as e:
            logger.warning(f'Could not verify deposit {deposit.reference_id}: {e}')
    logger.info(f'Verified {verified}/{stuck.count()} pending deposits')
    return {'verified': verified}

@shared_task
def expire_old_deposits():
    """Mark deposits expired after 1 hour of pending."""
    from api.payment_gateways.models.deposit import DepositRequest
    from django.utils import timezone
    from datetime import timedelta

    old = DepositRequest.objects.filter(
        status__in=['initiated', 'pending'],
        initiated_at__lte=timezone.now() - timedelta(hours=1),
    )
    count = old.update(status='expired')
    logger.info(f'Expired {count} old deposits')
    return {'expired': count}
