# api/referral/constants.py
# System-wide constants for the referral module
# ============================================================

from decimal import Decimal

# ── Commission Levels ─────────────────────────────────────────────────────────
MAX_REFERRAL_LEVELS = 3
LEVEL_1 = 1
LEVEL_2 = 2
LEVEL_3 = 3

DEFAULT_LEVEL1_RATE = Decimal('10.00')   # 10% direct
DEFAULT_LEVEL2_RATE = Decimal('5.00')    # 5% indirect
DEFAULT_LEVEL3_RATE = Decimal('2.00')    # 2% deep

# ── Fraud Detection ───────────────────────────────────────────────────────────
FRAUD_BLOCK_SCORE = 70
FRAUD_HOLD_SCORE = 40
FRAUD_FLAG_SCORE = 20
MAX_FRAUD_SCORE = 100

# Velocity: max referrals per hour before flagging
VELOCITY_THRESHOLD_PER_HOUR = 20
VELOCITY_WINDOW_MINUTES = 60

# ── Commission Hold ───────────────────────────────────────────────────────────
DEFAULT_HOLD_DAYS = 7
MIN_PAYOUT_THRESHOLD = Decimal('100.00')

# ── Referral Code ────────────────────────────────────────────────────────────
CODE_LENGTH = 8
CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # no O, 0, I, 1 (confusing)
CUSTOM_CODE_MIN_LEN = 4
CUSTOM_CODE_MAX_LEN = 30
COOKIE_NAME = 'ref_code'
COOKIE_DAYS = 30

# ── Campaign ──────────────────────────────────────────────────────────────────
MIN_CAMPAIGN_MULTIPLIER = Decimal('0.1')
MAX_CAMPAIGN_MULTIPLIER = Decimal('10.0')

# ── Cache Keys ────────────────────────────────────────────────────────────────
CACHE_SETTINGS_KEY = 'referral_settings'
CACHE_ACTIVE_CAMPAIGN_KEY = 'referral_active_campaign'
CACHE_TTL_SETTINGS = 300         # 5 minutes
CACHE_TTL_LEADERBOARD = 900      # 15 minutes
CACHE_TTL_TREE = 3600            # 1 hour

# ── Pagination ────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
LEADERBOARD_SIZE = 50

# ── Notification Types ────────────────────────────────────────────────────────
NOTIF_COMMISSION_EARNED = 'referral_commission'
NOTIF_NEW_REFERRAL = 'new_referral'
NOTIF_SIGNUP_BONUS = 'signup_bonus'
NOTIF_MILESTONE_REACHED = 'milestone_reached'
NOTIF_COMMISSION_HELD = 'commission_held'
NOTIF_COMMISSION_RELEASED = 'commission_released'
NOTIF_CAMPAIGN_STARTED = 'campaign_started'
NOTIF_CONTEST_RANK = 'contest_rank_update'
NOTIF_CONTEST_PRIZE = 'contest_prize'
NOTIF_WEEKLY_SUMMARY = 'weekly_summary'
NOTIF_FRAUD_ALERT = 'fraud_alert'

# ── Source Types ──────────────────────────────────────────────────────────────
SOURCE_TASK = 'task'
SOURCE_OFFER = 'offer'
SOURCE_WITHDRAWAL = 'withdrawal'
SOURCE_DEPOSIT = 'deposit'
SOURCE_PURCHASE = 'purchase'
SOURCE_SIGNUP = 'signup'
SOURCE_COMMISSION = 'referral_commission'
SOURCE_COMMISSION_RELEASED = 'referral_commission_released'
SOURCE_MILESTONE_BONUS = 'referral_milestone_bonus'
SOURCE_CONTEST_PRIZE = 'contest_prize'
SOURCE_PAYOUT = 'commission_payout'
SOURCE_CLAWBACK = 'referral_clawback'

# ── Status Choices ────────────────────────────────────────────────────────────
STATUS_PENDING = 'pending'
STATUS_HELD = 'held'
STATUS_RELEASED = 'released'
STATUS_CLAWED_BACK = 'clawed_back'
STATUS_CANCELLED = 'cancelled'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'

# ── Suspicious/Fraud ──────────────────────────────────────────────────────────
FRAUD_STATUS_PENDING = 'pending'
FRAUD_STATUS_REVIEWING = 'reviewing'
FRAUD_STATUS_CLEARED = 'cleared'
FRAUD_STATUS_FRAUD = 'fraud'

# ── Analytics Periods ─────────────────────────────────────────────────────────
PERIOD_DAILY = 'daily'
PERIOD_WEEKLY = 'weekly'
PERIOD_MONTHLY = 'monthly'
PERIOD_ALLTIME = 'alltime'

# ── Milestones ────────────────────────────────────────────────────────────────
MILESTONE_REFERRAL_COUNT = 'referral_count'
MILESTONE_ACTIVE_REFERRAL_COUNT = 'active_referral_count'
MILESTONE_COMMISSION_EARNED = 'commission_earned'
MILESTONE_TEAM_SIZE = 'team_size'

# ── Suspicious Email Domains ──────────────────────────────────────────────────
SUSPICIOUS_EMAIL_DOMAINS = [
    'tempmail.com', 'throwaway.email', 'guerrillamail.com',
    'mailinator.com', 'yopmail.com', '10minutemail.com',
    'trashmail.com', 'sharklasers.com', 'guerrillamailblock.com',
    'dispostable.com', 'fakeinbox.com', 'getairmail.com',
    'spamgourmet.com', 'mytrashmail.com', 'mt2015.com',
]

# ── LTV Categories ────────────────────────────────────────────────────────────
LTV_HIGH_VALUE_THRESHOLD = Decimal('1000.00')
LTV_MID_VALUE_THRESHOLD = Decimal('100.00')
LTV_CHURN_HIGH_DAYS = 30    # No activity for 30 days = high churn
LTV_CHURN_MED_DAYS = 14     # No activity for 14 days = medium churn
LTV_CHURN_CHURNED_DAYS = 60 # No activity for 60 days = churned

# ── Contest Types ─────────────────────────────────────────────────────────────
CONTEST_MOST_REFERRALS = 'most_referrals'
CONTEST_MOST_ACTIVE = 'most_active_referrals'
CONTEST_HIGHEST_COMMISSION = 'highest_commission'
CONTEST_HIGHEST_LTV = 'highest_ltv'

# ── Export ────────────────────────────────────────────────────────────────────
EXPORT_MAX_ROWS = 10000
CSV_ENCODING = 'utf-8-sig'   # BOM for Excel compatibility

# ── API Rate Limiting ─────────────────────────────────────────────────────────
RATE_LIMIT_REFERRAL_CLICK = '100/hour'
RATE_LIMIT_CODE_VALIDATE = '50/minute'

# Referral code prefix (matches users/referral/referral_code.py)
CODE_PREFIX = 'EARN'


class ReferralConstants:
    """
    Backward-compatible constants class.
    Used by api/users/referral/referral_code.py
    """
    CODE_PREFIX = CODE_PREFIX
    CODE_LENGTH = CODE_LENGTH
    COOKIE_NAME = COOKIE_NAME
    COOKIE_DAYS = COOKIE_DAYS