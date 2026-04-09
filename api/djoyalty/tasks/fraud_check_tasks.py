# api/djoyalty/tasks/fraud_check_tasks.py
"""
Celery task: Hourly fraud scan।
Scans for suspicious patterns and logs high-risk cases।
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


@shared_task(name='djoyalty.fraud_scan', bind=True, max_retries=3)
def fraud_scan_task(self):
    """
    Hourly fraud scan:
    1. High-risk unresolved logs count করো
    2. Rapid transaction customers flag করো
    Returns: count of unresolved high-risk logs
    """
    try:
        from ..models.advanced import PointsAbuseLog

        unresolved = PointsAbuseLog.objects.filter(
            is_resolved=False,
            risk_level__in=['high', 'critical'],
        ).count()

        if unresolved > 0:
            logger.warning('[djoyalty] %d unresolved high-risk fraud logs pending review!', unresolved)
        else:
            logger.info('[djoyalty] Fraud scan: no high-risk unresolved logs.')

        return unresolved

    except Exception as exc:
        logger.error('[djoyalty] fraud_scan error: %s', exc)
        raise self.retry(exc=exc, countdown=60) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.scan_rapid_transactions', bind=True, max_retries=3)
def scan_rapid_transactions_task(self):
    """
    Recent period এ অস্বাভাবিক transaction pattern আছে এমন customers খুঁজে flag করো।
    Returns: count of flagged customers
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        from ..models.core import Customer, Txn
        from ..services.advanced.LoyaltyFraudService import LoyaltyFraudService
        from ..constants import FRAUD_RAPID_TXN_WINDOW_MINUTES

        window_start = timezone.now() - timedelta(minutes=FRAUD_RAPID_TXN_WINDOW_MINUTES)
        flagged = 0

        # Get customers with txns in window
        active_customers = Customer.objects.filter(
            transactions__timestamp__gte=window_start,
            is_active=True,
        ).distinct()

        for customer in active_customers:
            if LoyaltyFraudService.check_rapid_transactions(customer):
                flagged += 1

        logger.info('[djoyalty] Rapid transaction scan: %d customers flagged', flagged)
        return flagged

    except Exception as exc:
        logger.error('[djoyalty] scan_rapid_transactions error: %s', exc)
        raise self.retry(exc=exc, countdown=120) if hasattr(self, 'retry') else exc
