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
