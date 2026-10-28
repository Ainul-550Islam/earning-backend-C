# publisher_tools/app_management/app_approval.py
"""
App Approval Record — publisher app-এর manual review decisions track করে।

Import করা হয়:
    views_app_management_full.py → approval_history(), approval_checklist()

Fields expected by view (getattr-safe):
    app (FK), action, reason, decided_by, created_at
Class method expected:
    AppApprovalRecord.get_checklist(app) -> list
"""
import logging
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel

logger = logging.getLogger(__name__)


# ── Helper (module-level, referenced inside get_checklist) ────────────────────
def _check_sdk_integrated(app) -> bool:
    """App-এ SDK integration আছে কিনা check করে (safe)."""
    try:
        sdk_cfg = getattr(app, 'sdk_config', None)
        if sdk_cfg is None:
            return False
        return bool(getattr(sdk_cfg, 'is_sdk_integrated', False))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────

class AppApprovalRecord(TimeStampedModel):
    """
    Publisher app-এর প্রতিটি review/approval/rejection decision এখানে log হয়।
    একটা app-এর multiple records থাকতে পারে (resubmission cycle)।

    Usage:
        record = AppApprovalRecord.create_for_app(app, action='submitted')
        record.approve(reviewer=user, decided_by='admin@earnify.io')
        record.reject(reviewer=user, reason='policy_violation', feedback='...')
        checklist = AppApprovalRecord.get_checklist(app)
    """

    # ── Action constants ──────────────────────────────────────────────────────
    ACTION_SUBMITTED    = 'submitted'
    ACTION_UNDER_REVIEW = 'under_review'
    ACTION_APPROVED     = 'approved'
    ACTION_REJECTED     = 'rejected'
    ACTION_SUSPENDED    = 'suspended'
    ACTION_REINSTATED   = 'reinstated'
    ACTION_RESUBMITTED  = 'resubmitted'

    ACTION_CHOICES = [
        (ACTION_SUBMITTED,    _('Submitted for Review')),
        (ACTION_UNDER_REVIEW, _('Under Review')),
        (ACTION_APPROVED,     _('Approved')),
        (ACTION_REJECTED,     _('Rejected')),
        (ACTION_SUSPENDED,    _('Suspended')),
        (ACTION_REINSTATED,   _('Reinstated')),
        (ACTION_RESUBMITTED,  _('Resubmitted')),
    ]

    # ── Reason constants ──────────────────────────────────────────────────────
    REASON_MANUAL_REVIEW         = 'manual_review'
    REASON_AUTOMATIC             = 'automatic_approval'
    REASON_POLICY_VIOLATION      = 'policy_violation'
    REASON_CONTENT_INAPPROPRIATE = 'content_inappropriate'
    REASON_TECHNICAL_ISSUES      = 'technical_issues'
    REASON_FRAUD_RISK            = 'fraud_risk'
    REASON_INCOMPLETE_INFO       = 'incomplete_info'
    REASON_DUPLICATE_APP         = 'duplicate_app'
    REASON_SUSPENDED_PUBLISHER   = 'suspended_publisher'

    REASON_CHOICES = [
        (REASON_MANUAL_REVIEW,         _('Manual Review')),
        (REASON_AUTOMATIC,             _('Automatic Approval')),
        (REASON_POLICY_VIOLATION,      _('Policy Violation')),
        (REASON_CONTENT_INAPPROPRIATE, _('Content Inappropriate')),
        (REASON_TECHNICAL_ISSUES,      _('Technical Issues')),
        (REASON_FRAUD_RISK,            _('Fraud Risk')),
        (REASON_INCOMPLETE_INFO,       _('Incomplete Information')),
        (REASON_DUPLICATE_APP,         _('Duplicate App')),
        (REASON_SUSPENDED_PUBLISHER,   _('Publisher Suspended')),
    ]

    # ── Fields ────────────────────────────────────────────────────────────────
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publisher_tools_app_approval_tenant',
        db_index=True,
    )
    app = models.ForeignKey(
        'publisher_tools.App',
        on_delete=models.CASCADE,
        related_name='approval_records',
        db_index=True,
        verbose_name=_('App'),
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='app_approvals_reviewed',
        verbose_name=_('Reviewer'),
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        default=ACTION_SUBMITTED,
        db_index=True,
        verbose_name=_('Action'),
    )
    reason = models.CharField(
        max_length=40,
        choices=REASON_CHOICES,
        default=REASON_MANUAL_REVIEW,
        verbose_name=_('Reason'),
    )
    decided_by = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_('Decided By'),
        help_text=_('Username or system identifier that made the decision'),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Internal Notes'),
        help_text=_('Visible only to admin reviewers'),
    )
    rejection_feedback = models.TextField(
        blank=True,
        verbose_name=_('Rejection Feedback'),
        help_text=_('Feedback delivered to the publisher on rejection'),
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_('Reviewed At'),
    )
    is_resubmission = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_('Is Resubmission'),
    )
    previous_action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        blank=True,
        verbose_name=_('Previous Action'),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Checklist results, automated scores, and other review data'),
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    class Meta:
        app_label = 'publisher_tools'
        db_table = 'publisher_tools_app_approval_records'
        verbose_name = _('App Approval Record')
        verbose_name_plural = _('App Approval Records')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', 'action'],
                         name='idx_app_approval_action_1601'),
            models.Index(fields=['reviewer', 'reviewed_at'],
                         name='idx_app_approval_reviewer_1602'),
            models.Index(fields=['app', 'created_at'],
                         name='idx_app_approval_date_1603'),
        ]

    # ── Dunder ────────────────────────────────────────────────────────────────
    def __str__(self):
        app_id = getattr(self.app, 'app_id', self.app_id) if self.app_id else '?'
        return (
            f"AppApproval(app={app_id}, "
            f"action={self.action}, "
            f"by={self.decided_by or 'system'})"
        )

    # ── Instance methods ──────────────────────────────────────────────────────

    def approve(self, reviewer=None, notes: str = '', decided_by: str = ''):
        """App-কে approved করে এবং record update করে।"""
        self.previous_action = self.action
        self.action          = self.ACTION_APPROVED
        self.reviewer        = reviewer
        self.notes           = notes
        self.decided_by      = decided_by or (
            reviewer.username if reviewer and hasattr(reviewer, 'username')
            else 'system'
        )
        self.reviewed_at = timezone.now()
        self.save(update_fields=[
            'action', 'reviewer', 'notes', 'decided_by',
            'reviewed_at', 'previous_action', 'updated_at',
        ])
        logger.info(
            'AppApprovalRecord: app=%s APPROVED by=%s',
            self.app_id, self.decided_by,
        )

    def reject(
        self,
        reviewer=None,
        reason: str = '',
        notes: str = '',
        feedback: str = '',
        decided_by: str = '',
    ):
        """App-কে rejected করে, feedback publisher-কে দেওয়া হবে।"""
        self.previous_action    = self.action
        self.action             = self.ACTION_REJECTED
        self.reason             = reason or self.REASON_POLICY_VIOLATION
        self.reviewer           = reviewer
        self.notes              = notes
        self.rejection_feedback = feedback
        self.decided_by         = decided_by or (
            reviewer.username if reviewer and hasattr(reviewer, 'username')
            else 'system'
        )
        self.reviewed_at = timezone.now()
        self.save(update_fields=[
            'action', 'reason', 'reviewer', 'notes',
            'rejection_feedback', 'decided_by',
            'reviewed_at', 'previous_action', 'updated_at',
        ])
        logger.info(
            'AppApprovalRecord: app=%s REJECTED by=%s reason=%s',
            self.app_id, self.decided_by, self.reason,
        )

    def suspend(self, reviewer=None, notes: str = '', decided_by: str = ''):
        """Approved app-কে suspend করে।"""
        self.previous_action = self.action
        self.action          = self.ACTION_SUSPENDED
        self.reviewer        = reviewer
        self.notes           = notes
        self.decided_by      = decided_by or (
            reviewer.username if reviewer and hasattr(reviewer, 'username')
            else 'system'
        )
        self.reviewed_at = timezone.now()
        self.save(update_fields=[
            'action', 'reviewer', 'notes', 'decided_by',
            'reviewed_at', 'previous_action', 'updated_at',
        ])
        logger.warning(
            'AppApprovalRecord: app=%s SUSPENDED by=%s',
            self.app_id, self.decided_by,
        )

    def reinstate(self, reviewer=None, notes: str = '', decided_by: str = ''):
        """Suspended app-কে reinstate করে।"""
        self.previous_action = self.action
        self.action          = self.ACTION_REINSTATED
        self.reviewer        = reviewer
        self.notes           = notes
        self.decided_by      = decided_by or (
            reviewer.username if reviewer and hasattr(reviewer, 'username')
            else 'system'
        )
        self.reviewed_at = timezone.now()
        self.save(update_fields=[
            'action', 'reviewer', 'notes', 'decided_by',
            'reviewed_at', 'previous_action', 'updated_at',
        ])
        logger.info(
            'AppApprovalRecord: app=%s REINSTATED by=%s',
            self.app_id, self.decided_by,
        )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_approved(self) -> bool:
        """App currently approved কিনা।"""
        return self.action == self.ACTION_APPROVED

    @property
    def is_pending(self) -> bool:
        """App review-এর অপেক্ষায় আছে কিনা।"""
        return self.action in (self.ACTION_SUBMITTED, self.ACTION_UNDER_REVIEW)

    @property
    def is_rejected(self) -> bool:
        """App rejected কিনা।"""
        return self.action == self.ACTION_REJECTED

    @property
    def is_suspended(self) -> bool:
        """App suspended কিনা।"""
        return self.action == self.ACTION_SUSPENDED

    @property
    def is_resubmittable(self) -> bool:
        """Publisher কি resubmit করতে পারবে।"""
        return self.action in (self.ACTION_REJECTED, self.ACTION_SUSPENDED)

    # ── Class methods ─────────────────────────────────────────────────────────

    @classmethod
    def get_checklist(cls, app) -> list:
        """
        App approval checklist generate করে।
        views_app_management_full.py → approval_checklist() action-এ ব্যবহার হয়।

        Returns:
            list of dicts: [{'item': str, 'label': str, 'passed': bool, 'required': bool}]
        """
        return [
            {
                'item':     'store_url_valid',
                'label':    'Store URL set (Play Store or App Store)',
                'passed':   bool(
                    getattr(app, 'play_store_url', '') or
                    getattr(app, 'app_store_url', '')
                ),
                'required': True,
            },
            {
                'item':     'package_name_set',
                'label':    'Package / Bundle ID set',
                'passed':   bool(getattr(app, 'package_name', '')),
                'required': True,
            },
            {
                'item':     'category_set',
                'label':    'App category set',
                'passed':   bool(getattr(app, 'category', '')),
                'required': True,
            },
            {
                'item':     'name_set',
                'label':    'App name set',
                'passed':   bool(getattr(app, 'name', '')),
                'required': True,
            },
            {
                'item':     'platform_set',
                'label':    'Platform set (Android / iOS / Web)',
                'passed':   bool(getattr(app, 'platform', '')),
                'required': True,
            },
            {
                'item':     'content_rating_set',
                'label':    'Content rating set',
                'passed':   bool(getattr(app, 'content_rating', '')),
                'required': True,
            },
            {
                'item':     'icon_uploaded',
                'label':    'App icon URL provided',
                'passed':   bool(getattr(app, 'icon_url', '')),
                'required': False,
            },
            {
                'item':     'publisher_kyc_verified',
                'label':    'Publisher KYC verified',
                'passed':   bool(
                    getattr(
                        getattr(app, 'publisher', None),
                        'is_kyc_verified',
                        False,
                    )
                ),
                'required': False,
            },
            {
                'item':     'sdk_integrated',
                'label':    'SDK integration completed',
                'passed':   _check_sdk_integrated(app),
                'required': False,
            },
        ]

    @classmethod
    def create_for_app(
        cls,
        app,
        action: str = None,
        reason: str = None,
        reviewer=None,
        decided_by: str = 'system',
        notes: str = '',
    ) -> 'AppApprovalRecord':
        """
        App-এর জন্য নতুন approval record তৈরি করে।

        Usage:
            record = AppApprovalRecord.create_for_app(
                app=app_instance,
                action=AppApprovalRecord.ACTION_SUBMITTED,
                decided_by='publisher_portal',
            )
        """
        record = cls(
            app       = app,
            action    = action or cls.ACTION_SUBMITTED,
            reason    = reason or cls.REASON_MANUAL_REVIEW,
            reviewer  = reviewer,
            decided_by= decided_by,
            notes     = notes,
        )
        # Tenant propagation
        publisher = getattr(app, 'publisher', None)
        if publisher:
            tenant = getattr(publisher, 'tenant', None)
            if tenant:
                record.tenant = tenant
        record.save()
        logger.info(
            'AppApprovalRecord CREATED for app=%s action=%s',
            getattr(app, 'app_id', app.pk),
            record.action,
        )
        return record

    @classmethod
    def latest_for_app(cls, app) -> 'AppApprovalRecord | None':
        """App-এর সর্বশেষ approval record।"""
        return cls.objects.filter(app=app).order_by('-created_at').first()

    @classmethod
    def is_app_approved(cls, app) -> bool:
        """App-এর সর্বশেষ record approved কিনা।"""
        record = cls.latest_for_app(app)
        return record.is_approved if record else False
