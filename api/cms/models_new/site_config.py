# api/cms/models_new/site_config.py
"""
SiteConfig — Per-site settings. CMS owns this.
Theme, logo, social links, maintenance mode, cookie notice, etc.
Rule: এক কাজের জন্য একটাই মালিক।
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


class SiteConfig(models.Model):
    """Complete site configuration — one row per site."""
    # Identity
    site_name     = models.CharField(max_length=200, default='My Earning Site')
    site_tagline  = models.CharField(max_length=300, blank=True)
    site_domain   = models.CharField(max_length=200, blank=True, db_index=True)
    logo_url      = models.URLField(blank=True)
    favicon_url   = models.URLField(blank=True)
    # Theme
    primary_color    = models.CharField(max_length=20, default='#007bff')
    secondary_color  = models.CharField(max_length=20, default='#6c757d')
    font_family      = models.CharField(max_length=100, default='Inter, sans-serif')
    dark_mode_default = models.BooleanField(default=False)
    custom_css       = models.TextField(blank=True)
    custom_js        = models.TextField(blank=True)
    # Contact
    contact_email    = models.EmailField(blank=True)
    support_url      = models.URLField(blank=True)
    privacy_url      = models.URLField(blank=True)
    terms_url        = models.URLField(blank=True)
    # Social
    twitter_url      = models.URLField(blank=True)
    facebook_url     = models.URLField(blank=True)
    instagram_url    = models.URLField(blank=True)
    youtube_url      = models.URLField(blank=True)
    discord_url      = models.URLField(blank=True)
    telegram_url     = models.URLField(blank=True)
    # Maintenance
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(default='Site under maintenance. Please check back later.')
    maintenance_allowed_ips = models.TextField(blank=True,
                                               help_text="Allowed IPs during maintenance, one per line")
    # Cookie / GDPR
    cookie_notice_enabled = models.BooleanField(default=True)
    cookie_notice_text    = models.TextField(blank=True)
    # Analytics
    google_analytics_id   = models.CharField(max_length=50, blank=True)
    facebook_pixel_id     = models.CharField(max_length=50, blank=True)
    # Features toggles
    registration_enabled  = models.BooleanField(default=True)
    referral_enabled      = models.BooleanField(default=True)
    leaderboard_enabled   = models.BooleanField(default=True)
    quiz_enabled          = models.BooleanField(default=True)
    offerwall_enabled     = models.BooleanField(default=True)
    blog_enabled          = models.BooleanField(default=True)
    # Min withdrawal
    min_withdrawal_coins  = models.DecimalField(max_digits=10, decimal_places=2, default=1000)
    min_withdrawal_usd    = models.DecimalField(max_digits=8, decimal_places=2, default=10)
    is_active    = models.BooleanField(default=True, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Site Config"
        verbose_name_plural = "Site Configs"

    def __str__(self):
        return f"{self.site_name} ({self.site_domain or 'default'})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('site_config_active')  # Invalidate cache

    @classmethod
    def get_active(cls, domain: str = ''):
        cache_key = f'site_config_{domain or "active"}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            if domain:
                config = cls.objects.filter(site_domain=domain, is_active=True).first()
                if not config:
                    config = cls.objects.filter(is_active=True, site_domain='').first()
            else:
                config = cls.objects.filter(is_active=True).order_by('site_domain').first()
        except Exception:
            config = None
        cache.set(cache_key, config, 300)  # 5 min cache
        return config

    def get_maintenance_ips(self):
        return [ip.strip() for ip in self.maintenance_allowed_ips.split('\n') if ip.strip()]


class ContentSchedule(models.Model):
    """Content calendar — schedule content publication."""
    CONTENT_TYPES = [
        ('blog_post',    'Blog Post'),
        ('page',         'CMS Page'),
        ('announcement', 'Announcement'),
        ('popup',        'Popup'),
        ('banner',       'Banner'),
        ('email',        'Email Campaign'),
    ]
    STATUS = [
        ('draft',     'Draft'),
        ('scheduled', 'Scheduled'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
    ]
    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title         = models.CharField(max_length=300)
    content_type  = models.CharField(max_length=20, choices=CONTENT_TYPES, db_index=True)
    content_id    = models.PositiveIntegerField(null=True, blank=True)
    status        = models.CharField(max_length=15, choices=STATUS,
                                     default='scheduled', db_index=True)
    scheduled_at  = models.DateTimeField(db_index=True)
    published_at  = models.DateTimeField(null=True, blank=True)
    expires_at    = models.DateTimeField(null=True, blank=True)
    note          = models.TextField(blank=True)
    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='content_schedules')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Content Schedule"
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['content_type', 'content_id']),
        ]

    def __str__(self):
        return f"{self.title} → {self.scheduled_at:%Y-%m-%d %H:%M}"

    def is_due(self) -> bool:
        return self.status == 'scheduled' and timezone.now() >= self.scheduled_at
