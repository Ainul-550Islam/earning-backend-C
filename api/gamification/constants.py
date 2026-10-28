"""
Gamification Constants — All magic numbers in one place.
"""

# Field length limits
MAX_CONTEST_NAME_LENGTH: int = 255
MAX_REWARD_TITLE_LENGTH: int = 255
MAX_ACHIEVEMENT_TITLE_LENGTH: int = 255
MAX_DESCRIPTION_LENGTH: int = 2000

# Points bounds (stored as INT in DB)
MIN_POINTS_VALUE: int = 0
MAX_POINTS_VALUE: int = 10_000_000

# Rank upper bound
MAX_RANK_VALUE: int = 1_000_000

# JSON metadata size cap (bytes)
MAX_META_JSON_SIZE_BYTES: int = 65_536  # 64 KB

# Leaderboard defaults
DEFAULT_LEADERBOARD_TOP_N: int = 100
LEADERBOARD_CACHE_TTL_SECONDS: int = 300  # 5 minutes

# Batch processing
MAX_BATCH_AWARD_SIZE: int = 500

# ---------------------------------------------------------------------------
# Constants for New Models
# ---------------------------------------------------------------------------

# Points transaction limits
MAX_TRANSACTION_DESCRIPTION_LENGTH: int = 500
MAX_SOURCE_ID_LENGTH: int = 255
MIN_TRANSACTION_AMOUNT: int = -1_000_000  # Allow large deductions
MAX_TRANSACTION_AMOUNT: int = 1_000_000

# Streak freeze limits
MAX_FREEZE_REASON_LENGTH: int = 255
MAX_FREEZES_PER_USER_PER_MONTH: int = 5

# Contest participant limits
MAX_CONTEST_PARTICIPANTS: int = 10_000
DEFAULT_CONTEST_POINTS: int = 0
MIN_CONTEST_POINTS: int = 0
MAX_CONTEST_POINTS: int = 100_000_000

# Gamification config limits
DEFAULT_LEADERBOARD_REFRESH_INTERVAL: int = 300  # 5 minutes
MIN_LEADERBOARD_REFRESH_INTERVAL: int = 60  # 1 minute
MAX_LEADERBOARD_REFRESH_INTERVAL: int = 3600  # 1 hour
DEFAULT_POINTS_EXPIRY_DAYS: int = 365  # 1 year
MIN_POINTS_EXPIRY_DAYS: int = 1
MAX_POINTS_EXPIRY_DAYS: int = 3650  # 10 years

# Insights calculation limits
DEFAULT_INSIGHTS_BATCH_SIZE: int = 1000
MAX_INSIGHTS_HISTORY_DAYS: int = 730  # 2 years
MIN_ENGAGEMENT_RATE: float = 0.0
MAX_ENGAGEMENT_RATE: float = 1.0

# Alert system limits
MAX_ALERT_MESSAGE_LENGTH: int = 1000
MAX_ALERT_METADATA_SIZE: int = 16384  # 16 KB
DEFAULT_ALERT_RETENTION_DAYS: int = 90

# Performance and caching limits
POINTS_CACHE_TTL_SECONDS: int = 600  # 10 minutes
TRANSACTION_CACHE_TTL_SECONDS: int = 300  # 5 minutes
LEADERBOARD_CACHE_TTL_SECONDS: int = 300  # 5 minutes
INSIGHTS_CACHE_TTL_SECONDS: int = 3600  # 1 hour

# Pagination limits
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
DEFAULT_TRANSACTION_PAGE_SIZE: int = 50
MAX_TRANSACTION_PAGE_SIZE: int = 500

# Security limits
MAX_POINTS_CHANGE_PER_TRANSACTION: int = 100_000
MAX_POINTS_CHANGE_PER_USER_PER_DAY: int = 1_000_000
RATE_LIMIT_POINTS_REQUESTS: int = 100  # per minute per user
RATE_LIMIT_CONTEST_JOINS: int = 10  # per minute per user
