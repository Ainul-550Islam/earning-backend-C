from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/models/seo.py
"""
SEO models: SEOConfig, Sitemap, Redirect301, RobotsConfig
Full production-ready with sitemap generation, robots.txt management, and redirect tracking.
"""
import uuid
import logging
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from imagekit.models import ProcessedImageField
from imagekit.processors import SmartResize
from core.models import TimeStampedModel

logger = logging.getLogger(__name__)


def default_dict():
    return {}


def default_list():
    return []


# ─────────────────────────────────────────────
# SEOConfig
# ─────────────────────────────────────────────

class SEOConfig(TimeStampedModel):
    """
    Global SEO configuration for the site.
    Singleton-like model (one active record per site).
    """
    TWITTER_CARD_CHOICES = [
        ('summary', _('Summary')),
        ('summary_large_image', _('Summary Large Image')),
        ('app', _('App')),
        ('player', _('Player')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    site_name = models.CharField(_("Site Name"), max_length=200, default='My Site')
    default_title = models.CharField(
        _("Default Title"), max_length=200, blank=True
    )
    title_separator = models.CharField(
        _("Title Separator"), max_length=10, default=' | '
    )
    default_description = models.TextField(
        _("Default Meta Description"), blank=True
    )
    default_keywords = models.CharField(
        _("Default Keywords"), max_length=500, blank=True
    )
    og_image = ProcessedImageField(
        upload_to='seo/og/%Y/%m/',
        processors=[SmartResize(1200, 630)],
        format='WEBP',
        options={'quality': 90},
        blank=True, null=True,
        verbose_name=_("Default OG Image")
    )
    og_type = models.CharField(
        _("OG Type"), max_length=50, default='website'
    )
    twitter_card = models.CharField(
        _("Twitter Card"), max_length=30,
        choices=TWITTER_CARD_CHOICES, default='summary_large_image'
    )
    twitter_site = models.CharField(
        _("Twitter Site"), max_length=100, blank=True,
        help_text=_("@twitterhandle")
    )
    twitter_creator = models.CharField(
        _("Twitter Creator"), max_length=100, blank=True
    )
    google_analytics_id = models.CharField(
        _("Google Analytics ID"), max_length=50, blank=True,
        help_text=_("e.g. G-XXXXXXXXXX or UA-XXXXXXX-X")
    )
    google_tag_manager_id = models.CharField(
        _("Google Tag Manager ID"), max_length=50, blank=True
    )
    google_search_console = models.TextField(
        _("Google Search Console Verification"), blank=True,
        help_text=_("Meta tag content or HTML file content")
    )
    bing_webmaster = models.CharField(
        _("Bing Webmaster Verification"), max_length=200, blank=True
    )
    facebook_app_id = models.CharField(
        _("Facebook App ID"), max_length=100, blank=True
    )
    canonical_base_url = models.URLField(
        _("Canonical Base URL"), blank=True,
        help_text=_("e.g. https://www.example.com")
    )
    enable_breadcrumbs = models.BooleanField(_("Enable Breadcrumbs"), default=True)
    enable_json_ld = models.BooleanField(_("Enable JSON-LD"), default=True)
    json_ld_org_data = models.JSONField(
        _("Organization JSON-LD"), default=default_dict, blank=True,
        help_text=_("Schema.org organization data")
    )
    noindex_site = models.BooleanField(
        _("Noindex Entire Site"), default=False,
        help_text=_("WARNING: Will prevent search engine indexing")
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("SEO Config")
        verbose_name_plural = _("SEO Configs")
        ordering = ['-created_at']

    def __str__(self):
        return f"SEO Config: {self.site_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('seo_config_active')

    @classmethod
    def get_active(cls):
        """Get the active SEO config with caching."""
        config = cache.get('seo_config_active')
        if config is None:
            try:
                config = cls.objects.filter(is_active=True).latest('created_at')
            except cls.DoesNotExist:
                config = None
            cache.set('seo_config_active', config, 3600)
        return config

    def build_page_title(self, page_title=''):
        """Build full page title."""
        if not page_title:
            return self.default_title or self.site_name
        if self.default_title:
            return f"{page_title}{self.title_separator}{self.site_name}"
        return page_title

    def get_og_image_url(self):
        """Get default OG image URL."""
        if self.og_image:
            return self.og_image.url
        return ''


# ─────────────────────────────────────────────
# Sitemap
# ─────────────────────────────────────────────

class Sitemap(TimeStampedModel):
    """Individual sitemap entry for a URL."""

    CHANGEFREQ_CHOICES = [
        ('always', _('Always')),
        ('hourly', _('Hourly')),
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
        ('yearly', _('Yearly')),
        ('never', _('Never')),
    ]

    PRIORITY_CHOICES = [
        (0.0, '0.0'),
        (0.1, '0.1'),
        (0.2, '0.2'),
        (0.3, '0.3'),
        (0.4, '0.4'),
        (0.5, '0.5'),
        (0.6, '0.6'),
        (0.7, '0.7'),
        (0.8, '0.8'),
        (0.9, '0.9'),
        (1.0, '1.0'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    url = models.URLField(_("URL"), unique=True, max_length=2000)
    changefreq = models.CharField(
        _("Change Frequency"), max_length=20,
        choices=CHANGEFREQ_CHOICES, default='weekly'
    )
    priority = models.FloatField(
        _("Priority"), default=0.5,
        choices=PRIORITY_CHOICES
    )
    last_modified = models.DateTimeField(
        _("Last Modified"), default=timezone.now
    )
    is_active = models.BooleanField(_("Active"), default=True)
    source_type = models.CharField(
        _("Source Type"), max_length=100, blank=True,
        help_text=_("Model name, e.g. 'BlogPost', 'ContentPage'")
    )
    source_id = models.PositiveIntegerField(
        _("Source ID"), null=True, blank=True
    )
    # Auto-regeneration
    is_auto_generated = models.BooleanField(
        _("Auto Generated"), default=False
    )
    last_crawled = models.DateTimeField(
        _("Last Crawled"), null=True, blank=True
    )
    crawl_status = models.IntegerField(
        _("Crawl Status"), null=True, blank=True,
        help_text=_("HTTP status code from last crawl")
    )

    class Meta:
        app_label = "cms"
        verbose_name = _("Sitemap Entry")
        verbose_name_plural = _("Sitemap Entries")
        ordering = ['-priority', 'url']
        indexes = [
            models.Index(fields=['is_active', 'priority']),
            models.Index(fields=['source_type', 'source_id']),
            models.Index(fields=['last_modified']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return self.url

    def clean(self):
        if not 0.0 <= self.priority <= 1.0:
            raise ValidationError(_("Priority must be between 0.0 and 1.0."))

    def update_last_modified(self):
        """Update last modified timestamp."""
        Sitemap.objects.filter(id=self.id).update(last_modified=timezone.now())

    def deactivate(self):
        """Deactivate this sitemap entry."""
        Sitemap.objects.filter(id=self.id).update(is_active=False)

    @classmethod
    def upsert_for_object(cls, url, source_type, source_id, priority=0.5, changefreq='weekly'):
        """Create or update sitemap entry for a model object."""
        obj, created = cls.objects.update_or_create(
            url=url,
            defaults={
                'source_type': source_type,
                'source_id': source_id,
                'priority': priority,
                'changefreq': changefreq,
                'last_modified': timezone.now(),
                'is_active': True,
                'is_auto_generated': True,
            }
        )
        return obj

    @classmethod
    def remove_for_object(cls, source_type, source_id):
        """Remove/deactivate sitemap entries for a model object."""
        cls.objects.filter(
            source_type=source_type, source_id=source_id
        ).update(is_active=False)

    @classmethod
    def generate_xml(cls):
        """Generate sitemap XML content."""
        entries = cls.objects.filter(is_active=True).order_by('-priority')
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        for entry in entries:
            lines.append('  <url>')
            lines.append(f'    <loc>{entry.url}</loc>')
            lines.append(f'    <lastmod>{entry.last_modified.strftime("%Y-%m-%d")}</lastmod>')
            lines.append(f'    <changefreq>{entry.changefreq}</changefreq>')
            lines.append(f'    <priority>{entry.priority:.1f}</priority>')
            lines.append('  </url>')
        lines.append('</urlset>')
        return '\n'.join(lines)


# ─────────────────────────────────────────────
# Redirect301
# ─────────────────────────────────────────────

class Redirect301(TimeStampedModel):
    """301 permanent redirect management."""

    REDIRECT_TYPE_CHOICES = [
        (301, '301 Permanent'),
        (302, '302 Temporary'),
        (307, '307 Temporary (preserve method)'),
        (308, '308 Permanent (preserve method)'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    from_url = models.CharField(
        _("From URL"), max_length=2000, unique=True,
        help_text=_("Source URL path, e.g. /old-page/")
    )
    to_url = models.CharField(
        _("To URL"), max_length=2000,
        help_text=_("Destination URL")
    )
    redirect_type = models.IntegerField(
        _("Redirect Type"),
        choices=REDIRECT_TYPE_CHOICES, default=301
    )
    is_active = models.BooleanField(_("Active"), default=True)
    hit_count = models.PositiveIntegerField(_("Hit Count"), default=0)
    last_hit = models.DateTimeField(_("Last Hit"), null=True, blank=True)
    notes = models.TextField(_("Notes"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_redirects'
    )
    expires_at = models.DateTimeField(
        _("Expires At"), null=True, blank=True,
        help_text=_("Redirect expires after this date")
    )

    class Meta:
        app_label = "cms"
        verbose_name = _("Redirect")
        verbose_name_plural = _("Redirects")
        ordering = ['-hit_count', 'from_url']
        indexes = [
            models.Index(fields=['from_url', 'is_active']),
            models.Index(fields=['is_active', 'redirect_type']),
            models.Index(fields=['uuid']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.from_url} → {self.to_url} ({self.redirect_type})"

    def clean(self):
        if self.from_url == self.to_url:
            raise ValidationError(_("From URL and To URL cannot be the same."))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate redirect lookup cache
        cache.delete(f'redirect_{self.from_url}')
        cache.delete('redirect_map')

    def record_hit(self):
        """Record a redirect hit."""
        Redirect301.objects.filter(id=self.id).update(
            hit_count=F('hit_count') + 1,
            last_hit=timezone.now()
        )
        self.refresh_from_db()

    def is_expired(self):
        """Check if this redirect has expired."""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def deactivate_if_expired(self):
        """Deactivate if expired."""
        if self.is_expired():
            self.is_active = False
            self.save(update_fields=['is_active'])
            return True
        return False

    @classmethod
    def find_redirect(cls, from_url):
        """Find active redirect for URL (with caching)."""
        cache_key = f'redirect_{from_url}'
        result = cache.get(cache_key)
        if result is None:
            try:
                redirect = cls.objects.get(
                    from_url=from_url, is_active=True
                )
                if redirect.is_expired():
                    redirect.deactivate_if_expired()
                    result = None
                else:
                    result = redirect
            except cls.DoesNotExist:
                result = None
            cache.set(cache_key, result, 3600)
        return result

    @classmethod
    def bulk_create_from_csv(cls, csv_content, user=None):
        """
        Bulk create redirects from CSV data.
        CSV format: from_url, to_url, redirect_type (optional)
        """
        import csv
        import io
        reader = csv.reader(io.StringIO(csv_content))
        created = 0
        errors = []
        with transaction.atomic():
            for row in reader:
                try:
                    if len(row) < 2:
                        continue
                    from_url = row[0].strip()
                    to_url = row[1].strip()
                    redirect_type = int(row[2].strip()) if len(row) > 2 else 301
                    _, created_now = cls.objects.update_or_create(
                        from_url=from_url,
                        defaults={
                            'to_url': to_url,
                            'redirect_type': redirect_type,
                            'is_active': True,
                            'created_by': user,
                        }
                    )
                    if created_now:
                        created += 1
                except Exception as e:
                    errors.append(str(e))
        return created, errors


# ─────────────────────────────────────────────
# RobotsConfig
# ─────────────────────────────────────────────

class RobotsConfig(TimeStampedModel):
    """Robots.txt configuration management."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Config Name"), max_length=200, default='Default')
    is_active = models.BooleanField(_("Active"), default=True)

    # Rules (stored as JSON arrays)
    allow_rules = models.JSONField(
        _("Allow Rules"), default=default_list,
        help_text=_("List of paths to allow, e.g. ['/public/', '/blog/']")
    )
    disallow_rules = models.JSONField(
        _("Disallow Rules"), default=default_list,
        help_text=_("List of paths to disallow, e.g. ['/admin/', '/api/private/']")
    )
    sitemap_url = models.URLField(
        _("Sitemap URL"), blank=True,
        help_text=_("Full URL to sitemap.xml")
    )
    crawl_delay = models.IntegerField(
        _("Crawl Delay"), default=0,
        help_text=_("Crawl delay in seconds (0 = no delay)")
    )

    # Per-bot rules
    per_bot_rules = models.JSONField(
        _("Per-Bot Rules"), default=default_dict, blank=True,
        help_text=_("Rules per bot, e.g. {Googlebot: {allow: ['/'], disallow: ['/private/']}}")
    )

    # Additional custom content
    custom_content = models.TextField(
        _("Custom Content"), blank=True,
        help_text=_("Additional raw content to append to robots.txt")
    )

    class Meta:
        app_label = "cms"
        verbose_name = _("Robots Config")
        verbose_name_plural = _("Robots Configs")
        ordering = ['-created_at']

    def __str__(self):
        return f"Robots Config: {self.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('robots_txt')
        cache.delete('robots_config_active')

    @classmethod
    def get_active(cls):
        """Get active robots config."""
        config = cache.get('robots_config_active')
        if config is None:
            try:
                config = cls.objects.filter(is_active=True).latest('created_at')
            except cls.DoesNotExist:
                config = None
            cache.set('robots_config_active', config, 3600)
        return config

    def generate_robots_txt(self):
        """Generate robots.txt content."""
        lines = ['User-agent: *']

        for rule in self.allow_rules:
            lines.append(f'Allow: {rule}')

        for rule in self.disallow_rules:
            lines.append(f'Disallow: {rule}')

        if self.crawl_delay > 0:
            lines.append(f'Crawl-delay: {self.crawl_delay}')

        # Per-bot rules
        for bot_name, bot_rules in (self.per_bot_rules or {}).items():
            lines.append(f'\nUser-agent: {bot_name}')
            for allow_path in bot_rules.get('allow', []):
                lines.append(f'Allow: {allow_path}')
            for disallow_path in bot_rules.get('disallow', []):
                lines.append(f'Disallow: {disallow_path}')

        if self.sitemap_url:
            lines.append(f'\nSitemap: {self.sitemap_url}')

        if self.custom_content:
            lines.append(f'\n{self.custom_content}')

        content = '\n'.join(lines)
        cache.set('robots_txt', content, 3600)
        return content

    def add_disallow_rule(self, path):
        """Add a disallow rule."""
        rules = self.disallow_rules or []
        if path not in rules:
            rules.append(path)
            self.disallow_rules = rules
            self.save(update_fields=['disallow_rules'])

    def add_allow_rule(self, path):
        """Add an allow rule."""
        rules = self.allow_rules or []
        if path not in rules:
            rules.append(path)
            self.allow_rules = rules
            self.save(update_fields=['allow_rules'])

    def remove_rule(self, path, rule_type='disallow'):
        """Remove a rule."""
        if rule_type == 'disallow':
            rules = [r for r in (self.disallow_rules or []) if r != path]
            self.disallow_rules = rules
        else:
            rules = [r for r in (self.allow_rules or []) if r != path]
            self.allow_rules = rules
        self.save(update_fields=[f'{rule_type}_rules'])


# Alias used in tests
SEOModel = SEOConfig
