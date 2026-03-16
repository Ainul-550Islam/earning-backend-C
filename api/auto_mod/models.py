# =============================================================================
# auto_mod/models.py
# =============================================================================
"""
ORM models for the auto_mod (AI Moderation) application.

Models:
  AutoApprovalRule     — configurable rule engine for automatic decisions
  SuspiciousSubmission — submissions flagged by AI or rules for review
  ProofScanner         — tracks individual scan jobs (image / text / OCR)
  TaskBot              — autonomous bot that processes pending submissions
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from .choices import (
    BotStatus,
    FlagReason,
    ModerationStatus,
    ModelTrainingStatus,
    RiskLevel,
    RuleAction,
    RuleConditionOperator,
    ScanType,
    SubmissionType,
)
from .constants import (
    AUTO_APPROVE_THRESHOLD,
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    MAX_BOT_RETRIES,
    MAX_CONDITIONS_PER_RULE,
    MAX_PROOF_FILES_PER_SUBMISSION,
    MAX_RULES_PER_EVALUATION,
    MAX_SUBMISSION_TEXT_LENGTH,
    RULE_PRIORITY_MAX,
    RULE_PRIORITY_MIN,
    SUSPICIOUS_KEYWORD_LIMIT,
)
from .exceptions import (
    InvalidConfidenceScoreError,
    InvalidRuleConfigError,
)
from .managers import (
    AutoApprovalRuleManager,
    ProofScannerManager,
    SuspiciousSubmissionManager,
    TaskBotManager,
)

User = get_user_model()

_CONF_VALIDATORS = [
    MinValueValidator(CONFIDENCE_MIN),
    MaxValueValidator(CONFIDENCE_MAX),
]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class TimeStampedUUIDModel(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} pk={self.pk}>"


# =============================================================================
# AutoApprovalRule
# =============================================================================

class AutoApprovalRule(TimeStampedUUIDModel):
    """
    A configurable rule that determines how the system handles a submission
    automatically.

    Each rule has:
      - A submission_type scope
      - A set of conditions (stored as JSON) evaluated against submission data
      - An action taken when ALL conditions match
      - A priority (lower = higher priority, evaluated first)
      - A confidence_threshold: AI must be ≥ this to fire the action

    Condition JSON schema (list of condition objects):
        [
          {
            "field":    "text_length",
            "operator": "gt",
            "value":    100
          },
          ...
        ]
    """

    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name=_("Rule Name"),
    )
    description = models.TextField(blank=True, default="", verbose_name=_("Description"))

    submission_type = models.CharField(
        max_length=20,
        choices=SubmissionType.choices,
        db_index=True,
        verbose_name=_("Submission Type"),
    )
    priority = models.PositiveSmallIntegerField(
        default=50,
        validators=[
            MinValueValidator(RULE_PRIORITY_MIN),
            MaxValueValidator(RULE_PRIORITY_MAX),
        ],
        db_index=True,
        verbose_name=_("Priority"),
        help_text=_("Lower number = higher priority (evaluated first)."),
    )
    conditions = models.JSONField(
        default=list,
        verbose_name=_("Conditions"),
        help_text=_("List of condition objects. All must match for the rule to fire."),
    )
    action = models.CharField(
        max_length=20,
        choices=RuleAction.choices,
        verbose_name=_("Action"),
    )
    confidence_threshold = models.FloatField(
        default=AUTO_APPROVE_THRESHOLD,
        validators=_CONF_VALIDATORS,
        verbose_name=_("Confidence Threshold"),
        help_text=_("AI confidence must be ≥ this value for the action to fire."),
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_system  = models.BooleanField(
        default=False,
        verbose_name=_("System Rule"),
        help_text=_("System rules cannot be deleted via the API."),
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_mod_rules",
        verbose_name=_("Created By"),
    )
    metadata = models.JSONField(default=dict, blank=True)

    objects = AutoApprovalRuleManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Auto-Approval Rule")
        verbose_name_plural = _("Auto-Approval Rules")
        indexes = [
            models.Index(fields=["submission_type", "is_active", "priority"]),
            models.Index(fields=["action", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"Rule[{self.submission_type}] '{self.name}' → {self.action} (pri={self.priority})"

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.conditions, list):
            raise InvalidRuleConfigError(_("conditions must be a JSON list."))
        if len(self.conditions) > MAX_CONDITIONS_PER_RULE:
            raise InvalidRuleConfigError(
                _(f"conditions may not exceed {MAX_CONDITIONS_PER_RULE} items.")
            )
        if not (CONFIDENCE_MIN <= self.confidence_threshold <= CONFIDENCE_MAX):
            raise InvalidConfidenceScoreError()

    @property
    def condition_count(self) -> int:
        return len(self.conditions) if isinstance(self.conditions, list) else 0


# =============================================================================
# SuspiciousSubmission
# =============================================================================

class SuspiciousSubmission(TimeStampedUUIDModel):
    """
    A submission that has been flagged by the AI moderation engine for
    further inspection.

    This model is a moderation record — it references the original
    submission via a generic content_id (UUID string) and content_type
    so it can work with any upstream model (tasks, posts, profiles, etc.)
    without tight coupling.

    The AI fills in:
      - ai_confidence   : overall confidence of the AI decision
      - risk_score      : normalised [0, 1] risk score
      - risk_level      : LOW / MEDIUM / HIGH / CRITICAL
      - flag_reason     : primary reason for flagging
      - ai_explanation  : human-readable explanation of the decision
      - scan_metadata   : raw output from the scanner

    Human reviewers fill in:
      - reviewed_by
      - reviewer_note
      - final_status
    """

    # ------------------------------------------------------------------
    # Reference to original submission
    # ------------------------------------------------------------------
    content_type = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_("Content Type"),
        help_text=_("Model label, e.g. 'tasks.taskproof'"),
    )
    content_id = models.CharField(
        max_length=128,
        db_index=True,
        verbose_name=_("Content ID"),
    )
    submission_type = models.CharField(
        max_length=20,
        choices=SubmissionType.choices,
        db_index=True,
        verbose_name=_("Submission Type"),
    )
    submitted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="suspicious_submissions",
        verbose_name=_("Submitted By"),
    )

    # ------------------------------------------------------------------
    # AI analysis results
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
        verbose_name=_("Moderation Status"),
    )
    ai_confidence = models.FloatField(
        null=True,
        blank=True,
        validators=_CONF_VALIDATORS,
        verbose_name=_("AI Confidence"),
    )
    risk_score = models.FloatField(
        null=True,
        blank=True,
        validators=_CONF_VALIDATORS,
        verbose_name=_("Risk Score"),
    )
    risk_level = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
        db_index=True,
        verbose_name=_("Risk Level"),
    )
    flag_reason = models.CharField(
        max_length=25,
        choices=FlagReason.choices,
        default=FlagReason.OTHER,
        verbose_name=_("Flag Reason"),
    )
    ai_explanation = models.TextField(
        blank=True,
        default="",
        verbose_name=_("AI Explanation"),
    )
    scan_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Scan Metadata"),
        help_text=_("Raw JSON output from the AI scanner."),
    )
    matched_rule = models.ForeignKey(
        AutoApprovalRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="flagged_submissions",
        verbose_name=_("Matched Rule"),
    )

    # ------------------------------------------------------------------
    # Human review
    # ------------------------------------------------------------------
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_suspicious_submissions",
        verbose_name=_("Reviewed By"),
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reviewed At"),
    )
    reviewer_note = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Reviewer Note"),
    )
    final_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        blank=True,
        default="",
        verbose_name=_("Final Status"),
    )
    escalated_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="escalated_submissions",
        verbose_name=_("Escalated To"),
    )

    objects = SuspiciousSubmissionManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Suspicious Submission")
        verbose_name_plural = _("Suspicious Submissions")
        indexes = [
            models.Index(fields=["status", "risk_level", "created_at"]),
            models.Index(fields=["content_type", "content_id"]),
            models.Index(fields=["submitted_by", "status"]),
            models.Index(fields=["submission_type", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "content_id"],
                name="unique_submission_per_content",
            )
        ]

    def __str__(self) -> str:
        return (
            f"Suspicious[{self.submission_type}] {self.content_id[:12]}… "
            f"risk={self.risk_level} status={self.status}"
        )

    @property
    def is_pending_human_review(self) -> bool:
        return self.status == ModerationStatus.HUMAN_REVIEW

    @property
    def is_resolved(self) -> bool:
        return self.status in (
            ModerationStatus.AUTO_APPROVED,
            ModerationStatus.AUTO_REJECTED,
            ModerationStatus.HUMAN_APPROVED,
            ModerationStatus.HUMAN_REJECTED,
        )

    def set_ai_result(
        self,
        *,
        confidence: float,
        risk_score: float,
        risk_level: str,
        flag_reason: str,
        explanation: str = "",
        metadata: dict | None = None,
    ) -> None:
        """
        Populate AI analysis fields (in-memory). Caller must call .save().
        """
        self.ai_confidence  = confidence
        self.risk_score     = risk_score
        self.risk_level     = risk_level
        self.flag_reason    = flag_reason
        self.ai_explanation = explanation
        self.scan_metadata  = metadata or {}


# =============================================================================
# ProofScanner
# =============================================================================

class ProofScanner(TimeStampedUUIDModel):
    """
    Tracks a single AI scan job against a SuspiciousSubmission.

    One submission may have multiple scanner records (e.g. image + text).
    Results from all scanners are aggregated into the parent submission.
    """

    submission = models.ForeignKey(
        SuspiciousSubmission,
        on_delete=models.CASCADE,
        related_name="scans",
        db_index=True,
        verbose_name=_("Submission"),
    )
    scan_type = models.CharField(
        max_length=10,
        choices=ScanType.choices,
        db_index=True,
        verbose_name=_("Scan Type"),
    )
    file_url = models.URLField(
        max_length=2048,
        blank=True,
        default="",
        verbose_name=_("File URL"),
        help_text=_("URL of the file scanned (image/PDF). Empty for text scans."),
    )
    input_text = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Input Text"),
        help_text=_("Raw text sent for analysis (truncated if > MAX_SUBMISSION_TEXT_LENGTH)."),
    )

    # Results
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=_CONF_VALIDATORS,
        verbose_name=_("Confidence"),
    )
    is_flagged = models.BooleanField(
        null=True,
        blank=True,
        verbose_name=_("Flagged?"),
    )
    labels = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Detected Labels"),
        help_text=_("List of label strings returned by the AI model."),
    )
    ocr_text = models.TextField(
        blank=True,
        default="",
        verbose_name=_("OCR Extracted Text"),
    )
    raw_result = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Raw Scanner Result"),
    )
    error_message = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Error Message"),
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Scan Duration (ms)"),
    )
    model_version = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Model Version"),
    )

    objects = ProofScannerManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Proof Scanner")
        verbose_name_plural = _("Proof Scanners")
        indexes = [
            models.Index(fields=["submission", "scan_type"]),
            models.Index(fields=["is_flagged", "created_at"]),
        ]

    def __str__(self) -> str:
        flagged = "FLAGGED" if self.is_flagged else "CLEAN"
        return f"Scan[{self.scan_type}] {flagged} conf={self.confidence}"

    @property
    def succeeded(self) -> bool:
        return self.confidence is not None and not self.error_message


# =============================================================================
# TaskBot
# =============================================================================

class TaskBot(TimeStampedUUIDModel):
    """
    An autonomous bot that processes moderation queues on a schedule.

    Each bot has a scope (submission_type + action_filter) and a heartbeat
    so the system can detect stalled bots.

    Configuration JSON schema:
        {
          "max_batch_size":    50,
          "process_interval":  60,
          "priority_filter":   ["high", "critical"],
          "auto_escalate":     true,
          "notify_on_error":   true
        }
    """

    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name=_("Bot Name"),
    )
    description = models.TextField(blank=True, default="")

    submission_type = models.CharField(
        max_length=20,
        choices=SubmissionType.choices,
        db_index=True,
        verbose_name=_("Target Submission Type"),
    )
    status = models.CharField(
        max_length=12,
        choices=BotStatus.choices,
        default=BotStatus.IDLE,
        db_index=True,
        verbose_name=_("Status"),
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Bot Configuration"),
    )

    # Statistics
    total_processed = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Total Processed"),
    )
    total_approved  = models.PositiveIntegerField(default=0)
    total_rejected  = models.PositiveIntegerField(default=0)
    total_escalated = models.PositiveIntegerField(default=0)
    total_errors    = models.PositiveIntegerField(default=0)

    # Heartbeat / health
    last_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Heartbeat"),
    )
    last_error = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Last Error"),
    )
    retry_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Current Retry Count"),
    )
    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_bots",
        verbose_name=_("Assigned To"),
    )

    objects = TaskBotManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Task Bot")
        verbose_name_plural = _("Task Bots")
        indexes = [
            models.Index(fields=["status", "submission_type"]),
            models.Index(fields=["last_heartbeat"]),
        ]

    def __str__(self) -> str:
        return f"Bot '{self.name}' [{self.status}] → {self.submission_type}"

    @property
    def is_healthy(self) -> bool:
        """Return True if heartbeat was received within the expected interval."""
        if not self.last_heartbeat:
            return False
        from django.utils import timezone
        from datetime import timedelta
        from .constants import BOT_HEARTBEAT_INTERVAL_SEC
        cutoff = timezone.now() - timedelta(seconds=BOT_HEARTBEAT_INTERVAL_SEC * 3)
        return self.last_heartbeat >= cutoff

    @property
    def approval_rate(self) -> float:
        if not self.total_processed:
            return 0.0
        return round(self.total_approved / self.total_processed * 100, 2)

    def bump_stat(self, field: str, amount: int = 1) -> None:
        """Increment a stat counter in-memory. Caller saves with update_fields."""
        current = getattr(self, field, 0)
        setattr(self, field, current + amount)
