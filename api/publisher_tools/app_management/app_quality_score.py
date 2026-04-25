# api/publisher_tools/app_management/app_quality_score.py
"""App Quality Score — Automated quality scoring for mobile apps."""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppQualityScore(TimeStampedModel):
    """App quality score breakdown — monthly."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appquality_tenant", db_index=True)
    app              = models.ForeignKey("publisher_tools.App", on_delete=models.CASCADE, related_name="quality_scores", db_index=True)
    month            = models.DateField(db_index=True)
    overall_score    = models.IntegerField(default=0, db_index=True)
    store_rating_score = models.IntegerField(default=0)
    download_score   = models.IntegerField(default=0)
    traffic_score    = models.IntegerField(default=0)
    sdk_compliance_score = models.IntegerField(default=0)
    content_score    = models.IntegerField(default=0)
    # Data
    avg_store_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))
    total_downloads  = models.BigIntegerField(default=0)
    monthly_active_users = models.BigIntegerField(default=0)
    crash_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    ivt_rate         = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    has_policy_violation = models.BooleanField(default=False)
    alerts           = models.JSONField(default=list, blank=True)
    has_alerts       = models.BooleanField(default=False, db_index=True)
    score_change     = models.IntegerField(default=0)

    class Meta:
        db_table = "publisher_tools_app_quality_scores"
        verbose_name = _("App Quality Score")
        unique_together = [["app", "month"]]
        ordering = ["-month"]
        indexes = [
            models.Index(fields=["app", "month"], name='idx_app_month_1539'),
            models.Index(fields=["overall_score"], name='idx_overall_score_1540'),
        ]

    def __str__(self):
        return f"{self.app.name} — {self.month.strftime('%B %Y')} — Score: {self.overall_score}"

    def recalculate(self):
        weights = {"store_rating": 0.30, "download": 0.20, "traffic": 0.25, "sdk": 0.15, "content": 0.10}
        self.overall_score = round(
            self.store_rating_score * weights["store_rating"] +
            self.download_score * weights["download"] +
            self.traffic_score * weights["traffic"] +
            self.sdk_compliance_score * weights["sdk"] +
            self.content_score * weights["content"]
        )
        self.has_alerts = bool(self.alerts) or self.has_policy_violation
        self.save()
        self.app.quality_score = self.overall_score
        self.app.save(update_fields=["quality_score", "updated_at"])
        return self.overall_score
