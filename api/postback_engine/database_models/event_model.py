"""
database_models/event_model.py
────────────────────────────────
Goal/event tracking for multi-step conversion flows.
"""
from django.db import models
from django.conf import settings
import uuid

class ConversionEvent(models.Model):
    """Track individual goal completions within a conversion flow."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversion = models.ForeignKey(
        "postback_engine.Conversion", on_delete=models.CASCADE,
        related_name="events", null=True, blank=True,
    )
    network = models.ForeignKey(
        "postback_engine.AdNetworkConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="postback_events",
    )
    goal_id = models.CharField(max_length=100, blank=True, db_index=True)
    goal_name = models.CharField(max_length=200, blank=True)
    goal_value = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    offer_id = models.CharField(max_length=255, blank=True, db_index=True)
    transaction_id = models.CharField(max_length=255, blank=True, db_index=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = "conversion event"
        verbose_name_plural = "conversion events"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["goal_id", "occurred_at"], name='idx_goal_id_occurred_at_1407'),
            models.Index(fields=["offer_id", "occurred_at"], name='idx_offer_id_occurred_at_1408'),
        ]

    def __str__(self):
        return f"Event[{self.goal_id}] offer={self.offer_id}"
