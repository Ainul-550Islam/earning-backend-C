# api/djoyalty/models/redemption.py
"""
Djoyalty Redemption Models।
RedemptionRule, RedemptionRequest, RedemptionHistory,
Voucher, VoucherRedemption, GiftCard।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager, PendingManager

logger = logging.getLogger(__name__)


class RedemptionRule(models.Model):
    """
    Configurable redemption rule -- কীভাবে points redeem করা যাবে।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='redemption_rules',
    )
    name = models.CharField(max_length=200, verbose_name='Rule Name')
    description = models.TextField(null=True, blank=True)

    reward_type = models.CharField(
        max_length=30,
        choices=[
            ('cashback', 'Cashback'), ('voucher', 'Voucher'),
            ('product', 'Product'), ('gift', 'Gift'),
            ('donation', 'Donation'),
        ],
        default='cashback',
        verbose_name='Reward Type',
    )
    points_required = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Points Required',
    )
    cash_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Cash Value',
    )
    min_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('100'),
        verbose_name='Minimum Points',
    )
    max_per_user_per_day = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Max Redemptions per User per Day',
    )

    # Tier restriction
    min_tier = models.ForeignKey(
        'djoyalty.LoyaltyTier',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='redemption_rules',
        verbose_name='Minimum Tier Required',
    )

    approval_required = models.BooleanField(default=False, verbose_name='Approval Required')
    is_active = models.BooleanField(default=True)

    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    image = models.URLField(null=True, blank=True, verbose_name='Reward Image URL')
    terms = models.TextField(null=True, blank=True, verbose_name='Terms & Conditions')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Redemption Rule'
        verbose_name_plural = 'Redemption Rules'
        ordering = ['points_required']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['reward_type']),
        ]

    def __str__(self):
        return f'RedemptionRule({self.name}: {self.points_required} pts -> {self.reward_type})'


class RedemptionRequest(models.Model):
    """
    Customer redemption request।
    pending -> approved/rejected -> fulfilled।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='redemption_requests',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='redemption_requests',
    )
    rule = models.ForeignKey(
        RedemptionRule,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='requests',
        verbose_name='Redemption Rule',
    )

    points_used = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Points Used')
    redemption_type = models.CharField(max_length=30, default='cashback', verbose_name='Redemption Type')
    reward_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Reward Value (currency)',
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'), ('approved', 'Approved'),
            ('rejected', 'Rejected'), ('fulfilled', 'Fulfilled'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        verbose_name='Status',
    )

    reviewed_by = models.CharField(max_length=200, null=True, blank=True, verbose_name='Reviewed By')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Reviewed At')
    fulfilled_at = models.DateTimeField(null=True, blank=True, verbose_name='Fulfilled At')
    note = models.TextField(null=True, blank=True, verbose_name='Review Note')
    reference = models.CharField(max_length=100, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    pending = PendingManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Redemption Request'
        verbose_name_plural = 'Redemption Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'RedemptionReq(#{self.id}: {self.customer.code} -- {self.points_used} pts [{self.status}])'


class RedemptionHistory(models.Model):
    """
    Redemption status change history (audit trail)।
    """
    request = models.ForeignKey(
        RedemptionRequest,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Redemption Request',
    )
    from_status = models.CharField(max_length=20, verbose_name='From Status')
    to_status = models.CharField(max_length=20, verbose_name='To Status')
    changed_by = models.CharField(max_length=200, null=True, blank=True, verbose_name='Changed By')
    note = models.TextField(null=True, blank=True, verbose_name='Note')
    changed_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Redemption History'
        ordering = ['-changed_at']
        # AUDIT FIX (4): (request, changed_at) for audit trail ordering.
        indexes = [
            models.Index(fields=['request', 'changed_at'],
                         name='redemhist_request_time_idx'),
        ]

    def __str__(self):
        return f'RedHistory(#{self.request_id}: {self.from_status} -> {self.to_status})'


class Voucher(models.Model):
    """
    Discount voucher -- points redeem করে generate হয়।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='vouchers',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='vouchers',
    )

    code = models.CharField(max_length=50, unique=True, verbose_name='Voucher Code')
    voucher_type = models.CharField(
        max_length=30,
        choices=[
            ('percent', 'Percentage Discount'), ('fixed', 'Fixed Discount'),
            ('free_shipping', 'Free Shipping'), ('product', 'Free Product'),
        ],
        default='percent',
        verbose_name='Voucher Type',
    )
    discount_value = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Discount Value',
    )
    points_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Cost',
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'), ('used', 'Used'),
            ('expired', 'Expired'), ('cancelled', 'Cancelled'),
        ],
        default='active',
    )

    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Expires At')
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    merchant = models.CharField(max_length=200, null=True, blank=True, verbose_name='Merchant')
    terms = models.TextField(null=True, blank=True)
    minimum_order = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Voucher'
        verbose_name_plural = 'Vouchers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['expires_at', 'status']),
        ]

    def __str__(self):
        return f'Voucher({self.code}: {self.discount_value} [{self.status}])'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)


class VoucherRedemption(models.Model):
    """
    Voucher usage record।
    """
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name='redemptions',
        verbose_name='Voucher',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='voucher_redemptions',
        verbose_name='Used By',
    )
    order_reference = models.CharField(max_length=100, null=True, blank=True, verbose_name='Order Reference')
    discount_applied = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Discount Applied',
    )
    merchant_ref = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=200, null=True, blank=True)
    used_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Voucher Redemption'
        ordering = ['-used_at']
        # AUDIT FIX (4): (voucher,) for checking voucher usage count;
        # (customer, used_at) for customer redemption history.
        indexes = [
            models.Index(fields=['voucher', 'used_at'],
                         name='voucherred_voucher_time_idx'),
            models.Index(fields=['customer', 'used_at'],
                         name='voucherred_customer_time_idx'),
        ]

    def __str__(self):
        return f'VoucherUse({self.voucher.code} by {self.customer.code})'


class GiftCard(models.Model):
    """
    Gift card -- issue করা যায়, balance আছে।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='gift_cards',
    )
    issued_to = models.ForeignKey(
        'djoyalty.Customer',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='gift_cards',
        verbose_name='Issued To',
    )

    code = models.CharField(max_length=30, unique=True, verbose_name='Gift Card Code')
    initial_value = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Initial Value')
    remaining_value = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Remaining Value')
    currency = models.CharField(max_length=10, default='BDT')

    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'), ('used', 'Used'),
            ('expired', 'Expired'), ('cancelled', 'Cancelled'),
        ],
        default='active',
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    used_at = models.DateTimeField(null=True, blank=True)

    issued_by = models.CharField(max_length=200, null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Gift Card'
        verbose_name_plural = 'Gift Cards'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'GiftCard({self.code}: {self.remaining_value}/{self.initial_value} [{self.status}])'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)
