# engagement/constants.py
from decimal import Decimal

# ─── Check-In ───────────────────────────────────────────────────────────────
CHECKIN_BASE_COINS        = Decimal("5")
CHECKIN_MAX_STREAK_BONUS  = 7          # day 7+ gets same multiplier
CHECKIN_STREAK_MULTIPLIER = Decimal("1")  # coins = BASE * min(streak, 7)

# ─── Spin Wheel ──────────────────────────────────────────────────────────────
SPIN_MAX_PER_DAY = 5
SPIN_OUTCOMES    = [       # (coins, weight)
    (1,   50),
    (2,   25),
    (5,   15),
    (10,   8),
    (50,   2),
]

# ─── XP & Levels ─────────────────────────────────────────────────────────────
XP_PER_CHECKIN     = 10
XP_PER_SPIN        = 5
XP_PER_QUEST       = 50
XP_PER_CHALLENGE   = 100
LEVEL_XP_BASE      = 100       # Level 1 → 2 needs 100 XP
LEVEL_XP_GROWTH    = 1.5       # each level needs 1.5× more XP

# ─── Leaderboard ─────────────────────────────────────────────────────────────
LEADERBOARD_MAX_RANK  = 100
LEADERBOARD_TOP_REWARD = 10   # top N get rewards

# ─── Achievements ────────────────────────────────────────────────────────────
ACHIEVEMENT_TYPES = [
    ("streak",    "Streak"),
    ("spins",     "Spins"),
    ("coins",     "Coins Earned"),
    ("level",     "Level"),
    ("referral",  "Referrals"),
    ("quest",     "Quests"),
    ("purchase",  "Shop Purchase"),
    ("social",    "Social"),
]

# ─── Quests ──────────────────────────────────────────────────────────────────
QUEST_TYPES    = [("daily", "Daily"), ("weekly", "Weekly"), ("special", "Special")]
QUEST_STATUSES = [("active", "Active"), ("completed", "Completed"), ("expired", "Expired")]

# ─── Challenges ──────────────────────────────────────────────────────────────
CHALLENGE_STATUSES = [
    ("pending",   "Pending"),
    ("active",    "Active"),
    ("completed", "Completed"),
    ("forfeited", "Forfeited"),
]

# ─── Shop ────────────────────────────────────────────────────────────────────
SHOP_ITEM_TYPES = [
    ("streak_shield",  "Streak Shield"),
    ("spin_boost",     "Spin Boost"),
    ("xp_multiplier",  "XP Multiplier"),
    ("coin_pack",      "Coin Pack"),
    ("avatar_frame",   "Avatar Frame"),
    ("badge",          "Exclusive Badge"),
]

# ─── Notifications ───────────────────────────────────────────────────────────
NOTIF_TYPES = [
    ("checkin_reminder", "Check-in Reminder"),
    ("streak_at_risk",   "Streak at Risk"),
    ("level_up",         "Level Up"),
    ("achievement",      "Achievement Unlocked"),
    ("quest_complete",   "Quest Complete"),
    ("leaderboard",      "Leaderboard Update"),
    ("reward",           "Reward Received"),
    ("challenge",        "Challenge Update"),
]

# ─── Cache Keys ──────────────────────────────────────────────────────────────
CACHE_LEADERBOARD       = "engagement:leaderboard:{date}:{tenant}"
CACHE_USER_STATS        = "engagement:user_stats:{user_id}"
CACHE_STREAK            = "engagement:streak:{user_id}"
CACHE_SHOP_ITEMS        = "engagement:shop_items:{tenant}"
CACHE_ACHIEVEMENTS      = "engagement:achievements:{tenant}"
CACHE_TTL_SHORT         = 60 * 5        # 5 min
CACHE_TTL_MEDIUM        = 60 * 60       # 1 hour
CACHE_TTL_LONG          = 60 * 60 * 24  # 24 hours
