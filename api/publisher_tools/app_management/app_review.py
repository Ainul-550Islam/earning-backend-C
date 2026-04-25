# api/publisher_tools/app_management/app_review.py
"""App Review — Admin review workflow for app registration."""
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.models import TimeStampedModel


class AppApprovalRecord(TimeStampedModel):
    """App approval/rejection record."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appapproval_tenant", db_index=True)
    DECISIONS = [("pending","Pending"),("approved","Approved"),("rejected","Rejected"),("on_hold","On Hold")]
    app                 = models.ForeignKey("publisher_tools.App", on_delete=models.CASCADE, related_name="approval_records", db_index=True)
    reviewer            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_app_reviews")
    decision            = models.CharField(max_length=20, choices=DECISIONS, default="pending", db_index=True)
    store_check_pass    = models.BooleanField(default=False)
    content_check_pass  = models.BooleanField(default=False)
    sdk_check_pass      = models.BooleanField(default=False)
    reviewer_notes      = models.TextField(blank=True)
    rejection_reasons   = models.JSONField(default=list, blank=True)
    publisher_feedback  = models.TextField(blank=True)
    review_started_at   = models.DateTimeField(null=True, blank=True)
    review_completed_at = models.DateTimeField(null=True, blank=True)
    auto_approved       = models.BooleanField(default=False)

    class Meta:
        db_table = "publisher_tools_app_approval_records"
        verbose_name = _("App Approval Record")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["app", "decision"], name='idx_app_decision_1541')]

    def __str__(self):
        return f"Review: {self.app.name} — {self.decision}"

    @transaction.atomic
    def make_decision(self, decision: str, reviewer=None, notes: str = "", feedback: str = ""):
        self.decision = decision
        self.reviewer = reviewer
        self.reviewer_notes = notes
        self.publisher_feedback = feedback
        self.review_completed_at = timezone.now()
        self.save()
        app = self.app
        if decision == "approved":
            app.status = "active"
            app.approved_at = timezone.now()
            app.approved_by = reviewer
        elif decision == "rejected":
            app.status = "rejected"
            app.rejection_reason = feedback
        app.save(update_fields=["status", "approved_at", "approved_by", "rejection_reason", "updated_at"])
