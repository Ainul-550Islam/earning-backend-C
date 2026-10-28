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
    AppealOutcome,
    AppealStatus,
    BotStatus,
    DecisionType,
    FlagReason,
    ModelTrainingStatus,
    ModelType,
    ModerationStatus,
    QueuePriority,
    RiskLevel,
    RuleAction,
    RuleConditionOperator,
    ScanStatus,
    ScanType,
    SignalType,
    SubmissionType,
    TaskType,
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
    ContentSignalManager,
    MLModelVersionManager,
    ModerationAppealManager,
    ModerationDecisionManager,
    ModerationQueueManager,
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

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
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
        max_length=30,
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
        related_name="created_moderation_rules",
        verbose_name=_("Created By"),
    )
    metadata = models.JSONField(default=dict, blank=True)

    objects = AutoApprovalRuleManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Auto-Approval Rule")
        verbose_name_plural = _("Auto-Approval Rules")
        indexes = [
            models.Index(fields=["submission_type", "is_active", "priority"], name='idx_submission_type_is_act_f29'),
            models.Index(fields=["action", "is_active"], name='idx_action_is_active_817'),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.submission_type})"

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
    # 'user' is an alias for submitted_by used by tests and external code
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissions_as_user",
        verbose_name=_("User"),
        db_column="user_id",
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
            models.Index(fields=["status", "risk_level", "created_at"], name='idx_status_risk_level_crea_b03'),
            models.Index(fields=["content_type", "content_id"], name='idx_content_type_content_i_9a3'),
            models.Index(fields=["submitted_by", "status"], name='idx_submitted_by_status_820'),
            models.Index(fields=["submission_type", "status"], name='idx_submission_type_status_821'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "content_id"],
                name="unique_submission_per_content",
            )
        ]

    @property
    def metadata(self) -> dict:
        """Alias for scan_metadata — used by tests and external integrations."""
        return self.scan_metadata or {}

    @metadata.setter
    def metadata(self, value: dict) -> None:
        self.scan_metadata = value

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
        max_length=20,
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
    status = models.CharField(
        max_length=10,
        choices=ScanStatus.choices,
        default=ScanStatus.PENDING,
        db_index=True,
        verbose_name=_("Scan Status"),
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
    started_at = models.DateTimeField(
        default=None,
        null=True,
        blank=True,
        verbose_name=_("Started At"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Completed At"),
    )
    result_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Result Data"),
        help_text=_("Structured result from the scan."),
    )

    initiated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="initiated_scans",
        verbose_name=_("Initiated By"),
        help_text=_("User or bot that initiated this scan. Null for automated scans."),
    )

    @property
    def duration_seconds(self):
        """Return duration in seconds, or None if not completed."""
        if self.completed_at is None or self.started_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def mark_completed(self, status: str, result_data: dict) -> None:
        """Mark this scan as completed with a given status and result."""
        from django.utils import timezone
        now = timezone.now()
        self.status = status
        self.result_data = result_data
        self.completed_at = now
        if self.started_at is None:
            self.started_at = now
        update_fields = ["status", "result_data", "completed_at", "started_at", "updated_at"]
        self.save(update_fields=update_fields)

    objects = ProofScannerManager()

    def __str__(self) -> str:
        return f"{self.get_scan_type_display()} - {self.submission.content_id}"

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Proof Scanner")
        verbose_name_plural = _("Proof Scanners")
        indexes = [
            models.Index(fields=["submission", "scan_type"], name='idx_submission_scan_type_822'),
            models.Index(fields=["is_flagged", "created_at"], name='idx_is_flagged_created_at_823'),
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

    bot_type = models.CharField(
        max_length=15,
        choices=TaskType.choices,
        default=TaskType.IMAGE_SCANNER,
        db_index=True,
        verbose_name=_("Bot Type"),
    )
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
    max_retries = models.PositiveSmallIntegerField(
        default=3,
        verbose_name=_("Max Retries"),
        help_text=_("Maximum number of retries before bot enters ERROR state."),
    )
    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_bots",
        verbose_name=_("Assigned To"),
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_task_bots",
        verbose_name=_("Created By"),
    )

    current_retry = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Current Retry"),
    )
    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Run At"),
    )

    objects = TaskBotManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Task Bot")
        verbose_name_plural = _("Task Bots")
        indexes = [
            models.Index(fields=["status", "submission_type"], name='idx_status_submission_type_824'),
            models.Index(fields=["last_heartbeat"], name='idx_last_heartbeat_825'),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_bot_type_display()})"

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


    def start(self) -> None:
        """Start this bot."""
        from django.utils import timezone
        self.status = BotStatus.RUNNING
        self.last_run_at = timezone.now()
        self.current_retry = 0
        self.save(update_fields=["status", "last_run_at", "current_retry", "updated_at"])

    def stop(self) -> None:
        """Stop this bot."""
        self.status = BotStatus.STOPPED
        self.save(update_fields=["status", "updated_at"])

    def pause(self) -> None:
        """Pause this bot."""
        self.status = BotStatus.PAUSED
        self.save(update_fields=["status", "updated_at"])

    def restart(self) -> None:
        """Restart this bot."""
        from django.utils import timezone
        self.status = BotStatus.RUNNING
        self.current_retry = 0
        self.last_run_at = timezone.now()
        self.save(update_fields=["status", "current_retry", "last_run_at", "updated_at"])

    def increment_retry(self) -> None:
        """Increment retry count; mark FAILED if max reached."""
        self.current_retry = (self.current_retry or 0) + 1
        if self.current_retry >= self.max_retries:
            self.status = BotStatus.FAILED
        self.save(update_fields=["current_retry", "status", "updated_at"])

    def update_heartbeat(self) -> None:
        """Refresh last_heartbeat timestamp."""
        from django.utils import timezone
        self.last_heartbeat = timezone.now()
        self.save(update_fields=["last_heartbeat"])

    def is_healthy(self) -> bool:
        """Return True if bot is in a healthy state."""
        if self.status in [BotStatus.FAILED, BotStatus.ERROR, BotStatus.DISABLED]:
            return False
        if self.status == BotStatus.RUNNING and self.last_heartbeat is None:
            return False
        if self.status == BotStatus.RUNNING and self.last_heartbeat:
            from django.utils import timezone
            stale_threshold = timezone.now() - timezone.timedelta(minutes=10)
            if self.last_heartbeat < stale_threshold:
                return False
        return True

    def can_run(self) -> bool:
        """Return True if this bot can be started/run."""
        if self.status in [BotStatus.RUNNING, BotStatus.FAILED, BotStatus.DISABLED, BotStatus.ERROR]:
            return False
        if (self.current_retry or 0) >= self.max_retries:
            return False
        return True

    def get_runtime_stats(self) -> dict:
        """Return runtime statistics for this bot."""
        return {
            "status":        self.status,
            "last_run_at":   str(self.last_run_at) if self.last_run_at else None,
            "last_heartbeat": str(self.last_heartbeat) if self.last_heartbeat else None,
            "current_retry": self.current_retry or 0,
            "max_retries":   self.max_retries,
            "is_healthy":    self.is_healthy(),
            "total_processed": self.total_processed,
        }

    def bump_stat(self, field: str, amount: int = 1) -> None:
        """Increment a stat counter in-memory. Caller saves with update_fields."""
        current = getattr(self, field, 0)
        setattr(self, field, current + amount)


# =============================================================================
# ModerationQueue
# =============================================================================

class ModerationQueue(TimeStampedUUIDModel):
    """
    Queue management for submissions requiring human review or special processing.
    
    This model tracks submissions that need to be processed by human moderators
    or specialized bots, with priority-based ordering and assignment tracking.
    """

    submission = models.OneToOneField(
        SuspiciousSubmission,
        on_delete=models.CASCADE,
        related_name="queue_entry",
        db_index=True,
        verbose_name=_("Submission"),
    )
    priority = models.CharField(
        max_length=10,
        choices=QueuePriority.choices,
        default=QueuePriority.MEDIUM,
        db_index=True,
        verbose_name=_("Priority"),
        help_text=_("Higher priority submissions are processed first."),
    )
    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_queue_items",
        verbose_name=_("Assigned To"),
        help_text=_("Moderator currently assigned to this queue item."),
    )
    assigned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_queue_items_by",
        verbose_name=_("Assigned By"),
    )
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Assigned At"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Completed At"),
    )
    queued_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Queued At"),
    )
    due_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Due At"),
        help_text=_("Deadline for processing this queue item."),
    )
    estimated_processing_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Estimated Processing Time (minutes)"),
        help_text=_("Estimated time required to process this submission."),
    )
    escalation_level = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Escalation Level"),
        help_text=_("Number of times this item has been escalated."),
    )
    auto_escalate_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Auto Escalate At"),
        help_text=_("When to automatically escalate if not processed."),
    )
    processing_notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Processing Notes"),
        help_text=_("Internal notes for moderators about this submission."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Queue Metadata"),
        help_text=_("Additional queue-specific data."),
    )

    objects = ModerationQueueManager()

    def __str__(self) -> str:
        return f"Queue: {self.submission.content_id} ({self.get_priority_display()})"

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name = _("Moderation Queue")
        verbose_name_plural = _("Moderation Queues")
        indexes = [
            models.Index(fields=["priority", "queued_at"], name='idx_priority_queued_at_826'),
            models.Index(fields=["assigned_to", "queued_at"], name='idx_assigned_to_queued_827'),
            models.Index(fields=["due_at", "priority"], name='idx_due_at_priority_828'),
            models.Index(fields=["auto_escalate_at"], name='idx_auto_escalate_at_829'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["submission"],
                name="unique_queue_per_submission",
            )
        ]

    def __str__(self) -> str:
        assigned = f"→{self.assigned_to.username}" if self.assigned_to else "Unassigned"
        return f"Queue[{self.priority}] {self.submission.content_id[:12]}… {assigned}"

    @property
    def is_overdue(self) -> bool:
        """Return True if the queue item is past its due date."""
        if not self.due_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.due_at

    @property
    def should_auto_escalate(self) -> bool:
        """Return True if the item should be auto-escalated."""
        if not self.auto_escalate_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.auto_escalate_at

    @property
    def processing_time_elapsed(self) -> int:
        """Return minutes elapsed since queuing."""
        from django.utils import timezone
        elapsed = timezone.now() - self.queued_at
        return int(elapsed.total_seconds() / 60)

    def complete(self) -> None:
        """Complete this queue item."""
        from django.utils import timezone
        self.completed_at = timezone.now()
        self.assigned_to = None
        self.save(update_fields=["completed_at", "assigned_to", "updated_at"])

    def assign_to(self, user: User) -> None:
        """Assign this queue item to a user and update timestamps."""
        from django.utils import timezone
        self.assigned_to = user
        self.assigned_at = timezone.now()
        # Auto-escalate if not processed within SLA
        if self.estimated_processing_time:
            self.auto_escalate_at = timezone.now() + timezone.timedelta(
                minutes=self.estimated_processing_time * 2  # 2x SLA for escalation
            )

    def escalate(self, new_priority: str = None) -> None:
        """Escalate this queue item to higher priority/level."""
        from django.utils import timezone
        self.escalation_level += 1
        if new_priority:
            self.priority = new_priority
        # Set new auto-escalate time
        self.auto_escalate_at = timezone.now() + timezone.timedelta(hours=1)


# =============================================================================
# ModerationDecision
# =============================================================================

class ModerationDecision(TimeStampedUUIDModel):
    """
    Records all moderation decisions made on submissions.
    
    This model provides an audit trail of every decision, whether made by AI,
    human moderators, or automated systems, with full context and reasoning.
    """

    submission = models.ForeignKey(
        SuspiciousSubmission,
        on_delete=models.CASCADE,
        related_name="decisions",
        db_index=True,
        verbose_name=_("Submission"),
    )
    decision_type = models.CharField(
        max_length=15,
        choices=DecisionType.choices,
        db_index=True,
        verbose_name=_("Decision Type"),
    )
    reason = models.TextField(
        verbose_name=_("Decision Reason"),
        help_text=_("Detailed explanation of why this decision was made."),
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=_CONF_VALIDATORS,
        verbose_name=_("Decision Confidence"),
        help_text=_("Confidence score for this decision (0.0-1.0)."),
    )
    decided_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderation_decisions",
        verbose_name=_("Decided By"),
        help_text=_("User who made this decision (null for AI decisions)."),
    )
    decided_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Decision Time"),
    )
    is_automated = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Automated Decision"),
        help_text=_("True if this decision was made by AI/automation."),
    )
    applied_rule = models.ForeignKey(
        AutoApprovalRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_decisions",
        verbose_name=_("Applied Rule"),
        help_text=_("Rule that triggered this automated decision."),
    )
    decision_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Decision Data"),
        help_text=_("Additional data related to this decision."),
    )
    reviewer_notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Reviewer Notes"),
        help_text=_("Private notes from the reviewer."),
    )
    previous_decision = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subsequent_decisions",
        verbose_name=_("Previous Decision"),
        help_text=_("Previous decision that this one overrides."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Decision Metadata"),
        help_text=_("Additional metadata about the decision process."),
    )

    objects = ModerationDecisionManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name = _("Moderation Decision")
        verbose_name_plural = _("Moderation Decisions")
        indexes = [
            models.Index(fields=["submission", "decided_at"], name='idx_submission_decided_at_830'),
            models.Index(fields=["decision_type", "is_automated"], name='idx_decision_type_is_auto_831'),
            models.Index(fields=["decided_by", "decided_at"], name='idx_decided_by_decided_at_832'),
            models.Index(fields=["applied_rule"], name='idx_applied_rule_833'),
        ]
        ordering = ["-decided_at"]

    def __str__(self) -> str:
        decider = "AI" if self.is_automated else (self.decided_by.username if self.decided_by else "Unknown")
        return f"Decision[{self.decision_type}] {self.submission.content_id[:12]}… by {decider}"

    @property
    def is_final(self) -> bool:
        """Return True if this is a final decision (no further appeals allowed)."""
        return self.decision_type in [DecisionType.APPROVE, DecisionType.REJECT]

    @property
    def requires_follow_up(self) -> bool:
        """Return True if this decision requires follow-up action."""
        return self.decision_type in [DecisionType.ESCALATE, DecisionType.REQUEST_INFO]

    def create_appeal(self, user: User, appeal_reason: str) -> "ModerationAppeal":
        """Create an appeal against this decision."""
        return ModerationAppeal.objects.create(
            submission=self.submission,
            user=user,
            reason=appeal_reason,
            original_decision=self,
        )


# =============================================================================
# ModerationAppeal
# =============================================================================

class ModerationAppeal(TimeStampedUUIDModel):
    """
    Appeals against moderation decisions by users.
    
    This model tracks user appeals against moderation decisions, including
    the review process and final resolution.
    """

    submission = models.ForeignKey(
        SuspiciousSubmission,
        on_delete=models.CASCADE,
        related_name="appeals",
        db_index=True,
        verbose_name=_("Submission"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="moderation_appeals",
        db_index=True,
        verbose_name=_("Appealing User"),
    )
    original_decision = models.ForeignKey(
        ModerationDecision,
        on_delete=models.CASCADE,
        related_name="appeals",
        verbose_name=_("Original Decision"),
    )
    reason = models.TextField(
        verbose_name=_("Appeal Reason"),
        help_text=_("User's reason for appealing the decision."),
    )
    status = models.CharField(
        max_length=15,
        choices=AppealStatus.choices,
        default=AppealStatus.PENDING,
        db_index=True,
        verbose_name=_("Appeal Status"),
    )
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_appeals",
        verbose_name=_("Reviewed By"),
        help_text=_("Moderator who reviewed this appeal."),
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reviewed At"),
    )
    review_notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Review Notes"),
        help_text=_("Notes from the appeal review process."),
    )
    final_decision = models.CharField(
        max_length=15,
        choices=DecisionType.choices,
        blank=True,
        default="",
        verbose_name=_("Final Decision"),
        help_text=_("Final decision after appeal review."),
    )
    final_outcome = models.CharField(
        max_length=15,
        choices=AppealOutcome.choices,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Appeal Outcome"),
        help_text=_("Whether the appeal was upheld, overturned, or partially granted."),
    )
    final_reason = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Final Reason"),
        help_text=_("Explanation for the final appeal decision."),
    )
    appeal_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Appeal Data"),
        help_text=_("Additional data related to this appeal."),
    )
    additional_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Additional Data"),
        help_text=_("Additional evidence or context provided by the appellant."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Appeal Metadata"),
        help_text=_("Additional metadata about the appeal."),
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Resolved At"),
        help_text=_("When this appeal was resolved."),
    )

    objects = ModerationAppealManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name = _("Moderation Appeal")
        verbose_name_plural = _("Moderation Appeals")
        indexes = [
            models.Index(fields=["submission", "status"], name='idx_submission_status_834'),
            models.Index(fields=["user", "status"], name='idx_user_status_835'),
            models.Index(fields=["original_decision"], name='idx_original_decision_836'),
            models.Index(fields=["reviewed_by", "reviewed_at"], name='idx_reviewed_at_837'),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Appeal: {self.submission.content_id} by {self.user.username}"

    @property
    def is_pending_review(self) -> bool:
        """Return True if this appeal is waiting for review."""
        return self.status in [AppealStatus.PENDING, AppealStatus.UNDER_REVIEW]

    @property
    def is_resolved(self) -> bool:
        """Return True if this appeal has been resolved."""
        from .choices import AppealStatus as AS
        return self.status in [AS.APPROVED, AS.REJECTED, AS.CLOSED, AS.RESOLVED]

    @property
    def is_overdue(self) -> bool:
        """Return True if the appeal is overdue (pending > 7 days)."""
        if self.is_resolved:
            return False
        from django.utils import timezone
        overdue_threshold = timezone.now() - timezone.timedelta(days=7)
        return self.created_at < overdue_threshold

    @property
    def was_successful(self) -> bool:
        """Return True if the appeal was successful (original decision overturned)."""
        return self.status == AppealStatus.APPROVED

    def assign_reviewer(self, reviewer: User) -> None:
        """Assign a reviewer to this appeal."""
        from django.utils import timezone
        self.reviewed_by = reviewer
        self.status = AppealStatus.UNDER_REVIEW
        self.reviewed_at = timezone.now()

    def resolve(
        self,
        final_reason: str,
        reviewer: User,
        final_outcome: str = "",
        final_decision: str = "",
    ) -> None:
        """Resolve this appeal.

        Accepts either ``final_outcome`` (AppealOutcome value) or the older
        ``final_decision`` kwarg for backwards compatibility.
        """
        from django.utils import timezone
        outcome = final_outcome or final_decision
        self.final_outcome = outcome
        self.final_decision = outcome
        self.final_reason = final_reason
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.resolved_at = timezone.now()
        self.status = AppealStatus.RESOLVED


# =============================================================================
# MLModelVersion
# =============================================================================

class MLModelVersion(TimeStampedUUIDModel):
    """
    Version tracking for ML models used in moderation.
    
    This model tracks different versions of ML models, their performance metrics,
    deployment status, and training history.
    """

    model_type = models.CharField(
        max_length=10,
        choices=ModelType.choices,
        db_index=True,
        verbose_name=_("Model Type"),
    )
    version = models.CharField(
        max_length=50,
        verbose_name=_("Version"),
        help_text=_("Semantic version (e.g., '1.2.3' or 'v2024.03.15')."),
    )
    display_name = models.CharField(
        max_length=200,
        verbose_name=_("Display Name"),
        help_text=_("Human-readable name for this model version."),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Description"),
        help_text=_("Detailed description of this model version."),
    )
    file_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Model File Path"),
        help_text=_("Path to the model file on storage."),
    )
    file_size_mb = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("File Size (MB)"),
        help_text=_("Size of the model file in megabytes."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("SHA-256 Checksum"),
        help_text=_("SHA-256 checksum of the model file for integrity verification."),
    )
    
    # Performance metrics
    accuracy = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Accuracy"),
        help_text=_("Model accuracy on test dataset (0.0-1.0)."),
    )
    precision = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Precision"),
        help_text=_("Model precision on test dataset (0.0-1.0)."),
    )
    recall = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Recall"),
        help_text=_("Model recall on test dataset (0.0-1.0)."),
    )
    f1_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("F1 Score"),
        help_text=_("Model F1 score on test dataset (0.0-1.0)."),
    )
    auc_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("AUC Score"),
        help_text=_("Model AUC score on test dataset (0.0-1.0)."),
    )
    
    # Training data
    training_data_version = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Training Data Version"),
        help_text=_("Version of the training dataset used."),
    )
    training_samples = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Training Samples"),
        help_text=_("Number of samples used for training."),
    )
    validation_samples = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Validation Samples"),
        help_text=_("Number of samples used for validation."),
    )
    training_duration_hours = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Training Duration (hours)"),
        help_text=_("Time taken to train this model version."),
    )
    
    # Deployment status
    status = models.CharField(
        max_length=15,
        choices=ModelTrainingStatus.choices,
        default=ModelTrainingStatus.IDLE,
        db_index=True,
        verbose_name=_("Status"),
    )
    deployed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Deployed At"),
        help_text=_("When this model version was deployed to production."),
    )
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("True if this model version is currently active in production."),
    )
    deployment_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Deployment Config"),
        help_text=_("Configuration used for deployment."),
    )
    
    # Metadata
    hyperparameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Hyperparameters"),
        help_text=_("Model hyperparameters and training configuration."),
    )
    feature_importance = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Feature Importance"),
        help_text=_("Feature importance scores from the model."),
    )
    training_log = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Training Log"),
        help_text=_("Detailed training log and metrics."),
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_ml_models",
        verbose_name=_("Created By"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Model Metadata"),
        help_text=_("Additional metadata about this model version."),
    )

    objects = MLModelVersionManager()

    def __str__(self) -> str:
        return f"{self.display_name} v{self.version}"

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name = _("ML Model Version")
        verbose_name_plural = _("ML Model Versions")
        indexes = [
            models.Index(fields=["model_type", "version"], name='idx_model_type_version_838'),
            models.Index(fields=["status", "is_active"], name='idx_status_is_active_839'),
            models.Index(fields=["deployed_at"], name='idx_deployed_at_840'),
            models.Index(fields=["accuracy"], name='idx_accuracy_841'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["model_type", "version"],
                name="unique_model_version",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        active = "[ACTIVE]" if self.is_active else ""
        return f"Model[{self.model_type}] {self.version} {active}"

    @property
    def is_deployed(self) -> bool:
        """Return True if this model version has been deployed."""
        return self.deployed_at is not None

    @property
    def performance_summary(self) -> dict:
        """Return a summary of performance metrics."""
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "auc_score": self.auc_score,
        }

    def deploy(self, config: dict = None) -> None:
        """Deploy this model version to production."""
        from django.utils import timezone
        # Deactivate other versions of the same model type
        MLModelVersion.objects.filter(
            model_type=self.model_type,
            is_active=True
        ).update(is_active=False, deployed_at=None)
        
        # Activate this version
        self.is_active = True
        self.deployed_at = timezone.now()
        self.status = ModelTrainingStatus.DEPLOYED
        if config:
            self.deployment_config = config

    def retire(self) -> None:
        """Retire this model version from production."""
        self.is_active = False
        self.status = ModelTrainingStatus.IDLE


# =============================================================================
# ContentSignal
# =============================================================================

class ContentSignal(TimeStampedUUIDModel):
    """
    Signals and indicators detected in content during analysis.
    
    This model tracks various signals detected by AI, pattern matching,
    user reports, or other analysis methods that contribute to moderation decisions.
    """

    submission = models.ForeignKey(
        SuspiciousSubmission,
        on_delete=models.CASCADE,
        related_name="signals",
        db_index=True,
        verbose_name=_("Submission"),
    )
    signal_type = models.CharField(
        max_length=20,
        choices=SignalType.choices,
        db_index=True,
        verbose_name=_("Signal Type"),
    )
    value = models.CharField(
        max_length=500,
        verbose_name=_("Signal Value"),
        help_text=_("The actual signal value or description."),
    )
    weight = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        verbose_name=_("Signal Weight"),
        help_text=_("Weight/importance of this signal (0.0-10.0)."),
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=_CONF_VALIDATORS,
        verbose_name=_("Signal Confidence"),
        help_text=_("Confidence in this signal detection (0.0-1.0)."),
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Signal Source"),
        help_text=_("Source that generated this signal (e.g., model name, rule ID)."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Signal Metadata"),
        help_text=_("Additional data about this signal."),
    )
    is_positive = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Positive Signal"),
        help_text=_("True if this signal indicates problematic content."),
    )
    severity = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
        db_index=True,
        verbose_name=_("Signal Severity"),
        help_text=_("Severity level of this signal."),
    )
    processed = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Processed"),
        help_text=_("True if this signal has been processed in decision making."),
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Processed At"),
        help_text=_("When this signal was processed."),
    )

    objects = ContentSignalManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name = _("Content Signal")
        verbose_name_plural = _("Content Signals")
        indexes = [
            models.Index(fields=["submission", "signal_type"], name='idx_submission_signal_type_842'),
            models.Index(fields=["signal_type", "is_positive"], name='idx_signal_positive_843'),
            models.Index(fields=["weight", "confidence"], name='idx_weight_confidence_844'),
            models.Index(fields=["severity", "processed"], name='idx_severity_processed_845'),
            models.Index(fields=["created_at"], name='idx_created_at_846'),
        ]
        ordering = ["-weight", "-created_at"]

    def __str__(self) -> str:
        pos_neg = "+" if self.is_positive else "-"
        return f"Signal[{self.signal_type}] {pos_neg} {self.value[:30]}… (w={self.weight})"

    @property
    def impact_score(self) -> float:
        """Calculate the impact score of this signal."""
        base_score = self.weight
        if self.confidence is not None:
            base_score *= self.confidence
        
        # Apply severity multiplier
        severity_multipliers = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 1.5,
            RiskLevel.HIGH: 2.0,
            RiskLevel.CRITICAL: 3.0,
        }
        
        return base_score * severity_multipliers.get(self.severity, 1.0)

    def mark_processed(self) -> None:
        """Mark this signal as processed."""
        from django.utils import timezone
        self.processed = True
        self.processed_at = timezone.now()

    @classmethod
    def create_signal(
        cls,
        submission: SuspiciousSubmission,
        signal_type: str,
        value: str,
        weight: float = 1.0,
        confidence: float = None,
        source: str = "",
        metadata: dict = None,
        is_positive: bool = True,
        severity: str = RiskLevel.LOW,
    ) -> "ContentSignal":
        """Create a new content signal."""
        return cls.objects.create(
            submission=submission,
            signal_type=signal_type,
            value=value,
            weight=weight,
            confidence=confidence,
            source=source,
            metadata=metadata or {},
            is_positive=is_positive,
            severity=severity,
        )


# =============================================================================
# Compliance-related models
# (also defined in compliance.py for backwards compat — models.py is canonical)
# =============================================================================

class ModerationRule(models.Model):
    """Rule used by compliance/moderation systems."""
    name        = models.CharField(max_length=200)
    rule_type   = models.CharField(max_length=50)
    criteria    = models.JSONField(default=dict, blank=True)
    action      = models.CharField(max_length=50)
    severity    = models.CharField(max_length=20, default="medium")
    automated   = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_mod_rules",
        verbose_name=_("Created By"),
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "auto_mod"
        verbose_name = _("Moderation Rule")
        verbose_name_plural = _("Moderation Rules")

    def __str__(self):
        return f"ModerationRule: {self.name}"


class ModerationAction(models.Model):
    """Recorded action taken by a moderator or automated system."""
    moderator        = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="moderation_actions_done",
    )
    target_user      = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="moderation_actions_received",
    )
    action_type      = models.CharField(max_length=50)
    content_type     = models.CharField(max_length=50)
    content_id       = models.CharField(max_length=200)
    reason           = models.TextField(blank=True, default="")
    automated        = models.BooleanField(default=False)
    confidence_score = models.FloatField(null=True, blank=True)
    human_reviewed   = models.BooleanField(default=False)
    user_group       = models.CharField(max_length=100, blank=True, default="")
    rule             = models.ForeignKey(
        ModerationRule, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="actions",
    )
    created_by       = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_mod_actions",
    )
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "auto_mod"
        verbose_name = _("Moderation Action")
        verbose_name_plural = _("Moderation Actions")

    def __str__(self):
        return f"ModerationAction: {self.action_type} on {self.content_id}"


class ModerationLog(models.Model):
    """Tamper-evident log entry for compliance audit trails."""
    moderator    = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="mod_logs",
    )
    user         = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="mod_logs_received",
    )
    action       = models.CharField(max_length=50)
    reason       = models.TextField(blank=True, default="")
    content_type = models.CharField(max_length=50)
    content_id   = models.CharField(max_length=200)
    automated    = models.BooleanField(default=False)
    created_at   = models.DateTimeField(default=None, null=True, blank=True)

    class Meta:
        app_label = "auto_mod"
        verbose_name = _("Moderation Log")
        verbose_name_plural = _("Moderation Logs")

    def save(self, *args, **kwargs):
        if self.created_at is None:
            from django.utils import timezone
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ModerationLog: {self.action} on {self.content_id}"


class ContentFlag(models.Model):
    """User-submitted flag for a piece of content."""
    user         = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="content_flags",
    )
    content_type = models.CharField(max_length=50)
    content_id   = models.CharField(max_length=200)
    flag_type    = models.CharField(max_length=50)
    reason       = models.TextField(blank=True, default="")
    status       = models.CharField(max_length=20, default="pending")
    created_by   = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_flags",
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "auto_mod"
        verbose_name = _("Content Flag")
        verbose_name_plural = _("Content Flags")

    def __str__(self):
        return f"ContentFlag: {self.flag_type} on {self.content_id}"


class AutoModerationQueue(models.Model):
    """Lightweight queue for auto-moderation pipeline entries."""
    content_type = models.CharField(max_length=50)
    content_id   = models.CharField(max_length=200)
    status       = models.CharField(max_length=20, default="pending")
    priority     = models.PositiveSmallIntegerField(default=5)
    assigned_to  = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="auto_mod_queue",
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "auto_mod"
        verbose_name = _("Auto Moderation Queue")
        verbose_name_plural = _("Auto Moderation Queues")

    def __str__(self):
        return f"AutoModerationQueue: {self.content_id} [{self.status}]"


class ModerationStats(models.Model):
    """Aggregated statistics for a moderation period."""
    period_start   = models.DateTimeField()
    period_end     = models.DateTimeField()
    total_actions  = models.PositiveIntegerField(default=0)
    auto_actions   = models.PositiveIntegerField(default=0)
    human_actions  = models.PositiveIntegerField(default=0)
    appeals_filed  = models.PositiveIntegerField(default=0)
    data           = models.JSONField(default=dict, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "auto_mod"
        verbose_name = _("Moderation Stats")
        verbose_name_plural = _("Moderation Stats")

    def __str__(self):
        return f"ModerationStats: {self.period_start.date()} → {self.period_end.date()}"
