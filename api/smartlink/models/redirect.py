from django.db import models
from django.utils.translation import gettext_lazy as _
from .smartlink import SmartLink
from ..choices import RedirectType
from ..validators import validate_redirect_url


class RedirectLog(models.Model):
    """
    Full audit log of every SmartLink → Offer redirect.
    Used for transparency, debugging, and postback matching.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='smartlink_redirect_logs',
        db_index=True,
    )
    offer = models.ForeignKey(
        'offer_inventory.Offer', on_delete=models.SET_NULL,
        null=True, related_name='smartlink_redirect_logs',
    )
    click = models.OneToOneField(
        'smartlink.Click', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='redirect_log',
    )
    ip = models.GenericIPAddressField()
    country = models.CharField(max_length=2, blank=True)
    device_type = models.CharField(max_length=10, blank=True)
    redirect_type = models.CharField(
        max_length=5,
        choices=RedirectType.choices,
        default=RedirectType.HTTP_302,
    )
    source_url = models.URLField(max_length=2048, blank=True)
    destination_url = models.URLField(max_length=2048)
    status_code = models.PositiveSmallIntegerField(default=302)
    response_time_ms = models.FloatField(default=0.0)
    was_cached = models.BooleanField(default=False)
    was_fallback = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'sl_redirect_log'
        verbose_name = _('Redirect Log')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['smartlink', 'created_at'], name='rlog_sl_ts_idx'),
            models.Index(fields=['offer', 'created_at'], name='rlog_offer_ts_idx'),
            models.Index(fields=['ip'], name='rlog_ip_idx'),
        ]

    def __str__(self):
        return f"Redirect#{self.pk}: {self.smartlink.slug} → {self.destination_url[:60]}"


class RedirectRule(models.Model):
    """
    Custom redirect logic override for a SmartLink.
    Allows hard-coded redirects that bypass the targeting engine.
    Example: If IP = specific range → always redirect to offer X.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='redirect_rules',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    condition_type = models.CharField(
        max_length=20,
        choices=[
            ('ip_range', 'IP Range'),
            ('country', 'Country'),
            ('ua_contains', 'User Agent Contains'),
            ('param_match', 'URL Parameter Match'),
            ('time_based', 'Time Based'),
        ]
    )
    condition_value = models.CharField(max_length=500, help_text=_('Value to match against.'))
    redirect_url = models.URLField(
        max_length=2048,
        validators=[validate_redirect_url],
        help_text=_('Override redirect URL when condition is matched.')
    )
    priority = models.PositiveSmallIntegerField(default=0, help_text=_('Higher = evaluated first.'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_redirect_rule'
        verbose_name = _('Redirect Rule')
        ordering = ['-priority', 'name']

    def __str__(self):
        return f"Rule: [{self.smartlink.slug}] {self.name} ({self.condition_type})"


class LandingPage(models.Model):
    """
    Intermediate landing page shown before offer redirect.
    Publisher can host a pre-sell page before sending traffic to the offer.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='landing_pages',
    )
    name = models.CharField(max_length=100)
    url = models.URLField(max_length=2048, validators=[validate_redirect_url])
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    traffic_split = models.PositiveSmallIntegerField(
        default=100,
        help_text=_('Percentage of traffic to this landing page (0-100).')
    )
    # Performance stats
    views = models.PositiveBigIntegerField(default=0)
    clicks_through = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_landing_page'
        verbose_name = _('Landing Page')
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"LP: {self.smartlink.slug} → {self.name}"

    @property
    def ctr(self):
        if self.views == 0:
            return 0.0
        return round(self.clicks_through / self.views * 100, 2)


class PreLander(models.Model):
    """
    Pre-landing page (survey/quiz) shown before landing page or offer.
    Warms up the user with qualifying questions to improve conversion rates.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='pre_landers',
    )
    name = models.CharField(max_length=100)
    url = models.URLField(max_length=2048, validators=[validate_redirect_url])
    type = models.CharField(
        max_length=20,
        choices=[
            ('survey', 'Survey'),
            ('quiz', 'Quiz'),
            ('video', 'Video'),
            ('article', 'Article'),
            ('custom', 'Custom'),
        ],
        default='custom',
    )
    is_active = models.BooleanField(default=True)
    pass_through_params = models.BooleanField(
        default=True,
        help_text=_('Pass sub1-sub5 params through the pre-lander URL.')
    )
    views = models.PositiveBigIntegerField(default=0)
    pass_through_count = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_pre_lander'
        verbose_name = _('Pre-Lander')
        ordering = ['name']

    def __str__(self):
        return f"PreLander: {self.smartlink.slug} | {self.name} ({self.type})"

    @property
    def pass_through_rate(self):
        if self.views == 0:
            return 0.0
        return round(self.pass_through_count / self.views * 100, 2)


class RedirectChain(models.Model):
    """
    Multi-hop redirect tracking.
    Records the full chain: SmartLink → PreLander → LandingPage → Offer.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='redirect_chains',
    )
    click = models.ForeignKey(
        'smartlink.Click', on_delete=models.CASCADE,
        related_name='redirect_chain',
    )
    chain = models.JSONField(
        default=list,
        help_text=_(
            'Ordered list of hops. Each hop: '
            '{"step": 1, "type": "pre_lander", "url": "...", "ts": "..."}'
        )
    )
    hop_count = models.PositiveSmallIntegerField(default=0)
    total_time_ms = models.FloatField(default=0.0)
    completed = models.BooleanField(default=False)
    final_url = models.URLField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_redirect_chain'
        verbose_name = _('Redirect Chain')
        ordering = ['-created_at']

    def __str__(self):
        return f"Chain: {self.smartlink.slug} | {self.hop_count} hops | {'✓' if self.completed else '…'}"

    def add_hop(self, step_type: str, url: str):
        from django.utils import timezone
        self.chain.append({
            'step': self.hop_count + 1,
            'type': step_type,
            'url': url,
            'ts': timezone.now().isoformat(),
        })
        self.hop_count += 1
        self.save(update_fields=['chain', 'hop_count', 'updated_at'])
