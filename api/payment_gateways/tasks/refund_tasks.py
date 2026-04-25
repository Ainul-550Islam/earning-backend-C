# tasks/refund_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def process_approved_refunds():
    """Process all approved deposit refunds via gateway."""
    from api.payment_gateways.models.deposit import DepositRefund
    from django.utils import timezone

    approved = DepositRefund.objects.filter(status='approved')
    processed = 0
    for refund in approved:
        try:
            from api.payment_gateways.services.PaymentFactory import PaymentFactory
            processor = PaymentFactory.get_processor(refund.deposit.gateway)
            result    = processor.process_withdrawal(
                user=refund.deposit.user,
                amount=refund.refund_amount,
                payment_method=None,
                metadata={'refund_id': refund.id, 'deposit_ref': refund.deposit.reference_id}
            )
            refund.status           = 'completed'
            refund.gateway_refund_id= str(result.get('payout', {}).reference_id if hasattr(result.get('payout',{}), 'reference_id') else '')
            refund.refunded_at      = timezone.now()
            refund.save()
            processed += 1
        except Exception as e:
            refund.status = 'failed'
            refund.save(update_fields=['status'])
            logger.error(f'Refund {refund.id} failed: {e}')
    logger.info(f'Processed {processed} refunds')
    return {'processed': processed}

@shared_task
def check_pending_refunds_timeout():
    """Flag refunds stuck in processing for > 24 hours."""
    from api.payment_gateways.models.deposit import DepositRefund
    from django.utils import timezone
    from datetime import timedelta
    stuck = DepositRefund.objects.filter(
        status='processing',
        created_at__lte=timezone.now() - timedelta(hours=24)
    )
    count = stuck.update(status='requested')  # Reset for retry
    logger.info(f'Reset {count} stuck refunds')
    return {'reset': count}
