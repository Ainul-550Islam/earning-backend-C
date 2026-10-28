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
    IMAGE         = "image",         "Image"
    TEXT          = "text",          "Text"


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
    NORMAL   = "normal",   "Normal"
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
    AUTO_APPROVE   = "approve_automatically", "Auto-Approve"
    AUTO_REJECT    = "auto_reject",   "Auto-Reject"
    REJECT         = "reject",         "Auto-Reject"
    FLAG           = "flag",           "Flag for Review"
    ESCALATE       = "escalate",       "Escalate"
    REQUEST_PROOF  = "request_proof",  "Request Additional Proof"
    NOTIFY_ADMIN   = "notify_admin",   "Notify Admin"


class ScanType(models.TextChoices):
    IMAGE    = "image",    "Image Scan"
    TEXT     = "text",     "Text Analysis"
    OCR      = "ocr",      "OCR Extraction"
    COMBINED       = "combined",       "Combined (Image + Text)"
    IMAGE_ANALYSIS = "image_analysis", "Image Analysis"
    TEXT_ANALYSIS  = "text_analysis",  "Text Analysis"


class BotStatus(models.TextChoices):
    IDLE       = "idle",       "Idle"
    RUNNING    = "running",    "Running"
    PAUSED     = "paused",     "Paused"
    ERROR      = "error",      "Error"
    DISABLED   = "disabled",   "Disabled"
    STOPPED    = "stopped",    "Stopped"
    FAILED     = "failed",     "Failed"


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


class QueuePriority(models.TextChoices):
    LOW      = "low",      "Low"
    NORMAL   = "normal",   "Normal"
    MEDIUM   = "medium",   "Medium"
    HIGH     = "high",     "High"
    URGENT   = "urgent",   "Urgent"
    CRITICAL = "critical", "Critical"


class DecisionType(models.TextChoices):
    APPROVE   = "approve",   "Approve"
    REJECT    = "reject",    "Reject"
    ESCALATE  = "escalate",  "Escalate"
    REQUEST_INFO = "request_info", "Request More Info"


class AppealStatus(models.TextChoices):
    PENDING      = "pending",      "Pending Review"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED     = "approved",     "Appeal Approved"
    REJECTED     = "rejected",     "Appeal Rejected"
    CLOSED       = "closed",       "Closed"
    RESOLVED     = "resolved",     "Resolved"


class ModelType(models.TextChoices):
    TEXT   = "text",   "Text Classification"
    IMAGE  = "image",  "Image Classification"
    OCR    = "ocr",    "OCR Extraction"
    COMBINED = "combined", "Combined Multi-Modal"


class SignalType(models.TextChoices):
    USER_REPORT      = "user_report",      "User Report"
    AI_DETECTION     = "ai_detection",     "AI Detection"
    PATTERN_MATCH    = "pattern_match",    "Pattern Match"
    MANUAL_FLAG      = "manual_flag",      "Manual Flag"
    SYSTEM_ALERT     = "system_alert",     "System Alert"
    CONTENT_ANALYSIS = "content_analysis", "Content Analysis"


class AppealOutcome(models.TextChoices):
    UPHELD      = "upheld",      "Appeal Upheld (Decision Overturned)"
    OVERTURNED  = "overturned",  "Appeal Overturned (Original Decision Stands)"
    PARTIAL     = "partial",     "Partial Relief Granted"
    WITHDRAWN   = "withdrawn",   "Appeal Withdrawn"


class ScanStatus(models.TextChoices):
    PENDING    = "pending",    "Pending"
    RUNNING    = "running",    "Running"
    COMPLETED  = "completed",  "Completed"
    FAILED     = "failed",     "Failed"
    SKIPPED    = "skipped",    "Skipped"
    SUCCESS    = "success",    "Success"


class TaskType(models.TextChoices):
    IMAGE_SCANNER  = "image_scanner",  "Image Scanner"
    TEXT_SCANNER   = "text_scanner",   "Text Scanner"
    OCR_SCANNER    = "ocr_scanner",    "OCR Scanner"
    RULE_ENGINE    = "rule_engine",    "Rule Engine"
    QUEUE_MANAGER  = "queue_manager",  "Queue Manager"
    CLEANUP        = "cleanup",        "Cleanup Bot"
