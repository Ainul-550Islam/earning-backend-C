# =============================================================================
# behavior_analytics/choices.py
# =============================================================================
"""
Django TextChoices / IntegerChoices for all enum-like fields in this app.
Using Django's built-in Choices classes ensures DB-level validation, clean
admin display, and type-safe usage throughout the codebase.
"""

from django.db import models


class EngagementTier(models.TextChoices):
    """Human-readable engagement band derived from the numeric score."""
    LOW    = "low",    "Low (0–30)"
    MEDIUM = "medium", "Medium (31–60)"
    HIGH   = "high",   "High (61–85)"
    ELITE  = "elite",  "Elite (86–100)"


class DeviceType(models.TextChoices):
    DESKTOP = "desktop", "Desktop"
    MOBILE  = "mobile",  "Mobile"
    TABLET  = "tablet",  "Tablet"
    UNKNOWN = "unknown", "Unknown"


class SessionStatus(models.TextChoices):
    ACTIVE    = "active",    "Active"
    COMPLETED = "completed", "Completed"
    BOUNCED   = "bounced",   "Bounced"
    EXPIRED   = "expired",   "Expired"


class ClickCategory(models.TextChoices):
    NAVIGATION = "navigation", "Navigation"
    CTA        = "cta",        "Call-to-Action"
    LINK       = "link",       "Hyperlink"
    BUTTON     = "button",     "Button"
    FORM       = "form",       "Form Element"
    MEDIA      = "media",      "Media Control"
    OTHER      = "other",      "Other"


class ReportStatus(models.TextChoices):
    PENDING    = "pending",    "Pending"
    PROCESSING = "processing", "Processing"
    READY      = "ready",      "Ready"
    FAILED     = "failed",     "Failed"
    ARCHIVED   = "archived",   "Archived"


class PathNodeType(models.TextChoices):
    ENTRY      = "entry",      "Entry Point"
    NAVIGATION = "navigation", "Navigation Step"
    CONVERSION = "conversion", "Conversion Event"
    EXIT       = "exit",       "Exit Point"
    ERROR      = "error",      "Error Page"
