# api/djoyalty/constants.py
"""
Djoyalty -- system-wide constants।
Business logic defaults, thresholds, and configuration values।
"""
from decimal import Decimal

# ─── Points Engine Defaults ───
DEFAULT_EARN_RATE = Decimal('1')          # 1 point per 1 currency unit
DEFAULT_POINT_VALUE = Decimal('0.01')     # 1 point = 0.01 currency
DEFAULT_POINTS_EXPIRY_DAYS = 365          # Points expire in 1 year

# ─── Tier Thresholds (lifetime_earned points) ───
TIER_THRESHOLDS = {
    'bronze':   Decimal('0'),
    'silver':   Decimal('500'),
    'gold':     Decimal('2000'),
    'platinum': Decimal('10000'),
    'diamond':  Decimal('50000'),
}

# Tier order -- for progression logic
TIER_ORDER = ['bronze', 'silver', 'gold', 'platinum', 'diamond']

# Tier multipliers -- bonus earn rate per tier
TIER_MULTIPLIERS = {
    'bronze':   Decimal('1.0'),
    'silver':   Decimal('1.2'),
    'gold':     Decimal('1.5'),
    'platinum': Decimal('2.0'),
    'diamond':  Decimal('3.0'),
}

# ─── Redemption Limits ───
MIN_REDEMPTION_POINTS = Decimal('100')       # Minimum points to redeem
MAX_REDEMPTION_PER_DAY = Decimal('50000')    # Max per day per customer
REDEMPTION_AUTO_APPROVE_THRESHOLD = Decimal('1000')  # Auto-approve below this

# ─── Referral Bonuses ───
REFERRAL_BONUS_REFERRER = Decimal('200')    # Points for the person who referred
REFERRAL_BONUS_REFEREE = Decimal('100')     # Points for the new customer

# ─── Voucher Defaults ───
VOUCHER_DEFAULT_VALIDITY_DAYS = 90           # Default voucher validity

# ─── Streak Configuration ───
STREAK_RESET_AFTER_DAYS = 1                 # Break after missing N days
STREAK_MILESTONES = {
    7:   Decimal('50'),     # 7-day streak -> 50 bonus points
    30:  Decimal('200'),    # 30-day streak -> 200 bonus points
    100: Decimal('500'),    # 100-day streak -> 500 bonus points
    365: Decimal('2000'),   # 365-day streak -> 2000 bonus points
}

# ─── Points Expiry Warning ───
POINTS_EXPIRY_WARNING_DAYS = 30             # Warn N days before expiry

# ─── Fraud Detection ───
FRAUD_RAPID_TXN_COUNT = 10                  # Flag if N transactions in window
FRAUD_RAPID_TXN_WINDOW_MINUTES = 15         # Window for rapid txn check
FRAUD_MAX_DAILY_REDEMPTION = Decimal('10000')  # Max redemption per day (fraud cap)

# ─── Webhook ───
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_BACKOFF_SECONDS = [30, 120, 600]   # 30s, 2min, 10min

# ─── Cache TTL (seconds) ───
CACHE_TTL_TIER = 3600           # 1 hour
CACHE_TTL_BALANCE = 300         # 5 minutes
CACHE_TTL_LEADERBOARD = 1800    # 30 minutes
CACHE_TTL_CAMPAIGNS = 600       # 10 minutes

# ─── Pagination ───
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
LEDGER_PAGE_SIZE = 50

# ─── Transfer ───
MAX_TRANSFER_PER_DAY = Decimal('5000')
TRANSFER_FEE_PERCENT = Decimal('0')         # 0% fee (set to charge if needed)

# ─── Gift Card ───
GIFT_CARD_CODE_LENGTH = 16
GIFT_CARD_DEFAULT_VALIDITY_DAYS = 365

# ─── Points Reservation ───
RESERVATION_DEFAULT_HOLD_MINUTES = 30

# ─── Admin Adjustment ───
MAX_ADMIN_ADJUSTMENT_PER_REQUEST = Decimal('100000')

# ─── Subscription Plans ───
SUBSCRIPTION_PLANS = {
    'basic': {
        'multiplier': Decimal('1.5'),
        'monthly_fee': Decimal('9.99'),
        'bonus_points_monthly': Decimal('100'),
    },
    'premium': {
        'multiplier': Decimal('2.0'),
        'monthly_fee': Decimal('19.99'),
        'bonus_points_monthly': Decimal('300'),
    },
    'vip': {
        'multiplier': Decimal('3.0'),
        'monthly_fee': Decimal('49.99'),
        'bonus_points_monthly': Decimal('1000'),
    },
}

# ─── Leaderboard ───
LEADERBOARD_DEFAULT_LIMIT = 10
LEADERBOARD_MAX_LIMIT = 100

# ─── Partner Merchant ───
PARTNER_DEFAULT_EARN_RATE = Decimal('1.0')
PARTNER_DEFAULT_BURN_RATE = Decimal('1.0')

# ─── Insight ───
INSIGHT_DEFAULT_PERIOD = 'daily'

# ─── Tenant ───
DEFAULT_TENANT_SLUG = 'default'

# ─── API Rate Limits ───
THROTTLE_RATE_USER = '1000/hour'
THROTTLE_RATE_BURST = '60/min'
THROTTLE_RATE_PUBLIC = '200/hour'

# ─── Security ───
API_KEY_LENGTH = 40
HMAC_SECRET_LENGTH = 32

# ─── Downgrade Protection ───
TIER_DOWNGRADE_PROTECTION_MONTHS = 3

# ─── Earn Rule Condition ───
EARN_CONDITION_MIN_AMOUNT = 'min_amount'
EARN_CONDITION_TIER = 'tier'
EARN_CONDITION_DAY = 'day'
EARN_CONDITION_OFFER = 'offer'

# Transfer limits
MAX_DAILY_TRANSFER_POINTS = Decimal('5000')   # Max P2P transfer per day per customer
