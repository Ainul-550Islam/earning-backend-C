# earning_backend/api/notifications/models/campaign.py
"""
Campaign management models:
  - NotificationCampaign  — high-level campaign (extends core model)
  - CampaignSegment       — user-targeting segment for a campaign
  - CampaignABTest        — A/B test configuration on a campaign
  - CampaignResult        — aggregated campaign performance results
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ---------------------------------------------------------------------------
# CampaignSegment
# (Defined before NotificationCampaign because Campaign has FK → Segment)
# ---------------------------------------------------------------------------

class CampaignSegment(models.Model):
    """
    Defines the target audience for a campaign.
    The 'conditions' JSON field stores flexible filter criteria evaluated by
    SegmentService to build the actual queryset of User objects.
    """

    SEGMENT_TYPE_CHOICES = (
        ('all', 'All Users'),
        ('tier', 'By Membership Tier'),
        ('geo', 'By Geography'),
        ('inactive', 'Inactive Users'),
        ('new', 'New Users (< 30 days)'),
        ('high_value', 'High-Value Users'),
        ('custom', 'Custom Conditions'),
    )

    campaign = models.ForeignKey(
        'notifications.NotificationCampaign',
        on_delete=models.CASCADE,
        related_name='segments',
        null=True,
        blank=True,
        help_text='Leave null to use the segment across multiple campaigns',
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    segment_type = models.CharField(
        max_length=20,
        choices=SEGMENT_TYPE_CHOICES,
        default='all',
    )

    # Flexible filter conditions evaluated by SegmentService
    # Example: {"tier": "gold", "country": "BD", "min_balance": 100}
    conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text='Arbitrary filter conditions evaluated by SegmentService',
    )

    # Cached user count from last evaluation (updated after each segment build)
    estimated_size = models.PositiveIntegerField(
        default=0,
        help_text='Estimated number of users matching this segment',
    )
    last_evaluated_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_segments',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Campaign Segment'
        verbose_name_plural = 'Campaign Segments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['segment_type']),
            models.Index(fields=['campaign']),
        ]

    def __str__(self):
        return f"Segment '{self.name}' ({self.segment_type}, ~{self.estimated_size} users)"

    def update_estimated_size(self, size: int, save=True):
        """Cache the evaluated user count."""
        self.estimated_size = size
        self.last_evaluated_at = timezone.now()
        if save:
            self.save(update_fields=['estimated_size', 'last_evaluated_at', 'updated_at'])


# ---------------------------------------------------------------------------
# NotificationCampaign (new, separate from the core model in models.py)
# ---------------------------------------------------------------------------

class NotificationCampaign(models.Model):
    """
    A marketing / engagement campaign that sends a template to a segment.

    NOTE: The original monolithic models.py also has a NotificationCampaign
    class. This module provides the *new* split version with additional
    fields. During migration, the original table will be kept as-is and
    this one will have a distinct app_label table name via Meta.
    """

    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    template = models.ForeignKey(
        'notifications.NotificationTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='new_campaigns',
    )

    # Primary segment (optional — segments can also be linked via
    # the CampaignSegment.campaign FK for multi-segment campaigns)
    segment = models.ForeignKey(
        CampaignSegment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_campaigns',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
    )

    # Scheduling
    send_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='UTC time to start sending. Null = send immediately on launch.',
    )

    # Progress
    total_users = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)

    # Template context variables common to all notifications in the campaign
    context = models.JSONField(default=dict, blank=True)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='new_created_campaigns',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Notification Campaign (New)'
        verbose_name_plural = 'Notification Campaigns (New)'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['send_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Campaign '{self.name}' [{self.status}]"

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def can_start(self):
        return self.status in ('draft', 'scheduled', 'paused')

    def start(self, save=True):
        if not self.can_start():
            return False
        self.status = 'running'
        self.started_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'started_at', 'updated_at'])
        return True

    def pause(self, save=True):
        if self.status == 'running':
            self.status = 'paused'
            if save:
                self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    def complete(self, save=True):
        self.status = 'completed'
        self.completed_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def cancel(self, save=True):
        if self.status not in ('completed', 'cancelled'):
            self.status = 'cancelled'
            if save:
                self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    # ------------------------------------------------------------------
    # Progress helpers
    # ------------------------------------------------------------------

    @property
    def progress_pct(self):
        if self.total_users == 0:
            return 0
        return round((self.sent_count + self.failed_count) / self.total_users * 100, 2)

    def increment_sent(self, count=1, save=True):
        self.sent_count += count
        if save:
            self.save(update_fields=['sent_count', 'updated_at'])

    def increment_failed(self, count=1, save=True):
        self.failed_count += count
        if save:
            self.save(update_fields=['failed_count', 'updated_at'])


# ---------------------------------------------------------------------------
# CampaignABTest
# ---------------------------------------------------------------------------

class CampaignABTest(models.Model):
    """
    A/B test configuration attached to a campaign.
    Two notification templates (variant A and variant B) are tested against
    each other. The split_pct field controls what percentage of users receive
    variant A (the rest receive variant B).
    """

    WINNER_CHOICES = (
        ('none', 'No Winner Yet'),
        ('a', 'Variant A'),
        ('b', 'Variant B'),
        ('tie', 'Tie'),
    )

    METRIC_CHOICES = (
        ('open_rate', 'Open Rate'),
        ('click_rate', 'Click-Through Rate'),
        ('conversion_rate', 'Conversion Rate'),
        ('delivery_rate', 'Delivery Rate'),
    )

    campaign = models.OneToOneField(
        NotificationCampaign,
        on_delete=models.CASCADE,
        related_name='ab_test',
    )

    # Variant templates
    variant_a = models.ForeignKey(
        'notifications.NotificationTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ab_test_variant_a',
    )
    variant_b = models.ForeignKey(
        'notifications.NotificationTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ab_test_variant_b',
    )

    # Percentage of users who receive variant A (0–100)
    split_pct = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        help_text='Percentage of users who receive variant A',
    )

    # Winning metric used to determine the winner
    winning_metric = models.CharField(
        max_length=20,
        choices=METRIC_CHOICES,
        default='open_rate',
    )

    winner = models.CharField(
        max_length=10,
        choices=WINNER_CHOICES,
        default='none',
    )

    # Results snapshot
    variant_a_stats = models.JSONField(default=dict, blank=True)
    variant_b_stats = models.JSONField(default=dict, blank=True)

    winner_declared_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Campaign A/B Test'
        verbose_name_plural = 'Campaign A/B Tests'
        ordering = ['-created_at']

    def __str__(self):
        return f"A/B Test for '{self.campaign.name}' — winner: {self.winner}"

    def declare_winner(self, winner: str, save=True):
        """
        Set the winner. winner must be one of: 'a', 'b', 'tie'.
        """
        if winner not in ('a', 'b', 'tie'):
            raise ValueError("winner must be 'a', 'b', or 'tie'")
        self.winner = winner
        self.winner_declared_at = timezone.now()
        self.is_active = False
        if save:
            self.save(update_fields=['winner', 'winner_declared_at', 'is_active', 'updated_at'])

    def update_stats(self, variant: str, stats: dict, save=True):
        """
        Update the stats snapshot for a variant.
        variant must be 'a' or 'b'.
        """
        if variant == 'a':
            self.variant_a_stats = stats
            fields = ['variant_a_stats', 'updated_at']
        elif variant == 'b':
            self.variant_b_stats = stats
            fields = ['variant_b_stats', 'updated_at']
        else:
            raise ValueError("variant must be 'a' or 'b'")
        if save:
            self.save(update_fields=fields)


# ---------------------------------------------------------------------------
# CampaignResult
# ---------------------------------------------------------------------------

class CampaignResult(models.Model):
    """
    Aggregated performance results for a completed (or running) campaign.
    Updated periodically by DeliveryTracker / insight tasks.
    """

    campaign = models.OneToOneField(
        NotificationCampaign,
        on_delete=models.CASCADE,
        related_name='result',
    )

    # Volume
    sent = models.PositiveIntegerField(default=0)
    delivered = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)

    # Engagement
    opened = models.PositiveIntegerField(default=0)
    clicked = models.PositiveIntegerField(default=0)
    converted = models.PositiveIntegerField(default=0)

    # Opt-outs triggered by this campaign
    unsubscribed = models.PositiveIntegerField(default=0)

    # Derived rates (stored for fast dashboard reads)
    delivery_rate = models.FloatField(default=0.0)
    open_rate = models.FloatField(default=0.0)
    click_rate = models.FloatField(default=0.0)
    conversion_rate = models.FloatField(default=0.0)

    # Cost tracking
    total_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    cost_currency = models.CharField(max_length=10, default='USD')

    # Timestamps
    calculated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Campaign Result'
        verbose_name_plural = 'Campaign Results'

    def __str__(self):
        return f"Results for '{self.campaign.name}'"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def recalculate_rates(self, save=True):
        """Recompute percentage fields from raw counts."""
        base = self.sent or 0
        if base > 0:
            self.delivery_rate = round(self.delivered / base * 100, 2)
            self.open_rate = round(self.opened / base * 100, 2)
            self.click_rate = round(self.clicked / base * 100, 2)
            self.conversion_rate = round(self.converted / base * 100, 2)
        else:
            self.delivery_rate = 0.0
            self.open_rate = 0.0
            self.click_rate = 0.0
            self.conversion_rate = 0.0
        if save:
            self.save(update_fields=[
                'delivery_rate', 'open_rate', 'click_rate',
                'conversion_rate', 'calculated_at',
            ])

    def to_dict(self):
        return {
            'campaign_id': self.campaign_id,
            'sent': self.sent,
            'delivered': self.delivered,
            'failed': self.failed,
            'opened': self.opened,
            'clicked': self.clicked,
            'converted': self.converted,
            'unsubscribed': self.unsubscribed,
            'delivery_rate': self.delivery_rate,
            'open_rate': self.open_rate,
            'click_rate': self.click_rate,
            'conversion_rate': self.conversion_rate,
            'total_cost': float(self.total_cost),
            'cost_currency': self.cost_currency,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None,
        }
