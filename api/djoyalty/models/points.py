# api/djoyalty/models/points.py
"""
Points models: LoyaltyPoints, PointsLedger, PointsExpiry,
PointsTransfer, PointsConversion, PointsReservation, PointsRate, PointsAdjustment
"""

from django.db import models
from django.utils import timezone
from ..choices import (
    LEDGER_TYPE_CHOICES, LEDGER_SOURCE_CHOICES,
    TRANSFER_STATUS_CHOICES, GIFTCARD_STATUS_CHOICES,
)
from ..constants import POINTS_DECIMAL_PLACES, POINTS_MAX_DIGITS
from ..managers import (
    CreditLedgerManager, DebitLedgerManager,
    ActiveLedgerManager, ExpiringLedgerManager, ExpiredLedgerManager,
    PendingTransferManager, CompletedTransferManager,
)


class LoyaltyPoints(models.Model):
    """Customer এর total points balance — single source of truth।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_loyaltypoints_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='loyalty_points',
    )
    balance = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS,
        decimal_places=POINTS_DECIMAL_PLACES,
        default=0,
    )
    lifetime_earned = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0,
    )
    lifetime_redeemed = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0,
    )
    lifetime_expired = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0,
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('tenant', 'customer')]
        indexes = [models.Index(fields=['tenant', 'customer'])]

    def __str__(self):
        return f'{self.customer} — {self.balance} pts'

    def credit(self, amount, save=True):
        from decimal import Decimal
        self.balance += Decimal(str(amount))
        self.lifetime_earned += Decimal(str(amount))
        if save:
            self.save(update_fields=['balance', 'lifetime_earned', 'updated_at'])

    def debit(self, amount, save=True):
        from decimal import Decimal
        amt = Decimal(str(amount))
        if self.balance < amt:
            from ..exceptions import InsufficientPointsError
            raise InsufficientPointsError(available=self.balance, required=amt)
        self.balance -= amt
        self.lifetime_redeemed += amt
        if save:
            self.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])


class PointsLedger(models.Model):
    """Points এর প্রতিটি credit/debit এর audit trail।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointsledger_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_ledger',
    )
    txn_type = models.CharField(max_length=16, choices=LEDGER_TYPE_CHOICES, db_index=True)
    source = models.CharField(max_length=32, choices=LEDGER_SOURCE_CHOICES, db_index=True)
    points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    remaining_points = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0,
    )
    balance_after = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0,
    )
    description = models.TextField(null=True, blank=True)
    reference_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)

    objects = models.Manager()
    credits = CreditLedgerManager()
    debits = DebitLedgerManager()
    active = ActiveLedgerManager()
    expiring = ExpiringLedgerManager()
    expired = ExpiredLedgerManager()

    class Meta:
        app_label = 'djoyalty'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['txn_type', 'source']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.txn_type.upper()} {self.points} pts — {self.customer}'


class PointsExpiry(models.Model):
    """Points expiry schedule।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointsexpiry_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_expiries',
    )
    ledger_entry = models.ForeignKey(
        'PointsLedger', on_delete=models.CASCADE,
        related_name='expiry_records', null=True, blank=True,
    )
    points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    expires_at = models.DateTimeField(db_index=True)
    is_processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    warning_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        indexes = [
            models.Index(fields=['expires_at', 'is_processed']),
            models.Index(fields=['tenant', 'customer']),
        ]

    def __str__(self):
        return f'{self.points} pts expire @ {self.expires_at} for {self.customer}'


class PointsTransfer(models.Model):
    """Customer থেকে Customer points transfer।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointstransfer_tenant', db_index=True,
    )
    from_customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_transfers_sent',
    )
    to_customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_transfers_received',
    )
    points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    status = models.CharField(max_length=16, choices=TRANSFER_STATUS_CHOICES, default='pending', db_index=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    pending = PendingTransferManager()
    completed = CompletedTransferManager()

    class Meta:
        app_label = 'djoyalty'
        indexes = [models.Index(fields=['status']), models.Index(fields=['tenant'])]

    def __str__(self):
        return f'{self.points} pts: {self.from_customer} → {self.to_customer} [{self.status}]'


class PointsConversion(models.Model):
    """Points to currency conversion log।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointsconversion_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_conversions',
    )
    points_used = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    currency_value = models.DecimalField(max_digits=10, decimal_places=2)
    conversion_rate = models.DecimalField(max_digits=8, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.points_used} pts = {self.currency_value} for {self.customer}'


class PointsReservation(models.Model):
    """Points reservation (hold) — checkout এর সময়।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointsreservation_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_reservations',
    )
    points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    reference = models.CharField(max_length=128, db_index=True)
    is_released = models.BooleanField(default=False, db_index=True)
    is_confirmed = models.BooleanField(default=False)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'
        indexes = [models.Index(fields=['reference']), models.Index(fields=['expires_at'])]

    def __str__(self):
        return f'Reserved {self.points} pts for {self.customer} [{self.reference}]'


class PointsRate(models.Model):
    """Earn/burn rate configuration per tenant।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointsrate_tenant', db_index=True,
    )
    earn_rate = models.DecimalField(max_digits=8, decimal_places=4, default=1)
    point_value = models.DecimalField(max_digits=8, decimal_places=6, default=0.01)
    min_spend_to_earn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rounding = models.CharField(
        max_length=16,
        choices=[('floor', 'Floor'), ('ceil', 'Ceil'), ('round', 'Round')],
        default='floor',
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'Rate: {self.earn_rate} pts/unit | 1pt={self.point_value}'


class PointsAdjustment(models.Model):
    """Admin manual points adjustment।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointsadjustment_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_adjustments',
    )
    points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    reason = models.TextField()
    adjusted_by = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'Adj {self.points} pts for {self.customer} — {self.reason[:40]}'
