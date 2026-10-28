# api/djoyalty/enums.py
"""
Djoyalty -- Python Enums (optional, for type-safe code)।
Import করে use করো যেখানে string choices এর চেয়ে type safety দরকার।
"""
from enum import Enum


class LedgerTxnType(str, Enum):
    CREDIT = 'credit'
    DEBIT = 'debit'


class LedgerSource(str, Enum):
    PURCHASE = 'purchase'
    REFERRAL = 'referral'
    BONUS = 'bonus'
    OFFER = 'offer'
    REDEMPTION = 'redemption'
    EXPIRY = 'expiry'
    TRANSFER = 'transfer'
    ADMIN = 'admin'
    SUBSCRIPTION = 'subscription'
    BADGE = 'badge'
    STREAK = 'streak'
    CHALLENGE = 'challenge'
    MILESTONE = 'milestone'
    COALITION = 'coalition'
    PARTNER = 'partner'
    CONVERSION = 'conversion'


class TierName(str, Enum):
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    PLATINUM = 'platinum'
    DIAMOND = 'diamond'


class TierChangeType(str, Enum):
    UPGRADE = 'upgrade'
    DOWNGRADE = 'downgrade'
    INITIAL = 'initial'
    MANUAL = 'manual'


class EarnRuleType(str, Enum):
    FIXED = 'fixed'
    PERCENTAGE = 'percentage'
    MULTIPLIER = 'multiplier'


class EarnTrigger(str, Enum):
    PURCHASE = 'purchase'
    OFFER = 'offer'
    LOGIN = 'login'
    REFERRAL = 'referral'
    BIRTHDAY = 'birthday'
    SIGNUP = 'signup'
    REVIEW = 'review'
    SOCIAL_SHARE = 'social_share'


class RedemptionType(str, Enum):
    CASHBACK = 'cashback'
    VOUCHER = 'voucher'
    PRODUCT = 'product'
    GIFT = 'gift'
    DONATION = 'donation'


class RedemptionStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    FULFILLED = 'fulfilled'
    CANCELLED = 'cancelled'


class VoucherType(str, Enum):
    PERCENT = 'percent'
    FIXED = 'fixed'
    FREE_SHIPPING = 'free_shipping'
    PRODUCT = 'product'


class VoucherStatus(str, Enum):
    ACTIVE = 'active'
    USED = 'used'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class TransferStatus(str, Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REVERSED = 'reversed'


class CampaignType(str, Enum):
    MULTIPLIER = 'points_multiplier'
    BONUS = 'bonus_points'
    DOUBLE_POINTS = 'double_points'
    FLASH_EARN = 'flash_earn'
    CHALLENGE = 'challenge'


class CampaignStatus(str, Enum):
    DRAFT = 'draft'
    ACTIVE = 'active'
    ENDED = 'ended'
    PAUSED = 'paused'


class BadgeRarity(str, Enum):
    COMMON = 'common'
    RARE = 'rare'
    EPIC = 'epic'
    LEGENDARY = 'legendary'


class ChallengeType(str, Enum):
    INDIVIDUAL = 'individual'
    TEAM = 'team'
    SPEND = 'spend'
    TRANSACTION = 'transaction'
    LEADERBOARD = 'leaderboard'


class ChallengeStatus(str, Enum):
    DRAFT = 'draft'
    ACTIVE = 'active'
    ENDED = 'ended'
    PAUSED = 'paused'


class NotificationType(str, Enum):
    EXPIRY = 'expiry'
    TIER_UP = 'tier_up'
    TIER_DOWN = 'tier_down'
    CHALLENGE = 'challenge'
    BADGE = 'badge'
    STREAK = 'streak'
    CAMPAIGN = 'campaign'


class FraudRiskLevel(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class FraudAction(str, Enum):
    FLAG = 'flag'
    BLOCK = 'block'
    REVERSE = 'reverse'
    SUSPEND = 'suspend'


class InsightPeriod(str, Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    ANNUAL = 'annual'


class SubscriptionPlan(str, Enum):
    BASIC = 'basic'
    PREMIUM = 'premium'
    VIP = 'vip'


class BenefitType(str, Enum):
    DISCOUNT = 'discount'
    SHIPPING = 'shipping'
    CASHBACK = 'cashback'
    PERK = 'perk'
    ACCESS = 'access'
    POINTS_BOOST = 'points_boost'


class MilestoneType(str, Enum):
    TOTAL_POINTS = 'total_points'
    TOTAL_SPEND = 'total_spend'
    TRANSACTION_COUNT = 'transaction_count'
    REFERRAL_COUNT = 'referral_count'
    STREAK_DAYS = 'streak_days'


class AlertType(str, Enum):
    LOW_BALANCE = 'low_balance'
    EXPIRY_WARNING = 'expiry_warning'
    TIER_PROGRESS = 'tier_progress'
