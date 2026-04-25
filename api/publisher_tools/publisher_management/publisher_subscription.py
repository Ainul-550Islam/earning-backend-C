# api/publisher_tools/publisher_management/publisher_subscription.py
"""
Publisher Subscription — Plan management system।
Free, Standard, Premium, Enterprise plan সব কিছু।
"""
from decimal import Decimal
from datetime import date
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class SubscriptionPlan(TimeStampedModel):
    """
    Subscription plan definition।
    Features, limits, pricing এখানে define হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_subplan_tenant', db_index=True,
    )

    PLAN_TYPE_CHOICES = [
        ('free',       _('Free')),
        ('starter',    _('Starter')),
        ('standard',   _('Standard')),
        ('premium',    _('Premium')),
        ('enterprise', _('Enterprise')),
        ('custom',     _('Custom / Negotiated')),
    ]

    BILLING_CYCLE_CHOICES = [
        ('monthly',  _('Monthly')),
        ('quarterly',_('Quarterly')),
        ('annual',   _('Annual')),
        ('lifetime', _('Lifetime')),
    ]

    # ── Plan Identity ──────────────────────────────────────────────────────────
    plan_type    = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, unique=True, db_index=True)
    name         = models.CharField(max_length=100, verbose_name=_("Plan Name"))
    description  = models.TextField(blank=True, verbose_name=_("Description"))
    tagline      = models.CharField(max_length=200, blank=True, verbose_name=_("Tagline"))
    badge_color  = models.CharField(max_length=10, default='#6b7280')
    badge_icon   = models.CharField(max_length=20, default='⭐')
    is_popular   = models.BooleanField(default=False, verbose_name=_("Mark as Popular"))
    is_active    = models.BooleanField(default=True, db_index=True)
    sort_order   = models.IntegerField(default=0)

    # ── Pricing ───────────────────────────────────────────────────────────────
    monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_("Monthly Price (USD)"),
    )
    quarterly_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_("Quarterly Price (USD)"),
    )
    annual_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_("Annual Price (USD)"),
    )
    setup_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_("One-time Setup Fee (USD)"),
    )
    currency = models.CharField(max_length=5, default='USD')

    # ── Revenue Share ──────────────────────────────────────────────────────────
    revenue_share_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('70.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Publisher Revenue Share (%)"),
    )

    # ── Inventory Limits ──────────────────────────────────────────────────────
    max_sites     = models.IntegerField(default=1,  verbose_name=_("Max Sites (-1 = unlimited)"))
    max_apps      = models.IntegerField(default=1,  verbose_name=_("Max Apps (-1 = unlimited)"))
    max_ad_units  = models.IntegerField(default=5,  verbose_name=_("Max Ad Units (-1 = unlimited)"))
    max_placements= models.IntegerField(default=10, verbose_name=_("Max Placements (-1 = unlimited)"))

    # ── Payout Settings ───────────────────────────────────────────────────────
    min_payout_threshold = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('100.00'),
        verbose_name=_("Min Payout Threshold (USD)"),
    )
    payout_frequency = models.CharField(
        max_length=20,
        choices=[('monthly', 'Monthly'), ('bimonthly', 'Bi-Monthly'), ('weekly', 'Weekly'), ('on_demand', 'On Demand')],
        default='monthly',
        verbose_name=_("Payout Frequency"),
    )

    # ── Features ──────────────────────────────────────────────────────────────
    has_api_access           = models.BooleanField(default=False)
    has_advanced_analytics   = models.BooleanField(default=False)
    has_real_time_reporting  = models.BooleanField(default=False)
    has_custom_reports       = models.BooleanField(default=False)
    has_header_bidding       = models.BooleanField(default=False)
    has_mediation            = models.BooleanField(default=True)
    has_a_b_testing          = models.BooleanField(default=False)
    has_fraud_protection     = models.BooleanField(default=True)
    has_advanced_fraud       = models.BooleanField(default=False)
    has_white_label          = models.BooleanField(default=False)
    has_priority_support     = models.BooleanField(default=False)
    has_dedicated_manager    = models.BooleanField(default=False)
    has_custom_integrations  = models.BooleanField(default=False)
    has_multi_currency       = models.BooleanField(default=False)
    has_bulk_operations      = models.BooleanField(default=False)
    has_waterfall_optimizer  = models.BooleanField(default=False)
    has_geo_targeting        = models.BooleanField(default=True)
    has_device_targeting     = models.BooleanField(default=True)
    has_frequency_capping    = models.BooleanField(default=False)
    has_viewability_targeting= models.BooleanField(default=False)
    has_data_export          = models.BooleanField(default=False)

    # ── Support Level ──────────────────────────────────────────────────────────
    support_level = models.CharField(
        max_length=20,
        choices=[
            ('community',  _('Community Forum')),
            ('email',      _('Email Support')),
            ('priority',   _('Priority Email + Chat')),
            ('dedicated',  _('Dedicated Account Manager')),
        ],
        default='email',
        verbose_name=_("Support Level"),
    )
    support_response_hours = models.IntegerField(
        default=48,
        verbose_name=_("Support Response Time (hours)"),
    )

    # ── Trial ─────────────────────────────────────────────────────────────────
    trial_days = models.IntegerField(
        default=0,
        verbose_name=_("Free Trial Days"),
        help_text=_("0 = no trial"),
    )

    # ── Features List for Marketing ────────────────────────────────────────────
    feature_bullets = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Marketing Feature Bullets"),
        help_text=_("['Up to 5 sites', 'Advanced analytics', ...]"),
    )
    limitations = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Limitations / Not Included"),
    )

    class Meta:
        db_table = 'publisher_tools_subscription_plans'
        verbose_name = _('Subscription Plan')
        verbose_name_plural = _('Subscription Plans')
        ordering = ['sort_order', 'monthly_price']
        indexes = [
            models.Index(fields=['plan_type'], name='idx_plan_type_1636'),
            models.Index(fields=['is_active'], name='idx_is_active_1637'),
        ]

    def __str__(self):
        return f"{self.badge_icon} {self.name} — ${self.monthly_price}/mo"

    def get_price(self, billing_cycle: str = 'monthly') -> Decimal:
        """Billing cycle অনুযায়ী price return করে"""
        prices = {
            'monthly':   self.monthly_price,
            'quarterly': self.quarterly_price or (self.monthly_price * 3 * Decimal('0.90')),
            'annual':    self.annual_price or (self.monthly_price * 12 * Decimal('0.80')),
        }
        return prices.get(billing_cycle, self.monthly_price)

    def get_discount_pct(self, billing_cycle: str) -> float:
        """Billing cycle-এর discount percentage"""
        if billing_cycle == 'quarterly' and self.monthly_price > 0:
            quarterly_monthly = (self.quarterly_price or 0) / 3
            if quarterly_monthly > 0:
                return round((1 - quarterly_monthly / self.monthly_price) * 100, 1)
        elif billing_cycle == 'annual' and self.monthly_price > 0:
            annual_monthly = (self.annual_price or 0) / 12
            if annual_monthly > 0:
                return round((1 - annual_monthly / self.monthly_price) * 100, 1)
        return 0.0

    def can_add_site(self, current_site_count: int) -> bool:
        return self.max_sites == -1 or current_site_count < self.max_sites

    def can_add_app(self, current_app_count: int) -> bool:
        return self.max_apps == -1 or current_app_count < self.max_apps

    def can_add_ad_unit(self, current_unit_count: int) -> bool:
        return self.max_ad_units == -1 or current_unit_count < self.max_ad_units


class PublisherSubscription(TimeStampedModel):
    """
    Publisher-এর current subscription।
    কোন plan-এ আছে, কতদিন পর্যন্ত।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publishersub_tenant', db_index=True,
    )

    STATUS_CHOICES = [
        ('trialing',   _('Free Trial')),
        ('active',     _('Active')),
        ('past_due',   _('Past Due')),
        ('cancelled',  _('Cancelled')),
        ('expired',    _('Expired')),
        ('paused',     _('Paused')),
    ]

    BILLING_CYCLE_CHOICES = [
        ('monthly',  _('Monthly')),
        ('quarterly',_('Quarterly')),
        ('annual',   _('Annual')),
        ('lifetime', _('Lifetime')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.OneToOneField(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name=_("Publisher"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name=_("Plan"),
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly',
        verbose_name=_("Billing Cycle"),
    )

    # ── Status & Dates ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Subscription Status"),
        db_index=True,
    )
    started_at    = models.DateTimeField(default=timezone.now, verbose_name=_("Started At"))
    current_period_start = models.DateField(verbose_name=_("Current Period Start"))
    current_period_end   = models.DateField(verbose_name=_("Current Period End"))
    trial_ends_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Trial Ends At"))
    cancelled_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Cancelled At"))
    expires_at    = models.DateTimeField(null=True, blank=True, verbose_name=_("Expires At"))

    # ── Pricing ───────────────────────────────────────────────────────────────
    current_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Current Subscription Price (USD)"),
    )
    discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Discount (%)"),
    )
    coupon_code = models.CharField(max_length=50, blank=True, verbose_name=_("Coupon Code Applied"))

    # ── Auto-renewal ──────────────────────────────────────────────────────────
    auto_renew = models.BooleanField(
        default=True,
        verbose_name=_("Auto Renew"),
    )
    renewal_reminder_sent = models.BooleanField(default=False)
    cancel_at_period_end  = models.BooleanField(
        default=False,
        verbose_name=_("Cancel at Period End"),
    )

    # ── Upgrade/Downgrade ─────────────────────────────────────────────────────
    previous_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='downgraded_subscriptions',
        verbose_name=_("Previous Plan"),
    )
    upgraded_at   = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Upgraded At"))
    downgraded_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Downgraded At"))

    # ── Payment ───────────────────────────────────────────────────────────────
    bank_account = models.ForeignKey(
        'PublisherBankAccount',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subscriptions',
        verbose_name=_("Payment Method"),
    )
    last_payment_at     = models.DateTimeField(null=True, blank=True)
    next_billing_date   = models.DateField(null=True, blank=True)
    failed_payment_count= models.IntegerField(default=0)

    # ── Custom Overrides (for Enterprise) ─────────────────────────────────────
    custom_revenue_share = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name=_("Custom Revenue Share (%) — Override"),
    )
    custom_limits = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Custom Limits Override"),
        help_text=_("{'max_sites': 50, 'max_ad_units': -1}"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Admin Notes"))

    class Meta:
        db_table = 'publisher_tools_publisher_subscriptions'
        verbose_name = _('Publisher Subscription')
        verbose_name_plural = _('Publisher Subscriptions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher'], name='idx_publisher_1638'),
            models.Index(fields=['status'], name='idx_status_1639'),
            models.Index(fields=['current_period_end'], name='idx_current_period_end_1640'),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.plan.name} [{self.status}]"

    @property
    def is_active(self):
        return self.status in ('active', 'trialing')

    @property
    def is_trial(self):
        return self.status == 'trialing' and self.trial_ends_at and timezone.now() < self.trial_ends_at

    @property
    def days_until_renewal(self):
        if self.next_billing_date:
            return (self.next_billing_date - timezone.now().date()).days
        return None

    @property
    def effective_revenue_share(self):
        """Custom override থাকলে সেটা, না হলে plan-এর share"""
        return self.custom_revenue_share or self.plan.revenue_share_pct

    @property
    def effective_max_sites(self):
        return self.custom_limits.get('max_sites', self.plan.max_sites)

    @property
    def effective_max_apps(self):
        return self.custom_limits.get('max_apps', self.plan.max_apps)

    @property
    def effective_max_ad_units(self):
        return self.custom_limits.get('max_ad_units', self.plan.max_ad_units)

    @transaction.atomic
    def upgrade_to(self, new_plan: SubscriptionPlan, billing_cycle: str = None):
        """নতুন plan-এ upgrade করে"""
        self.previous_plan = self.plan
        self.plan = new_plan
        if billing_cycle:
            self.billing_cycle = billing_cycle
        self.current_price = new_plan.get_price(self.billing_cycle)
        self.upgraded_at = timezone.now()
        self.save()

        # Update publisher tier
        publisher = self.publisher
        publisher.tier = new_plan.plan_type if new_plan.plan_type in ('standard', 'premium', 'enterprise') else 'standard'
        publisher.save(update_fields=['tier', 'updated_at'])

    @transaction.atomic
    def cancel(self, cancel_immediately: bool = False):
        """Subscription cancel করে"""
        if cancel_immediately:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
        else:
            self.cancel_at_period_end = True
            self.cancelled_at = timezone.now()
        self.auto_renew = False
        self.save()

    def renew(self):
        """Subscription renew করে"""
        from datetime import timedelta
        if self.billing_cycle == 'monthly':
            delta = timedelta(days=30)
        elif self.billing_cycle == 'quarterly':
            delta = timedelta(days=90)
        elif self.billing_cycle == 'annual':
            delta = timedelta(days=365)
        else:
            return

        today = timezone.now().date()
        self.current_period_start = today
        self.current_period_end   = today + delta
        self.next_billing_date    = today + delta
        self.status = 'active'
        self.last_payment_at = timezone.now()
        self.renewal_reminder_sent = False
        self.save()


class SubscriptionPaymentHistory(TimeStampedModel):
    """
    Subscription payment history।
    প্রতিটি billing event track করে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_subpayment_tenant', db_index=True,
    )

    STATUS_CHOICES = [
        ('pending',   _('Pending')),
        ('succeeded', _('Succeeded')),
        ('failed',    _('Failed')),
        ('refunded',  _('Refunded')),
        ('voided',    _('Voided')),
    ]

    EVENT_CHOICES = [
        ('initial',    _('Initial Subscription')),
        ('renewal',    _('Renewal')),
        ('upgrade',    _('Plan Upgrade')),
        ('downgrade',  _('Plan Downgrade')),
        ('trial_end',  _('Trial Ended')),
        ('refund',     _('Refund')),
        ('adjustment', _('Manual Adjustment')),
    ]

    subscription    = models.ForeignKey(PublisherSubscription, on_delete=models.CASCADE, related_name='payments')
    event_type      = models.CharField(max_length=20, choices=EVENT_CHOICES, db_index=True)
    amount          = models.DecimalField(max_digits=10, decimal_places=2)
    currency        = models.CharField(max_length=5, default='USD')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    payment_method  = models.CharField(max_length=50, blank=True)
    transaction_id  = models.CharField(max_length=100, blank=True, unique=True, null=True)
    gateway_response= models.JSONField(default=dict, blank=True)
    description     = models.CharField(max_length=500, blank=True)
    paid_at         = models.DateTimeField(null=True, blank=True)
    failure_reason  = models.TextField(blank=True)

    class Meta:
        db_table = 'publisher_tools_subscription_payments'
        verbose_name = _('Subscription Payment')
        verbose_name_plural = _('Subscription Payments')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subscription.publisher.publisher_id} — {self.event_type} — ${self.amount} — {self.status}"
