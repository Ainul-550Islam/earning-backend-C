"""WEBHOOKS/webhook_logger.py — Log inbound webhook events"""
from django.db import models
from api.tenants.models import Tenant


class WebhookLog(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_webhook_logs_tenant")
    source = models.CharField(max_length=50)
    event = models.CharField(max_length=100)
    payload = models.JSONField()
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_webhook_log"
        ordering = ["-received_at"]

    def __str__(self):
        return f"[{self.source}] {self.event} @ {self.received_at:%Y-%m-%d %H:%M}"
