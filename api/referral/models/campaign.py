# api/referral/models/campaign.py
# Campaign, Bonus, Contest, Reward models
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone


class ReferralCampaign(models.Model):
    """
    Time-limited referral campaigns।
    Bonus multiplier + special rates।
    ReferralSettings.active_campaign এ link করা হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True, default='')

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    # Commission multiplier during campaign
    # e.g. 2.0 = double commission rates
    bonus_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, default=1,
        validators=[MinValueValidator(Decimal('0.1')), MaxValueValidator(Decimal('10'))],
        help_text="Commission multiplier: 1 = normal, 2 = double, 1.5 = 50% extra"
    )

    # Extra signup bonus during campaign (on top of base)
    extra_signup_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Extra signup bonus on top of base settings"
    )

    # Maximum total budget for this campaign
    max_budget = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Campaign budget cap (null = unlimited)"
    )

    # Current spend
    current_spend = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Target: max referrals for this campaign
    max_referrals = models.IntegerField(
        null=True, blank=True,
        help_text="Maximum referrals cap for campaign (null = unlimited)"
    )

    current_referrals = models.IntegerField(default=0)

    # Banner/promotional image
    banner_image = models.ImageField(
        upload_to='referral/campaigns/', null=True, blank=True
    )

    # Terms and conditions
    terms = models.TextField(blank=True, default='')

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(
        default=False,
        help_text="Show in featured campaigns section"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_referral_campaigns'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['is_active', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return f"Campaign: {self.name} ({self.start_date.date()} to {self.end_date.date()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def is_currently_active(self) -> bool:
        """Campaign এখন active কিনা check করো।"""
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.start_date or now > self.end_date:
            return False
        if self.max_budget and self.current_spend >= self.max_budget:
            return False
        if self.max_referrals and self.current_referrals >= self.max_referrals:
            return False
        return True

    def remaining_budget(self) -> Decimal:
        if not self.max_budget:
            return Decimal('999999.99')
        return max(Decimal('0'), self.max_budget - self.current_spend)

    def record_spend(self, amount: Decimal):
        self.current_spend += amount
        self.current_referrals += 1
        self.save(update_fields=['current_spend', 'current_referrals'])


class ReferralBonus(models.Model):
    """
    Milestone-based bonuses within a campaign।
    e.g. 10 referrals → ৳500 bonus, 25 referrals → ৳1500 bonus
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    campaign = models.ForeignKey(
        ReferralCampaign,
        on_delete=models.CASCADE,
        related_name='bonuses'
    )

    MILESTONE_TYPE_CHOICES = [
        ('referral_count', 'Total Referrals'),
        ('active_referral_count', 'Active Referrals'),
        ('commission_earned', 'Commission Earned'),
        ('team_size', 'Team Size (all levels)'),
    ]
    milestone_type = models.CharField(
        max_length=25, choices=MILESTONE_TYPE_CHOICES, default='referral_count'
    )

    # Milestone value (e.g. 10, 25, 50 referrals)
    milestone_value = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="e.g. 10 referrals, ৳1000 commission earned"
    )

    bonus_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Bonus amount when milestone is reached"
    )

    REWARD_TYPE_CHOICES = [
        ('cash', 'Cash Bonus'),
        ('coins', 'Coins'),
        ('badge', 'Badge/Achievement'),
        ('multiplier', 'Commission Multiplier'),
    ]
    reward_type = models.CharField(
        max_length=15, choices=REWARD_TYPE_CHOICES, default='cash'
    )

    # For multiplier reward type
    multiplier_value = models.DecimalField(
        max_digits=5, decimal_places=2, default=1
    )

    # Multiplier duration in days
    multiplier_duration_days = models.IntegerField(default=0)

    title = models.CharField(max_length=200, blank=True, default='')
    description = models.CharField(max_length=500, blank=True, default='')
    icon = models.CharField(max_length=100, blank=True, default='')

    # Can a user claim this bonus multiple times?
    is_repeatable = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['milestone_value']
        indexes = [
            models.Index(fields=['campaign', 'is_active']),
        ]

    def __str__(self):
        return (
            f"Bonus({self.campaign.name}: "
            f"{self.milestone_type}={self.milestone_value} "
            f"→ ৳{self.bonus_amount})"
        )


class ReferralBonusClaim(models.Model):
    """
    User কোন bonus claim করেছে তার record।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_bonus_claims'
    )

    bonus = models.ForeignKey(
        ReferralBonus,
        on_delete=models.CASCADE,
        related_name='claims'
    )

    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    wallet_transaction_id = models.CharField(
        max_length=100, null=True, blank=True
    )

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending'
    )

    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        # By default one claim per user per bonus (unless repeatable)
        indexes = [
            models.Index(fields=['user', 'bonus']),
        ]

    def __str__(self):
        return f"BonusClaim({self.user.username} → {self.bonus_id})"


class ReferralContest(models.Model):
    """
    Referral contest — competition among referrers।
    Leaderboard + prize pool।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    rules = models.TextField(blank=True, default='')

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    prize_pool = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Total prize pool amount"
    )

    # How many positions get prizes
    leaderboard_size = models.IntegerField(
        default=10,
        help_text="Top N referrers in leaderboard"
    )

    CONTEST_TYPE_CHOICES = [
        ('most_referrals', 'Most Referrals'),
        ('most_active_referrals', 'Most Active Referrals'),
        ('highest_commission', 'Highest Commission Earned'),
        ('highest_ltv', 'Highest LTV from Referrals'),
    ]
    contest_type = models.CharField(
        max_length=25, choices=CONTEST_TYPE_CHOICES, default='most_referrals'
    )

    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('prizes_distributed', 'Prizes Distributed'),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='upcoming'
    )

    banner_image = models.ImageField(
        upload_to='referral/contests/', null=True, blank=True
    )

    is_public = models.BooleanField(
        default=True,
        help_text="Show in public leaderboard"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_referral_contests'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-start_date']

    def __str__(self):
        return f"Contest: {self.title} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def is_currently_active(self) -> bool:
        now = timezone.now()
        return self.status == 'active' and self.start_date <= now <= self.end_date

    def update_status(self):
        now = timezone.now()
        if now < self.start_date:
            new_status = 'upcoming'
        elif self.start_date <= now <= self.end_date:
            new_status = 'active'
        elif now > self.end_date and self.status not in ['prizes_distributed']:
            new_status = 'ended'
        else:
            return

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])


class ReferralReward(models.Model):
    """
    Contest prize structure।
    Rank 1 → prize_value, Rank 2 → prize_value, etc.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    contest = models.ForeignKey(
        ReferralContest,
        on_delete=models.CASCADE,
        related_name='rewards'
    )

    rank = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Position in leaderboard"
    )

    # Rank range support: rank_to allows e.g. rank 4-10 to get same prize
    rank_to = models.IntegerField(
        null=True, blank=True,
        help_text="End rank for range rewards (e.g. rank=4, rank_to=10 means 4th-10th)"
    )

    REWARD_TYPE_CHOICES = [
        ('cash', 'Cash'),
        ('coins', 'Platform Coins'),
        ('gift_card', 'Gift Card'),
        ('voucher', 'Voucher'),
        ('badge', 'Badge'),
        ('physical', 'Physical Prize'),
    ]
    reward_type = models.CharField(
        max_length=15, choices=REWARD_TYPE_CHOICES, default='cash'
    )

    reward_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Cash/coin value of reward"
    )

    reward_description = models.CharField(
        max_length=500, blank=True, default='',
        help_text="e.g. '৳5000 bKash' or 'iPhone 15'"
    )

    # Winner assignment
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contest_rewards_won'
    )

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Winner Assigned'),
        ('distributed', 'Prize Distributed'),
        ('failed', 'Distribution Failed'),
    ]
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending'
    )

    distributed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['rank']
        unique_together = ['contest', 'rank']

    def __str__(self):
        rank_str = (
            f"Rank {self.rank}-{self.rank_to}"
            if self.rank_to else f"Rank {self.rank}"
        )
        return (
            f"Reward({self.contest.title}: "
            f"{rank_str} → {self.reward_type} ৳{self.reward_value})"
        )

    def assign_winner(self, user):
        self.winner = user
        self.status = 'assigned'
        self.save(update_fields=['winner', 'status'])

    def mark_distributed(self):
        from django.utils import timezone
        self.status = 'distributed'
        self.distributed_at = timezone.now()
        self.save(update_fields=['status', 'distributed_at'])


class ContestEntry(models.Model):
    """
    Contest participant entry।
    Leaderboard data — contest শেষ হলে snapshot নেওয়া হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    contest = models.ForeignKey(
        ReferralContest,
        on_delete=models.CASCADE,
        related_name='entries'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contest_entries'
    )

    # Performance metrics
    referral_count = models.IntegerField(default=0)
    active_referral_count = models.IntegerField(default=0)
    commission_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    ltv_score = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Current rank (updated periodically)
    current_rank = models.IntegerField(null=True, blank=True)

    # Final rank (set when contest ends)
    final_rank = models.IntegerField(null=True, blank=True)

    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['contest', 'user']
        ordering = ['current_rank']
        indexes = [
            models.Index(fields=['contest', 'current_rank']),
        ]

    def __str__(self):
        return (
            f"Entry({self.user.username} in {self.contest.title}: "
            f"rank={self.current_rank})"
        )