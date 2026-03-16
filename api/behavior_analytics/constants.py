# =============================================================================
# behavior_analytics/constants.py
# =============================================================================
"""
Module-level constants for the behavior analytics application.
All magic numbers, strings, and configuration values live here.
Never import settings directly inside this file.
"""

from decimal import Decimal

# ---------------------------------------------------------------------------
# Engagement Score Thresholds
# ---------------------------------------------------------------------------
ENGAGEMENT_SCORE_MIN: int = 0
ENGAGEMENT_SCORE_MAX: int = 100

ENGAGEMENT_TIER_LOW: int = 30
ENGAGEMENT_TIER_MEDIUM: int = 60
ENGAGEMENT_TIER_HIGH: int = 85

# ---------------------------------------------------------------------------
# Stay / Session Time  (seconds)
# ---------------------------------------------------------------------------
STAY_TIME_MIN_SECONDS: int = 0
STAY_TIME_MAX_SECONDS: int = 86_400          # 24 h hard-cap
STAY_TIME_BOUNCE_THRESHOLD: int = 10         # < 10 s  → bounce
STAY_TIME_SHORT_SESSION: int = 60
STAY_TIME_MEDIUM_SESSION: int = 300
STAY_TIME_LONG_SESSION: int = 1_800

# ---------------------------------------------------------------------------
# Path / Click Limits
# ---------------------------------------------------------------------------
MAX_PATH_NODES: int = 500
MAX_CLICK_METRICS_PER_SESSION: int = 2_000
MAX_URL_LENGTH: int = 2_048

# ---------------------------------------------------------------------------
# Celery Task Names
# ---------------------------------------------------------------------------
TASK_CALCULATE_ENGAGEMENT: str = "behavior_analytics.tasks.calculate_engagement_score"
TASK_PROCESS_CLICK_BATCH: str  = "behavior_analytics.tasks.process_click_batch"
TASK_GENERATE_DAILY_REPORT: str  = "behavior_analytics.tasks.generate_daily_report"
TASK_GENERATE_WEEKLY_REPORT: str = "behavior_analytics.tasks.generate_weekly_report"
TASK_CLEANUP_OLD_PATHS: str     = "behavior_analytics.tasks.cleanup_old_paths"

# ---------------------------------------------------------------------------
# Cache Keys & TTLs
# ---------------------------------------------------------------------------
CACHE_KEY_ENGAGEMENT_SCORE: str = "analytics:engagement:{user_id}"
CACHE_KEY_DAILY_REPORT: str     = "analytics:report:daily:{date}"
CACHE_KEY_WEEKLY_REPORT: str    = "analytics:report:weekly:{week}"
CACHE_KEY_PATH_SUMMARY: str     = "analytics:path:summary:{session_id}"

CACHE_TTL_ENGAGEMENT: int    = 3_600
CACHE_TTL_DAILY_REPORT: int  = 86_400
CACHE_TTL_WEEKLY_REPORT: int = 604_800
CACHE_TTL_PATH_SUMMARY: int  = 1_800

# ---------------------------------------------------------------------------
# Engagement Calculator Weights  (must sum to 1.00)
# ---------------------------------------------------------------------------
WEIGHT_CLICK_COUNT: Decimal   = Decimal("0.25")
WEIGHT_STAY_TIME: Decimal     = Decimal("0.35")
WEIGHT_PATH_DEPTH: Decimal    = Decimal("0.20")
WEIGHT_RETURN_VISITS: Decimal = Decimal("0.20")

# ---------------------------------------------------------------------------
# Report Retention
# ---------------------------------------------------------------------------
REPORT_DAILY_RETENTION_DAYS: int   = 90
REPORT_WEEKLY_RETENTION_WEEKS: int = 52

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
TRACKING_EXCLUDED_PATHS: tuple[str, ...] = (
    "/health/",
    "/metrics/",
    "/favicon.ico",
    "/static/",
    "/media/",
    "/admin/jsi18n/",
)
TRACKING_HEADER_SESSION: str = "X-Session-ID"
TRACKING_HEADER_DEVICE: str  = "X-Device-Type"

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int     = 200
