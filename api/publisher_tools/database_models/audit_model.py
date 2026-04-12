# api/publisher_tools/database_models/audit_model.py
"""AuditLog database model — extended data warehouse model."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AuditLogRecord(TimeStampedModel):
    """AuditLog extended record for reporting and analytics warehouse."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_audit_logs_tenant", db_index=True)
    publisher   = models.ForeignKey("publisher_tools.Publisher", on_delete=models.CASCADE, related_name="publisher_tools_db_audit_logs_records", db_index=True)
    record_date = models.DateField(db_index=True)
    record_hour = models.IntegerField(null=True, blank=True)
    data        = models.JSONField(default=dict, blank=True, verbose_name=_("Record Data"))
    summary     = models.JSONField(default=dict, blank=True, verbose_name=_("Summary Metrics"))
    source      = models.CharField(max_length=50, default="api", verbose_name=_("Data Source"))
    is_processed= models.BooleanField(default=False, db_index=True)
    processed_at= models.DateTimeField(null=True, blank=True)
    checksum    = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "publisher_tools_db_audit_logs"
        verbose_name = _("AuditLog Record")
        verbose_name_plural = _("AuditLog Records")
        ordering = ["-record_date", "-created_at"]
        indexes = [
            models.Index(fields=["publisher", "record_date"]),
            models.Index(fields=["is_processed"]),
        ]

    def __str__(self):
        return f"AuditLog: {self.publisher.publisher_id} — {self.record_date}"

    def mark_processed(self):
        import hashlib, json
        self.is_processed = True
        self.processed_at = __import__("django.utils.timezone", fromlist=["now"]).now()
        self.checksum = hashlib.md5(json.dumps(self.data, sort_keys=True, default=str).encode()).hexdigest()
        self.save(update_fields=["is_processed", "processed_at", "checksum", "updated_at"])
