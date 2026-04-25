# api/wallet/models_cpalead_extra.py
"""
WORLD-CLASS UPGRADE: Missing features after comparing with:
  - CPAlead   (affiliate wallet)
  - Binance   (crypto exchange wallet)
  - Razorpay  (payment gateway)
  - Stripe    (financial infrastructure)
  - PayPal    (payment platform)
  - bKash     (MFS Bangladesh)

New models added:
  KYCVerification    — Binance-style tiered KYC with withdrawal limit gates
  VirtualAccount     — Razorpay-style sub-wallet / virtual account
  SettlementBatch    — Razorpay T+0/T+1/T+2 settlement schedules
  InstantPayout      — Stripe-style instant payout with fee
  MassPayoutJob      — PayPal Payouts API bulk disbursement
  DisputeCase        — Chargeback / dispute management
  WithdrawalWhitelist — Binance-style address whitelist
  SecurityEvent      — 24h lock after security change
  RefundRequest      — Full refund lifecycle
  FraudScore         — ML-based risk scoring per transaction
  AMLFlag            — Anti-money laundering hold
  EarningOffer       — CPAlead CPA/CPI/CPC offer model
  ContentLocker      — CPAlead content locking monetization
  OfferWall          — CPAlead offer wall virtual currency
  WebhookEndpoint    — Configurable webhook destinations
  TaxRecord          — Tax reporting / 1099 generation
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
# 1. KYC VERIFICATION TIERS (Binance-style)
# ─────────────────────────────────────────────────────────────

class KYCVerification(models.Model):
    """
    Binance-style tiered KYC.
    Level 0: Unverified  — very limited withdrawal (50 BDT/day)
    Level 1: Basic       — NID + selfie  → 50,000 BDT/day
    Level 2: Intermediate— NID + address → 500,000 BDT/day
    Level 3: Advanced    — Business docs → Unlimited
    """
    LEVELS = [
        (0, "Level 0 — Unverified"),
        (1, "Level 1 — Basic (NID/Passport)"),
        (2, "Level 2 — Intermediate (Address Proof)"),
        (3, "Level 3 — Advanced (Business/Institutional)"),
    ]
    STATUS = [
        ("pending",  "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired",  "Expired"),
    ]
    DOC_TYPES = [
        ("nid",       "National ID Card"),
        ("passport",  "Passport"),
        ("driving",   "Driving License"),
        ("birth",     "Birth Certificate"),
        ("trade",     "Trade License"),
        ("tin",       "TIN Certificate"),
    ]

    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_kyc_tenant", db_index=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_kyc_user")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="kyc_verifications")
    level           = models.PositiveSmallIntegerField(choices=LEVELS, default=0)
    status          = models.CharField(max_length=10, choices=STATUS, default="pending")

    # Documents
    doc_type        = models.CharField(max_length=15, choices=DOC_TYPES, blank=True)
    doc_number      = models.CharField(max_length=50, blank=True)
    doc_front_url   = models.URLField(blank=True)
    doc_back_url    = models.URLField(blank=True)
    selfie_url      = models.URLField(blank=True)
    address_proof_url = models.URLField(blank=True)

    # Limits unlocked (BDT)
    daily_wd_limit  = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("500.00"))
    monthly_wd_limit= models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("5000.00"))

    # Review
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_kyc_reviewed")
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    rejection_reason= models.TextField(blank=True)
    expires_at      = models.DateTimeField(null=True, blank=True)
    risk_score      = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_kyc_verification"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} | KYC L{self.level} | {self.status}"

    # Withdrawal limits by level (BDT)
    LEVEL_LIMITS = {
        0: {"daily": Decimal("500"),      "monthly": Decimal("5000")},
        1: {"daily": Decimal("50000"),    "monthly": Decimal("500000")},
        2: {"daily": Decimal("500000"),   "monthly": Decimal("5000000")},
        3: {"daily": Decimal("9999999"),  "monthly": Decimal("99999999")},
    }

    def approve(self, reviewed_by=None):
        self.status = "approved"
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        limits = self.LEVEL_LIMITS.get(self.level, self.LEVEL_LIMITS[0])
        self.daily_wd_limit   = limits["daily"]
        self.monthly_wd_limit = limits["monthly"]
        self.save()
        # Update wallet daily limit
        self.wallet.daily_limit = limits["daily"]
        self.wallet.save(update_fields=["daily_limit","updated_at"])

    def reject(self, reason: str, reviewed_by=None):
        self.status = "rejected"
        self.rejection_reason = reason
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save()


# ─────────────────────────────────────────────────────────────
# 2. VIRTUAL ACCOUNT (Razorpay-style)
# ─────────────────────────────────────────────────────────────

class VirtualAccount(models.Model):
    """
    Razorpay-style virtual account — unique bank account for each user.
    Used for Smart Collect: any transfer to this account auto-credits wallet.
    """
    STATUSES = [("active","Active"),("closed","Closed"),("paid","Paid")]
    TYPES    = [("bank","Bank Account"),("vpa","UPI VPA"),("bkash","bKash")]

    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_virtualaccount_tenant", db_index=True)
    va_id           = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="virtual_accounts")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="virtual_accounts")
    account_type    = models.CharField(max_length=10, choices=TYPES, default="bank")
    status          = models.CharField(max_length=6, choices=STATUSES, default="active")

    # Bank details (auto-generated)
    account_number  = models.CharField(max_length=30, unique=True, blank=True)
    ifsc_code       = models.CharField(max_length=15, blank=True)
    bank_name       = models.CharField(max_length=100, blank=True)
    vpa_address     = models.CharField(max_length=100, blank=True)  # UPI: user@bank

    # Limits
    expected_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_received = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    close_by        = models.DateTimeField(null=True, blank=True)

    description     = models.TextField(blank=True)
    metadata        = models.JSONField(default=dict, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    closed_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_virtual_account"

    def __str__(self):
        return f"VA {self.account_number} | {self.user.username} | {self.status}"


# ─────────────────────────────────────────────────────────────
# 3. SETTLEMENT BATCH (Razorpay T+0/T+1/T+2)
# ─────────────────────────────────────────────────────────────

class SettlementBatch(models.Model):
    """
    Razorpay-style settlement: batch of transactions settled to merchant.
    T+0 = same day, T+1 = next day, T+2 = 2 days.
    """
    SCHEDULES = [
        ("instant","Instant (T+0)"),
        ("next_day","Next Day (T+1)"),
        ("two_day", "Two Days (T+2)"),
        ("weekly",  "Weekly"),
        ("monthly", "Monthly"),
    ]
    STATUSES = [
        ("pending","Pending"),("processing","Processing"),
        ("settled","Settled"),("failed","Failed"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_settlementbatch_tenant", db_index=True)
    settlement_id   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="settlements")
    schedule        = models.CharField(max_length=10, choices=SCHEDULES, default="two_day")
    status          = models.CharField(max_length=12, choices=STATUSES, default="pending")
    total_amount    = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    fee_amount      = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_amount      = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    transaction_count = models.PositiveIntegerField(default=0)
    settlement_date = models.DateField()
    settled_at      = models.DateTimeField(null=True, blank=True)
    utr_number      = models.CharField(max_length=100, blank=True)  # Bank UTR
    bank_reference  = models.CharField(max_length=200, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_settlement_batch"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"Settlement {self.settlement_id} | {self.schedule} | {self.status}"


# ─────────────────────────────────────────────────────────────
# 4. INSTANT PAYOUT (Stripe-style)
# ─────────────────────────────────────────────────────────────

class InstantPayout(models.Model):
    """
    Stripe-style instant payout: immediate transfer with fee.
    Standard: T+2, free.
    Instant: within minutes, 1.5% fee (min 5 BDT).
    """
    STATUSES = [("pending","Pending"),("in_transit","In Transit"),("paid","Paid"),("failed","Failed"),("cancelled","Cancelled")]
    METHODS  = [("bkash","bKash"),("nagad","Nagad"),("bank_instant","Instant Bank")]

    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_instantpayout_tenant", db_index=True)
    payout_id       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="instant_payouts")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="instant_payouts")
    amount          = models.DecimalField(max_digits=20, decimal_places=2)
    fee             = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_amount      = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    fee_percent     = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.50"))
    min_fee         = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("5.00"))
    method          = models.CharField(max_length=20, choices=METHODS)
    destination     = models.CharField(max_length=100)
    status          = models.CharField(max_length=12, choices=STATUSES, default="pending")
    arrival_time    = models.DateTimeField(null=True, blank=True)
    gateway_ref     = models.CharField(max_length=200, blank=True)
    failure_reason  = models.TextField(blank=True)
    withdrawal      = models.ForeignKey("WithdrawalRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="instant_payout")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_instant_payout"

    def __str__(self):
        return f"InstantPayout {self.payout_id} | {self.amount} | {self.status}"

    def calculate_fee(self) -> Decimal:
        fee = (self.amount * self.fee_percent / 100).quantize(Decimal("0.01"))
        return max(fee, self.min_fee)


# ─────────────────────────────────────────────────────────────
# 5. MASS PAYOUT JOB (PayPal Payouts API style)
# ─────────────────────────────────────────────────────────────

class MassPayoutJob(models.Model):
    """
    PayPal-style mass payout: send money to hundreds of users at once.
    Used by admin for batch affiliate payments, referral distributions, etc.
    """
    STATUSES = [
        ("draft","Draft"),("queued","Queued"),("processing","Processing"),
        ("success","Success"),("partial","Partial Success"),("failed","Failed"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_masspayjob_tenant", db_index=True)
    job_id          = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title           = models.CharField(max_length=200)
    status          = models.CharField(max_length=12, choices=STATUSES, default="draft")
    total_amount    = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_count     = models.PositiveIntegerField(default=0)
    success_count   = models.PositiveIntegerField(default=0)
    failed_count    = models.PositiveIntegerField(default=0)
    pending_count   = models.PositiveIntegerField(default=0)
    payout_type     = models.CharField(max_length=50, blank=True)  # "referral_bonus", "contest_prize", etc.
    method          = models.CharField(max_length=20, default="bkash")
    note            = models.TextField(blank=True)
    created_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="mass_payout_jobs")
    approved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_mass_payouts")
    created_at      = models.DateTimeField(auto_now_add=True)
    started_at      = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_mass_payout_job"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"MassPayout {self.job_id} | {self.title} | {self.status}"


class MassPayoutItem(models.Model):
    """Individual item in a MassPayoutJob."""
    STATUSES = [("pending","Pending"),("success","Success"),("failed","Failed"),("skipped","Skipped")]
    job         = models.ForeignKey(MassPayoutJob, on_delete=models.CASCADE, related_name="items")
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mass_payout_items")
    wallet      = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="mass_payout_items")
    amount      = models.DecimalField(max_digits=20, decimal_places=2)
    status      = models.CharField(max_length=8, choices=STATUSES, default="pending")
    error       = models.TextField(blank=True)
    withdrawal  = models.ForeignKey("WithdrawalRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="mass_payout_item")
    processed_at= models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_mass_payout_item"


# ─────────────────────────────────────────────────────────────
# 6. DISPUTE / CHARGEBACK (PayPal/Stripe-style)
# ─────────────────────────────────────────────────────────────

class DisputeCase(models.Model):
    """Chargeback and dispute management — full lifecycle."""
    REASONS = [
        ("unauthorized","Unauthorized Transaction"),
        ("not_received", "Payment Not Received"),
        ("incorrect",   "Incorrect Amount"),
        ("duplicate",   "Duplicate Transaction"),
        ("fraud",       "Fraud"),
        ("other",       "Other"),
    ]
    STATUSES = [
        ("open","Open"),("under_review","Under Review"),
        ("resolved_user","Resolved — User Favor"),
        ("resolved_platform","Resolved — Platform Favor"),
        ("cancelled","Cancelled"),
    ]
    OUTCOMES = [
        ("refund_full","Full Refund"),("refund_partial","Partial Refund"),
        ("no_refund","No Refund"),("warning","Warning Issued"),
        ("account_suspended","Account Suspended"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_dispute_tenant", db_index=True)
    case_id         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_disputes")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="disputes")
    transaction     = models.ForeignKey("WalletTransaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="disputes")
    withdrawal      = models.ForeignKey("WithdrawalRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="disputes")
    reason          = models.CharField(max_length=20, choices=REASONS)
    status          = models.CharField(max_length=25, choices=STATUSES, default="open")
    outcome         = models.CharField(max_length=20, choices=OUTCOMES, blank=True)
    disputed_amount = models.DecimalField(max_digits=20, decimal_places=2)
    refunded_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    description     = models.TextField()
    evidence        = models.JSONField(default=list, blank=True)  # [{url, type, description}]
    internal_notes  = models.TextField(blank=True)
    assigned_to     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_disputes")
    resolved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_resolved_disputes")
    resolved_at     = models.DateTimeField(null=True, blank=True)
    due_by          = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_dispute"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"Dispute {self.case_id} | {self.user.username} | {self.reason} | {self.status}"


# ─────────────────────────────────────────────────────────────
# 7. WITHDRAWAL ADDRESS WHITELIST (Binance-style)
# ─────────────────────────────────────────────────────────────

class WithdrawalWhitelist(models.Model):
    """
    Binance-style: only whitelisted addresses/accounts can receive withdrawals.
    Adds 24h lock after adding a new address.
    """
    METHOD_TYPES = [("bkash","bKash"),("nagad","Nagad"),("bank","Bank"),("usdt","USDT"),("paypal","PayPal")]

    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_whitelist_tenant", db_index=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawal_whitelist")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="whitelist")
    method_type     = models.CharField(max_length=10, choices=METHOD_TYPES)
    account         = models.CharField(max_length=200)
    label           = models.CharField(max_length=100, blank=True)
    is_active       = models.BooleanField(default=False)  # inactive for 24h
    activated_at    = models.DateTimeField(null=True, blank=True)  # 24h after creation
    is_trusted      = models.BooleanField(default=False)  # admin-trusted, no 24h lock
    added_ip        = models.GenericIPAddressField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_whitelist"
        unique_together = [("user","method_type","account")]

    def __str__(self):
        return f"Whitelist {self.user.username} | {self.method_type} | {self.account}"

    def activate(self):
        self.is_active = True
        self.activated_at = timezone.now()
        self.save(update_fields=["is_active","activated_at"])

    def is_unlocked(self) -> bool:
        """Active after 24h from creation (Binance-style security)."""
        if self.is_trusted:
            return True
        if not self.is_active:
            return False
        return True


# ─────────────────────────────────────────────────────────────
# 8. SECURITY EVENT (Binance-style 24h lock)
# ─────────────────────────────────────────────────────────────

class SecurityEvent(models.Model):
    """
    Binance-style: after security change (password/2FA/pin reset),
    withdrawals locked for 24 hours to prevent unauthorized access.
    """
    EVENT_TYPES = [
        ("password_reset","Password Reset"),
        ("2fa_change",    "2FA Changed"),
        ("pin_reset",     "Withdrawal PIN Reset"),
        ("email_change",  "Email Changed"),
        ("phone_change",  "Phone Changed"),
        ("kyc_failed",    "KYC Verification Failed"),
        ("suspicious_login","Suspicious Login"),
        ("api_key_created","API Key Created"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_securityevent_tenant", db_index=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_security_events")
    wallet          = models.ForeignKey("Wallet", on_delete=models.SET_NULL, null=True, blank=True, related_name="security_events")
    event_type      = models.CharField(max_length=25, choices=EVENT_TYPES)
    lock_hours      = models.PositiveIntegerField(default=24)
    lock_until      = models.DateTimeField()
    is_resolved     = models.BooleanField(default=False)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    device_info     = models.JSONField(default=dict, blank=True)
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_security_event"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"SecurityEvent {self.user.username} | {self.event_type} | lock_until={self.lock_until}"

    def save(self, *args, **kwargs):
        if not self.lock_until:
            from datetime import timedelta
            self.lock_until = timezone.now() + timedelta(hours=self.lock_hours)
        super().save(*args, **kwargs)

    def is_locked(self) -> bool:
        return not self.is_resolved and timezone.now() < self.lock_until


# ─────────────────────────────────────────────────────────────
# 9. REFUND REQUEST (Stripe/Razorpay-style)
# ─────────────────────────────────────────────────────────────

class RefundRequest(models.Model):
    """Full refund lifecycle — partial or full refund with audit trail."""
    STATUSES = [
        ("pending","Pending"),("approved","Approved"),
        ("processing","Processing"),("completed","Completed"),
        ("rejected","Rejected"),("cancelled","Cancelled"),
    ]
    REASONS = [
        ("duplicate","Duplicate Payment"),
        ("fraudulent","Fraudulent"),
        ("customer_request","Customer Request"),
        ("service_not_provided","Service Not Provided"),
        ("admin","Admin Initiated"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_refund_tenant", db_index=True)
    refund_id       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_refunds")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="refunds")
    original_txn    = models.ForeignKey("WalletTransaction", on_delete=models.PROTECT, related_name="refund_requests")
    reason          = models.CharField(max_length=25, choices=REASONS)
    status          = models.CharField(max_length=12, choices=STATUSES, default="pending")
    requested_amount= models.DecimalField(max_digits=20, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    description     = models.TextField(blank=True)
    processed_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_refunds")
    processed_at    = models.DateTimeField(null=True, blank=True)
    refund_txn      = models.ForeignKey("WalletTransaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="refund_origin")
    rejection_reason= models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_refund_request"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"Refund {self.refund_id} | {self.user.username} | {self.requested_amount} | {self.status}"


# ─────────────────────────────────────────────────────────────
# 10. FRAUD SCORE (ML-based risk scoring)
# ─────────────────────────────────────────────────────────────

class FraudScore(models.Model):
    """
    Stripe Radar-style: ML risk score per transaction/withdrawal.
    Score 0-100: 0=safe, 100=high risk.
    Auto-block if score >= 85.
    """
    RISK_LEVELS = [
        ("low",    "Low Risk (0-30)"),
        ("medium", "Medium Risk (31-70)"),
        ("high",   "High Risk (71-84)"),
        ("blocked","Blocked (85+)"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_fraudscore_tenant", db_index=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_fraud_scores")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="fraud_scores")
    transaction     = models.OneToOneField("WalletTransaction", on_delete=models.CASCADE, null=True, blank=True, related_name="fraud_score")
    withdrawal      = models.OneToOneField("WithdrawalRequest", on_delete=models.CASCADE, null=True, blank=True, related_name="fraud_score")
    score           = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    risk_level      = models.CharField(max_length=8, choices=RISK_LEVELS, default="low")
    is_blocked      = models.BooleanField(default=False)
    block_reason    = models.TextField(blank=True)

    # Signal breakdown
    velocity_score   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ip_risk_score    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    device_risk_score= models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount_risk_score= models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pattern_score    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    kyc_score        = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    signals         = models.JSONField(default=list, blank=True)  # list of triggered signals
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_fraud_scores")
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    override_reason = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_fraud_score"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"FraudScore {self.user.username} | {self.score} | {self.risk_level}"

    def calculate(self) -> Decimal:
        """Compute composite fraud score from signals."""
        weights = {
            "velocity": Decimal("0.25"),
            "ip_risk":  Decimal("0.20"),
            "device":   Decimal("0.15"),
            "amount":   Decimal("0.20"),
            "pattern":  Decimal("0.10"),
            "kyc":      Decimal("0.10"),
        }
        self.score = (
            self.velocity_score   * weights["velocity"]
            + self.ip_risk_score  * weights["ip_risk"]
            + self.device_risk_score * weights["device"]
            + self.amount_risk_score * weights["amount"]
            + self.pattern_score  * weights["pattern"]
            + self.kyc_score      * weights["kyc"]
        ).quantize(Decimal("0.01"))

        if self.score >= 85:
            self.risk_level = "blocked"
            self.is_blocked = True
        elif self.score >= 71:
            self.risk_level = "high"
        elif self.score >= 31:
            self.risk_level = "medium"
        else:
            self.risk_level = "low"

        self.save()
        return self.score


# ─────────────────────────────────────────────────────────────
# 11. AML FLAG (Anti-Money Laundering)
# ─────────────────────────────────────────────────────────────

class AMLFlag(models.Model):
    """Anti-money laundering detection and case management."""
    FLAG_TYPES = [
        ("structuring",       "Structuring (Smurfing)"),
        ("rapid_movement",    "Rapid Fund Movement"),
        ("unusual_pattern",   "Unusual Transaction Pattern"),
        ("high_risk_country", "High Risk Country"),
        ("politically_exposed","Politically Exposed Person"),
        ("sanction_match",    "Sanctions List Match"),
        ("large_cash",        "Large Cash Equivalent"),
        ("round_numbers",     "Suspicious Round Numbers"),
    ]
    STATUSES = [
        ("flagged","Flagged"),("investigating","Investigating"),
        ("cleared","Cleared"),("reported","Reported to Authority"),("frozen","Account Frozen"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_amlflag_tenant", db_index=True)
    flag_id         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="aml_flags")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="aml_flags")
    flag_type       = models.CharField(max_length=25, choices=FLAG_TYPES)
    status          = models.CharField(max_length=15, choices=STATUSES, default="flagged")
    description     = models.TextField()
    suspicious_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    transactions    = models.ManyToManyField("WalletTransaction", blank=True, related_name="aml_flags")
    evidence        = models.JSONField(default=list, blank=True)
    assigned_to     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_aml_cases")
    resolved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_aml_cases")
    resolved_at     = models.DateTimeField(null=True, blank=True)
    reported_to     = models.CharField(max_length=200, blank=True)
    reported_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_aml_flag"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"AML {self.flag_id} | {self.user.username} | {self.flag_type} | {self.status}"


# ─────────────────────────────────────────────────────────────
# 12. EARNING OFFER (CPAlead CPA/CPI/CPC)
# ─────────────────────────────────────────────────────────────

class EarningOffer(models.Model):
    """
    CPAlead-style earning offers: CPA, CPI, CPC, Content Lock.
    Publishers earn per action/install/click.
    """
    OFFER_TYPES = [
        ("cpa",          "CPA — Cost Per Action"),
        ("cpi",          "CPI — Cost Per Install"),
        ("cpc",          "CPC — Cost Per Click"),
        ("cpl",          "CPL — Cost Per Lead"),
        ("content_lock", "Content Lock"),
        ("offer_wall",   "Offer Wall"),
        ("survey",       "Survey"),
        ("daily_task",   "Daily Task"),
        ("video",        "Video Watch"),
    ]
    GEO_TIERS = [("tier1","Tier 1"),("tier2","Tier 2"),("tier3","Tier 3"),("all","All GEOs")]

    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_earningoffer_tenant", db_index=True)
    offer_id        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title           = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    offer_type      = models.CharField(max_length=15, choices=OFFER_TYPES)
    geo_tier        = models.CharField(max_length=6, choices=GEO_TIERS, default="all")
    target_countries= models.JSONField(default=list, blank=True)  # ["US","UK","CA"]
    payout          = models.DecimalField(max_digits=10, decimal_places=4)  # per action
    payout_currency = models.CharField(max_length=5, default="USD")
    payout_bdt      = models.DecimalField(max_digits=14, decimal_places=4, default=0)  # auto-converted
    daily_cap       = models.PositiveIntegerField(default=0, help_text="0=unlimited")
    total_cap       = models.PositiveIntegerField(default=0)
    conversions_today = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    is_active       = models.BooleanField(default=True)
    requires_kyc    = models.BooleanField(default=False)
    min_publisher_level = models.PositiveSmallIntegerField(default=1)
    advertiser      = models.CharField(max_length=200, blank=True)
    offer_url       = models.URLField(blank=True)
    preview_url     = models.URLField(blank=True)
    icon_url        = models.URLField(blank=True)
    starts_at       = models.DateTimeField(null=True, blank=True)
    ends_at         = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_earning_offer"
        ordering  = ["-payout","-created_at"]

    def __str__(self):
        return f"{self.offer_type.upper()}: {self.title} | ${self.payout}"

    def is_capped(self) -> bool:
        if self.daily_cap > 0 and self.conversions_today >= self.daily_cap:
            return True
        if self.total_cap > 0 and self.total_conversions >= self.total_cap:
            return True
        return False


class OfferConversion(models.Model):
    """Log every conversion for an EarningOffer — immutable record."""
    STATUSES = [("pending","Pending"),("approved","Approved"),("rejected","Rejected"),("chargeback","Chargeback")]

    offer           = models.ForeignKey(EarningOffer, on_delete=models.PROTECT, related_name="conversions")
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offer_conversions")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="offer_conversions")
    transaction     = models.ForeignKey("WalletTransaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="offer_conversions")
    status          = models.CharField(max_length=12, choices=STATUSES, default="pending")
    payout          = models.DecimalField(max_digits=10, decimal_places=4)
    click_id        = models.CharField(max_length=100, blank=True, db_index=True)
    sub_id          = models.CharField(max_length=100, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.TextField(blank=True)
    country_code    = models.CharField(max_length=3, blank=True)
    device_type     = models.CharField(max_length=20, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    approved_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_offer_conversion"
        ordering  = ["-created_at"]


# ─────────────────────────────────────────────────────────────
# 13. CONFIGURABLE WEBHOOK ENDPOINTS
# ─────────────────────────────────────────────────────────────

class WebhookEndpoint(models.Model):
    """
    Stripe-style configurable webhooks.
    Users can register URLs to receive wallet event notifications.
    """
    EVENTS = [
        ("wallet.credited",      "Wallet Credited"),
        ("wallet.debited",       "Wallet Debited"),
        ("withdrawal.created",   "Withdrawal Created"),
        ("withdrawal.completed", "Withdrawal Completed"),
        ("withdrawal.failed",    "Withdrawal Failed"),
        ("transaction.reversed", "Transaction Reversed"),
        ("kyc.approved",         "KYC Approved"),
        ("kyc.rejected",         "KYC Rejected"),
        ("fraud.blocked",        "Fraud Blocked"),
        ("aml.flagged",          "AML Flagged"),
        ("dispute.opened",       "Dispute Opened"),
        ("dispute.resolved",     "Dispute Resolved"),
        ("*",                    "All Events"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_webhookendpoint_tenant", db_index=True)
    endpoint_id     = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_webhook_endpoints")
    url             = models.URLField()
    secret          = models.CharField(max_length=256, blank=True)  # HMAC signing secret
    subscribed_events = models.JSONField(default=list)  # ["wallet.credited", "withdrawal.completed"]
    is_active       = models.BooleanField(default=True)
    last_called_at  = models.DateTimeField(null=True, blank=True)
    last_status     = models.PositiveIntegerField(null=True, blank=True)  # HTTP status
    failure_count   = models.PositiveIntegerField(default=0)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_webhook_endpoint"

    def __str__(self):
        return f"Webhook {self.user.username} | {self.url}"


# ─────────────────────────────────────────────────────────────
# 14. TAX RECORD (1099 / Tax reporting)
# ─────────────────────────────────────────────────────────────

class TaxRecord(models.Model):
    """Annual tax reporting — 1099-MISC equivalent for Bangladesh."""
    TAX_YEARS = [(y, str(y)) for y in range(2020, 2031)]
    STATUSES  = [("pending","Pending"),("generated","Generated"),("sent","Sent to User"),("filed","Filed")]

    tenant          = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_taxrecord_tenant", db_index=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_tax_records")
    wallet          = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name="tax_records")
    tax_year        = models.PositiveSmallIntegerField(choices=TAX_YEARS)
    status          = models.CharField(max_length=10, choices=STATUSES, default="pending")
    total_income    = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_fees      = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_bonuses   = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_referral  = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    transaction_count = models.PositiveIntegerField(default=0)
    tin_number      = models.CharField(max_length=20, blank=True)
    pdf_url         = models.URLField(blank=True)
    generated_at    = models.DateTimeField(null=True, blank=True)
    sent_at         = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_tax_record"
        unique_together = [("user","tax_year")]
        ordering  = ["-tax_year"]

    def __str__(self):
        return f"Tax {self.user.username} | {self.tax_year} | {self.total_income}"


# ─────────────────────────────────────────────────────────────
# GEO RATE (ported from original models.py)
# ─────────────────────────────────────────────────────────────

class GeoRate(models.Model):
    """CPAlead: Tier1 (US/UK/CA/AU) pays 2.5× more than Tier3."""
    GEO_TIERS = [
        ("tier1","Tier1 — US,UK,CA,AU,NZ"),
        ("tier2","Tier2 — EU,JP,SG,KR,AE"),
        ("tier3","Tier3 — South/SE Asia"),
        ("tier4","Tier4 — Africa, Rest"),
        ("bd","Bangladesh Local"),
    ]
    tenant           = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_georate_tenant", db_index=True)
    country_code     = models.CharField(max_length=3, db_index=True)
    country_name     = models.CharField(max_length=100)
    geo_tier         = models.CharField(max_length=6, choices=GEO_TIERS, default="tier3")
    rate_multiplier  = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("1.0000"))
    base_cpa_rate    = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    base_cpi_rate    = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    base_cpc_rate    = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_georate"
        unique_together = [("country_code",)]

    def __str__(self):
        return f"{self.country_code} | {self.geo_tier} | ×{self.rate_multiplier}"


# ─────────────────────────────────────────────────────────────────────
# CPAlead-INSPIRED: REFERRAL PROGRAM (6-month time limit)
# ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
# PUBLISHER LEVEL (CPAlead — NET30→Daily unlock)
# ─────────────────────────────────────────────────────────────
class PublisherLevel(models.Model):
    """
    CPAlead-style publisher quality level.
    Level 1 (New)    → NET30 payout, 30-day hold
    Level 2 (Verified) → NET15 payout
    Level 3 (Trusted)  → Weekly payout
    Level 4 (Premium)  → Daily payout
    Level 5 (Elite)    → FastPay / Instant
    """
    LEVELS = [
        (1,"Level 1 — New (NET30)"),
        (2,"Level 2 — Verified (NET15)"),
        (3,"Level 3 — Trusted (Weekly)"),
        (4,"Level 4 — Premium (Daily)"),
        (5,"Level 5 — Elite (FastPay)"),
    ]
    PAYOUT_FREQS = [
        ("net30","Net-30"),("net15","Net-15"),
        ("weekly","Weekly"),("daily","Daily"),("instant","Instant"),
    ]
    tenant         = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_publisherlevel_tenant",db_index=True)
    user           = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="publisher_level")
    wallet         = models.OneToOneField("wallet.Wallet",on_delete=models.CASCADE,related_name="publisher_level")
    level          = models.PositiveSmallIntegerField(choices=LEVELS,default=1)
    quality_score  = models.DecimalField(max_digits=5,decimal_places=2,default=0)
    total_earnings = models.DecimalField(max_digits=20,decimal_places=8,default=Decimal("0"))
    fraud_flags    = models.PositiveIntegerField(default=0)
    payout_freq    = models.CharField(max_length=10,choices=PAYOUT_FREQS,default="net30")
    hold_released  = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label="wallet"; db_table="wallet_publisher_level"

    def __str__(self):
        return f"{self.user.username} | L{self.level} | {self.payout_freq}"

    def can_upgrade(self) -> bool:
        thresholds = {1:Decimal("100"),2:Decimal("500"),3:Decimal("2000"),4:Decimal("10000")}
        return (self.level < 5 and
                self.total_earnings >= thresholds.get(self.level, Decimal("999999")) and
                self.fraud_flags == 0)

    def upgrade(self) -> bool:
        if not self.can_upgrade(): return False
        self.level += 1
        freq_map = {1:"net30",2:"net15",3:"weekly",4:"daily",5:"instant"}
        self.payout_freq = freq_map.get(self.level,"net30")
        self.save(); return True

# ─────────────────────────────────────────────────────────────
# PAYOUT SCHEDULE (CPAlead daily/weekly/NET30)
# ─────────────────────────────────────────────────────────────
class PayoutSchedule(models.Model):
    """CPAlead payout schedule per publisher."""
    FREQ_CHOICES = [
        ("daily","Daily (earn $1+ today → paid tomorrow)"),
        ("weekly","Weekly"),("net15","Net-15"),("net30","Net-30"),
        ("instant","Instant / Fast Pay"),("on_request","On Request"),
    ]
    tenant             = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_payoutschedule_tenant",db_index=True)
    user               = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="payout_schedule")
    wallet             = models.OneToOneField("wallet.Wallet",on_delete=models.CASCADE,related_name="payout_schedule")
    frequency          = models.CharField(max_length=12,choices=FREQ_CHOICES,default="net30")
    minimum_threshold  = models.DecimalField(max_digits=14,decimal_places=2,default=Decimal("50"))
    auto_payout        = models.BooleanField(default=True)
    fast_pay_enabled   = models.BooleanField(default=False)
    hold_days          = models.PositiveIntegerField(default=30,help_text="New publisher hold period in days")
    hold_released      = models.BooleanField(default=False)
    last_payout_date   = models.DateField(null=True,blank=True)
    last_payout_amount = models.DecimalField(max_digits=14,decimal_places=2,default=Decimal("0"))
    total_payouts      = models.PositiveIntegerField(default=0)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        app_label="wallet"; db_table="wallet_payout_schedule"

    def __str__(self):
        return f"{self.user.username} | {self.frequency} | min={self.minimum_threshold}"

    def can_payout_now(self) -> bool:
        from .models.core import Wallet
        try:
            w = self.wallet
            return (w.current_balance >= self.minimum_threshold and not w.is_locked)
        except Exception:
            return False

# ─────────────────────────────────────────────────────────────
# POINTS LEDGER (CPAlead virtual currency 1000pts=$1)
# ─────────────────────────────────────────────────────────────
class PointsLedger(models.Model):
    """CPAlead virtual currency / points system."""
    tenant          = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_pointsledger_tenant",db_index=True)
    user            = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="points_ledger")
    wallet          = models.OneToOneField("wallet.Wallet",on_delete=models.CASCADE,related_name="points_ledger")
    total_points    = models.PositiveBigIntegerField(default=0)
    lifetime_points = models.PositiveBigIntegerField(default=0)
    redeemed_points = models.PositiveBigIntegerField(default=0)
    points_per_dollar = models.PositiveIntegerField(default=1000)
    current_tier    = models.CharField(max_length=50,blank=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label="wallet"; db_table="wallet_points_ledger"

    def __str__(self):
        return f"{self.user.username} | {self.total_points}pts"

    def award(self, earned_bdt: Decimal):
        pts = int(earned_bdt * self.points_per_dollar / 100)
        self.total_points    += pts
        self.lifetime_points += pts
        self._update_tier(); self.save()

    def _update_tier(self):
        lt = self.lifetime_points
        if lt >= 1_000_000: self.current_tier = "Diamond"
        elif lt >= 500_000: self.current_tier = "Platinum"
        elif lt >= 100_000: self.current_tier = "Gold"
        elif lt >= 50_000:  self.current_tier = "Silver"
        elif lt >= 10_000:  self.current_tier = "Bronze"
        else:               self.current_tier = "Starter"

# ─────────────────────────────────────────────────────────────
# PERFORMANCE BONUS (CPAlead top earner 20% bonus)
# ─────────────────────────────────────────────────────────────
class PerformanceBonus(models.Model):
    """CPAlead-style performance bonus for top earners (up to 20%)."""
    BONUS_TYPES = [
        ("top_earner","Top Earner"),("streak","Streak Bonus"),
        ("tier_upgrade","Tier Upgrade"),("promo","Promotional"),
    ]
    STATUS = [("active","Active"),("expired","Expired"),("used","Used")]

    tenant        = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_performancebonus_tenant",db_index=True)
    user          = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="performance_bonuses")
    wallet        = models.ForeignKey("wallet.Wallet",on_delete=models.CASCADE,related_name="performance_bonuses")
    bonus_type    = models.CharField(max_length=20,choices=BONUS_TYPES,default="top_earner")
    status        = models.CharField(max_length=10,choices=STATUS,default="active")
    bonus_percent = models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("10.00"),
                                        help_text="Extra % added to every earning (max 20%)")
    period        = models.CharField(max_length=20,blank=True)
    total_paid    = models.DecimalField(max_digits=14,decimal_places=8,default=Decimal("0"))
    max_bonus     = models.DecimalField(max_digits=14,decimal_places=2,null=True,blank=True)
    starts_at     = models.DateTimeField(default=timezone.now)
    expires_at    = models.DateTimeField(null=True,blank=True)
    note          = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label="wallet"; db_table="wallet_performance_bonus"

    def __str__(self):
        return f"{self.user.username} | {self.bonus_type} | {self.bonus_percent}%"

    def is_active_now(self) -> bool:
        now = timezone.now()
        return (self.status == "active" and
                self.starts_at <= now and
                (self.expires_at is None or now < self.expires_at))

# ─────────────────────────────────────────────────────────────
# REFERRAL PROGRAM (CPAlead 6-month 10%/5%/2%)
# ─────────────────────────────────────────────────────────────
class ReferralProgram(models.Model):
    """
    CPAlead-style 3-level referral with 6-month validity.
    L1: 10% | L2: 5% | L3: 2%
    """
    tenant         = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_referralprogram_tenant",db_index=True)
    referrer       = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="referral_programs_as_referrer")
    referred       = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="referral_programs_as_referred")
    level          = models.PositiveSmallIntegerField(default=1,choices=[(1,"Level 1 (10%)"),(2,"Level 2 (5%)"),(3,"Level 3 (2%)")])
    commission_rate = models.DecimalField(max_digits=5,decimal_places=4,default=Decimal("0.1000"))
    is_active      = models.BooleanField(default=True)
    duration_months = models.PositiveSmallIntegerField(default=6)
    total_earned   = models.DecimalField(max_digits=14,decimal_places=8,default=Decimal("0"))
    starts_at      = models.DateTimeField(default=timezone.now)
    expires_at     = models.DateTimeField(null=True,blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label="wallet"; db_table="wallet_referral_program"
        unique_together=[("referrer","referred","level")]

    def __str__(self):
        return f"{self.referrer.username}→{self.referred.username} L{self.level} {int(self.commission_rate*100)}%"

    def save(self,*args,**kwargs):
        if not self.expires_at and self.starts_at:
            from datetime import timedelta
            self.expires_at = self.starts_at + timedelta(days=self.duration_months*30)
        if not self.commission_rate:
            self.commission_rate = {1:Decimal("0.10"),2:Decimal("0.05"),3:Decimal("0.02")}.get(self.level,Decimal("0"))
        super().save(*args,**kwargs)

    def is_valid(self) -> bool:
        return self.is_active and (self.expires_at is None or timezone.now() < self.expires_at)
