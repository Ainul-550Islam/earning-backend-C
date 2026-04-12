from django.conf import settings
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from .smartlink import SmartLink
from ..choices import DeviceType, OSType, BrowserType


class ClickSession(models.Model):
    """
    Session tracking across multiple clicks from the same user.
    Identified by a session UUID stored in cookie or URL param.
    """
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='sessions',
    )
    ip = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    country = models.CharField(max_length=2, blank=True)
    device_type = models.CharField(max_length=10, choices=DeviceType.choices, blank=True)
    click_count = models.PositiveSmallIntegerField(default=0)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_click_session'
        verbose_name = _('Click Session')
        indexes = [
            models.Index(fields=['session_id'], name='session_id_idx'),
            models.Index(fields=['ip', 'smartlink'], name='session_ip_sl_idx'),
        ]

    def __str__(self):
        return f"Session: {self.session_id} | {self.smartlink.slug}"


class Click(models.Model):
    """
    Core click tracking model.
    Every visit to a SmartLink redirect URL creates a Click record.
    High-volume table — archived periodically via management command.
    """
    id = models.BigAutoField(primary_key=True)
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='clicks',
        db_index=True,
    )
    offer = models.ForeignKey(
        'offer_inventory.Offer', on_delete=models.SET_NULL,
        null=True, related_name='smartlink_clicks',
    )
    session = models.ForeignKey(
        ClickSession, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='clicks',
    )
    # Geo
    ip = models.GenericIPAddressField(db_index=True)
    country = models.CharField(max_length=2, blank=True, db_index=True)
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    # Device
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=10, choices=DeviceType.choices, blank=True, db_index=True)
    os = models.CharField(max_length=10, choices=OSType.choices, blank=True)
    browser = models.CharField(max_length=10, choices=BrowserType.choices, blank=True)
    # Status flags
    is_unique = models.BooleanField(default=False, db_index=True)
    is_fraud = models.BooleanField(default=False, db_index=True)
    is_bot = models.BooleanField(default=False, db_index=True)
    is_converted = models.BooleanField(default=False)
    fraud_score = models.PositiveSmallIntegerField(default=0)
    # Revenue
    payout = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    # Referrer
    referrer = models.URLField(max_length=2048, blank=True)
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'sl_click'
        verbose_name = _('Click')
        verbose_name_plural = _('Clicks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['smartlink', 'created_at'], name='click_sl_ts_idx'),
            models.Index(fields=['offer', 'created_at'], name='click_offer_ts_idx'),
            models.Index(fields=['ip', 'created_at'], name='click_ip_ts_idx'),
            models.Index(fields=['country', 'device_type'], name='click_geo_device_idx'),
            models.Index(fields=['is_unique', 'is_fraud', 'is_bot'], name='click_flags_idx'),
        ]

    def __str__(self):
        return f"Click#{self.pk}: {self.smartlink.slug} | {self.country}/{self.device_type} @ {self.created_at}"


class ClickMetadata(models.Model):
    """
    Sub-ID parameters (sub1-sub5) and custom tracking params.
    Stored separately to keep Click table lean.
    """
    click = models.OneToOneField(
        Click, on_delete=models.CASCADE,
        related_name='metadata',
    )
    sub1 = models.CharField(max_length=255, blank=True, db_index=True)
    sub2 = models.CharField(max_length=255, blank=True)
    sub3 = models.CharField(max_length=255, blank=True)
    sub4 = models.CharField(max_length=255, blank=True)
    sub5 = models.CharField(max_length=255, blank=True)
    custom_params = models.JSONField(default=dict, blank=True)
    referrer = models.URLField(max_length=2048, blank=True)
    landing_page_url = models.URLField(max_length=2048, blank=True)
    offer_url_final = models.URLField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sl_click_metadata'
        verbose_name = _('Click Metadata')
        indexes = [
            models.Index(fields=['sub1'], name='meta_sub1_idx'),
        ]

    def __str__(self):
        return f"Metadata: Click#{self.click_id} sub1={self.sub1}"


class UniqueClick(models.Model):
    """
    Deduplication record: IP + offer + day.
    If a record exists, the click is a duplicate.
    """
    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    smartlink = models.ForeignKey(SmartLink, on_delete=models.CASCADE, related_name='unique_clicks')
    offer = models.ForeignKey('offer_inventory.Offer', on_delete=models.CASCADE, related_name='unique_clicks')
    ip = models.GenericIPAddressField()
    date = models.DateField(db_index=True)
    first_click = models.ForeignKey(Click, on_delete=models.SET_NULL, null=True, related_name='+')
    click_count = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sl_unique_click'
        verbose_name = _('Unique Click')
        indexes = [
            models.Index(fields=['date', 'smartlink'], name='unique_date_sl_idx'),
        ]

    def __str__(self):
        return f"UniqueClick: {self.fingerprint[:16]}... × {self.click_count}"


class ClickFraudFlag(models.Model):
    """
    Fraud detection flag for a click.
    Contains fraud score, reason, and action taken.
    """
    click = models.OneToOneField(
        Click, on_delete=models.CASCADE,
        related_name='fraud_flag',
    )
    score = models.PositiveSmallIntegerField(default=0, help_text=_('0-100 fraud probability score.'))
    signals = models.JSONField(
        default=list,
        help_text=_('List of fraud signal types detected.')
    )
    action_taken = models.CharField(max_length=20, help_text=_('allow/block/flag'))
    is_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_fraud_flags',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sl_click_fraud_flag'
        verbose_name = _('Click Fraud Flag')
        indexes = [
            models.Index(fields=['score', 'action_taken'], name='fraud_score_action_idx'),
            models.Index(fields=['is_reviewed'], name='fraud_reviewed_idx'),
        ]

    def __str__(self):
        return f"Fraud#{self.click_id}: score={self.score} action={self.action_taken}"


class ClickHeatmap(models.Model):
    """
    Geo heatmap data per SmartLink.
    Aggregated click count per country per day.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='heatmap_data',
    )
    country = models.CharField(max_length=2)
    date = models.DateField(db_index=True)
    click_count = models.PositiveIntegerField(default=0)
    unique_click_count = models.PositiveIntegerField(default=0)
    conversion_count = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    epc = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_click_heatmap'
        verbose_name = _('Click Heatmap')
        unique_together = [('smartlink', 'country', 'date')]
        indexes = [
            models.Index(fields=['date', 'country'], name='heatmap_date_country_idx'),
        ]

    def __str__(self):
        return f"Heatmap: {self.smartlink.slug} | {self.country} {self.date}"


class BotClick(models.Model):
    """
    Detected bot/crawler click records.
    Stored separately from Click for reporting purposes.
    """
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='bot_clicks',
    )
    ip = models.GenericIPAddressField()
    user_agent = models.TextField()
    bot_type = models.CharField(max_length=50, blank=True, help_text=_('Googlebot, SEMrush, etc.'))
    detection_method = models.CharField(max_length=30, help_text=_('ua_pattern, ip_list, behavior'))
    country = models.CharField(max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'sl_bot_click'
        verbose_name = _('Bot Click')
        ordering = ['-created_at']

    def __str__(self):
        return f"Bot: {self.bot_type or 'unknown'} | {self.ip} → {self.smartlink.slug}"
