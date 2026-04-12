# api/publisher_tools/site_management/site_approval.py
"""Site Approval — Review workflow for site registration."""
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.models import TimeStampedModel


class SiteApprovalRecord(TimeStampedModel):
    """Site approval/rejection record।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_siteapproval_tenant', db_index=True)

    DECISION_CHOICES = [
        ('pending',   _('Pending')),
        ('approved',  _('Approved')),
        ('rejected',  _('Rejected')),
        ('conditional',_('Conditionally Approved')),
        ('on_hold',   _('On Hold')),
    ]

    site                = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='approval_records', db_index=True)
    reviewer            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_site_reviews')
    decision            = models.CharField(max_length=20, choices=DECISION_CHOICES, default='pending', db_index=True)
    # Checklist
    content_check_pass  = models.BooleanField(default=False)
    ads_txt_check_pass  = models.BooleanField(default=False)
    domain_check_pass   = models.BooleanField(default=False)
    traffic_check_pass  = models.BooleanField(default=False)
    policy_check_pass   = models.BooleanField(default=False)
    # Notes
    reviewer_notes      = models.TextField(blank=True)
    rejection_reasons   = models.JSONField(default=list, blank=True)
    conditions          = models.TextField(blank=True)
    publisher_feedback  = models.TextField(blank=True)
    # Timing
    review_started_at   = models.DateTimeField(null=True, blank=True)
    review_completed_at = models.DateTimeField(null=True, blank=True)
    auto_approved       = models.BooleanField(default=False)

    class Meta:
        db_table = 'publisher_tools_site_approval_records'
        verbose_name = _('Site Approval Record')
        verbose_name_plural = _('Site Approval Records')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', 'decision']),
            models.Index(fields=['reviewer']),
        ]

    def __str__(self):
        return f"Review: {self.site.domain} — {self.decision}"

    @property
    def checklist_score(self):
        checks = [self.content_check_pass, self.ads_txt_check_pass, self.domain_check_pass, self.traffic_check_pass, self.policy_check_pass]
        return sum(20 for c in checks if c)

    @transaction.atomic
    def make_decision(self, decision: str, reviewer=None, notes: str = '', feedback: str = ''):
        self.decision = decision
        self.reviewer = reviewer
        self.reviewer_notes = notes
        self.publisher_feedback = feedback
        self.review_completed_at = timezone.now()
        self.save()
        site = self.site
        if decision == 'approved':
            site.status = 'active'
            site.approved_at = timezone.now()
            site.approved_by = reviewer
        elif decision == 'rejected':
            site.status = 'rejected'
            site.rejection_reason = feedback
        elif decision == 'on_hold':
            site.status = 'inactive'
        site.save(update_fields=['status', 'approved_at', 'approved_by', 'rejection_reason', 'updated_at'])
