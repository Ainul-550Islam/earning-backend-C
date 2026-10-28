# engagement/models/campaign.py
"""
Campaign Manager System
Scheduled engagement campaigns targeting specific user segments.
Includes A/B testing and feature flag support.
"""
from django.db import models
from django.conf import settings
from .base import TenantModel, UserEngagementModel


# ── User Segments ─────────────────────────────────────────────────────────────

class UserSegment(TenantModel):
    """A defined group of users for targeting."""
    CRITERIA_CHOICES = [
        ("all",            "All Users"),
        ("new",            "New Users (≤7 days)"),
        ("at_risk",        "At-Risk Users (no checkin 3+ days)"),
        ("high_value",     "High Value (top 10% earners)"),
        ("low_engagement", "Low Engagement"),
        ("premium",        "Battle Pass Premium"),
        ("guild_member",   "Guild Members"),
        ("custom",         "Custom SQL Filter"),
    ]
    name         = models.CharField(max_length=100)
    slug         = models.SlugField(max_length=100, unique=True)
    criteria     = models.CharField(max_length=20, choices=CRITERIA_CHOICES, default="custom")
    description  = models.TextField(blank=True)
    member_count = models.IntegerField(default=0)    # cached, updated by task
    last_synced  = models.DateTimeField(null=True, blank=True)
    is_dynamic   = models.BooleanField(default=True)   # re-evaluate membership daily

    def __str__(self):
        return f"[Segment] {self.name} ({self.member_count} users)"


class SegmentMember(TenantModel):
    """Cached list of users in a segment."""
    segment = models.ForeignKey(UserSegment, on_delete=models.CASCADE, related_name="members")
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["segment", "user"]


# ── Campaign ──────────────────────────────────────────────────────────────────

class Campaign(TenantModel):
    """An engagement campaign (coin bonus, push blast, quest unlock, etc.)."""
    CAMPAIGN_TYPES = [
        ("coin_bonus",     "Coin Bonus Event"),
        ("xp_boost",       "XP Boost Period"),
        ("push_blast",     "Push Notification Blast"),
        ("quest_unlock",   "Special Quest Unlock"),
        ("chest_drop",     "Free Chest Drop"),
        ("referral_boost", "Referral Reward Boost"),
        ("double_spin",    "Double Spin Rewards"),
    ]
    STATUS_CHOICES = [
        ("draft",     "Draft"),
        ("scheduled", "Scheduled"),
        ("running",   "Running"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    name            = models.CharField(max_length=200)
    slug            = models.SlugField(max_length=100, unique=True)
    campaign_type   = models.CharField(max_length=20, choices=CAMPAIGN_TYPES)
    status          = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    target_segment  = models.ForeignKey(UserSegment, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name="campaigns")
    starts_at       = models.DateTimeField()
    ends_at         = models.DateTimeField()
    config          = models.JSONField(default=dict)    # campaign-specific settings
    created_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, related_name="created_campaigns")
    reach_count     = models.IntegerField(default=0)    # how many users received it
    conversion_count = models.IntegerField(default=0)   # how many acted on it

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return f"[{self.campaign_type}] {self.name} ({self.status})"

    @property
    def conversion_rate(self):
        return round(self.conversion_count / self.reach_count * 100, 1) if self.reach_count else 0


class CampaignEvent(TenantModel):
    """Log of a user receiving / converting from a campaign."""
    campaign  = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="events")
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event     = models.CharField(max_length=10, choices=[("reach","Reach"),("convert","Convert")])

    class Meta:
        unique_together = ["campaign", "user", "event"]


# ── Feature Flags & A/B Testing ───────────────────────────────────────────────

class FeatureFlag(TenantModel):
    """A feature flag for gradual rollouts."""
    slug          = models.SlugField(max_length=100, unique=True)
    name          = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    is_enabled    = models.BooleanField(default=False)
    rollout_pct   = models.IntegerField(default=0)     # 0–100: % of users who see it
    allowed_segments = models.ManyToManyField(UserSegment, blank=True)
    config        = models.JSONField(default=dict)     # feature-specific config

    def __str__(self):
        return f"[Flag] {self.slug} {'ON' if self.is_enabled else 'OFF'} ({self.rollout_pct}%)"


class ABTest(TenantModel):
    """An A/B test experiment."""
    STATUS_CHOICES = [("draft","Draft"),("running","Running"),("concluded","Concluded")]
    slug        = models.SlugField(max_length=100, unique=True)
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status      = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    starts_at   = models.DateTimeField(null=True, blank=True)
    ends_at     = models.DateTimeField(null=True, blank=True)
    winner_variant = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"[A/B] {self.name} ({self.status})"


class ABTestVariant(TenantModel):
    """One variant in an A/B test."""
    test          = models.ForeignKey(ABTest, on_delete=models.CASCADE, related_name="variants")
    slug          = models.SlugField(max_length=50)
    name          = models.CharField(max_length=100)
    traffic_pct   = models.IntegerField(default=50)    # % of traffic
    config        = models.JSONField(default=dict)
    participant_count = models.IntegerField(default=0)
    conversion_count  = models.IntegerField(default=0)

    class Meta:
        unique_together = ["test", "slug"]

    @property
    def conversion_rate(self):
        return round(self.conversion_count / self.participant_count * 100, 1) if self.participant_count else 0


class UserABAssignment(TenantModel):
    """Which variant a user is assigned to in a test."""
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    test    = models.ForeignKey(ABTest, on_delete=models.CASCADE)
    variant = models.ForeignKey(ABTestVariant, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["user", "test"]
