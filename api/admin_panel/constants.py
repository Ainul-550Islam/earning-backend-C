# api/admin_panel/constants.py
"""
Constants for the admin_panel app.
CPAlead-style earning platform.
"""

# ==================== Cache Keys ====================

CACHE_KEY_SYSTEM_SETTINGS = 'admin_panel:system_settings'
CACHE_KEY_FEATURE_FLAGS = 'admin_panel:feature_flags'
CACHE_KEY_DASHBOARD_STATS = 'admin_panel:dashboard_stats:{period}'
CACHE_KEY_ACTIVE_SESSIONS = 'admin_panel:active_sessions'
CACHE_KEY_ENDPOINT_TOGGLES = 'admin_panel:endpoint_toggles'
CACHE_KEY_CONFIG = 'admin_panel:config:{key}'
CACHE_KEY_REPORT = 'admin_panel:report:{report_id}'
CACHE_KEY_SYSTEM_HEALTH = 'admin_panel:system_health'

# Cache TTL (seconds)
CACHE_TTL_SETTINGS = 3600          # 1 hour
CACHE_TTL_FEATURE_FLAGS = 300      # 5 minutes
CACHE_TTL_DASHBOARD = 300          # 5 minutes
CACHE_TTL_SYSTEM_HEALTH = 60       # 1 minute
CACHE_TTL_CONFIG = 600             # 10 minutes
CACHE_TTL_ENDPOINT_TOGGLE = 30     # 30 seconds

# ==================== Pagination ====================

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200
ADMIN_PAGE_SIZE = 50

# ==================== Activity Log ====================

ACTIVITY_LOG_RETENTION_DAYS = 90       # Keep logs for 90 days
SESSION_RETENTION_DAYS = 30            # Keep session logs for 30 days
SEARCH_HISTORY_RETENTION_DAYS = 7      # Keep search history for 7 days
REPORT_FILE_RETENTION_DAYS = 7         # Reports expire after 7 days
EXPORT_FILE_RETENTION_DAYS = 3         # Exports expire after 3 days

# ==================== Dashboard ====================

DASHBOARD_REFRESH_INTERVAL_SECONDS = 300   # 5 min
DASHBOARD_METRICS_PERIODS = ['1h', '24h', '7d', '30d', '90d', '1y']
MAX_DASHBOARD_WIDGETS = 20
MAX_QUICK_ACTIONS = 10
DASHBOARD_ALERT_CHECK_INTERVAL = 60        # seconds

# ==================== Report ====================

REPORT_MAX_ROWS = 100_000
REPORT_CHUNK_SIZE = 1000
REPORT_ALLOWED_FORMATS = ['csv', 'xlsx', 'pdf', 'json']
MAX_SCHEDULED_REPORTS_PER_USER = 10

# ==================== Search ====================

SEARCH_MIN_QUERY_LENGTH = 2
SEARCH_MAX_RESULTS_PER_MODEL = 20
SEARCH_GLOBAL_MAX_RESULTS = 100

# Global searchable models registry
GLOBAL_SEARCH_MODELS = [
    'users.User',
    'users.UserProfile',
    'transactions.Transaction',
    'withdrawals.Withdrawal',
    'admin_panel.Report',
    'admin_panel.SiteContent',
    'admin_panel.SiteNotification',
]

# ==================== Bulk Actions ====================

BULK_ACTION_MAX_IDS = 500   # max records per bulk action

# ==================== Feature Flag ====================

FEATURE_FLAG_ROLLOUT_MIN = 0
FEATURE_FLAG_ROLLOUT_MAX = 100

# Built-in feature flag keys
FLAG_REFERRAL_SYSTEM = 'referral_system'
FLAG_LEADERBOARD = 'leaderboard'
FLAG_DAILY_BONUS = 'daily_bonus'
FLAG_PUSH_NOTIFICATIONS = 'push_notifications'
FLAG_TWO_FACTOR_AUTH = 'two_factor_auth'
FLAG_MAINTENANCE_MODE = 'maintenance_mode'
FLAG_API_RATE_LIMITING = 'api_rate_limiting'
FLAG_FRAUD_DETECTION = 'fraud_detection'
FLAG_VPN_BLOCK = 'vpn_block'
FLAG_AUTO_WITHDRAWAL = 'auto_withdrawal'

# ==================== Maintenance ====================

MAINTENANCE_BYPASS_IPS = []  # IPs that bypass maintenance mode
MAINTENANCE_BYPASS_PATHS = [
    '/admin/',
    '/api/admin-panel/',
    '/api/auth/admin/',
    '/api/schema/',
    '/api/docs/',
    '/static/',
    '/media/',
]

# ==================== System Health Checks ====================

HEALTH_CHECK_SERVICES = [
    'database',
    'cache',
    'celery',
    'storage',
    'email',
]

HEALTH_STATUS_HEALTHY = 'healthy'
HEALTH_STATUS_DEGRADED = 'degraded'
HEALTH_STATUS_DOWN = 'down'
HEALTH_STATUS_UNKNOWN = 'unknown'

# ==================== Notifications / Digest ====================

ADMIN_DIGEST_SEND_HOUR = 8   # 8 AM local time
ADMIN_INSIGHT_GENERATE_HOUR = 2  # 2 AM local time

# ==================== Rate Limiting ====================

API_DEFAULT_THROTTLE_RATE = '100/hour'
API_BURST_THROTTLE_RATE = '30/minute'
ADMIN_API_THROTTLE_RATE = '500/hour'

# ==================== File Upload ====================

REPORT_UPLOAD_PATH = 'reports/'
EXPORT_UPLOAD_PATH = 'exports/'
ADMIN_AVATAR_UPLOAD_PATH = 'admin_avatars/'

MAX_REPORT_FILE_SIZE_MB = 50
MAX_EXPORT_FILE_SIZE_MB = 200

# ==================== Email ====================

EMAIL_SUBJECT_PREFIX = '[Admin Panel] '
REPORT_EMAIL_SUBJECT = 'Your Report is Ready'
DIGEST_EMAIL_SUBJECT = 'Daily Admin Digest'
MAINTENANCE_EMAIL_SUBJECT = 'Scheduled Maintenance Notice'
INSIGHT_EMAIL_SUBJECT = 'New Admin Insight'

# ==================== Celery Task Names ====================

TASK_DASHBOARD_REFRESH = 'admin_panel.tasks.dashboard_refresh_tasks.refresh_dashboard_kpis'
TASK_REPORT_GENERATE = 'admin_panel.tasks.report_generation_tasks.generate_report_task'
TASK_DATA_EXPORT = 'admin_panel.tasks.data_export_tasks.process_data_export'
TASK_INSIGHT_GENERATE = 'admin_panel.tasks.insight_tasks.generate_daily_insights'
TASK_ACTIVITY_CLEANUP = 'admin_panel.tasks.activity_cleanup_tasks.cleanup_old_activity'
TASK_SESSION_CLEANUP = 'admin_panel.tasks.session_cleanup_tasks.cleanup_stale_sessions'
TASK_CONFIG_CACHE_REFRESH = 'admin_panel.tasks.config_cache_tasks.refresh_config_cache'
TASK_SYSTEM_HEALTH = 'admin_panel.tasks.system_health_tasks.check_system_health'
TASK_ADMIN_DIGEST = 'admin_panel.tasks.admin_digest_tasks.send_admin_digest'