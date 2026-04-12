# api/publisher_tools/publisher_management/publisher_commission.py
"""
Publisher Commission — Tiered commission structure ও referral earning system।
Publisher revenue share, referral bonuses, performance bonuses।
"""
from decimal import Decimal
from datetime import date, timedelta
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class CommissionTier(TimeStampedModel):
    """
    Commission tier structure।
    Revenue বেশি হলে commission rate বেশি — tiered system।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_commissiontier_tenant', db_index=True,
    )

    tier_name = models.CharField(
        max_length=100,
        verbose_name=_("Tier Name"),
        help_text=_("e.g., Bronze, Silver, Gold, Platinum"),
    )
    tier_level = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name=_("Tier Level"),
        help_text=_("1 = lowest, 10 = highest"),
    )

    # ── Revenue Requirements ───────────────────────────────────────────────────
    min_monthly_revenue = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Min Monthly Revenue (USD)"),
        help_text=_("এই tier-এ আসতে হলে min monthly revenue"),
    )
    max_monthly_revenue = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name=_("Max Monthly Revenue (USD)"),
        help_text=_("Unlimited হলে খালি রাখুন"),
    )

    # ── Commission Rates ───────────────────────────────────────────────────────
    base_revenue_share = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('70.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Base Revenue Share (%)"),
        help_text=_("Platform-এর পাশে publisher কত % পাবে"),
    )
    referral_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('5.00'),
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        verbose_name=_("Referral Commission (%)"),
        help_text=_("Referred publisher-এর earning-এর কত % পাবে"),
    )
    performance_bonus_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Performance Bonus (%)"),
        help_text=_("Target exceed করলে extra bonus"),
    )

    # ── Benefits ──────────────────────────────────────────────────────────────
    min_payout_threshold = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('100.00'),
        verbose_name=_("Min Payout Threshold (USD)"),
    )
    payout_frequency = models.CharField(
        max_length=20,
        choices=[
            ('monthly', _('Monthly')),
            ('bimonthly', _('Bi-Monthly')),
            ('weekly', _('Weekly')),
            ('on_demand', _('On Demand')),
        ],
        default='monthly',
        verbose_name=_("Payout Frequency"),
    )
    priority_support = models.BooleanField(default=False, verbose_name=_("Priority Support"))
    dedicated_account_manager = models.BooleanField(
        default=False,
        verbose_name=_("Dedicated Account Manager"),
    )
    advanced_analytics = models.BooleanField(default=False, verbose_name=_("Advanced Analytics Access"))
    custom_floor_prices = models.BooleanField(default=False, verbose_name=_("Custom Floor Prices"))
    header_bidding_access = models.BooleanField(default=False, verbose_name=_("Header Bidding Access"))
    api_access = models.BooleanField(default=True, verbose_name=_("API Access"))
    max_ad_units = models.IntegerField(
        default=10,
        verbose_name=_("Max Ad Units"),
        help_text=_("-1 = unlimited"),
    )
    max_sites = models.IntegerField(default=5, verbose_name=_("Max Sites"), help_text=_("-1 = unlimited"))
    max_apps  = models.IntegerField(default=3, verbose_name=_("Max Apps"),  help_text=_("-1 = unlimited"))

    # ── Badge ─────────────────────────────────────────────────────────────────
    badge_color = models.CharField(max_length=10, default='#6b7280', verbose_name=_("Badge Color (hex)"))
    badge_icon  = models.CharField(max_length=20, default='🥉', verbose_name=_("Badge Icon (emoji)"))
    description = models.TextField(blank=True, verbose_name=_("Tier Description"))

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'publisher_tools_commission_tiers'
        verbose_name = _('Commission Tier')
        verbose_name_plural = _('Commission Tiers')
        ordering = ['tier_level']
        indexes = [
            models.Index(fields=['tier_level']),
            models.Index(fields=['min_monthly_revenue']),
        ]

    def __str__(self):
        return f"{self.badge_icon} {self.tier_name} (Level {self.tier_level}) — {self.base_revenue_share}%"


class PublisherCommission(TimeStampedModel):
    """
    Publisher-এর commission earning record।
    প্রতিটি commission transaction আলাদাভাবে tracked।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publishercommission_tenant', db_index=True,
    )

    COMMISSION_TYPE_CHOICES = [
        ('ad_revenue',        _('Ad Revenue Share')),
        ('referral_level1',   _('Level 1 Referral Commission')),
        ('referral_level2',   _('Level 2 Referral Commission')),
        ('referral_level3',   _('Level 3 Referral Commission')),
        ('performance_bonus', _('Performance Bonus')),
        ('signup_bonus',      _('Signup Bonus')),
        ('milestone_bonus',   _('Milestone Bonus')),
        ('tier_upgrade_bonus',_('Tier Upgrade Bonus')),
        ('seasonal_bonus',    _('Seasonal / Campaign Bonus')),
        ('adjustment',        _('Manual Adjustment')),
    ]

    STATUS_CHOICES = [
        ('pending',   _('Pending')),
        ('confirmed', _('Confirmed')),
        ('paid',      _('Paid')),
        ('cancelled', _('Cancelled')),
        ('reversed',  _('Reversed')),
    ]

    # ── Publisher & Reference ──────────────────────────────────────────────────
    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='commissions',
        verbose_name=_("Publisher"),
        db_index=True,
    )
    commission_type = models.CharField(
        max_length=30,
        choices=COMMISSION_TYPE_CHOICES,
        verbose_name=_("Commission Type"),
        db_index=True,
    )

    # ── Referral specific ─────────────────────────────────────────────────────
    referred_publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='generated_commissions',
        verbose_name=_("Referred Publisher"),
    )
    referral_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Referral Level"),
    )

    # ── Financial ─────────────────────────────────────────────────────────────
    base_amount = models.DecimalField(
        max_digits=14, decimal_places=6,
        verbose_name=_("Base Amount (USD)"),
        help_text=_("যে amount-এর উপর commission calculate হয়েছে"),
    )
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=4,
        verbose_name=_("Commission Rate (%)"),
    )
    commission_amount = models.DecimalField(
        max_digits=14, decimal_places=6,
        verbose_name=_("Commission Amount (USD)"),
    )
    currency = models.CharField(max_length=5, default='USD')

    # ── Period ────────────────────────────────────────────────────────────────
    period_date  = models.DateField(verbose_name=_("Period Date"), db_index=True)
    period_start = models.DateField(null=True, blank=True)
    period_end   = models.DateField(null=True, blank=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status"),
        db_index=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    invoice = models.ForeignKey(
        'publisher_tools.PublisherInvoice',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='commissions',
        verbose_name=_("Invoice"),
    )

    # ── Description ───────────────────────────────────────────────────────────
    description = models.CharField(max_length=500, blank=True, verbose_name=_("Description"))
    notes       = models.TextField(blank=True, verbose_name=_("Notes"))
    metadata    = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_commissions'
        verbose_name = _('Publisher Commission')
        verbose_name_plural = _('Publisher Commissions')
        ordering = ['-period_date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'period_date']),
            models.Index(fields=['commission_type', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['period_date']),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} | {self.commission_type} | ${self.commission_amount} | {self.status}"

    @classmethod
    @transaction.atomic
    def create_ad_revenue_commission(
        cls,
        publisher,
        gross_revenue: Decimal,
        period_date: date,
        tier: CommissionTier = None,
    ) -> 'PublisherCommission':
        """Ad revenue-এর জন্য commission record তৈরি করে"""
        if tier is None:
            # Publisher-এর current tier খোঁজে
            tier = CommissionTier.objects.filter(
                min_monthly_revenue__lte=gross_revenue,
                is_active=True,
            ).order_by('-tier_level').first()

        rate = tier.base_revenue_share if tier else Decimal('70.00')
        amount = gross_revenue * (rate / 100)

        return cls.objects.create(
            publisher=publisher,
            commission_type='ad_revenue',
            base_amount=gross_revenue,
            commission_rate=rate,
            commission_amount=amount,
            period_date=period_date,
            description=f'Ad revenue commission @ {rate}% for {period_date}',
        )

    @classmethod
    @transaction.atomic
    def create_referral_commission(
        cls,
        publisher,
        referred_publisher,
        base_amount: Decimal,
        level: int,
        period_date: date,
    ) -> 'PublisherCommission':
        """Referral commission record তৈরি করে"""
        # Level অনুযায়ী rate
        level_rates = {1: Decimal('5.00'), 2: Decimal('2.00'), 3: Decimal('1.00')}
        rate = level_rates.get(level, Decimal('1.00'))
        amount = base_amount * (rate / 100)

        return cls.objects.create(
            publisher=publisher,
            referred_publisher=referred_publisher,
            commission_type=f'referral_level{level}',
            referral_level=level,
            base_amount=base_amount,
            commission_rate=rate,
            commission_amount=amount,
            period_date=period_date,
            description=f'Level {level} referral commission from {referred_publisher.publisher_id}',
        )

    @classmethod
    def create_milestone_bonus(
        cls,
        publisher,
        milestone_name: str,
        bonus_amount: Decimal,
    ) -> 'PublisherCommission':
        """Milestone bonus commission তৈরি করে"""
        return cls.objects.create(
            publisher=publisher,
            commission_type='milestone_bonus',
            base_amount=bonus_amount,
            commission_rate=Decimal('100.00'),
            commission_amount=bonus_amount,
            period_date=timezone.now().date(),
            description=f'Milestone bonus: {milestone_name}',
        )


class PublisherReferral(TimeStampedModel):
    """
    Publisher referral network।
    কে কাকে refer করেছে এবং তার earnings tracking।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherreferral_tenant', db_index=True,
    )

    # ── Referral Relationship ─────────────────────────────────────────────────
    referrer = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='referred_publishers',
        verbose_name=_("Referrer Publisher"),
    )
    referred = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='referred_by_publisher',
        verbose_name=_("Referred Publisher"),
    )
    referral_code = models.CharField(
        max_length=20,
        verbose_name=_("Referral Code Used"),
        db_index=True,
    )

    # ── Status & Earnings ─────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, db_index=True)
    activation_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Activation Date"),
    )
    first_earning_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("First Earning Date"),
    )

    # ── Aggregate Earnings ────────────────────────────────────────────────────
    total_referred_revenue = models.DecimalField(
        max_digits=14, decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Referred Revenue (USD)"),
    )
    total_commission_earned = models.DecimalField(
        max_digits=14, decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Commission Earned (USD)"),
    )
    level1_commission = models.DecimalField(
        max_digits=14, decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Level 1 Commission (USD)"),
    )
    level2_commission = models.DecimalField(
        max_digits=14, decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Level 2 Commission (USD)"),
    )

    # ── Signup Bonus ──────────────────────────────────────────────────────────
    signup_bonus_paid = models.BooleanField(
        default=False,
        verbose_name=_("Signup Bonus Paid"),
    )
    signup_bonus_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Signup Bonus Amount (USD)"),
    )

    class Meta:
        db_table = 'publisher_tools_publisher_referrals'
        verbose_name = _('Publisher Referral')
        verbose_name_plural = _('Publisher Referrals')
        unique_together = [['referrer', 'referred']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referrer', 'is_active']),
            models.Index(fields=['referred']),
            models.Index(fields=['referral_code']),
        ]

    def __str__(self):
        return f"{self.referrer.publisher_id} → {self.referred.publisher_id}"

    def record_commission(self, referred_revenue: Decimal, level: int = 1):
        """Referral commission record করে"""
        level_rates = {1: Decimal('5.00'), 2: Decimal('2.00'), 3: Decimal('1.00')}
        rate = level_rates.get(level, Decimal('1.00'))
        commission = referred_revenue * (rate / 100)

        self.total_referred_revenue += referred_revenue
        self.total_commission_earned += commission

        if level == 1:
            self.level1_commission += commission
        elif level == 2:
            self.level2_commission += commission

        if not self.first_earning_date:
            self.first_earning_date = timezone.now()

        self.save()

        # Create commission record
        PublisherCommission.create_referral_commission(
            publisher=self.referrer,
            referred_publisher=self.referred,
            base_amount=referred_revenue,
            level=level,
            period_date=timezone.now().date(),
        )

        return commission
