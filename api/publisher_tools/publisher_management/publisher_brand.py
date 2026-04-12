# api/publisher_tools/publisher_management/publisher_brand.py
"""
Publisher Brand & Store — Publisher-এর branding, white-label settings।
Publisher-এর নিজস্ব brand identity ও public store page।
"""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class PublisherBrand(TimeStampedModel):
    """
    Publisher-এর brand identity।
    Logo, colors, social links — সব এখানে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherbrand_tenant', db_index=True,
    )

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.OneToOneField(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='brand',
        verbose_name=_("Publisher"),
    )

    # ── Brand Identity ────────────────────────────────────────────────────────
    brand_name = models.CharField(
        max_length=200, blank=True,
        verbose_name=_("Brand Name"),
        help_text=_("Publisher display name থেকে আলাদা হলে"),
    )
    tagline = models.CharField(
        max_length=300, blank=True,
        verbose_name=_("Brand Tagline"),
        help_text=_("e.g., 'Your trusted ad partner'"),
    )
    short_description = models.TextField(
        blank=True,
        verbose_name=_("Short Description (max 200 chars)"),
    )
    full_description = models.TextField(
        blank=True,
        verbose_name=_("Full About Description"),
    )

    # ── Visual Identity ────────────────────────────────────────────────────────
    logo = models.ImageField(
        upload_to='publisher_brands/logos/',
        null=True, blank=True,
        verbose_name=_("Brand Logo"),
    )
    logo_dark = models.ImageField(
        upload_to='publisher_brands/logos/dark/',
        null=True, blank=True,
        verbose_name=_("Dark Mode Logo"),
    )
    favicon = models.ImageField(
        upload_to='publisher_brands/favicons/',
        null=True, blank=True,
        verbose_name=_("Favicon"),
    )
    cover_image = models.ImageField(
        upload_to='publisher_brands/covers/',
        null=True, blank=True,
        verbose_name=_("Cover / Banner Image"),
    )

    # ── Colors ────────────────────────────────────────────────────────────────
    primary_color   = models.CharField(max_length=10, default='#2563eb', verbose_name=_("Primary Color"))
    secondary_color = models.CharField(max_length=10, default='#7c3aed', verbose_name=_("Secondary Color"))
    accent_color    = models.CharField(max_length=10, default='#f59e0b', verbose_name=_("Accent Color"))
    text_color      = models.CharField(max_length=10, default='#1f2937', verbose_name=_("Text Color"))
    background_color= models.CharField(max_length=10, default='#ffffff', verbose_name=_("Background Color"))

    # ── Custom Fonts ──────────────────────────────────────────────────────────
    heading_font = models.CharField(
        max_length=100, default='Inter',
        verbose_name=_("Heading Font"),
    )
    body_font = models.CharField(
        max_length=100, default='Inter',
        verbose_name=_("Body Font"),
    )

    # ── Social Media ──────────────────────────────────────────────────────────
    website_url   = models.URLField(blank=True, verbose_name=_("Website URL"))
    facebook_url  = models.URLField(blank=True, verbose_name=_("Facebook Page URL"))
    twitter_url   = models.URLField(blank=True, verbose_name=_("Twitter / X URL"))
    linkedin_url  = models.URLField(blank=True, verbose_name=_("LinkedIn URL"))
    youtube_url   = models.URLField(blank=True, verbose_name=_("YouTube Channel URL"))
    instagram_url = models.URLField(blank=True, verbose_name=_("Instagram URL"))
    telegram_url  = models.URLField(blank=True, verbose_name=_("Telegram Channel URL"))
    whatsapp_number = models.CharField(max_length=20, blank=True, verbose_name=_("WhatsApp Number"))

    # ── White-label Settings ──────────────────────────────────────────────────
    custom_domain = models.CharField(
        max_length=255, blank=True,
        verbose_name=_("Custom Domain"),
        help_text=_("e.g., ads.yourdomain.com — Enterprise only"),
    )
    custom_domain_verified = models.BooleanField(default=False)
    custom_email_domain = models.CharField(
        max_length=255, blank=True,
        verbose_name=_("Custom Email Domain"),
        help_text=_("e.g., noreply@yourdomain.com for notifications"),
    )
    email_from_name = models.CharField(
        max_length=100, blank=True,
        verbose_name=_("Email Sender Name"),
    )

    # ── Publisher Store Page ───────────────────────────────────────────────────
    store_slug = models.SlugField(
        max_length=100, unique=True, blank=True,
        verbose_name=_("Store Page Slug"),
        help_text=_("e.g., 'my-media-company' → publishertools.io/publisher/my-media-company"),
    )
    is_store_public = models.BooleanField(
        default=False,
        verbose_name=_("Make Store Page Public"),
    )
    store_headline = models.CharField(max_length=300, blank=True, verbose_name=_("Store Page Headline"))
    store_cta_text = models.CharField(
        max_length=100, default='Contact Us',
        verbose_name=_("Store CTA Button Text"),
    )
    store_cta_url = models.URLField(blank=True, verbose_name=_("Store CTA URL"))

    # ── SEO ───────────────────────────────────────────────────────────────────
    meta_title       = models.CharField(max_length=200, blank=True, verbose_name=_("Meta Title"))
    meta_description = models.CharField(max_length=400, blank=True, verbose_name=_("Meta Description"))
    meta_keywords    = models.CharField(max_length=500, blank=True, verbose_name=_("Meta Keywords"))

    # ── Contact Info ──────────────────────────────────────────────────────────
    contact_email   = models.EmailField(blank=True, verbose_name=_("Public Contact Email"))
    contact_phone   = models.CharField(max_length=20, blank=True, verbose_name=_("Public Contact Phone"))
    support_url     = models.URLField(blank=True, verbose_name=_("Support Page URL"))
    privacy_url     = models.URLField(blank=True, verbose_name=_("Privacy Policy URL"))
    terms_url       = models.URLField(blank=True, verbose_name=_("Terms of Service URL"))

    # ── Awards & Certifications ────────────────────────────────────────────────
    awards       = models.JSONField(default=list, blank=True, verbose_name=_("Awards & Recognition"))
    certifications = models.JSONField(default=list, blank=True, verbose_name=_("Certifications"))
    partner_badges = models.JSONField(default=list, blank=True, verbose_name=_("Partner Badges"))

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_brands'
        verbose_name = _('Publisher Brand')
        verbose_name_plural = _('Publisher Brands')
        ordering = ['-created_at']

    def __str__(self):
        return f"Brand: {self.publisher.publisher_id} — {self.brand_name or self.publisher.display_name}"

    @property
    def effective_brand_name(self):
        return self.brand_name or self.publisher.display_name

    @property
    def store_url(self):
        if self.store_slug:
            return f"https://publishertools.io/publisher/{self.store_slug}"
        return None

    @property
    def color_palette(self):
        return {
            'primary':    self.primary_color,
            'secondary':  self.secondary_color,
            'accent':     self.accent_color,
            'text':       self.text_color,
            'background': self.background_color,
        }

    @property
    def social_links(self):
        links = {}
        if self.facebook_url:  links['facebook']  = self.facebook_url
        if self.twitter_url:   links['twitter']   = self.twitter_url
        if self.linkedin_url:  links['linkedin']  = self.linkedin_url
        if self.youtube_url:   links['youtube']   = self.youtube_url
        if self.instagram_url: links['instagram'] = self.instagram_url
        if self.telegram_url:  links['telegram']  = self.telegram_url
        return links


class PublisherRating(TimeStampedModel):
    """
    Publisher-এর rating ও review system।
    Advertiser বা admin দেওয়া rating track করে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherrating_tenant', db_index=True,
    )

    RATING_TYPE_CHOICES = [
        ('advertiser_review', _('Advertiser Review')),
        ('admin_quality',     _('Admin Quality Assessment')),
        ('automated_score',   _('Automated Quality Score')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name=_("Publisher"),
        db_index=True,
    )
    rated_by = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_ratings_given',
        verbose_name=_("Rated By (Tenant/Advertiser)"),
    )
    rating_type = models.CharField(
        max_length=30,
        choices=RATING_TYPE_CHOICES,
        default='admin_quality',
        verbose_name=_("Rating Type"),
        db_index=True,
    )

    # ── Ratings (1-5 scale) ────────────────────────────────────────────────────
    overall_rating = models.DecimalField(
        max_digits=3, decimal_places=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Overall Rating (1-5)"),
    )
    traffic_quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=Decimal('5.0'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Traffic Quality"),
    )
    content_quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=Decimal('5.0'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Content Quality"),
    )
    compliance_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=Decimal('5.0'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Compliance / Policy Adherence"),
    )
    communication_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=Decimal('5.0'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Communication"),
    )

    # ── Review Text ───────────────────────────────────────────────────────────
    review_title = models.CharField(max_length=200, blank=True, verbose_name=_("Review Title"))
    review_text  = models.TextField(blank=True, verbose_name=_("Review Text"))
    is_public    = models.BooleanField(default=False, verbose_name=_("Show on Public Profile"))
    is_verified  = models.BooleanField(default=False, verbose_name=_("Verified Review"))

    # ── Publisher Response ─────────────────────────────────────────────────────
    publisher_response = models.TextField(blank=True, verbose_name=_("Publisher Response"))
    response_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_ratings'
        verbose_name = _('Publisher Rating')
        verbose_name_plural = _('Publisher Ratings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'rating_type']),
            models.Index(fields=['overall_rating']),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.overall_rating}/5 ({self.rating_type})"


class PublisherBlacklist(TimeStampedModel):
    """
    Publisher blacklist / whitelist system।
    Specific advertisers বা content categories block করার জন্য।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherblacklist_tenant', db_index=True,
    )

    LIST_TYPE_CHOICES = [
        ('advertiser_blacklist', _('Advertiser Blacklist')),
        ('advertiser_whitelist', _('Advertiser Whitelist')),
        ('category_blacklist',   _('Content Category Blacklist')),
        ('keyword_blacklist',    _('Keyword Blacklist')),
        ('competitor_block',     _('Competitor Brand Block')),
        ('domain_blacklist',     _('Ad Domain Blacklist')),
    ]

    publisher   = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='blacklist_entries',
        verbose_name=_("Publisher"),
    )
    list_type   = models.CharField(max_length=30, choices=LIST_TYPE_CHOICES, verbose_name=_("List Type"), db_index=True)
    value       = models.CharField(max_length=500, verbose_name=_("Blocked Value"), help_text=_("Advertiser ID, category name, keyword, domain, etc."))
    reason      = models.TextField(blank=True, verbose_name=_("Reason"))
    is_active   = models.BooleanField(default=True, db_index=True)
    expires_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Expires At"))
    created_by  = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='publisher_tools_blacklist_created',
    )

    class Meta:
        db_table = 'publisher_tools_publisher_blacklists'
        verbose_name = _('Publisher Blacklist Entry')
        verbose_name_plural = _('Publisher Blacklist Entries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'list_type', 'is_active']),
            models.Index(fields=['value']),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.list_type}: {self.value[:50]}"

    @property
    def is_expired(self):
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False
