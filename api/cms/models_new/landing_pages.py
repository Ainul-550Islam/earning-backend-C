# api/cms/models_new/landing_pages.py
"""
CPAlead Landing Pages — pre-designed pages for gaming traffic.
CPAlead 2025: Minecraft, Roblox, Fortnite, GTA V, etc.
"""
import uuid
from django.db import models
from django.conf import settings

GAMING_NICHES = [
    ('minecraft',  'Minecraft'),
    ('roblox',     'Roblox'),
    ('fortnite',   'Fortnite'),
    ('gta_v',      'GTA V'),
    ('valorant',   'Valorant'),
    ('general',    'General'),
    ('free_robux', 'Free Robux'),
    ('free_vbucks','Free V-Bucks'),
    ('mod_menu',   'Mod Menu'),
    ('cheats',     'Cheats & Hacks'),
    ('skins',      'Free Skins'),
    ('custom',     'Custom'),
]


class LandingPage(models.Model):
    """Pre-designed CPAlead landing page for gaming/social traffic."""
    uuid         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name         = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=200, unique=True)
    niche        = models.CharField(max_length=20, choices=GAMING_NICHES, default='general', db_index=True)
    headline     = models.CharField(max_length=300)
    sub_headline = models.CharField(max_length=500, blank=True)
    description  = models.TextField(blank=True)
    cta_text     = models.CharField(max_length=100, default='Get It Now — Free!')
    thumbnail    = models.URLField(blank=True)
    background_color = models.CharField(max_length=20, default='#1a1a2e')
    accent_color = models.CharField(max_length=20, default='#00d2ff')
    # Monetization
    locker       = models.ForeignKey('cms.ContentLocker', on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='landing_pages')
    smartlink    = models.ForeignKey('cms.SmartLink', on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='landing_pages')
    # Tracking
    views        = models.PositiveIntegerField(default=0)
    clicks       = models.PositiveIntegerField(default=0)
    conversions  = models.PositiveIntegerField(default=0)
    # Status
    is_active    = models.BooleanField(default=True, db_index=True)
    is_featured  = models.BooleanField(default=False)
    custom_css   = models.TextField(blank=True)
    custom_html  = models.TextField(blank=True)
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL, null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Landing Page"
        ordering = ['-is_featured', '-created_at']

    def __str__(self):
        return f"[{self.niche}] {self.name}"

    @property
    def conversion_rate(self):
        if not self.views:
            return 0.0
        return round(self.conversions / self.views * 100, 2)

    @property
    def ctr(self):
        if not self.views:
            return 0.0
        return round(self.clicks / self.views * 100, 2)
