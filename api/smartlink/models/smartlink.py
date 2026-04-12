import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ..choices import SmartLinkType, RedirectType, RotationMethod
from ..validators import validate_slug_format, validate_redirect_url

User = get_user_model()


class SmartLinkGroup(models.Model):
    """Folder/campaign grouping for SmartLinks."""
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='smartlink_groups',
        verbose_name=_('Publisher')
    )
    name = models.CharField(max_length=100, verbose_name=_('Group Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    color = models.CharField(max_length=7, default='#6366f1', verbose_name=_('Color'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'smartlink_group'
        verbose_name = _('SmartLink Group')
        verbose_name_plural = _('SmartLink Groups')
        unique_together = [('publisher', 'name')]
        ordering = ['name']

    def __str__(self):
        return f"{self.publisher.username} / {self.name}"


class SmartLinkTag(models.Model):
    """Label/tag for organizing SmartLinks."""
    name = models.CharField(max_length=50, unique=True, verbose_name=_('Tag Name'))
    color = models.CharField(max_length=7, default='#10b981')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'smartlink_tag'
        verbose_name = _('SmartLink Tag')
        ordering = ['name']

    def __str__(self):
        return self.name


class SmartLink(models.Model):
    """
    Core SmartLink model.
    Each SmartLink has a unique slug and routes traffic to offers
    based on targeting rules and rotation configuration.
    """
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='smartlink_smartlinks',
        verbose_name=_('Publisher')
    )
    group = models.ForeignKey(
        SmartLinkGroup, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='smartlink_smartlinks',
        verbose_name=_('Group')
    )
    name = models.CharField(max_length=255, verbose_name=_('Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    slug = models.CharField(
        max_length=32, unique=True,
        validators=[validate_slug_format],
        verbose_name=_('Slug'),
        db_index=True
    )
    type = models.CharField(
        max_length=20,
        choices=SmartLinkType.choices,
        default=SmartLinkType.GENERAL,
        verbose_name=_('Type')
    )
    redirect_type = models.CharField(
        max_length=5,
        choices=RedirectType.choices,
        default=RedirectType.HTTP_302,
        verbose_name=_('Redirect Type')
    )
    rotation_method = models.CharField(
        max_length=20,
        choices=RotationMethod.choices,
        default=RotationMethod.WEIGHTED,
        verbose_name=_('Rotation Method')
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_archived = models.BooleanField(default=False)
    enable_ab_test = models.BooleanField(default=False)
    enable_fraud_filter = models.BooleanField(default=True)
    enable_bot_filter = models.BooleanField(default=True)
    enable_unique_click = models.BooleanField(default=True)
    notes = models.TextField(blank=True, verbose_name=_('Internal Notes'))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_click_at = models.DateTimeField(null=True, blank=True)

    # Counters (denormalized for speed)
    total_clicks = models.PositiveBigIntegerField(default=0)
    total_unique_clicks = models.PositiveBigIntegerField(default=0)
    total_conversions = models.PositiveBigIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        db_table = 'smartlink'
        verbose_name = _('SmartLink')
        verbose_name_plural = _('SmartLinks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug'], name='sl_slug_idx'),
            models.Index(fields=['publisher', 'is_active'], name='sl_pub_active_idx'),
            models.Index(fields=['created_at'], name='sl_created_idx'),
        ]

    def __str__(self):
        return f"[{self.slug}] {self.name}"

    @property
    def full_url(self):
        from django.conf import settings
        base = getattr(settings, 'SMARTLINK_BASE_URL', 'https://go.example.com')
        return f"{base}/{self.slug}/"

    def increment_clicks(self, unique: bool = False):
        """Thread-safe click counter increment."""
        from django.db.models import F
        SmartLink.objects.filter(pk=self.pk).update(
            total_clicks=F('total_clicks') + 1,
            **(dict(total_unique_clicks=F('total_unique_clicks') + 1) if unique else {})
        )


class SmartLinkDomain(models.Model):
    """Custom domain per publisher (e.g., go.mysite.com)."""
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='smartlink_domains',
    )
    domain = models.CharField(max_length=253, unique=True, verbose_name=_('Domain'))
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'smartlink_domain'
        verbose_name = _('SmartLink Domain')

    def __str__(self):
        return f"{self.domain} ({'verified' if self.is_verified else 'unverified'})"


class SmartLinkTagging(models.Model):
    """M2M relationship between SmartLink and Tag."""
    smartlink = models.ForeignKey(SmartLink, on_delete=models.CASCADE, related_name='taggings')
    tag = models.ForeignKey(SmartLinkTag, on_delete=models.CASCADE, related_name='taggings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'smartlink_tagging'
        unique_together = [('smartlink', 'tag')]
        verbose_name = _('SmartLink Tagging')


# Add M2M through SmartLinkTagging
SmartLink.add_to_class(
    'tags',
    models.ManyToManyField(SmartLinkTag, through=SmartLinkTagging, related_name='smartlink_smartlinks', blank=True)
)


class SmartLinkRotation(models.Model):
    """Weight-based offer rotation configuration for a SmartLink."""
    smartlink = models.OneToOneField(
        SmartLink, on_delete=models.CASCADE,
        related_name='rotation_config',
    )
    method = models.CharField(
        max_length=20,
        choices=RotationMethod.choices,
        default=RotationMethod.WEIGHTED
    )
    auto_optimize_epc = models.BooleanField(
        default=False,
        help_text=_('Automatically shift weight to higher-EPC offers.')
    )
    optimization_interval_minutes = models.PositiveSmallIntegerField(default=30)
    epc_min_clicks = models.PositiveSmallIntegerField(
        default=10,
        help_text=_('Minimum clicks before offer is included in EPC optimization.')
    )
    last_optimized_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'smartlink_rotation'
        verbose_name = _('SmartLink Rotation Config')

    def __str__(self):
        return f"Rotation: {self.smartlink.slug} ({self.method})"


class SmartLinkFallback(models.Model):
    """Fallback URL when no offer matches targeting rules."""
    smartlink = models.OneToOneField(
        SmartLink, on_delete=models.CASCADE,
        related_name='fallback',
    )
    url = models.URLField(
        max_length=2048,
        validators=[validate_redirect_url],
        verbose_name=_('Fallback URL')
    )
    reason = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'smartlink_fallback'
        verbose_name = _('SmartLink Fallback')

    def __str__(self):
        return f"Fallback: {self.smartlink.slug} → {self.url[:50]}"


class SmartLinkVersion(models.Model):
    """
    A/B test variant version of a SmartLink.
    Multiple versions can be active simultaneously with split traffic.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='versions',
    )
    name = models.CharField(max_length=100, verbose_name=_('Version Name'))
    description = models.TextField(blank=True)
    traffic_split = models.PositiveSmallIntegerField(
        default=50,
        help_text=_('Percentage of traffic for this variant (0-100).')
    )
    is_control = models.BooleanField(default=False, help_text=_('Is this the control variant?'))
    is_active = models.BooleanField(default=True)
    is_winner = models.BooleanField(default=False)
    clicks = models.PositiveBigIntegerField(default=0)
    conversions = models.PositiveBigIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'smartlink_version'
        verbose_name = _('SmartLink Version (A/B)')
        ordering = ['-is_control', 'name']

    def __str__(self):
        return f"{self.smartlink.slug} — {self.name} ({self.traffic_split}%)"

    @property
    def conversion_rate(self):
        if self.clicks == 0:
            return 0.0
        return round(self.conversions / self.clicks * 100, 2)

    @property
    def epc(self):
        if self.clicks == 0:
            return 0.0
        return round(float(self.revenue) / self.clicks, 4)
