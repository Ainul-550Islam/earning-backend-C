# api/publisher_tools/publisher_management/publisher_review.py
"""Publisher Review — Admin review workflow for publisher applications."""
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.models import TimeStampedModel


class PublisherReview(TimeStampedModel):
    """Publisher application review record।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_pubrev_tenant', db_index=True)

    REVIEW_STATUS_CHOICES = [
        ('pending',             _('Pending Assignment')),
        ('in_review',           _('Under Review')),
        ('approved',            _('Approved')),
        ('conditionally_approved', _('Conditionally Approved')),
        ('rejected',            _('Rejected')),
        ('on_hold',             _('On Hold')),
        ('escalated',           _('Escalated to Senior')),
    ]
    REVIEW_TYPE_CHOICES = [
        ('initial_application', _('Initial Application')),
        ('reapplication',       _('Re-application')),
        ('periodic_review',     _('Periodic Review')),
        ('complaint_triggered', _('Complaint Triggered')),
        ('upgrade_request',     _('Tier Upgrade Request')),
        ('kyc_review',          _('KYC Document Review')),
    ]

    publisher       = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='reviews', db_index=True)
    reviewer        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_reviews_assigned')
    review_type     = models.CharField(max_length=30, choices=REVIEW_TYPE_CHOICES, default='initial_application', db_index=True)
    status          = models.CharField(max_length=30, choices=REVIEW_STATUS_CHOICES, default='pending', db_index=True)
    priority        = models.CharField(max_length=10, choices=[('low','Low'),('normal','Normal'),('high','High'),('urgent','Urgent')], default='normal', db_index=True)
    # Checklist
    content_policy_check    = models.BooleanField(default=False)
    traffic_quality_check   = models.BooleanField(default=False)
    identity_verification_check = models.BooleanField(default=False)
    business_legitimacy_check   = models.BooleanField(default=False)
    compliance_check        = models.BooleanField(default=False)
    # Scores
    content_score           = models.IntegerField(default=0)
    traffic_score           = models.IntegerField(default=0)
    identity_score          = models.IntegerField(default=0)
    overall_review_score    = models.IntegerField(default=0)
    # Notes
    internal_notes          = models.TextField(blank=True)
    reviewer_recommendation = models.TextField(blank=True)
    rejection_reasons       = models.JSONField(default=list, blank=True)
    conditions              = models.TextField(blank=True, verbose_name=_("Conditions for Approval"))
    publisher_feedback      = models.TextField(blank=True, verbose_name=_("Feedback for Publisher"))
    # Timing
    assigned_at             = models.DateTimeField(null=True, blank=True)
    started_at              = models.DateTimeField(null=True, blank=True)
    completed_at            = models.DateTimeField(null=True, blank=True)
    sla_deadline            = models.DateTimeField(null=True, blank=True)
    is_sla_breached         = models.BooleanField(default=False)
    escalated_to            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_escalated_reviews')
    metadata                = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_reviews'
        verbose_name = _('Publisher Review')
        verbose_name_plural = _('Publisher Reviews')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['reviewer', 'status']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['sla_deadline']),
        ]

    def __str__(self):
        return f"Review: {self.publisher.publisher_id} [{self.review_type}] — {self.status}"

    def assign_to(self, reviewer):
        self.reviewer = reviewer
        self.assigned_at = timezone.now()
        self.status = 'in_review'
        self.started_at = timezone.now()
        from datetime import timedelta
        self.sla_deadline = timezone.now() + timedelta(hours=48)
        self.save()

    def calculate_overall_score(self):
        weights = {'content': 0.35, 'traffic': 0.35, 'identity': 0.30}
        self.overall_review_score = round(
            self.content_score * weights['content'] +
            self.traffic_score * weights['traffic'] +
            self.identity_score * weights['identity']
        )
        self.save(update_fields=['overall_review_score', 'updated_at'])
        return self.overall_review_score

    @property
    def checklist_complete(self):
        return all([
            self.content_policy_check, self.traffic_quality_check,
            self.identity_verification_check, self.business_legitimacy_check,
            self.compliance_check
        ])

    @transaction.atomic
    def complete_review(self, decision: str, notes: str = '', feedback: str = ''):
        valid = {'approved', 'conditionally_approved', 'rejected', 'on_hold'}
        if decision not in valid:
            raise ValueError(f"Invalid decision. Choose from: {valid}")
        self.status = decision
        self.completed_at = timezone.now()
        self.internal_notes = notes
        self.publisher_feedback = feedback
        self.save()
        # Update publisher status
        publisher = self.publisher
        if decision == 'approved':
            publisher.status = 'active'
        elif decision == 'rejected':
            publisher.status = 'suspended'
        elif decision == 'on_hold':
            publisher.status = 'under_review'
        publisher.save(update_fields=['status', 'updated_at'])

    @property
    def is_overdue(self):
        return bool(self.sla_deadline and timezone.now() > self.sla_deadline and self.status not in ('approved', 'rejected'))
