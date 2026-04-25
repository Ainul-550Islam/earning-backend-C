from django.conf import settings
"""
Compliance Database Model

This module contains compliance-related models for managing
advertiser compliance, verification, and regulatory requirements.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class ComplianceCheck(AdvertiserPortalBaseModel, AuditModel, TrackingModel):
    """
    Compliance check model for tracking regulatory compliance.
    
    This model stores compliance check results and documentation
    for advertisers and campaigns.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='compliance_checks',
        help_text="Associated advertiser"
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='compliance_checks',
        help_text="Associated campaign (null for advertiser-level)"
    )
    
    check_type = models.CharField(
        max_length=50,
        choices=ComplianceCheckTypeEnum.choices(),
        help_text="Type of compliance check"
    )
    
    status = models.CharField(
        max_length=50,
        choices=ComplianceStatusEnum.choices(),
        default=ComplianceStatusEnum.PENDING,
        help_text="Compliance check status"
    )
    
    priority = models.CharField(
        max_length=50,
        choices=CompliancePriorityEnum.choices(),
        default=CompliancePriorityEnum.MEDIUM,
        help_text="Compliance check priority"
    )
    
    # Check details
    check_description = models.TextField(
        help_text="Description of compliance check"
    )
    
    requirements = models.JSONField(
        default=list,
        blank=True,
        help_text="List of compliance requirements"
    )
    
    submitted_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of submitted compliance documents"
    )
    
    # Review information
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_compliance_checks',
        help_text="User who reviewed the compliance check"
    )
    
    review_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date of compliance review"
    )
    
    review_notes = models.TextField(
        blank=True,
        help_text="Notes from compliance review"
    )
    
    approval_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date of compliance approval"
    )
    
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for compliance rejection"
    )
    
    # Expiration and renewal
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Compliance check expiration date"
    )
    
    auto_renew = models.BooleanField(
        default=False,
        help_text="Automatically renew compliance check"
    )
    
    renewal_reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether renewal reminder was sent"
    )
    
    # Risk assessment
    risk_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('10.00'))],
        help_text="Compliance risk score (0-10)"
    )
    
    risk_factors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of identified risk factors"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_compliance_checks'
        indexes = [
            models.Index(fields=['advertiser', 'check_type'], name='idx_advertiser_check_type_178'),
            models.Index(fields=['campaign', 'status'], name='idx_campaign_status_179'),
            models.Index(fields=['status', 'priority'], name='idx_status_priority_180'),
            models.Index(fields=['review_date'], name='idx_review_date_181'),
            models.Index(fields=['expires_at'], name='idx_expires_at_182'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        target = self.campaign or self.advertiser
        return f"{target} - {self.check_type} ({self.status})"
    
    def clean(self):
        """Validate compliance check data."""
        super().clean()
        
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError("Expiration date must be in the future")
        
        if self.status == ComplianceStatusEnum.APPROVED and not self.review_date:
            raise ValidationError("Review date is required for approved compliance checks")
        
        if self.status == ComplianceStatusEnum.REJECTED and not self.rejection_reason:
            raise ValidationError("Rejection reason is required for rejected compliance checks")
    
    def is_expired(self) -> bool:
        """Check if compliance check is expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def is_expiring_soon(self, days: int = 30) -> bool:
        """Check if compliance check is expiring soon."""
        if not self.expires_at:
            return False
        return timezone.now() + timezone.timedelta(days=days) >= self.expires_at
    
    def approve(self, reviewer: 'User', notes: str = '', expires_at: datetime = None) -> None:
        """Approve the compliance check."""
        self.status = ComplianceStatusEnum.APPROVED
        self.reviewed_by = reviewer
        self.review_date = timezone.now()
        self.review_notes = notes
        self.approval_date = timezone.now()
        self.rejection_reason = ''
        
        if expires_at:
            self.expires_at = expires_at
        
        self.save()
    
    def reject(self, reviewer: 'User', reason: str) -> None:
        """Reject the compliance check."""
        self.status = ComplianceStatusEnum.REJECTED
        self.reviewed_by = reviewer
        self.review_date = timezone.now()
        self.rejection_reason = reason
        self.approval_date = None
        
        self.save()


class ComplianceDocument(AdvertiserPortalBaseModel, AuditModel):
    """
    Compliance document model for storing compliance-related documents.
    
    This model stores uploaded compliance documents and their metadata.
    """
    
    compliance_check = models.ForeignKey(
        ComplianceCheck,
        on_delete=models.CASCADE,
        related_name='documents',
        help_text="Associated compliance check"
    )
    
    document_type = models.CharField(
        max_length=50,
        choices=DocumentTypeEnum.choices(),
        help_text="Type of document"
    )
    
    title = models.CharField(
        max_length=255,
        help_text="Document title"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Document description"
    )
    
    file = models.FileField(
        upload_to='compliance_documents/',
        help_text="Uploaded document file"
    )
    
    file_name = models.CharField(
        max_length=255,
        help_text="Original file name"
    )
    
    file_size = models.BigIntegerField(
        help_text="File size in bytes"
    )
    
    file_type = models.CharField(
        max_length=100,
        help_text="File MIME type"
    )
    
    # Document status
    status = models.CharField(
        max_length=50,
        choices=DocumentStatusEnum.choices(),
        default=DocumentStatusEnum.UPLOADED,
        help_text="Document status"
    )
    
    verification_status = models.CharField(
        max_length=50,
        choices=VerificationStatusEnum.choices(),
        default=VerificationStatusEnum.PENDING,
        help_text="Document verification status"
    )
    
    # Metadata
    upload_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Document upload date"
    )
    
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_documents',
        help_text="User who verified the document"
    )
    
    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Document verification date"
    )
    
    verification_notes = models.TextField(
        blank=True,
        help_text="Document verification notes"
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Document expiration date"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_compliance_documents'
        indexes = [
            models.Index(fields=['compliance_check', 'document_type'], name='idx_compliance_check_docum_dc9'),
            models.Index(fields=['status', 'verification_status'], name='idx_status_verification_st_3b7'),
            models.Index(fields=['upload_date'], name='idx_upload_date_185'),
            models.Index(fields=['expires_at'], name='idx_expires_at_186'),
        ]
        ordering = ['-upload_date']
    
    def __str__(self):
        return f"{self.compliance_check} - {self.title}"
    
    def clean(self):
        """Validate document data."""
        super().clean()
        
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError("Expiration date must be in the future")
    
    def is_expired(self) -> bool:
        """Check if document is expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def verify(self, verifier: 'User', status: str, notes: str = '') -> None:
        """Verify the document."""
        self.verification_status = status
        self.verified_by = verifier
        self.verification_date = timezone.now()
        self.verification_notes = notes
        
        self.save()


class ComplianceViolation(AdvertiserPortalBaseModel, AuditModel, TrackingModel):
    """
    Compliance violation model for tracking compliance breaches.
    
    This model stores compliance violations and their resolution.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='compliance_violations',
        help_text="Associated advertiser"
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='compliance_violations',
        help_text="Associated campaign (null for advertiser-level)"
    )
    
    violation_type = models.CharField(
        max_length=50,
        choices=ViolationTypeEnum.choices(),
        help_text="Type of compliance violation"
    )
    
    severity = models.CharField(
        max_length=50,
        choices=ViolationSeverityEnum.choices(),
        help_text="Violation severity level"
    )
    
    # Violation details
    description = models.TextField(
        help_text="Description of the violation"
    )
    
    detected_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date violation was detected"
    )
    
    detection_method = models.CharField(
        max_length=50,
        choices=DetectionMethodEnum.choices(),
        help_text="How the violation was detected"
    )
    
    # Resolution information
    status = models.CharField(
        max_length=50,
        choices=ViolationStatusEnum.choices(),
        default=ViolationStatusEnum.OPEN,
        help_text="Violation resolution status"
    )
    
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='resolved_violations',
        help_text="User who resolved the violation"
    )
    
    resolution_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date violation was resolved"
    )
    
    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about violation resolution"
    )
    
    # Impact assessment
    impact_assessment = models.TextField(
        blank=True,
        help_text="Assessment of violation impact"
    )
    
    financial_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Financial impact of violation"
    )
    
    corrective_actions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of corrective actions taken"
    )
    
    # Follow-up
    follow_up_required = models.BooleanField(
        default=True,
        help_text="Whether follow-up is required"
    )
    
    follow_up_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date for follow-up review"
    )
    
    follow_up_completed = models.BooleanField(
        default=False,
        help_text="Whether follow-up has been completed"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_compliance_violations'
        indexes = [
            models.Index(fields=['advertiser', 'violation_type'], name='idx_advertiser_violation_t_233'),
            models.Index(fields=['campaign', 'severity'], name='idx_campaign_severity_188'),
            models.Index(fields=['status', 'severity'], name='idx_status_severity_189'),
            models.Index(fields=['detected_at'], name='idx_detected_at_190'),
            models.Index(fields=['resolution_date'], name='idx_resolution_date_191'),
        ]
        ordering = ['-detected_at']
    
    def __str__(self):
        target = self.campaign or self.advertiser
        return f"{target} - {self.violation_type} ({self.severity})"
    
    def resolve(self, resolver: 'User', notes: str = '', financial_impact: Decimal = None) -> None:
        """Resolve the violation."""
        self.status = ViolationStatusEnum.RESOLVED
        self.resolved_by = resolver
        self.resolution_date = timezone.now()
        self.resolution_notes = notes
        
        if financial_impact is not None:
            self.financial_impact = financial_impact
        
        self.save()
    
    def is_overdue_follow_up(self) -> bool:
        """Check if follow-up is overdue."""
        if not self.follow_up_required or not self.follow_up_date:
            return False
        return timezone.now() > self.follow_up_date and not self.follow_up_completed


class ComplianceAudit(AdvertiserPortalBaseModel, AuditModel):
    """
    Compliance audit model for tracking audit activities.
    
    This model stores audit records and findings for compliance verification.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='compliance_audits',
        help_text="Associated advertiser"
    )
    
    audit_type = models.CharField(
        max_length=50,
        choices=AuditTypeEnum.choices(),
        help_text="Type of compliance audit"
    )
    
    audit_period_start = models.DateField(
        help_text="Audit period start date"
    )
    
    audit_period_end = models.DateField(
        help_text="Audit period end date"
    )
    
    # Audit details
    auditor = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_audits',
        help_text="User who conducted the audit"
    )
    
    audit_date = models.DateTimeField(
        help_text="Date audit was conducted"
    )
    
    audit_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Overall audit score (0-100)"
    )
    
    audit_grade = models.CharField(
        max_length=10,
        choices=AuditGradeEnum.choices(),
        null=True,
        blank=True,
        help_text="Audit grade"
    )
    
    # Findings and recommendations
    findings = models.JSONField(
        default=list,
        blank=True,
        help_text="List of audit findings"
    )
    
    recommendations = models.JSONField(
        default=list,
        blank=True,
        help_text="List of audit recommendations"
    )
    
    violations_found = models.IntegerField(
        default=0,
        help_text="Number of violations found during audit"
    )
    
    critical_issues = models.IntegerField(
        default=0,
        help_text="Number of critical issues found"
    )
    
    # Follow-up
    next_audit_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date for next scheduled audit"
    )
    
    follow_up_required = models.BooleanField(
        default=False,
        help_text="Whether follow-up audit is required"
    )
    
    audit_report = models.FileField(
        upload_to='compliance_audit_reports/',
        null=True,
        blank=True,
        help_text="Audit report file"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_compliance_audits'
        indexes = [
            models.Index(fields=['advertiser', 'audit_type'], name='idx_advertiser_audit_type_192'),
            models.Index(fields=['audit_date'], name='idx_audit_date_193'),
            models.Index(fields=['audit_score'], name='idx_audit_score_194'),
            models.Index(fields=['next_audit_date'], name='idx_next_audit_date_195'),
        ]
        ordering = ['-audit_date']
    
    def __str__(self):
        return f"{self.advertiser.company_name} - {self.audit_type} ({self.audit_date})"
    
    def clean(self):
        """Validate audit data."""
        super().clean()
        
        if self.audit_period_start >= self.audit_period_end:
            raise ValidationError("Audit period start must be before end")
        
        if self.next_audit_date and self.next_audit_date <= self.audit_period_end:
            raise ValidationError("Next audit date must be after current audit period")
    
    def calculate_grade(self) -> str:
        """Calculate audit grade based on score."""
        if not self.audit_score:
            return AuditGradeEnum.NOT_GRADED
        
        if self.audit_score >= 95:
            return AuditGradeEnum.A_PLUS
        elif self.audit_score >= 90:
            return AuditGradeEnum.A
        elif self.audit_score >= 85:
            return AuditGradeEnum.B_PLUS
        elif self.audit_score >= 80:
            return AuditGradeEnum.B
        elif self.audit_score >= 75:
            return AuditGradeEnum.C_PLUS
        elif self.audit_score >= 70:
            return AuditGradeEnum.C
        elif self.audit_score >= 60:
            return AuditGradeEnum.D
        else:
            return AuditGradeEnum.F
