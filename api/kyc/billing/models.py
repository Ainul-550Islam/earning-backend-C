# kyc/billing/models.py  ── WORLD #1
"""
Billing & Pricing Module.
SaaS-এর জন্য essential — Jumio/Sumsub সবাই per-verification charge করে।
Models: Plan, Subscription, UsageRecord, Invoice, APIKey.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class KYCPlan(models.Model):
    """Subscription plans for KYC SaaS."""
    PLAN_TYPE = [
        ('starter',    'Starter'),
        ('growth',     'Growth'),
        ('business',   'Business'),
        ('enterprise', 'Enterprise'),
        ('pay_as_you_go', 'Pay As You Go'),
    ]
    name               = models.CharField(max_length=100, null=True, blank=True)
    plan_type          = models.CharField(max_length=20, choices=PLAN_TYPE, unique=True, null=True, blank=True)
    description        = models.TextField(blank=True)
    is_active          = models.BooleanField(default=True)

    # Pricing
    monthly_price_bdt  = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    monthly_price_usd  = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    per_kyc_price_bdt  = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Per KYC verification", null=True, blank=True)
    per_aml_price_bdt  = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Per AML screening", null=True, blank=True)
    per_video_kyc_bdt  = models.DecimalField(max_digits=8, decimal_places=2, default=0, null=True, blank=True)

    # Limits
    monthly_kyc_limit     = models.IntegerField(default=0, help_text="0 = unlimited")
    monthly_aml_limit     = models.IntegerField(default=0)
    max_tenants           = models.IntegerField(default=1)
    api_rate_limit        = models.IntegerField(default=100, help_text="Requests per minute")
    data_retention_days   = models.IntegerField(default=365)

    # Features
    features              = models.JSONField(default=list, blank=True, help_text="List of included features")
    kyb_enabled           = models.BooleanField(default=False)
    video_kyc_enabled     = models.BooleanField(default=False)
    aml_enabled           = models.BooleanField(default=False)
    perpetual_kyc_enabled = models.BooleanField(default=False)
    behavioral_enabled    = models.BooleanField(default=False)
    custom_branding       = models.BooleanField(default=False)
    dedicated_support     = models.BooleanField(default=False)
    sla_hours             = models.IntegerField(default=72, help_text="Response SLA in hours")

    sort_order   = models.IntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_plans'
        verbose_name = 'KYC Plan'
        ordering = ['sort_order', 'monthly_price_bdt']

    def __str__(self):
        return f"{self.name} (৳{self.monthly_price_bdt}/mo)"


class KYCSubscription(models.Model):
    """Tenant subscription to a KYC plan."""
    STATUS = [
        ('trial',     'Free Trial'),
        ('active',    'Active'),
        ('past_due',  'Past Due'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
        ('expired',   'Expired'),
    ]
    tenant           = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='kyc_subscription', null=True, blank=True)
    plan             = models.ForeignKey(KYCPlan, on_delete=models.PROTECT, related_name='subscriptions', null=True, blank=True)
    status           = models.CharField(max_length=15, choices=STATUS, default='trial', db_index=True, null=True, blank=True)

    # Billing cycle
    billing_cycle_start = models.DateField()
    billing_cycle_end   = models.DateField()
    next_billing_date   = models.DateField(null=True, blank=True, db_index=True)

    # Trial
    trial_ends_at    = models.DateTimeField(null=True, blank=True)
    is_trial         = models.BooleanField(default=True)

    # Custom overrides
    custom_kyc_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Override plan price")
    custom_limit     = models.IntegerField(null=True, blank=True)
    discount_pct     = models.IntegerField(default=0, help_text="Discount percentage")

    # Billing contact
    billing_email    = models.EmailField(blank=True)
    billing_name     = models.CharField(max_length=200, null=True, blank=True)
    billing_address  = models.TextField(blank=True)

    auto_renew       = models.BooleanField(default=True)
    cancelled_at     = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_subscriptions'
        verbose_name = 'KYC Subscription'

    def __str__(self):
        return f"Sub[{self.plan.name}:{self.status}] {self.tenant}"

    @property
    def is_active(self):
        return self.status in ('trial', 'active')

    @property
    def days_until_renewal(self):
        if not self.next_billing_date: return None
        return (self.next_billing_date - timezone.now().date()).days

    def cancel(self, reason=''):
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.auto_renew = False
        self.save()


class KYCUsageRecord(models.Model):
    """Per-verification usage tracking for billing."""
    USAGE_TYPE = [
        ('kyc_verification',    'KYC Verification'),
        ('aml_screening',       'AML/PEP Screening'),
        ('face_match',          'Face Match'),
        ('liveness_check',      'Liveness Check'),
        ('ocr_extraction',      'OCR Extraction'),
        ('video_kyc',           'Video KYC Session'),
        ('kyb_verification',    'KYB Verification'),
        ('batch_verification',  'Batch Verification'),
        ('api_call',            'API Call'),
    ]
    tenant           = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, db_index=True)
    subscription     = models.ForeignKey(KYCSubscription, on_delete=models.SET_NULL, null=True, blank=True)
    usage_type       = models.CharField(max_length=25, choices=USAGE_TYPE, db_index=True, null=True, blank=True)
    unit_price_bdt   = models.DecimalField(max_digits=8, decimal_places=4, default=0, null=True, blank=True)
    quantity         = models.IntegerField(default=1)
    total_bdt        = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    kyc_id           = models.IntegerField(null=True, blank=True)
    user_id          = models.IntegerField(null=True, blank=True)
    metadata         = models.JSONField(default=dict, blank=True)
    billed           = models.BooleanField(default=False, db_index=True)
    invoice_id       = models.IntegerField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'kyc_usage_records'
        verbose_name = 'Usage Record'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'usage_type', 'created_at']),
            models.Index(fields=['tenant', 'billed']),
        ]

    def __str__(self):
        return f"Usage[{self.usage_type}] ৳{self.total_bdt} - {self.created_at.date()}"

    def save(self, *args, **kwargs):
        self.total_bdt = self.unit_price_bdt * self.quantity
        super().save(*args, **kwargs)


class KYCInvoice(models.Model):
    """Monthly invoices for KYC SaaS billing."""
    STATUS = [
        ('draft',    'Draft'),
        ('sent',     'Sent'),
        ('paid',     'Paid'),
        ('overdue',  'Overdue'),
        ('cancelled','Cancelled'),
    ]
    invoice_number    = models.CharField(max_length=30, unique=True, null=True, blank=True)
    tenant            = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='kyc_invoices', null=True, blank=True)
    subscription      = models.ForeignKey(KYCSubscription, on_delete=models.SET_NULL, null=True)
    status            = models.CharField(max_length=15, choices=STATUS, default='draft', db_index=True, null=True, blank=True)

    # Period
    period_start      = models.DateField()
    period_end        = models.DateField()

    # Amounts
    subtotal_bdt      = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    discount_bdt      = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    vat_bdt           = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="15% VAT", null=True, blank=True)
    total_bdt         = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)

    # Line items
    line_items        = models.JSONField(default=list, blank=True)

    # Dates
    issued_at         = models.DateTimeField(null=True, blank=True)
    due_date          = models.DateField(null=True, blank=True)
    paid_at           = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, null=True, blank=True)
    payment_method    = models.CharField(max_length=50, null=True, blank=True)

    notes             = models.TextField(blank=True)
    pdf_file          = models.FileField(upload_to='kyc/invoices/', null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_invoices'
        verbose_name = 'Invoice'
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice#{self.invoice_number} ৳{self.total_bdt} [{self.status}]"

    def calculate_total(self):
        """Calculate VAT and total."""
        self.vat_bdt   = round(self.subtotal_bdt * 15 / 100, 2)
        self.total_bdt = self.subtotal_bdt - self.discount_bdt + self.vat_bdt
        return self.total_bdt

    def mark_paid(self, reference='', method=''):
        self.status            = 'paid'
        self.paid_at           = timezone.now()
        self.payment_reference = reference
        self.payment_method    = method
        self.save()

    @classmethod
    def generate_number(cls):
        """Generate unique invoice number: KYC-2025-0001"""
        year  = timezone.now().year
        count = cls.objects.filter(created_at__year=year).count() + 1
        return f"KYC-{year}-{count:04d}"


class APIKey(models.Model):
    """API keys for programmatic access."""
    KEY_TYPE = [
        ('test',       'Test Key (Sandbox)'),
        ('live',       'Live Key (Production)'),
        ('restricted', 'Restricted Key (Read-only)'),
    ]
    tenant       = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='kyc_api_keys', null=True, blank=True)
    name         = models.CharField(max_length=100, null=True, blank=True)
    key_type     = models.CharField(max_length=15, choices=KEY_TYPE, default='test', null=True, blank=True)
    key_prefix   = models.CharField(max_length=10, db_index=True, null=True, blank=True)
    key_hash     = models.CharField(max_length=128, help_text="SHA-256 of the actual key", null=True, blank=True)
    is_active    = models.BooleanField(default=True, db_index=True)
    permissions  = models.JSONField(default=list, blank=True, help_text="Allowed scopes")
    ip_whitelist = models.JSONField(default=list, blank=True, help_text="Allowed IPs (empty = all)")
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    revoked_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kyc_api_keys'
        verbose_name = 'API Key'
        ordering = ['-created_at']

    def __str__(self):
        return f"APIKey[{self.key_type}:{self.key_prefix}...] {self.tenant}"

    @property
    def is_valid(self):
        if not self.is_active: return False
        if self.expires_at and timezone.now() > self.expires_at: return False
        return True

    @classmethod
    def generate(cls, tenant, name: str, key_type: str = 'test', created_by=None) -> tuple:
        """
        Generate a new API key.
        Returns (APIKey instance, raw_key string).
        Raw key is shown ONCE — hash is stored.
        """
        import secrets, hashlib
        prefix  = 'kyc_test_' if key_type == 'test' else 'kyc_live_'
        raw_key = prefix + secrets.token_hex(24)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        instance = cls.objects.create(
            tenant=tenant, name=name, key_type=key_type,
            key_prefix=raw_key[:12],
            key_hash=key_hash,
            created_by=created_by,
        )
        return instance, raw_key   # raw_key shown only once
