# api/referral/models/tree.py
# Multi-level referral tree models
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid


class ReferralRelationship(models.Model):
    """
    Explicit referral relationship — referrer, referred, level (1/2/3), joined_at।
    ReferralChain এর নতুন detailed version।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_relationships_as_referrer',
        help_text="যে refer করেছে (ancestor/beneficiary)"
    )
    referred = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_relationships_as_referred',
        help_text="যাকে refer করা হয়েছে (descendant/earner)"
    )

    LEVEL_CHOICES = [
        (1, 'Level 1 — Direct'),
        (2, 'Level 2 — Indirect'),
        (3, 'Level 3 — Deep'),
    ]
    level = models.IntegerField(
        choices=LEVEL_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )

    # Commission rate snapshot at time of relationship creation
    commission_rate_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Rate at time of relationship creation"
    )

    # Total commission earned through this relationship
    total_commission_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'referral'
        unique_together = ['referrer', 'referred', 'level']
        indexes = [
            models.Index(fields=['referrer', 'level']),
            models.Index(fields=['referred']),
            models.Index(fields=['joined_at']),
        ]

    def __str__(self):
        return (
            f"L{self.level}: {self.referrer.username} "
            f"→ {self.referred.username}"
        )


class ReferralTree(models.Model):
    """
    Root user এর সম্পূর্ণ referral tree এর summary।
    প্রতিটি user এর নিজস্ব tree আছে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    root_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_tree',
        help_text="Tree এর মূল user"
    )

    depth = models.IntegerField(
        default=0,
        help_text="Tree এর maximum depth (0 = no referrals)"
    )

    total_members = models.IntegerField(
        default=0,
        help_text="সব level মিলিয়ে মোট referred members"
    )

    # Per-level counts
    level1_count = models.IntegerField(default=0)
    level2_count = models.IntegerField(default=0)
    level3_count = models.IntegerField(default=0)

    # Earnings summary
    total_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    level1_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    level2_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    level3_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Last rebuild timestamp
    last_rebuilt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'

    def __str__(self):
        return (
            f"Tree({self.root_user.username}: "
            f"{self.total_members} members, "
            f"৳{self.total_earned})"
        )

    def refresh_counts(self):
        """Tree counts and earnings recalculate করো।"""
        from django.db.models import Sum, Count, Q
        from .core import ReferralEarning

        rels = ReferralRelationship.objects.filter(referrer=self.root_user)

        self.level1_count = rels.filter(level=1).count()
        self.level2_count = rels.filter(level=2).count()
        self.level3_count = rels.filter(level=3).count()
        self.total_members = self.level1_count + self.level2_count + self.level3_count
        self.depth = 3 if self.level3_count > 0 else (
            2 if self.level2_count > 0 else (
                1 if self.level1_count > 0 else 0
            )
        )

        earnings = ReferralEarning.objects.filter(
            referrer=self.root_user
        ).aggregate(
            total=Sum('amount'),
            l1=Sum('amount', filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(level=1)),
            l2=Sum('amount', filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(level=2)),
            l3=Sum('amount', filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(level=3)),
        )

        self.total_earned = earnings['total'] or Decimal('0')
        self.level1_earned = earnings['l1'] or Decimal('0')
        self.level2_earned = earnings['l2'] or Decimal('0')
        self.level3_earned = earnings['l3'] or Decimal('0')

        from django.utils import timezone
        self.last_rebuilt_at = timezone.now()
        self.save()


class ReferralTreeSnapshot(models.Model):
    """
    Periodic tree snapshot — analytics ও history এর জন্য।
    Weekly বা Monthly Celery task দিয়ে নেওয়া হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    tree = models.ForeignKey(
        ReferralTree,
        on_delete=models.CASCADE,
        related_name='snapshots'
    )

    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    period = models.CharField(
        max_length=10, choices=PERIOD_CHOICES, default='weekly'
    )

    # JSON snapshot of tree state at this point in time
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Full tree state: counts, earnings, top members, etc."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tree', '-created_at']),
            models.Index(fields=['period', '-created_at']),
        ]

    def __str__(self):
        return (
            f"Snapshot({self.tree.root_user.username} "
            f"- {self.period} @ {self.created_at.date()})"
        )


class ReferralLevel(models.Model):
    """
    Commission level configuration।
    ReferralSettings থেকে আলাদা করে level-specific rules রাখা যায়।
    Admin এখান থেকে per-level configuration করতে পারবে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    level_number = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Level number (1 = direct, 2 = indirect, etc.)"
    )

    name = models.CharField(
        max_length=100, default='',
        help_text="Level name (e.g. 'Direct', 'Silver', 'Gold')"
    )

    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Commission percentage for this level"
    )

    max_depth = models.IntegerField(
        default=3,
        help_text="Maximum depth this level applies to"
    )

    # Minimum activity requirement to earn at this level
    min_activity_requirement = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Minimum earning by referred user to trigger commission"
    )

    # Color for UI display
    color_code = models.CharField(
        max_length=7, default='#4CAF50',
        help_text="Hex color code for UI badge"
    )

    icon = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Icon name (e.g. FontAwesome class)"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['level_number']

    def __str__(self):
        return (
            f"Level {self.level_number} "
            f"({self.name or 'L' + str(self.level_number)}): "
            f"{self.commission_rate}%"
        )


class ReferralCode(models.Model):
    """
    User-specific referral codes।
    Multiple codes per user supported।
    Click + conversion tracking included।
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
        related_name='referral_codes'
    )

    # System-generated unique code
    code = models.CharField(
        max_length=20, unique=True, db_index=True
    )

    # Custom vanity code (optional, user-defined)
    custom_code = models.CharField(
        max_length=30, unique=True, null=True, blank=True,
        help_text="User-defined custom code"
    )

    # Source/campaign tagging
    source_tag = models.CharField(
        max_length=100, blank=True, default='',
        help_text="Where this code is being shared (social, email, etc.)"
    )

    # Campaign this code is tied to
    campaign = models.ForeignKey(
        'referral.ReferralCampaign',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='codes',
        help_text="Optional campaign this code is linked to"
    )

    # Analytics
    clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)

    # Revenue generated by this specific code
    revenue_generated = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(
        default=False,
        help_text="User এর primary code (first one)"
    )

    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['code']),
            models.Index(fields=['custom_code']),
        ]

    def __str__(self):
        display = self.custom_code or self.code
        return f"Code({self.user.username}: {display})"

    @property
    def conversion_rate(self) -> float:
        if self.clicks == 0:
            return 0.0
        return round((self.conversions / self.clicks) * 100, 2)

    def record_click(self, is_unique: bool = True):
        self.clicks += 1
        if is_unique:
            self.unique_clicks += 1
        self.save(update_fields=['clicks', 'unique_clicks'])

    def record_conversion(self):
        self.conversions += 1
        self.save(update_fields=['conversions'])

    def get_active_code(self) -> str:
        """Custom code থাকলে সেটা, নইলে system code।"""
        return self.custom_code or self.code

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at