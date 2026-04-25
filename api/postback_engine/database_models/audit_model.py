"""
database_models/audit_model.py
────────────────────────────────
Immutable audit log for all admin actions in PostbackEngine.
"""
from django.db import models
from django.conf import settings
import uuid

class PostbackEngineAuditLog(models.Model):
    ACTION_CHOICES = [
        ("approve_conversion",  "Approve Conversion"),
        ("reverse_conversion",  "Reverse Conversion"),
        ("blacklist_ip",        "Blacklist IP"),
        ("unblacklist_ip",      "Remove from Blacklist"),
        ("update_network",      "Update Network Config"),
        ("replay_postback",     "Replay Postback"),
        ("manual_reward",       "Manual Reward"),
        ("fraud_review",        "Fraud Review"),
        ("bulk_approve",        "Bulk Approve"),
        ("export_data",         "Export Data"),
        ("purge_dlq",           "Purge Dead Letter Queue"),
        ("update_offer",        "Update Offer Config"),
        ("add_publisher",       "Add Publisher"),
        ("blacklist_publisher",  "Blacklist Publisher"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = "audit log"
        verbose_name_plural = "audit logs"
        ordering = ["-performed_at"]
        indexes = [
            models.Index(fields=["action", "performed_at"], name='idx_action_performed_at_1405'),
            models.Index(fields=["performed_by_id", "performed_at"], name='idx_performed_by_id_perfor_90c'),
        ]

    def __str__(self):
        return f"[{self.action}] by {self.performed_by_id} @ {self.performed_at:%Y-%m-%d %H:%M}"

    @classmethod
    def log(cls, action, performed_by=None, target_type="", target_id="", details=None, ip=None):
        return cls.objects.create(
            action=action,
            performed_by=performed_by,
            target_type=target_type,
            target_id=str(target_id),
            details=details or {},
            ip_address=ip,
        )
