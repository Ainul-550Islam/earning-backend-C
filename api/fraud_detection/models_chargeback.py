# =============================================================================
# fraud_detection/models_chargeback.py
#
# INSTRUCTION: এই ফাইলের classes গুলো আপনার models.py-এর শেষে copy করুন।
# তারপর একটি migration তৈরি করুন:
#   python manage.py makemigrations fraud_detection
#   python manage.py migrate
# =============================================================================
from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from api.core.models import TimeStampedModel

User = get_user_model()


# =============================================================================
# ChargebackDispute
# =============================================================================

class ChargebackDispute(TimeStampedModel):
    """
    Tracks payment chargebacks and disputes filed against the platform.

    A chargeback happens when a user disputes a charge with their bank/card issuer
    and the payment processor reverses the transaction. High chargeback rates are a
    direct financial loss and can trigger payment processor penalties or account termination.
    """

    class Status(models.TextChoices):
        RECEIVED       = 'received',       'Received'
        INVESTIGATING  = 'investigating',  'Investigating'
        REPRESENTED    = 'represented',    'Represented (Fighting)'
        WON            = 'won',            'Won (Dispute Resolved)'
        LOST           = 'lost',           'Lost (Amount Debited)'
        REVERSED       = 'reversed',       'Reversed by Bank'
        WITHDRAWN      = 'withdrawn',      'Withdrawn by User'

    class Reason(models.TextChoices):
        UNAUTHORIZED         = 'unauthorized',         'Unauthorized Transaction'
        DUPLICATE            = 'duplicate',            'Duplicate Charge'
        ITEM_NOT_RECEIVED    = 'not_received',         'Item / Service Not Received'
        ITEM_NOT_AS_DESCRIBED = 'not_as_described',   'Not As Described'
        CREDIT_NOT_PROCESSED = 'credit_not_processed', 'Credit Not Processed'
        FRAUD                = 'fraud',                'Fraud / Identity Theft'
        SUBSCRIPTION         = 'subscription',         'Subscription Cancelled'
        OTHER                = 'other',                'Other'

    dispute_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chargeback_disputes',
    )
    fraud_attempt = models.ForeignKey(
        'FraudAttempt',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chargeback_disputes',
    )
    fraud_case = models.ForeignKey(
        'FraudCase',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chargeback_disputes',
    )

    # Payment info
    transaction_id       = models.CharField(max_length=255, db_index=True)
    payment_processor    = models.CharField(max_length=100, default='unknown')
    original_amount      = models.DecimalField(max_digits=14, decimal_places=2)
    disputed_amount      = models.DecimalField(max_digits=14, decimal_places=2)
    currency             = models.CharField(max_length=10, default='USD')

    # Dispute details
    reason               = models.CharField(max_length=30, choices=Reason.choices)
    status               = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    bank_reference       = models.CharField(max_length=255, blank=True)
    processor_reference  = models.CharField(max_length=255, blank=True)
    description          = models.TextField(blank=True)
    evidence_submitted   = models.JSONField(default=dict)

    # Dates
    transaction_date     = models.DateTimeField(null=True, blank=True)
    received_at          = models.DateTimeField(default=timezone.now)
    response_deadline    = models.DateTimeField(null=True, blank=True)
    resolved_at          = models.DateTimeField(null=True, blank=True)

    # Resolution
    resolved_by          = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_chargebacks',
    )
    resolution_notes     = models.TextField(blank=True)
    is_fraudulent        = models.BooleanField(default=False)
    fraud_confirmed      = models.BooleanField(default=False)

    # Metadata
    metadata             = models.JSONField(default=dict)

    class Meta:
        ordering    = ['-received_at']
        indexes     = [
            models.Index(fields=['status', 'received_at'], name='idx_chargeback_status_received'),
            models.Index(fields=['user', 'status'],         name='idx_chargeback_user_status'),
            models.Index(fields=['transaction_id'],         name='idx_chargeback_txn'),
            models.Index(fields=['is_fraudulent'],          name='idx_chargeback_fraud'),
        ]
        verbose_name        = 'Chargeback Dispute'
        verbose_name_plural = 'Chargeback Disputes'

    def __str__(self):
        return f"Chargeback {self.dispute_id} — {self.status} — ${self.disputed_amount}"

    def mark_as_won(self, notes: str = '', resolved_by=None) -> None:
        self.status       = self.Status.WON
        self.resolved_at  = timezone.now()
        self.resolution_notes = notes
        if resolved_by:
            self.resolved_by = resolved_by
        self.save(update_fields=['status', 'resolved_at', 'resolution_notes', 'resolved_by'])

    def mark_as_lost(self, notes: str = '', resolved_by=None) -> None:
        self.status       = self.Status.LOST
        self.resolved_at  = timezone.now()
        self.resolution_notes = notes
        if resolved_by:
            self.resolved_by = resolved_by
        self.save(update_fields=['status', 'resolved_at', 'resolution_notes', 'resolved_by'])

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.RECEIVED, self.Status.INVESTIGATING, self.Status.REPRESENTED)

    @property
    def days_until_deadline(self) -> int | None:
        if not self.response_deadline:
            return None
        delta = self.response_deadline - timezone.now()
        return max(0, delta.days)


# =============================================================================
# ConversionCap
# =============================================================================

class ConversionCap(TimeStampedModel):
    """
    Enforces conversion caps per offer / advertiser / user to prevent abuse.

    Caps can be:
      - Global per offer (e.g. max 1000 completions total)
      - Per user per offer (e.g. max 1 completion per user)
      - Per IP per offer
      - Per day / week / month
    """

    class CapType(models.TextChoices):
        GLOBAL_OFFER      = 'global_offer',      'Global (whole offer)'
        PER_USER          = 'per_user',           'Per User'
        PER_IP            = 'per_ip',             'Per IP Address'
        PER_DEVICE        = 'per_device',         'Per Device'
        PER_USER_DAILY    = 'per_user_daily',     'Per User Per Day'
        PER_USER_WEEKLY   = 'per_user_weekly',    'Per User Per Week'
        PER_IP_DAILY      = 'per_ip_daily',       'Per IP Per Day'
        ADVERTISER_BUDGET = 'advertiser_budget',  'Advertiser Budget Cap'

    class Action(models.TextChoices):
        BLOCK  = 'block',  'Block conversion'
        FLAG   = 'flag',   'Flag for review'
        REDUCE = 'reduce', 'Reduce reward'
        NOTIFY = 'notify', 'Notify admin only'

    # Link to offer (offerwall app)
    offer = models.ForeignKey(
        'offerwall.Offer',
        on_delete=models.CASCADE,
        related_name='conversion_caps',
        null=True, blank=True,
    )
    # Or advertiser-level cap (no specific offer)
    advertiser_id    = models.IntegerField(null=True, blank=True, db_index=True)
    advertiser_name  = models.CharField(max_length=255, blank=True)

    cap_type         = models.CharField(max_length=30, choices=CapType.choices, db_index=True)
    cap_limit        = models.PositiveIntegerField(help_text='Maximum allowed conversions within window')
    current_count    = models.PositiveIntegerField(default=0)
    window_hours     = models.PositiveIntegerField(
        default=0,
        help_text='0 = lifetime cap, >0 = rolling window in hours',
    )
    action_on_exceed = models.CharField(max_length=10, choices=Action.choices, default=Action.BLOCK)
    is_active        = models.BooleanField(default=True)
    reset_at         = models.DateTimeField(null=True, blank=True)
    metadata         = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['offer', 'cap_type'],      name='idx_cap_offer_type'),
            models.Index(fields=['advertiser_id', 'cap_type'], name='idx_cap_adv_type'),
            models.Index(fields=['is_active'],              name='idx_cap_active'),
        ]
        verbose_name        = 'Conversion Cap'
        verbose_name_plural = 'Conversion Caps'

    def __str__(self):
        target = f"offer={self.offer_id}" if self.offer_id else f"adv={self.advertiser_id}"
        return f"Cap [{self.cap_type}] {target} — {self.current_count}/{self.cap_limit}"

    @property
    def is_exceeded(self) -> bool:
        if self.window_hours > 0 and self.reset_at and timezone.now() > self.reset_at:
            return False  # Window expired — not exceeded
        return self.current_count >= self.cap_limit

    @property
    def remaining(self) -> int:
        return max(0, self.cap_limit - self.current_count)

    def increment(self) -> bool:
        """
        Increment count. Returns True if still within cap, False if exceeded.
        Thread-safe via select_for_update.
        """
        from django.db import transaction
        with transaction.atomic():
            obj = ConversionCap.objects.select_for_update().get(pk=self.pk)
            if obj.is_exceeded:
                return False
            obj.current_count += 1
            if obj.window_hours > 0 and not obj.reset_at:
                obj.reset_at = timezone.now() + __import__('datetime').timedelta(hours=obj.window_hours)
            obj.save(update_fields=['current_count', 'reset_at'])
            self.current_count = obj.current_count
            self.reset_at = obj.reset_at
        return True

    def reset(self) -> None:
        """Reset counter (used by scheduled task)."""
        self.current_count = 0
        self.reset_at      = None
        self.save(update_fields=['current_count', 'reset_at'])
