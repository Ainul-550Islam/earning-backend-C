# engagement/models/analytics.py
"""
Engagement Analytics System
Tracks every meaningful user action for funnel analysis,
retention cohorts, revenue attribution, and ML feature extraction.
"""
from django.db import models
from django.conf import settings
from .base import TenantModel


class EngagementEvent(TenantModel):
    """
    Immutable event log. Written once, never updated.
    Used for analytics, cohort analysis, and ML pipelines.
    """
    EVENT_TYPES = [
        # Check-in
        ("checkin",               "Daily Check-In"),
        ("checkin_streak_bonus",  "Streak Bonus"),
        # Spin
        ("spin",                  "Spin Wheel"),
        ("spin_jackpot",          "Spin Jackpot"),
        # Quests
        ("quest_started",         "Quest Started"),
        ("quest_progress",        "Quest Progress"),
        ("quest_completed",       "Quest Completed"),
        # Achievements
        ("achievement_unlocked",  "Achievement Unlocked"),
        ("milestone_reached",     "Milestone Reached"),
        # Shop
        ("shop_viewed",           "Shop Viewed"),
        ("shop_purchased",        "Item Purchased"),
        # Battle Pass
        ("bp_tier_unlocked",      "Battle Pass Tier"),
        ("bp_premium_purchased",  "BP Premium Bought"),
        # Guild
        ("guild_joined",          "Guild Joined"),
        ("guild_contributed",     "Guild Contribution"),
        # Social
        ("feed_liked",            "Feed Item Liked"),
        ("friend_added",          "Friend Added"),
        # Chest
        ("chest_opened",          "Chest Opened"),
        # Referral
        ("referral_made",         "Referral Made"),
        ("referral_rewarded",     "Referral Rewarded"),
        # Prestige
        ("prestige_reached",      "Prestige Reached"),
        # Campaign
        ("campaign_received",     "Campaign Received"),
        ("campaign_converted",    "Campaign Converted"),
        # Session
        ("session_start",         "Session Started"),
        ("session_end",           "Session Ended"),
    ]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="engagement_events", db_index=True)
    event_type  = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    coins_delta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    xp_delta    = models.IntegerField(default=0)
    value       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    properties  = models.JSONField(default=dict, blank=True)
    session_id  = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    device_type = models.CharField(max_length=20, blank=True)   # "mobile", "desktop", "tablet"
    platform    = models.CharField(max_length=20, blank=True)   # "android", "ios", "web"
    app_version = models.CharField(max_length=20, blank=True)
    event_time  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-event_time"]
        indexes  = [
            models.Index(fields=["user", "event_type", "event_time"]),
            models.Index(fields=["tenant", "event_type", "event_time"]),
            models.Index(fields=["event_time", "event_type"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.event_type} @ {self.event_time:%Y-%m-%d %H:%M}"


class RetentionCohort(TenantModel):
    """Pre-computed daily/weekly retention numbers per signup cohort."""
    cohort_date   = models.DateField(db_index=True)   # date users signed up
    period_type   = models.CharField(max_length=10, choices=[("daily","D"),("weekly","W")])
    period_number = models.IntegerField()              # D1, D7, D30 etc.
    total_users   = models.IntegerField(default=0)
    retained      = models.IntegerField(default=0)

    class Meta:
        unique_together = ["tenant", "cohort_date", "period_type", "period_number"]

    @property
    def retention_rate(self):
        return round(self.retained / self.total_users * 100, 1) if self.total_users else 0


class DailyPlatformMetric(TenantModel):
    """Aggregated daily platform-wide engagement KPIs."""
    date             = models.DateField(unique=True, db_index=True)
    dau              = models.IntegerField(default=0)    # Daily Active Users
    checkins         = models.IntegerField(default=0)
    spins            = models.IntegerField(default=0)
    quests_completed = models.IntegerField(default=0)
    achievements_unlocked = models.IntegerField(default=0)
    shop_purchases   = models.IntegerField(default=0)
    coins_distributed = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    xp_distributed   = models.BigIntegerField(default=0)
    new_users        = models.IntegerField(default=0)
    chest_openings   = models.IntegerField(default=0)
    guild_actions    = models.IntegerField(default=0)
    bp_premium_purchases = models.IntegerField(default=0)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Metrics {self.date}: DAU={self.dau}"
