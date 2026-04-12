"""
database_models/webhook_log_model.py
──────────────────────────────────────
Webhook delivery log model — tracks all outbound webhook attempts.
"""
from django.db import models
import uuid

class WebhookLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversion = models.ForeignKey(
        "postback_engine.Conversion", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="webhook_logs",
    )
    network = models.ForeignKey(
        "postback_engine.AdNetworkConfig", on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    event = models.CharField(max_length=100, db_index=True)
    url = models.URLField(max_length=2000)
    payload = models.JSONField(default=dict)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    success = models.BooleanField(default=False, db_index=True)
    attempt_number = models.PositiveSmallIntegerField(default=1)
    duration_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = "webhook log"
        verbose_name_plural = "webhook logs"
        ordering = ["-attempted_at"]
        indexes = [
            models.Index(fields=["success", "attempted_at"]),
            models.Index(fields=["event", "attempted_at"]),
        ]

    def __str__(self):
        return f"Webhook[{self.event}] {'OK' if self.success else 'FAIL'} {self.url[:60]}"
