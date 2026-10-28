"""
api/offerwall/b2b/models.py

B2B SaaS models for the offerwall white-label platform.

A B2BClient is any company/developer that embeds your offerwall
into their product.  Each client has:
  - A Plan          (free / starter / pro / enterprise)
  - A UsageRecord   (API calls, conversions, revenue this month)
  - A RevenueShare  (how much % they earn per conversion)
  - An Onboarding   (signup → verified → active lifecycle)
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
# 1. Plan
# ─────────────────────────────────────────────────────────────

class B2BPlan(models.Model):
    """
    Subscription plan tiers offered to publishers.

    free        → 0 cost, limited API calls, 0% rev share
    starter     → ৳2,000/mo, 50k calls, 10% rev share
    pro         → ৳8,000/mo, 500k calls, 20% rev share
    enterprise  → custom pricing, unlimited, 30%+ rev share
    """

    PLAN_TYPES = (
        ('free',       'Free'),
        ('starter',    'Starter'),
        ('pro',        'Pro'),
        ('enterprise', 'Enterprise'),
    )

    id                   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name                 = models.CharField(max_length=50, unique=True)
    plan_type            = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    monthly_price_bdt    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    monthly_price_usd    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    # Limits
    monthly_api_calls    = models.PositiveIntegerField(default=1000,
                           help_text='Max API calls per calendar month (0=unlimited)')
    monthly_conversions  = models.PositiveIntegerField(default=100,
                           help_text='Max conversions credited per month')
    max_active_walls     = models.PositiveIntegerField(default=1,
                           help_text='Number of OfferWall instances allowed')
    max_api_keys         = models.PositiveIntegerField(default=2)

    # Revenue share (publisher earns this % of offer payout)
    revenue_share_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))

    # Features
    allow_content_lock   = models.BooleanField(default=False)
    allow_bulk_webhook   = models.BooleanField(default=False)
    allow_custom_domain  = models.BooleanField(default=False)
    allow_white_label    = models.BooleanField(default=False)
    allow_survey_offers  = models.BooleanField(default=False)
    allow_analytics_api  = models.BooleanField(default=False)
    support_level        = models.CharField(max_length=50, default='community',
                           help_text='community / email / priority / dedicated')

    is_active            = models.BooleanField(default=True)
    is_public            = models.BooleanField(default=True,
                           help_text='Show on pricing page')
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'offerwall'
        ordering = ['monthly_price_bdt']
        verbose_name        = 'B2B plan'
        verbose_name_plural = 'B2B plans'

    def __str__(self):
        return f'{self.name} (৳{self.monthly_price_bdt}/mo)'

    @classmethod
    def get_free(cls):
        return cls.objects.filter(plan_type='free').first()

    def is_unlimited_calls(self):
        return self.monthly_api_calls == 0

    def get_feature_list(self):
        feats = []
        if self.allow_content_lock:   feats.append('Content locking')
        if self.allow_bulk_webhook:   feats.append('Bulk webhook')
        if self.allow_custom_domain:  feats.append('Custom domain')
        if self.allow_white_label:    feats.append('White-label branding')
        if self.allow_survey_offers:  feats.append('Survey offers')
        if self.allow_analytics_api:  feats.append('Analytics API')
        return feats


# ─────────────────────────────────────────────────────────────
# 2. B2B Client (the publisher / company)
# ─────────────────────────────────────────────────────────────

class B2BClient(models.Model):
    """
    A business that embeds the offerwall into their product.

    Lifecycle:  pending → verified → active → suspended → churned
    """

    STATUS_CHOICES = (
        ('pending',    'Pending review'),
        ('verified',   'Verified'),
        ('active',     'Active'),
        ('suspended',  'Suspended'),
        ('churned',    'Churned'),
    )

    BUSINESS_TYPES = (
        ('mobile_app',   'Mobile app'),
        ('web_app',      'Web application'),
        ('game',         'Game'),
        ('browser_ext',  'Browser extension'),
        ('other',        'Other'),
    )

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Owner account
    owner           = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='b2b_client',
    )

    # Company info
    company_name    = models.CharField(max_length=200)
    company_website = models.URLField(max_length=500, blank=True)
    business_type   = models.CharField(max_length=30, choices=BUSINESS_TYPES, default='web_app')
    country         = models.CharField(max_length=2, default='BD',
                      help_text='ISO 3166-1 alpha-2')
    vat_number      = models.CharField(max_length=100, blank=True)
    description     = models.TextField(blank=True,
                      help_text='What is your product / how will you use the offerwall?')

    # Plan
    plan            = models.ForeignKey(B2BPlan, on_delete=models.PROTECT,
                      related_name='clients', null=True, blank=True)
    plan_started_at = models.DateTimeField(null=True, blank=True)
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    billing_cycle   = models.CharField(max_length=10, default='monthly',
                      choices=[('monthly','Monthly'),('annual','Annual')])

    # Status
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    verified_at     = models.DateTimeField(null=True, blank=True)
    suspended_at    = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    # Revenue share (overrides plan default if set)
    custom_revenue_share_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Leave blank to use plan default')

    # Contact
    contact_email   = models.EmailField()
    contact_phone   = models.CharField(max_length=20, blank=True)

    # Internal notes
    notes           = models.TextField(blank=True)
    internal_tags   = models.JSONField(default=list, blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'offerwall'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'],       name='idx_b2b_status'),
            models.Index(fields=['owner'],        name='idx_b2b_owner'),
            models.Index(fields=['plan', 'status'], name='idx_b2b_plan_status'),
        ]
        verbose_name        = 'B2B client'
        verbose_name_plural = 'B2B clients'

    def __str__(self):
        return f'{self.company_name} [{self.status}]'

    @property
    def effective_revenue_share(self):
        if self.custom_revenue_share_pct is not None:
            return self.custom_revenue_share_pct
        if self.plan:
            return self.plan.revenue_share_pct
        return Decimal('0')

    def is_active(self):
        return self.status == 'active'

    def is_plan_valid(self):
        if not self.plan:
            return False
        if self.plan_expires_at and timezone.now() > self.plan_expires_at:
            return False
        return True

    def activate(self):
        self.status = 'active'
        self.save(update_fields=['status', 'updated_at'])

    def suspend(self, reason=''):
        self.status = 'suspended'
        self.suspended_at = timezone.now()
        self.suspension_reason = reason
        self.save(update_fields=['status', 'suspended_at', 'suspension_reason', 'updated_at'])

    def get_current_usage(self):
        now = timezone.now()
        record, _ = B2BUsageRecord.objects.get_or_create(
            client=self,
            period_year=now.year,
            period_month=now.month,
        )
        return record

    def has_feature(self, feature_name):
        """Check if client's plan includes a feature."""
        if not self.plan:
            return False
        return getattr(self.plan, f'allow_{feature_name}', False)

    def can_make_api_call(self):
        """Check quota before serving any API request."""
        if not self.is_active():
            return False, 'client_suspended'
        usage = self.get_current_usage()
        if not self.plan.is_unlimited_calls():
            if usage.api_calls >= self.plan.monthly_api_calls:
                return False, 'quota_exceeded'
        return True, None


# ─────────────────────────────────────────────────────────────
# 3. Usage metering (per month)
# ─────────────────────────────────────────────────────────────

class B2BUsageRecord(models.Model):
    """
    Rolling monthly usage counters per B2BClient.
    One row per (client, year, month).
    """

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client          = models.ForeignKey(B2BClient, on_delete=models.CASCADE,
                      related_name='usage_records')
    period_year     = models.PositiveSmallIntegerField()
    period_month    = models.PositiveSmallIntegerField()   # 1–12

    # Counts
    api_calls        = models.PositiveIntegerField(default=0)
    conversions      = models.PositiveIntegerField(default=0)
    offer_views      = models.PositiveIntegerField(default=0)
    offer_clicks     = models.PositiveIntegerField(default=0)
    content_unlocks  = models.PositiveIntegerField(default=0)
    webhook_calls    = models.PositiveIntegerField(default=0)

    # Revenue
    gross_revenue_usd   = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    publisher_share_usd = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))

    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'offerwall'
        unique_together = [('client', 'period_year', 'period_month')]
        ordering = ['-period_year', '-period_month']
        verbose_name        = 'B2B usage record'
        verbose_name_plural = 'B2B usage records'

    def __str__(self):
        return f'{self.client.company_name} {self.period_year}/{self.period_month:02d}'

    def increment(self, field, amount=1):
        """Thread-safe atomic increment."""
        B2BUsageRecord.objects.filter(pk=self.pk).update(
            **{field: models.F(field) + amount})

    def quota_pct(self):
        """Percentage of monthly API call quota used."""
        if not self.client.plan or self.client.plan.is_unlimited_calls():
            return 0.0
        limit = self.client.plan.monthly_api_calls
        return round(self.api_calls / limit * 100, 1) if limit else 0.0


# ─────────────────────────────────────────────────────────────
# 4. Revenue share / Invoice
# ─────────────────────────────────────────────────────────────

class B2BInvoice(models.Model):
    """
    Monthly invoice generated for each B2BClient.
    Includes plan fee + revenue share earned.
    """

    STATUS_CHOICES = (
        ('draft',     'Draft'),
        ('issued',    'Issued'),
        ('paid',      'Paid'),
        ('overdue',   'Overdue'),
        ('cancelled', 'Cancelled'),
    )

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client          = models.ForeignKey(B2BClient, on_delete=models.CASCADE,
                      related_name='invoices')
    invoice_number  = models.CharField(max_length=30, unique=True)
    period_year     = models.PositiveSmallIntegerField()
    period_month    = models.PositiveSmallIntegerField()

    # Amounts
    plan_fee_bdt         = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    revenue_share_usd    = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    revenue_share_bdt    = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    tax_bdt              = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    total_due_bdt        = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_payable_bdt    = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                           help_text='After subtracting revenue share earned')

    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    issued_at       = models.DateTimeField(null=True, blank=True)
    due_date        = models.DateField(null=True, blank=True)
    paid_at         = models.DateTimeField(null=True, blank=True)
    payment_method  = models.CharField(max_length=50, blank=True)
    payment_ref     = models.CharField(max_length=200, blank=True)
    notes           = models.TextField(blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'offerwall'
        ordering = ['-period_year', '-period_month']
        verbose_name        = 'B2B invoice'
        verbose_name_plural = 'B2B invoices'

    def __str__(self):
        return f'{self.invoice_number} — {self.client.company_name}'

    def mark_paid(self, method='', ref=''):
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.payment_method = method
        self.payment_ref = ref
        self.save(update_fields=['status', 'paid_at', 'payment_method',
                                  'payment_ref'])

    @classmethod
    def generate_number(cls, client, year, month):
        seq = cls.objects.filter(
            period_year=year, period_month=month).count() + 1
        return f'INV-{year}{month:02d}-{seq:04d}'


# ─────────────────────────────────────────────────────────────
# 5. Onboarding checklist
# ─────────────────────────────────────────────────────────────

class B2BOnboarding(models.Model):
    """
    Tracks each publisher's onboarding progress.
    Steps: signup → verified → integrated → live
    """

    STEP_CHOICES = (
        ('signup',      'Account created'),
        ('profile',     'Company profile complete'),
        ('plan',        'Plan selected'),
        ('api_key',     'First API key created'),
        ('integration', 'First embed token generated'),
        ('test_conv',   'First test conversion received'),
        ('live',        'First real conversion approved'),
    )

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client          = models.OneToOneField(B2BClient, on_delete=models.CASCADE,
                      related_name='onboarding')

    completed_steps = models.JSONField(default=list,
                      help_text='List of completed step keys')
    current_step    = models.CharField(max_length=20, choices=STEP_CHOICES, default='signup')
    is_complete     = models.BooleanField(default=False)
    completed_at    = models.DateTimeField(null=True, blank=True)

    # Timestamps per step
    signup_at       = models.DateTimeField(null=True, blank=True)
    profile_at      = models.DateTimeField(null=True, blank=True)
    plan_at         = models.DateTimeField(null=True, blank=True)
    api_key_at      = models.DateTimeField(null=True, blank=True)
    integration_at  = models.DateTimeField(null=True, blank=True)
    test_conv_at    = models.DateTimeField(null=True, blank=True)
    live_at         = models.DateTimeField(null=True, blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    STEP_ORDER = ['signup', 'profile', 'plan', 'api_key', 'integration', 'test_conv', 'live']

    class Meta:
        app_label = 'offerwall'
        verbose_name        = 'B2B onboarding'
        verbose_name_plural = 'B2B onboardings'

    def __str__(self):
        pct = self.completion_pct()
        return f'{self.client.company_name} onboarding ({pct}%)'

    def complete_step(self, step_key):
        if step_key not in self.completed_steps:
            self.completed_steps.append(step_key)
            ts_field = f'{step_key}_at'
            if hasattr(self, ts_field):
                setattr(self, ts_field, timezone.now())
            # Advance current_step
            idx = self.STEP_ORDER.index(step_key) if step_key in self.STEP_ORDER else -1
            if idx >= 0 and idx + 1 < len(self.STEP_ORDER):
                self.current_step = self.STEP_ORDER[idx + 1]
            if set(self.STEP_ORDER).issubset(set(self.completed_steps)):
                self.is_complete = True
                self.completed_at = timezone.now()
            self.save()

    def completion_pct(self):
        done = len([s for s in self.STEP_ORDER if s in self.completed_steps])
        return round(done / len(self.STEP_ORDER) * 100)

    def next_step_display(self):
        for step in self.STEP_ORDER:
            if step not in self.completed_steps:
                return dict(self.STEP_CHOICES).get(step, step)
        return 'Complete'
