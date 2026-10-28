# api/cms/models_new/smartlink.py
"""
SmartLink — Geo+Device offer routing. CMS owns this.
CPAlead SmartLink: auto-detects visitor location+device → shows best offer.
Rule: এক কাজের জন্য একটাই মালিক।
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class SmartLink(models.Model):
    """A smart link that routes users to best offer by geo+device."""
    ROTATION_MODES = [
        ('best_payout',   'Best Payout First'),
        ('geo_optimized', 'GEO Optimized'),
        ('device_match',  'Device Match'),
        ('round_robin',   'Round Robin'),
        ('weight',        'Weighted Random'),
    ]
    uuid         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name         = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=200, unique=True)
    description  = models.TextField(blank=True)
    rotation_mode = models.CharField(max_length=20, choices=ROTATION_MODES,
                                      default='best_payout')
    fallback_url  = models.URLField(blank=True,
                                    help_text="URL when no matching offer found")
    is_active     = models.BooleanField(default=True, db_index=True)
    # Stats
    total_clicks  = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.SET_NULL, null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Smart Link"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.rotation_mode})"

    def get_best_offer(self, country: str = '', device: str = 'desktop'):
        """Return the best matching offer for given country+device."""
        rules = self.routing_rules.filter(is_active=True)
        # Geo filter
        if country:
            geo_rules = rules.filter(
                models.Q(target_countries=[]) | models.Q(target_countries__icontains=country.upper())
            )
            if geo_rules.exists():
                rules = geo_rules
        # Device filter
        if device:
            dev_rules = rules.filter(
                models.Q(target_devices=[]) | models.Q(target_devices__icontains=device.lower())
            )
            if dev_rules.exists():
                rules = dev_rules

        if self.rotation_mode == 'best_payout':
            return rules.order_by('-payout_usd').first()
        elif self.rotation_mode == 'round_robin':
            import random
            items = list(rules)
            return random.choice(items) if items else None
        elif self.rotation_mode == 'weight':
            import random
            items = list(rules)
            if not items:
                return None
            weights = [r.weight for r in items]
            return random.choices(items, weights=weights, k=1)[0]
        return rules.first()


class SmartLinkRule(models.Model):
    """Routing rule within a SmartLink."""
    smartlink     = models.ForeignKey(SmartLink, on_delete=models.CASCADE,
                                       related_name='routing_rules')
    offer_id      = models.CharField(max_length=100, blank=True,
                                      help_text="CPAlead offer_id")
    offer_url     = models.URLField(blank=True)
    offer_title   = models.CharField(max_length=300, blank=True)
    payout_usd    = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    target_countries = models.JSONField(default=list, blank=True,
                                         help_text="Empty = all countries")
    target_devices   = models.JSONField(default=list, blank=True,
                                         help_text="desktop, mobile, tablet. Empty = all")
    weight        = models.PositiveIntegerField(default=1,
                                                 help_text="Higher = more traffic in weighted mode")
    is_active     = models.BooleanField(default=True)
    click_count   = models.PositiveIntegerField(default=0)
    conversion_count = models.PositiveIntegerField(default=0)
    order         = models.PositiveIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Smart Link Rule"
        ordering = ['order', '-payout_usd']

    def __str__(self):
        return f"{self.smartlink.name} → {self.offer_title or self.offer_url}"


class SmartLinkClick(models.Model):
    """Track clicks on smart links for analytics."""
    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    smartlink     = models.ForeignKey(SmartLink, on_delete=models.CASCADE,
                                       related_name='clicks')
    rule_used     = models.ForeignKey(SmartLinkRule, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='clicks')
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    country_code  = models.CharField(max_length=5, blank=True)
    device_type   = models.CharField(max_length=20, blank=True)
    subid         = models.CharField(max_length=200, blank=True)
    has_converted = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Click on {self.smartlink.name} from {self.country_code or self.ip_address}"

    class Meta:
        app_label = "cms"
        verbose_name = "Smart Link Click"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['smartlink', 'created_at']),
            models.Index(fields=['country_code', 'device_type']),
        ]
