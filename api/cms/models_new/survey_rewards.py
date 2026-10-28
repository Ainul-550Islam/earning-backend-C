# api/cms/models_new/survey_rewards.py
"""
Survey Reward Management Models
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .profile_surveys import SurveyTemplate, SurveyCompletion

User = get_user_model()


class SurveyReward(models.Model):
    """
    Individual survey reward configuration
    """
    REWARD_TYPES = [
        ('fixed', _('Fixed Amount')),
        ('tiered', _('Tiered Based on Quality')),
        ('performance', _('Performance Based')),
        ('bonus', _('Bonus Reward')),
    ]
    
    REWARD_STATUS = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('expired', _('Expired')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    survey = models.ForeignKey(SurveyTemplate, on_delete=models.CASCADE, related_name='reward_configs')
    name = models.CharField(_("Reward Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    
    # Reward configuration
    reward_type = models.CharField(_("Reward Type"), max_length=20, choices=REWARD_TYPES)
    base_amount = models.DecimalField(_("Base Amount"), max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    currency = models.CharField(max_length=10, default='USD')
    
    # Tiered rewards (for tiered type)
    min_quality_for_bonus = models.DecimalField(
        _("Min Quality for Bonus"), max_digits=5, decimal_places=2, 
        null=True, blank=True, help_text=_("Minimum quality score to earn bonus")
    )
    bonus_amount = models.DecimalField(
        _("Bonus Amount"), max_digits=10, decimal_places=2, default=0.00
    )
    
    # Performance rewards
    completion_time_threshold = models.PositiveIntegerField(
        _("Completion Time Threshold (seconds)"), null=True, blank=True,
        help_text=_("Complete within this time to earn full reward")
    )
    speed_bonus_amount = models.DecimalField(
        _("Speed Bonus Amount"), max_digits=10, decimal_places=2, default=0.00
    )
    
    # Limits and conditions
    max_total_payout = models.DecimalField(
        _("Max Total Payout"), max_digits=15, decimal_places=2, null=True, blank=True,
        help_text=_("Maximum total payout for this reward configuration")
    )
    daily_payout_limit = models.DecimalField(
        _("Daily Payout Limit"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    
    # Status and timing
    status = models.CharField(_("Status"), max_length=20, choices=REWARD_STATUS, default='active')
    start_date = models.DateTimeField(_("Start Date"), null=True, blank=True)
    end_date = models.DateTimeField(_("End Date"), null=True, blank=True)
    
    # Statistics
    total_paid = models.DecimalField(_("Total Paid"), max_digits=15, decimal_places=2, default=0.00)
    times_paid = models.PositiveIntegerField(_("Times Paid"), default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Survey Reward")
        verbose_name_plural = _("Survey Rewards")
        indexes = [
            models.Index(fields=['survey', 'status']),
            models.Index(fields=['reward_type']),
            models.Index(fields=['status', 'start_date']),
        ]
    
    def __str__(self):
        return f"{self.survey.title} - {self.name}"
    
    def clean(self):
        """Validate reward configuration"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_("End date must be after start date"))
        
        if self.reward_type == 'tiered' and not self.min_quality_for_bonus:
            raise ValidationError(_("Tiered rewards require minimum quality for bonus"))
        
        if self.reward_type == 'performance' and not self.completion_time_threshold:
            raise ValidationError(_("Performance rewards require completion time threshold"))
    
    def is_active(self) -> bool:
        """Check if reward is currently active"""
        if self.status != 'active':
            return False

        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False

        if self.max_total_payout and self.total_paid >= self.max_total_payout:
            return False

        return True

    def save(self, *args, **kwargs):
        # Coerce VirtualCurrency FK objects to their symbol string so the
        # CharField never receives an ORM instance.
        if hasattr(self.currency, 'symbol'):
            self.currency = self.currency.symbol
        elif hasattr(self.currency, 'pk') and not isinstance(self.currency, str):
            self.currency = str(self.currency)
        super().save(*args, **kwargs)
    
    def calculate_reward(self, completion: SurveyCompletion) -> Decimal:
        """Calculate reward amount for a survey completion"""
        if not self.is_active():
            return Decimal('0')
        
        reward_amount = self.base_amount
        
        # Quality bonus for tiered rewards
        if (self.reward_type == 'tiered' and 
            completion.quality_score and 
            completion.quality_score >= self.min_quality_for_bonus):
            reward_amount += self.bonus_amount
        
        # Speed bonus for performance rewards
        if (self.reward_type == 'performance' and 
            self.completion_time_threshold and 
            completion.time_spent_seconds <= self.completion_time_threshold):
            reward_amount += self.speed_bonus_amount

        # Store base reward before penalties
        base_reward = reward_amount

        # Speed penalty: if completion was too fast (suspicious), apply 50% penalty
        if (self.completion_time_threshold and completion.time_spent_seconds and
                completion.time_spent_seconds < self.completion_time_threshold * 0.3):
            reward_amount = base_reward * Decimal('0.5')

        # Attention check penalties: 10% per failed check
        failed_checks = getattr(completion, 'failed_attention_checks', 0) or 0
        if failed_checks > 0:
            penalty_rate = Decimal(str(failed_checks * 10)) / Decimal('100')
            reward_amount = base_reward * (Decimal('1') - penalty_rate)

        return max(Decimal('0'), reward_amount)

        # Apply penalties for quality issues
        if completion.flagged_for_speeding:
            reward_amount *= Decimal('0.5')  # 50% penalty
        
        if completion.failed_attention_checks > 0:
            penalty_per_check = Decimal('0.1')
            total_penalty = penalty_per_check * completion.failed_attention_checks
            reward_amount *= (Decimal('1') - min(total_penalty, Decimal('0.5')))  # Max 50% penalty
        
        return max(reward_amount, Decimal('0'))
    
    def update_statistics(self, amount: Decimal):
        """Update reward statistics"""
        self.total_paid += amount
        self.times_paid += 1
        self.save(update_fields=['total_paid', 'times_paid'])


class RewardTransaction(models.Model):
    """
    Individual reward transactions
    """
    TRANSACTION_TYPES = [
        ('earned', _('Reward Earned')),
        ('bonus', _('Bonus Awarded')),
        ('penalty', _('Penalty Applied')),
        ('adjustment', _('Manual Adjustment')),
        ('refund', _('Refund')),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('paid', _('Paid')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reward_transactions')
    survey_completion = models.ForeignKey(
        SurveyCompletion, on_delete=models.CASCADE, related_name='reward_transactions', null=True, blank=True
    )
    reward_config = models.ForeignKey(
        SurveyReward, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    
    # Transaction details
    transaction_type = models.CharField(_("Transaction Type"), max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    
    # Description and metadata
    description = models.TextField(_("Description"))
    reference_id = models.CharField(_("Reference ID"), max_length=100, blank=True)
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    
    # Status and processing
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_at = models.DateTimeField(_("Processed At"), null=True, blank=True)
    paid_at = models.DateTimeField(_("Paid At"), null=True, blank=True)
    
    # Review information
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_reward_transactions'
    )
    review_notes = models.TextField(_("Review Notes"), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Reward Transaction")
        verbose_name_plural = _("Reward Transactions")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['survey_completion']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"
    
    def approve(self, reviewer=None, notes=""):
        """Approve the transaction"""
        self.status = 'approved'
        self.processed_at = timezone.now()
        if reviewer:
            self.reviewed_by = reviewer
        if notes:
            self.review_notes = notes
        self.save()
    
    def mark_paid(self):
        """Mark transaction as paid"""
        if self.status == 'approved':
            self.status = 'paid'
            self.paid_at = timezone.now()
            self.save()
    
    def cancel(self, reason=""):
        """Cancel the transaction"""
        self.status = 'cancelled'
        self.review_notes = reason
        self.save()


class RewardPool(models.Model):
    """
    Reward pool for managing survey rewards budget
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Pool Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    
    # Budget configuration
    total_budget = models.DecimalField(_("Total Budget"), default=0, max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    allocated_amount = models.DecimalField(_("Allocated Amount"), max_digits=15, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(_("Paid Amount"), max_digits=15, decimal_places=2, default=Decimal("0.00"))
    
    # Pool configuration
    auto_refill = models.BooleanField(_("Auto Refill"), default=False)
    refill_amount = models.DecimalField(
        _("Refill Amount"), max_digits=15, decimal_places=2, null=True, blank=True
    )
    refill_threshold = models.DecimalField(
        _("Refill Threshold"), max_digits=15, decimal_places=2, null=True, blank=True
    )
    
    # Status
    is_active = models.BooleanField(_("Active"), default=True)
    start_date = models.DateTimeField(_("Start Date"), null=True, blank=True)
    end_date = models.DateTimeField(_("End Date"), null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Reward Pool")
        verbose_name_plural = _("Reward Pools")
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        currency = self.currency
        if hasattr(currency, 'symbol'):
            currency = currency.symbol
        return f"{self.name} ({currency if currency else 'USD'})"

    def save(self, *args, **kwargs):
        # Coerce VirtualCurrency objects → symbol string before writing to CharField.
        if hasattr(self.currency, 'symbol'):
            self.currency = self.currency.symbol
        elif hasattr(self.currency, 'pk') and not isinstance(self.currency, str):
            self.currency = str(self.currency)
        super().save(*args, **kwargs)

    @property
    def remaining_budget(self) -> Decimal:
        """Calculate remaining budget = total_budget - allocated_amount."""
        total     = Decimal(str(self.total_budget     if self.total_budget     is not None else 0))
        allocated = Decimal(str(self.allocated_amount if self.allocated_amount is not None else 0))
        return total - allocated
    
    @property
    def available_budget(self) -> Decimal:
        """Calculate available budget = total_budget - allocated_amount - paid_amount."""
        total     = Decimal(str(self.total_budget     or 0))
        allocated = Decimal(str(self.allocated_amount or 0))
        paid      = Decimal(str(getattr(self, 'paid_amount', 0) or 0))
        return total - allocated - paid
    
    def allocate_funds(self, amount: Decimal) -> bool:
        """Allocate funds from pool"""
        if self.available_budget >= amount:
            self.allocated_amount = Decimal(str(self.allocated_amount or 0)) + amount
            self.save(update_fields=['allocated_amount'])
            return True
        return False
    
    def release_funds(self, amount: Decimal):
        """Release allocated funds back to pool"""
        self.allocated_amount = max(self.allocated_amount - amount, Decimal('0'))
        self.save(update_fields=['allocated_amount'])
    
    def mark_paid(self, amount: Decimal):
        """Mark funds as paid and trigger auto-refill if remaining budget hits threshold."""
        amount = Decimal(str(amount))
        # Check refill BEFORE deducting so the pre-payment remaining triggers it.
        should_refill = (
            self.auto_refill
            and self.refill_amount
            and self.refill_threshold is not None
            and self.remaining_budget <= Decimal(str(self.refill_threshold))
        )
        self.paid_amount = Decimal(str(self.paid_amount or 0)) + amount
        self.allocated_amount = max(
            Decimal(str(self.allocated_amount or 0)) - amount, Decimal("0")
        )
        if should_refill:
            self.total_budget = Decimal(str(self.total_budget or 0)) + Decimal(str(self.refill_amount))
            self.save(update_fields=["paid_amount", "allocated_amount", "total_budget"])
        else:
            self.save(update_fields=["paid_amount", "allocated_amount"])


# Alias used in tests
Transaction = RewardTransaction
