from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/models/popup.py
"""
Popup models: Popup, PopupRule, PopupStat, PopupABTest
Full production-ready with trigger rules, A/B testing, and analytics.
"""
import uuid
import logging
from decimal import Decimal
from django.db import models, transaction
from django.db.models import F, Q, Sum, Avg, Count
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
# Popup
# ─────────────────────────────────────────────

class Popup(TimeStampedModel):
    """
    Popup/modal/toast/banner management.
    Supports modal, toast, banner, slide-in types.
    """
    POPUP_TYPES = [
        ('modal', _('Modal Dialog')),
        ('toast', _('Toast Notification')),
        ('banner', _('Top/Bottom Banner')),
        ('slide_in', _('Slide-in Panel')),
        ('fullscreen', _('Fullscreen Overlay')),
    ]

    POSITION_CHOICES = [
        ('center', _('Center')),
        ('top', _('Top')),
        ('bottom', _('Bottom')),
        ('top_left', _('Top Left')),
        ('top_right', _('Top Right')),
        ('bottom_left', _('Bottom Left')),
        ('bottom_right', _('Bottom Right')),
    ]

    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('paused', _('Paused')),
        ('archived', _('Archived')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Name"), max_length=200)
    popup_type = models.CharField(
        _("Popup Type"), max_length=20,
        choices=POPUP_TYPES, default='modal',
        db_index=True
    )
    status = models.CharField(
        _("Status"), max_length=20,
        choices=STATUS_CHOICES, default='draft',
        db_index=True
    )
    position = models.CharField(
        _("Position"), max_length=20,
        choices=POSITION_CHOICES, default='center'
    )

    # Content
    title = models.CharField(_("Title"), max_length=300)
    body = models.TextField(_("Body"))
    cta_text = models.CharField(
        _("CTA Button Text"), max_length=100, blank=True
    )
    cta_url = models.URLField(_("CTA URL"), blank=True)
    cta_secondary_text = models.CharField(
        _("Secondary CTA Text"), max_length=100, blank=True
    )
    cta_secondary_url = models.URLField(_("Secondary CTA URL"), blank=True)
    image = ProcessedImageField(
        upload_to='popups/%Y/%m/',
        processors=[SmartResize(800, 600)],
        format='WEBP',
        options={'quality': 90},
        blank=True, null=True,
        verbose_name=_("Popup Image")
    )
    background_color = models.CharField(
        _("Background Color"), max_length=20, default='#ffffff', blank=True
    )
    text_color = models.CharField(
        _("Text Color"), max_length=20, default='#000000', blank=True
    )
    custom_css = models.TextField(_("Custom CSS"), blank=True)
    custom_html = models.TextField(
        _("Custom HTML"), blank=True,
        help_text=_("Override body with custom HTML")
    )

    # Scheduling
    start_date = models.DateTimeField(_("Start Date"), null=True, blank=True)
    end_date = models.DateTimeField(_("End Date"), null=True, blank=True)

    # Targeting
    is_active = models.BooleanField(_("Active"), default=True)
    target_pages = models.JSONField(
        _("Target Pages"), default=default_list, blank=True,
        help_text=_("List of page URLs or patterns to show popup on")
    )
    exclude_pages = models.JSONField(
        _("Exclude Pages"), default=default_list, blank=True
    )
    target_audience = models.JSONField(
        _("Target Audience"), default=default_dict, blank=True,
        help_text=_("Audience targeting rules JSON")
    )
    show_to_logged_in = models.BooleanField(_("Show to Logged In"), default=True)
    show_to_anonymous = models.BooleanField(_("Show to Anonymous"), default=True)
    min_user_level = models.IntegerField(_("Min User Level"), default=0)

    # Display settings
    animation = models.CharField(
        _("Animation"), max_length=50, blank=True, default='fadeIn',
        help_text=_("CSS animation name, e.g. fadeIn, slideUp")
    )
    overlay = models.BooleanField(_("Show Overlay"), default=True)
    close_on_overlay = models.BooleanField(_("Close on Overlay Click"), default=True)
    show_close_button = models.BooleanField(_("Show Close Button"), default=True)
    auto_close_seconds = models.IntegerField(
        _("Auto Close (seconds)"), default=0,
        help_text=_("0 = no auto close")
    )
    delay_seconds = models.IntegerField(
        _("Delay (seconds)"), default=0
    )
    cookie_days = models.IntegerField(
        _("Cookie Duration (days)"), default=7,
        help_text=_("Don't show again for N days after dismissal")
    )
    max_shows_per_user = models.IntegerField(
        _("Max Shows Per User"), default=3,
        help_text=_("0 = unlimited")
    )

    # Stats
    total_views = models.PositiveIntegerField(_("Total Views"), default=0)
    total_clicks = models.PositiveIntegerField(_("Total Clicks"), default=0)
    total_dismissals = models.PositiveIntegerField(_("Total Dismissals"), default=0)
    total_conversions = models.PositiveIntegerField(_("Total Conversions"), default=0)

    # Priority
    priority = models.IntegerField(_("Priority"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Popup")
        verbose_name_plural = _("Popups")
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['popup_type', 'status', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['uuid', 'is_active']),
            models.Index(fields=['priority', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_popup_type_display()})"

    def clean(self):
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError(_("End date must be after start date."))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(f'popup_{self.uuid}')
        cache.delete('active_popups')

    def is_active_now(self):
        """Check if popup should be shown right now."""
        if not self.is_active or self.status != 'active':
            return False
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    def record_view(self):
        Popup.objects.filter(id=self.id).update(total_views=F('total_views') + 1)
        self.refresh_from_db()

    def record_click(self):
        Popup.objects.filter(id=self.id).update(total_clicks=F('total_clicks') + 1)
        self.refresh_from_db()

    def record_dismissal(self):
        Popup.objects.filter(id=self.id).update(total_dismissals=F('total_dismissals') + 1)
        self.refresh_from_db()

    def record_conversion(self):
        Popup.objects.filter(id=self.id).update(total_conversions=F('total_conversions') + 1)
        self.refresh_from_db()

    @property
    def click_through_rate(self):
        if self.total_views == 0:
            return 0.0
        return round((self.total_clicks / self.total_views) * 100, 2)

    @property
    def conversion_rate(self):
        if self.total_clicks == 0:
            return 0.0
        return round((self.total_conversions / self.total_clicks) * 100, 2)

    @property
    def dismissal_rate(self):
        if self.total_views == 0:
            return 0.0
        return round((self.total_dismissals / self.total_views) * 100, 2)


# ─────────────────────────────────────────────
# PopupRule
# ─────────────────────────────────────────────

class PopupRule(TimeStampedModel):
    """
    Trigger rules for popups.
    Determines WHEN and WHERE a popup appears.
    """
    TRIGGER_TYPES = [
        ('on_page_load', _('On Page Load')),
        ('on_page', _('On Specific Page')),
        ('after_seconds', _('After N Seconds')),
        ('on_exit', _('On Exit Intent')),
        ('on_scroll', _('On Scroll Depth')),
        ('on_click', _('On Element Click')),
        ('on_inactivity', _('On Inactivity')),
        ('on_second_visit', _('On Second Visit')),
        ('after_n_pages', _('After N Pages Viewed')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    popup = models.ForeignKey(
        Popup, on_delete=models.CASCADE,
        related_name='rules',
        verbose_name=_("Popup")
    )
    trigger_type = models.CharField(
        _("Trigger Type"), max_length=30,
        choices=TRIGGER_TYPES, default='on_page_load'
    )
    conditions = models.JSONField(
        _("Conditions"), default=default_dict, blank=True,
        help_text=_("Additional conditions JSON, e.g. {delay_seconds: 5, scroll_depth: 50}")
    )
    is_active = models.BooleanField(_("Active"), default=True)
    priority = models.IntegerField(_("Priority"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Popup Rule")
        verbose_name_plural = _("Popup Rules")
        ordering = ['-priority', 'trigger_type']
        indexes = [
            models.Index(fields=['popup', 'is_active']),
            models.Index(fields=['trigger_type']),
        ]

    def __str__(self):
        return f"{self.popup.name} - {self.get_trigger_type_display()}"

    def get_condition(self, key, default=None):
        """Safely get a condition value."""
        return self.conditions.get(key, default)

    def evaluate(self, context):
        """
        Evaluate if this rule should trigger.
        context: dict with page_url, scroll_depth, seconds_on_page, etc.
        """
        try:
            if self.trigger_type == 'after_seconds':
                delay = self.get_condition('delay_seconds', 0)
                return context.get('seconds_on_page', 0) >= delay

            elif self.trigger_type == 'on_scroll':
                depth = self.get_condition('scroll_depth', 50)
                return context.get('scroll_depth', 0) >= depth

            elif self.trigger_type == 'on_page':
                target_url = self.get_condition('page_url', '')
                current_url = context.get('page_url', '')
                return target_url in current_url

            elif self.trigger_type == 'after_n_pages':
                n = self.get_condition('page_count', 2)
                return context.get('pages_viewed', 0) >= n

            elif self.trigger_type in ('on_page_load', 'on_exit', 'on_click', 'on_inactivity', 'on_second_visit'):
                return True  # Client-side triggers

            return False
        except Exception as e:
            logger.error(f"Error evaluating popup rule {self.id}: {e}")
            return False


# ─────────────────────────────────────────────
# PopupStat
# ─────────────────────────────────────────────

class PopupStat(TimeStampedModel):
    """Daily statistics for popups."""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    popup = models.ForeignKey(
        Popup, on_delete=models.CASCADE,
        related_name='stats',
        verbose_name=_("Popup")
    )
    date = models.DateField(_("Date"), db_index=True)
    views = models.PositiveIntegerField(_("Views"), default=0)
    clicks = models.PositiveIntegerField(_("Clicks"), default=0)
    dismissals = models.PositiveIntegerField(_("Dismissals"), default=0)
    conversions = models.PositiveIntegerField(_("Conversions"), default=0)
    unique_users = models.PositiveIntegerField(_("Unique Users"), default=0)
    conversion_rate = models.FloatField(_("Conversion Rate"), default=0.0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Popup Stat")
        verbose_name_plural = _("Popup Stats")
        unique_together = [['popup', 'date']]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['popup', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.popup.name} - {self.date}"

    def save(self, *args, **kwargs):
        # Calculate conversion rate
        if self.clicks > 0:
            self.conversion_rate = round((self.conversions / self.clicks) * 100, 2)
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_today(cls, popup):
        """Get or create today's stat for popup."""
        today = timezone.now().date()
        obj, _ = cls.objects.get_or_create(
            popup=popup, date=today,
            defaults={'views': 0, 'clicks': 0, 'dismissals': 0, 'conversions': 0}
        )
        return obj

    @classmethod
    def record_view(cls, popup):
        today = timezone.now().date()
        cls.objects.update_or_create(
            popup=popup, date=today,
            defaults={'views': F('views') + 1}
        )

    @classmethod
    def record_click(cls, popup):
        today = timezone.now().date()
        cls.objects.update_or_create(
            popup=popup, date=today,
            defaults={'clicks': F('clicks') + 1}
        )

    @classmethod
    def record_dismissal(cls, popup):
        today = timezone.now().date()
        cls.objects.update_or_create(
            popup=popup, date=today,
            defaults={'dismissals': F('dismissals') + 1}
        )

    @classmethod
    def get_period_stats(cls, popup, days=30):
        """Get aggregated stats for last N days."""
        from datetime import timedelta
        start = timezone.now().date() - timedelta(days=days)
        return cls.objects.filter(
            popup=popup, date__gte=start
        ).aggregate(
            total_views=Sum('views'),
            total_clicks=Sum('clicks'),
            total_dismissals=Sum('dismissals'),
            total_conversions=Sum('conversions'),
            avg_conversion_rate=Avg('conversion_rate'),
        )


# ─────────────────────────────────────────────
# PopupABTest
# ─────────────────────────────────────────────

class PopupABTest(TimeStampedModel):
    """A/B testing for popups."""
    STATUS_CHOICES = [
        ('running', _('Running')),
        ('paused', _('Paused')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    popup = models.ForeignKey(
        Popup, on_delete=models.CASCADE,
        related_name='ab_tests',
        verbose_name=_("Popup")
    )
    name = models.CharField(_("Test Name"), max_length=200)
    status = models.CharField(
        _("Status"), max_length=20,
        choices=STATUS_CHOICES, default='running',
        db_index=True
    )

    # Variant A (original)
    variant_a = models.TextField(
        _("Variant A Content"),
        help_text=_("JSON or HTML content for variant A")
    )
    variant_a_name = models.CharField(_("Variant A Name"), max_length=100, default='Control')

    # Variant B (challenger)
    variant_b = models.TextField(
        _("Variant B Content"),
        help_text=_("JSON or HTML content for variant B")
    )
    variant_b_name = models.CharField(_("Variant B Name"), max_length=100, default='Variant')

    # Split settings
    split_pct = models.FloatField(
        _("Split Percentage (A%)"),
        default=50.0,
        help_text=_("Percentage of traffic to show variant A (0-100)")
    )

    # Results
    winner = models.CharField(
        _("Winner"), max_length=10,
        choices=[('A', 'Variant A'), ('B', 'Variant B'), ('tie', 'Tie')],
        blank=True
    )
    winner_determined_at = models.DateTimeField(
        _("Winner Determined At"), null=True, blank=True
    )
    ended_at = models.DateTimeField(_("Ended At"), null=True, blank=True)

    # Metrics
    variant_a_views = models.PositiveIntegerField(_("Variant A Views"), default=0)
    variant_a_conversions = models.PositiveIntegerField(_("Variant A Conversions"), default=0)
    variant_b_views = models.PositiveIntegerField(_("Variant B Views"), default=0)
    variant_b_conversions = models.PositiveIntegerField(_("Variant B Conversions"), default=0)

    # Minimum sample size before determining winner
    min_sample_size = models.IntegerField(_("Min Sample Size"), default=100)
    confidence_level = models.FloatField(_("Confidence Level"), default=95.0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Popup A/B Test")
        verbose_name_plural = _("Popup A/B Tests")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['popup', 'status']),
            models.Index(fields=['status', 'ended_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def clean(self):
        if not 0 < self.split_pct < 100:
            raise ValidationError(_("Split percentage must be between 0 and 100 (exclusive)."))

    @property
    def variant_a_conversion_rate(self):
        if self.variant_a_views == 0:
            return 0.0
        return round((self.variant_a_conversions / self.variant_a_views) * 100, 2)

    @property
    def variant_b_conversion_rate(self):
        if self.variant_b_views == 0:
            return 0.0
        return round((self.variant_b_conversions / self.variant_b_views) * 100, 2)

    @property
    def has_sufficient_data(self):
        return (
            self.variant_a_views >= self.min_sample_size and
            self.variant_b_views >= self.min_sample_size
        )

    def determine_winner(self):
        """Determine winner based on conversion rates."""
        if not self.has_sufficient_data:
            return None
        rate_a = self.variant_a_conversion_rate
        rate_b = self.variant_b_conversion_rate
        if abs(rate_a - rate_b) < 0.5:
            winner = 'tie'
        elif rate_a > rate_b:
            winner = 'A'
        else:
            winner = 'B'
        self.winner = winner
        self.winner_determined_at = timezone.now()
        self.save(update_fields=['winner', 'winner_determined_at'])
        return winner

    def end_test(self, winner=None):
        """End the A/B test."""
        if winner:
            self.winner = winner
        elif not self.winner:
            self.determine_winner()
        self.status = 'completed'
        self.ended_at = timezone.now()
        self.save()

    def get_variant_for_user(self, user_id):
        """Determine which variant to show to a user."""
        import hashlib
        # Consistent hashing: same user always sees same variant
        h = int(hashlib.md5(f"{self.id}:{user_id}".encode()).hexdigest(), 16)
        threshold = int(self.split_pct)
        return 'A' if (h % 100) < threshold else 'B'

    def record_variant_view(self, variant):
        if variant == 'A':
            PopupABTest.objects.filter(id=self.id).update(
                variant_a_views=F('variant_a_views') + 1
            )
        elif variant == 'B':
            PopupABTest.objects.filter(id=self.id).update(
                variant_b_views=F('variant_b_views') + 1
            )

    def record_variant_conversion(self, variant):
        if variant == 'A':
            PopupABTest.objects.filter(id=self.id).update(
                variant_a_conversions=F('variant_a_conversions') + 1
            )
        elif variant == 'B':
            PopupABTest.objects.filter(id=self.id).update(
                variant_b_conversions=F('variant_b_conversions') + 1
            )
