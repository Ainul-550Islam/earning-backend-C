# api/djoyalty/tasks/redemption_tasks.py
"""
Celery task: Redemption auto-processing।
Schedule: Every 15 minutes।
"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func:
            return func
        def decorator(f):
            return f
        return decorator

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.auto_approve_redemptions', bind=True, max_retries=3)
def auto_approve_redemptions_task(self):
    """
    Threshold এর নিচের pending redemptions auto-approve করো।
    Returns: count of auto-approved redemptions
    """
    try:
        from ..services.redemption.RedemptionApprovalService import RedemptionApprovalService

        count = RedemptionApprovalService.auto_approve_pending()
        logger.info('[djoyalty] Auto-approved redemptions: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] auto_approve_redemptions error: %s', exc)
        raise self.retry(exc=exc, countdown=60) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.expire_old_pending_redemptions', bind=True, max_retries=3)
def expire_old_pending_redemptions_task(self):
    """
    ৩০ দিনের বেশি পুরনো pending redemptions cancel করো।
    Returns: count of cancelled redemptions
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        from ..models.redemption import RedemptionRequest, RedemptionHistory

        cutoff = timezone.now() - timedelta(days=30)
        old_pending = RedemptionRequest.objects.filter(
            status='pending',
            created_at__lt=cutoff,
        )
        count = 0
        for req in old_pending:
            try:
                old_status = req.status
                req.status = 'cancelled'
                req.note = 'Auto-cancelled: pending for more than 30 days'
                req.save(update_fields=['status', 'note'])

                # Refund points
                lp = req.customer.loyalty_points.first()
                if lp:
                    lp.credit(req.points_used)
                    lp.lifetime_redeemed -= req.points_used
                    lp.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])

                RedemptionHistory.objects.create(
                    request=req,
                    from_status=old_status,
                    to_status='cancelled',
                    changed_by='system',
                    note='Auto-cancelled after 30 days pending',
                )
                count += 1
            except Exception as e:
                logger.error('[djoyalty] Error cancelling redemption %d: %s', req.id, e)

        logger.info('[djoyalty] Expired old pending redemptions: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] expire_old_pending_redemptions error: %s', exc)
        raise self.retry(exc=exc, countdown=60) if hasattr(self, 'retry') else exc
