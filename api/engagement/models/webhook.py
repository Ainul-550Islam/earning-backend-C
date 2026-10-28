# engagement/models/webhook.py
"""
Webhook System
Platform operators can register webhook endpoints to receive real-time
events (checkin, level_up, achievement, purchase, etc.) at their own URLs.
Includes retry logic, signature verification, and delivery logs.
"""
from django.db import models
from .base import TenantModel


class WebhookEndpoint(TenantModel):
    """A registered webhook URL for outbound event delivery."""
    EVENT_CHOICES = [
        ("checkin",          "Daily Check-In"),
        ("level_up",         "Level Up"),
        ("achievement",      "Achievement Unlocked"),
        ("quest_complete",   "Quest Completed"),
        ("shop_purchase",    "Shop Purchase"),
        ("referral",         "Referral Rewarded"),
        ("leaderboard",      "Leaderboard Reward"),
        ("battle_pass_tier", "Battle Pass Tier"),
        ("prestige",         "Prestige"),
        ("guild_event",      "Guild Event"),
        ("anti_cheat",       "Anti-Cheat Flag"),
        ("all",              "All Events"),
    ]
    name           = models.CharField(max_length=200)
    url            = models.URLField(max_length=500)
    secret         = models.CharField(max_length=64)    # HMAC signing secret
    events         = models.JSONField(default=list)     # list of event types to subscribe to
    is_active      = models.BooleanField(default=True)
    timeout_seconds = models.IntegerField(default=10)
    retry_count    = models.IntegerField(default=3)
    last_triggered = models.DateTimeField(null=True, blank=True)
    success_count  = models.IntegerField(default=0)
    failure_count  = models.IntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"Webhook: {self.name} → {self.url}"


class WebhookDelivery(TenantModel):
    """One delivery attempt for a webhook event."""
    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("success",   "Success"),
        ("failed",    "Failed"),
        ("retrying",  "Retrying"),
        ("abandoned", "Abandoned"),
    ]
    endpoint      = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries")
    event_type    = models.CharField(max_length=30)
    payload       = models.JSONField()
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    attempt_count = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    delivered_at  = models.DateTimeField(null=True, blank=True)
    duration_ms   = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["endpoint", "status"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self):
        return f"Delivery {self.event_type} → {self.endpoint.name} [{self.status}]"
