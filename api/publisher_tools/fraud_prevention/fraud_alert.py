# api/publisher_tools/fraud_prevention/fraud_alert.py
"""Fraud Alert — Alert generation and notification for fraud events."""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class FraudAlert(TimeStampedModel):
    """Fraud detection alert record।"""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_fraudalert_tenant", db_index=True)
    ALERT_TYPES = [
        ("high_ivt_rate","High IVT Rate"),("suspicious_spike","Traffic Spike"),
        ("bot_farm_detected","Bot Farm Detected"),("click_fraud","Click Fraud Campaign"),
        ("account_anomaly","Account Anomaly"),("payout_fraud","Payout Fraud Attempt"),
    ]
    SEVERITY = [("low","Low"),("medium","Medium"),("high","High"),("critical","Critical")]
    publisher    = models.ForeignKey("publisher_tools.Publisher", on_delete=models.CASCADE, related_name="fraud_alerts", db_index=True)
    alert_type   = models.CharField(max_length=30, choices=ALERT_TYPES, db_index=True)
    severity     = models.CharField(max_length=10, choices=SEVERITY, default="medium", db_index=True)
    title        = models.CharField(max_length=300)
    description  = models.TextField()
    fraud_score  = models.IntegerField(default=0)
    affected_sites    = models.JSONField(default=list, blank=True)
    affected_units    = models.JSONField(default=list, blank=True)
    data_summary      = models.JSONField(default=dict, blank=True)
    is_read      = models.BooleanField(default=False, db_index=True)
    is_resolved  = models.BooleanField(default=False, db_index=True)
    resolved_at  = models.DateTimeField(null=True, blank=True)
    resolution   = models.TextField(blank=True)
    auto_action_taken = models.CharField(max_length=50, blank=True)
    notified_via = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "publisher_tools_fraud_alerts"
        verbose_name = _("Fraud Alert")
        verbose_name_plural = _("Fraud Alerts")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publisher", "is_resolved", "severity"]),
            models.Index(fields=["alert_type"]),
        ]

    def __str__(self):
        return f"Alert: {self.publisher.publisher_id} — {self.alert_type} [{self.severity}]"

    def mark_read(self):
        self.is_read = True
        self.save(update_fields=["is_read", "updated_at"])

    def resolve(self, resolution: str = ""):
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolution  = resolution
        self.save()


def create_fraud_alert(publisher, alert_type: str, severity: str, title: str, description: str, data: dict = None) -> FraudAlert:
    alert = FraudAlert.objects.create(
        publisher=publisher, alert_type=alert_type, severity=severity,
        title=title, description=description, data_summary=data or {},
    )
    if severity in ("high", "critical"):
        # Send notification
        try:
            from api.publisher_tools.webhooks.webhook_manager import send_webhook_event
            send_webhook_event(publisher, "fraud.high_risk_detected", {"alert_type": alert_type, "severity": severity})
        except Exception:
            pass
    return alert


def get_unresolved_alerts(publisher) -> list:
    return list(FraudAlert.objects.filter(publisher=publisher, is_resolved=False).order_by("-created_at")[:20])
