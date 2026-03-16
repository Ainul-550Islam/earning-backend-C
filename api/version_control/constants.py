# =============================================================================
# version_control/constants.py
# =============================================================================
"""
Module-level constants for the version_control (App Update) application.
"""

# ---------------------------------------------------------------------------
# Version string patterns
# ---------------------------------------------------------------------------
VERSION_REGEX: str = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9._-]+)?(\+[a-zA-Z0-9._-]+)?$"
MAX_VERSION_LENGTH: int = 32          # e.g. "10.99.999-alpha.1+build.20240315"

# ---------------------------------------------------------------------------
# Platform identifiers
# ---------------------------------------------------------------------------
PLATFORM_IOS     = "ios"
PLATFORM_ANDROID = "android"
PLATFORM_WEB     = "web"
PLATFORM_WINDOWS = "windows"
PLATFORM_MACOS   = "macos"
PLATFORM_LINUX   = "linux"
ALL_PLATFORMS    = (PLATFORM_IOS, PLATFORM_ANDROID, PLATFORM_WEB,
                    PLATFORM_WINDOWS, PLATFORM_MACOS, PLATFORM_LINUX)

# ---------------------------------------------------------------------------
# Update policy
# ---------------------------------------------------------------------------
UPDATE_TYPE_OPTIONAL  = "optional"
UPDATE_TYPE_REQUIRED  = "required"
UPDATE_TYPE_CRITICAL  = "critical"      # blocks app usage until updated

# ---------------------------------------------------------------------------
# Maintenance window
# ---------------------------------------------------------------------------
MAINTENANCE_MAX_DURATION_HOURS: int = 24
MAINTENANCE_WARNING_ADVANCE_MINUTES: int = 30   # warn users this many minutes before

# ---------------------------------------------------------------------------
# Cache keys & TTLs
# ---------------------------------------------------------------------------
CACHE_KEY_UPDATE_POLICY: str    = "version_control:policy:{platform}:{app_version}"
CACHE_KEY_MAINTENANCE: str      = "version_control:maintenance:active"
CACHE_KEY_REDIRECT: str         = "version_control:redirect:{platform}"

CACHE_TTL_UPDATE_POLICY: int    = 300      # 5 min — frequent checks by mobile clients
CACHE_TTL_MAINTENANCE: int      = 60       # 1 min — needs to be near-real-time
CACHE_TTL_REDIRECT: int         = 3_600    # 1 hour

# ---------------------------------------------------------------------------
# Celery task names
# ---------------------------------------------------------------------------
TASK_CHECK_UPDATES: str          = "version_control.tasks.check_updates"
TASK_SCHEDULE_MAINTENANCE: str   = "version_control.tasks.schedule_maintenance_notification"
TASK_END_MAINTENANCE: str        = "version_control.tasks.end_maintenance"
TASK_CLEANUP_OLD_POLICIES: str   = "version_control.tasks.cleanup_old_policies"

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
VERSION_HEADER_CLIENT: str       = "X-App-Version"
VERSION_HEADER_PLATFORM: str     = "X-App-Platform"
MAINTENANCE_BYPASS_HEADER: str   = "X-Maintenance-Bypass"  # staff only
MAINTENANCE_RESPONSE_STATUS: int = 503

# ---------------------------------------------------------------------------
# Redirect
# ---------------------------------------------------------------------------
MAX_REDIRECT_URL_LENGTH: int     = 2_048
