# api/djoyalty/models/points.py
"""
Djoyalty Points Models।
LoyaltyPoints, PointsLedger, PointsExpiry, PointsTransfer,
PointsConversion, PointsReservation, PointsRate, PointsAdjustment।

AUDIT FIXES (v1 -- Indexes):
  PointsConversion: was missing indexes entirely -- customer, status not indexed।
  PointsRate:       was missing index on (tenant, effective_date) -- every earn
                    lookup did a full table scan per tenant।
  PointsAdjustment: was missing index on (customer, created_at) -- admin dashboard
                    queries were unindexed on this table।
  All three now have proper Meta.indexes blocks।

AUDIT FIXES (v2 -- Financial Integrity):
  PointsLedger.reference_id:
    Previously only had an Index -- the DB could store two ledger rows with the
    same reference_id if the Redis idempotency key expired between retries।
    Now enforced via a partial UniqueConstraint (non-null values only) so
    PostgreSQL/MySQL reject duplicate non-null reference_ids at the DB level।
    NULL values remain allowed (no-reference earns)।

  on_delete PROTECT for financial audit tables:
    LoyaltyPoints, PointsLedger, PointsTransfer (both sides) changed from
    CASCADE to PROTECT।  Deleting a Customer who has any financial record will
    now raise a ProtectedError, forcing the caller to archive/soft-delete first।
    This prevents silent loss of financial audit trails।
    PointsExpiry / PointsConversion / PointsReservation / PointsAdjustment
    retain CASCADE (operational records, not permanent audit trails)।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..exceptions import InsufficientPointsError

logger = logging.getLogger(__name__)


class LoyaltyPoints(models.Model):
    """
    Customer এর points wallet।
    balance, lifetime_earned, lifetime_redeemed, pending, frozen।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        # AUDIT FIX (v2): CASCADE → PROTECT।  Deleting a customer with an
        # active balance must be blocked; use soft-delete on Customer instead।
        on_delete=models.PROTECT,
        related_name='loyalty_points',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='loyalty_points',
    )

    balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Current Balance',
    )
    lifetime_earned = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Lifetime Earned',
    )
    lifetime_redeemed = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Lifetime Redeemed',
    )
    lifetime_expired = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Lifetime Expired',
    )
    pending_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Pending Balance',
        help_text='Points pending approval',
    )
    frozen_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Frozen Balance',
        help_text='Points temporarily frozen (fraud hold)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Loyalty Points'
        verbose_name_plural = 'Loyalty Points'
        unique_together = [('customer', 'tenant')]
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['tenant', 'balance']),
        ]

    def __str__(self):
        return f'Points({self.customer.code}: {self.balance})'

    def credit(self, amount: Decimal):
        """Points add করো -- thread-safe নয়, atomic block এ call করুন।"""
        amount = Decimal(str(amount))
        if amount <= 0:
            return
        self.balance += amount
        self.lifetime_earned += amount
        self.save(update_fields=['balance', 'lifetime_earned', 'updated_at'])

    def debit(self, amount: Decimal):
        """Points deduct করো।"""
        amount = Decimal(str(amount))
        if amount <= 0:
            return
        if self.balance < amount:
            raise InsufficientPointsError(available=self.balance, required=amount)
        self.balance -= amount
        self.lifetime_redeemed += amount
        self.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])

    @property
    def available_balance(self) -> Decimal:
        """Frozen balance বাদ দিয়ে available balance।"""
        return max(self.balance - self.frozen_balance, Decimal('0'))


class PointsLedger(models.Model):
    """
    Points transaction ledger -- every credit/debit recorded।
    Immutable audit trail।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        # AUDIT FIX (v2): CASCADE → PROTECT।  The ledger is a permanent
        # financial audit trail; customer deletion must be blocked until
        # ledger records are archived।
        on_delete=models.PROTECT,
        related_name='points_ledger',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='points_ledger',
    )

    txn_type = models.CharField(
        max_length=10,
        choices=[('credit', 'Credit'), ('debit', 'Debit')],
        verbose_name='Transaction Type',
    )
    source = models.CharField(
        max_length=30,
        choices=[
            ('purchase', 'Purchase'), ('referral', 'Referral'),
            ('bonus', 'Bonus'), ('offer', 'Offer'),
            ('redemption', 'Redemption'), ('expiry', 'Expiry'),
            ('transfer', 'Transfer'), ('admin', 'Admin'),
            ('subscription', 'Subscription'), ('badge', 'Badge'),
            ('streak', 'Streak'), ('challenge', 'Challenge'),
            ('milestone', 'Milestone'), ('coalition', 'Coalition'),
            ('partner', 'Partner'), ('conversion', 'Conversion'),
        ],
        verbose_name='Source',
    )
    points = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Points',
    )
    remaining_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Remaining Points',
        help_text='For FIFO expiry tracking',
    )
    balance_after = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Balance After Transaction',
    )
    description = models.CharField(max_length=500, null=True, blank=True)
    # AUDIT FIX (v2): reference_id is now backed by a partial UniqueConstraint
    # (non-null only) defined in Meta.constraints below।  The previous plain
    # Index only sped up lookups; it did NOT prevent duplicates at DB level।
    # The constraint ensures that if the Redis IdempotencyGuard key expires,
    # the database itself rejects a second ledger entry with the same ref।
    reference_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='Reference ID')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Expires At')
    is_reversed = models.BooleanField(default=False, verbose_name='Reversed')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Ledger'
        verbose_name_plural = 'Points Ledger'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['tenant', 'txn_type']),
            models.Index(fields=['source']),
            models.Index(fields=['expires_at']),
            # reference_id plain index retained for fast lookups।
            # Uniqueness enforced by the partial constraint below।
            models.Index(fields=['reference_id']),
        ]
        constraints = [
            # AUDIT FIX (v2): Partial unique constraint -- only non-null
            # reference_ids must be unique।  Multiple NULL values allowed
            # (earns without a caller-supplied reference)।
            # Migration: 0014_financial_integrity_constraints.py
            models.UniqueConstraint(
                fields=['reference_id'],
                condition=models.Q(reference_id__isnull=False),
                name='unique_pointsledger_reference_id_notnull',
            ),
        ]

    def __str__(self):
        return f'Ledger({self.customer.code}: {self.txn_type} {self.points} [{self.source}])'


class PointsExpiry(models.Model):
    """
    Points expiry schedule।
    Earned points এর expiry date track করে।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='points_expiry',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='points_expiry',
    )
    ledger = models.ForeignKey(
        PointsLedger,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='expiry_records',
    )

    points = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Points to Expire')
    earned_at = models.DateTimeField(default=timezone.now, verbose_name='Earned At')
    expires_at = models.DateTimeField(verbose_name='Expires At')

    is_processed = models.BooleanField(default=False, verbose_name='Processed')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='Processed At')
    warning_sent = models.BooleanField(default=False, verbose_name='Warning Sent')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Expiry'
        verbose_name_plural = 'Points Expiry Records'
        ordering = ['expires_at']
        indexes = [
            models.Index(fields=['customer', 'is_processed']),
            models.Index(fields=['expires_at', 'is_processed']),
        ]

    def __str__(self):
        return f'Expiry({self.customer.code}: {self.points} pts @ {self.expires_at.date()})'


class PointsTransfer(models.Model):
    """
    P2P points transfer record।
    Customer থেকে Customer পয়েন্ট transfer।
    """
    from_customer = models.ForeignKey(
        'djoyalty.Customer',
        # AUDIT FIX (v2): CASCADE → PROTECT।  Transfer records are financial
        # audit trails and must survive customer deletion।
        on_delete=models.PROTECT,
        related_name='outgoing_transfers',
        verbose_name='From Customer',
    )
    to_customer = models.ForeignKey(
        'djoyalty.Customer',
        # AUDIT FIX (v2): CASCADE → PROTECT।  Symmetric with from_customer।
        on_delete=models.PROTECT,
        related_name='incoming_transfers',
        verbose_name='To Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='transfers',
    )

    points = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Points Transferred')
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), verbose_name='Transfer Fee')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'), ('completed', 'Completed'),
            ('failed', 'Failed'), ('reversed', 'Reversed'),
        ],
        default='pending',
    )
    note = models.CharField(max_length=500, null=True, blank=True, verbose_name='Note')
    reference = models.CharField(max_length=100, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Transfer'
        verbose_name_plural = 'Points Transfers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['from_customer']),
            models.Index(fields=['to_customer']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'Transfer({self.from_customer.code} -> {self.to_customer.code}: {self.points})'


class PointsConversion(models.Model):
    """
    Points ↔ Cash conversion record।

    AUDIT FIX (v1): Was missing Meta.indexes entirely -- this is a high-query table
    (looked up on every cashout and conversion API call)।
    Added: (customer, status) composite index, (tenant, created_at) index।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='point_conversions',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='point_conversions',
    )

    points_amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Points Amount')
    cash_amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Cash Amount')
    rate = models.DecimalField(max_digits=10, decimal_places=6, verbose_name='Conversion Rate')
    conversion_type = models.CharField(
        max_length=20,
        choices=[('to_cash', 'Points -> Cash'), ('from_cash', 'Cash -> Points')],
        verbose_name='Conversion Type',
    )
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')],
        default='completed',
    )
    reference = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Conversion'
        verbose_name_plural = 'Points Conversions'
        ordering = ['-created_at']
        # AUDIT FIX (v1): Added missing indexes -- was causing full table scans
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'Conversion({self.customer.code}: {self.points_amount} pts ↔ {self.cash_amount})'


class PointsReservation(models.Model):
    """
    Points reservation (hold) before confirmed redemption।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='point_reservations',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='point_reservations',
    )

    points = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Reserved Points')
    reason = models.CharField(max_length=200, null=True, blank=True, verbose_name='Reason')
    reference = models.CharField(max_length=100, unique=True, verbose_name='Reference')
    expires_at = models.DateTimeField(verbose_name='Reservation Expires At')

    is_released = models.BooleanField(default=False, verbose_name='Released')
    is_confirmed = models.BooleanField(default=False, verbose_name='Confirmed')
    released_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Reservation'
        verbose_name_plural = 'Points Reservations'
        indexes = [
            models.Index(fields=['customer', 'is_released']),
            models.Index(fields=['reference']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f'Reservation({self.customer.code}: {self.points} pts, ref={self.reference})'


class PointsRate(models.Model):
    """
    Configurable earn/burn rate per tenant।

    AUDIT FIX (v1): Was missing Meta.indexes -- every earn operation calls
    PointsRate.objects.filter(tenant=..., is_active=True) without an index,
    causing a full table scan per earn transaction।
    Added: (tenant, is_active, effective_date) composite index।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='points_rates',
    )
    earn_rate = models.DecimalField(
        max_digits=10, decimal_places=4,
        default=Decimal('1'),
        verbose_name='Earn Rate',
        help_text='Points per 1 currency unit',
    )
    point_value = models.DecimalField(
        max_digits=10, decimal_places=6,
        default=Decimal('0.01'),
        verbose_name='Point Value',
        help_text='Currency value per 1 point',
    )
    currency = models.CharField(max_length=10, default='BDT', verbose_name='Currency')
    effective_date = models.DateField(default=timezone.now, verbose_name='Effective Date')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Rate'
        verbose_name_plural = 'Points Rates'
        ordering = ['-effective_date']
        # AUDIT FIX (v1): Added missing indexes -- was causing full table scan on every earn
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'effective_date']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'Rate({self.tenant}: earn={self.earn_rate}, value={self.point_value})'


class PointsAdjustment(models.Model):
    """
    Admin manual points adjustment record।

    AUDIT FIX (v1): Was missing Meta.indexes -- admin dashboard queries on
    PointsAdjustment filter by customer and order by created_at without
    any index, causing full table scans on admin views।
    Added: (customer, created_at) composite index, (tenant, created_at) index।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='point_adjustments',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='point_adjustments',
    )

    points = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Points Adjusted',
        help_text='Positive = credit, Negative = debit',
    )
    reason = models.CharField(max_length=500, verbose_name='Reason')
    adjusted_by = models.CharField(max_length=200, null=True, blank=True, verbose_name='Adjusted By')
    admin_note = models.TextField(null=True, blank=True, verbose_name='Admin Note')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Adjustment'
        verbose_name_plural = 'Points Adjustments'
        ordering = ['-created_at']
        # AUDIT FIX (v1): Added missing indexes -- admin dashboard queries unindexed
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self):
        sign = '+' if self.points > 0 else ''
        return f'Adjustment({self.customer.code}: {sign}{self.points} -- {self.reason[:40]})'
