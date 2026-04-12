# =============================================================================
# api/promotions/models.py
# Bulletproof Django Models - Full Defensive Code
# =============================================================================

import hashlib
import uuid
from decimal import Decimal, ROUND_DOWN

from django.core.exceptions import ValidationError
from django.core.validators import (
    MinValueValidator, MaxValueValidator,
    MinLengthValidator, URLValidator,
    RegexValidator,
)
from django.db import models, transaction
from django.db.models import F, Q, CheckConstraint, UniqueConstraint
from django.utils import timezone as tz_module
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings


# =============================================================================
# ── ABSTRACT BASE MODELS ──────────────────────────────────────────────────────
# =============================================================================

class TimestampedModel(models.Model):
    """সব মডেলের জন্য created_at ও updated_at অটোমেটিক।"""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """Soft delete করা রেকর্ড বাদ দিয়ে query করে।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(TimestampedModel):
    """রেকর্ড ডিলিট না করে is_deleted=True করে রাখার সিস্টেম।"""
    is_deleted  = models.BooleanField(default=False, db_index=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)
    deleted_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',)

    objects     = SoftDeleteManager()
    all_objects = models.Manager()  # Soft-deleted সহ সবকিছু

    def delete(self, deleted_by=None, *args, **kwargs):
        """Hard delete এর বদলে soft delete।"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def hard_delete(self, *args, **kwargs):
        """সত্যিকারের ডিলিট - শুধু super admin করতে পারবে।"""
        super().delete(*args, **kwargs)

    class Meta:
        abstract = True


# =============================================================================
# ── ১. SYSTEM FOUNDATION ─────────────────────────────────────────────────────
# =============================================================================

class PromotionCategory(SoftDeleteModel):
    """অফারের ধরণ: Social, Apps, Web, Surveys"""

    class CategoryType(models.TextChoices):
        SOCIAL   = 'social',   _('Social Media')
        APPS     = 'apps',     _('Mobile Apps')
        WEB      = 'web',      _('Web Tasks')
        SURVEYS  = 'surveys',  _('Surveys')

    name         = models.CharField(
        max_length=50,
        unique=True,
        choices=CategoryType.choices,
        verbose_name=_('ক্যাটেগরি নাম'),
    )
    description  = models.TextField(blank=True, default='')
    icon_url     = models.URLField(blank=True, default='', null=True)
    sort_order   = models.PositiveSmallIntegerField(default=0)
    is_active    = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table            = 'promotion_category'
        verbose_name        = _('Promotion Category')
        verbose_name_plural = _('Promotion Categories')
        ordering            = ['sort_order', 'name']

    def __str__(self):
        return self.get_name_display()

    def clean(self):
        self.name = self.name.lower().strip()


# ─────────────────────────────────────────────────────────────────────────────

class Platform(SoftDeleteModel):
    """মিডিয়া প্ল্যাটফর্ম: YouTube, Facebook, TikTok ইত্যাদি"""

    class PlatformType(models.TextChoices):
        YOUTUBE    = 'youtube',    _('YouTube')
        FACEBOOK   = 'facebook',   _('Facebook')
        INSTAGRAM  = 'instagram',  _('Instagram')
        TIKTOK     = 'tiktok',     _('TikTok')
        PLAY_STORE = 'play_store', _('Google Play Store')
        APP_STORE  = 'app_store',  _('Apple App Store')
        TWITTER    = 'twitter',    _('Twitter / X')
        OTHER      = 'other',      _('Other')

    name       = models.CharField(
        max_length=50,
        unique=True,
        choices=PlatformType.choices, null=True, blank=True)
    base_url   = models.URLField(blank=True, default='', null=True)
    icon_url   = models.URLField(blank=True, default='', null=True)
    is_active  = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table            = 'platform'
        verbose_name        = _('Platform')
        verbose_name_plural = _('Platforms')
        ordering            = ['name']

    def __str__(self):
        return self.get_name_display()


# ─────────────────────────────────────────────────────────────────────────────

class RewardPolicy(TimestampedModel):
    """দেশভিত্তিক পেমেন্ট রেট। যেমন: USA → $0.50, BD → $0.05"""

    country_code = models.CharField(
        max_length=2,
        validators=[RegexValidator(r'^[A-Z]{2}$', 'ISO 3166-1 alpha-2 কোড দিন (যেমন: US, BD)')],
        help_text=_('ISO 3166-1 alpha-2 country code (e.g. US, BD, IN)'),
    )
    category = models.ForeignKey(
        PromotionCategory,
        on_delete=models.PROTECT,
        related_name='reward_policies', null=True, blank=True)
    rate_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0001'))],
        help_text=_('USD তে পার-ট্র্যাক রেট'),
    )
    min_payout_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table            = 'reward_policy'
        verbose_name        = _('Reward Policy')
        verbose_name_plural = _('Reward Policies')
        # একই দেশ + ক্যাটেগরি জন্য একটির বেশি active policy থাকতে পারবে না
        constraints = [
            UniqueConstraint(
                fields=['country_code', 'category'],
                condition=Q(is_active=True),
                name='uq_active_reward_policy_per_country_category',
            ),
        ]
        ordering = ['country_code', 'category']

    def __str__(self):
        return f"{self.country_code} | {self.category} | ${self.rate_usd}"

    def clean(self):
        self.country_code = self.country_code.upper().strip()
        if self.min_payout_usd and self.rate_usd and self.min_payout_usd < self.rate_usd:
            raise ValidationError({
                'min_payout_usd': _('Minimum payout অবশ্যই rate এর চেয়ে বেশি বা সমান হতে হবে।')
            })


# ─────────────────────────────────────────────────────────────────────────────

class AdCreative(TimestampedModel):
    """বিজ্ঞাপনের ইমেজ, থাম্বনেইল বা ভিডিও মেটাডাটা"""

    class CreativeType(models.TextChoices):
        IMAGE   = 'image',   _('Image')
        VIDEO   = 'video',   _('Video')
        BANNER  = 'banner',  _('Banner')

    campaign      = models.ForeignKey(
        'Campaign',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='creatives',)
    type          = models.CharField(max_length=10, choices=CreativeType.choices, null=True, blank=True)
    file_url      = models.URLField(null=True, blank=True)
    thumbnail_url = models.URLField(blank=True, default='', null=True)
    title         = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(3)],
    )
    duration_sec  = models.PositiveIntegerField(
        help_text=_('শুধু ভিডিওর জন্য, সেকেন্ডে'),
        validators=[MaxValueValidator(3600)],  # সর্বোচ্চ ১ ঘণ্টা
    )
    is_approved   = models.BooleanField(default=False)

    class Meta:
        db_table = 'ad_creative'
        verbose_name        = _('Ad Creative')
        verbose_name_plural = _('Ad Creatives')
        indexes = [
            models.Index(fields=['campaign', 'type']),
        ]

    def __str__(self):
        return f"{self.campaign_id} | {self.type} | {self.title[:40]}"

    def clean(self):
        # ভিডিও ছাড়া অন্য টাইপে duration_sec থাকা উচিত নয়
        if self.type != self.CreativeType.VIDEO and self.duration_sec:
            raise ValidationError({
                'duration_sec': _('duration_sec শুধু video type এর জন্য প্রযোজ্য।')
            })
        if self.type == self.CreativeType.VIDEO and not self.duration_sec:
            raise ValidationError({
                'duration_sec': _('Video creative এর জন্য duration_sec আবশ্যক।')
            })


# ─────────────────────────────────────────────────────────────────────────────

class CurrencyRate(models.Model):
    """বিশ্বের মুদ্রার বিনিময় হার — প্রতিদিন Cron Job দ্বারা আপডেট।"""

    class RateSource(models.TextChoices):
        OPEN_EXCHANGE = 'open_exchange_rates', _('Open Exchange Rates')
        FIXER         = 'fixer',               _('Fixer.io')
        MANUAL        = 'manual',              _('Manual Entry')

    from_currency = models.CharField(
        max_length=3,
        default='USD',
        validators=[RegexValidator(r'^[A-Z]{3}$', 'ISO 4217 currency code দিন (e.g. USD)')],
    )
    to_currency = models.CharField(
        max_length=3,
        default='BDT',
        validators=[RegexValidator(r'^[A-Z]{3}$', 'ISO 4217 currency code দিন (e.g. BDT)')],
    )
    rate = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('1.0'),
        validators=[MinValueValidator(Decimal('0.00000001'))],
    )
    source     = models.CharField(
        max_length=30,
        choices=RateSource.choices,
        default=RateSource.OPEN_EXCHANGE,)
    fetched_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table            = 'currency_rate'
        verbose_name        = _('Currency Rate')
        verbose_name_plural = _('Currency Rates')
        # প্রতি pair এর জন্য শুধু একটি সর্বশেষ রেট — application layer এ enforce করুন
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', '-fetched_at']),
        ]
        # constraints = [
        #     models.CheckConstraint(
        #         check=models.Q(from_currency__ne=models.F('to_currency')),
        #         name='chk_currency_rate_different_currencies',
        #     ),
        # ]

    def __str__(self):
        return f"1 {self.from_currency} = {self.rate} {self.to_currency}"

    def clean(self):
        self.from_currency = self.from_currency.upper().strip()
        self.to_currency   = self.to_currency.upper().strip()
        if self.from_currency == self.to_currency:
            raise ValidationError(_('from_currency এবং to_currency একই হতে পারবে না।'))

    @classmethod
    def get_latest_rate(cls, from_currency: str, to_currency: str) -> 'CurrencyRate | None':
        """সর্বশেষ রেট সহজে পাওয়ার helper method।"""
        return (
            cls.objects
            .filter(from_currency=from_currency.upper(), to_currency=to_currency.upper())
            .order_by('-fetched_at')
            .first()
        )

    def convert(self, amount: Decimal) -> Decimal:
        """নির্দিষ্ট amount convert করে ফেরত দেয়।"""
        return (amount * self.rate).quantize(Decimal('0.01'), rounding=ROUND_DOWN)


# =============================================================================
# ── ২. CAMPAIGN MANAGEMENT (ADVERTISER SIDE) ─────────────────────────────────
# =============================================================================

class Campaign(SoftDeleteModel):
    """মূল Campaign মডেল — বাজেট, প্রফিট, টাইমলাইন সব এখানে।"""

    class Status(models.TextChoices):
        DRAFT      = 'draft',      _('Draft')
        PENDING    = 'pending',    _('Pending Review')
        ACTIVE     = 'active',     _('Active')
        PAUSED     = 'paused',     _('Paused')
        COMPLETED  = 'completed',  _('Completed')
        CANCELLED  = 'cancelled',  _('Cancelled')

    # ─── Ownership ──────────────────────────────────────────────────────────
    advertiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name=_('Advertiser'),
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        help_text=_('Public-facing unique ID'),
    )

    # ─── Basic Info ─────────────────────────────────────────────────────────
    title       = models.CharField(
        max_length=200,
        default='',
        blank=True,
        validators=[MinLengthValidator(5)],
    )
    description = models.TextField(blank=True, default='')
    category    = models.ForeignKey(
        PromotionCategory,
        on_delete=models.PROTECT,
        related_name='campaigns',
        null=True, blank=True)
    platform = models.ForeignKey(
        Platform,
        on_delete=models.PROTECT,
        related_name='campaigns',
        null=True,
        blank=True,
    )
    target_url  = models.URLField(
        validators=[URLValidator(schemes=['http', 'https'])],
        blank=True,
        default='',
    )

    # ─── Budget & Finance ───────────────────────────────────────────────────
    total_budget_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text=_('মোট বাজেট USD তে'),
    )
    spent_usd = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    profit_margin = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
        help_text=_('Admin profit percentage (%)'),
    )

    # ─── Slot Management ────────────────────────────────────────────────────
    total_slots  = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(1), MaxValueValidator(1_000_000)],
        help_text=_('কতজন worker কাজ করতে পারবে'),
    )
    filled_slots = models.PositiveIntegerField(default=0)

    # ─── Status ─────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,)
    rejection_reason = models.TextField(blank=True, default='')
    # ── Frontend Display Fields ──────────────────────────────────────────────
    bonus_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    promo_type       = models.CharField(max_length=20, default='bonus',
                    choices=[('bonus','Bonus'),('yield','Yield'),('fraud','Fraud'),
                             ('seasonal','Seasonal'),('referral','Referral')])
    traffic_monitor  = models.BooleanField(default=True)
    yield_optimization = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    risk_level = models.CharField(max_length=10, default='LOW', choices=[('LOW','Low'),('SAFE','Safe'),('MEDIUM','Medium'),('HIGH','High')])
    risk_score = models.PositiveSmallIntegerField(default=0)
    verified = models.BooleanField(default=False)
    sparkline_data = models.JSONField(default=list, blank=True)

    class Meta:
        db_table            = 'campaign'
        verbose_name        = _('Campaign')
        verbose_name_plural = _('Campaigns')
        indexes = [
            models.Index(fields=['advertiser', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
        # constraints = [
        #     CheckConstraint(
        #         condition=models.Q(spent_usd__lte=models.F('total_budget_usd')),
        #         name='chk_campaign_spent_not_exceed_budget',
        #     ),
        #     CheckConstraint(
        #         condition=models.Q(filled_slots__lte=models.F('total_slots')),
        #         name='chk_campaign_filled_not_exceed_total_slots',
        #     ),
        #     CheckConstraint(
        #         condition=models.Q(total_budget_usd__gt=0),
        #         name='chk_campaign_budget_positive',
        #     ),
        # ]

    def __str__(self):
        return f"[{self.status.upper()}] {self.title}"

    def clean(self):
        if self.spent_usd and self.total_budget_usd:
            if self.spent_usd > self.total_budget_usd:
                raise ValidationError(_('spent_usd বাজেটের বেশি হতে পারবে না।'))
        if self.filled_slots and self.total_slots:
            if self.filled_slots > self.total_slots:
                raise ValidationError(_('filled_slots মোট slots এর বেশি হতে পারবে না।'))

    @property
    def remaining_budget(self) -> Decimal:
        return self.total_budget_usd - self.spent_usd

    @property
    def is_full(self) -> bool:
        return self.filled_slots >= self.total_slots

    @property
    def fill_percentage(self) -> float:
        if self.total_slots == 0:
            return 0.0
        return round((self.filled_slots / self.total_slots) * 100, 2)

    @transaction.atomic
    def increment_filled_slot(self) -> bool:
        """Race condition ছাড়া একটি slot নিরাপদে বাড়ানোর method।"""
        updated = (
            Campaign.objects
            .filter(pk=self.pk, filled_slots__lt=F('total_slots'))
            .update(filled_slots=F('filled_slots') + 1)
        )
        if updated:
            self.refresh_from_db(fields=['filled_slots'])
        return bool(updated)


# ─────────────────────────────────────────────────────────────────────────────

class TargetingCondition(TimestampedModel):
    """Campaign এর টার্গেটিং — লোকেশন, ডিভাইস, ইউজার লেভেল।"""

    campaign = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name='targeting',
        primary_key=True,)
    # JSON arrays — application layer এ validate করতে হবে
    countries = models.JSONField(
        default=list,
        blank=True,
        help_text=_('ISO alpha-2 country codes. e.g. ["US","BD","IN"]'),
    )
    devices = models.JSONField(
        default=list,
        help_text=_('["mobile","desktop","tablet"]'),
    )
    os_types = models.JSONField(
        default=list,
        help_text=_('["android","ios","windows","macos"]'),
    )
    min_user_level = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    max_user_level = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    min_reputation_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
    )

    class Meta:
        db_table = 'targeting_condition'
        verbose_name        = _('Targeting Condition')
        verbose_name_plural = _('Targeting Conditions')
        # constraints = [
        #     CheckConstraint(
        #         condition=models.Q(min_user_level__lte=models.F('max_user_level')),
        #         name='chk_targeting_user_level_range_valid',
        #     ),
        # ]

    def __str__(self):
        return f"Targeting for Campaign #{self.campaign_id}"

    def clean(self):
        if self.min_user_level > self.max_user_level:
            raise ValidationError(_('min_user_level অবশ্যই max_user_level এর চেয়ে কম বা সমান হতে হবে।'))

        _valid_devices = {'mobile', 'desktop', 'tablet'}
        if self.devices:
            invalid = set(self.devices) - _valid_devices
            if invalid:
                raise ValidationError({'devices': _(f'Invalid device types: {invalid}')})

        _valid_os = {'android', 'ios', 'windows', 'macos', 'linux'}
        if self.os_types:
            invalid = set(self.os_types) - _valid_os
            if invalid:
                raise ValidationError({'os_types': _(f'Invalid OS types: {invalid}')})


# ─────────────────────────────────────────────────────────────────────────────

class TaskStep(TimestampedModel):
    """একটি Campaign এর ভেতরে কতগুলো ধাপ আছে তার তালিকা।"""

    class ProofType(models.TextChoices):
        SCREENSHOT = 'screenshot', _('Screenshot')
        LINK       = 'link',       _('Link / URL')
        TEXT       = 'text',       _('Text Answer')
        VIDEO      = 'video',      _('Screen Recording')

    campaign     = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='steps', null=True, blank=True)
    step_order   = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    instruction  = models.TextField(
        validators=[MinLengthValidator(10)],
        help_text=_('ইউজারকে কী করতে হবে তার বিস্তারিত নির্দেশনা'),
    )
    proof_type   = models.CharField(max_length=15, choices=ProofType.choices, null=True, blank=True)
    is_required  = models.BooleanField(default=True)
    hint_text    = models.TextField(blank=True, default='')

    class Meta:
        db_table            = 'task_step'
        verbose_name        = _('Task Step')
        verbose_name_plural = _('Task Steps')
        # একই campaign এ duplicate step_order থাকতে পারবে না
        constraints = [
            UniqueConstraint(
                fields=['campaign', 'step_order'],
                name='uq_task_step_order_per_campaign',
            ),
        ]
        ordering = ['step_order']

    def __str__(self):
        return f"Campaign #{self.campaign_id} | Step {self.step_order}"


# ─────────────────────────────────────────────────────────────────────────────

class TaskLimit(TimestampedModel):
    """Spam Protection — IP/Device/User পার লিমিট।"""

    campaign        = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name='limits',
        primary_key=True,)
    max_per_ip      = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    max_per_device  = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    max_per_user    = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    cooldown_hours  = models.PositiveSmallIntegerField(
        default=24,
        validators=[MaxValueValidator(8760)],  # সর্বোচ্চ ১ বছর
        help_text=_('পরবর্তী submission এর আগে কতক্ষণ অপেক্ষা করতে হবে'),
    )

    class Meta:
        db_table = 'task_limit'
        verbose_name        = _('Task Limit')
        verbose_name_plural = _('Task Limits')

    def __str__(self):
        return f"Limits for Campaign #{self.campaign_id}"


# ─────────────────────────────────────────────────────────────────────────────

class BonusPolicy(TimestampedModel):
    """কাজের গুণমান ভালো হলে অটোমেটিক বোনাস লজিক।"""

    class ConditionType(models.TextChoices):
        APPROVAL_RATE = 'approval_rate', _('Approval Rate')
        SPEED         = 'speed',         _('Completion Speed')
        STREAK        = 'streak',        _('Consecutive Approvals')

    campaign        = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='bonus_policies',
        null=True, blank=True,)
    condition_type  = models.CharField(max_length=20, choices=ConditionType.choices, null=True, blank=True)
    threshold_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_('যেমন: 95 মানে ৯৫% approval rate'),
    )
    bonus_percent   = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('200')),  # সর্বোচ্চ ২০০% বোনাস
        ],
        help_text=_('Base reward এর উপর কত % বোনাস দেওয়া হবে'),
    )
    is_active       = models.BooleanField(default=True)
    description     = models.TextField(blank=True, default='')

    class Meta:
        db_table            = 'bonus_policy'
        verbose_name        = _('Bonus Policy')
        verbose_name_plural = _('Bonus Policies')
        # একই campaign এ duplicate condition_type থাকতে পারবে না
        constraints = [
            UniqueConstraint(
                fields=['campaign', 'condition_type'],
                condition=Q(is_active=True),
                name='uq_active_bonus_policy_per_campaign_condition',
            ),
        ]

    def __str__(self):
        return f"Campaign #{self.campaign_id} | {self.condition_type} → +{self.bonus_percent}%"


# ─────────────────────────────────────────────────────────────────────────────

class CampaignSchedule(TimestampedModel):
    """Campaign কখন শুরু এবং কখন বন্ধ হবে।"""

    campaign       = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name='schedule',
        null=True,
        blank=True,
    )
    start_at       = models.DateTimeField(db_index=True, null=True, blank=True)
    end_at         = models.DateTimeField(null=True, blank=True, db_index=True)
    timezone       = models.CharField(
        max_length=50,
        default='UTC',
        help_text=_('pytz timezone string, e.g. Asia/Dhaka'),
    )
    auto_pause_on_budget_exhaust = models.BooleanField(
        default=True,
        help_text=_('বাজেট শেষ হলে অটোমেটিক pause হবে কিনা'),
    )
    daily_budget_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text=_('প্রতিদিন সর্বোচ্চ কত USD খরচ হতে পারবে'),
    )
    active_hours_start = models.TimeField(null=True, blank=True,
        help_text=_('কোন সময় থেকে কাজ নেওয়া যাবে'),
    )
    active_hours_end   = models.TimeField(null=True, blank=True,
        help_text=_('কোন সময়ের পরে কাজ নেওয়া যাবে না'),
    )

    class Meta:
        db_table = 'campaign_schedule'
        verbose_name        = _('Campaign Schedule')
        verbose_name_plural = _('Campaign Schedules')

    def __str__(self):
        return f"Schedule for Campaign #{self.campaign_id} | {self.start_at} → {self.end_at or '∞'}"

    def clean(self):
        if self.end_at and self.start_at >= self.end_at:
            raise ValidationError(_('end_at অবশ্যই start_at এর পরে হতে হবে।'))

        # active_hours — দুটো হয় দুটোই থাকবে, নয়তো কোনোটাই না
        has_start = self.active_hours_start is not None
        has_end   = self.active_hours_end is not None
        if has_start != has_end:
            raise ValidationError(
                _('active_hours_start এবং active_hours_end — দুটো একসাথে দিতে হবে বা দুটোই বাদ দিতে হবে।')
            )
        if has_start and has_end and self.active_hours_start >= self.active_hours_end:
            raise ValidationError(_('active_hours_end অবশ্যই active_hours_start এর পরে হতে হবে।'))

    @property
    def is_currently_active(self) -> bool:
        """এই মুহূর্তে campaign active কিনা check করে।"""
        now = timezone.now()
        if now < self.start_at:
            return False
        if self.end_at and now > self.end_at:
            return False
        return True


# =============================================================================
# ── ৩. USER ACTION & TASK SUBMISSION (WORKER SIDE) ───────────────────────────
# =============================================================================

class TaskSubmission(TimestampedModel):
    """কাজের প্রধান রেকর্ড — একটি Worker এর একটি Campaign এর attempt।"""

    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending Review')
        APPROVED  = 'approved',  _('Approved')
        REJECTED  = 'rejected',  _('Rejected')
        DISPUTED  = 'disputed',  _('Under Dispute')
        EXPIRED   = 'expired',   _('Expired')

    uuid       = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    worker     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='submissions',)
    campaign   = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name='submissions', null=True, blank=True)
    status     = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,)

    # ─── Reward ─────────────────────────────────────────────────────────────
    reward_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    bonus_usd  = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )

    # ─── Review Info ────────────────────────────────────────────────────────
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_submissions',)
    review_note = models.TextField(blank=True, default='')

    # ─── Security Tracking ──────────────────────────────────────────────────
    ip_address           = models.GenericIPAddressField(
        protocol='both',
        unpack_ipv4=True,
    )
    device_fingerprint   = models.ForeignKey(
        'DeviceFingerprint',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='submissions',)
    submitted_at         = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table            = 'task_submission'
        verbose_name        = _('Task Submission')
        verbose_name_plural = _('Task Submissions')
        indexes = [
            models.Index(fields=['worker', 'campaign']),
            models.Index(fields=['status', 'submitted_at']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['ip_address']),
        ]
        # constraints = [
        #     CheckConstraint(
        #         condition=models.Q(bonus_usd__gte=0),
        #         name='chk_submission_bonus_non_negative',
        #     ),
        # ]

    def __str__(self):
        return f"Submission #{self.pk} | Worker:{self.worker_id} | {self.status}"

    @property
    def total_reward(self) -> Decimal:
        base    = self.reward_usd or Decimal('0')
        bonus   = self.bonus_usd or Decimal('0')
        return base + bonus

    def approve(self, reviewer, note: str = '') -> None:
        """Submission approve করার safe method।"""
        if self.status not in (self.Status.PENDING, self.Status.DISPUTED):
            raise ValidationError(_('শুধু pending বা disputed submission approve করা যাবে।'))
        self.status      = self.Status.APPROVED
        self.reviewer    = reviewer
        self.review_note = note
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewer', 'review_note', 'reviewed_at'])

    def reject(self, reviewer, note: str) -> None:
        """Submission reject করার safe method।"""
        if not note.strip():
            raise ValidationError(_('Rejection এর জন্য কারণ (note) দেওয়া আবশ্যক।'))
        if self.status not in (self.Status.PENDING, self.Status.DISPUTED):
            raise ValidationError(_('শুধু pending বা disputed submission reject করা যাবে।'))
        self.status      = self.Status.REJECTED
        self.reviewer    = reviewer
        self.review_note = note
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewer', 'review_note', 'reviewed_at'])


# ─────────────────────────────────────────────────────────────────────────────

class SubmissionProof(TimestampedModel):
    """প্রতিটি TaskStep এর জন্য Worker এর প্রুফ/প্রমাণ।"""

    MAX_FILE_SIZE_KB = 10 * 1024  # 10 MB

    submission   = models.ForeignKey(
        TaskSubmission,
        on_delete=models.CASCADE,
        related_name='proofs', null=True, blank=True)
    step         = models.ForeignKey(
        TaskStep,
        on_delete=models.PROTECT,
        related_name='proofs', null=True, blank=True)
    proof_type   = models.CharField(
        max_length=15,
        choices=TaskStep.ProofType.choices, null=True, blank=True)
    content      = models.TextField(
        validators=[MinLengthValidator(1)],
        help_text=_('URL (screenshot/link/video) অথবা টেক্সট উত্তর'),
    )
    file_size_kb = models.PositiveIntegerField(
        validators=[MaxValueValidator(MAX_FILE_SIZE_KB)],
    )
    uploaded_at  = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table            = 'submission_proof'
        verbose_name        = _('Submission Proof')
        verbose_name_plural = _('Submission Proofs')
        # একই submission এ একই step এর জন্য duplicate proof নয়
        constraints = [
            UniqueConstraint(
                fields=['submission', 'step'],
                name='uq_proof_per_submission_step',
            ),
        ]

    def __str__(self):
        return f"Proof | Submission #{self.submission_id} | Step #{self.step_id}"

    def clean(self):
        # Link টাইপে URL validate করা
        if self.proof_type == TaskStep.ProofType.LINK:
            validator = URLValidator(schemes=['http', 'https'])
            try:
                validator(self.content)
            except ValidationError:
                raise ValidationError({'content': _('Valid HTTP/HTTPS URL দিন।')})

        # Screenshot/Video তে file_size_kb থাকা আবশ্যক
        if self.proof_type in (TaskStep.ProofType.SCREENSHOT, TaskStep.ProofType.VIDEO):
            if not self.file_size_kb:
                raise ValidationError({'file_size_kb': _('Screenshot বা video এর জন্য file size দেওয়া আবশ্যক।')})
            if self.file_size_kb > self.MAX_FILE_SIZE_KB:
                raise ValidationError({'file_size_kb': _(f'File size সর্বোচ্চ {self.MAX_FILE_SIZE_KB} KB হতে পারবে।')})


# ─────────────────────────────────────────────────────────────────────────────

class VerificationLog(models.Model):
    """AI বা Admin দ্বারা প্রতিটি Submission রিভিউ এর অডিট ট্রেইল।"""

    class VerifiedBy(models.TextChoices):
        AI     = 'ai',     _('AI System')
        ADMIN  = 'admin',  _('Admin')
        SYSTEM = 'system', _('Auto System')

    class Decision(models.TextChoices):
        APPROVE   = 'approve',   _('Approve')
        REJECT    = 'reject',    _('Reject')
        ESCALATE  = 'escalate',  _('Escalate to Human')

    submission          = models.ForeignKey(
        TaskSubmission,
        on_delete=models.CASCADE,
        related_name='verification_logs', null=True, blank=True)
    verified_by         = models.CharField(max_length=10, choices=VerifiedBy.choices, null=True, blank=True)
    verifier_admin      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verification_logs',
        help_text=_('verified_by=admin হলে কোন Admin'),
    )
    ai_model_version    = models.CharField(
        max_length=100,
        blank=True, default='',
        help_text=_('AI verify করলে model version লগ করুন'),
    )
    ai_confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
    )
    decision            = models.CharField(max_length=10, choices=Decision.choices, null=True, blank=True)
    reason              = models.TextField(blank=True, default='')
    verified_at         = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table            = 'verification_log'
        verbose_name        = _('Verification Log')
        verbose_name_plural = _('Verification Logs')
        ordering            = ['-verified_at']
        indexes = [
            models.Index(fields=['submission', '-verified_at']),
        ]

    def __str__(self):
        return f"VerifyLog #{self.pk} | Sub#{self.submission_id} | {self.verified_by} → {self.decision}"

    def clean(self):
        # Admin verify করলে verifier_admin থাকা আবশ্যক
        if self.verified_by == self.VerifiedBy.ADMIN and not self.verifier_admin_id:
            raise ValidationError({'verifier_admin': _('Admin verification এ verifier_admin দেওয়া আবশ্যক।')})
        # AI verify করলে confidence score থাকা উচিত
        if self.verified_by == self.VerifiedBy.AI and self.ai_confidence_score is None:
            raise ValidationError({'ai_confidence_score': _('AI verification এ confidence score দেওয়া আবশ্যক।')})


# ─────────────────────────────────────────────────────────────────────────────

class Dispute(TimestampedModel):
    """Reject হওয়া কাজের বিরুদ্ধে Worker এর আপিল।"""

    class Status(models.TextChoices):
        OPEN               = 'open',               _('Open')
        UNDER_REVIEW       = 'under_review',       _('Under Review')
        RESOLVED_APPROVED  = 'resolved_approved',  _('Resolved — Approved')
        RESOLVED_REJECTED  = 'resolved_rejected',  _('Resolved — Rejected')

    submission    = models.OneToOneField(
        TaskSubmission,
        on_delete=models.CASCADE,
        related_name='dispute', null=True, blank=True)
    worker        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='disputes', null=True, blank=True)
    reason        = models.TextField(
        validators=[MinLengthValidator(20)],
        default='',
        help_text=_('কেন রিজেক্ট সঠিক নয় তার বিস্তারিত কারণ'),
    )
    evidence_url  = models.URLField(blank=True, default='', null=True)
    status        = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,)
    admin_note    = models.TextField(blank=True, default='')
    resolved_at   = models.DateTimeField(null=True, blank=True)
    resolved_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_disputes',)

    class Meta:
        db_table            = 'dispute'
        verbose_name        = _('Dispute')
        verbose_name_plural = _('Disputes')
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Dispute #{self.pk} | Sub#{self.submission_id} | {self.status}"

    def clean(self):
        # শুধু rejected submission এ dispute করা যাবে
        if self.submission_id and self.submission.status != TaskSubmission.Status.REJECTED:
            raise ValidationError(_('শুধুমাত্র REJECTED submission এর বিরুদ্ধে dispute করা যাবে।'))

        # Resolved হলে resolved_at এবং resolved_by থাকা আবশ্যক
        if self.status in (self.Status.RESOLVED_APPROVED, self.Status.RESOLVED_REJECTED):
            if not self.resolved_at:
                self.resolved_at = timezone.now()


# =============================================================================
# ── ৪. FINANCE & PROFIT TRACKING ─────────────────────────────────────────────
# =============================================================================

class PromotionTransaction(TimestampedModel):
    """মূল আর্থিক লেজার — প্রতিটি টাকার movement এখানে রেকর্ড হয়।"""

    class TransactionType(models.TextChoices):
        DEPOSIT          = 'deposit',          _('Deposit')
        WITHDRAWAL       = 'withdrawal',       _('Withdrawal')
        REWARD           = 'reward',           _('Task Reward')
        COMMISSION       = 'commission',       _('Admin Commission')
        REFERRAL         = 'referral',         _('Referral Commission')
        REFUND           = 'refund',           _('Refund')
        ESCROW_LOCK      = 'escrow_lock',      _('Escrow Lock')
        ESCROW_RELEASE   = 'escrow_release',   _('Escrow Release')
        BONUS            = 'bonus',            _('Bonus Payment')
        PENALTY          = 'penalty',          _('Fraud Penalty')

    uuid           = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    type           = models.CharField(max_length=20, choices=TransactionType.choices, db_index=True, null=True, blank=True)
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='promotion_transactions', null=True, blank=True)
    campaign       = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name='promotion_transactions', null=True, blank=True)
    amount_usd     = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))],
        help_text=_('সবসময় positive amount — type দিয়ে direction বোঝা যাবে'),
    )
    currency_code  = models.CharField(
        max_length=3,
        default='USD',
        validators=[RegexValidator(r'^[A-Z]{3}$', 'ISO 4217 code দিন')],
    )
    amount_local   = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True, blank=True,
        help_text=_('স্থানীয় মুদ্রায় equivalent amount'),
    )
    balance_after  = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        help_text=_('Transaction এর পরে user এর balance'),
    )
    reference_id   = models.PositiveBigIntegerField(
        help_text=_('submission_id বা অন্য সংশ্লিষ্ট রেকর্ডের ID'),
    )
    note           = models.TextField(blank=True, default='')
    # Immutability tracking
    is_reversed    = models.BooleanField(default=False)
    reversed_by_tx = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reversal_of',)

    class Meta:
        db_table            = 'promotion_transaction'
        verbose_name        = _('Promotion Transaction')
        verbose_name_plural = _('Promotion Transactions')
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['campaign', 'type']),
            models.Index(fields=['type', '-created_at']),
        ]
        # Transaction একবার তৈরি হলে delete করা যাবে না — permission দিয়ে enforce করুন

    def __str__(self):
        return f"TX #{self.pk} | {self.type} | ${self.amount_usd}"


# ─────────────────────────────────────────────────────────────────────────────

class EscrowWallet(TimestampedModel):
    """Campaign চলাকালীন Advertiser এর বাজেট 'হোল্ড' করার সিস্টেম।"""

    class Status(models.TextChoices):
        LOCKED             = 'locked',             _('Locked')
        PARTIALLY_RELEASED = 'partially_released', _('Partially Released')
        FULLY_RELEASED     = 'fully_released',     _('Fully Released')
        REFUNDED           = 'refunded',           _('Refunded to Advertiser')

    campaign          = models.OneToOneField(
        Campaign,
        on_delete=models.PROTECT,
        related_name='escrow',
        primary_key=True,)
    advertiser        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='escrow_wallets',)
    locked_amount_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    released_amount_usd = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    status            = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.LOCKED,
        db_index=True,)
    locked_at         = models.DateTimeField(default=timezone.now)
    released_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'escrow_wallet'
        verbose_name        = _('Escrow Wallet')
        verbose_name_plural = _('Escrow Wallets')
        # constraints = [
        #     CheckConstraint(
        #         condition=models.Q(released_amount_usd__lte=models.F('locked_amount_usd')),
        #         name='chk_escrow_released_not_exceed_locked',
        #     ),
        #     CheckConstraint(
        #         condition=models.Q(locked_amount_usd__gt=0),
        #         name='chk_escrow_locked_positive',
        #     ),
        # ]

    def __str__(self):
        return f"Escrow | Campaign #{self.campaign_id} | ${self.locked_amount_usd} [{self.status}]"

    @property
    def remaining_amount_usd(self) -> Decimal:
        return self.locked_amount_usd - self.released_amount_usd

    @transaction.atomic
    def release(self, amount: Decimal) -> None:
        """নির্দিষ্ট পরিমাণ escrow থেকে release করে।"""
        if amount <= 0:
            raise ValidationError(_('Release amount অবশ্যই positive হতে হবে।'))
        if amount > self.remaining_amount_usd:
            raise ValidationError(_(
                f'Release amount (${amount}) remaining balance (${self.remaining_amount_usd}) এর বেশি হতে পারবে না।'
            ))
        EscrowWallet.objects.filter(pk=self.pk).update(
            released_amount_usd=F('released_amount_usd') + amount
        )
        self.refresh_from_db()
        if self.released_amount_usd >= self.locked_amount_usd:
            self.status = self.Status.FULLY_RELEASED
            self.released_at = timezone.now()
            self.save(update_fields=['status', 'released_at'])


# ─────────────────────────────────────────────────────────────────────────────

class AdminCommissionLog(models.Model):
    """প্রতিটি Approved কাজ থেকে Admin এর নিট লাভের হিসাব।"""

    submission      = models.OneToOneField(
        TaskSubmission,
        on_delete=models.PROTECT,
        related_name='commission_log',
        null=True, blank=True,)
    campaign        = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name='commission_logs',
        null=True, blank=True,)
    gross_amount_usd  = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_('Advertiser মোট কত দিল'),
    )
    worker_reward_usd = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_('Worker কত পেল'),
    )
    commission_usd    = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_('Admin এর নিট লাভ'),
    )
    commission_rate   = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
    )
    created_at        = models.DateTimeField(auto_now_add=True, db_index=True, null=True)

    class Meta:
        db_table            = 'admin_commission_log'
        verbose_name        = _('Admin Commission Log')
        verbose_name_plural = _('Admin Commission Logs')
        # constraints = [
        #     CheckConstraint(
        #         condition=models.Q(commission_usd__lte=models.F('gross_amount_usd')),
        #         name='chk_commission_not_exceed_gross',
        #     ),
        #     CheckConstraint(
        #         condition=(
        #             models.Q(worker_reward_usd__gte=0) &
        #             models.Q(commission_usd__gte=0) &
        #             models.Q(gross_amount_usd__gte=0)
        #         ),
        #         name='chk_commission_all_non_negative',
        #     ),
        # ]

    def __str__(self):
        return f"Commission | Sub#{self.submission_id} | Admin:${self.commission_usd}"

    def clean(self):
        if (
            self.gross_amount_usd is not None and
            self.worker_reward_usd is not None and
            self.commission_usd is not None
        ):
            expected = self.gross_amount_usd - self.worker_reward_usd
            tolerance = Decimal('0.000001')
            if abs(self.commission_usd - expected) > tolerance:
                raise ValidationError(
                    _('commission_usd = gross_amount_usd - worker_reward_usd হতে হবে।')
                )


# ─────────────────────────────────────────────────────────────────────────────

class ReferralCommissionLog(TimestampedModel):
    """Multi-level রেফারেল নেটওয়ার্কের কমিশন ট্র্যাকিং।"""

    class CommissionStatus(models.TextChoices):
        PENDING  = 'pending',  _('Pending')
        PAID     = 'paid',     _('Paid')
        CANCELLED= 'cancelled',_('Cancelled')

    referrer              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='referral_commissions_earned',
        help_text=_('যে রেফার করেছে'),
    )
    referred              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='referral_commissions_generated',
        help_text=_('যাকে রেফার করা হয়েছে'),
    )
    level                 = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Level-1 = direct referral, Level-2 = indirect'),
    )
    source_submission     = models.ForeignKey(
        TaskSubmission,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referral_commissions',)
    commission_usd        = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))],
    )
    commission_rate       = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('50')),
        ],
    )
    status                = models.CharField(
        max_length=15,
        choices=CommissionStatus.choices,
        default=CommissionStatus.PENDING,
        db_index=True,)
    paid_at               = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table            = 'referral_commission_log'
        verbose_name        = _('Referral Commission Log')
        verbose_name_plural = _('Referral Commission Logs')
        indexes = [
            models.Index(fields=['referrer', 'status']),
            models.Index(fields=['referred', 'level']),
        ]
        # constraints = [
        #     CheckConstraint(
        #         condition=models.Q(referrer__ne=models.F('referred')),
        #         name='chk_referral_referrer_not_same_as_referred',
        #     ),
        # ]

    def __str__(self):
        return f"Referral | L{self.level} | {self.referrer_id}→{self.referred_id} | ${self.commission_usd}"

    def clean(self):
        if self.referrer_id and self.referred_id and self.referrer_id == self.referred_id:
            raise ValidationError(_('referrer এবং referred একই user হতে পারবে না।'))


# =============================================================================
# ── ৫. SECURITY & ANALYTICS ──────────────────────────────────────────────────
# =============================================================================

class UserReputation(models.Model):
    """প্রতিটি Worker এর Trust Score এবং Performance Statistics।"""

    user                 = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reputation',
        primary_key=True,)
    total_submissions    = models.PositiveIntegerField(default=0)
    approved_count       = models.PositiveIntegerField(default=0)
    rejected_count       = models.PositiveIntegerField(default=0)
    disputed_count       = models.PositiveIntegerField(default=0)
    success_rate         = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
    )
    trust_score          = models.PositiveSmallIntegerField(
        default=50,
        validators=[MaxValueValidator(100)],
    )
    level                = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    last_active_at       = models.DateTimeField(null=True, blank=True)
    last_updated         = models.DateTimeField(auto_now=True)
    is_verified_worker   = models.BooleanField(default=False)

    class Meta:
        db_table            = 'user_reputation'
        verbose_name        = _('User Reputation')
        verbose_name_plural = _('User Reputations')
        # constraints = [
        #     CheckConstraint(
        #         condition=(
        #             models.Q(approved_count__lte=models.F('total_submissions')) &
        #             models.Q(rejected_count__lte=models.F('total_submissions'))
        #         ),
        #         name='chk_reputation_counts_not_exceed_total',
        #     ),
        #     CheckConstraint(
        #         condition=models.Q(trust_score__gte=0) & models.Q(trust_score__lte=100),
        #         name='chk_reputation_trust_score_range',
        #     ),
        # ]

    def __str__(self):
        return f"Reputation | User #{self.user_id} | Score:{self.trust_score} | L{self.level}"

    def recalculate(self) -> None:
        """Stats পুনরায় calculate করে save করে।"""
        if self.total_submissions > 0:
            self.success_rate = (
                Decimal(self.approved_count) / Decimal(self.total_submissions) * 100
            ).quantize(Decimal('0.01'))
        else:
            self.success_rate = Decimal('0')
        self.save(update_fields=['success_rate', 'last_updated'])


# ─────────────────────────────────────────────────────────────────────────────

class FraudReport(TimestampedModel):
    """AI কর্তৃক চিহ্নিত Fraud Activity এর রেকর্ড।"""

    class FraudType(models.TextChoices):
        FAKE_SCREENSHOT     = 'fake_screenshot',      _('Fake Screenshot')
        VPN_DETECTED        = 'vpn_detected',         _('VPN / Proxy Detected')
        BOT_ACTIVITY        = 'bot_activity',         _('Bot / Automated Activity')
        DUPLICATE_SUBMIT    = 'duplicate_submission', _('Duplicate Submission')
        ACCOUNT_FARMING     = 'account_farming',      _('Multiple Account Farming')
        EMULATOR_DETECTED   = 'emulator_detected',    _('Emulator Detected')
        CLICK_FRAUD         = 'click_fraud',          _('Click Fraud')

    class ActionTaken(models.TextChoices):
        FLAGGED  = 'flagged',  _('Flagged for Review')
        WARNED   = 'warned',   _('Warning Issued')
        BANNED   = 'banned',   _('Account Banned')
        IGNORED  = 'ignored',  _('Ignored / False Positive')

    user              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='promotional_fraud_reports',)
    submission        = models.ForeignKey(
        TaskSubmission,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='promotional_fraud_reports',)
    fraud_type        = models.CharField(max_length=30, choices=FraudType.choices, db_index=True, null=True, blank=True)
    ai_model_version  = models.CharField(max_length=100, blank=True, default='', null=True)
    confidence_score  = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
    )
    evidence          = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('AI এর detected features, signals ইত্যাদি'),
    )
    action_taken      = models.CharField(
        max_length=10,
        choices=ActionTaken.choices,
        default=ActionTaken.FLAGGED,)
    reviewed_by_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_fraud_reports',)
    admin_note        = models.TextField(blank=True, default='')

    class Meta:
        db_table            = 'fraud_report'
        verbose_name        = _('Fraud Report')
        verbose_name_plural = _('Fraud Reports')
        indexes = [
            models.Index(fields=['user', 'fraud_type']),
            models.Index(fields=['action_taken', 'created_at']),
        ]

    def __str__(self):
        return f"Fraud #{self.pk} | {self.fraud_type} | User:{self.user_id} | {self.action_taken}"


# ─────────────────────────────────────────────────────────────────────────────

class DeviceFingerprint(TimestampedModel):
    """Multiple Account ধরার জন্য Hardware/Browser Fingerprint।"""

    user               = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='promotional_device_fingerprints',)
    # fingerprint_hash: FingerprintJS Pro বা client-side library দিয়ে generate করুন
    fingerprint_hash   = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default='',
        validators=[
            MinLengthValidator(32),
            RegexValidator(r'^[a-f0-9]+$', 'Lowercase hex hash দিন'),
        ],
    )
    device_type        = models.CharField(
        max_length=20,
        blank=True, default='',
        # 'mobile', 'desktop', 'tablet', 'unknown'
    )
    os                 = models.CharField(max_length=50, blank=True, default='', null=True)
    os_version         = models.CharField(max_length=30, blank=True, default='', null=True)
    browser            = models.CharField(max_length=50, blank=True, default='', null=True)
    browser_version    = models.CharField(max_length=20, blank=True, default='', null=True)
    screen_resolution  = models.CharField(
        max_length=20,
        blank=True, default='',
        validators=[RegexValidator(r'^\d+x\d+$', 'Format: WxH, e.g. 1920x1080')],
    )
    user_timezone           = models.CharField(max_length=50, blank=True, default='', null=True)
    language           = models.CharField(max_length=10, blank=True, default='', null=True)
    first_seen         = models.DateTimeField(default=timezone.now)
    last_seen          = models.DateTimeField(default=timezone.now)
    is_flagged         = models.BooleanField(default=False, db_index=True)
    flag_reason        = models.TextField(blank=True, default='')
    # একটি device fingerprint এ কতটি ভিন্ন account সংযুক্ত
    linked_account_count = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table            = 'device_fingerprint'
        verbose_name        = _('Device Fingerprint')
        verbose_name_plural = _('Device Fingerprints')
        indexes = [
            models.Index(fields=['user', '-last_seen']),
            models.Index(fields=['is_flagged']),
        ]

    def __str__(self):
        return f"Device | User:{self.user_id} | {self.fingerprint_hash[:16]}... | flagged:{self.is_flagged}"

    @classmethod
    def generate_hash(cls, raw_fingerprint_data: str) -> str:
        """Client data থেকে consistent SHA-256 hash তৈরি করে।"""
        return hashlib.sha256(raw_fingerprint_data.encode('utf-8')).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────

class Blacklist(TimestampedModel):
    """নিষিদ্ধ User, IP, Device, YouTube Channel বা Email Domain।"""

    class BlacklistType(models.TextChoices):
        USER         = 'user',         _('User Account')
        IP           = 'ip',           _('IP Address')
        DEVICE       = 'device',       _('Device Fingerprint')
        CHANNEL_URL  = 'channel_url',  _('YouTube / Social Channel')
        EMAIL_DOMAIN = 'email_domain', _('Email Domain')
        PHONE        = 'phone',        _('Phone Number')

    class Severity(models.TextChoices):
        WARN      = 'warn',      _('Warning Only')
        TEMP_BAN  = 'temp_ban',  _('Temporary Ban')
        PERMANENT = 'permanent', _('Permanent Ban')

    type       = models.CharField(max_length=15, choices=BlacklistType.choices, db_index=True, null=True, blank=True)
    value      = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(1)],
        help_text=_('IP, user_id, domain, channel URL ইত্যাদি'),
    )
    reason     = models.TextField(validators=[MinLengthValidator(5)], default='')
    added_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='blacklist_entries',)
    severity   = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.PERMANENT,)
    expires_at = models.DateTimeField(
        help_text=_('শুধু temp_ban এর জন্য'),
    )
    is_active  = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table            = 'blacklist'
        verbose_name        = _('Blacklist Entry')
        verbose_name_plural = _('Blacklist Entries')
        constraints = [
            UniqueConstraint(
                fields=['type', 'value'],
                condition=Q(is_active=True),
                name='uq_active_blacklist_type_value',
            ),
        ]
        indexes = [
            models.Index(fields=['type', 'value', 'is_active']),
        ]

    def __str__(self):
        return f"Blacklist | {self.type}: {self.value[:50]} | {self.severity}"

    def clean(self):
        # Temporary ban এ expires_at থাকা আবশ্যক
        if self.severity == self.Severity.TEMP_BAN and not self.expires_at:
            raise ValidationError({
                'expires_at': _('Temporary ban এ expires_at দেওয়া আবশ্যক।')
            })
        # Permanent ban এ expires_at থাকা উচিত নয়
        if self.severity == self.Severity.PERMANENT and self.expires_at:
            raise ValidationError({
                'expires_at': _('Permanent ban এ expires_at দেওয়া যাবে না।')
            })
        # IP address format validate
        if self.type == self.BlacklistType.IP:
            import ipaddress
            try:
                ipaddress.ip_address(self.value.strip())
            except ValueError:
                raise ValidationError({'value': _('Valid IP address দিন (IPv4 বা IPv6)।')})

    @classmethod
    def is_blacklisted(cls, type_: str, value: str) -> bool:
        """দ্রুত check করার utility method।"""
        now = timezone.now()
        return cls.objects.filter(
            type=type_,
            value=value,
            is_active=True,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).exists()


# ─────────────────────────────────────────────────────────────────────────────

class CampaignAnalytics(models.Model):
    """প্রতিটি Campaign এর দৈনিক রিয়েল-টাইম পারফরম্যান্স ডাটা।"""

    campaign              = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='analytics',
        null=True,
        blank=True,
    )
    date                  = models.DateField(db_index=True, null=True, blank=True)
    # ─── Traffic ────────────────────────────────────────────────────────────
    total_views           = models.PositiveIntegerField(default=0)
    total_clicks          = models.PositiveIntegerField(default=0)
    unique_visitors       = models.PositiveIntegerField(default=0)
    # ─── Submission Stats ───────────────────────────────────────────────────
    total_submissions     = models.PositiveIntegerField(default=0)
    approved_count        = models.PositiveIntegerField(default=0)
    rejected_count        = models.PositiveIntegerField(default=0)
    disputed_count        = models.PositiveIntegerField(default=0)
    fraud_detected        = models.PositiveIntegerField(default=0)
    # ─── Finance ────────────────────────────────────────────────────────────
    total_spent_usd       = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    admin_commission_usd  = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    # ─── Performance ────────────────────────────────────────────────────────
    avg_completion_time_sec = models.PositiveIntegerField(null=True, blank=True)
    unique_countries        = models.PositiveSmallIntegerField(default=0)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'campaign_analytics'
        verbose_name        = _('Campaign Analytics')
        verbose_name_plural = _('Campaign Analytics')
        constraints = [
            UniqueConstraint(
                fields=['campaign', 'date'],
                name='uq_campaign_analytics_per_day',
            ),
            # CheckConstraint(
            #     condition=models.Q(approved_count__lte=models.F('total_submissions')),
            #     name='chk_analytics_approved_not_exceed_submissions',
            # ),
            # CheckConstraint(
            #     condition=models.Q(total_clicks__lte=models.F('total_views')),
            #     name='chk_analytics_clicks_not_exceed_views',
            # ),
        ]
        indexes = [
            models.Index(fields=['campaign', '-date']),
        ]
        ordering = ['-date']

    def __str__(self):
        return f"Analytics | Campaign #{self.campaign_id} | {self.date}"

    @property
    def approval_rate(self) -> float:
        if self.total_submissions == 0:
            return 0.0
        return round((self.approved_count / self.total_submissions) * 100, 2)

    @property
    def click_through_rate(self) -> float:
        if self.total_views == 0:
            return 0.0
        return round((self.total_clicks / self.total_views) * 100, 2)


# =============================================================================
# ── BIDDING SYSTEM ────────────────────────────────────────────────────────────
# =============================================================================

class CampaignBid(TimestampedModel):
    """Advertiser এর Campaign Slot Bid।"""

    class Status(models.TextChoices):
        PENDING  = 'pending',  _('Pending')
        WON      = 'won',      _('Won')
        LOST     = 'lost',     _('Lost')
        CANCELLED= 'cancelled',_('Cancelled')

    class AuctionType(models.TextChoices):
        GSP         = 'gsp',         _('Generalized Second Price')
        FIRST_PRICE = 'first_price', _('First Price')

    campaign      = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='bids', null=True, blank=True)
    advertiser    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='campaign_bids', null=True, blank=True)
    bid_amount    = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    floor_price   = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    final_price   = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    auction_type  = models.CharField(max_length=15, choices=AuctionType.choices, default=AuctionType.GSP, null=True, blank=True)
    status        = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True, null=True, blank=True)
    bid_at        = models.DateTimeField(default=timezone.now)
    resolved_at   = models.DateTimeField(null=True, blank=True)
    note          = models.TextField(blank=True, default='')

    class Meta:
        db_table            = 'campaign_bid'
        verbose_name        = _('Campaign Bid')
        verbose_name_plural = _('Campaign Bids')
        ordering            = ['-bid_at']
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['advertiser', '-bid_at']),
        ]

    def __str__(self):
        return f"Bid #{self.pk} | Campaign:{self.campaign_id} | ${self.bid_amount} | {self.status}"


# =============================================================================
# ── SECTION 8: NEW OFFER TYPES — DB PERSISTENT ──────────────────────────────
# =============================================================================

class PublisherProfile(TimestampedModel):
    """Publisher এর extended profile — tier, stats, settings।"""
    user              = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='promotions_publisher_profile', null=True, blank=True)
    website_url       = models.URLField(blank=True, default='', null=True)
    traffic_source    = models.CharField(max_length=50, blank=True, default='', null=True)
    monthly_traffic   = models.PositiveIntegerField(default=0)
    country           = models.CharField(max_length=2, blank=True, default='', null=True)
    niche             = models.CharField(max_length=50, blank=True, default='', null=True)
    tier              = models.CharField(max_length=20, default='starter',
        choices=[('starter','Starter'),('bronze','Bronze'),('silver','Silver'),('gold','Gold'),('platinum','Platinum')])
    approval_status   = models.CharField(max_length=20, default='pending',
        choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')])
    approved_at       = models.DateTimeField(null=True, blank=True)
    device_token_fcm  = models.CharField(max_length=200, blank=True, default='', null=True)
    device_token_apns = models.CharField(max_length=200, blank=True, default='', null=True)
    phone_number      = models.CharField(max_length=20, blank=True, default='', null=True)
    telegram_id       = models.CharField(max_length=50, blank=True, default='', null=True)
    total_earned      = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_withdrawn   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    class Meta:
        db_table     = 'publisher_profile'
        verbose_name = _('Publisher Profile')

    def __str__(self):
        return f'Publisher: {self.user.username} [{self.tier}]'


class AdvertiserProfile(TimestampedModel):
    """Advertiser এর extended profile।"""
    user              = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='advertiser_profile', null=True, blank=True)
    company_name      = models.CharField(max_length=100, blank=True, default='', null=True)
    website_url       = models.URLField(blank=True, default='', null=True)
    country           = models.CharField(max_length=2, blank=True, default='', null=True)
    billing_email     = models.EmailField(blank=True, default='')
    total_deposited   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_spent       = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    credit_balance    = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    is_verified       = models.BooleanField(default=False)
    verified_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'advertiser_profile'
        verbose_name = _('Advertiser Profile')

    def __str__(self):
        return f'Advertiser: {self.user.username}'


class APIKeyModel(TimestampedModel):
    """Publisher API keys — persistent DB storage।"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys', null=True, blank=True)
    name        = models.CharField(max_length=100, null=True, blank=True)
    key_hash    = models.CharField(max_length=64, unique=True, db_index=True, null=True, blank=True)
    permissions = models.JSONField(default=list)
    rate_limit  = models.PositiveIntegerField(default=1000)
    is_active   = models.BooleanField(default=True, db_index=True)
    last_used   = models.DateTimeField(null=True, blank=True)
    total_requests = models.PositiveIntegerField(default=0)
    revoked_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'publisher_api_key'
        verbose_name = _('API Key')

    def __str__(self):
        return f'{self.user.username} — {self.name}'


class WebhookConfigModel(TimestampedModel):
    """Publisher webhook/postback URL config — DB persistent।"""
    publisher   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webhook_configs', null=True, blank=True)
    event       = models.CharField(max_length=50, null=True, blank=True)
    url         = models.URLField(max_length=2000, null=True, blank=True)
    method      = models.CharField(max_length=6, default='GET', choices=[('GET','GET'),('POST','POST')])
    secret_key  = models.CharField(max_length=100, blank=True, default='', null=True)
    is_active   = models.BooleanField(default=True)
    last_fired  = models.DateTimeField(null=True, blank=True)
    total_fires = models.PositiveIntegerField(default=0)
    last_status_code = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        db_table             = 'webhook_config'
        verbose_name         = _('Webhook Config')
        unique_together      = [('publisher', 'event')]

    def __str__(self):
        return f'{self.publisher.username} → {self.event}'


class VirtualCurrencyConfig(TimestampedModel):
    """Publisher-এর virtual currency config — DB persistent।"""
    publisher       = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vc_config', null=True, blank=True)
    currency_name   = models.CharField(max_length=30, default='Coins', null=True, blank=True)
    currency_icon   = models.CharField(max_length=10, default='🪙', null=True, blank=True)
    usd_to_vc_rate  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1000'))
    min_payout_vc   = models.PositiveIntegerField(default=100)
    rounding        = models.CharField(max_length=10, default='floor', choices=[('floor','Floor'),('ceil','Ceil'),('round','Round')])
    postback_url    = models.URLField(blank=True, default='', null=True)
    is_active       = models.BooleanField(default=True)

    class Meta:
        db_table     = 'virtual_currency_config'
        verbose_name = _('Virtual Currency Config')

    def __str__(self):
        return f'{self.publisher.username}: 1 USD = {self.usd_to_vc_rate} {self.currency_name}'


class WhiteLabelConfig(TimestampedModel):
    """Publisher white-label offerwall config।"""
    publisher        = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='white_label', null=True, blank=True)
    brand_name       = models.CharField(max_length=100, null=True, blank=True)
    logo_url         = models.URLField(blank=True, default='', null=True)
    primary_color    = models.CharField(max_length=7, default='#6C63FF', null=True, blank=True)
    secondary_color  = models.CharField(max_length=7, default='#FF6584', null=True, blank=True)
    custom_domain    = models.CharField(max_length=100, blank=True, default='', null=True)
    welcome_message  = models.TextField(blank=True, default='')
    footer_text      = models.TextField(blank=True, default='')
    show_powered_by  = models.BooleanField(default=True)
    is_active        = models.BooleanField(default=True)

    class Meta:
        db_table     = 'white_label_config'
        verbose_name = _('White Label Config')

    def __str__(self):
        return f'{self.publisher.username} — {self.brand_name}'


class EmailSubmitCampaign(TimestampedModel):
    """Email Submit campaign — SOI/DOI।"""
    advertiser       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='email_campaigns', null=True, blank=True)
    campaign_name    = models.CharField(max_length=200, null=True, blank=True)
    opt_in_type      = models.CharField(max_length=3, default='SOI', choices=[('SOI','Single Opt-in'),('DOI','Double Opt-in')])
    payout           = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    niche            = models.CharField(max_length=50, default='general', null=True, blank=True)
    target_countries = models.JSONField(default=list)
    daily_cap        = models.PositiveIntegerField(default=5000)
    today_submits    = models.PositiveIntegerField(default=0)
    total_submits    = models.PositiveIntegerField(default=0)
    redirect_url     = models.URLField(blank=True, default='', null=True)
    status           = models.CharField(max_length=20, default='active',
        choices=[('active','Active'),('paused','Paused'),('completed','Completed')])
    total_spent      = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    class Meta:
        db_table     = 'email_submit_campaign'
        verbose_name = _('Email Submit Campaign')

    def __str__(self):
        return f'{self.campaign_name} [{self.opt_in_type}] — ${self.payout}'


class EmailSubmitConversion(TimestampedModel):
    """Email submit conversion tracking।"""
    campaign     = models.ForeignKey(EmailSubmitCampaign, on_delete=models.PROTECT, related_name='conversions', null=True, blank=True)
    publisher    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='email_conversions', null=True, blank=True)
    email_hash   = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    ip_hash      = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    country      = models.CharField(max_length=2, null=True, blank=True)
    subid        = models.CharField(max_length=64, null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    payout_amount= models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0'))
    is_paid      = models.BooleanField(default=False)
    paid_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'email_submit_conversion'
        verbose_name = _('Email Submit Conversion')

    def __str__(self):
        return f'Email submit: {self.campaign.campaign_name} — pub:{self.publisher_id}'


class CPCCampaign(TimestampedModel):
    """CPC (Pay Per Click) campaign।"""
    advertiser       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cpc_campaigns', null=True, blank=True)
    title            = models.CharField(max_length=200, null=True, blank=True)
    destination_url  = models.URLField(null=True, blank=True)
    payout_us        = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.35'))
    payout_gb        = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.28'))
    payout_ca        = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.25'))
    payout_au        = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.22'))
    payout_other     = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.05'))
    daily_cap        = models.PositiveIntegerField(default=10000)
    total_budget     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_spent      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_clicks     = models.PositiveIntegerField(default=0)
    today_clicks     = models.PositiveIntegerField(default=0)
    dedup_window_sec = models.PositiveIntegerField(default=3600)
    status           = models.CharField(max_length=20, default='active',
        choices=[('active','Active'),('paused','Paused'),('completed','Completed')])

    class Meta:
        db_table     = 'cpc_campaign'
        verbose_name = _('CPC Campaign')

    def __str__(self):
        return f'{self.title} — avg $0.{self.payout_us}'


class CPIAppCampaign(TimestampedModel):
    """CPI (Cost Per Install) app campaign।"""
    advertiser        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cpi_campaigns', null=True, blank=True)
    app_name          = models.CharField(max_length=200, null=True, blank=True)
    bundle_id         = models.CharField(max_length=200, null=True, blank=True)
    platform          = models.CharField(max_length=10, choices=[('android','Android'),('ios','iOS'),('both','Both')], default='')

    app_store_url     = models.URLField(null=True, blank=True)
    payout_per_install= models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    mmp_provider      = models.CharField(max_length=20, default='appsflyer',
        choices=[('appsflyer','AppsFlyer'),('adjust','Adjust'),('firebase','Firebase'),('branch','Branch'),('kochava','Kochava')])
    mmp_app_id        = models.CharField(max_length=200, null=True, blank=True)
    target_countries  = models.JSONField(default=list)
    target_os_version = models.CharField(max_length=20, null=True, blank=True)
    daily_cap         = models.PositiveIntegerField(default=1000)
    total_budget      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_installs    = models.PositiveIntegerField(default=0)
    today_installs    = models.PositiveIntegerField(default=0)
    total_spent       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    status            = models.CharField(max_length=20, default='active',
        choices=[('active','Active'),('paused','Paused'),('completed','Completed')])

    class Meta:
        db_table     = 'cpi_app_campaign'
        verbose_name = _('CPI App Campaign')

    def __str__(self):
        return f'{self.app_name} [{self.platform}] — ${self.payout_per_install}/install'


class QuizCampaign(TimestampedModel):
    """Quiz/Survey campaign — Co-reg।"""
    advertiser       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='quiz_campaigns', null=True, blank=True)
    title            = models.CharField(max_length=200, null=True, blank=True)
    quiz_type        = models.CharField(max_length=20, default='personality',
        choices=[('personality','Personality'),('trivia','Trivia'),('survey','Survey'),('sweepstakes','Sweepstakes'),('iq','IQ Test')])
    questions        = models.JSONField(default=list)
    lead_form_fields = models.JSONField(default=list)
    payout           = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    target_countries = models.JSONField(default=list)
    daily_cap        = models.PositiveIntegerField(default=2000)
    total_completions= models.PositiveIntegerField(default=0)
    today_completions= models.PositiveIntegerField(default=0)
    total_spent      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    status           = models.CharField(max_length=20, default='active',
        choices=[('active','Active'),('paused','Paused'),('completed','Completed')])

    class Meta:
        db_table     = 'quiz_campaign'
        verbose_name = _('Quiz Campaign')

    def __str__(self):
        return f'{self.title} [{self.quiz_type}] — ${self.payout}'


class SmartLinkConfig(TimestampedModel):
    """Publisher SmartLink configuration — DB persistent।"""
    publisher     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='promotions_smartlinks', null=True, blank=True)
    name          = models.CharField(max_length=100, null=True, blank=True)
    link_hash     = models.CharField(max_length=20, unique=True, db_index=True, null=True, blank=True)
    total_clicks  = models.PositiveIntegerField(default=0)
    total_earnings= models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    is_active     = models.BooleanField(default=True)

    class Meta:
        db_table     = 'smartlink_config'
        verbose_name = _('SmartLink Config')

    def __str__(self):
        return f'{self.publisher.username} — {self.name}'


class ContentLockModel(TimestampedModel):
    """Content locker config — DB persistent।"""
    publisher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='content_locks', null=True, blank=True)
    lock_type       = models.CharField(max_length=10, choices=[('link','Link'),('file','File'),('content','Content')])
    lock_token      = models.CharField(max_length=40, unique=True, db_index=True, null=True, blank=True)
    title           = models.CharField(max_length=200, null=True, blank=True)
    description     = models.TextField(blank=True)
    destination_url = models.URLField(null=True, blank=True)
    file_url        = models.URLField(null=True, blank=True)
    file_name       = models.CharField(max_length=200, null=True, blank=True)
    theme           = models.CharField(max_length=20, default='dark', null=True, blank=True)
    required_offers = models.PositiveSmallIntegerField(default=1)
    total_views     = models.PositiveIntegerField(default=0)
    total_unlocks   = models.PositiveIntegerField(default=0)
    total_earnings  = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    is_active       = models.BooleanField(default=True)

    class Meta:
        db_table     = 'content_lock'
        verbose_name = _('Content Lock')

    def __str__(self):
        return f'{self.publisher.username} — {self.lock_type}: {self.title}'


class SubIDClick(TimestampedModel):
    """SubID click tracking — DB persistent।"""
    publisher   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subid_clicks', null=True, blank=True)
    campaign    = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='subid_clicks', null=True, blank=True)
    click_id    = models.CharField(max_length=40, unique=True, db_index=True, null=True, blank=True)
    s1          = models.CharField(max_length=64, blank=True, db_index=True, null=True)
    s2          = models.CharField(max_length=64, blank=True, db_index=True, null=True)
    s3          = models.CharField(max_length=64, null=True, blank=True)
    s4          = models.CharField(max_length=64, null=True, blank=True)
    s5          = models.CharField(max_length=64, null=True, blank=True)
    country     = models.CharField(max_length=2, null=True, blank=True)
    device      = models.CharField(max_length=20, null=True, blank=True)
    ip_hash     = models.CharField(max_length=64, null=True, blank=True)
    is_converted= models.BooleanField(default=False, db_index=True)
    payout      = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    converted_at= models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'subid_click'
        verbose_name = _('SubID Click')
        indexes      = [models.Index(fields=['publisher', 'created_at'])]

    def __str__(self):
        return f'Click {self.click_id[:8]} — s1:{self.s1}'


class PayoutBatch(TimestampedModel):
    """Bulk payout batch — tracking all payouts।"""
    class BatchStatus(models.TextChoices):
        PENDING    = 'pending',    _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED  = 'completed',  _('Completed')
        FAILED     = 'failed',     _('Failed')
        CANCELLED  = 'cancelled',  _('Cancelled')

    batch_id       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    publisher      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payout_batches', null=True, blank=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    method         = models.CharField(max_length=30,
        choices=[('paypal','PayPal'),('payoneer','Payoneer'),('wire','Wire'),('ach','ACH'),
                 ('usdt_trc20','USDT TRC20'),('usdt_erc20','USDT ERC20'),('usdt_bep20','USDT BEP20'),('btc','Bitcoin')])
    method_details = models.JSONField(default=dict)
    status         = BatchStatus.choices and models.CharField(max_length=20, default='pending', choices=BatchStatus.choices, null=True, blank=True)
    fee            = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    net_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tx_hash        = models.CharField(max_length=200, null=True, blank=True)
    processed_at   = models.DateTimeField(null=True, blank=True)
    processed_by   = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                        on_delete=models.SET_NULL, related_name='processed_payouts')
    notes          = models.TextField(blank=True)

    class Meta:
        db_table     = 'payout_batch'
        verbose_name = _('Payout Batch')
        ordering     = ['-created_at']

    def __str__(self):
        return f'Payout #{str(self.batch_id)[:8]} — {self.publisher.username} ${self.amount} [{self.method}]'


class IPBlacklistModel(TimestampedModel):
    """IP blacklist — persistent DB।"""
    ip_address  = models.GenericIPAddressField(db_index=True)
    cidr        = models.CharField(max_length=20, null=True, blank=True)
    reason      = models.TextField(default='')
    severity    = models.CharField(max_length=20, default='permanent',
        choices=[('warn','Warn'),('temp_ban','Temp Ban'),('permanent','Permanent')])
    expires_at  = models.DateTimeField(null=True, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    hit_count   = models.PositiveIntegerField(default=0)
    last_hit    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'ip_blacklist'
        verbose_name = _('IP Blacklist')

    def __str__(self):
        return f'Blocked: {self.ip_address} [{self.severity}]'


class TrackingDomain(TimestampedModel):
    """Custom tracking domains for publishers।"""
    publisher   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tracking_domains', null=True, blank=True)
    domain      = models.CharField(max_length=200, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    ssl_enabled = models.BooleanField(default=False)
    dns_target  = models.CharField(max_length=200, null=True, blank=True)
    total_clicks= models.PositiveIntegerField(default=0)
    is_active   = models.BooleanField(default=True)

    class Meta:
        db_table     = 'tracking_domain'
        verbose_name = _('Tracking Domain')

    def __str__(self):
        return f'{self.domain} — {self.publisher.username}'


class SystemConfig(models.Model):
    """Global system configuration — key-value store।"""
    key          = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    value        = models.TextField(default='')
    value_type   = models.CharField(max_length=20, default='string',
        choices=[('string','String'),('integer','Integer'),('decimal','Decimal'),('boolean','Boolean'),('json','JSON')])
    description  = models.TextField(blank=True)
    is_public    = models.BooleanField(default=False)
    updated_at   = models.DateTimeField(auto_now=True)
    updated_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table     = 'system_config'
        verbose_name = _('System Config')

    def __str__(self):
        return f'{self.key} = {self.value[:50]}'

    def get_typed_value(self):
        if self.value_type == 'integer':  return int(self.value)
        if self.value_type == 'decimal':  return Decimal(self.value)
        if self.value_type == 'boolean':  return self.value.lower() in ('true','1','yes')
        if self.value_type == 'json':
            import json; return json.loads(self.value)
        return self.value
