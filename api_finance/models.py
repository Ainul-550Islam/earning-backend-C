# api_finance/models.py
"""
Finance app models — financial ledger, wallets, payouts, and reconciliation.

FIX (audit): The original model had only one field (amount=0).
This expands it into a production-ready financial ledger with:
  - Transaction       — double-entry style ledger record
  - Wallet            — per-user balance store
  - PayoutRequest     — formal payout requests (USD)
  - ReconciliationLog — daily reconciliation audit records

The existing Transaction.amount field is preserved — all new fields are additive.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Wallet(models.Model):
    """
    Per-user wallet.  One wallet per user; created automatically on first
    credit via a post_save signal in apps.py.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.OneToOneField(User, on_delete=models.CASCADE,
                                       related_name='finance_wallet')
    balance_usd = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    balance_virtual = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_earned_usd = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_paid_usd   = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    is_locked   = models.BooleanField(default=False,
                                      help_text='Locked wallets cannot withdraw')
    locked_reason = models.CharField(max_length=255, blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'api_finance'

    def __str__(self):
        return f"Wallet({self.user_id}) ${self.balance_usd}"

    @property
    def available_balance(self):
        return self.balance_usd


class Transaction(models.Model):
    """
    Double-entry financial transaction record.

    Original field (amount) is preserved.
    New fields added for full financial tracking.
    """
    TYPE_CREDIT   = 'credit'
    TYPE_DEBIT    = 'debit'
    TYPE_HOLD     = 'hold'
    TYPE_RELEASE  = 'release'
    TYPE_REVERSAL = 'reversal'
    TYPE_CHOICES = [
        (TYPE_CREDIT,   'Credit'),
        (TYPE_DEBIT,    'Debit'),
        (TYPE_HOLD,     'Hold'),
        (TYPE_RELEASE,  'Release'),
        (TYPE_REVERSAL, 'Reversal'),
    ]

    SOURCE_OFFER      = 'offer_completion'
    SOURCE_SURVEY     = 'survey_completion'
    SOURCE_BONUS      = 'bonus'
    SOURCE_REFERRAL   = 'referral'
    SOURCE_WITHDRAWAL = 'withdrawal'
    SOURCE_ADMIN      = 'admin_adjustment'
    SOURCE_REFUND     = 'refund'
    SOURCE_CHOICES = [
        (SOURCE_OFFER,      'Offer Completion'),
        (SOURCE_SURVEY,     'Survey Completion'),
        (SOURCE_BONUS,      'Bonus'),
        (SOURCE_REFERRAL,   'Referral'),
        (SOURCE_WITHDRAWAL, 'Withdrawal'),
        (SOURCE_ADMIN,      'Admin Adjustment'),
        (SOURCE_REFUND,     'Refund'),
    ]

    STATUS_PENDING   = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED    = 'failed'
    STATUS_REVERSED  = 'reversed'
    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED,    'Failed'),
        (STATUS_REVERSED,  'Reversed'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet          = models.ForeignKey(Wallet, on_delete=models.CASCADE,
                                        related_name='transactions', null=True, blank=True)
    user            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                        related_name='finance_transactions')
    reference_id    = models.CharField(max_length=255, blank=True, db_index=True,
                                       help_text='Lead ID, payout ID, etc.')

    # ── Amounts — original field preserved ───────────────────────────────────
    amount          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_usd      = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                          help_text='Canonical USD amount')
    amount_virtual  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency        = models.CharField(max_length=5, default='USD')
    fee_usd         = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    net_usd         = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    # ── Type / Classification ─────────────────────────────────────────────────
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES,
                                        default=TYPE_CREDIT, db_index=True)
    source          = models.CharField(max_length=30, choices=SOURCE_CHOICES,
                                       default=SOURCE_OFFER, db_index=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                       default=STATUS_PENDING, db_index=True)

    # ── Balance snapshot ──────────────────────────────────────────────────────
    balance_before  = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    balance_after   = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # ── Metadata ──────────────────────────────────────────────────────────────
    description     = models.CharField(max_length=500, blank=True, default='')
    metadata        = models.JSONField(default=dict, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at      = models.DateTimeField(auto_now_add=True)
    completed_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'api_finance'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status', 'transaction_type']),
            models.Index(fields=['source', 'status']),
            models.Index(fields=['reference_id']),
        ]

    def __str__(self):
        return f"TX {self.id} {self.transaction_type} ${self.amount_usd}"

    def save(self, *args, **kwargs):
        # Auto-sync amount_usd ↔ amount for backwards compatibility
        if self.amount and not self.amount_usd:
            self.amount_usd = self.amount
        elif self.amount_usd and not self.amount:
            self.amount = self.amount_usd
        # Auto-compute net
        if not self.net_usd:
            self.net_usd = self.amount_usd - self.fee_usd
        super().save(*args, **kwargs)


class PayoutRequest(models.Model):
    """Formal payout request — created when user requests USD withdrawal."""
    METHOD_PAYPAL   = 'paypal'
    METHOD_STRIPE   = 'stripe'
    METHOD_BKASH    = 'bkash'
    METHOD_NAGAD    = 'nagad'
    METHOD_CRYPTO   = 'crypto'
    METHOD_BANK     = 'bank_transfer'
    METHOD_CHOICES = [
        (METHOD_PAYPAL, 'PayPal'),
        (METHOD_STRIPE, 'Stripe'),
        (METHOD_BKASH,  'bKash'),
        (METHOD_NAGAD,  'Nagad'),
        (METHOD_CRYPTO, 'Crypto'),
        (METHOD_BANK,   'Bank Transfer'),
    ]

    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_PAID     = 'paid'
    STATUS_REJECTED = 'rejected'
    STATUS_FAILED   = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PAID,     'Paid'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_FAILED,   'Failed'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(User, on_delete=models.CASCADE,
                                        related_name='api_finance_payout_requests')
    transaction     = models.OneToOneField(Transaction, on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           related_name='payout_request')
    amount_requested = models.DecimalField(max_digits=12, decimal_places=4)
    fee             = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    amount_net      = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    method          = models.CharField(max_length=20, choices=METHOD_CHOICES)
    destination     = models.CharField(max_length=500,
                                       help_text='PayPal email, phone number, wallet address, etc.')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                       default=STATUS_PENDING, db_index=True)
    fraud_score     = models.PositiveSmallIntegerField(default=0)
    admin_notes     = models.TextField(blank=True, default='')
    rejection_reason = models.CharField(max_length=255, blank=True, default='')
    external_ref    = models.CharField(max_length=255, blank=True, default='',
                                       help_text='Payment gateway transaction ID')
    created_at      = models.DateTimeField(auto_now_add=True)
    processed_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'api_finance'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Payout({self.user_id}) ${self.amount_requested} via {self.method}"

    def save(self, *args, **kwargs):
        if not self.amount_net:
            self.amount_net = self.amount_requested - self.fee
        super().save(*args, **kwargs)


class ReconciliationLog(models.Model):
    """Daily financial reconciliation audit record."""
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date            = models.DateField(unique=True)
    total_credited  = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    total_debited   = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    total_fees      = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_payouts   = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    transaction_count = models.PositiveIntegerField(default=0)
    payout_count    = models.PositiveIntegerField(default=0)
    discrepancy_usd = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    is_balanced     = models.BooleanField(default=False)
    notes           = models.TextField(blank=True, default='')
    run_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name='reconciliations_run')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'api_finance'
        ordering = ['-date']

    def __str__(self):
        balanced = '✓' if self.is_balanced else '✗'
        return f"Reconciliation {self.date} {balanced} (${self.discrepancy_usd} diff)"
