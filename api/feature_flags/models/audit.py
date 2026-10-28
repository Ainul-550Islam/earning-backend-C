"""
NEW FILE — Audit trail model.

Implements Missing Component #3 (Audit Trail) from the audit: there was
previously NO record of who changed a flag, what changed, or when —
making incident investigation and compliance (SOC2/GDPR) impossible.
"""
from django.conf import settings
from django.db import models

from .base import BaseModel
from .feature_flag import FeatureFlag


class AuditLog(BaseModel):
    """Immutable record of a single change to a FeatureFlag."""

    class Action(models.TextChoices):
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        ACTIVATE = 'activate', 'Activate'
        PAUSE = 'pause', 'Pause'
        ARCHIVE = 'archive', 'Archive'
        RESTORE = 'restore', 'Restore'
        ROLLBACK = 'rollback', 'Rollback'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='flag_audit_logs'
    )
    # Nullable + SET_NULL so audit history survives flag deletion.
    flag = models.ForeignKey(
        FeatureFlag, on_delete=models.SET_NULL, null=True, related_name='audit_logs'
    )
    flag_name_snapshot = models.CharField(max_length=255, help_text='Flag name at time of action (survives deletion).')

    action = models.CharField(max_length=20, choices=Action.choices)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['flag', '-timestamp'], name='audit_flag_ts_idx'),
            models.Index(fields=['user', '-timestamp'], name='audit_user_ts_idx'),
            models.Index(fields=['action', '-timestamp'], name='audit_action_ts_idx'),
        ]

    def __str__(self):
        return f"{self.action} on {self.flag_name_snapshot} by {self.user} @ {self.timestamp}"
