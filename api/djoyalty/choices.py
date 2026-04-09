# api/djoyalty/choices.py
"""
Django CharField choices — সব Enum-style constants এখানে।
"""

# ==================== TXN TYPE ====================

TXN_TYPE_FULL = 'full'
TXN_TYPE_DISCOUNT = 'discount'
TXN_TYPE_EARN = 'earn'
TXN_TYPE_BURN = 'burn'
TXN_TYPE_ADJUSTMENT = 'adjustment'
TXN_TYPE_EXPIRY = 'expiry'
TXN_TYPE_TRANSFER_IN = 'transfer_in'
TXN_TYPE_TRANSFER_OUT = 'transfer_out'
TXN_TYPE_REFUND = 'refund'
TXN_TYPE_BONUS = 'bonus'

TXN_TYPE_CHOICES = [
    (TXN_TYPE_FULL, 'Full Price'),
    (TXN_TYPE_DISCOUNT, 'Discount'),
    (TXN_TYPE_EARN, 'Points Earn'),
    (TXN_TYPE_BURN, 'Points Burn / Redeem'),
    (TXN_TYPE_ADJUSTMENT, 'Manual Adjustment'),
    (TXN_TYPE_EXPIRY, 'Points Expiry'),
    (TXN_TYPE_TRANSFER_IN, 'Transfer In'),
    (TXN_TYPE_TRANSFER_OUT, 'Transfer Out'),
    (TXN_TYPE_REFUND, 'Refund'),
    (TXN_TYPE_BONUS, 'Bonus Points'),
]

# ==================== LOYALTY TIER ====================

TIER_BRONZE = 'bronze'
TIER_SILVER = 'silver'
TIER_GOLD = 'gold'
TIER_PLATINUM = 'platinum'
TIER_DIAMOND = 'diamond'

TIER_CHOICES = [
    (TIER_BRONZE, '🥉 Bronze'),
    (TIER_SILVER, '🥈 Silver'),
    (TIER_GOLD, '🥇 Gold'),
    (TIER_PLATINUM, '💎 Platinum'),
    (TIER_DIAMOND, '💠 Diamond'),
]

TIER_RANK = {
    TIER_BRONZE: 1,
    TIER_SILVER: 2,
    TIER_GOLD: 3,
    TIER_PLATINUM: 4,
    TIER_DIAMOND: 5,
}

# ==================== POINTS LEDGER ====================

LEDGER_CREDIT = 'credit'
LEDGER_DEBIT = 'debit'

LEDGER_TYPE_CHOICES = [
    (LEDGER_CREDIT, 'Credit'),
    (LEDGER_DEBIT, 'Debit'),
]

LEDGER_SOURCE_PURCHASE = 'purchase'
LEDGER_SOURCE_BONUS = 'bonus'
LEDGER_SOURCE_REFERRAL = 'referral'
LEDGER_SOURCE_CAMPAIGN = 'campaign'
LEDGER_SOURCE_ADMIN = 'admin'
LEDGER_SOURCE_EXPIRY = 'expiry'
LEDGER_SOURCE_REDEMPTION = 'redemption'
LEDGER_SOURCE_TRANSFER = 'transfer'
LEDGER_SOURCE_REFUND = 'refund'
LEDGER_SOURCE_STREAK = 'streak'
LEDGER_SOURCE_BADGE = 'badge'
LEDGER_SOURCE_CHALLENGE = 'challenge'
LEDGER_SOURCE_MILESTONE = 'milestone'

LEDGER_SOURCE_CHOICES = [
    (LEDGER_SOURCE_PURCHASE, 'Purchase'),
    (LEDGER_SOURCE_BONUS, 'Bonus'),
    (LEDGER_SOURCE_REFERRAL, 'Referral'),
    (LEDGER_SOURCE_CAMPAIGN, 'Campaign'),
    (LEDGER_SOURCE_ADMIN, 'Admin Adjustment'),
    (LEDGER_SOURCE_EXPIRY, 'Points Expiry'),
    (LEDGER_SOURCE_REDEMPTION, 'Redemption'),
    (LEDGER_SOURCE_TRANSFER, 'Transfer'),
    (LEDGER_SOURCE_REFUND, 'Refund'),
    (LEDGER_SOURCE_STREAK, 'Daily Streak'),
    (LEDGER_SOURCE_BADGE, 'Badge Unlock'),
    (LEDGER_SOURCE_CHALLENGE, 'Challenge Completion'),
    (LEDGER_SOURCE_MILESTONE, 'Milestone'),
]

# ==================== EARN RULE ====================

EARN_RULE_FIXED = 'fixed'
EARN_RULE_PERCENTAGE = 'percentage'
EARN_RULE_MULTIPLIER = 'multiplier'
EARN_RULE_BONUS = 'bonus'
EARN_RULE_CATEGORY = 'category'

EARN_RULE_TYPE_CHOICES = [
    (EARN_RULE_FIXED, 'Fixed Points'),
    (EARN_RULE_PERCENTAGE, 'Percentage of Spend'),
    (EARN_RULE_MULTIPLIER, 'Multiplier'),
    (EARN_RULE_BONUS, 'Bonus Points'),
    (EARN_RULE_CATEGORY, 'Category-Based'),
]

EARN_RULE_TRIGGER_PURCHASE = 'purchase'
EARN_RULE_TRIGGER_SIGNUP = 'signup'
EARN_RULE_TRIGGER_BIRTHDAY = 'birthday'
EARN_RULE_TRIGGER_REFERRAL = 'referral'
EARN_RULE_TRIGGER_REVIEW = 'review'
EARN_RULE_TRIGGER_CHECKIN = 'checkin'
EARN_RULE_TRIGGER_CUSTOM = 'custom'

EARN_RULE_TRIGGER_CHOICES = [
    (EARN_RULE_TRIGGER_PURCHASE, 'Purchase'),
    (EARN_RULE_TRIGGER_SIGNUP, 'Sign Up'),
    (EARN_RULE_TRIGGER_BIRTHDAY, 'Birthday'),
    (EARN_RULE_TRIGGER_REFERRAL, 'Referral'),
    (EARN_RULE_TRIGGER_REVIEW, 'Write a Review'),
    (EARN_RULE_TRIGGER_CHECKIN, 'Check In'),
    (EARN_RULE_TRIGGER_CUSTOM, 'Custom Event'),
]

# ==================== REDEMPTION ====================

REDEMPTION_STATUS_PENDING = 'pending'
REDEMPTION_STATUS_APPROVED = 'approved'
REDEMPTION_STATUS_REJECTED = 'rejected'
REDEMPTION_STATUS_CANCELLED = 'cancelled'
REDEMPTION_STATUS_COMPLETED = 'completed'

REDEMPTION_STATUS_CHOICES = [
    (REDEMPTION_STATUS_PENDING, '⏳ Pending'),
    (REDEMPTION_STATUS_APPROVED, '✅ Approved'),
    (REDEMPTION_STATUS_REJECTED, '❌ Rejected'),
    (REDEMPTION_STATUS_CANCELLED, '🚫 Cancelled'),
    (REDEMPTION_STATUS_COMPLETED, '🎉 Completed'),
]

REDEMPTION_TYPE_VOUCHER = 'voucher'
REDEMPTION_TYPE_CASHBACK = 'cashback'
REDEMPTION_TYPE_PRODUCT = 'product'
REDEMPTION_TYPE_GIFTCARD = 'giftcard'
REDEMPTION_TYPE_DONATION = 'donation'

REDEMPTION_TYPE_CHOICES = [
    (REDEMPTION_TYPE_VOUCHER, '🎫 Voucher'),
    (REDEMPTION_TYPE_CASHBACK, '💵 Cashback'),
    (REDEMPTION_TYPE_PRODUCT, '📦 Product'),
    (REDEMPTION_TYPE_GIFTCARD, '🎁 Gift Card'),
    (REDEMPTION_TYPE_DONATION, '❤️ Donation'),
]

# ==================== VOUCHER ====================

VOUCHER_STATUS_ACTIVE = 'active'
VOUCHER_STATUS_USED = 'used'
VOUCHER_STATUS_EXPIRED = 'expired'
VOUCHER_STATUS_CANCELLED = 'cancelled'

VOUCHER_STATUS_CHOICES = [
    (VOUCHER_STATUS_ACTIVE, '✅ Active'),
    (VOUCHER_STATUS_USED, '✔️ Used'),
    (VOUCHER_STATUS_EXPIRED, '⌛ Expired'),
    (VOUCHER_STATUS_CANCELLED, '🚫 Cancelled'),
]

VOUCHER_TYPE_PERCENT = 'percent'
VOUCHER_TYPE_FIXED = 'fixed'
VOUCHER_TYPE_FREE_SHIPPING = 'free_shipping'
VOUCHER_TYPE_BOGO = 'bogo'

VOUCHER_TYPE_CHOICES = [
    (VOUCHER_TYPE_PERCENT, '% Percentage Discount'),
    (VOUCHER_TYPE_FIXED, '$ Fixed Discount'),
    (VOUCHER_TYPE_FREE_SHIPPING, '🚚 Free Shipping'),
    (VOUCHER_TYPE_BOGO, '🛒 Buy One Get One'),
]

# ==================== CAMPAIGN ====================

CAMPAIGN_STATUS_DRAFT = 'draft'
CAMPAIGN_STATUS_ACTIVE = 'active'
CAMPAIGN_STATUS_PAUSED = 'paused'
CAMPAIGN_STATUS_ENDED = 'ended'
CAMPAIGN_STATUS_CANCELLED = 'cancelled'

CAMPAIGN_STATUS_CHOICES = [
    (CAMPAIGN_STATUS_DRAFT, '📝 Draft'),
    (CAMPAIGN_STATUS_ACTIVE, '🟢 Active'),
    (CAMPAIGN_STATUS_PAUSED, '⏸️ Paused'),
    (CAMPAIGN_STATUS_ENDED, '🏁 Ended'),
    (CAMPAIGN_STATUS_CANCELLED, '🚫 Cancelled'),
]

CAMPAIGN_TYPE_POINTS_MULTIPLIER = 'points_multiplier'
CAMPAIGN_TYPE_BONUS_POINTS = 'bonus_points'
CAMPAIGN_TYPE_DOUBLE_POINTS = 'double_points'
CAMPAIGN_TYPE_FLASH_EARN = 'flash_earn'
CAMPAIGN_TYPE_REFERRAL_BOOST = 'referral_boost'

CAMPAIGN_TYPE_CHOICES = [
    (CAMPAIGN_TYPE_POINTS_MULTIPLIER, '✖️ Points Multiplier'),
    (CAMPAIGN_TYPE_BONUS_POINTS, '➕ Bonus Points'),
    (CAMPAIGN_TYPE_DOUBLE_POINTS, '✌️ Double Points'),
    (CAMPAIGN_TYPE_FLASH_EARN, '⚡ Flash Earn'),
    (CAMPAIGN_TYPE_REFERRAL_BOOST, '👥 Referral Boost'),
]

# ==================== BADGE ====================

BADGE_TRIGGER_TRANSACTION_COUNT = 'transaction_count'
BADGE_TRIGGER_TOTAL_SPEND = 'total_spend'
BADGE_TRIGGER_STREAK_DAYS = 'streak_days'
BADGE_TRIGGER_REFERRALS = 'referrals'
BADGE_TRIGGER_TIER_REACHED = 'tier_reached'
BADGE_TRIGGER_CUSTOM = 'custom'

BADGE_TRIGGER_CHOICES = [
    (BADGE_TRIGGER_TRANSACTION_COUNT, '💳 Transaction Count'),
    (BADGE_TRIGGER_TOTAL_SPEND, '💰 Total Spend'),
    (BADGE_TRIGGER_STREAK_DAYS, '🔥 Streak Days'),
    (BADGE_TRIGGER_REFERRALS, '👥 Referrals'),
    (BADGE_TRIGGER_TIER_REACHED, '🏆 Tier Reached'),
    (BADGE_TRIGGER_CUSTOM, '⚡ Custom'),
]

# ==================== EVENT ACTIONS ====================

EVENT_ACTION_REGISTER = 'register'
EVENT_ACTION_LOGIN = 'login'
EVENT_ACTION_LOGOUT = 'logout'
EVENT_ACTION_PURCHASE = 'purchase'
EVENT_ACTION_DISCOUNT_PURCHASE = 'discount_purchase'
EVENT_ACTION_POINTS_EARN = 'points_earn'
EVENT_ACTION_POINTS_REDEEM = 'points_redeem'
EVENT_ACTION_POINTS_EXPIRE = 'points_expire'
EVENT_ACTION_TIER_UPGRADE = 'tier_upgrade'
EVENT_ACTION_TIER_DOWNGRADE = 'tier_downgrade'
EVENT_ACTION_BADGE_UNLOCK = 'badge_unlock'
EVENT_ACTION_STREAK_MILESTONE = 'streak_milestone'
EVENT_ACTION_REFERRAL = 'referral'
EVENT_ACTION_VOUCHER_USE = 'voucher_use'
EVENT_ACTION_CHALLENGE_COMPLETE = 'challenge_complete'
EVENT_ACTION_ERROR = 'error'

EVENT_ACTION_CHOICES = [
    (EVENT_ACTION_REGISTER, 'Register'),
    (EVENT_ACTION_LOGIN, 'Login'),
    (EVENT_ACTION_LOGOUT, 'Logout'),
    (EVENT_ACTION_PURCHASE, 'Purchase'),
    (EVENT_ACTION_DISCOUNT_PURCHASE, 'Discount Purchase'),
    (EVENT_ACTION_POINTS_EARN, 'Points Earned'),
    (EVENT_ACTION_POINTS_REDEEM, 'Points Redeemed'),
    (EVENT_ACTION_POINTS_EXPIRE, 'Points Expired'),
    (EVENT_ACTION_TIER_UPGRADE, 'Tier Upgrade'),
    (EVENT_ACTION_TIER_DOWNGRADE, 'Tier Downgrade'),
    (EVENT_ACTION_BADGE_UNLOCK, 'Badge Unlocked'),
    (EVENT_ACTION_STREAK_MILESTONE, 'Streak Milestone'),
    (EVENT_ACTION_REFERRAL, 'Referral'),
    (EVENT_ACTION_VOUCHER_USE, 'Voucher Used'),
    (EVENT_ACTION_CHALLENGE_COMPLETE, 'Challenge Completed'),
    (EVENT_ACTION_ERROR, 'Error'),
]

# ==================== NOTIFICATION ====================

NOTIFICATION_TYPE_POINTS_EXPIRY = 'points_expiry'
NOTIFICATION_TYPE_TIER_CHANGE = 'tier_change'
NOTIFICATION_TYPE_BADGE_UNLOCK = 'badge_unlock'
NOTIFICATION_TYPE_CAMPAIGN = 'campaign'
NOTIFICATION_TYPE_REDEMPTION = 'redemption'
NOTIFICATION_TYPE_GENERAL = 'general'

NOTIFICATION_TYPE_CHOICES = [
    (NOTIFICATION_TYPE_POINTS_EXPIRY, '⌛ Points Expiry Warning'),
    (NOTIFICATION_TYPE_TIER_CHANGE, '🏆 Tier Change'),
    (NOTIFICATION_TYPE_BADGE_UNLOCK, '🎖️ Badge Unlocked'),
    (NOTIFICATION_TYPE_CAMPAIGN, '📣 Campaign'),
    (NOTIFICATION_TYPE_REDEMPTION, '🎁 Redemption Update'),
    (NOTIFICATION_TYPE_GENERAL, '📢 General'),
]

NOTIFICATION_CHANNEL_EMAIL = 'email'
NOTIFICATION_CHANNEL_SMS = 'sms'
NOTIFICATION_CHANNEL_PUSH = 'push'
NOTIFICATION_CHANNEL_IN_APP = 'in_app'

NOTIFICATION_CHANNEL_CHOICES = [
    (NOTIFICATION_CHANNEL_EMAIL, '📧 Email'),
    (NOTIFICATION_CHANNEL_SMS, '📱 SMS'),
    (NOTIFICATION_CHANNEL_PUSH, '🔔 Push Notification'),
    (NOTIFICATION_CHANNEL_IN_APP, '💬 In-App'),
]

# ==================== FRAUD ====================

FRAUD_RISK_LOW = 'low'
FRAUD_RISK_MEDIUM = 'medium'
FRAUD_RISK_HIGH = 'high'
FRAUD_RISK_CRITICAL = 'critical'

FRAUD_RISK_CHOICES = [
    (FRAUD_RISK_LOW, '🟢 Low'),
    (FRAUD_RISK_MEDIUM, '🟡 Medium'),
    (FRAUD_RISK_HIGH, '🟠 High'),
    (FRAUD_RISK_CRITICAL, '🔴 Critical'),
]

FRAUD_ACTION_FLAG = 'flag'
FRAUD_ACTION_SUSPEND = 'suspend'
FRAUD_ACTION_BLOCK = 'block'
FRAUD_ACTION_NOTIFY = 'notify'

FRAUD_ACTION_CHOICES = [
    (FRAUD_ACTION_FLAG, '⚑ Flag'),
    (FRAUD_ACTION_SUSPEND, '⏸️ Suspend'),
    (FRAUD_ACTION_BLOCK, '🚫 Block'),
    (FRAUD_ACTION_NOTIFY, '🔔 Notify Admin'),
]

# ==================== CHALLENGE ====================

CHALLENGE_STATUS_ACTIVE = 'active'
CHALLENGE_STATUS_COMPLETED = 'completed'
CHALLENGE_STATUS_FAILED = 'failed'
CHALLENGE_STATUS_UPCOMING = 'upcoming'
CHALLENGE_STATUS_EXPIRED = 'expired'

CHALLENGE_STATUS_CHOICES = [
    (CHALLENGE_STATUS_ACTIVE, '🟢 Active'),
    (CHALLENGE_STATUS_COMPLETED, '✅ Completed'),
    (CHALLENGE_STATUS_FAILED, '❌ Failed'),
    (CHALLENGE_STATUS_UPCOMING, '📅 Upcoming'),
    (CHALLENGE_STATUS_EXPIRED, '⌛ Expired'),
]

CHALLENGE_TYPE_SPEND = 'spend'
CHALLENGE_TYPE_VISIT = 'visit'
CHALLENGE_TYPE_REFERRAL = 'referral'
CHALLENGE_TYPE_CUSTOM = 'custom'

CHALLENGE_TYPE_CHOICES = [
    (CHALLENGE_TYPE_SPEND, '💰 Spend Target'),
    (CHALLENGE_TYPE_VISIT, '📍 Visit Count'),
    (CHALLENGE_TYPE_REFERRAL, '👥 Referral Count'),
    (CHALLENGE_TYPE_CUSTOM, '⚡ Custom'),
]

# ==================== POINTS TRANSFER ====================

TRANSFER_STATUS_PENDING = 'pending'
TRANSFER_STATUS_COMPLETED = 'completed'
TRANSFER_STATUS_FAILED = 'failed'
TRANSFER_STATUS_CANCELLED = 'cancelled'

TRANSFER_STATUS_CHOICES = [
    (TRANSFER_STATUS_PENDING, '⏳ Pending'),
    (TRANSFER_STATUS_COMPLETED, '✅ Completed'),
    (TRANSFER_STATUS_FAILED, '❌ Failed'),
    (TRANSFER_STATUS_CANCELLED, '🚫 Cancelled'),
]

# ==================== GIFT CARD ====================

GIFTCARD_STATUS_ACTIVE = 'active'
GIFTCARD_STATUS_USED = 'used'
GIFTCARD_STATUS_EXPIRED = 'expired'
GIFTCARD_STATUS_CANCELLED = 'cancelled'

GIFTCARD_STATUS_CHOICES = [
    (GIFTCARD_STATUS_ACTIVE, '✅ Active'),
    (GIFTCARD_STATUS_USED, '✔️ Used'),
    (GIFTCARD_STATUS_EXPIRED, '⌛ Expired'),
    (GIFTCARD_STATUS_CANCELLED, '🚫 Cancelled'),
]
