# api/offer_inventory/models.py
#
# ╔══════════════════════════════════════════════════════════╗
# ║         OFFER INVENTORY — FULL MODEL DEFINITIONS         ║
# ║  100 Classes | 6 Sections | Clean Architecture Pattern   ║
# ╚══════════════════════════════════════════════════════════╝
#
# Sections:
#   §1  — Offer & Network Management      (20 models)
#   §2  — Tracking & Conversion           (15 models)
#   §3  — Fraud & Security                (15 models)
#   §4  — Finance & Payment               (15 models)
#   §5  — User & Targeting                (15 models)
#   §6  — Analytics & System              (20 models)

from django.db import models
from django.conf import settings
from django.core.validators import (
    MinValueValidator, MaxValueValidator, URLValidator
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from core.models import TimeStampedModel

# ─────────────────────────────────────────────────────────────
#  Tenant shortcut — reused in every model
# ─────────────────────────────────────────────────────────────
def _tenant_fk():
    return models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )


# ═══════════════════════════════════════════════════════════════════
# §1  OFFER & NETWORK MANAGEMENT   (২০টি ক্লাস)
# ═══════════════════════════════════════════════════════════════════

class OfferNetwork(TimeStampedModel):
    """
    External affiliate / ad network (e.g. Tapjoy, Fyber, AdGem).
    প্রতিটি network থেকে অফার আসে।
    """
    class Status(models.TextChoices):
        ACTIVE   = 'active',   _('Active')
        INACTIVE = 'inactive', _('Inactive')
        TESTING  = 'testing',  _('Testing')

    tenant           = _tenant_fk()
    name             = models.CharField(max_length=120, unique=True, null=True, blank=True)
    slug             = models.SlugField(max_length=120, unique=True, null=True, blank=True)
    base_url         = models.URLField(null=True, blank=True)
    api_key          = models.CharField(max_length=255, null=True, blank=True)
    api_secret       = models.CharField(max_length=255, null=True, blank=True)
    postback_url     = models.URLField(null=True, blank=True)
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, null=True, blank=True)
    is_s2s_enabled   = models.BooleanField(default=True,  help_text="Server-to-server postback সক্রিয়?")
    priority         = models.PositiveSmallIntegerField(default=5, help_text="১=সর্বোচ্চ অগ্রাধিকার")
    revenue_share_pct= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('70.00'))
    notes            = models.TextField(blank=True)

    class Meta:
        app_label   = 'offer_inventory'
        ordering    = ['priority', 'name']
        verbose_name = _('Offer Network')

    def __str__(self):
        return self.name


class OfferCategory(TimeStampedModel):
    """অফারের বিভাগ — Gaming, Survey, App Install ইত্যাদি।"""
    tenant      = _tenant_fk()
    name        = models.CharField(max_length=100, unique=True, null=True, blank=True)
    slug        = models.SlugField(max_length=100, unique=True, null=True, blank=True)
    icon_url    = models.URLField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label   = 'offer_inventory'
        ordering    = ['sort_order', 'name']
        verbose_name = _('Offer Category')

    def __str__(self):
        return self.name


class Offer(TimeStampedModel):
    """
    একটি একক অফার (task/ad/survey)।
    ইউজার এটি complete করে reward পায়।
    """
    class Status(models.TextChoices):
        ACTIVE         = 'active',         _('Active')
        PAUSED         = 'paused',         _('Paused')
        EXPIRED        = 'expired',        _('Expired')
        DRAFT          = 'draft',          _('Draft')
        REJECTED       = 'rejected',       _('Rejected')
        PENDING_REVIEW = 'pending_review', _('Pending Review')

    class RewardType(models.TextChoices):
        COINS    = 'coins',    _('Coins')
        CASH     = 'cash',     _('Cash')
        POINTS   = 'points',   _('Points')
        BONUS    = 'bonus',    _('Bonus')

    tenant           = _tenant_fk()
    network          = models.ForeignKey(OfferNetwork,  on_delete=models.SET_NULL, null=True, blank=True, related_name='offers')
    category         = models.ForeignKey(OfferCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='offers')
    external_offer_id= models.CharField(max_length=255, blank=True, db_index=True, null=True)
    title            = models.CharField(max_length=255, null=True, blank=True)
    description      = models.TextField(blank=True)
    instructions     = models.TextField(blank=True)
    image_url        = models.URLField(null=True, blank=True)
    offer_url        = models.URLField(null=True, blank=True)
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, null=True, blank=True)
    reward_type      = models.CharField(max_length=20, choices=RewardType.choices, default=RewardType.COINS, null=True, blank=True)
    reward_amount    = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    payout_amount    = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'), help_text="নেটওয়ার্ক থেকে আমরা কত পাই")
    estimated_time   = models.PositiveSmallIntegerField(default=5, help_text="মিনিটে আনুমানিক সময়")
    difficulty       = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    is_featured      = models.BooleanField(default=False)
    is_recurring     = models.BooleanField(default=False)
    starts_at        = models.DateTimeField(null=True, blank=True)
    expires_at       = models.DateTimeField(null=True, blank=True)
    max_completions  = models.PositiveIntegerField(null=True, blank=True, help_text="মোট কতবার complete হতে পারবে")
    total_completions= models.PositiveIntegerField(default=0)
    conversion_rate  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))

    class Meta:
        app_label   = 'offer_inventory'
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['network', 'status']),
        ]
        verbose_name = _('Offer')

    def __str__(self):
        return self.title

    @property
    def is_available(self):
        now = timezone.now()
        if self.status != self.Status.ACTIVE:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        if self.max_completions and self.total_completions >= self.max_completions:
            return False
        return True


class OfferWallConfiguration(TimeStampedModel):
    """
    অফারওয়াল UI-এর গ্লোবাল কনফিগারেশন।
    প্রতি tenant-এর জন্য আলাদা।
    """
    tenant               = _tenant_fk()
    title                = models.CharField(max_length=200, default='Earn Rewards', null=True, blank=True)
    logo_url             = models.URLField(null=True, blank=True)
    primary_color        = models.CharField(max_length=7, default='#6C63FF', null=True, blank=True)
    secondary_color      = models.CharField(max_length=7, default='#FF6584', null=True, blank=True)
    min_payout           = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10.00'))
    max_daily_offers     = models.PositiveSmallIntegerField(default=20)
    show_completed       = models.BooleanField(default=False)
    allow_revoked        = models.BooleanField(default=False)
    maintenance_mode     = models.BooleanField(default=False)
    maintenance_message  = models.TextField(blank=True)
    tos_url              = models.URLField(null=True, blank=True)
    support_email        = models.EmailField(blank=True)

    class Meta:
        app_label   = 'offer_inventory'
        verbose_name = _('OfferWall Configuration')

    def __str__(self):
        return f"OfferWall Config — {self.tenant}"


class OfferLog(TimeStampedModel):
    """অফারের status পরিবর্তনের history।"""
    offer      = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    old_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20, null=True, blank=True)
    note       = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.offer} | {self.old_status} → {self.new_status}"


class SmartLink(TimeStampedModel):
    """
    Dynamic URL যা user/device দেখে সেরা অফার দেখায়।
    একটি SmartLink → অনেক Offer।
    """
    tenant       = _tenant_fk()
    slug         = models.SlugField(max_length=150, unique=True, null=True, blank=True)
    offers       = models.ManyToManyField(Offer, blank=True, related_name='smart_links')
    algorithm    = models.CharField(max_length=50, default='highest_payout', help_text="highest_payout | best_cvr | random", null=True, blank=True)
    is_active    = models.BooleanField(default=True)
    click_count  = models.PositiveBigIntegerField(default=0)
    custom_params= models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"SmartLink /{self.slug}"


class OfferCap(TimeStampedModel):
    """
    অফারের daily/weekly/total conversion cap।
    Cap পার হলে অফার auto-pause হবে।
    """
    class CapType(models.TextChoices):
        DAILY   = 'daily',   _('Daily')
        WEEKLY  = 'weekly',  _('Weekly')
        MONTHLY = 'monthly', _('Monthly')
        TOTAL   = 'total',   _('Total')

    offer         = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='caps', null=True, blank=True)
    cap_type      = models.CharField(max_length=10, choices=CapType.choices, null=True, blank=True)
    cap_limit     = models.PositiveIntegerField()
    current_count = models.PositiveIntegerField(default=0)
    reset_at      = models.DateTimeField(null=True, blank=True)
    pause_on_hit  = models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'
        unique_together = ('offer', 'cap_type')

    def __str__(self):
        return f"{self.offer.title} | {self.cap_type} cap: {self.current_count}/{self.cap_limit}"

    @property
    def is_reached(self):
        return self.current_count >= self.cap_limit


class OfferInventorySource(TimeStampedModel):
    """External feed/API source যেখান থেকে অফার pull করা হয়।"""
    tenant        = _tenant_fk()
    network       = models.ForeignKey(OfferNetwork, on_delete=models.CASCADE, related_name='sources', null=True, blank=True)
    feed_url      = models.URLField(null=True, blank=True)
    feed_type     = models.CharField(max_length=20, default='json', help_text="json | xml | csv", null=True, blank=True)
    auth_headers  = models.JSONField(default=dict, blank=True)
    last_synced   = models.DateTimeField(null=True, blank=True)
    sync_interval = models.PositiveSmallIntegerField(default=30, help_text="মিনিটে sync interval")
    is_enabled    = models.BooleanField(default=True)
    offers_pulled = models.PositiveIntegerField(default=0)
    error_count   = models.PositiveSmallIntegerField(default=0)
    last_error    = models.TextField(blank=True)
    # ── Postback Security ──────────────────────────────────────
    allowed_ips   = models.JSONField(
        default=list, blank=True,
        help_text='Trusted postback IPs e.g. ["54.1.2.3", "185.4.5.0/24"]'
    )
    postback_secret = models.CharField(
        max_length=255, blank=True,
        help_text='HMAC secret for postback signature verification')

    class Meta:
        app_label = 'offer_inventory'
        indexes   = [
            models.Index(fields=['network', 'is_enabled'], name='source_network_enabled_idx'),
        ]

    def __str__(self):
        return f"{self.network.name} — {self.feed_url[:60]}"


class DirectAdvertiser(TimeStampedModel):
    """
    সরাসরি চুক্তিবদ্ধ advertiser।
    নেটওয়ার্ক ছাড়া offer দিতে পারে।
    """
    tenant          = _tenant_fk()
    company_name    = models.CharField(max_length=200, null=True, blank=True)
    contact_name    = models.CharField(max_length=150, null=True, blank=True)
    contact_email   = models.EmailField()
    website         = models.URLField(null=True, blank=True)
    agreed_rev_share= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('60.00'))
    is_verified     = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=True)
    notes           = models.TextField(blank=True)

    class Meta:
        app_label   = 'offer_inventory'
        verbose_name = _('Direct Advertiser')

    def __str__(self):
        return self.company_name


class Campaign(TimeStampedModel):
    """একটি advertiser-এর campaign যা একাধিক offer ধারণ করে।"""
    class Status(models.TextChoices):
        DRAFT   = 'draft',   _('Draft')
        LIVE    = 'live',    _('Live')
        PAUSED  = 'paused',  _('Paused')
        ENDED   = 'ended',   _('Ended')

    tenant       = _tenant_fk()
    advertiser   = models.ForeignKey(DirectAdvertiser, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    network      = models.ForeignKey(OfferNetwork,     on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    name         = models.CharField(max_length=200, null=True, blank=True)
    status       = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, null=True, blank=True)
    budget       = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    spent        = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    daily_cap    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    starts_at    = models.DateTimeField(null=True, blank=True)
    ends_at      = models.DateTimeField(null=True, blank=True)
    goal         = models.CharField(max_length=50, default='cpa', help_text="cpa | cpi | cpl | cpc", null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def remaining_budget(self):
        return self.budget - self.spent


class OfferLandingPage(TimeStampedModel):
    """অফারের আগে দেখানো custom landing page।"""
    offer       = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='landing_pages', null=True, blank=True)
    title       = models.CharField(max_length=255, null=True, blank=True)
    html_content= models.TextField(blank=True)
    redirect_url= models.URLField(null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    variant_key = models.CharField(max_length=50, default='default', help_text="A/B test key", null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.offer.title} — {self.title}"


class OfferCreative(TimeStampedModel):
    """Banner/image/video creative অফারের সাথে যুক্ত।"""
    class CreativeType(models.TextChoices):
        BANNER  = 'banner',  _('Banner')
        VIDEO   = 'video',   _('Video')
        NATIVE  = 'native',  _('Native')
        ICON    = 'icon',    _('Icon')

    offer         = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='creatives', null=True, blank=True)
    creative_type = models.CharField(max_length=10, choices=CreativeType.choices, null=True, blank=True)
    asset_url     = models.URLField(null=True, blank=True)
    width         = models.PositiveSmallIntegerField(null=True, blank=True)
    height        = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_secs = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Video duration")
    is_approved   = models.BooleanField(default=False)
    click_count   = models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.offer.title} | {self.creative_type}"


class IncentiveLevel(TimeStampedModel):
    """Milestone-ভিত্তিক bonus — ১০টি অফার করলে অতিরিক্ত reward।"""
    tenant          = _tenant_fk()
    name            = models.CharField(max_length=100, null=True, blank=True)
    required_actions= models.PositiveIntegerField(help_text="কতটি action দরকার")
    bonus_amount    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    reward_type     = models.CharField(max_length=20, default='coins', null=True, blank=True)
    is_active       = models.BooleanField(default=True)
    icon_url        = models.URLField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['required_actions']

    def __str__(self):
        return f"{self.name} — {self.required_actions} actions"


class OfferDraft(TimeStampedModel):
    """অ্যাডমিন অফার save করার আগে draft হিসেবে রাখে।"""
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='offer_drafts')
    title       = models.CharField(max_length=255, null=True, blank=True)
    data        = models.JSONField(default=dict, help_text="Offer fields JSON")
    last_edited = models.DateTimeField(auto_now=True)
    is_submitted= models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-last_edited']

    def __str__(self):
        return f"Draft: {self.title}"


class OfferSchedule(TimeStampedModel):
    """অফারকে নির্দিষ্ট সময়ে auto-activate/deactivate করে।"""
    class Action(models.TextChoices):
        ACTIVATE   = 'activate',   _('Activate')
        DEACTIVATE = 'deactivate', _('Deactivate')
        PAUSE      = 'pause',      _('Pause')

    offer        = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='schedules', null=True, blank=True)
    action       = models.CharField(max_length=15, choices=Action.choices, null=True, blank=True)
    scheduled_at = models.DateTimeField()
    is_executed  = models.BooleanField(default=False)
    executed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['scheduled_at']

    def __str__(self):
        return f"{self.offer.title} → {self.action} @ {self.scheduled_at}"


class NetworkPinger(TimeStampedModel):
    """নেটওয়ার্ক health check log — প্রতি X মিনিটে ping করে।"""
    network       = models.ForeignKey(OfferNetwork, on_delete=models.CASCADE, related_name='pings', null=True, blank=True)
    response_code = models.PositiveSmallIntegerField()
    response_time = models.FloatField(help_text="Milliseconds")
    is_up         = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.network.name} | {self.response_code} | {self.response_time}ms"


class OfferRating(TimeStampedModel):
    """User-এর দেওয়া অফার rating (১–৫)।"""
    offer      = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True)
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_ratings', null=True, blank=True)
    score      = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review     = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('offer', 'user')

    def __str__(self):
        return f"{self.offer.title} — ★{self.score} by {self.user}"


class OfferQuestionnaire(TimeStampedModel):
    """Survey-type অফারের প্রশ্নাবলী।"""
    offer    = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    question = models.TextField()
    options  = models.JSONField(default=list, help_text='["A", "B", "C"]')
    answer   = models.CharField(max_length=500, blank=True, help_text="Correct answer (যদি থাকে, null=True)")
    order    = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['order']

    def __str__(self):
        return f"{self.offer.title} | Q{self.order}"


class OfferTag(TimeStampedModel):
    """অফারে tag — #easy, #gaming, #survey ইত্যাদি।"""
    name    = models.CharField(max_length=60, unique=True, null=True, blank=True)
    slug    = models.SlugField(max_length=60, unique=True, null=True, blank=True)
    offers  = models.ManyToManyField(Offer, blank=True, related_name='tags')
    color   = models.CharField(max_length=7, default='#6C63FF', null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"#{self.name}"


class OfferVisibilityRule(TimeStampedModel):
    """
    কোন ইউজার কোন অফার দেখতে পাবে তার নিয়ম।
    Country, device, user level ইত্যাদির উপর ভিত্তি করে।
    """
    offer         = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='visibility_rules', null=True, blank=True)
    rule_type     = models.CharField(max_length=30, help_text="country | device | user_level | segment", null=True, blank=True)
    operator      = models.CharField(max_length=10, default='include', help_text="include | exclude", null=True, blank=True)
    values        = models.JSONField(default=list, help_text='["BD","IN"] or ["android"] etc.')
    priority      = models.PositiveSmallIntegerField(default=0)
    is_active     = models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['priority']

    def __str__(self):
        return f"{self.offer.title} | {self.rule_type} {self.operator}"


# ═══════════════════════════════════════════════════════════════════
# §2  TRACKING & CONVERSION   (১৫টি ক্লাস)
# ═══════════════════════════════════════════════════════════════════

class TrafficSource(TimeStampedModel):
    """Click কোথা থেকে এলো — organic, referral, paid ইত্যাদি।"""
    tenant     = _tenant_fk()
    name       = models.CharField(max_length=100, null=True, blank=True)
    source_key = models.CharField(max_length=50, unique=True, null=True, blank=True)
    is_paid    = models.BooleanField(default=False)
    notes      = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return self.name


class TrackingDomain(TimeStampedModel):
    """Custom tracking domain — click.mysite.com।"""
    tenant     = _tenant_fk()
    domain     = models.CharField(max_length=255, unique=True, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    ssl_status = models.CharField(max_length=20, default='pending', null=True, blank=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return self.domain


class SubID(TimeStampedModel):
    """Sub-affiliate ID tracking — s1, s2, s3, s4, s5।"""
    tenant   = _tenant_fk()
    offer    = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='sub_ids', null=True, blank=True)
    user     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_ids')
    s1       = models.CharField(max_length=255, blank=True, db_index=True, null=True)
    s2       = models.CharField(max_length=255, null=True, blank=True)
    s3       = models.CharField(max_length=255, null=True, blank=True)
    s4       = models.CharField(max_length=255, null=True, blank=True)
    s5       = models.CharField(max_length=255, null=True, blank=True)
    revenue  = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    class Meta:
        app_label = 'offer_inventory'
        indexes   = [models.Index(fields=['s1', 'offer'])]

    def __str__(self):
        return f"SubID {self.s1} | {self.offer}"


class Click(TimeStampedModel):
    """
    প্রতিটি offer click-এর রেকর্ড।
    Fraud detection-এর ভিত্তি।
    """
    tenant          = _tenant_fk()
    offer           = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, related_name='clicks')
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='offer_clicks')
    sub_id          = models.ForeignKey(SubID, on_delete=models.SET_NULL, null=True, blank=True, related_name='clicks')
    traffic_source  = models.ForeignKey(TrafficSource, on_delete=models.SET_NULL, null=True, blank=True)
    tracking_domain = models.ForeignKey(TrackingDomain, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address      = models.GenericIPAddressField(db_index=True)
    user_agent      = models.TextField(blank=True)
    country_code    = models.CharField(max_length=2, blank=True, db_index=True, null=True)
    device_type     = models.CharField(max_length=20, null=True, blank=True)   # mobile|desktop|tablet
    os              = models.CharField(max_length=50, null=True, blank=True)
    browser         = models.CharField(max_length=50, null=True, blank=True)
    referrer        = models.URLField(null=True, blank=True)
    click_token     = models.CharField(max_length=64, unique=True, db_index=True, null=True, blank=True)
    is_unique       = models.BooleanField(default=True)
    is_fraud        = models.BooleanField(default=False)
    fraud_reason    = models.CharField(max_length=255, null=True, blank=True)
    converted       = models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']
        indexes   = [
            # High-cardinality lookup indexes
            models.Index(fields=['click_token'],                   name='click_token_idx'),
            models.Index(fields=['user'],                          name='click_user_idx'),
            models.Index(fields=['offer'],                         name='click_offer_idx'),
            models.Index(fields=['ip_address'],                    name='click_ip_idx'),
            # Composite indexes for common query patterns
            models.Index(fields=['user', 'offer', 'created_at'],  name='click_user_offer_date_idx'),
            models.Index(fields=['ip_address', 'offer', 'created_at'], name='click_ip_offer_date_idx'),
            models.Index(fields=['is_fraud', 'created_at'],        name='click_fraud_date_idx'),
            models.Index(fields=['converted', 'created_at'],       name='click_converted_date_idx'),
            # Fraud scan index
            models.Index(fields=['country_code', 'created_at'],   name='click_country_date_idx'),
        ]

    def __str__(self):
        return f"Click {self.click_token[:12]}... | {self.offer}"


class Impression(TimeStampedModel):
    """অফার দেখানোর রেকর্ড (view ≠ click)।"""
    offer      = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, related_name='impressions')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='offer_impressions')
    ip_address = models.GenericIPAddressField()
    country    = models.CharField(max_length=2, null=True, blank=True)
    device     = models.CharField(max_length=20, null=True, blank=True)
    is_viewable= models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Impression | {self.offer} | {self.ip_address}"


class ConversionStatus(TimeStampedModel):
    """Conversion-এর state machine।"""
    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending')
        APPROVED  = 'approved',  _('Approved')
        REJECTED  = 'rejected',  _('Rejected')
        REVERSED  = 'reversed',  _('Reversed')
        CHARGEBACK= 'chargeback',_('Chargeback')

    name        = models.CharField(max_length=20, choices=Status.choices, unique=True, null=True, blank=True)
    description = models.TextField(blank=True)
    is_terminal = models.BooleanField(default=False, help_text="এই state থেকে আর change হবে না?")

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return self.name


class Conversion(TimeStampedModel):
    """
    একটি সফল offer completion।
    Reward এখান থেকে generate হয়।
    """
    tenant        = _tenant_fk()
    click         = models.OneToOneField(Click, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversion')
    offer         = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, related_name='conversions')
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='conversions')
    status        = models.ForeignKey(ConversionStatus, on_delete=models.SET_NULL, null=True)
    payout_amount = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    reward_amount = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    # UNIQUE on transaction_id prevents duplicate payouts at DB level
    transaction_id= models.CharField(max_length=255, blank=True, db_index=True, unique=True, null=True)
    ip_address    = models.GenericIPAddressField(blank=True, null=True)
    country_code  = models.CharField(max_length=2, null=True, blank=True)
    postback_sent = models.BooleanField(default=False)
    postback_at   = models.DateTimeField(null=True, blank=True)
    approved_at   = models.DateTimeField(null=True, blank=True)
    rejected_at   = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=255, null=True, blank=True)
    is_duplicate  = models.BooleanField(default=False)
    raw_postback  = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']
        indexes   = [
            # Core lookup indexes
            models.Index(fields=['user'],                          name='conv_user_idx'),
            models.Index(fields=['offer'],                         name='conv_offer_idx'),
            models.Index(fields=['transaction_id'],                name='conv_txid_idx'),
            # Composite indexes for common query patterns
            models.Index(fields=['user', 'offer', 'created_at'],  name='conv_user_offer_date_idx'),
            models.Index(fields=['status', 'postback_sent'],       name='conv_status_postback_idx'),
            models.Index(fields=['status', 'created_at'],          name='conv_status_date_idx'),
            models.Index(fields=['is_duplicate', 'created_at'],    name='conv_dup_date_idx'),
            # Admin dashboard query index
            models.Index(fields=['approved_at'],                   name='conv_approved_at_idx'),
        ]
        # DB-level guarantee: one conversion per click
        constraints = [
            models.UniqueConstraint(
                fields=['click'],
                condition=models.Q(click__isnull=False),
                name='unique_conversion_per_click',
            ),
        ]

    def __str__(self):
        return f"Conversion | {self.offer} | {self.user}"


class PostbackLog(TimeStampedModel):
    """Network-এ postback পাঠানোর log।"""
    class Method(models.TextChoices):
        GET  = 'GET',  'GET'
        POST = 'POST', 'POST'

    conversion    = models.ForeignKey(Conversion, on_delete=models.CASCADE, related_name='postback_logs', null=True, blank=True)
    url           = models.URLField(null=True, blank=True)
    method        = models.CharField(max_length=4, choices=Method.choices, default=Method.GET, null=True, blank=True)
    request_body  = models.TextField(blank=True)
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    is_success    = models.BooleanField(default=False)
    retry_count   = models.PositiveSmallIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Postback {self.response_code} | {self.conversion}"


class PixelLog(TimeStampedModel):
    """Conversion pixel fire-এর log।"""
    conversion  = models.ForeignKey(Conversion, on_delete=models.CASCADE, related_name='pixel_logs', null=True, blank=True)
    pixel_url   = models.URLField(null=True, blank=True)
    fired_at    = models.DateTimeField(auto_now_add=True)
    is_fired    = models.BooleanField(default=False)
    error       = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Pixel | {self.conversion} | {'✓' if self.is_fired else '✗'}"


class ConversionReversal(TimeStampedModel):
    """Approved conversion বাতিল করা — chargeback বা fraud এ।"""
    conversion    = models.OneToOneField(Conversion, on_delete=models.CASCADE, related_name='reversal', null=True, blank=True)
    reason        = models.TextField()
    reversed_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='reversals_made')
    amount_clawed = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    wallet_debited= models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Reversal | {self.conversion}"


class ClickSignature(TimeStampedModel):
    """
    Tamper-proof click token।
    HMAC দিয়ে sign করা হয়।
    """
    click      = models.OneToOneField(Click, on_delete=models.CASCADE, related_name='signature', null=True, blank=True)
    signature  = models.CharField(max_length=128, null=True, blank=True)
    algorithm  = models.CharField(max_length=20, default='hmac-sha256', null=True, blank=True)
    is_valid   = models.BooleanField(default=True)
    verified_at= models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Sig {self.signature[:16]}... | {'✓' if self.is_valid else '✗'}"


class S2SRequest(TimeStampedModel):
    """Server-to-server postback request এর raw log।"""
    offer           = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, related_name='s2s_requests')
    source_ip       = models.GenericIPAddressField()
    method          = models.CharField(max_length=6, default='GET', null=True, blank=True)
    url             = models.URLField(null=True, blank=True)
    params          = models.JSONField(default=dict)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    processed       = models.BooleanField(default=False)
    error           = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"S2S {self.method} | {self.source_ip}"


class RedirectLog(TimeStampedModel):
    """SmartLink redirect-এর log।"""
    smart_link   = models.ForeignKey(SmartLink, on_delete=models.SET_NULL, null=True, related_name='offer_inventory_redirect_logs')
    offer        = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, related_name='offer_inventory_redirect_logs')
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.TextField(blank=True)
    final_url    = models.URLField(null=True, blank=True)
    redirect_code= models.PositiveSmallIntegerField(default=302)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Redirect → {self.final_url[:60]}"


class LeadQualityScore(TimeStampedModel):
    """Conversion-এর quality score — high/medium/low।"""
    conversion    = models.OneToOneField(Conversion, on_delete=models.CASCADE, related_name='quality_score', null=True, blank=True)
    score         = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    grade         = models.CharField(max_length=10, default='medium', null=True, blank=True)
    factors       = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Quality {self.score:.1f} ({self.grade}) | {self.conversion}"


class DuplicateConversionFilter(TimeStampedModel):
    """একই user-offer-এ duplicate conversion detect করে।"""
    offer         = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='dup_filters', null=True, blank=True)
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dup_filters', null=True, blank=True)
    fingerprint   = models.CharField(max_length=128, db_index=True, null=True, blank=True)
    first_seen    = models.DateTimeField(auto_now_add=True)
    attempt_count = models.PositiveSmallIntegerField(default=1)
    last_attempt  = models.DateTimeField(auto_now=True)
    is_blocked    = models.BooleanField(default=False)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('offer', 'user', 'fingerprint')

    def __str__(self):
        return f"DupFilter | {self.user} | {self.offer} | attempts: {self.attempt_count}"


# ═══════════════════════════════════════════════════════════════════
# §3  FRAUD & SECURITY   (১৫টি ক্লাস)
# ═══════════════════════════════════════════════════════════════════

class BlacklistedIP(TimeStampedModel):
    """Block করা IP address।"""
    tenant      = _tenant_fk()
    ip_address  = models.GenericIPAddressField(db_index=True)
    ip_range    = models.CharField(max_length=50, blank=True, help_text="CIDR e.g. 192.168.0.0/24", null=True)
    reason      = models.CharField(max_length=255, null=True, blank=True)
    source      = models.CharField(max_length=50, default='manual', help_text="manual | auto | external", null=True, blank=True)
    is_permanent= models.BooleanField(default=False)
    expires_at  = models.DateTimeField(null=True, blank=True)
    blocked_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='blocked_ips')

    class Meta:
        app_label = 'offer_inventory'
        indexes   = [models.Index(fields=['ip_address', 'expires_at'])]

    def __str__(self):
        return f"Blocked: {self.ip_address} ({self.reason})"


class ProxyList(TimeStampedModel):
    """Known proxy/VPN/TOR IP range।"""
    ip_range    = models.CharField(max_length=50, unique=True, null=True, blank=True)
    provider    = models.CharField(max_length=100, null=True, blank=True)
    proxy_type  = models.CharField(max_length=20, help_text="vpn | tor | datacenter | proxy", null=True, blank=True)
    risk_score  = models.PositiveSmallIntegerField(default=80)
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.proxy_type}: {self.ip_range}"


class UserRiskProfile(TimeStampedModel):
    """প্রতিটি user-এর fraud risk score।"""
    user            = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='risk_profile', null=True, blank=True)
    risk_score      = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    risk_level      = models.CharField(max_length=10, default='low', help_text="low | medium | high | critical", null=True, blank=True)
    total_flags     = models.PositiveSmallIntegerField(default=0)
    last_flagged_at = models.DateTimeField(null=True, blank=True)
    is_suspended    = models.BooleanField(default=False)
    suspension_reason=models.TextField(blank=True)
    notes           = models.TextField(blank=True)
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_risk_profiles')

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-risk_score']

    def __str__(self):
        return f"{self.user} | Risk: {self.risk_score:.1f} ({self.risk_level})"


class FraudRule(TimeStampedModel):
    """Auto fraud detection rule।"""
    class Action(models.TextChoices):
        FLAG     = 'flag',     _('Flag')
        BLOCK    = 'block',    _('Block')
        SUSPEND  = 'suspend',  _('Suspend')
        ALERT    = 'alert',    _('Alert')

    name        = models.CharField(max_length=150, unique=True, null=True, blank=True)
    description = models.TextField(blank=True)
    conditions  = models.JSONField(default=dict, help_text='{"max_clicks_per_hour": 50}')
    action      = models.CharField(max_length=10, choices=Action.choices, null=True, blank=True)
    severity    = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    is_active   = models.BooleanField(default=True)
    trigger_count=models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-severity']

    def __str__(self):
        return f"Rule: {self.name} → {self.action}"


class FraudAttempt(TimeStampedModel):
    """Fraud rule trigger হলে log হয়।"""
    rule        = models.ForeignKey(FraudRule, on_delete=models.SET_NULL, null=True, related_name='attempts')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='fraud_attempts')
    ip_address  = models.GenericIPAddressField(blank=True, null=True)
    description = models.TextField()
    evidence    = models.JSONField(default=dict, blank=True)
    action_taken= models.CharField(max_length=20, null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_fraud')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Fraud: {self.rule} | {self.user} | {'resolved' if self.is_resolved else 'open'}"


class DeviceFingerprint(TimeStampedModel):
    """Browser/device fingerprint — fraud linkage-এ ব্যবহার হয়।"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='fingerprints')
    fingerprint = models.CharField(max_length=128, db_index=True, null=True, blank=True)
    user_agent  = models.TextField(blank=True)
    screen_res  = models.CharField(max_length=20, null=True, blank=True)
    timezone    = models.CharField(max_length=60, null=True, blank=True)
    language    = models.CharField(max_length=10, null=True, blank=True)
    canvas_hash = models.CharField(max_length=64, null=True, blank=True)
    webgl_hash  = models.CharField(max_length=64, null=True, blank=True)
    is_flagged  = models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'
        indexes   = [models.Index(fields=['fingerprint'])]

    def __str__(self):
        return f"FP {self.fingerprint[:16]}... | {'⚠' if self.is_flagged else '✓'}"


class HoneypotLog(TimeStampedModel):
    """Honeypot trap তে ধরা পড়লে log।"""
    ip_address  = models.GenericIPAddressField()
    user_agent  = models.TextField(blank=True)
    trap_url    = models.CharField(max_length=255, null=True, blank=True)
    payload     = models.TextField(blank=True)
    is_bot      = models.BooleanField(default=True)
    blocked     = models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Honeypot | {self.ip_address} | {self.trap_url}"


class UserAgentBlacklist(TimeStampedModel):
    """Known bot/crawler user-agent string।"""
    pattern     = models.CharField(max_length=500, unique=True, help_text="Regex or exact string", null=True, blank=True)
    is_regex    = models.BooleanField(default=False)
    description = models.CharField(max_length=255, null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    match_count = models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"UA Blacklist: {self.pattern[:60]}"


class VPNProvider(TimeStampedModel):
    """Known VPN provider list।"""
    name        = models.CharField(max_length=100, unique=True, null=True, blank=True)
    asn_numbers = models.JSONField(default=list, help_text='["AS12345", "AS67890"]')
    risk_level  = models.CharField(max_length=10, default='high', null=True, blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return self.name


class BotSignature(TimeStampedModel):
    """Bot behavior pattern signature।"""
    name           = models.CharField(max_length=150, null=True, blank=True)
    signature_type = models.CharField(max_length=30, help_text="click_speed | ip_rotation | ua_mismatch", null=True, blank=True)
    pattern        = models.JSONField(default=dict)
    severity       = models.PositiveSmallIntegerField(default=5)
    is_active      = models.BooleanField(default=True)
    detections     = models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Bot Sig: {self.name}"


class IPCluster(TimeStampedModel):
    """একই household/org থেকে আসা IP cluster।"""
    label       = models.CharField(max_length=100, null=True, blank=True)
    ip_addresses= models.JSONField(default=list)
    isp         = models.CharField(max_length=150, null=True, blank=True)
    country     = models.CharField(max_length=2, null=True, blank=True)
    risk_score  = models.FloatField(default=0.0)
    is_flagged  = models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Cluster: {self.label} ({len(self.ip_addresses)} IPs)"


class SecurityIncident(TimeStampedModel):
    """Major security event — আক্রমণ, data breach ইত্যাদি।"""
    class Severity(models.TextChoices):
        LOW      = 'low',      _('Low')
        MEDIUM   = 'medium',   _('Medium')
        HIGH     = 'high',     _('High')
        CRITICAL = 'critical', _('Critical')

    title       = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    severity    = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM, null=True, blank=True)
    affected_ips= models.JSONField(default=list)
    affected_users=models.JSONField(default=list)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    actions_taken=models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title}"


class RateLimitLog(TimeStampedModel):
    """Rate limit হিট হলে log।"""
    ip_address  = models.GenericIPAddressField(db_index=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='offer_inventory_rate_limit_logs')
    endpoint    = models.CharField(max_length=255, null=True, blank=True)
    request_count=models.PositiveSmallIntegerField(default=1)
    window_secs = models.PositiveSmallIntegerField(default=60)
    blocked     = models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"RateLimit {self.ip_address} | {self.endpoint}"


class AccountLink(TimeStampedModel):
    """একই person-এর multiple account detect।"""
    primary_user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='primary_links', null=True, blank=True)
    linked_user   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='linked_accounts', null=True, blank=True)
    link_method   = models.CharField(max_length=30, help_text="ip | device | email | phone", null=True, blank=True)
    confidence    = models.FloatField(default=0.0, help_text="০–১ confidence score")
    is_confirmed  = models.BooleanField(default=False)
    is_blocked    = models.BooleanField(default=False)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('primary_user', 'linked_user')

    def __str__(self):
        return f"Link: {self.primary_user} ↔ {self.linked_user} ({self.link_method})"


class SuspiciousActivity(TimeStampedModel):
    """General suspicious activity flag।"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='suspicious_activities')
    ip_address  = models.GenericIPAddressField(blank=True, null=True)
    activity    = models.CharField(max_length=100, null=True, blank=True)
    details     = models.JSONField(default=dict, blank=True)
    risk_score  = models.FloatField(default=0.0)
    reviewed    = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_suspicious')

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Suspicious: {self.activity} | {self.user}"


# ═══════════════════════════════════════════════════════════════════
# §4  FINANCE & PAYMENT   (১৫টি ক্লাস)
# ═══════════════════════════════════════════════════════════════════

class CurrencyRate(TimeStampedModel):
    """Live currency exchange rate।"""
    from_currency = models.CharField(max_length=3, db_index=True, null=True, blank=True)
    to_currency   = models.CharField(max_length=3, db_index=True, null=True, blank=True)
    rate          = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    source        = models.CharField(max_length=50, default='openexchangerates', null=True, blank=True)
    fetched_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('from_currency', 'to_currency')

    def __str__(self):
        return f"{self.from_currency} → {self.to_currency}: {self.rate}"


class PaymentMethod(TimeStampedModel):
    """User withdrawal-এর payment method।"""
    class Provider(models.TextChoices):
        BKASH   = 'bkash',   'bKash'
        NAGAD   = 'nagad',   'Nagad'
        ROCKET  = 'rocket',  'Rocket'
        PAYPAL  = 'paypal',  'PayPal'
        STRIPE  = 'stripe',  'Stripe'
        BANK    = 'bank',    'Bank Transfer'
        CRYPTO  = 'crypto',  'Crypto'

    tenant          = _tenant_fk()
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_methods', null=True, blank=True)
    provider        = models.CharField(max_length=20, choices=Provider.choices, null=True, blank=True)
    account_number  = models.CharField(max_length=255, help_text="Encrypted", null=True, blank=True)
    account_name    = models.CharField(max_length=150, null=True, blank=True)
    is_primary      = models.BooleanField(default=False)
    is_verified     = models.BooleanField(default=False)
    verified_at     = models.DateTimeField(null=True, blank=True)
    last_used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.user} | {self.provider} | ***{self.account_number[-4:]}"


class RevenueShare(TimeStampedModel):
    """Network থেকে পাওয়া revenue-র ভাগ।"""
    offer         = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='revenue_shares', null=True, blank=True)
    conversion    = models.ForeignKey(Conversion, on_delete=models.CASCADE, related_name='revenue_shares', null=True, blank=True)
    gross_revenue = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    platform_cut  = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    user_share    = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    referral_share= models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    currency      = models.CharField(max_length=3, default='BDT', null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"RevShare | {self.conversion} | User: {self.user_share}"


class TaxRecord(TimeStampedModel):
    """Withdrawal-এ প্রযোজ্য tax record।"""
    class TaxType(models.TextChoices):
        VAT    = 'vat',    'VAT'
        TDS    = 'tds',    'TDS'
        GST    = 'gst',    'GST'
        CUSTOM = 'custom', 'Custom'

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tax_records', null=True, blank=True)
    tax_type    = models.CharField(max_length=10, choices=TaxType.choices, null=True, blank=True)
    rate        = models.DecimalField(max_digits=5, decimal_places=2, help_text="শতাংশে", null=True, blank=True)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_amount  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fiscal_year = models.CharField(max_length=10, null=True, blank=True)
    reference   = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Tax {self.tax_type} {self.rate}% | {self.user}"


class ReferralCommission(TimeStampedModel):
    """Referral থেকে আয় হওয়া commission।"""
    referrer      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_commissions', null=True, blank=True)
    referred_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='generated_commissions', null=True, blank=True)
    conversion    = models.ForeignKey(Conversion, on_delete=models.SET_NULL, null=True, blank=True, related_name='referral_commissions')
    commission_pct= models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    amount        = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    is_paid       = models.BooleanField(default=False)
    paid_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"RefComm {self.amount} | {self.referrer} ← {self.referred_user}"


class BonusWallet(TimeStampedModel):
    """Promotional bonus balance — আলাদাভাবে track করা।"""
    user       = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bonus_wallet', null=True, blank=True)
    balance    = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    expires_at = models.DateTimeField(null=True, blank=True)
    source     = models.CharField(max_length=100, blank=True, help_text="promo code | event | admin", null=True)
    is_expired = models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Bonus Wallet | {self.user} | {self.balance}"


class PayoutBatch(TimeStampedModel):
    """একসাথে অনেক withdrawal process করার batch।"""
    class Status(models.TextChoices):
        PENDING    = 'pending',    _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED  = 'completed',  _('Completed')
        FAILED     = 'failed',     _('Failed')

    tenant           = _tenant_fk()
    batch_ref        = models.CharField(max_length=50, unique=True, null=True, blank=True)
    status           = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, null=True, blank=True)
    total_amount     = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_requests   = models.PositiveIntegerField(default=0)
    processed_count  = models.PositiveIntegerField(default=0)
    failed_count     = models.PositiveSmallIntegerField(default=0)
    payment_provider = models.CharField(max_length=30, null=True, blank=True)
    started_at       = models.DateTimeField(null=True, blank=True)
    completed_at     = models.DateTimeField(null=True, blank=True)
    notes            = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Batch {self.batch_ref} | {self.status}"


class Invoice(TimeStampedModel):
    """Advertiser-এর জন্য invoice।"""
    tenant       = _tenant_fk()
    advertiser   = models.ForeignKey(DirectAdvertiser, on_delete=models.SET_NULL, null=True, related_name='invoices')
    invoice_no   = models.CharField(max_length=50, unique=True, null=True, blank=True)
    amount       = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency     = models.CharField(max_length=3, default='BDT', null=True, blank=True)
    issued_at    = models.DateTimeField(auto_now_add=True)
    due_at       = models.DateTimeField()
    paid_at      = models.DateTimeField(null=True, blank=True)
    is_paid      = models.BooleanField(default=False)
    pdf_url      = models.URLField(null=True, blank=True)
    notes        = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-issued_at']

    def __str__(self):
        return f"Invoice #{self.invoice_no} | {self.amount} {self.currency}"


class RefundRecord(TimeStampedModel):
    """Refund হওয়া transaction-এর record।"""
    original_conversion = models.ForeignKey(Conversion, on_delete=models.CASCADE, related_name='refunds', null=True, blank=True)
    user                = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='refunds', null=True, blank=True)
    refund_amount       = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    reason              = models.TextField()
    approved_by         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_refunds')
    processed_at        = models.DateTimeField(null=True, blank=True)
    is_processed        = models.BooleanField(default=False)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Refund {self.refund_amount} | {self.user}"


class WalletAudit(TimeStampedModel):
    """Wallet balance-এর প্রতিটি change-এর immutable log।"""
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_audits', null=True, blank=True)
    transaction_type= models.CharField(max_length=50, null=True, blank=True)
    amount          = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    balance_before  = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    balance_after   = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    reference_id    = models.CharField(max_length=100, null=True, blank=True)
    reference_type  = models.CharField(max_length=50, null=True, blank=True)
    note            = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Audit | {self.user} | {self.transaction_type} | {self.amount}"


class CommissionTier(TimeStampedModel):
    """Referral commission tier — আরো বেশি referral = বেশি %।"""
    tenant          = _tenant_fk()
    name            = models.CharField(max_length=100, null=True, blank=True)
    min_referrals   = models.PositiveSmallIntegerField(default=0)
    max_referrals   = models.PositiveSmallIntegerField(null=True, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active       = models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['min_referrals']

    def __str__(self):
        return f"Tier: {self.name} | {self.commission_rate}%"


class ExpenseLog(TimeStampedModel):
    """Platform-এর operational expense tracking।"""
    category    = models.CharField(max_length=100, null=True, blank=True)
    amount      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency    = models.CharField(max_length=3, default='BDT', null=True, blank=True)
    description = models.TextField(blank=True)
    invoice_ref = models.CharField(max_length=100, null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='expense_logs')

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Expense | {self.category} | {self.amount} {self.currency}"


class WithdrawalRequest(TimeStampedModel):
    """User-এর withdrawal request।"""
    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending')
        APPROVED  = 'approved',  _('Approved')
        PROCESSING= 'processing',_('Processing')
        COMPLETED = 'completed', _('Completed')
        REJECTED  = 'rejected',  _('Rejected')
        CANCELLED = 'cancelled', _('Cancelled')

    tenant          = _tenant_fk()
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawal_requests', null=True, blank=True)
    payment_method  = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, related_name='withdrawals')
    payout_batch    = models.ForeignKey(PayoutBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='withdrawal_requests')
    amount          = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('1'))])
    fee             = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    net_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    currency        = models.CharField(max_length=3, default='BDT', null=True, blank=True)
    status          = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, null=True, blank=True)
    reference_no    = models.CharField(max_length=100, null=True, blank=True)
    note            = models.TextField(blank=True)
    processed_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_withdrawals')
    processed_at    = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']
        indexes   = [models.Index(fields=['user', 'status', 'created_at'])]

    def __str__(self):
        return f"Withdrawal {self.amount} {self.currency} | {self.user} | {self.status}"

    def save(self, *args, **kwargs):
        self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)


class WalletTransaction(TimeStampedModel):
    """Wallet-এর প্রতিটি credit/debit transaction।"""
    class TxType(models.TextChoices):
        CREDIT     = 'credit',     _('Credit')
        DEBIT      = 'debit',      _('Debit')
        HOLD       = 'hold',       _('Hold')
        RELEASE    = 'release',    _('Release')
        REVERSAL   = 'reversal',   _('Reversal')

    tenant      = _tenant_fk()
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_transactions', null=True, blank=True)
    tx_type     = models.CharField(max_length=10, choices=TxType.choices, null=True, blank=True)
    amount      = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    currency    = models.CharField(max_length=3, default='BDT', null=True, blank=True)
    description = models.TextField(blank=True)
    source      = models.CharField(max_length=50, blank=True, help_text="conversion | withdrawal | bonus | reversal", null=True)
    source_id   = models.CharField(max_length=100, null=True, blank=True)
    balance_snapshot = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']
        indexes   = [models.Index(fields=['user', 'tx_type', 'created_at'])]

    def __str__(self):
        return f"{self.tx_type.upper()} {self.amount} {self.currency} | {self.user}"


# ═══════════════════════════════════════════════════════════════════
# §5  USER & TARGETING   (১৫টি ক্লাস)
# ═══════════════════════════════════════════════════════════════════

class GeoData(TimeStampedModel):
    """IP → Country/City geo mapping।"""
    ip_address  = models.GenericIPAddressField(unique=True, db_index=True)
    country_code= models.CharField(max_length=2, blank=True, db_index=True, null=True)
    country_name= models.CharField(max_length=100, null=True, blank=True)
    region      = models.CharField(max_length=100, null=True, blank=True)
    city        = models.CharField(max_length=100, null=True, blank=True)
    latitude    = models.FloatField(null=True, blank=True)
    longitude   = models.FloatField(null=True, blank=True)
    isp         = models.CharField(max_length=200, null=True, blank=True)
    is_vpn      = models.BooleanField(default=False)
    is_proxy    = models.BooleanField(default=False)
    last_checked= models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.ip_address} → {self.country_code}, {self.city}"


class ISPInfo(TimeStampedModel):
    """Internet Service Provider information।"""
    asn         = models.CharField(max_length=20, unique=True, null=True, blank=True)
    name        = models.CharField(max_length=200, null=True, blank=True)
    country     = models.CharField(max_length=2, null=True, blank=True)
    is_mobile   = models.BooleanField(default=False)
    is_hosting  = models.BooleanField(default=False)
    risk_level  = models.CharField(max_length=10, default='low', null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.asn} | {self.name}"


class UserLanguage(TimeStampedModel):
    """User-এর preferred language setting।"""
    user            = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='language_pref', null=True, blank=True)
    primary_language= models.CharField(max_length=10, default='bn', null=True, blank=True)
    secondary_lang  = models.CharField(max_length=10, null=True, blank=True)
    detect_from_browser = models.BooleanField(default=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.user} | {self.primary_language}"


class LoyaltyLevel(TimeStampedModel):
    """Gamification-এর loyalty tier — Bronze, Silver, Gold, Platinum।"""
    tenant          = _tenant_fk()
    name            = models.CharField(max_length=50, unique=True, null=True, blank=True)
    level_order     = models.PositiveSmallIntegerField(unique=True)
    min_points      = models.PositiveBigIntegerField(default=0)
    max_points      = models.PositiveBigIntegerField(null=True, blank=True)
    badge_url       = models.URLField(null=True, blank=True)
    payout_bonus_pct= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    perks           = models.JSONField(default=list, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['level_order']

    def __str__(self):
        return f"Level {self.level_order}: {self.name}"


class UserSegment(TimeStampedModel):
    """Dynamic user segment — offer targeting-এ ব্যবহার হয়।"""
    tenant      = _tenant_fk()
    name        = models.CharField(max_length=150, null=True, blank=True)
    description = models.TextField(blank=True)
    criteria    = models.JSONField(default=dict, help_text='{"min_earnings": 100, "country": "BD"}')
    is_dynamic  = models.BooleanField(default=True, help_text="Auto-update based on criteria?")
    user_count  = models.PositiveIntegerField(default=0)
    last_computed=models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Segment: {self.name} ({self.user_count} users)"


class ActivityHeatmap(TimeStampedModel):
    """User activity pattern — কোন সময়ে সবচেয়ে বেশি active।"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='heatmaps', null=True, blank=True)
    day_of_week = models.PositiveSmallIntegerField(help_text="0=Monday, 6=Sunday")
    hour_of_day = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(23)])
    activity_score=models.FloatField(default=0.0)
    click_count = models.PositiveIntegerField(default=0)
    conversion_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('user', 'day_of_week', 'hour_of_day')

    def __str__(self):
        return f"{self.user} | Day{self.day_of_week} Hour{self.hour_of_day} | Score:{self.activity_score}"


class UserKYC(TimeStampedModel):
    """Know Your Customer verification।"""
    class Status(models.TextChoices):
        PENDING  = 'pending',  _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        RESUBMIT = 'resubmit', _('Needs Resubmit')

    user          = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_profile', null=True, blank=True)
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, null=True, blank=True)
    id_type       = models.CharField(max_length=30, help_text="nid | passport | driving_license", null=True, blank=True)
    id_number     = models.CharField(max_length=50, null=True, blank=True)
    id_front_url  = models.URLField(null=True, blank=True)
    id_back_url   = models.URLField(null=True, blank=True)
    selfie_url    = models.URLField(null=True, blank=True)
    reviewed_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='kyc_reviews')
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    reject_reason = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"KYC | {self.user} | {self.status}"


class UserLoginHistory(TimeStampedModel):
    """User login record।"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_login_history', null=True, blank=True)
    ip_address  = models.GenericIPAddressField()
    country     = models.CharField(max_length=2, null=True, blank=True)
    device      = models.CharField(max_length=100, null=True, blank=True)
    is_success  = models.BooleanField(default=True)
    fail_reason = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.user} | {self.ip_address} | {'✓' if self.is_success else '✗'}"


class Achievement(TimeStampedModel):
    """Gamification achievement/badge।"""
    tenant       = _tenant_fk()
    name         = models.CharField(max_length=150, null=True, blank=True)
    description  = models.TextField(blank=True)
    badge_url    = models.URLField(null=True, blank=True)
    requirement  = models.JSONField(default=dict, help_text='{"offers_completed": 10}')
    points_award = models.PositiveIntegerField(default=0)
    is_active    = models.BooleanField(default=True)
    is_hidden    = models.BooleanField(default=False, help_text="Secret achievement?")
    users_earned = models.ManyToManyField(settings.AUTH_USER_MODEL, through='UserAchievement', blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"🏆 {self.name}"


class UserAchievement(TimeStampedModel):
    """User-Achievement many-to-many through model।"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, null=True, blank=True)
    earned_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('user', 'achievement')

    def __str__(self):
        return f"{self.user} earned {self.achievement}"


class UserReferral(TimeStampedModel):
    """Referral relationship।"""
    referrer     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals_made', null=True, blank=True)
    referred     = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_referral_referred_by', null=True, blank=True)
    referral_code= models.CharField(max_length=30, db_index=True, null=True, blank=True)
    is_converted = models.BooleanField(default=False)
    converted_at = models.DateTimeField(null=True, blank=True)
    total_earnings_generated = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Referral: {self.referrer} → {self.referred}"


class ChurnRecord(TimeStampedModel):
    """Inactive user churn detection।"""
    user              = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='churn_record', null=True, blank=True)
    churn_probability = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    last_active       = models.DateTimeField(null=True, blank=True)
    days_inactive     = models.PositiveSmallIntegerField(default=0)
    is_churned        = models.BooleanField(default=False)
    reactivation_sent = models.BooleanField(default=False)
    reactivated_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-churn_probability']

    def __str__(self):
        return f"Churn {self.churn_probability:.0%} | {self.user}"


class UserInterest(TimeStampedModel):
    """User-এর interest category।"""
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interests', null=True, blank=True)
    category   = models.ForeignKey(OfferCategory, on_delete=models.CASCADE, related_name='interested_users', null=True, blank=True)
    score      = models.FloatField(default=0.5, help_text="০–১ interest score")
    is_explicit= models.BooleanField(default=False, help_text="User নিজে select করেছে?")

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('user', 'category')

    def __str__(self):
        return f"{self.user} → {self.category} ({self.score:.2f})"


class UserFeedback(TimeStampedModel):
    """User-এর platform feedback।"""
    class FeedbackType(models.TextChoices):
        BUG       = 'bug',       _('Bug Report')
        FEATURE   = 'feature',   _('Feature Request')
        GENERAL   = 'general',   _('General')
        PAYMENT   = 'payment',   _('Payment Issue')
        COMPLAINT = 'complaint', _('Complaint')

    class StatusChoices(models.TextChoices):
        OPEN       = 'open',       _('Open')
        IN_PROGRESS= 'in_progress',_('In Progress')
        RESOLVED   = 'resolved',   _('Resolved')
        CLOSED     = 'closed',     _('Closed')

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedbacks', null=True, blank=True)
    feedback_type = models.CharField(max_length=10, choices=FeedbackType.choices, default=FeedbackType.GENERAL, null=True, blank=True)
    subject       = models.CharField(max_length=255, null=True, blank=True)
    message       = models.TextField()
    rating        = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    status        = models.CharField(max_length=15, choices=StatusChoices.choices, default=StatusChoices.OPEN, null=True, blank=True)
    is_resolved   = models.BooleanField(default=False)
    response      = models.TextField(blank=True)
    admin_note    = models.TextField(blank=True, help_text='Internal admin note')
    resolved_at   = models.DateTimeField(null=True, blank=True)
    offer         = models.ForeignKey('Offer', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks')

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']
        indexes   = [models.Index(fields=['status', 'feedback_type'])]

    def __str__(self):
        return f"Feedback | {self.feedback_type} | {self.user}"


class UserProfile(TimeStampedModel):
    """Extended user profile — offer platform specific।"""
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_profile', null=True, blank=True)
    loyalty_level    = models.ForeignKey(LoyaltyLevel, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    total_points     = models.PositiveBigIntegerField(default=0)
    total_offers     = models.PositiveIntegerField(default=0)
    daily_offer_count= models.PositiveSmallIntegerField(default=0)
    daily_reset_at   = models.DateTimeField(null=True, blank=True)
    preferred_currency= models.CharField(max_length=3, default='BDT', null=True, blank=True)
    notification_prefs= models.JSONField(default=dict, blank=True)
    is_verified      = models.BooleanField(default=False)
    ban_reason       = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Profile | {self.user} | {self.loyalty_level}"


# ═══════════════════════════════════════════════════════════════════
# §6  ANALYTICS & SYSTEM   (২০টি ক্লাস)
# ═══════════════════════════════════════════════════════════════════

class DailyStat(TimeStampedModel):
    """
    Daily aggregated statistics।
    Dashboard-এর মূল data source।
    """
    tenant           = _tenant_fk()
    date             = models.DateField(db_index=True)
    total_clicks     = models.PositiveBigIntegerField(default=0)
    unique_clicks    = models.PositiveBigIntegerField(default=0)
    total_conversions= models.PositiveIntegerField(default=0)
    approved_conversions=models.PositiveIntegerField(default=0)
    rejected_conversions=models.PositiveSmallIntegerField(default=0)
    total_revenue    = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    user_payouts     = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    platform_profit  = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    new_users        = models.PositiveIntegerField(default=0)
    active_users     = models.PositiveIntegerField(default=0)
    fraud_attempts   = models.PositiveSmallIntegerField(default=0)
    cvr              = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'), help_text="Conversion rate %")

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('tenant', 'date')
        ordering    = ['-date']

    def __str__(self):
        return f"DailyStat {self.date} | Revenue: {self.total_revenue}"


class NetworkStat(TimeStampedModel):
    """Per-network daily statistics।"""
    network           = models.ForeignKey(OfferNetwork, on_delete=models.CASCADE, related_name='stats', null=True, blank=True)
    date              = models.DateField()
    clicks            = models.PositiveBigIntegerField(default=0)
    conversions       = models.PositiveIntegerField(default=0)
    revenue           = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    avg_payout        = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0'))
    cvr               = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    epc               = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0'), help_text="Earnings per click")

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('network', 'date')
        ordering    = ['-date']

    def __str__(self):
        return f"{self.network.name} | {self.date} | {self.revenue}"


class ErrorLog(TimeStampedModel):
    """Application error logging।"""
    class Level(models.TextChoices):
        DEBUG   = 'debug',   'DEBUG'
        INFO    = 'info',    'INFO'
        WARNING = 'warning', 'WARNING'
        ERROR   = 'error',   'ERROR'
        CRITICAL= 'critical','CRITICAL'

    level       = models.CharField(max_length=10, choices=Level.choices, default=Level.ERROR, null=True, blank=True)
    logger_name = models.CharField(max_length=100, null=True, blank=True)
    message     = models.TextField()
    traceback   = models.TextField(blank=True)
    request_path= models.CharField(max_length=255, null=True, blank=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='error_logs')
    ip_address  = models.GenericIPAddressField(blank=True, null=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']
        indexes   = [models.Index(fields=['level', 'is_resolved'])]

    def __str__(self):
        return f"[{self.level.upper()}] {self.message[:80]}"


class Notification(TimeStampedModel):
    """User-কে পাঠানো in-app notification।"""
    class NotifType(models.TextChoices):
        INFO    = 'info',    _('Info')
        SUCCESS = 'success', _('Success')
        WARNING = 'warning', _('Warning')
        PAYMENT = 'payment', _('Payment')
        OFFER   = 'offer',   _('New Offer')
        SYSTEM  = 'system',  _('System')

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_notifications', null=True, blank=True)
    notif_type  = models.CharField(max_length=10, choices=NotifType.choices, default=NotifType.INFO, null=True, blank=True)
    title       = models.CharField(max_length=255, null=True, blank=True)
    body        = models.TextField()
    action_url  = models.URLField(null=True, blank=True)
    is_read     = models.BooleanField(default=False)
    read_at     = models.DateTimeField(null=True, blank=True)
    metadata    = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"[{self.notif_type}] {self.title} → {self.user}"


class EmailLog(TimeStampedModel):
    """পাঠানো email-এর log।"""
    class Status(models.TextChoices):
        QUEUED   = 'queued',   _('Queued')
        SENT     = 'sent',     _('Sent')
        DELIVERED= 'delivered',_('Delivered')
        OPENED   = 'opened',   _('Opened')
        FAILED   = 'failed',   _('Failed')
        BOUNCED  = 'bounced',  _('Bounced')

    recipient   = models.EmailField()
    subject     = models.CharField(max_length=255, null=True, blank=True)
    template    = models.CharField(max_length=100, null=True, blank=True)
    status      = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED, null=True, blank=True)
    sent_at     = models.DateTimeField(null=True, blank=True)
    opened_at   = models.DateTimeField(null=True, blank=True)
    provider_id = models.CharField(max_length=255, null=True, blank=True)
    error       = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Email to {self.recipient} | {self.status}"


class PushSubscription(TimeStampedModel):
    """Browser push notification subscription।"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_subscriptions', null=True, blank=True)
    endpoint    = models.TextField(unique=True)
    p256dh_key  = models.TextField()
    auth_key    = models.TextField()
    user_agent  = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    last_used   = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"PushSub | {self.user} | {'active' if self.is_active else 'inactive'}"


class SystemSetting(TimeStampedModel):
    """
    Key-value system configuration।
    Runtime-এ পরিবর্তনযোগ্য।
    """
    tenant      = _tenant_fk()
    key         = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    value       = models.TextField()
    value_type  = models.CharField(max_length=10, default='string', help_text="string | int | bool | json", null=True, blank=True)
    description = models.TextField(blank=True)
    is_public   = models.BooleanField(default=False, help_text="Frontend-এ expose করা যাবে?")

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('tenant', 'key')

    def __str__(self):
        return f"{self.key} = {self.value[:50]}"


class MaintenanceMode(TimeStampedModel):
    """Site maintenance mode control।"""
    tenant      = _tenant_fk()
    is_active   = models.BooleanField(default=False)
    message     = models.TextField(default='সাইটটি বর্তমানে রক্ষণাবেক্ষণের জন্য বন্ধ আছে।')
    started_at  = models.DateTimeField(null=True, blank=True)
    ends_at     = models.DateTimeField(null=True, blank=True)
    whitelist_ips= models.JSONField(default=list, help_text="এই IP গুলো access পাবে")
    activated_by= models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_modes')

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Maintenance {'ON' if self.is_active else 'OFF'} | {self.tenant}"


class BackupLog(TimeStampedModel):
    """Database/file backup log।"""
    class Status(models.TextChoices):
        RUNNING   = 'running',   _('Running')
        COMPLETED = 'completed', _('Completed')
        FAILED    = 'failed',    _('Failed')

    backup_type = models.CharField(max_length=20, help_text="db | files | full", null=True, blank=True)
    status      = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING, null=True, blank=True)
    file_path   = models.CharField(max_length=500, null=True, blank=True)
    file_size   = models.PositiveBigIntegerField(default=0, help_text="Bytes")
    duration_secs= models.PositiveIntegerField(default=0)
    error       = models.TextField(blank=True)
    started_by  = models.CharField(max_length=50, default='celery', null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Backup {self.backup_type} | {self.status} | {self.created_at.date()}"


class APIKeyManager(TimeStampedModel):
    """External API key management।"""
    tenant      = _tenant_fk()
    service     = models.CharField(max_length=100, null=True, blank=True)
    key_name    = models.CharField(max_length=100, null=True, blank=True)
    key_value   = models.TextField(help_text="Encrypted")
    is_active   = models.BooleanField(default=True)
    expires_at  = models.DateTimeField(null=True, blank=True)
    last_rotated= models.DateTimeField(null=True, blank=True)
    notes       = models.TextField(blank=True)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('tenant', 'service', 'key_name')

    def __str__(self):
        return f"APIKey | {self.service} | {self.key_name}"


class WebhookConfig(TimeStampedModel):
    """Outbound webhook configuration।"""
    tenant      = _tenant_fk()
    name        = models.CharField(max_length=150, null=True, blank=True)
    url         = models.URLField(null=True, blank=True)
    events      = models.JSONField(default=list, help_text='["conversion.approved", "withdrawal.completed"]')
    secret_key  = models.CharField(max_length=100, null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    retry_count = models.PositiveSmallIntegerField(default=3)
    last_fired  = models.DateTimeField(null=True, blank=True)
    last_status = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Webhook: {self.name} → {self.url[:60]}"


class CacheObject(TimeStampedModel):
    """Persistent cache store — Redis-এর বাইরে DB cache।"""
    key         = models.CharField(max_length=255, unique=True, db_index=True, null=True, blank=True)
    value       = models.JSONField(default=dict)
    expires_at  = models.DateTimeField(null=True, blank=True)
    hit_count   = models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Cache: {self.key}"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class AuditLog(TimeStampedModel):
    """
    Full activity audit trail।
    কে কখন কী করেছে সব রেকর্ড।
    """
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='offer_audit_logs')
    action      = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    model_name  = models.CharField(max_length=100, null=True, blank=True)
    object_id   = models.CharField(max_length=100, null=True, blank=True)
    changes     = models.JSONField(default=dict, blank=True)
    ip_address  = models.GenericIPAddressField(blank=True, null=True)
    user_agent  = models.TextField(blank=True)
    metadata    = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['action', 'model_name']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"Audit | {self.user} | {self.action} | {self.model_name}:{self.object_id}"


class FeedbackTicket(TimeStampedModel):
    """Support ticket system।"""
    class Priority(models.TextChoices):
        LOW    = 'low',    _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH   = 'high',   _('High')
        URGENT = 'urgent', _('Urgent')

    class Status(models.TextChoices):
        OPEN       = 'open',       _('Open')
        IN_PROGRESS= 'in_progress',_('In Progress')
        RESOLVED   = 'resolved',   _('Resolved')
        CLOSED     = 'closed',     _('Closed')

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='support_tickets')
    ticket_no    = models.CharField(max_length=20, unique=True, null=True, blank=True)
    subject      = models.CharField(max_length=255, null=True, blank=True)
    message      = models.TextField()
    priority     = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM, null=True, blank=True)
    status       = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN, null=True, blank=True)
    assigned_to  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    resolved_at  = models.DateTimeField(null=True, blank=True)
    resolution   = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Ticket #{self.ticket_no} | {self.priority} | {self.status}"


class AutoResponder(TimeStampedModel):
    """Support ticket auto-response template।"""
    trigger_keyword = models.CharField(max_length=100, null=True, blank=True)
    response_text   = models.TextField()
    is_active       = models.BooleanField(default=True)
    match_count     = models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"AutoRespond: '{self.trigger_keyword}'"


class PerformanceMetric(TimeStampedModel):
    """API/page performance metrics।"""
    endpoint    = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    method      = models.CharField(max_length=6, default='GET', null=True, blank=True)
    avg_ms      = models.FloatField(default=0.0, help_text="Average response time ms")
    p95_ms      = models.FloatField(default=0.0, help_text="95th percentile ms")
    p99_ms      = models.FloatField(default=0.0, help_text="99th percentile ms")
    error_rate  = models.FloatField(default=0.0, help_text="Error %")
    request_count=models.PositiveBigIntegerField(default=0)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-recorded_at']
        indexes   = [models.Index(fields=['endpoint', 'recorded_at'])]

    def __str__(self):
        return f"{self.method} {self.endpoint} | avg:{self.avg_ms:.0f}ms"


class ABTestGroup(TimeStampedModel):
    """A/B testing group।"""
    class Status(models.TextChoices):
        DRAFT    = 'draft',    _('Draft')
        RUNNING  = 'running',  _('Running')
        COMPLETED= 'completed',_('Completed')

    name          = models.CharField(max_length=150, null=True, blank=True)
    hypothesis    = models.TextField(blank=True)
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, null=True, blank=True)
    variant_a     = models.JSONField(default=dict, help_text="Control group config")
    variant_b     = models.JSONField(default=dict, help_text="Test group config")
    traffic_split = models.FloatField(default=0.5, help_text="A=50%, B=50%")
    winner        = models.CharField(max_length=1, blank=True, help_text="A or B", null=True)
    started_at    = models.DateTimeField(null=True, blank=True)
    ended_at      = models.DateTimeField(null=True, blank=True)
    metric        = models.CharField(max_length=50, default='conversion_rate', null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"A/B Test: {self.name} | {self.status}"


class TaskQueue(TimeStampedModel):
    """Celery task-এর tracking।"""
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        RUNNING = 'running', _('Running')
        SUCCESS = 'success', _('Success')
        FAILURE = 'failure', _('Failure')
        RETRY   = 'retry',   _('Retry')

    task_id     = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    task_name   = models.CharField(max_length=255, null=True, blank=True)
    status      = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, null=True, blank=True)
    args        = models.JSONField(default=list, blank=True)
    kwargs      = models.JSONField(default=dict, blank=True)
    result      = models.JSONField(default=dict, blank=True)
    error       = models.TextField(blank=True)
    started_at  = models.DateTimeField(null=True, blank=True)
    completed_at= models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = 'offer_inventory'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Task {self.task_name} | {self.status}"


class DocumentationSnippet(TimeStampedModel):
    """In-app documentation / help snippets।"""
    slug        = models.SlugField(max_length=150, unique=True, null=True, blank=True)
    title       = models.CharField(max_length=255, null=True, blank=True)
    content     = models.TextField()
    category    = models.CharField(max_length=100, null=True, blank=True)
    is_published= models.BooleanField(default=False)
    language    = models.CharField(max_length=10, default='bn', null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"Doc: {self.title}"


class MasterSwitch(TimeStampedModel):
    """
    Global feature flags।
    একটি switch দিয়ে পুরো feature on/off।
    """
    tenant      = _tenant_fk()
    feature     = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    is_enabled  = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    toggled_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='master_switches')
    toggled_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('tenant', 'feature')

    def __str__(self):
        return f"{'🟢' if self.is_enabled else '🔴'} {self.feature}"


# ══════════════════════════════════════════════════════════════════════════════
# RTB ENGINE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class BidLog(TimeStampedModel):
    """RTB bid request/response log."""
    request_id     = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    publisher_id   = models.CharField(max_length=50, blank=True, db_index=True, null=True)
    app_id         = models.CharField(max_length=50, null=True, blank=True)
    offer          = models.ForeignKey('Offer', on_delete=models.SET_NULL, null=True, blank=True, related_name='bid_logs')
    offer_external_id = models.CharField(max_length=50, null=True, blank=True)  # external offer ID string
    ecpm           = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))
    clearing_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    is_won         = models.BooleanField(default=False)
    no_bid         = models.BooleanField(default=False)
    loss_reason    = models.CharField(max_length=100, null=True, blank=True)
    response_ms    = models.FloatField(default=0.0)
    country        = models.CharField(max_length=2, null=True, blank=True)
    device_type    = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        app_label = 'offer_inventory'
        indexes   = [
            models.Index(fields=['publisher_id', 'created_at']),
            models.Index(fields=['is_won', 'created_at']),
        ]

    def __str__(self):
        return f"Bid {self.request_id[:12]} | {'WON' if self.is_won else 'LOSS'} | eCPM={self.ecpm}"


class DSPConfig(TimeStampedModel):
    """External Demand-Side Platform configuration."""
    tenant         = _tenant_fk()
    name           = models.CharField(max_length=100, null=True, blank=True)
    endpoint_url   = models.URLField(null=True, blank=True)
    api_key        = models.CharField(max_length=200, null=True, blank=True)
    timeout_ms     = models.PositiveSmallIntegerField(default=80)
    is_active      = models.BooleanField(default=True)
    revenue_share  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('30'))
    notes          = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"DSP: {self.name}"


class PublisherConfig(TimeStampedModel):
    """Publisher-specific RTB configuration (floor prices, etc.)."""
    publisher_id   = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)
    floor_prices   = models.JSONField(default=dict, blank=True, help_text='{"BD": "0.5", "default": "0.3"}')
    is_active      = models.BooleanField(default=True)
    notes          = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"PublisherConfig: {self.publisher_id}"


# ══════════════════════════════════════════════════════════════════════════════
# PUBLISHER SDK MODELS
# ══════════════════════════════════════════════════════════════════════════════

class Publisher(TimeStampedModel):
    """Publisher (app developer/website owner) account."""
    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending Review')
        ACTIVE    = 'active',    _('Active')
        SUSPENDED = 'suspended', _('Suspended')
        REJECTED  = 'rejected',  _('Rejected')

    class AppType(models.TextChoices):
        MOBILE    = 'mobile',    _('Mobile App')
        WEB       = 'web',       _('Website')
        GAME      = 'game',      _('Game')
        STREAMING = 'streaming', _('Streaming')

    tenant         = _tenant_fk()
    company_name   = models.CharField(max_length=200, null=True, blank=True)
    contact_email  = models.EmailField(unique=True)
    website        = models.URLField(null=True, blank=True)
    app_type       = models.CharField(max_length=15, choices=AppType.choices, default=AppType.MOBILE, null=True, blank=True)
    api_key        = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    status         = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, null=True, blank=True)
    revenue_share  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('30'))
    payout_method  = models.CharField(max_length=20, blank=True, default='wire', null=True)
    payout_email   = models.EmailField(blank=True)
    approved_at    = models.DateTimeField(null=True, blank=True)
    approved_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_publishers')
    total_earned   = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    notes          = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        indexes   = [models.Index(fields=['status', 'api_key'])]

    def __str__(self):
        return f"Publisher: {self.company_name} ({self.status})"


class PublisherApp(TimeStampedModel):
    """Individual app registered by a publisher."""
    class Platform(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS     = 'ios',     'iOS'
        WEB     = 'web',     'Web'
        UNITY   = 'unity',   'Unity'
        OTHER   = 'other',   'Other'

    publisher      = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name='apps', null=True, blank=True)
    name           = models.CharField(max_length=200, null=True, blank=True)
    platform       = models.CharField(max_length=10, choices=Platform.choices, null=True, blank=True)
    bundle_id      = models.CharField(max_length=200, blank=True, help_text='com.example.app', null=True)
    category       = models.CharField(max_length=50, null=True, blank=True)
    app_key        = models.CharField(max_length=60, unique=True, db_index=True, null=True, blank=True)
    status         = models.CharField(max_length=15, default='pending', null=True, blank=True)
    daily_impressions = models.PositiveBigIntegerField(default=0)
    total_revenue  = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))

    class Meta:
        app_label = 'offer_inventory'
        unique_together = ('publisher', 'bundle_id', 'platform')

    def __str__(self):
        return f"{self.name} ({self.platform})"


class AppPlacement(TimeStampedModel):
    """Ad placement within a publisher app."""
    app            = models.ForeignKey(PublisherApp, on_delete=models.CASCADE, related_name='placements', null=True, blank=True)
    name           = models.CharField(max_length=100, null=True, blank=True)
    placement_type = models.CharField(max_length=20, default='offerwall', null=True, blank=True)
    position       = models.CharField(max_length=50, null=True, blank=True)
    placement_id   = models.CharField(max_length=30, unique=True, db_index=True, null=True, blank=True)
    is_active      = models.BooleanField(default=True)
    ecpm_floor     = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0'))

    class Meta:
        app_label = 'offer_inventory'

    def __str__(self):
        return f"{self.app.name} / {self.name}"


class PublisherPayout(TimeStampedModel):
    """Publisher payout transaction."""
    publisher      = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name='payouts', null=True, blank=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    currency       = models.CharField(max_length=5, default='USD', null=True, blank=True)
    method         = models.CharField(max_length=20, default='wire', null=True, blank=True)
    status         = models.CharField(max_length=15, default='pending', null=True, blank=True)
    reference_no   = models.CharField(max_length=50, null=True, blank=True)
    period_start   = models.DateTimeField(null=True, blank=True)
    period_end     = models.DateTimeField(null=True, blank=True)
    paid_at        = models.DateTimeField(null=True, blank=True)
    notes          = models.TextField(blank=True)

    class Meta:
        app_label = 'offer_inventory'
        indexes   = [models.Index(fields=['publisher', 'status'])]

    def __str__(self):
        return f"PublisherPayout: {self.publisher.company_name} {self.amount} {self.currency}"


class PublisherRevenue(TimeStampedModel):
    """Daily revenue attribution for publishers."""
    publisher      = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name='revenue_records', null=True, blank=True)
    app            = models.ForeignKey(PublisherApp, on_delete=models.SET_NULL, null=True, blank=True)
    date           = models.DateField(db_index=True)
    impressions    = models.PositiveIntegerField(default=0)
    clicks         = models.PositiveIntegerField(default=0)
    conversions    = models.PositiveIntegerField(default=0)
    gross_revenue  = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    publisher_share= models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    ecpm           = models.DecimalField(max_digits=8,  decimal_places=4, default=Decimal('0'))

    class Meta:
        app_label   = 'offer_inventory'
        unique_together = ('publisher', 'app', 'date')

    def __str__(self):
        return f"Revenue: {self.publisher.company_name} | {self.date} | ${self.gross_revenue}"
