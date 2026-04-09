# api/djoyalty/models/redemption.py
from django.db import models
from ..choices import (
    REDEMPTION_STATUS_CHOICES, REDEMPTION_TYPE_CHOICES,
    VOUCHER_STATUS_CHOICES, VOUCHER_TYPE_CHOICES,
    GIFTCARD_STATUS_CHOICES,
)
from ..constants import POINTS_DECIMAL_PLACES, POINTS_MAX_DIGITS
from ..managers import (
    PendingRedemptionManager, ApprovedRedemptionManager, CompletedRedemptionManager,
    ActiveVoucherManager, ExpiredVoucherManager, UsedVoucherManager,
    ActiveGiftCardManager,
)


class RedemptionRule(models.Model):
    """Redemption rule — কত পয়েন্টে কী পাওয়া যাবে।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_redemptionrule_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    redemption_type = models.CharField(max_length=32, choices=REDEMPTION_TYPE_CHOICES)
    points_required = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    reward_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    min_tier = models.ForeignKey(
        'LoyaltyTier', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    max_per_customer = models.PositiveIntegerField(null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.name} ({self.points_required} pts)'


class RedemptionRequest(models.Model):
    """Customer redemption request।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_redemptionrequest_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='redemption_requests',
    )
    rule = models.ForeignKey(
        'RedemptionRule', on_delete=models.PROTECT,
        related_name='requests', null=True, blank=True,
    )
    redemption_type = models.CharField(max_length=32, choices=REDEMPTION_TYPE_CHOICES)
    points_used = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    reward_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=REDEMPTION_STATUS_CHOICES, default='pending', db_index=True)
    note = models.TextField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=128, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    pending = PendingRedemptionManager()
    approved = ApprovedRedemptionManager()
    completed = CompletedRedemptionManager()

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'tenant'])]

    def __str__(self):
        return f'{self.customer} redeem {self.points_used} pts [{self.status}]'


class RedemptionHistory(models.Model):
    """Redemption status change history।"""

    request = models.ForeignKey(
        'RedemptionRequest', on_delete=models.CASCADE,
        related_name='history',
    )
    from_status = models.CharField(max_length=16)
    to_status = models.CharField(max_length=16)
    changed_by = models.CharField(max_length=128, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request} : {self.from_status} → {self.to_status}'


class Voucher(models.Model):
    """Discount voucher।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_voucher_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vouchers',
    )
    redemption_request = models.ForeignKey(
        'RedemptionRequest', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vouchers',
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    voucher_type = models.CharField(max_length=32, choices=VOUCHER_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=VOUCHER_STATUS_CHOICES, default='active', db_index=True)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    active = ActiveVoucherManager()
    expired_vouchers = ExpiredVoucherManager()
    used_vouchers = UsedVoucherManager()

    class Meta:
        app_label = 'djoyalty'
        indexes = [models.Index(fields=['code']), models.Index(fields=['status'])]

    def __str__(self):
        return f'Voucher {self.code} [{self.status}]'


class VoucherRedemption(models.Model):
    """Voucher use log।"""

    voucher = models.ForeignKey(
        'Voucher', on_delete=models.CASCADE,
        related_name='redemptions',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='voucher_redemptions',
    )
    order_reference = models.CharField(max_length=128, null=True, blank=True)
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.voucher.code} used by {self.customer}'


class GiftCard(models.Model):
    """Gift card।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_giftcard_tenant', db_index=True,
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    initial_value = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_value = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=GIFTCARD_STATUS_CHOICES, default='active', db_index=True)
    issued_to = models.ForeignKey(
        'Customer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gift_cards',
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active_cards = ActiveGiftCardManager()

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'GiftCard {self.code} — {self.remaining_value} remaining [{self.status}]'
