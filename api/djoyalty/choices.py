# api/djoyalty/choices.py
"""
Djoyalty -- all choice constants।
LedgerEntry types, sources, tier ranks, etc.
"""

# ─── Ledger Transaction Types ───
LEDGER_CREDIT = 'credit'
LEDGER_DEBIT = 'debit'

LEDGER_TXN_TYPE_CHOICES = [
    (LEDGER_CREDIT, 'Credit'),
    (LEDGER_DEBIT, 'Debit'),
]

# ─── Ledger Sources ───
LEDGER_SOURCE_PURCHASE = 'purchase'
LEDGER_SOURCE_REFERRAL = 'referral'
LEDGER_SOURCE_BONUS = 'bonus'
LEDGER_SOURCE_OFFER = 'offer'
LEDGER_SOURCE_REDEMPTION = 'redemption'
LEDGER_SOURCE_EXPIRY = 'expiry'
LEDGER_SOURCE_TRANSFER = 'transfer'
LEDGER_SOURCE_ADMIN = 'admin'
LEDGER_SOURCE_SUBSCRIPTION = 'subscription'
LEDGER_SOURCE_BADGE = 'badge'
LEDGER_SOURCE_STREAK = 'streak'
LEDGER_SOURCE_CHALLENGE = 'challenge'
LEDGER_SOURCE_MILESTONE = 'milestone'
LEDGER_SOURCE_COALITION = 'coalition'
LEDGER_SOURCE_PARTNER = 'partner'
LEDGER_SOURCE_CONVERSION = 'conversion'

LEDGER_SOURCE_CHOICES = [
    (LEDGER_SOURCE_PURCHASE, 'Purchase'),
    (LEDGER_SOURCE_REFERRAL, 'Referral'),
    (LEDGER_SOURCE_BONUS, 'Bonus'),
    (LEDGER_SOURCE_OFFER, 'Offer'),
    (LEDGER_SOURCE_REDEMPTION, 'Redemption'),
    (LEDGER_SOURCE_EXPIRY, 'Expiry'),
    (LEDGER_SOURCE_TRANSFER, 'Transfer'),
    (LEDGER_SOURCE_ADMIN, 'Admin'),
    (LEDGER_SOURCE_SUBSCRIPTION, 'Subscription'),
    (LEDGER_SOURCE_BADGE, 'Badge'),
    (LEDGER_SOURCE_STREAK, 'Streak'),
    (LEDGER_SOURCE_CHALLENGE, 'Challenge'),
    (LEDGER_SOURCE_MILESTONE, 'Milestone'),
    (LEDGER_SOURCE_COALITION, 'Coalition'),
    (LEDGER_SOURCE_PARTNER, 'Partner'),
    (LEDGER_SOURCE_CONVERSION, 'Conversion'),
]

# ─── Tier Names ───
TIER_BRONZE = 'bronze'
TIER_SILVER = 'silver'
TIER_GOLD = 'gold'
TIER_PLATINUM = 'platinum'
TIER_DIAMOND = 'diamond'

TIER_CHOICES = [
    (TIER_BRONZE, 'Bronze'),
    (TIER_SILVER, 'Silver'),
    (TIER_GOLD, 'Gold'),
    (TIER_PLATINUM, 'Platinum'),
    (TIER_DIAMOND, 'Diamond'),
]

# Tier rank mapping -- higher = better tier
TIER_RANK = {
    TIER_BRONZE: 1,
    TIER_SILVER: 2,
    TIER_GOLD: 3,
    TIER_PLATINUM: 4,
    TIER_DIAMOND: 5,
}

TIER_RANK_CHOICES = [
    (1, 'Bronze'),
    (2, 'Silver'),
    (3, 'Gold'),
    (4, 'Platinum'),
    (5, 'Diamond'),
]

# ─── Tier Change Types ───
TIER_CHANGE_UPGRADE = 'upgrade'
TIER_CHANGE_DOWNGRADE = 'downgrade'
TIER_CHANGE_INITIAL = 'initial'
TIER_CHANGE_MANUAL = 'manual'

TIER_CHANGE_CHOICES = [
    (TIER_CHANGE_UPGRADE, 'Upgrade'),
    (TIER_CHANGE_DOWNGRADE, 'Downgrade'),
    (TIER_CHANGE_INITIAL, 'Initial'),
    (TIER_CHANGE_MANUAL, 'Manual'),
]

# ─── Earn Rule Types ───
EARN_RULE_FIXED = 'fixed'
EARN_RULE_PERCENTAGE = 'percentage'
EARN_RULE_MULTIPLIER = 'multiplier'

EARN_RULE_TYPE_CHOICES = [
    (EARN_RULE_FIXED, 'Fixed Points'),
    (EARN_RULE_PERCENTAGE, 'Percentage of Spend'),
    (EARN_RULE_MULTIPLIER, 'Multiplier'),
]

# ─── Earn Rule Triggers ───
TRIGGER_PURCHASE = 'purchase'
TRIGGER_OFFER = 'offer'
TRIGGER_LOGIN = 'login'
TRIGGER_REFERRAL = 'referral'
TRIGGER_BIRTHDAY = 'birthday'
TRIGGER_SIGNUP = 'signup'
TRIGGER_REVIEW = 'review'
TRIGGER_SOCIAL_SHARE = 'social_share'

TRIGGER_CHOICES = [
    (TRIGGER_PURCHASE, 'Purchase'),
    (TRIGGER_OFFER, 'Offer Completion'),
    (TRIGGER_LOGIN, 'Login'),
    (TRIGGER_REFERRAL, 'Referral'),
    (TRIGGER_BIRTHDAY, 'Birthday'),
    (TRIGGER_SIGNUP, 'Signup'),
    (TRIGGER_REVIEW, 'Review'),
    (TRIGGER_SOCIAL_SHARE, 'Social Share'),
]

# ─── Redemption Types ───
REDEMPTION_CASHBACK = 'cashback'
REDEMPTION_VOUCHER = 'voucher'
REDEMPTION_PRODUCT = 'product'
REDEMPTION_GIFT = 'gift'
REDEMPTION_DONATION = 'donation'

REDEMPTION_TYPE_CHOICES = [
    (REDEMPTION_CASHBACK, 'Cashback'),
    (REDEMPTION_VOUCHER, 'Voucher'),
    (REDEMPTION_PRODUCT, 'Product'),
    (REDEMPTION_GIFT, 'Gift'),
    (REDEMPTION_DONATION, 'Donation'),
]

# ─── Redemption Status ───
REDEMPTION_PENDING = 'pending'
REDEMPTION_APPROVED = 'approved'
REDEMPTION_REJECTED = 'rejected'
REDEMPTION_FULFILLED = 'fulfilled'
REDEMPTION_CANCELLED = 'cancelled'

REDEMPTION_STATUS_CHOICES = [
    (REDEMPTION_PENDING, 'Pending'),
    (REDEMPTION_APPROVED, 'Approved'),
    (REDEMPTION_REJECTED, 'Rejected'),
    (REDEMPTION_FULFILLED, 'Fulfilled'),
    (REDEMPTION_CANCELLED, 'Cancelled'),
]

# ─── Voucher Types ───
VOUCHER_PERCENT = 'percent'
VOUCHER_FIXED = 'fixed'
VOUCHER_FREE_SHIPPING = 'free_shipping'
VOUCHER_PRODUCT = 'product'

VOUCHER_TYPE_CHOICES = [
    (VOUCHER_PERCENT, 'Percentage Discount'),
    (VOUCHER_FIXED, 'Fixed Discount'),
    (VOUCHER_FREE_SHIPPING, 'Free Shipping'),
    (VOUCHER_PRODUCT, 'Free Product'),
]

# ─── Voucher / GiftCard Status ───
STATUS_ACTIVE = 'active'
STATUS_USED = 'used'
STATUS_EXPIRED = 'expired'
STATUS_CANCELLED = 'cancelled'

VOUCHER_STATUS_CHOICES = [
    (STATUS_ACTIVE, 'Active'),
    (STATUS_USED, 'Used'),
    (STATUS_EXPIRED, 'Expired'),
    (STATUS_CANCELLED, 'Cancelled'),
]

# ─── Transfer Status ───
TRANSFER_PENDING = 'pending'
TRANSFER_COMPLETED = 'completed'
TRANSFER_FAILED = 'failed'
TRANSFER_REVERSED = 'reversed'

TRANSFER_STATUS_CHOICES = [
    (TRANSFER_PENDING, 'Pending'),
    (TRANSFER_COMPLETED, 'Completed'),
    (TRANSFER_FAILED, 'Failed'),
    (TRANSFER_REVERSED, 'Reversed'),
]

# ─── Conversion Types ───
CONVERSION_TO_CASH = 'to_cash'
CONVERSION_FROM_CASH = 'from_cash'

CONVERSION_TYPE_CHOICES = [
    (CONVERSION_TO_CASH, 'Points -> Cash'),
    (CONVERSION_FROM_CASH, 'Cash -> Points'),
]

# ─── Campaign Types ───
CAMPAIGN_MULTIPLIER = 'points_multiplier'
CAMPAIGN_BONUS = 'bonus_points'
CAMPAIGN_DOUBLE_POINTS = 'double_points'
CAMPAIGN_FLASH_EARN = 'flash_earn'
CAMPAIGN_CHALLENGE = 'challenge'

CAMPAIGN_TYPE_CHOICES = [
    (CAMPAIGN_MULTIPLIER, 'Points Multiplier'),
    (CAMPAIGN_BONUS, 'Bonus Points'),
    (CAMPAIGN_DOUBLE_POINTS, 'Double Points'),
    (CAMPAIGN_FLASH_EARN, 'Flash Earn'),
    (CAMPAIGN_CHALLENGE, 'Challenge'),
]

# ─── Campaign Status ───
CAMPAIGN_DRAFT = 'draft'
CAMPAIGN_ACTIVE = 'active'
CAMPAIGN_ENDED = 'ended'
CAMPAIGN_PAUSED = 'paused'

CAMPAIGN_STATUS_CHOICES = [
    (CAMPAIGN_DRAFT, 'Draft'),
    (CAMPAIGN_ACTIVE, 'Active'),
    (CAMPAIGN_ENDED, 'Ended'),
    (CAMPAIGN_PAUSED, 'Paused'),
]

# ─── Badge Rarity ───
BADGE_COMMON = 'common'
BADGE_RARE = 'rare'
BADGE_EPIC = 'epic'
BADGE_LEGENDARY = 'legendary'

BADGE_RARITY_CHOICES = [
    (BADGE_COMMON, 'Common'),
    (BADGE_RARE, 'Rare'),
    (BADGE_EPIC, 'Epic'),
    (BADGE_LEGENDARY, 'Legendary'),
]

# ─── Challenge Types ───
CHALLENGE_INDIVIDUAL = 'individual'
CHALLENGE_TEAM = 'team'
CHALLENGE_SPEND = 'spend'
CHALLENGE_TRANSACTION = 'transaction'
CHALLENGE_LEADERBOARD = 'leaderboard'

CHALLENGE_TYPE_CHOICES = [
    (CHALLENGE_INDIVIDUAL, 'Individual'),
    (CHALLENGE_TEAM, 'Team'),
    (CHALLENGE_SPEND, 'Spend'),
    (CHALLENGE_TRANSACTION, 'Transaction Count'),
    (CHALLENGE_LEADERBOARD, 'Leaderboard'),
]

# ─── Challenge Status ───
CHALLENGE_DRAFT = 'draft'
CHALLENGE_ACTIVE = 'active'
CHALLENGE_ENDED = 'ended'
CHALLENGE_PAUSED = 'paused'

CHALLENGE_STATUS_CHOICES = [
    (CHALLENGE_DRAFT, 'Draft'),
    (CHALLENGE_ACTIVE, 'Active'),
    (CHALLENGE_ENDED, 'Ended'),
    (CHALLENGE_PAUSED, 'Paused'),
]

# ─── Notification Types ───
NOTIF_EXPIRY = 'expiry'
NOTIF_TIER_UP = 'tier_up'
NOTIF_TIER_DOWN = 'tier_down'
NOTIF_CHALLENGE = 'challenge'
NOTIF_BADGE = 'badge'
NOTIF_STREAK = 'streak'
NOTIF_CAMPAIGN = 'campaign'

NOTIFICATION_TYPE_CHOICES = [
    (NOTIF_EXPIRY, 'Points Expiry Warning'),
    (NOTIF_TIER_UP, 'Tier Upgrade'),
    (NOTIF_TIER_DOWN, 'Tier Downgrade'),
    (NOTIF_CHALLENGE, 'Challenge Update'),
    (NOTIF_BADGE, 'Badge Unlocked'),
    (NOTIF_STREAK, 'Streak Milestone'),
    (NOTIF_CAMPAIGN, 'Campaign'),
]

# ─── Fraud Risk Levels ───
FRAUD_LOW = 'low'
FRAUD_MEDIUM = 'medium'
FRAUD_HIGH = 'high'
FRAUD_CRITICAL = 'critical'

FRAUD_RISK_CHOICES = [
    (FRAUD_LOW, 'Low'),
    (FRAUD_MEDIUM, 'Medium'),
    (FRAUD_HIGH, 'High'),
    (FRAUD_CRITICAL, 'Critical'),
]

# ─── Fraud Actions ───
FRAUD_FLAG = 'flag'
FRAUD_BLOCK = 'block'
FRAUD_REVERSE = 'reverse'
FRAUD_SUSPEND = 'suspend'

FRAUD_ACTION_CHOICES = [
    (FRAUD_FLAG, 'Flagged'),
    (FRAUD_BLOCK, 'Blocked'),
    (FRAUD_REVERSE, 'Points Reversed'),
    (FRAUD_SUSPEND, 'Account Suspended'),
]

# ─── Insight Periods ───
INSIGHT_DAILY = 'daily'
INSIGHT_WEEKLY = 'weekly'
INSIGHT_MONTHLY = 'monthly'
INSIGHT_ANNUAL = 'annual'

INSIGHT_PERIOD_CHOICES = [
    (INSIGHT_DAILY, 'Daily'),
    (INSIGHT_WEEKLY, 'Weekly'),
    (INSIGHT_MONTHLY, 'Monthly'),
    (INSIGHT_ANNUAL, 'Annual'),
]

# ─── Tier Config Evaluation Periods ───
EVAL_ANNUAL = 'annual'
EVAL_ROLLING = 'rolling'

EVAL_PERIOD_CHOICES = [
    (EVAL_ANNUAL, 'Annual'),
    (EVAL_ROLLING, 'Rolling 12 months'),
]

# ─── Subscription Plans ───
PLAN_BASIC = 'basic'
PLAN_PREMIUM = 'premium'
PLAN_VIP = 'vip'

SUBSCRIPTION_PLAN_CHOICES = [
    (PLAN_BASIC, 'Basic'),
    (PLAN_PREMIUM, 'Premium'),
    (PLAN_VIP, 'VIP'),
]

# ─── Benefit Types ───
BENEFIT_DISCOUNT = 'discount'
BENEFIT_SHIPPING = 'shipping'
BENEFIT_CASHBACK = 'cashback'
BENEFIT_PERK = 'perk'
BENEFIT_ACCESS = 'access'
BENEFIT_POINTS_BOOST = 'points_boost'

BENEFIT_TYPE_CHOICES = [
    (BENEFIT_DISCOUNT, 'Discount'),
    (BENEFIT_SHIPPING, 'Free Shipping'),
    (BENEFIT_CASHBACK, 'Cashback'),
    (BENEFIT_PERK, 'Perk'),
    (BENEFIT_ACCESS, 'Exclusive Access'),
    (BENEFIT_POINTS_BOOST, 'Points Boost'),
]

# ─── Milestone Trigger Types ───
MILESTONE_TOTAL_POINTS = 'total_points'
MILESTONE_TOTAL_SPEND = 'total_spend'
MILESTONE_TRANSACTION_COUNT = 'transaction_count'
MILESTONE_REFERRAL_COUNT = 'referral_count'
MILESTONE_STREAK_DAYS = 'streak_days'

MILESTONE_TYPE_CHOICES = [
    (MILESTONE_TOTAL_POINTS, 'Total Points Earned'),
    (MILESTONE_TOTAL_SPEND, 'Total Spend'),
    (MILESTONE_TRANSACTION_COUNT, 'Transaction Count'),
    (MILESTONE_REFERRAL_COUNT, 'Referral Count'),
    (MILESTONE_STREAK_DAYS, 'Streak Days'),
]

# ─── Points Alert Types ───
ALERT_LOW_BALANCE = 'low_balance'
ALERT_EXPIRY_WARNING = 'expiry_warning'
ALERT_TIER_PROGRESS = 'tier_progress'

ALERT_TYPE_CHOICES = [
    (ALERT_LOW_BALANCE, 'Low Balance'),
    (ALERT_EXPIRY_WARNING, 'Expiry Warning'),
    (ALERT_TIER_PROGRESS, 'Tier Progress'),
]

# ─── Segment Types ───
SEGMENT_TIER = 'tier'
SEGMENT_GEO = 'geo'
SEGMENT_ACTIVITY = 'activity'
SEGMENT_PURCHASE = 'purchase'

SEGMENT_TYPE_CHOICES = [
    (SEGMENT_TIER, 'Tier'),
    (SEGMENT_GEO, 'Geographic'),
    (SEGMENT_ACTIVITY, 'Activity'),
    (SEGMENT_PURCHASE, 'Purchase'),
]

# ─── Condition Operators ───
OP_GT = 'gt'
OP_GTE = 'gte'
OP_LT = 'lt'
OP_LTE = 'lte'
OP_EQ = 'eq'
OP_IN = 'in'

OPERATOR_CHOICES = [
    (OP_GT, 'Greater Than'),
    (OP_GTE, 'Greater Than or Equal'),
    (OP_LT, 'Less Than'),
    (OP_LTE, 'Less Than or Equal'),
    (OP_EQ, 'Equal'),
    (OP_IN, 'In'),
]

# ─── Condition Types ───
COND_MIN_AMOUNT = 'min_amount'
COND_TIER = 'tier'
COND_DAY = 'day'
COND_OFFER = 'offer'

CONDITION_TYPE_CHOICES = [
    (COND_MIN_AMOUNT, 'Minimum Amount'),
    (COND_TIER, 'Tier'),
    (COND_DAY, 'Day of Week'),
    (COND_OFFER, 'Offer'),
]

# FIXED: enums.py (LedgerTxnType, LedgerSource, TierName, etc.) was orphaned
# Canonical enums now accessible from choices module
try:
    from .enums import (
        LedgerTxnType, LedgerSource, TierName,
        RedemptionStatus, CashoutStatus, NotificationChannel,
    )
except ImportError:
    pass
