# api/djoyalty/services/points/PointsExpiryService.py
import logging
from django.db import transaction
from django.utils import timezone
from ...models.points import PointsExpiry, PointsLedger, LoyaltyPoints
from ...choices import LEDGER_DEBIT, LEDGER_SOURCE_EXPIRY

logger = logging.getLogger(__name__)

class PointsExpiryService:
    @staticmethod
    @transaction.atomic
    def process_expired_points():
        expired = PointsExpiry.objects.filter(expires_at__lte=timezone.now(), is_processed=False)
        count = 0
        for record in expired:
            try:
                lp = record.customer.loyalty_points.first()
                if lp and record.points > 0:
                    actual = min(record.points, lp.balance)
                    if actual > 0:
                        lp.balance -= actual
                        lp.lifetime_expired += actual
                        lp.save(update_fields=['balance', 'lifetime_expired', 'updated_at'])
                        PointsLedger.objects.create(
                            tenant=record.tenant, customer=record.customer,
                            txn_type=LEDGER_DEBIT, source=LEDGER_SOURCE_EXPIRY,
                            points=actual, balance_after=lp.balance,
                            description=f'Points expired on {record.expires_at.date()}',
                        )
                record.is_processed = True
                record.processed_at = timezone.now()
                record.save(update_fields=['is_processed', 'processed_at'])
                count += 1
            except Exception as e:
                logger.error('Expiry error for %s: %s', record, e)
        logger.info('Processed %d expiry records', count)
        return count

    @staticmethod
    def send_expiry_warnings():
        from ...constants import POINTS_EXPIRY_WARNING_DAYS
        from datetime import timedelta
        cutoff = timezone.now() + timedelta(days=POINTS_EXPIRY_WARNING_DAYS)
        records = PointsExpiry.objects.filter(
            expires_at__lte=cutoff, expires_at__gt=timezone.now(),
            is_processed=False, warning_sent=False,
        )
        count = 0
        for record in records:
            try:
                record.warning_sent = True
                record.save(update_fields=['warning_sent'])
                count += 1
            except Exception as e:
                logger.error('Warning send error: %s', e)
        return count
