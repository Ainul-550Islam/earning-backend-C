"""
api/publisher_tools/models.py

Publisher Tools — সম্পূর্ণ ডাটাবেস মডেল লেয়ার।

Design Decisions:
  • সব মডেল `core.models.TimeStampedModel` থেকে inherit করে (UUID PK + timestamps)।
  • Multi-tenant support: প্রতিটি মডেলে Tenant FK আছে।
  • related_name pattern: '%(app_label)s_%(class)s_<field>' — Django clash এড়াতে।
  • Indexing: সব frequently-queried field-এ db_index বা Index আছে।
  • Properties: computed fields model-এই রাখা হয়েছে, view/serializer-এ নয়।

Module গঠন:
  ১. Publisher & Inventory       (Publisher, Site, App, InventoryVerification)
  ২. Ad Unit & Placement         (AdUnit, AdPlacement, AdUnitTargeting)
  ৩. Mediation & Waterfall       (MediationGroup, WaterfallItem, HeaderBiddingConfig)
  ৪. Earnings & Payouts          (PublisherEarning, PayoutThreshold, PublisherInvoice)
  ৫. Traffic Quality             (TrafficSafetyLog, SiteQualityMetric)
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    URLValidator,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


# ─── Helper defaults ──────────────────────────────────────────────────────────

def _default_list():
    return []

def _default_dict():
    return {}

def _default_countries():
    """সব দেশে চলবে by default"""
    return ["ALL"]


# ==============================================================================
# ১. PUBLISHER & INVENTORY MANAGEMENT
# পাবলিশারের প্রোফাইল, সাইট, অ্যাপ এবং ভেরিফিকেশন
# ==============================================================================

class Publisher(TimeStampedModel):
    """
    পাবলিশারের মেইন প্রোফাইল মডেল।
    একজন Publisher-এর অধীনে একাধিক Site ও App থাকতে পারে।
    """

    # ── Tenant ───────────────────────────────────────────────────────────────
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publisher_tools_publisher_tenant',
        db_index=True,
        verbose_name=_("Tenant"),
    )

    # ── Business Type ─────────────────────────────────────────────────────────
    BUSINESS_TYPES = [
        ('individual',   _('Individual / Freelancer')),
        ('company',      _('Company / LLC')),
        ('agency',       _('Agency')),
        ('ngo',          _('NGO / Non-profit')),
        ('startup',      _('Startup')),
    ]

    # ── Status ────────────────────────────────────────────────────────────────
    STATUS_CHOICES = [
        ('pending',     _('Pending Review')),
        ('active',      _('Active')),
        ('suspended',   _('Suspended')),
        ('banned',      _('Banned')),
        ('under_review',_('Under Review')),
    ]

    # ── Tier ─────────────────────────────────────────────────────────────────
    TIER_CHOICES = [
        ('standard',  _('Standard')),
        ('premium',   _('Premium')),
        ('enterprise',_('Enterprise')),
    ]

    # ── Core Identity ─────────────────────────────────────────────────────────
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='publisher_profile',
        verbose_name=_("User Account"),
    )
    publisher_id = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Publisher ID"),
        help_text=_("Auto-generated: PUB000001"),
    )
    display_name = models.CharField(
        null=True, blank=True,
        max_length=200,
        verbose_name=_("Display Name"),
    )
    business_type = models.CharField(
        max_length=20,
        choices=BUSINESS_TYPES,
        default='individual',
        verbose_name=_("Business Type"),
    )

    # ── Contact ───────────────────────────────────────────────────────────────
    contact_email = models.EmailField(
        null=True, blank=True,
        verbose_name=_("Contact Email"),
    )
    contact_phone = models.CharField(
        max_length=20,
        verbose_name=_("Contact Phone"),
    )
    website = models.URLField(
        verbose_name=_("Company Website"),
    )
    country = models.CharField(
        max_length=100,
        default='Bangladesh',
        verbose_name=_("Country"),
        db_index=True,
    )
    city = models.CharField(
        null=True, blank=True,
        max_length=100,
        verbose_name=_("City"),
    )
    address = models.TextField(
        verbose_name=_("Business Address"),
    )

    # ── Status & Tier ─────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status"),
        db_index=True,
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='standard',
        verbose_name=_("Publisher Tier"),
    )

    # ── Verification ─────────────────────────────────────────────────────────
    is_kyc_verified = models.BooleanField(
        default=False,
        verbose_name=_("KYC Verified"),
    )
    is_email_verified = models.BooleanField(
        default=False,
        verbose_name=_("Email Verified"),
    )
    kyc_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("KYC Verified At"),
    )

    # ── Financial ─────────────────────────────────────────────────────────────
    total_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Revenue (USD)"),
    )
    total_paid_out = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Paid Out (USD)"),
    )
    pending_balance = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Pending Balance (USD)"),
    )

    # ── Commission ────────────────────────────────────────────────────────────
    revenue_share_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('70.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Revenue Share %"),
        help_text=_("Platform-এর পাশে পাবলিশার কত % পাবে।"),
    )

    # ── API Access ────────────────────────────────────────────────────────────
    api_key = models.CharField(
        null=True, blank=True,
        max_length=64,
        unique=True,
        verbose_name=_("API Key"),
    )
    api_secret = models.CharField(
        max_length=128,
        verbose_name=_("API Secret"),
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    internal_notes = models.TextField(
        null=True, blank=True,
        verbose_name=_("Internal Notes (Admin Only)"),
    )
    metadata = models.JSONField(
        default=_default_dict,
        verbose_name=_("Metadata"),
    )

    class Meta:
        db_table = 'publisher_tools_publishers'
        verbose_name = _('Publisher')
        verbose_name_plural = _('Publishers')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher_id']),
            models.Index(fields=['status']),
            models.Index(fields=['country']),
            models.Index(fields=['tier']),
            models.Index(fields=['is_kyc_verified']),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.publisher_id})"

    def save(self, *args, **kwargs):
        # Auto-generate Publisher ID
        if not self.publisher_id:
            count = Publisher.objects.count() + 1
            self.publisher_id = f"PUB{count:06d}"
        # Auto-generate API Key
        if not self.api_key:
            self.api_key = uuid.uuid4().hex + uuid.uuid4().hex[:32]
        super().save(*args, **kwargs)

    @property
    def available_balance(self):
        """উইথড্র করার জন্য available balance"""
        return self.total_revenue - self.total_paid_out

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def active_sites_count(self):
        return self.sites.filter(status='active').count()

    @property
    def active_apps_count(self):
        return self.apps.filter(status='active').count()


class Site(TimeStampedModel):
    """
    পাবলিশারের ভেরিফাইড ওয়েবসাইট।
    প্রতিটি Site-এ একাধিক AdUnit থাকতে পারে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_site_tenant',
        db_index=True,)

    # ── Status ────────────────────────────────────────────────────────────────
    STATUS_CHOICES = [
        ('pending',  _('Pending Verification')),
        ('active',   _('Active')),
        ('rejected', _('Rejected')),
        ('suspended',_('Suspended')),
        ('inactive', _('Inactive')),
    ]

    # ── Category ──────────────────────────────────────────────────────────────
    CATEGORY_CHOICES = [
        ('news',         _('News & Media')),
        ('blog',         _('Blog / Personal')),
        ('entertainment',_('Entertainment')),
        ('technology',   _('Technology')),
        ('finance',      _('Finance')),
        ('health',       _('Health & Wellness')),
        ('sports',       _('Sports')),
        ('education',    _('Education')),
        ('ecommerce',    _('E-Commerce')),
        ('gaming',       _('Gaming')),
        ('travel',       _('Travel')),
        ('food',         _('Food & Lifestyle')),
        ('automotive',   _('Automotive')),
        ('real_estate',  _('Real Estate')),
        ('other',        _('Other')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='sites',
        verbose_name=_("Publisher"),
    )
    site_id = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Site ID"),
        help_text=_("Auto-generated: SITE000001"),
    )
    name = models.CharField(
        null=True, blank=True,
        max_length=200,
        verbose_name=_("Site Name"),
    )
    domain = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Domain"),
        help_text=_("e.g., example.com (without https://)"),
        db_index=True,
    )
    url = models.URLField(
        null=True, blank=True,
        verbose_name=_("Site URL"),
    )

    # ── Classification ────────────────────────────────────────────────────────
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name=_("Category"),
        db_index=True,
    )
    subcategory = models.CharField(
        null=True, blank=True,
        max_length=100,
        verbose_name=_("Sub-Category"),
    )
    language = models.CharField(
        max_length=10,
        default='en',
        verbose_name=_("Primary Language"),
    )
    target_countries = models.JSONField(
        default=_default_countries,
        blank=True,
        verbose_name=_("Target Countries"),
        help_text=_("['BD', 'US', 'ALL']"),
    )

    # ── Status & Quality ──────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status"),
        db_index=True,
    )
    quality_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Quality Score"),
        help_text=_("0-100, automated content & traffic quality score"),
        db_index=True,
    )
    content_rating = models.CharField(
        max_length=20,
        default='G',
        choices=[('G','G - All Ages'),('PG','PG'),('PG13','PG-13'),('R','R - Adults')],
        verbose_name=_("Content Rating"),
    )

    # ── Traffic Stats ─────────────────────────────────────────────────────────
    monthly_pageviews = models.BigIntegerField(
        default=0,
        verbose_name=_("Monthly Pageviews"),
    )
    monthly_unique_visitors = models.BigIntegerField(
        default=0,
        verbose_name=_("Monthly Unique Visitors"),
    )
    avg_session_duration = models.IntegerField(
        default=0,
        verbose_name=_("Avg Session Duration (seconds)"),
    )
    bounce_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Bounce Rate (%)"),
    )

    # ── Technical ─────────────────────────────────────────────────────────────
    ads_txt_verified = models.BooleanField(
        default=False,
        verbose_name=_("ads.txt Verified"),
    )
    ads_txt_content = models.TextField(
        null=True, blank=True,
        verbose_name=_("ads.txt Content"),
    )
    sellers_json_verified = models.BooleanField(
        default=False,
        verbose_name=_("sellers.json Verified"),
    )

    # ── Revenue ───────────────────────────────────────────────────────────────
    total_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Revenue (USD)"),
    )
    lifetime_impressions = models.BigIntegerField(
        default=0,
        verbose_name=_("Lifetime Impressions"),
    )
    lifetime_clicks = models.BigIntegerField(
        default=0,
        verbose_name=_("Lifetime Clicks"),
    )

    # ── Rejection Info ────────────────────────────────────────────────────────
    rejection_reason = models.TextField(
        null=True, blank=True,
        verbose_name=_("Rejection Reason"),
    )
    approved_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Approved At"),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_site_approved_by',
        verbose_name=_("Approved By"),
    )

    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_sites'
        verbose_name = _('Site')
        verbose_name_plural = _('Sites')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site_id']),
            models.Index(fields=['domain']),
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['category']),
            models.Index(fields=['quality_score']),
        ]

    def __str__(self):
        return f"{self.name} ({self.domain})"

    def save(self, *args, **kwargs):
        if not self.site_id:
            count = Site.objects.count() + 1
            self.site_id = f"SITE{count:06d}"
        super().save(*args, **kwargs)

    @property
    def ctr(self):
        """Click-Through Rate"""
        if self.lifetime_impressions > 0:
            return round((self.lifetime_clicks / self.lifetime_impressions) * 100, 4)
        return 0.0

    @property
    def is_active(self):
        return self.status == 'active'


class App(TimeStampedModel):
    """
    পাবলিশারের মোবাইল অ্যাপ।
    Android, iOS, বা উভয় প্ল্যাটফর্মে থাকতে পারে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_app_tenant',
        db_index=True,)

    PLATFORM_CHOICES = [
        ('android', _('Android')),
        ('ios',     _('iOS')),
        ('both',    _('Android + iOS')),
        ('web_app', _('Web App (PWA)')),
        ('other',   _('Other')),
    ]

    STATUS_CHOICES = [
        ('pending',  _('Pending Review')),
        ('active',   _('Active')),
        ('rejected', _('Rejected')),
        ('suspended',_('Suspended')),
        ('removed',  _('Removed from Store')),
    ]

    CATEGORY_CHOICES = [
        ('games',          _('Games')),
        ('tools',          _('Tools & Utilities')),
        ('entertainment',  _('Entertainment')),
        ('social',         _('Social')),
        ('finance',        _('Finance')),
        ('health',         _('Health & Fitness')),
        ('education',      _('Education')),
        ('shopping',       _('Shopping')),
        ('travel',         _('Travel')),
        ('news',           _('News')),
        ('photography',    _('Photography')),
        ('productivity',   _('Productivity')),
        ('lifestyle',      _('Lifestyle')),
        ('sports',         _('Sports')),
        ('other',          _('Other')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='apps',
        verbose_name=_("Publisher"),
    )
    app_id = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("App ID"),
    )
    name = models.CharField(
        null=True, blank=True,
        max_length=200,
        verbose_name=_("App Name"),
    )
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        verbose_name=_("Platform"),
        db_index=True,
    )
    package_name = models.CharField(
        null=True, blank=True,
        max_length=255,
        unique=True,
        verbose_name=_("Package Name / Bundle ID"),
        help_text=_("e.g., com.example.myapp"),
        db_index=True,
    )

    # ── Store Info ────────────────────────────────────────────────────────────
    play_store_url = models.URLField(
        null=True, blank=True,
        verbose_name=_("Google Play Store URL"),
    )
    app_store_url = models.URLField(
        verbose_name=_("Apple App Store URL"),
    )
    store_app_id = models.CharField(
        max_length=100,
        verbose_name=_("Store App ID"),
    )

    # ── Classification ────────────────────────────────────────────────────────
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name=_("Category"),
        db_index=True,
    )
    content_rating = models.CharField(
        max_length=20,
        default='Everyone',
        choices=[
            ('Everyone','Everyone'),('Everyone10+','Everyone 10+'),
            ('Teen','Teen'),('Mature17','Mature 17+'),('Adults','Adults Only 18+'),
        ],
        verbose_name=_("Content Rating"),
    )

    # ── Status & Quality ──────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status"),
        db_index=True,
    )
    quality_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Quality Score"),
        db_index=True,
    )

    # ── Download Stats ────────────────────────────────────────────────────────
    total_downloads = models.BigIntegerField(
        default=0,
        verbose_name=_("Total Downloads"),
    )
    active_users = models.BigIntegerField(
        default=0,
        verbose_name=_("Monthly Active Users"),
    )
    store_rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal('0.0'),
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Store Rating"),
    )
    store_reviews_count = models.IntegerField(
        default=0,
        verbose_name=_("Store Reviews Count"),
    )

    # ── Revenue ───────────────────────────────────────────────────────────────
    total_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Revenue (USD)"),
    )
    lifetime_impressions = models.BigIntegerField(default=0)
    lifetime_clicks = models.BigIntegerField(default=0)

    # ── App Details ───────────────────────────────────────────────────────────
    description = models.TextField(blank=True, verbose_name=_("Description"))
    icon_url = models.URLField(blank=True, verbose_name=_("App Icon URL"))
    screenshot_urls = models.JSONField(
        default=_default_list, blank=True,
        verbose_name=_("Screenshot URLs"),
    )
    version = models.CharField(max_length=20, blank=True, verbose_name=_("Version"))
    min_os_version = models.CharField(max_length=20, blank=True, verbose_name=_("Min OS Version"))

    # ── Review ────────────────────────────────────────────────────────────────
    rejection_reason = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_app_approved_by',)

    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_apps'
        verbose_name = _('App')
        verbose_name_plural = _('Apps')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app_id']),
            models.Index(fields=['package_name']),
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['platform', 'category']),
            models.Index(fields=['quality_score']),
        ]

    def __str__(self):
        return f"{self.name} ({self.package_name})"

    def save(self, *args, **kwargs):
        if not self.app_id:
            count = App.objects.count() + 1
            self.app_id = f"APP{count:06d}"
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == 'active'


class InventoryVerification(TimeStampedModel):
    """
    সাইট বা অ্যাপের মালিকানা যাচাই করার রেকর্ড।
    ads.txt, meta tag, DNS record, বা file-based verification।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_inventoryverification_tenant',
        db_index=True,)

    INVENTORY_TYPE_CHOICES = [
        ('site', _('Website')),
        ('app',  _('Mobile App')),
    ]

    VERIFICATION_METHOD_CHOICES = [
        ('ads_txt',    _('ads.txt File')),
        ('meta_tag',   _('HTML Meta Tag')),
        ('dns_record', _('DNS TXT Record')),
        ('file',       _('HTML File Upload')),
        ('api',        _('API Verification')),
        ('manual',     _('Manual Admin Verification')),
    ]

    STATUS_CHOICES = [
        ('pending',  _('Pending')),
        ('verified', _('Verified')),
        ('failed',   _('Failed')),
        ('expired',  _('Expired')),
    ]

    # ── Target ────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='verifications',
        verbose_name=_("Publisher"),
    )
    inventory_type = models.CharField(
        max_length=10,
        choices=INVENTORY_TYPE_CHOICES,
        verbose_name=_("Inventory Type"),
    )
    # Generic FK — site অথবা app যেকোনো একটা থাকবে
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='verifications',
        verbose_name=_("Site"),
    )
    app = models.ForeignKey(
        App,
        on_delete=models.CASCADE,
        related_name='verifications',
        verbose_name=_("App"),
    )

    # ── Verification Details ──────────────────────────────────────────────────
    method = models.CharField(
        max_length=20,
        choices=VERIFICATION_METHOD_CHOICES,
        default='ads_txt',
        verbose_name=_("Verification Method"),
    )
    verification_token = models.CharField(
        null=True, blank=True,
        max_length=64,
        unique=True,
        verbose_name=_("Verification Token"),
    )
    verification_code = models.TextField(
        verbose_name=_("Verification Code / Snippet"),
        help_text=_("যে code/tag টি সাইটে বসাতে হবে"),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status"),
        db_index=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Verified At"))
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Expires At"))
    last_checked_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, verbose_name=_("Failure Reason"))

    # ── Attempt Tracking ──────────────────────────────────────────────────────
    attempt_count = models.IntegerField(default=0, verbose_name=_("Verification Attempts"))
    max_attempts = models.IntegerField(default=5)

    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_inventory_verifications'
        verbose_name = _('Inventory Verification')
        verbose_name_plural = _('Inventory Verifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['verification_token']),
            models.Index(fields=['method', 'status']),
        ]

    def __str__(self):
        target = self.site or self.app
        return f"{self.publisher} → {target} [{self.method}] {self.status}"

    def save(self, *args, **kwargs):
        if not self.verification_token:
            self.verification_token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    @property
    def is_verified(self):
        return self.status == 'verified'

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


# ==============================================================================
# ২. AD UNIT & PLACEMENT MANAGEMENT
# বিজ্ঞাপনের ফরম্যাট, সাইজ এবং প্লেসমেন্ট কনফিগারেশন
# ==============================================================================

class AdUnit(TimeStampedModel):
    """
    একটি নির্দিষ্ট বিজ্ঞাপনের ফরম্যাট।
    একটি Site বা App-এ একাধিক AdUnit থাকতে পারে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_adunit_tenant',
        db_index=True,)

    # ── Ad Formats ────────────────────────────────────────────────────────────
    FORMAT_CHOICES = [
        # Web Formats
        ('banner',          _('Banner')),
        ('leaderboard',     _('Leaderboard (728×90)')),
        ('rectangle',       _('Rectangle (300×250)')),
        ('skyscraper',      _('Skyscraper (160×600)')),
        ('billboard',       _('Billboard (970×250)')),
        ('native',          _('Native Ad')),
        ('sticky',          _('Sticky / Anchor')),
        # App Formats
        ('interstitial',    _('Interstitial (Full Screen)')),
        ('rewarded_video',  _('Rewarded Video')),
        ('app_open',        _('App Open Ad')),
        ('offerwall',       _('Offerwall')),
        # Video
        ('instream_video',  _('In-Stream Video')),
        ('outstream_video', _('Out-Stream Video')),
        # Audio
        ('audio',           _('Audio Ad')),
        # Playable
        ('playable',        _('Playable Ad')),
    ]

    STATUS_CHOICES = [
        ('active',   _('Active')),
        ('paused',   _('Paused')),
        ('archived', _('Archived')),
        ('pending',  _('Pending Review')),
    ]

    INVENTORY_TYPE_CHOICES = [
        ('site', _('Website')),
        ('app',  _('Mobile App')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='ad_units',
        verbose_name=_("Publisher"),
    )
    inventory_type = models.CharField(
        max_length=10,
        choices=INVENTORY_TYPE_CHOICES,
        default='site',
        verbose_name=_("Inventory Type"),
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='ad_units',
        verbose_name=_("Site"),
    )
    app = models.ForeignKey(
        App,
        on_delete=models.CASCADE,
        related_name='ad_units',
        verbose_name=_("App"),
    )
    unit_id = models.CharField(
        null=True, blank=True,
        max_length=30,
        unique=True,
        verbose_name=_("Ad Unit ID"),
        db_index=True,
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("Ad Unit Name"),
    )
    format = models.CharField(
        null=True, blank=True,
        max_length=30,
        choices=FORMAT_CHOICES,
        verbose_name=_("Ad Format"),
        db_index=True,
    )

    # ── Size ──────────────────────────────────────────────────────────────────
    width = models.IntegerField(
        null=True, blank=True,
        verbose_name=_("Width (px)"),
    )
    height = models.IntegerField(
        verbose_name=_("Height (px)"),
    )
    is_responsive = models.BooleanField(
        default=True,
        verbose_name=_("Responsive Size"),
    )

    # ── Status & Settings ─────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Status"),
        db_index=True,
    )
    is_test_mode = models.BooleanField(
        default=False,
        verbose_name=_("Test Mode"),
        help_text=_("Test Mode-এ real ads দেখাবে না"),
    )

    # ── Floor Price ───────────────────────────────────────────────────────────
    floor_price = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Floor Price (USD CPM)"),
        help_text=_("এই মূল্যের নিচে bid accept হবে না"),
    )

    # ── Performance Stats ─────────────────────────────────────────────────────
    total_impressions = models.BigIntegerField(default=0, verbose_name=_("Total Impressions"))
    total_clicks = models.BigIntegerField(default=0, verbose_name=_("Total Clicks"))
    total_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Total Revenue (USD)"),
    )
    avg_ecpm = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Average eCPM (USD)"),
    )
    fill_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Fill Rate (%)"),
    )

    # ── Tag / Code ────────────────────────────────────────────────────────────
    tag_code = models.TextField(
        null=True, blank=True,
        verbose_name=_("Ad Tag Code"),
        help_text=_("সাইটে বসানোর জন্য generated JavaScript tag"),
    )
    sdk_key = models.CharField(
        max_length=100,
        verbose_name=_("SDK Key (for apps, null=True, blank=True)"),
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_ad_units'
        verbose_name = _('Ad Unit')
        verbose_name_plural = _('Ad Units')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['unit_id']),
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['format']),
            models.Index(fields=['inventory_type']),
            models.Index(fields=['floor_price']),
        ]

    def __str__(self):
        return f"{self.name} ({self.unit_id}) [{self.format}]"

    def save(self, *args, **kwargs):
        if not self.unit_id:
            count = AdUnit.objects.count() + 1
            self.unit_id = f"UNIT{count:06d}"
        super().save(*args, **kwargs)

    @property
    def ctr(self):
        if self.total_impressions > 0:
            return round((self.total_clicks / self.total_impressions) * 100, 4)
        return 0.0

    @property
    def size_label(self):
        if self.is_responsive:
            return "Responsive"
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "Unknown"


class AdPlacement(TimeStampedModel):
    """
    সাইট বা অ্যাপের কোন জায়গায় বিজ্ঞাপনটি দেখাবে — তার কনফিগারেশন।
    একটি AdUnit-এর সাথে অনেক Placement থাকতে পারে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_adplacement_tenant',
        db_index=True,)

    POSITION_CHOICES = [
        # Site Positions
        ('above_fold',     _('Above the Fold')),
        ('below_fold',     _('Below the Fold')),
        ('header',         _('Header')),
        ('footer',         _('Footer')),
        ('sidebar_left',   _('Left Sidebar')),
        ('sidebar_right',  _('Right Sidebar')),
        ('in_content',     _('In-Content')),
        ('between_posts',  _('Between Posts')),
        ('popup',          _('Popup')),
        ('sticky_bottom',  _('Sticky Bottom')),
        ('sticky_top',     _('Sticky Top')),
        # App Positions
        ('app_start',      _('App Launch Screen')),
        ('level_end',      _('Level / Stage End')),
        ('pause_menu',     _('Pause Menu')),
        ('exit_intent',    _('Exit Intent')),
        ('in_feed',        _('In-Feed')),
    ]

    REFRESH_TYPE_CHOICES = [
        ('none',       _('No Refresh')),
        ('time_based', _('Time-Based Refresh')),
        ('scroll',     _('Scroll-Based Refresh')),
        ('click',      _('Click-Based Refresh')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    ad_unit = models.ForeignKey(
        AdUnit,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='placements',
        verbose_name=_("Ad Unit"),
    )
    name = models.CharField(max_length=200, verbose_name=_("Placement Name"))
    position = models.CharField(
        max_length=30,
        choices=POSITION_CHOICES,
        verbose_name=_("Position on Page / App"),
        db_index=True,
    )

    # ── Visibility ────────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, verbose_name=_("Active"), db_index=True)
    show_on_mobile = models.BooleanField(default=True, verbose_name=_("Show on Mobile"))
    show_on_tablet = models.BooleanField(default=True, verbose_name=_("Show on Tablet"))
    show_on_desktop = models.BooleanField(default=True, verbose_name=_("Show on Desktop"))

    # ── Refresh ───────────────────────────────────────────────────────────────
    refresh_type = models.CharField(
        max_length=20,
        choices=REFRESH_TYPE_CHOICES,
        default='none',
        verbose_name=_("Refresh Type"),
    )
    refresh_interval_seconds = models.IntegerField(
        default=30,
        validators=[MinValueValidator(15), MaxValueValidator(300)],
        verbose_name=_("Refresh Interval (seconds)"),
        help_text=_("Minimum 15s, Maximum 300s"),
    )

    # ── Floor Price Override ──────────────────────────────────────────────────
    floor_price_override = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True, blank=True,
        verbose_name=_("Floor Price Override (USD CPM, null=True, blank=True)"),
        help_text=_("Set করলে AdUnit-এর floor price override হবে"),
    )

    # ── Viewability ───────────────────────────────────────────────────────────
    min_viewability_percentage = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Min Viewability Threshold (%)"),
    )
    avg_viewability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Avg Viewability (%)"),
    )

    # ── CSS / DOM Config ──────────────────────────────────────────────────────
    css_selector = models.CharField(
        null=True, blank=True,
        max_length=255,
        verbose_name=_("CSS Selector"),
        help_text=_("DOM element কোথায় inject হবে"),
    )
    custom_css = models.TextField(blank=True, verbose_name=_("Custom CSS"))

    # ── Stats ─────────────────────────────────────────────────────────────────
    total_impressions = models.BigIntegerField(default=0)
    total_clicks = models.BigIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000')
    )

    description = models.TextField(blank=True)
    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_ad_placements'
        verbose_name = _('Ad Placement')
        verbose_name_plural = _('Ad Placements')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad_unit', 'is_active']),
            models.Index(fields=['position']),
        ]

    def __str__(self):
        return f"{self.name} [{self.position}] on {self.ad_unit.name}"

    @property
    def effective_floor_price(self):
        """Placement-specific override, না থাকলে AdUnit-এর floor price"""
        return self.floor_price_override or self.ad_unit.floor_price


class AdUnitTargeting(TimeStampedModel):
    """
    কোন দেশের ইউজার বা কোন ডিভাইসে বিজ্ঞাপনটি চলবে — তার targeting রুলস।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_adunittargeting_tenant',
        db_index=True,)

    OS_CHOICES = [
        ('all',     _('All')),
        ('android', _('Android')),
        ('ios',     _('iOS')),
        ('windows', _('Windows')),
        ('macos',   _('macOS')),
        ('linux',   _('Linux')),
    ]

    DEVICE_TYPE_CHOICES = [
        ('all',     _('All Devices')),
        ('mobile',  _('Mobile Only')),
        ('tablet',  _('Tablet Only')),
        ('desktop', _('Desktop Only')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    ad_unit = models.OneToOneField(
        AdUnit,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='targeting',
        verbose_name=_("Ad Unit"),
    )
    name = models.CharField(
        max_length=200,
        default='Default Targeting',
        verbose_name=_("Targeting Name"),
    )

    # ── Geo Targeting ─────────────────────────────────────────────────────────
    target_countries = models.JSONField(
        default=_default_countries,
        blank=True,
        verbose_name=_("Target Countries"),
        help_text=_("['BD', 'US', 'ALL'] — ALL মানে সব দেশ"),
    )
    exclude_countries = models.JSONField(
        default=_default_list,
        verbose_name=_("Exclude Countries"),
    )
    target_regions = models.JSONField(
        default=_default_list,
        verbose_name=_("Target Regions / States"),
    )
    target_cities = models.JSONField(
        default=_default_list,
        verbose_name=_("Target Cities"),
    )

    # ── Device Targeting ──────────────────────────────────────────────────────
    device_type = models.CharField(
        max_length=10,
        choices=DEVICE_TYPE_CHOICES,
        default='all',
        verbose_name=_("Device Type"),
    )
    target_os = models.CharField(
        max_length=10,
        choices=OS_CHOICES,
        default='all',
        verbose_name=_("Operating System"),
    )
    min_os_version = models.CharField(
        null=True, blank=True,
        max_length=20,
        verbose_name=_("Min OS Version"),
    )

    # ── Browser / App Targeting ───────────────────────────────────────────────
    target_browsers = models.JSONField(
        default=_default_list,
        verbose_name=_("Target Browsers"),
        help_text=_("[] মানে সব browser"),
    )
    target_languages = models.JSONField(
        default=_default_list,
        blank=True,
        verbose_name=_("Target Languages"),
        help_text=_("['en', 'bn'] — [] মানে সব language"),
    )

    # ── Audience & Frequency ──────────────────────────────────────────────────
    frequency_cap = models.IntegerField(
        default=0,
        verbose_name=_("Frequency Cap (per user per day)"),
        help_text=_("0 মানে unlimited"),
    )
    frequency_window_hours = models.IntegerField(
        default=24,
        verbose_name=_("Frequency Window (hours)"),
    )

    # ── Schedule ──────────────────────────────────────────────────────────────
    schedule_days = models.JSONField(
        default=_default_list,
        blank=True,
        verbose_name=_("Schedule Days"),
        help_text=_("[0,1,2,3,4,5,6] — 0=Monday, [] মানে everyday"),
    )
    schedule_hours_start = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        verbose_name=_("Schedule Start Hour"),
    )
    schedule_hours_end = models.IntegerField(
        default=23,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        verbose_name=_("Schedule End Hour"),
    )

    is_active = models.BooleanField(default=True, verbose_name=_("Targeting Active"))
    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_ad_unit_targeting'
        verbose_name = _('Ad Unit Targeting')
        verbose_name_plural = _('Ad Unit Targeting Rules')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad_unit']),
            models.Index(fields=['device_type']),
        ]

    def __str__(self):
        return f"Targeting: {self.ad_unit.name} [{self.device_type}]"


# ==============================================================================
# ৩. MEDIATION & WATERFALL MANAGEMENT
# একাধিক Ad Network-কে একসাথে ম্যানেজ করার সিস্টেম
# ==============================================================================

class MediationGroup(TimeStampedModel):
    """
    একাধিক অ্যাড নেটওয়ার্ককে একত্রে ম্যানেজ করার গ্রুপ।
    একটি AdUnit-এ একটি MediationGroup assign করা হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_mediationgroup_tenant',
        db_index=True,)

    MEDIATION_TYPE_CHOICES = [
        ('waterfall',      _('Traditional Waterfall')),
        ('header_bidding', _('Header Bidding (Prebid)')),
        ('hybrid',         _('Hybrid (Waterfall + Bidding)')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    ad_unit = models.OneToOneField(
        AdUnit,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='mediation_group',
        verbose_name=_("Ad Unit"),
    )
    name = models.CharField(max_length=200, verbose_name=_("Mediation Group Name"))
    mediation_type = models.CharField(
        max_length=20,
        choices=MEDIATION_TYPE_CHOICES,
        default='waterfall',
        verbose_name=_("Mediation Type"),
        db_index=True,
    )

    # ── Optimization ─────────────────────────────────────────────────────────
    auto_optimize = models.BooleanField(
        default=False,
        verbose_name=_("Auto-Optimize Waterfall"),
        help_text=_("eCPM-based automatic waterfall reordering"),
    )
    optimization_interval_hours = models.IntegerField(
        default=24,
        verbose_name=_("Optimization Interval (hours)"),
    )
    last_optimized_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Last Optimized At"),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, verbose_name=_("Active"), db_index=True)

    # ── Performance ───────────────────────────────────────────────────────────
    total_ad_requests = models.BigIntegerField(default=0)
    total_impressions = models.BigIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000')
    )
    avg_ecpm = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('0.0000')
    )
    fill_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )

    description = models.TextField(blank=True)
    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_mediation_groups'
        verbose_name = _('Mediation Group')
        verbose_name_plural = _('Mediation Groups')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad_unit']),
            models.Index(fields=['mediation_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} [{self.mediation_type}] → {self.ad_unit.name}"


class WaterfallItem(TimeStampedModel):
    """
    Waterfall-এ কোন Ad Network কত priority-তে call হবে এবং
    তার eCPM floor কত — সেই কনফিগারেশন।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_waterfallitem_tenant',
        db_index=True,)

    BIDDING_TYPE_CHOICES = [
        ('cpm',         _('Fixed CPM')),
        ('dynamic',     _('Dynamic eCPM')),
        ('guaranteed',  _('Guaranteed Deal')),
        ('programmatic',_('Programmatic')),
    ]

    STATUS_CHOICES = [
        ('active',   _('Active')),
        ('paused',   _('Paused')),
        ('disabled', _('Disabled')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    mediation_group = models.ForeignKey(
        MediationGroup,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='waterfall_items',
        verbose_name=_("Mediation Group"),
    )
    # Ad Network — existing AdNetwork model থেকে reference
    network = models.ForeignKey(
        'ad_networks.AdNetwork',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='publisher_tools_waterfall_items',
        verbose_name=_("Ad Network"),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("Item Name"),
        help_text=_("e.g., AdMob Tier 1"),
    )

    # ── Priority & Pricing ────────────────────────────────────────────────────
    priority = models.IntegerField(
        null=True, blank=True,
        verbose_name=_("Priority"),
        help_text=_("1 = সবার আগে call হবে, সংখ্যা বড় হলে পরে"),
        db_index=True,
    )
    floor_ecpm = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Floor eCPM (USD)"),
        help_text=_("এই eCPM-এর নিচে bid reject হবে"),
    )
    bidding_type = models.CharField(
        max_length=20,
        choices=BIDDING_TYPE_CHOICES,
        default='dynamic',
        verbose_name=_("Bidding Type"),
    )

    # ── Network Config ────────────────────────────────────────────────────────
    network_app_id = models.CharField(
        null=True, blank=True,
        max_length=200,
        verbose_name=_("Network App ID"),
    )
    network_unit_id = models.CharField(
        max_length=200,
        verbose_name=_("Network Ad Unit ID"),
    )
    network_api_key = models.CharField(
        null=True, blank=True,
        max_length=255,
        verbose_name=_("Network API Key"),
    )
    extra_config = models.JSONField(
        default=_default_dict,
        verbose_name=_("Extra Network Config"),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Status"),
        db_index=True,
    )

    # ── Performance Stats ─────────────────────────────────────────────────────
    total_ad_requests = models.BigIntegerField(default=0)
    total_impressions = models.BigIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000')
    )
    avg_ecpm = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('0.0000')
    )
    fill_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    avg_latency_ms = models.IntegerField(
        default=0,
        verbose_name=_("Avg Latency (ms)"),
    )

    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_waterfall_items'
        verbose_name = _('Waterfall Item')
        verbose_name_plural = _('Waterfall Items')
        ordering = ['mediation_group', 'priority']
        unique_together = [['mediation_group', 'priority']]
        indexes = [
            models.Index(fields=['mediation_group', 'priority', 'status']),
            models.Index(fields=['network']),
            models.Index(fields=['floor_ecpm']),
        ]

    def __str__(self):
        return f"#{self.priority} {self.network.name} (floor: ${self.floor_ecpm})"


class HeaderBiddingConfig(TimeStampedModel):
    """
    Real-Time Bidding (RTB) / Header Bidding-এর জন্য demand partner config।
    Prebid.js বা server-side bidding-এর জন্য ব্যবহার হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_headerbiddingconfig_tenant',
        db_index=True,)

    BIDDER_TYPE_CHOICES = [
        ('prebid',         _('Prebid.js Client-Side')),
        ('prebid_server',  _('Prebid Server')),
        ('amazon_tam',     _('Amazon TAM')),
        ('google_open_bidding', _('Google Open Bidding')),
        ('custom',         _('Custom RTB')),
    ]

    STATUS_CHOICES = [
        ('active',  _('Active')),
        ('paused',  _('Paused')),
        ('testing', _('Testing')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    mediation_group = models.ForeignKey(
        MediationGroup,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='header_bidding_configs',
        verbose_name=_("Mediation Group"),
    )
    bidder_name = models.CharField(
        max_length=100,
        verbose_name=_("Bidder Name"),
        help_text=_("e.g., appnexus, rubicon, openx"),
    )
    bidder_type = models.CharField(
        max_length=30,
        choices=BIDDER_TYPE_CHOICES,
        default='prebid',
        verbose_name=_("Bidder Type"),
    )

    # ── Bidder Parameters ─────────────────────────────────────────────────────
    bidder_params = models.JSONField(
        default=_default_dict,
        verbose_name=_("Bidder Parameters"),
        help_text=_("Prebid.js bidder-specific params (JSON)"),
    )
    endpoint_url = models.URLField(
        null=True, blank=True,
        verbose_name=_("Endpoint URL"),
    )

    # ── Timing ────────────────────────────────────────────────────────────────
    timeout_ms = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(100), MaxValueValidator(5000)],
        verbose_name=_("Bid Timeout (ms)"),
    )
    price_floor = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Price Floor (USD CPM)"),
    )

    # ── Status & Stats ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Status"),
        db_index=True,
    )
    total_bid_requests = models.BigIntegerField(default=0)
    total_bid_responses = models.BigIntegerField(default=0)
    total_bid_wins = models.BigIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000')
    )
    avg_bid_cpm = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('0.0000')
    )

    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_header_bidding_configs'
        verbose_name = _('Header Bidding Config')
        verbose_name_plural = _('Header Bidding Configs')
        ordering = ['-created_at']
        unique_together = [['mediation_group', 'bidder_name']]
        indexes = [
            models.Index(fields=['mediation_group', 'status']),
            models.Index(fields=['bidder_name']),
        ]

    def __str__(self):
        return f"{self.bidder_name} [{self.bidder_type}] → {self.mediation_group.name}"

    @property
    def win_rate(self):
        if self.total_bid_responses > 0:
            return round((self.total_bid_wins / self.total_bid_responses) * 100, 2)
        return 0.0

    @property
    def bid_response_rate(self):
        if self.total_bid_requests > 0:
            return round((self.total_bid_responses / self.total_bid_requests) * 100, 2)
        return 0.0


# ==============================================================================
# ৪. EARNINGS & PAYOUTS
# পাবলিশারের আয়, ইনভয়েস এবং পেমেন্ট সিস্টেম
# ==============================================================================

class PublisherEarning(TimeStampedModel):
    """
    প্রতিদিনের বা প্রতি ঘণ্টার আয়ের রেকর্ড।
    Impression, Click, Revenue — granular data store।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherearning_tenant',
        db_index=True,)

    GRANULARITY_CHOICES = [
        ('hourly',  _('Hourly')),
        ('daily',   _('Daily')),
        ('weekly',  _('Weekly')),
        ('monthly', _('Monthly')),
    ]

    EARNING_TYPE_CHOICES = [
        ('display',       _('Display Ad')),
        ('video',         _('Video Ad')),
        ('native',        _('Native Ad')),
        ('interstitial',  _('Interstitial')),
        ('rewarded',      _('Rewarded Video')),
        ('offerwall',     _('Offerwall')),
        ('programmatic',  _('Programmatic')),
        ('direct_deal',   _('Direct Deal')),
        ('header_bidding',_('Header Bidding')),
    ]

    STATUS_CHOICES = [
        ('estimated',  _('Estimated')),
        ('confirmed',  _('Confirmed')),
        ('adjusted',   _('Adjusted')),
        ('finalized',  _('Finalized')),
        ('reversed',   _('Reversed')),
    ]

    # ── Core Reference ────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='earnings',
        verbose_name=_("Publisher"),
        db_index=True,
    )
    ad_unit = models.ForeignKey(
        AdUnit,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='earnings',
        verbose_name=_("Ad Unit"),
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='earnings',
        verbose_name=_("Site"),
    )
    app = models.ForeignKey(
        App,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='earnings',
        verbose_name=_("App"),
    )

    # ── Time Dimension ────────────────────────────────────────────────────────
    granularity = models.CharField(
        max_length=10,
        choices=GRANULARITY_CHOICES,
        default='daily',
        verbose_name=_("Granularity"),
        db_index=True,
    )
    date = models.DateField(verbose_name=_("Date"), db_index=True)
    hour = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        verbose_name=_("Hour (for hourly granularity)"),
    )

    # ── Ad Type ───────────────────────────────────────────────────────────────
    earning_type = models.CharField(
        max_length=20,
        choices=EARNING_TYPE_CHOICES,
        default='display',
        verbose_name=_("Earning Type"),
        db_index=True,
    )
    network = models.ForeignKey(
        'ad_networks.AdNetwork',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_earnings',
        verbose_name=_("Ad Network"),
    )

    # ── Geo Dimension ─────────────────────────────────────────────────────────
    country = models.CharField(
        max_length=10,
        verbose_name=_("Country Code"),
        db_index=True,
    )
    country_name = models.CharField(max_length=100, null=True, blank=True)

    # ── Traffic Metrics ───────────────────────────────────────────────────────
    ad_requests = models.BigIntegerField(default=0, verbose_name=_("Ad Requests"))
    impressions = models.BigIntegerField(default=0, verbose_name=_("Impressions"))
    clicks = models.BigIntegerField(default=0, verbose_name=_("Clicks"))
    conversions = models.IntegerField(default=0, verbose_name=_("Conversions"))
    video_starts = models.BigIntegerField(default=0, verbose_name=_("Video Starts"))
    video_completions = models.BigIntegerField(default=0, verbose_name=_("Video Completions"))

    # ── Revenue ───────────────────────────────────────────────────────────────
    gross_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=Decimal('0.000000'),
        verbose_name=_("Gross Revenue (USD)"),
    )
    publisher_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=Decimal('0.000000'),
        verbose_name=_("Publisher Revenue (USD)"),
        help_text=_("Revenue share-এর পরে publisher কত পাবে"),
    )
    platform_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=Decimal('0.000000'),
        verbose_name=_("Platform Revenue (USD)"),
    )

    # ── Derived Metrics (stored for fast aggregation) ─────────────────────────
    ecpm = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("eCPM (USD)"),
    )
    ctr = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("CTR (%)"),
    )
    fill_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Fill Rate (%)"),
    )
    rpm = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("RPM (Revenue per 1000 pageviews)"),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='estimated',
        verbose_name=_("Status"),
        db_index=True,
    )
    invalid_traffic_deduction = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=Decimal('0.000000'),
        verbose_name=_("IVT Deduction (USD)"),
        help_text=_("Invalid Traffic-এর কারণে কাটা গেছে"),
    )
    adjustment_amount = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=Decimal('0.000000'),
        verbose_name=_("Adjustment Amount"),
    )
    adjustment_reason = models.TextField(blank=True, verbose_name=_("Adjustment Reason"))

    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_earnings'
        verbose_name = _('Publisher Earning')
        verbose_name_plural = _('Publisher Earnings')
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'date']),
            models.Index(fields=['publisher', 'date', 'granularity']),
            models.Index(fields=['date', 'country']),
            models.Index(fields=['ad_unit', 'date']),
            models.Index(fields=['status']),
            models.Index(fields=['earning_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['publisher', 'ad_unit', 'date', 'hour', 'country', 'earning_type'],
                name='unique_publisher_earning_record',
                condition=models.Q(ad_unit__isnull=False),
            )
        ]

    def __str__(self):
        return f"{self.publisher} | {self.date} | ${self.publisher_revenue}"

    @property
    def net_publisher_revenue(self):
        """IVT deduction এবং adjustment-এর পরে actual revenue"""
        return (
            self.publisher_revenue
            - self.invalid_traffic_deduction
            + self.adjustment_amount
        )


class PayoutThreshold(TimeStampedModel):
    """
    পাবলিশার কত টাকা হলে উইথড্র করতে পারবে — সেই threshold কনফিগারেশন।
    Publisher tier বা payment method অনুযায়ী আলাদা threshold থাকতে পারে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_payoutthreshold_tenant',
        db_index=True,)

    PAYMENT_METHOD_CHOICES = [
        ('paypal',       _('PayPal')),
        ('bank_transfer',_('Bank Transfer')),
        ('wire',         _('Wire Transfer')),
        ('crypto_btc',   _('Crypto (Bitcoin)')),
        ('crypto_usdt',  _('Crypto (USDT)')),
        ('payoneer',     _('Payoneer')),
        ('bkash',        _('bKash')),
        ('nagad',        _('Nagad')),
        ('rocket',       _('Rocket')),
        ('check',        _('Paper Check')),
    ]

    FREQUENCY_CHOICES = [
        ('monthly',    _('Monthly (Net 30)')),
        ('bimonthly',  _('Bi-Monthly (Net 15)')),
        ('weekly',     _('Weekly')),
        ('on_demand',  _('On Demand')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='payout_thresholds',
        verbose_name=_("Publisher"),
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name=_("Payment Method"),
        db_index=True,
    )

    # ── Threshold Config ──────────────────────────────────────────────────────
    minimum_threshold = models.DecimalField(
        null=True, blank=True,
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Minimum Payout Threshold (USD, null=True, blank=True)"),
        help_text=_("এই পরিমাণ না হলে payout request করা যাবে না"),
    )
    payment_frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='monthly',
        verbose_name=_("Payment Frequency"),
    )

    # ── Fee & Tax ─────────────────────────────────────────────────────────────
    processing_fee_flat = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Processing Fee (flat, USD)"),
    )
    processing_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Processing Fee (%)"),
    )
    withholding_tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Withholding Tax (%)"),
    )

    # ── Payment Details ───────────────────────────────────────────────────────
    payment_details = models.JSONField(
        default=_default_dict,
        verbose_name=_("Payment Details"),
        help_text=_("PayPal email, bank account info, etc."),
    )

    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Primary Payment Method"),
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("Payment Method Verified"),
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'publisher_tools_payout_thresholds'
        verbose_name = _('Payout Threshold')
        verbose_name_plural = _('Payout Thresholds')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'payment_method']),
            models.Index(fields=['is_primary']),
        ]

    def __str__(self):
        return f"{self.publisher} | {self.payment_method} | Min: ${self.minimum_threshold}"

    @property
    def effective_fee(self):
        """Flat fee + percentage fee combined"""
        return self.processing_fee_flat + (
            self.publisher.pending_balance * (self.processing_fee_percentage / 100)
        )


class PublisherInvoice(TimeStampedModel):
    """
    প্রতি মাসের পেমেন্ট স্টেটমেন্ট বা ইনভয়েস।
    Net 30 বা On Demand পেমেন্টের জন্য invoice generate হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherinvoice_tenant',
        db_index=True,)

    STATUS_CHOICES = [
        ('draft',      _('Draft')),
        ('issued',     _('Issued')),
        ('processing', _('Processing Payment')),
        ('paid',       _('Paid')),
        ('failed',     _('Payment Failed')),
        ('disputed',   _('Disputed')),
        ('cancelled',  _('Cancelled')),
    ]

    INVOICE_TYPE_CHOICES = [
        ('regular',    _('Regular Monthly')),
        ('on_demand',  _('On Demand Request')),
        ('adjustment', _('Adjustment')),
        ('bonus',      _('Bonus Payment')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_("Publisher"),
        db_index=True,
    )
    invoice_number = models.CharField(
        max_length=30,
        unique=True,
        verbose_name=_("Invoice Number"),
        help_text=_("Auto-generated: INV-2024-01-000001"),
        db_index=True,
    )
    invoice_type = models.CharField(
        max_length=20,
        choices=INVOICE_TYPE_CHOICES,
        default='regular',
        verbose_name=_("Invoice Type"),
    )

    # ── Period ────────────────────────────────────────────────────────────────
    period_start = models.DateField(verbose_name=_("Period Start"), null=True, blank=True)
    period_end = models.DateField(verbose_name=_("Period End"), null=True, blank=True)

    # ── Financial Summary ─────────────────────────────────────────────────────
    gross_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Gross Revenue (USD)"),
    )
    publisher_share = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Publisher Share (USD)"),
    )
    ivt_deduction = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("IVT Deduction (USD)"),
    )
    adjustment = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Adjustment (USD)"),
    )
    processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Processing Fee (USD)"),
    )
    withholding_tax = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Withholding Tax (USD)"),
    )
    net_payable = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Net Payable (USD)"),
        help_text=_("সব deduction-এর পরে actual payment amount"),
    )
    currency = models.CharField(
        max_length=5,
        default='USD',
        verbose_name=_("Currency"),
    )

    # ── Payment Details ───────────────────────────────────────────────────────
    payout_threshold = models.ForeignKey(
        PayoutThreshold,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
        verbose_name=_("Payment Method Used"),
    )
    payment_reference = models.CharField(
        max_length=200,
        verbose_name=_("Payment Reference / Transaction ID"),
    )

    # ── Status & Dates ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name=_("Status"),
        db_index=True,
    )
    issued_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Issued At"))
    due_date = models.DateField(null=True, blank=True, verbose_name=_("Due Date"))
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Paid At"))
    failed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Failed At"))
    failure_reason = models.TextField(blank=True, verbose_name=_("Failure Reason"))

    # ── Traffic Stats Summary ─────────────────────────────────────────────────
    total_impressions = models.BigIntegerField(default=0)
    total_clicks = models.BigIntegerField(default=0)
    total_ad_requests = models.BigIntegerField(default=0)

    # ── Admin ─────────────────────────────────────────────────────────────────
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_invoice_processed_by',
        verbose_name=_("Processed By"),
    )
    admin_notes = models.TextField(blank=True, verbose_name=_("Admin Notes"))
    publisher_notes = models.TextField(blank=True, verbose_name=_("Publisher Notes"))

    metadata = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_invoices'
        verbose_name = _('Publisher Invoice')
        verbose_name_plural = _('Publisher Invoices')
        ordering = ['-period_end', '-created_at']
        indexes = [
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"{self.invoice_number} | {self.publisher} | ${self.net_payable} | {self.status}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            now = timezone.now()
            count = PublisherInvoice.objects.filter(
                period_start__year=now.year,
                period_start__month=now.month,
            ).count() + 1
            self.invoice_number = f"INV-{now.year}-{now.month:02d}-{count:06d}"
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ('paid', 'cancelled'):
            return timezone.now().date() > self.due_date
        return False

    def calculate_net_payable(self):
        """Net payable auto-calculate করে save করে"""
        self.net_payable = (
            self.publisher_share
            - self.ivt_deduction
            + self.adjustment
            - self.processing_fee
            - self.withholding_tax
        )
        self.save()
        return self.net_payable


# ==============================================================================
# ৫. TRAFFIC QUALITY & FRAUD PREVENTION
# Invalid Traffic (IVT) detection এবং site quality monitoring
# ==============================================================================

class TrafficSafetyLog(TimeStampedModel):
    """
    Invalid Traffic (IVT) বা Bot Traffic-এর ডিটেইলস লগ।
    প্রতিটি suspicious event আলাদাভাবে log হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_trafficsafetylog_tenant',
        db_index=True,)

    TRAFFIC_TYPE_CHOICES = [
        # General IVT
        ('bot',              _('Bot Traffic')),
        ('crawler',          _('Web Crawler / Spider')),
        ('scraper',          _('Content Scraper')),
        # Click Fraud
        ('click_fraud',      _('Click Fraud')),
        ('click_injection',  _('Click Injection')),
        ('click_flooding',   _('Click Flooding')),
        # Impression Fraud
        ('impression_fraud', _('Impression Fraud')),
        ('ad_stacking',      _('Ad Stacking')),
        ('pixel_stuffing',   _('Pixel Stuffing')),
        ('hidden_ad',        _('Hidden Ad')),
        # Device/IP Fraud
        ('device_farm',      _('Device Farm')),
        ('emulator',         _('Emulator / Virtual Device')),
        ('vpn',              _('VPN Traffic')),
        ('proxy',            _('Proxy Traffic')),
        ('tor',              _('Tor Network')),
        # Geographic
        ('geo_mismatch',     _('Geo Mismatch')),
        # SDK Fraud
        ('sdk_spoofing',     _('SDK Spoofing')),
        ('install_hijacking',_('Install Hijacking')),
        # Organic Fraud
        ('incentivized',     _('Incentivized Non-Compliant Traffic')),
        ('suspicious',       _('Suspicious Pattern')),
        ('other',            _('Other IVT')),
    ]

    SEVERITY_CHOICES = [
        ('low',      _('Low')),
        ('medium',   _('Medium')),
        ('high',     _('High')),
        ('critical', _('Critical')),
    ]

    ACTION_TAKEN_CHOICES = [
        ('flagged',     _('Flagged for Review')),
        ('deducted',    _('Revenue Deducted')),
        ('warned',      _('Publisher Warned')),
        ('suspended',   _('Publisher Suspended')),
        ('blocked',     _('IP / Device Blocked')),
        ('no_action',   _('No Action Required')),
        ('pending',     _('Pending Review')),
    ]

    # ── Source Reference ──────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        Publisher,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='traffic_safety_logs',
        verbose_name=_("Publisher"),
        db_index=True,
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='traffic_safety_logs',
        verbose_name=_("Site"),
    )
    app = models.ForeignKey(
        App,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='traffic_safety_logs',
        verbose_name=_("App"),
    )
    ad_unit = models.ForeignKey(
        AdUnit,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='traffic_safety_logs',
        verbose_name=_("Ad Unit"),
    )

    # ── Event Details ─────────────────────────────────────────────────────────
    traffic_type = models.CharField(
        max_length=30,
        choices=TRAFFIC_TYPE_CHOICES,
        verbose_name=_("IVT Type"),
        db_index=True,
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='medium',
        verbose_name=_("Severity"),
        db_index=True,
    )
    detected_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Detected At"),
        db_index=True,
    )

    # ── Traffic Source ────────────────────────────────────────────────────────
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name=_("IP Address"),
        db_index=True,
    )
    ip_range = models.CharField(
        max_length=20,
        verbose_name=_("IP Range / CIDR"),
    )
    user_agent = models.TextField(blank=True, verbose_name=_("User Agent"))
    device_id = models.CharField(max_length=255, blank=True, db_index=True, null=True)
    country = models.CharField(max_length=10, blank=True, db_index=True, null=True)
    city = models.CharField(max_length=100, null=True, blank=True)

    # ── Detection Details ─────────────────────────────────────────────────────
    fraud_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Fraud Score (0-100)"),
        db_index=True,
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Detection Confidence (%)"),
    )
    detection_method = models.CharField(
        null=True, blank=True,
        max_length=100,
        verbose_name=_("Detection Method"),
        help_text=_("e.g., ML Model, IP Blacklist, Pattern Matching"),
    )
    detection_signals = models.JSONField(
        default=_default_dict,
        verbose_name=_("Detection Signals"),
        help_text=_("Detailed signals that triggered this alert"),
    )

    # ── Revenue Impact ────────────────────────────────────────────────────────
    affected_impressions = models.BigIntegerField(
        default=0,
        verbose_name=_("Affected Impressions"),
    )
    affected_clicks = models.BigIntegerField(
        default=0,
        verbose_name=_("Affected Clicks"),
    )
    revenue_at_risk = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Revenue at Risk (USD)"),
    )
    revenue_deducted = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name=_("Revenue Deducted (USD)"),
    )

    # ── Action ────────────────────────────────────────────────────────────────
    action_taken = models.CharField(
        max_length=20,
        choices=ACTION_TAKEN_CHOICES,
        default='pending',
        verbose_name=_("Action Taken"),
        db_index=True,
    )
    action_taken_at = models.DateTimeField(null=True, blank=True)
    action_taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_traffic_actions',
        verbose_name=_("Action Taken By"),
    )

    is_false_positive = models.BooleanField(
        default=False,
        verbose_name=_("Marked as False Positive"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    raw_data = models.JSONField(default=_default_dict, blank=True, verbose_name=_("Raw Event Data"))

    class Meta:
        db_table = 'publisher_tools_traffic_safety_logs'
        verbose_name = _('Traffic Safety Log')
        verbose_name_plural = _('Traffic Safety Logs')
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['publisher', 'detected_at']),
            models.Index(fields=['traffic_type', 'severity']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['fraud_score']),
            models.Index(fields=['action_taken']),
            models.Index(fields=['is_false_positive']),
        ]

    def __str__(self):
        return (
            f"{self.traffic_type} | {self.severity} | "
            f"{self.publisher} | Score: {self.fraud_score} | {self.detected_at:%Y-%m-%d}"
        )

    @property
    def is_high_risk(self):
        return self.fraud_score >= 70 or self.severity in ('high', 'critical')

    @property
    def requires_action(self):
        return self.action_taken == 'pending' and not self.is_false_positive


class SiteQualityMetric(TimeStampedModel):
    """
    সাইটের Viewability, Content Quality এবং UX Score।
    Daily basis-এ update হয়, long-term trend analysis-এর জন্য।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_sitequalitymetric_tenant',
        db_index=True,)

    CONTENT_QUALITY_CHOICES = [
        ('excellent', _('Excellent')),
        ('good',      _('Good')),
        ('average',   _('Average')),
        ('poor',      _('Poor')),
        ('rejected',  _('Rejected / Non-Compliant')),
    ]

    # ── Reference ─────────────────────────────────────────────────────────────
    site = models.ForeignKey(
        Site,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='quality_metrics',
        verbose_name=_("Site"),
        db_index=True,
    )
    date = models.DateField(verbose_name=_("Date"), db_index=True)

    # ── Viewability Metrics ───────────────────────────────────────────────────
    viewability_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Viewability Rate (%)"),
        help_text=_("MRC standard: ad visible for 1+ sec (display) / 2+ sec (video)"),
    )
    avg_time_in_view = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Avg Time in View (seconds)"),
    )
    measured_impressions = models.BigIntegerField(
        default=0,
        verbose_name=_("Measured Impressions"),
    )
    viewable_impressions = models.BigIntegerField(
        default=0,
        verbose_name=_("Viewable Impressions"),
    )

    # ── Traffic Quality ───────────────────────────────────────────────────────
    bot_traffic_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Bot Traffic (%)"),
    )
    invalid_traffic_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Invalid Traffic (%)"),
    )
    vpn_traffic_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("VPN Traffic (%)"),
    )

    # ── Content Quality ───────────────────────────────────────────────────────
    content_quality = models.CharField(
        max_length=20,
        choices=CONTENT_QUALITY_CHOICES,
        default='average',
        verbose_name=_("Content Quality Rating"),
        db_index=True,
    )
    content_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Content Score"),
    )
    spam_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Spam Score"),
        help_text=_("0 = ভালো, 100 = সম্পূর্ণ spam"),
    )
    adult_content_detected = models.BooleanField(
        default=False,
        verbose_name=_("Adult Content Detected"),
    )
    malware_detected = models.BooleanField(
        default=False,
        verbose_name=_("Malware Detected"),
    )

    # ── Page Performance (Core Web Vitals) ───────────────────────────────────
    page_speed_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Page Speed Score (0-100)"),
    )
    lcp_ms = models.IntegerField(
        null=True, blank=True,
        verbose_name=_("LCP (Largest Contentful Paint, ms)"),
    )
    fid_ms = models.IntegerField(
        null=True, blank=True,
        verbose_name=_("FID (First Input Delay, ms)"),
    )
    cls_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True, blank=True,
        verbose_name=_("CLS (Cumulative Layout Shift, null=True, blank=True)"),
    )

    # ── Overall Quality Score ─────────────────────────────────────────────────
    overall_quality_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Overall Quality Score"),
        db_index=True,
        help_text=_("Composite score: viewability + traffic quality + content"),
    )
    score_change = models.IntegerField(
        default=0,
        verbose_name=_("Score Change vs Previous Day"),
    )

    # ── Ads Compliance ────────────────────────────────────────────────────────
    ads_txt_present = models.BooleanField(default=False, verbose_name=_("ads.txt Present"))
    ads_txt_valid = models.BooleanField(default=False, verbose_name=_("ads.txt Valid"))
    ad_density_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Ad Density Score"),
        help_text=_("100 = optimal density, 0 = too many ads"),
    )

    # ── Alerts ────────────────────────────────────────────────────────────────
    has_alerts = models.BooleanField(
        default=False,
        verbose_name=_("Has Quality Alerts"),
        db_index=True,
    )
    alert_details = models.JSONField(
        default=_default_list,
        blank=True,
        verbose_name=_("Alert Details"),
    )

    raw_report = models.JSONField(
        default=_default_dict,
        verbose_name=_("Raw Quality Report Data"),
    )

    class Meta:
        db_table = 'publisher_tools_site_quality_metrics'
        verbose_name = _('Site Quality Metric')
        verbose_name_plural = _('Site Quality Metrics')
        ordering = ['-date']
        unique_together = [['site', 'date']]
        indexes = [
            models.Index(fields=['site', 'date']),
            models.Index(fields=['overall_quality_score']),
            models.Index(fields=['content_quality']),
            models.Index(fields=['has_alerts']),
            models.Index(fields=['viewability_rate']),
        ]

    def __str__(self):
        return (
            f"{self.site.domain} | {self.date} | "
            f"Score: {self.overall_quality_score} | Viewability: {self.viewability_rate}%"
        )

    @property
    def is_high_quality(self):
        return (
            self.overall_quality_score >= 70
            and self.viewability_rate >= 50
            and self.invalid_traffic_percentage <= 10
        )

    @property
    def needs_attention(self):
        return (
            self.overall_quality_score < 40
            or self.invalid_traffic_percentage >= 20
            or self.malware_detected
            or self.adult_content_detected
        )

    def calculate_overall_score(self):
        """
        Composite quality score calculate করে।
        Weights: Viewability 35%, Content 30%, Traffic 25%, Performance 10%
        """
        viewability_component = min(float(self.viewability_rate), 100) * 0.35
        content_component = self.content_score * 0.30
        traffic_quality = max(0, 100 - float(self.invalid_traffic_percentage)) * 0.25
        performance = (self.page_speed_score or 50) * 0.10

        self.overall_quality_score = round(
            viewability_component
            + content_component
            + traffic_quality
            + performance
        )
        return self.overall_quality_score
