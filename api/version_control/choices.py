# =============================================================================
# version_control/choices.py
# =============================================================================

from django.db import models


class Platform(models.TextChoices):
    IOS     = "ios",     "iOS"
    ANDROID = "android", "Android"
    WEB     = "web",     "Web"
    WINDOWS = "windows", "Windows"
    MACOS   = "macos",   "macOS"
    LINUX   = "linux",   "Linux"


class UpdateType(models.TextChoices):
    OPTIONAL = "optional", "Optional"
    REQUIRED = "required", "Required"
    CRITICAL = "critical", "Critical (Blocking)"


class MaintenanceStatus(models.TextChoices):
    SCHEDULED  = "scheduled",  "Scheduled"
    ACTIVE     = "active",     "Active"
    COMPLETED  = "completed",  "Completed"
    CANCELLED  = "cancelled",  "Cancelled"


class RedirectType(models.TextChoices):
    STORE    = "store",    "App Store / Play Store"
    WEB      = "web",      "Web URL"
    DOWNLOAD = "download", "Direct Download"
    CUSTOM   = "custom",   "Custom"


class PolicyStatus(models.TextChoices):
    DRAFT    = "draft",    "Draft"
    ACTIVE   = "active",   "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"
