# api/djoyalty/models/referral.py
"""
Referral Tracking Models -- Complete referral system।
ReferralLink, ReferralClick, ReferralConversion, CommissionPayout।

World reference: CPAlead 5% referral program,
Smile.io referrals, Dropbox-style referral growth।

AUDIT FIXES (v1 -- Database Index):
  ReferralConversion: Added (referred_customer, status) composite index।
  This is used in LoyaltyValidator.validate_referral() duplicate-referral
  check and in referral dashboards -- previously caused a full table scan
  on every referral validation request।

AUDIT FIXES (v2 -- Financial Integrity):
  ReferralConversion.Meta.constraints:
    Added UniqueConstraint `unique_referred_customer_active` (partial):
    Only one ReferralConversion record per referred_customer may have
    status 'approved' or 'paid'।  This removes the race condition in
    LoyaltyValidator.validate_referral() where two concurrent requests
    both pass the exists() check before either commits, resulting in a
    customer receiving double welcome points and the referrer receiving
    double commission।
    The index added in v1 speeds up the check; this constraint enforces
    it at DB level regardless of application-layer timing।
    Migration: 0014_financial_integrity_constraints.py
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class ReferralLink(models.Model):
    """
    Customer এর unique referral link।
    Track clicks, conversions, commissions।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='referral_links',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referral_links',
    )
    code = models.CharField(max_length=30, unique=True, verbose_name='Referral Code')
    short_url = models.URLField(null=True, blank=True, verbose_name='Short URL')
    destination_url = models.URLField(
        null=True, blank=True,
        verbose_name='Landing URL',
        help_text='Where referral link redirects to',
    )

    # Stats
    total_clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    total_points_earned = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    total_commission_earned = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )

    is_active = models.BooleanField(default=True)
    campaign = models.ForeignKey(
        'djoyalty.LoyaltyCampaign', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referral_links',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Referral Link'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['customer']),
        ]

    def __str__(self):
        return f'RefLink({self.customer.code}: {self.code} clicks={self.total_clicks})'


class ReferralClick(models.Model):
    """
    Individual click on a referral link।
    """
    referral_link = models.ForeignKey(
        ReferralLink, on_delete=models.CASCADE,
        related_name='clicks',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    country_code = models.CharField(max_length=5, null=True, blank=True)
    device_type = models.CharField(
        max_length=15,
        choices=[('mobile', 'Mobile'), ('desktop', 'Desktop'), ('tablet', 'Tablet')],
        null=True, blank=True,
    )
    referrer_url = models.URLField(null=True, blank=True)
    is_unique = models.BooleanField(default=True)
    converted = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Referral Click'
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['referral_link', 'converted']),
            models.Index(fields=['ip_address', 'clicked_at']),
        ]

    def __str__(self):
        return f'Click({self.referral_link.code}: {self.ip_address})'


class ReferralConversion(models.Model):
    """
    Successful referral conversion -- new customer signed up/purchased।
    """
    referral_link = models.ForeignKey(
        ReferralLink, on_delete=models.CASCADE,
        related_name='conversions',
    )
    referrer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='referral_conversions_made',
        verbose_name='Referrer (who shared the link)',
    )
    referred_customer = models.ForeignKey(
        'djoyalty.Customer', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referral_conversions_received',
        verbose_name='Referred Customer (who joined)',
    )
    referral_click = models.ForeignKey(
        ReferralClick, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='conversions',
    )

    conversion_type = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'New Signup'),
            ('first_purchase', 'First Purchase'),
            ('purchase', 'Purchase'),
            ('offer_complete', 'Offer Completion'),
        ],
        default='signup',
    )

    # Rewards
    referrer_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Awarded to Referrer',
    )
    referred_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Welcome Points Awarded to New Customer',
    )
    commission_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Cash Commission Earned',
    )
    commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name='Commission %',
    )

    # Metadata
    order_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Order Value (if purchase)',
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('paid', 'Points/Commission Paid'),
            ('rejected', 'Rejected'),
            ('chargeback', 'Chargeback'),
        ],
        default='approved',
    )
    level = models.PositiveIntegerField(
        default=1,
        verbose_name='Referral Level',
        help_text='1=direct, 2=indirect (referrer of referrer)',
    )

    converted_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Referral Conversion'
        ordering = ['-converted_at']
        indexes = [
            models.Index(fields=['referrer', 'status']),
            models.Index(fields=['converted_at']),
            # AUDIT FIX (v1): Added (referred_customer, status) -- used in
            # duplicate referral validation and dashboards।
            models.Index(fields=['referred_customer', 'status']),
        ]
        constraints = [
            # AUDIT FIX (v2): Prevent double-referral race condition।
            # Only one active (approved/paid) ReferralConversion per
            # referred_customer is allowed at the DB level।
            # The application-level check in LoyaltyValidator.validate_referral()
            # had a TOCTOU race condition: two concurrent requests both passed
            # .exists() before either committed, resulting in double points for
            # the referrer and double welcome points for the new customer।
            # This partial UniqueConstraint closes that window definitively।
            # Migration: 0014_financial_integrity_constraints.py
            models.UniqueConstraint(
                fields=['referred_customer'],
                condition=models.Q(status__in=['approved', 'paid']),
                name='unique_referred_customer_active',
            ),
        ]

    def __str__(self):
        return (
            f'Conversion({self.referrer.code} -> '
            f'{self.referred_customer.code if self.referred_customer else "?"}: '
            f'+{self.referrer_points} pts)'
        )


class ReferralProgram(models.Model):
    """
    Referral program configuration per tenant।
    Define: how much points referrer gets, how much referred gets,
    multi-level commissions, etc.
    """
    tenant = models.OneToOneField(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referral_program',
    )
    name = models.CharField(max_length=200, default='Refer a Friend')
    description = models.TextField(null=True, blank=True)

    # Referrer rewards
    referrer_signup_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('100'),
        verbose_name='Points for Referrer on New Signup',
    )
    referrer_first_purchase_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('200'),
        verbose_name="Points for Referrer on Referred Customer's First Purchase",
    )
    referrer_ongoing_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5'),
        verbose_name='Ongoing Commission % (CPAlead style)',
        help_text="% of referred customer's purchases credited to referrer as points",
    )

    # Referred customer rewards
    referred_welcome_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('50'),
        verbose_name='Welcome Bonus for New Customer',
    )

    # Multi-level (CPAlead has up to 3 levels)
    max_levels = models.PositiveIntegerField(
        default=1, verbose_name='Max Referral Levels',
        help_text='1=direct only, 2=referrer of referrer also gets rewards',
    )
    level2_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2'),
        verbose_name='Level 2 Commission %',
    )
    level3_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('1'),
        verbose_name='Level 3 Commission %',
    )

    # Limits
    max_referrals_per_customer = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Max Referrals per Customer (null=unlimited)',
    )
    self_referral_allowed = models.BooleanField(default=False)
    require_first_purchase = models.BooleanField(
        default=False,
        verbose_name='Require First Purchase for Referrer to Get Points',
    )

    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Referral Program'
        # AUDIT FIX (4): tenant is OneToOneField (covered by unique index).
        # (is_active,) for 'is referral active?' check on every new signup.
        indexes = [
            models.Index(fields=['is_active'],
                         name='refprog_active_idx'),
        ]

    def __str__(self):
        return f'ReferralProgram({self.name})'
