# api/djoyalty/constants.py
"""
সব system-wide numeric/string constants — magic numbers নেই।
"""

from decimal import Decimal


# ==================== POINTS ENGINE ====================

# ১ টাকা খরচে কত পয়েন্ট পাওয়া যাবে (default)
DEFAULT_EARN_RATE = Decimal('1.0')  # 1 point per 1 unit spend

# ১ পয়েন্টের মূল্য (টাকায়)
DEFAULT_POINT_VALUE = Decimal('0.01')  # 1 point = 0.01 currency unit

# সর্বনিম্ন redeem পরিমাণ
MIN_REDEMPTION_POINTS = 100

# একবারে সর্বোচ্চ redeem পরিমাণ
MAX_REDEMPTION_POINTS = 100_000

# পয়েন্ট expiry (দিনে) — 0 মানে কখনো expire হবে না
DEFAULT_POINTS_EXPIRY_DAYS = 365  # ১ বছর

# Warning পাঠানো হবে expiry এর কত দিন আগে
POINTS_EXPIRY_WARNING_DAYS = 30

# ==================== TIER THRESHOLDS ====================

TIER_THRESHOLDS = {
    'bronze': Decimal('0'),
    'silver': Decimal('500'),
    'gold': Decimal('2000'),
    'platinum': Decimal('5000'),
    'diamond': Decimal('10000'),
}

# Tier evaluation period (মাসে)
TIER_EVALUATION_PERIOD_MONTHS = 12

# Tier downgrade protection period (মাসে)
TIER_DOWNGRADE_PROTECTION_MONTHS = 3

# ==================== EARN RULES ====================

# Default multipliers per tier
TIER_EARN_MULTIPLIERS = {
    'bronze': Decimal('1.0'),
    'silver': Decimal('1.25'),
    'gold': Decimal('1.5'),
    'platinum': Decimal('2.0'),
    'diamond': Decimal('3.0'),
}

# Birthday bonus points
BIRTHDAY_BONUS_POINTS = Decimal('200')

# Signup bonus points
SIGNUP_BONUS_POINTS = Decimal('100')

# Referral bonus — referrer পাবে
REFERRAL_BONUS_REFERRER = Decimal('150')

# Referral bonus — নতুন customer পাবে
REFERRAL_BONUS_REFEREE = Decimal('50')

# ==================== STREAK ====================

# Streak reset হবে যদি consecutive দিন miss হয়
STREAK_RESET_AFTER_DAYS = 1  # ১ দিন miss = reset

# Streak milestone rewards (streak_days → bonus_points)
STREAK_MILESTONES = {
    7: Decimal('50'),    # ৭ দিন = ৫০ পয়েন্ট
    30: Decimal('200'),  # ৩০ দিন = ২০০ পয়েন্ট
    90: Decimal('500'),  # ৯০ দিন = ৫০০ পয়েন্ট
    365: Decimal('2000'),  # ১ বছর = ২০০০ পয়েন্ট
}

# ==================== VOUCHER ====================

# Voucher code length
VOUCHER_CODE_LENGTH = 12

# Voucher default validity (দিনে)
VOUCHER_DEFAULT_VALIDITY_DAYS = 30

# Gift card minimum value
GIFT_CARD_MIN_VALUE = Decimal('50')

# Gift card maximum value
GIFT_CARD_MAX_VALUE = Decimal('10000')

# ==================== FRAUD DETECTION ====================

# একদিনে এই পরিমাণের বেশি redeem করলে flag
FRAUD_MAX_DAILY_REDEMPTION = Decimal('5000')

# এই সময়ের মধ্যে এতটি transaction হলে flag (মিনিটে)
FRAUD_RAPID_TXN_WINDOW_MINUTES = 5
FRAUD_RAPID_TXN_COUNT = 10

# অস্বাভাবিক earn rate (একটি purchase এ এতটির বেশি পয়েন্ট)
FRAUD_MAX_SINGLE_EARN = Decimal('10000')

# ==================== CAMPAIGN ====================

# Campaign participant max (0 = unlimited)
CAMPAIGN_MAX_PARTICIPANTS_DEFAULT = 0

# Campaign max duration (দিনে)
CAMPAIGN_MAX_DURATION_DAYS = 365

# ==================== PAGINATION ====================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ==================== CACHE TTL (seconds) ====================

CACHE_TTL_CUSTOMER_BALANCE = 60 * 5       # ৫ মিনিট
CACHE_TTL_TIER_INFO = 60 * 60             # ১ ঘন্টা
CACHE_TTL_LEADERBOARD = 60 * 60           # ১ ঘন্টা
CACHE_TTL_EARN_RULES = 60 * 30            # ৩০ মিনিট
CACHE_TTL_CAMPAIGN_ACTIVE = 60 * 10       # ১০ মিনিট

# ==================== WEBHOOK ====================

WEBHOOK_MAX_RETRIES = 5
WEBHOOK_RETRY_BACKOFF_SECONDS = [10, 30, 60, 300, 900]  # exponential
WEBHOOK_TIMEOUT_SECONDS = 10
WEBHOOK_SECRET_LENGTH = 32

# ==================== TRANSFER ====================

# নিজের কাছে transfer করা যাবে না
TRANSFER_MIN_POINTS = Decimal('10')
TRANSFER_MAX_POINTS = Decimal('50000')

# ==================== PARTNER ====================

# Partner sync interval (মিনিটে)
PARTNER_SYNC_INTERVAL_MINUTES = 60

# ==================== REDEMPTION ====================

# Auto-approve হবে যদি পয়েন্ট এর বেশি না হয়
REDEMPTION_AUTO_APPROVE_THRESHOLD = Decimal('1000')

# ==================== GDPR / DATA EXPORT ====================

# Export file validity (ঘন্টায়)
DATA_EXPORT_EXPIRY_HOURS = 24

# ==================== SYSTEM ====================

DJOYALTY_VERSION = '1.0.0'
DJOYALTY_APP_LABEL = 'djoyalty'

# Points decimal places
POINTS_DECIMAL_PLACES = 2
POINTS_MAX_DIGITS = 12
