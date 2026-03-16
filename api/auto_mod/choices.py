# =============================================================================
# auto_mod/choices.py
# =============================================================================

from django.db import models


class SubmissionType(models.TextChoices):
    TASK_PROOF    = "task_proof",    "Task Proof"
    USER_CONTENT  = "user_content",  "User Content"
    PROFILE       = "profile",       "Profile"
    REPORT        = "report",        "Report"
    COMMENT       = "comment",       "Comment"
    MEDIA         = "media",         "Media Upload"


class ModerationStatus(models.TextChoices):
    PENDING         = "pending",          "Pending"
    SCANNING        = "scanning",         "AI Scanning"
    AUTO_APPROVED   = "auto_approved",    "Auto-Approved"
    AUTO_REJECTED   = "auto_rejected",    "Auto-Rejected"
    HUMAN_REVIEW    = "human_review",     "Awaiting Human Review"
    HUMAN_APPROVED  = "human_approved",   "Human-Approved"
    HUMAN_REJECTED  = "human_rejected",   "Human-Rejected"
    ESCALATED       = "escalated",        "Escalated"
    EXPIRED         = "expired",          "Expired"


class RiskLevel(models.TextChoices):
    LOW      = "low",      "Low"
    MEDIUM   = "medium",   "Medium"
    HIGH     = "high",     "High"
    CRITICAL = "critical", "Critical"


class RuleConditionOperator(models.TextChoices):
    EQUALS          = "eq",         "Equals"
    NOT_EQUALS      = "neq",        "Not Equals"
    CONTAINS        = "contains",   "Contains"
    NOT_CONTAINS    = "not_contains","Does Not Contain"
    REGEX           = "regex",      "Regex Match"
    GT              = "gt",         "Greater Than"
    LT              = "lt",         "Less Than"
    GTE             = "gte",        "Greater Than or Equal"
    LTE             = "lte",        "Less Than or Equal"
    IN              = "in",         "In List"
    NOT_IN          = "not_in",     "Not In List"


class RuleAction(models.TextChoices):
    APPROVE        = "approve",        "Auto-Approve"
    REJECT         = "reject",         "Auto-Reject"
    FLAG           = "flag",           "Flag for Review"
    ESCALATE       = "escalate",       "Escalate"
    REQUEST_PROOF  = "request_proof",  "Request Additional Proof"
    NOTIFY_ADMIN   = "notify_admin",   "Notify Admin"


class ScanType(models.TextChoices):
    IMAGE    = "image",    "Image Scan"
    TEXT     = "text",     "Text Analysis"
    OCR      = "ocr",      "OCR Extraction"
    COMBINED = "combined", "Combined (Image + Text)"


class BotStatus(models.TextChoices):
    IDLE       = "idle",       "Idle"
    RUNNING    = "running",    "Running"
    PAUSED     = "paused",     "Paused"
    ERROR      = "error",      "Error"
    DISABLED   = "disabled",   "Disabled"


class FlagReason(models.TextChoices):
    SPAM             = "spam",             "Spam"
    FAKE_PROOF       = "fake_proof",       "Fake Proof"
    INAPPROPRIATE    = "inappropriate",    "Inappropriate Content"
    DUPLICATE        = "duplicate",        "Duplicate Submission"
    POLICY_VIOLATION = "policy_violation", "Policy Violation"
    SUSPICIOUS_PATTERN = "suspicious_pattern", "Suspicious Pattern"
    LOW_QUALITY      = "low_quality",      "Low Quality"
    OTHER            = "other",            "Other"


class ModelTrainingStatus(models.TextChoices):
    IDLE       = "idle",       "Idle"
    TRAINING   = "training",   "Training"
    VALIDATING = "validating", "Validating"
    DEPLOYED   = "deployed",   "Deployed"
    FAILED     = "failed",     "Failed"
