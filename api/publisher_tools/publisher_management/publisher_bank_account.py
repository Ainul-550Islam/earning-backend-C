# api/publisher_tools/publisher_management/publisher_bank_account.py
"""
Publisher Bank Account — সম্পূর্ণ payment method management।
Bank account, mobile banking, crypto wallet সব support করে।
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class PublisherBankAccount(TimeStampedModel):
    """
    Publisher-এর bank account ও payment method।
    bKash, Nagad, Rocket, Bank Transfer, Payoneer সব support।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherbankaccount_tenant', db_index=True,
    )

    ACCOUNT_TYPE_CHOICES = [
        # Bangladesh Mobile Banking
        ('bkash',           _('বিকাশ (bKash)')),
        ('nagad',           _('নগদ (Nagad)')),
        ('rocket',          _('রকেট (Rocket)')),
        ('upay',            _('UpAy')),
        ('mcash',           _('mCash')),
        ('tap',             _('Tap')),
        # International
        ('paypal',          _('PayPal')),
        ('payoneer',        _('Payoneer')),
        ('wise',            _('Wise (TransferWise)')),
        ('skrill',          _('Skrill')),
        # Bank Transfer
        ('bank_bd',         _('Bangladesh Bank Account')),
        ('bank_international', _('International Bank (SWIFT)')),
        # Crypto
        ('bitcoin',         _('Bitcoin (BTC)')),
        ('ethereum',        _('Ethereum (ETH)')),
        ('usdt_trc20',      _('USDT (TRC-20)')),
        ('usdt_erc20',      _('USDT (ERC-20)')),
        ('usdc',            _('USD Coin (USDC)')),
        ('bnb',             _('BNB (Binance)')),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('unverified',  _('Unverified')),
        ('pending',     _('Verification Pending')),
        ('verified',    _('Verified')),
        ('failed',      _('Verification Failed')),
        ('suspended',   _('Suspended')),
    ]

    CURRENCY_CHOICES = [
        ('BDT', _('Bangladeshi Taka (৳)')),
        ('USD', _('US Dollar ($)')),
        ('EUR', _('Euro (€)')),
        ('GBP', _('British Pound (£)')),
        ('INR', _('Indian Rupee (₹)')),
        ('USDT', _('Tether (USDT)')),
        ('BTC',  _('Bitcoin (BTC)')),
        ('ETH',  _('Ethereum (ETH)')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name=_("Publisher"),
    )
    account_type = models.CharField(
        max_length=30,
        choices=ACCOUNT_TYPE_CHOICES,
        verbose_name=_("Account Type"),
        db_index=True,
    )
    account_label = models.CharField(
        max_length=100,
        verbose_name=_("Account Label"),
        help_text=_("e.g., 'My bKash', 'Business Account'"),
    )
    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default='BDT',
        verbose_name=_("Currency"),
        db_index=True,
    )

    # ── Account Details (encrypted in production) ─────────────────────────────
    account_number = models.CharField(
        max_length=255,
        verbose_name=_("Account Number / Wallet Address / Email"),
        help_text=_("bKash/Nagad: phone number | Bank: account number | PayPal: email | Crypto: wallet address"),
    )
    account_holder_name = models.CharField(
        max_length=300,
        verbose_name=_("Account Holder Name"),
        help_text=_("Account-এ যে নাম রেজিস্টার করা আছে"),
    )

    # ── Bank-Specific Fields ──────────────────────────────────────────────────
    bank_name = models.CharField(max_length=200, blank=True, verbose_name=_("Bank Name"))
    bank_branch = models.CharField(max_length=200, blank=True, verbose_name=_("Branch Name"))
    routing_number = models.CharField(max_length=50, blank=True, verbose_name=_("Routing Number"))
    swift_code = models.CharField(max_length=20, blank=True, verbose_name=_("SWIFT / BIC Code"))
    iban = models.CharField(max_length=50, blank=True, verbose_name=_("IBAN"))
    bank_address = models.TextField(blank=True, verbose_name=_("Bank Address"))
    bank_country = models.CharField(max_length=100, blank=True, verbose_name=_("Bank Country"))

    # ── Mobile Banking Specific ───────────────────────────────────────────────
    mobile_number = models.CharField(
        max_length=20, blank=True,
        verbose_name=_("Mobile Number (for Mobile Banking)"),
    )
    mobile_account_type = models.CharField(
        max_length=20, blank=True,
        choices=[('personal', _('Personal')), ('agent', _('Agent')), ('merchant', _('Merchant'))],
        verbose_name=_("Mobile Account Type"),
    )

    # ── Crypto Specific ───────────────────────────────────────────────────────
    crypto_network = models.CharField(
        max_length=50, blank=True,
        verbose_name=_("Crypto Network"),
        help_text=_("e.g., TRC-20, ERC-20, BEP-20"),
    )
    crypto_wallet_address = models.CharField(
        max_length=255, blank=True,
        verbose_name=_("Crypto Wallet Address"),
    )
    crypto_memo_tag = models.CharField(
        max_length=50, blank=True,
        verbose_name=_("Memo / Tag (for XRP, XLM, etc.)"),
    )

    # ── PayPal / Payoneer Specific ────────────────────────────────────────────
    paypal_email = models.EmailField(blank=True, verbose_name=_("PayPal Email"))
    payoneer_id  = models.CharField(max_length=100, blank=True, verbose_name=_("Payoneer Customer ID"))
    wise_email   = models.EmailField(blank=True, verbose_name=_("Wise Email"))

    # ── Status & Verification ─────────────────────────────────────────────────
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='unverified',
        verbose_name=_("Verification Status"),
        db_index=True,
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Primary Account"),
        help_text=_("Payout default এই account-এ যাবে"),
        db_index=True,
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        db_index=True,
    )

    # ── Verification Details ──────────────────────────────────────────────────
    verification_code = models.CharField(max_length=20, blank=True, verbose_name=_("Verification Code"))
    verification_amount = models.DecimalField(
        max_digits=10, decimal_places=4,
        null=True, blank=True,
        verbose_name=_("Micro-deposit Amount"),
        help_text=_("Bank verification-এর জন্য ছোট amount পাঠানো হয়"),
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Verified At"))
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_bankaccount_verified_by',
        verbose_name=_("Verified By (Admin)"),
    )
    verification_notes = models.TextField(blank=True, verbose_name=_("Verification Notes"))

    # ── Payment History ───────────────────────────────────────────────────────
    total_received = models.DecimalField(
        max_digits=14, decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Received (USD)"),
    )
    last_payment_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Payment At"))
    payment_count = models.IntegerField(default=0, verbose_name=_("Total Payments Received"))

    # ── Minimum Payout ────────────────────────────────────────────────────────
    minimum_payout_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        verbose_name=_("Minimum Payout Amount (USD)"),
    )
    payout_frequency = models.CharField(
        max_length=20,
        choices=[
            ('monthly', _('Monthly (Net 30)')),
            ('bimonthly', _('Bi-Monthly (Net 15)')),
            ('weekly', _('Weekly')),
            ('on_demand', _('On Demand')),
        ],
        default='monthly',
        verbose_name=_("Preferred Payout Frequency"),
    )

    # ── Processing Fees ───────────────────────────────────────────────────────
    processing_fee_flat = models.DecimalField(
        max_digits=8, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Processing Fee (Flat USD)"),
    )
    processing_fee_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name=_("Processing Fee (%)"),
    )
    withholding_tax_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        verbose_name=_("Withholding Tax (%)"),
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_bank_accounts'
        verbose_name = _('Publisher Bank Account')
        verbose_name_plural = _('Publisher Bank Accounts')
        ordering = ['-is_primary', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'is_primary']),
            models.Index(fields=['account_type']),
            models.Index(fields=['verification_status']),
            models.Index(fields=['currency']),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.account_type} ({self.account_label})"

    @property
    def is_verified(self):
        return self.verification_status == 'verified'

    @property
    def masked_account_number(self):
        """Account number mask করে show করে"""
        num = self.account_number
        if len(num) <= 8:
            return '*' * len(num)
        return num[:4] + '*' * (len(num) - 8) + num[-4:]

    @property
    def display_info(self):
        """User-friendly display string"""
        if self.account_type in ('bkash', 'nagad', 'rocket', 'upay'):
            return f"{self.get_account_type_display()} — {self.masked_account_number}"
        elif self.account_type == 'paypal':
            return f"PayPal — {self.paypal_email}"
        elif self.account_type in ('bank_bd', 'bank_international'):
            return f"{self.bank_name} — {self.masked_account_number}"
        elif self.account_type in ('bitcoin', 'ethereum', 'usdt_trc20', 'usdt_erc20'):
            addr = self.crypto_wallet_address
            return f"{self.get_account_type_display()} — {addr[:6]}...{addr[-4:]}" if addr else self.get_account_type_display()
        return self.account_label

    def set_as_primary(self):
        """এই account-কে primary করে, অন্যগুলো non-primary করে"""
        PublisherBankAccount.objects.filter(
            publisher=self.publisher
        ).update(is_primary=False)
        self.is_primary = True
        self.save(update_fields=['is_primary', 'updated_at'])

    def verify(self, verified_by=None, notes: str = ''):
        """Account verify করে"""
        self.verification_status = 'verified'
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.verification_notes = notes
        self.save()

    def send_verification_code(self):
        """Verification code generate করে পাঠায়"""
        import random
        import string
        code = ''.join(random.choices(string.digits, k=6))
        self.verification_code = code
        self.verification_status = 'pending'
        self.save(update_fields=['verification_code', 'verification_status', 'updated_at'])
        # production: SMS বা email-এ code পাঠাও
        return code

    def confirm_verification_code(self, code: str) -> bool:
        """User-এর দেওয়া code verify করে"""
        if self.verification_code == code:
            self.verification_status = 'verified'
            self.verified_at = timezone.now()
            self.verification_code = ''
            self.save()
            return True
        return False

    def calculate_net_payout(self, gross_amount: Decimal) -> dict:
        """Net payout calculate করে সব fees কাটার পর"""
        fee_flat = self.processing_fee_flat
        fee_pct  = gross_amount * (self.processing_fee_pct / 100)
        tax      = gross_amount * (self.withholding_tax_pct / 100)
        total_deduction = fee_flat + fee_pct + tax
        net_amount = max(Decimal('0'), gross_amount - total_deduction)

        return {
            'gross_amount':      float(gross_amount),
            'processing_fee':    float(fee_flat + fee_pct),
            'withholding_tax':   float(tax),
            'total_deductions':  float(total_deduction),
            'net_amount':        float(net_amount),
            'currency':          self.currency,
        }

    def record_payment(self, amount: Decimal):
        """Payment received record করে"""
        self.total_received += amount
        self.payment_count  += 1
        self.last_payment_at = timezone.now()
        self.save(update_fields=['total_received', 'payment_count', 'last_payment_at', 'updated_at'])
