# api/djoyalty/pending_points.py
"""
Djoyalty Pending Points -- Voucherify 2025 feature।
Points held in "pending" state during return period before confirming।
Prevents points fraud when customers buy -> earn points -> return items।

World reference: Voucherify changelog 2025 "pending points" feature।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class PendingPointsBucket(models.Model):
    """
    Points held pending for a specific transaction।
    Activated after return_period days, cancelled if item returned।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='pending_points_buckets',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='pending_points_buckets',
    )
    txn = models.ForeignKey(
        'djoyalty.Txn', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='pending_points_buckets',
    )

    points = models.DecimalField(max_digits=14, decimal_places=2)
    source = models.CharField(max_length=50, default='purchase')
    reference_id = models.CharField(max_length=200, null=True, blank=True)
    description = models.CharField(max_length=300, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending',   'Pending -- awaiting return period'),
            ('activated', 'Activated -- added to balance'),
            ('cancelled', 'Cancelled -- item returned'),
            ('expired',   'Expired -- auto-cancelled'),
        ],
        default='pending',
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    activates_at = models.DateTimeField(verbose_name='When points become available')
    activated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, null=True, blank=True)

    # Adjustment tracking
    adjusted_by = models.CharField(max_length=200, null=True, blank=True)
    adjustment_note = models.CharField(max_length=300, null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Pending Points Bucket'
        verbose_name_plural = 'Pending Points Buckets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'activates_at']),
        ]

    def __str__(self):
        return f'Pending({self.customer.code}: {self.points} pts [{self.status}] activates {self.activates_at.date()})'


class PendingPointsManager:
    """
    Manages the pending points lifecycle।
    Create -> Hold -> Activate (after return period) or Cancel (if returned)।

    Usage:
        # When order is placed (points held)
        bucket = PendingPointsManager.hold(customer, points=100,
                                           txn=order_txn, return_days=14)

        # When return period passes (auto via task)
        PendingPointsManager.activate_due()

        # When customer returns item
        PendingPointsManager.cancel(bucket, reason='Item returned by customer')

        # Manual adjustment
        PendingPointsManager.adjust(bucket, new_points=80, reason='Partial return')
    """

    DEFAULT_RETURN_DAYS = 14  # Standard return period

    @staticmethod
    @transaction.atomic
    def hold(customer, points: Decimal, txn=None,
              reference_id: str = '', description: str = '',
              return_days: int = None, tenant=None) -> PendingPointsBucket:
        """Create a pending points bucket -- points held until return period ends।"""
        days = return_days if return_days is not None else PendingPointsManager.DEFAULT_RETURN_DAYS
        activates_at = timezone.now() + timedelta(days=days)

        bucket = PendingPointsBucket.objects.create(
            customer=customer,
            tenant=tenant or customer.tenant,
            txn=txn,
            points=points,
            source='purchase',
            reference_id=reference_id,
            description=description or f'Pending {points} pts ({days}d hold)',
            status='pending',
            activates_at=activates_at,
        )

        # Notify customer about pending points
        try:
            from .services.NotificationService import NotificationService
            NotificationService.send(
                customer, 'points_earned',
                title=f'⏳ {points} পয়েন্ট Pending!',
                body=f'{days} দিন পর আপনার {points} পয়েন্ট যোগ হবে।',
                icon='⏳',
                metadata={'points': str(points), 'days': days, 'activates_at': activates_at.isoformat()},
            )
        except Exception:
            pass

        logger.info('PendingPointsManager.hold: %s pts held for %s (activates %s)',
                    points, customer.code, activates_at.date())
        return bucket

    @staticmethod
    @transaction.atomic
    def activate(bucket: PendingPointsBucket) -> bool:
        """Activate a pending bucket -- move points to customer balance।"""
        if bucket.status != 'pending':
            return False

        try:
            from .repositories import PointsRepository
            PointsRepository.credit(
                customer=bucket.customer,
                points=bucket.points,
                source=bucket.source,
                reference_id=bucket.reference_id or f'PENDING-{bucket.id}',
                description=bucket.description or f'Activated pending points',
            )
            bucket.status = 'activated'
            bucket.activated_at = timezone.now()
            bucket.save(update_fields=['status', 'activated_at'])

            logger.info('PendingPointsManager.activate: %s pts activated for %s',
                        bucket.points, bucket.customer.code)
            return True
        except Exception as e:
            logger.error('PendingPointsManager.activate error: %s', e)
            return False

    @staticmethod
    def activate_due() -> int:
        """Activate all pending buckets past their activates_at date। Run daily।"""
        now = timezone.now()
        due = PendingPointsBucket.objects.filter(
            status='pending',
            activates_at__lte=now,
        )
        activated = 0
        for bucket in due:
            if PendingPointsManager.activate(bucket):
                activated += 1
        logger.info('PendingPointsManager.activate_due: activated %d buckets', activated)
        return activated

    @staticmethod
    @transaction.atomic
    def cancel(bucket: PendingPointsBucket, reason: str = '',
                cancelled_by: str = 'system') -> bool:
        """Cancel pending points (item returned)।"""
        if bucket.status != 'pending':
            return False

        bucket.status = 'cancelled'
        bucket.cancelled_at = timezone.now()
        bucket.cancel_reason = reason[:200]
        bucket.adjusted_by = cancelled_by
        bucket.save(update_fields=['status', 'cancelled_at', 'cancel_reason', 'adjusted_by'])

        # Notify
        try:
            from .services.NotificationService import NotificationService
            NotificationService.send(
                bucket.customer, 'system',
                title='⚠️ Pending Points Cancelled',
                body=f'{bucket.points} পয়েন্ট বাতিল হয়েছে। কারণ: {reason or "Return/cancellation"}',
            )
        except Exception:
            pass

        logger.info('PendingPointsManager.cancel: %s pts cancelled for %s -- %s',
                    bucket.points, bucket.customer.code, reason)
        return True

    @staticmethod
    @transaction.atomic
    def adjust(bucket: PendingPointsBucket, new_points: Decimal,
                reason: str = '', adjusted_by: str = 'system') -> bool:
        """Adjust pending points amount (partial return)।"""
        if bucket.status != 'pending':
            return False

        old_points = bucket.points
        bucket.points = new_points
        bucket.adjustment_note = f'{reason} (adjusted from {old_points} to {new_points})'
        bucket.adjusted_by = adjusted_by
        bucket.save(update_fields=['points', 'adjustment_note', 'adjusted_by'])

        logger.info('PendingPointsManager.adjust: %s pts -> %s for %s -- %s',
                    old_points, new_points, bucket.customer.code, reason)
        return True

    @staticmethod
    def get_pending_total(customer) -> Decimal:
        """Get total pending points for customer।"""
        result = PendingPointsBucket.objects.filter(
            customer=customer, status='pending'
        ).aggregate(total=models.Sum('points'))
        return result['total'] or Decimal('0')

    @staticmethod
    def get_customer_pending_buckets(customer) -> list:
        """Get all pending buckets for a customer।"""
        return list(
            PendingPointsBucket.objects.filter(customer=customer)
            .order_by('-created_at')[:20]
        )
