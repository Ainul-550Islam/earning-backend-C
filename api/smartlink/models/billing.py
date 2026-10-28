"""
SmartLink Billing Models
Covers the 4 missing business-critical models:
  1. PublisherProfile    — contact info, payment details, GDPR consent
  2. PublisherAPIKey     — database-backed API key (auth.py referenced this but the model didn't exist)
  3. PublisherWallet     — running earnings balance per publisher
  4. PayoutRecord        — individual payout transactions (calculated → pending → paid)
  5. PayoutBatch         — admin-initiated payment run grouping multiple PayoutRecords
"""
import uuid
import hashlib
import secrets
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class PublisherProfile(models.Model):
    """
    Extended publisher profile.
    Stores payment method details, contact info, tax data, and GDPR consent.
    One-to-one with User. Created automatically via post_save signal.
    """

    class PaymentMethod(models.TextChoices):
        PAYPAL    = 'paypal',  _('PayPal')
        WISE      = 'wise',    _('Wise (TransferWise)')
        BANK_WIRE = 'wire',    _('Bank Wire Transfer')
        CRYPTO    = 'crypto',  _('Cryptocurrency')
        PAYONEER  = 'payoneer',_('Payoneer')

    publisher = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='smartlink_publisher_profile',
        verbose_name=_('Publisher'),
    )

    # Contact
    company_name     = models.CharField(_('Company name'), max_length=200, blank=True)
    phone            = models.CharField(_('Phone'), max_length=30, blank=True)
    country_code     = models.CharField(_('Country'), max_length=2, blank=True)
    timezone         = models.CharField(_('Timezone'), max_length=50, default='UTC')
    website          = models.URLField(_('Website'), blank=True)
    traffic_sources  = models.JSONField(
        _('Primary traffic sources'), default=list, blank=True,
        help_text=_('e.g. ["social","push","email","seo"]')
    )
    vertical         = models.CharField(
        _('Vertical'), max_length=100, blank=True,
        help_text=_('Primary vertical: finance, gaming, health, dating, etc.')
    )

    # Payment
    payment_method      = models.CharField(
        _('Payment method'), max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.PAYPAL,
    )
    payment_email       = models.EmailField(_('Payment email (PayPal/Wise/Payoneer)'), blank=True)
    bank_name           = models.CharField(_('Bank name'), max_length=200, blank=True)
    bank_account_number = models.CharField(_('Bank account number'), max_length=100, blank=True)
    bank_routing_number = models.CharField(_('Routing/SWIFT/IBAN'), max_length=50, blank=True)
    crypto_address      = models.CharField(_('Crypto wallet address'), max_length=200, blank=True)
    crypto_currency     = models.CharField(_('Crypto currency'), max_length=10, blank=True, default='USDT')
    min_payout          = models.DecimalField(
        _('Minimum payout threshold'), max_digits=10, decimal_places=2, default=50,
        help_text=_('Payout only when earnings exceed this amount.')
    )
    payout_currency     = models.CharField(_('Payout currency'), max_length=3, default='USD')

    # Attribution — per-publisher override
    attribution_window_days = models.PositiveSmallIntegerField(
        _('Attribution window (days)'),
        null=True,
        blank=True,
        help_text=_(
            'Per-publisher attribution lookback window in days. '
            'Leave blank to inherit the global SMARTLINK_ATTRIBUTION_WINDOW_HOURS setting. '
            'e.g. 1 = 24 h, 7 = 7 days, 30 = 30 days.'
        ),
    )

    # Tax / compliance
    tax_id              = models.CharField(_('Tax ID / VAT number'), max_length=50, blank=True)
    w9_submitted        = models.BooleanField(_('W9 submitted (US only)'), default=False)
    is_company          = models.BooleanField(_('Is a company'), default=False)

    # GDPR / privacy
    gdpr_consent        = models.BooleanField(_('GDPR consent given'), default=False)
    gdpr_consent_at     = models.DateTimeField(_('GDPR consent timestamp'), null=True, blank=True)
    marketing_opt_in    = models.BooleanField(_('Marketing opt-in'), default=True)
    data_anonymized     = models.BooleanField(_('Data anonymized (GDPR erasure)'), default=False)
    anonymized_at       = models.DateTimeField(null=True, blank=True)

    # Notification preferences (mirrors NotificationPreferenceSerializer)
    notification_preferences = models.JSONField(default=dict, blank=True)

    # Meta
    notes               = models.TextField(_('Internal notes (admin only)'), blank=True)
    is_verified         = models.BooleanField(_('KYC verified'), default=False)
    verified_at         = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_publisher_profile'
        verbose_name = _('Publisher Profile')

    def __str__(self):
        return f"Profile: {self.publisher.username}"

    def anonymize(self):
        """
        GDPR right-to-erasure: replace all PII with anonymized placeholders.
        Preserves aggregated analytics — only removes identifying data.
        """
        from django.utils import timezone
        self.company_name     = '[ANONYMIZED]'
        self.phone            = ''
        self.payment_email    = ''
        self.bank_account_number = ''
        self.bank_routing_number = ''
        self.crypto_address   = ''
        self.tax_id           = ''
        self.data_anonymized  = True
        self.anonymized_at    = timezone.now()
        self.save()


class PublisherAPIKey(models.Model):
    """
    Database-backed API key for publisher integrations.
    Previously referenced in api/authentication.py but the model didn't exist.
    Key is stored as SHA-256 hash — never in plaintext after creation.
    """

    class Scope(models.TextChoices):
        READ_ONLY  = 'read',  _('Read only')
        READ_WRITE = 'write', _('Read + write')
        FULL       = 'full',  _('Full access (create/delete)')

    publisher   = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='smartlink_api_keys',
    )
    name        = models.CharField(
        _('Key name'), max_length=100,
        help_text=_('e.g. "Postback integration", "Dashboard app"')
    )
    key_prefix  = models.CharField(max_length=8, db_index=True)
    key_hash    = models.CharField(max_length=64, unique=True)
    scope       = models.CharField(max_length=10, choices=Scope.choices, default=Scope.READ_WRITE)
    is_active   = models.BooleanField(default=True)
    allowed_ips = models.JSONField(
        default=list, blank=True,
        help_text=_('Whitelist IPs. Empty = allow all.')
    )
    last_used_at  = models.DateTimeField(null=True, blank=True)
    expires_at    = models.DateTimeField(null=True, blank=True)
    request_count = models.PositiveBigIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sl_publisher_api_key'
        verbose_name = _('Publisher API Key')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.publisher.username} / {self.name} ({self.key_prefix}…)"

    @classmethod
    def generate(cls, publisher, name: str, scope: str = 'write',
                 allowed_ips=None, expires_at=None) -> tuple:
        """
        Create a new API key. Returns (key_object, raw_key).
        raw_key is shown ONCE — it cannot be recovered after this call.
        """
        raw_key    = f"sl_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:8]
        key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()
        obj = cls.objects.create(
            publisher=publisher,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scope=scope,
            allowed_ips=allowed_ips or [],
            expires_at=expires_at,
        )
        return obj, raw_key

    def verify(self, raw_key: str) -> bool:
        """Check a submitted raw key against the stored hash."""
        return hashlib.sha256(raw_key.encode()).hexdigest() == self.key_hash

    def is_valid(self, ip: str = '') -> bool:
        """Check active + not expired + IP whitelist."""
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.allowed_ips and ip and ip not in self.allowed_ips:
            return False
        return True


class PublisherWallet(models.Model):
    """
    Running earnings balance per publisher.
    Updated on every attributed conversion. Decremented on payout.
    One-to-one with User.
    """
    publisher        = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='wallet',
    )
    balance_usd      = models.DecimalField(
        _('Available balance (USD)'), max_digits=14, decimal_places=4, default=0,
    )
    pending_usd      = models.DecimalField(
        _('Pending balance (hold period, USD)'), max_digits=14, decimal_places=4, default=0,
    )
    lifetime_earned  = models.DecimalField(
        _('Lifetime earnings (USD)'), max_digits=14, decimal_places=4, default=0,
    )
    lifetime_paid    = models.DecimalField(
        _('Lifetime paid out (USD)'), max_digits=14, decimal_places=4, default=0,
    )
    last_credit_at   = models.DateTimeField(null=True, blank=True)
    last_payout_at   = models.DateTimeField(null=True, blank=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_publisher_wallet'
        verbose_name = _('Publisher Wallet')

    def __str__(self):
        return f"{self.publisher.username}: ${self.balance_usd}"

    def credit(self, amount_usd: float, hold_days: int = 0):
        """
        Credit an earned amount. Amounts in hold go to pending_usd.
        Use F() expressions to avoid race conditions.
        """
        from django.db.models import F
        from django.utils import timezone
        from decimal import Decimal
        amount = Decimal(str(amount_usd))
        if hold_days > 0:
            PublisherWallet.objects.filter(pk=self.pk).update(
                pending_usd=F('pending_usd') + amount,
                lifetime_earned=F('lifetime_earned') + amount,
                last_credit_at=timezone.now(),
            )
        else:
            PublisherWallet.objects.filter(pk=self.pk).update(
                balance_usd=F('balance_usd') + amount,
                lifetime_earned=F('lifetime_earned') + amount,
                last_credit_at=timezone.now(),
            )

    def debit(self, amount_usd: float) -> bool:
        """
        Debit a payout amount from balance. Returns False if insufficient.
        Uses select_for_update to prevent double-debit race conditions.
        """
        from decimal import Decimal
        from django.db.models import F
        from django.utils import timezone
        amount = Decimal(str(amount_usd))
        updated = PublisherWallet.objects.filter(
            pk=self.pk, balance_usd__gte=amount
        ).update(
            balance_usd=F('balance_usd') - amount,
            lifetime_paid=F('lifetime_paid') + amount,
            last_payout_at=timezone.now(),
        )
        return updated == 1


class PayoutRecord(models.Model):
    """
    Individual payout transaction record.
    Lifecycle: calculated → approved → processing → paid | rejected | failed
    """

    class Status(models.TextChoices):
        CALCULATED  = 'calculated',  _('Calculated')
        APPROVED    = 'approved',    _('Approved')
        PROCESSING  = 'processing',  _('Processing')
        PAID        = 'paid',        _('Paid')
        REJECTED    = 'rejected',    _('Rejected')
        FAILED      = 'failed',      _('Failed')
        ON_HOLD     = 'on_hold',     _('On Hold')

    class PaymentMethod(models.TextChoices):
        PAYPAL   = 'paypal',  _('PayPal')
        WISE     = 'wise',    _('Wise')
        WIRE     = 'wire',    _('Wire Transfer')
        CRYPTO   = 'crypto',  _('Crypto')
        PAYONEER = 'payoneer',_('Payoneer')

    batch           = models.ForeignKey(
        'PayoutBatch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='records',
    )
    publisher       = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='payout_records',
    )
    reference_id    = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    period_from     = models.DateField(_('Period start'))
    period_to       = models.DateField(_('Period end'))

    # Amounts
    gross_amount    = models.DecimalField(_('Gross amount (USD)'), max_digits=14, decimal_places=4)
    scrub_amount    = models.DecimalField(_('Scrubbed / deducted (USD)'), max_digits=14, decimal_places=4, default=0)
    net_amount      = models.DecimalField(_('Net payout (USD)'), max_digits=14, decimal_places=4)
    currency        = models.CharField(_('Payout currency'), max_length=3, default='USD')
    fx_rate         = models.DecimalField(_('FX rate to USD'), max_digits=10, decimal_places=6, default=1)
    local_amount    = models.DecimalField(_('Amount in payout currency'), max_digits=14, decimal_places=4, default=0)

    # Quality stats at time of calculation
    total_clicks    = models.PositiveBigIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    fraud_rate      = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    scrub_rate      = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    scrub_reason    = models.TextField(blank=True)

    # Payment details
    status          = models.CharField(max_length=15, choices=Status.choices, default=Status.CALCULATED, db_index=True)
    payment_method  = models.CharField(max_length=15, choices=PaymentMethod.choices)
    payment_address = models.CharField(max_length=200, blank=True)
    transaction_ref = models.CharField(_('External transaction reference'), max_length=200, blank=True)
    paid_at         = models.DateTimeField(null=True, blank=True)
    failure_reason  = models.TextField(blank=True)

    # Audit
    calculated_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='calculated_payouts',
    )
    approved_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_payouts',
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'sl_payout_record'
        verbose_name = _('Payout Record')
        ordering     = ['-created_at']
        indexes      = [
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['period_from', 'period_to']),
        ]

    def __str__(self):
        return f"Payout #{self.reference_id.hex[:8]} — {self.publisher.username} ${self.net_amount} [{self.status}]"

    def approve(self, admin_user):
        from django.utils import timezone
        PayoutRecord.objects.filter(pk=self.pk, status=self.Status.CALCULATED).update(
            status=self.Status.APPROVED,
            approved_by=admin_user,
        )

    def mark_paid(self, transaction_ref: str = ''):
        from django.utils import timezone
        PayoutRecord.objects.filter(pk=self.pk).update(
            status=self.Status.PAID,
            transaction_ref=transaction_ref,
            paid_at=timezone.now(),
        )
        # Debit wallet
        try:
            self.publisher.wallet.debit(float(self.net_amount))
        except Exception:
            pass

    def mark_failed(self, reason: str = ''):
        PayoutRecord.objects.filter(pk=self.pk).update(
            status=self.Status.FAILED,
            failure_reason=reason,
        )


class PayoutBatch(models.Model):
    """
    A batch payment run grouping multiple payout records.
    Admin initiates a batch, system calculates all eligible publishers,
    then marks them paid after external payment is confirmed.
    """
    reference_id  = models.UUIDField(default=uuid.uuid4, unique=True)
    label         = models.CharField(max_length=200, help_text=_('e.g. "March 2024 Payout"'))
    period_from   = models.DateField()
    period_to     = models.DateField()
    total_records = models.PositiveIntegerField(default=0)
    total_amount  = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    status        = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('calculating', 'Calculating'),
            ('review', 'Under Review'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
    )
    created_by    = models.ForeignKey(User, on_delete=models.PROTECT, related_name='smartlink_payout_batches')
    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    completed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'sl_payout_batch'
        verbose_name = _('Payout Batch')
        ordering     = ['-created_at']

    def __str__(self):
        return f"Batch: {self.label} — ${self.total_amount} ({self.status})"
