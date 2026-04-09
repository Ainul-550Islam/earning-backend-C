# api/djoyalty/enums.py
"""
Python Enum classes — type-safe constants।
choices.py এর string values এর সাথে compatible।
"""

from enum import Enum, IntEnum


class TxnType(str, Enum):
    FULL = 'full'
    DISCOUNT = 'discount'
    EARN = 'earn'
    BURN = 'burn'
    ADJUSTMENT = 'adjustment'
    EXPIRY = 'expiry'
    TRANSFER_IN = 'transfer_in'
    TRANSFER_OUT = 'transfer_out'
    REFUND = 'refund'
    BONUS = 'bonus'

    @property
    def is_credit(self):
        return self in (
            TxnType.EARN, TxnType.BONUS,
            TxnType.TRANSFER_IN, TxnType.REFUND,
        )

    @property
    def is_debit(self):
        return self in (
            TxnType.BURN, TxnType.EXPIRY,
            TxnType.TRANSFER_OUT,
        )

    def __str__(self):
        return self.value


class LoyaltyTier(str, Enum):
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    PLATINUM = 'platinum'
    DIAMOND = 'diamond'

    @property
    def rank(self):
        _ranks = {
            LoyaltyTier.BRONZE: 1,
            LoyaltyTier.SILVER: 2,
            LoyaltyTier.GOLD: 3,
            LoyaltyTier.PLATINUM: 4,
            LoyaltyTier.DIAMOND: 5,
        }
        return _ranks[self]

    @property
    def label(self):
        _labels = {
            LoyaltyTier.BRONZE: '🥉 Bronze',
            LoyaltyTier.SILVER: '🥈 Silver',
            LoyaltyTier.GOLD: '🥇 Gold',
            LoyaltyTier.PLATINUM: '💎 Platinum',
            LoyaltyTier.DIAMOND: '💠 Diamond',
        }
        return _labels[self]

    def is_higher_than(self, other: 'LoyaltyTier') -> bool:
        return self.rank > other.rank

    def is_lower_than(self, other: 'LoyaltyTier') -> bool:
        return self.rank < other.rank

    def __str__(self):
        return self.value

    @classmethod
    def ordered(cls):
        """Rank অনুসারে sorted list।"""
        return sorted(cls, key=lambda t: t.rank)


class LedgerType(str, Enum):
    CREDIT = 'credit'
    DEBIT = 'debit'

    def __str__(self):
        return self.value


class LedgerSource(str, Enum):
    PURCHASE = 'purchase'
    BONUS = 'bonus'
    REFERRAL = 'referral'
    CAMPAIGN = 'campaign'
    ADMIN = 'admin'
    EXPIRY = 'expiry'
    REDEMPTION = 'redemption'
    TRANSFER = 'transfer'
    REFUND = 'refund'
    STREAK = 'streak'
    BADGE = 'badge'
    CHALLENGE = 'challenge'
    MILESTONE = 'milestone'

    def __str__(self):
        return self.value


class EarnRuleType(str, Enum):
    FIXED = 'fixed'
    PERCENTAGE = 'percentage'
    MULTIPLIER = 'multiplier'
    BONUS = 'bonus'
    CATEGORY = 'category'

    def __str__(self):
        return self.value


class EarnRuleTrigger(str, Enum):
    PURCHASE = 'purchase'
    SIGNUP = 'signup'
    BIRTHDAY = 'birthday'
    REFERRAL = 'referral'
    REVIEW = 'review'
    CHECKIN = 'checkin'
    CUSTOM = 'custom'

    def __str__(self):
        return self.value


class RedemptionStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'

    @property
    def is_terminal(self):
        """Final state — আর পরিবর্তন হবে না।"""
        return self in (
            RedemptionStatus.REJECTED,
            RedemptionStatus.CANCELLED,
            RedemptionStatus.COMPLETED,
        )

    def __str__(self):
        return self.value


class RedemptionType(str, Enum):
    VOUCHER = 'voucher'
    CASHBACK = 'cashback'
    PRODUCT = 'product'
    GIFTCARD = 'giftcard'
    DONATION = 'donation'

    def __str__(self):
        return self.value


class VoucherStatus(str, Enum):
    ACTIVE = 'active'
    USED = 'used'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'

    @property
    def is_usable(self):
        return self == VoucherStatus.ACTIVE

    def __str__(self):
        return self.value


class VoucherType(str, Enum):
    PERCENT = 'percent'
    FIXED = 'fixed'
    FREE_SHIPPING = 'free_shipping'
    BOGO = 'bogo'

    def __str__(self):
        return self.value


class CampaignStatus(str, Enum):
    DRAFT = 'draft'
    ACTIVE = 'active'
    PAUSED = 'paused'
    ENDED = 'ended'
    CANCELLED = 'cancelled'

    @property
    def is_live(self):
        return self == CampaignStatus.ACTIVE

    def __str__(self):
        return self.value


class CampaignType(str, Enum):
    POINTS_MULTIPLIER = 'points_multiplier'
    BONUS_POINTS = 'bonus_points'
    DOUBLE_POINTS = 'double_points'
    FLASH_EARN = 'flash_earn'
    REFERRAL_BOOST = 'referral_boost'

    def __str__(self):
        return self.value


class BadgeTrigger(str, Enum):
    TRANSACTION_COUNT = 'transaction_count'
    TOTAL_SPEND = 'total_spend'
    STREAK_DAYS = 'streak_days'
    REFERRALS = 'referrals'
    TIER_REACHED = 'tier_reached'
    CUSTOM = 'custom'

    def __str__(self):
        return self.value


class ChallengeStatus(str, Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    FAILED = 'failed'
    UPCOMING = 'upcoming'
    EXPIRED = 'expired'

    def __str__(self):
        return self.value


class ChallengeType(str, Enum):
    SPEND = 'spend'
    VISIT = 'visit'
    REFERRAL = 'referral'
    CUSTOM = 'custom'

    def __str__(self):
        return self.value


class TransferStatus(str, Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

    def __str__(self):
        return self.value


class FraudRisk(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

    @property
    def severity(self):
        _severity = {
            FraudRisk.LOW: 1,
            FraudRisk.MEDIUM: 2,
            FraudRisk.HIGH: 3,
            FraudRisk.CRITICAL: 4,
        }
        return _severity[self]

    def __str__(self):
        return self.value


class FraudAction(str, Enum):
    FLAG = 'flag'
    SUSPEND = 'suspend'
    BLOCK = 'block'
    NOTIFY = 'notify'

    def __str__(self):
        return self.value


class NotificationType(str, Enum):
    POINTS_EXPIRY = 'points_expiry'
    TIER_CHANGE = 'tier_change'
    BADGE_UNLOCK = 'badge_unlock'
    CAMPAIGN = 'campaign'
    REDEMPTION = 'redemption'
    GENERAL = 'general'

    def __str__(self):
        return self.value


class NotificationChannel(str, Enum):
    EMAIL = 'email'
    SMS = 'sms'
    PUSH = 'push'
    IN_APP = 'in_app'

    def __str__(self):
        return self.value


class GiftCardStatus(str, Enum):
    ACTIVE = 'active'
    USED = 'used'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'

    @property
    def is_usable(self):
        return self == GiftCardStatus.ACTIVE

    def __str__(self):
        return self.value


class EventAction(str, Enum):
    REGISTER = 'register'
    LOGIN = 'login'
    LOGOUT = 'logout'
    PURCHASE = 'purchase'
    DISCOUNT_PURCHASE = 'discount_purchase'
    POINTS_EARN = 'points_earn'
    POINTS_REDEEM = 'points_redeem'
    POINTS_EXPIRE = 'points_expire'
    TIER_UPGRADE = 'tier_upgrade'
    TIER_DOWNGRADE = 'tier_downgrade'
    BADGE_UNLOCK = 'badge_unlock'
    STREAK_MILESTONE = 'streak_milestone'
    REFERRAL = 'referral'
    VOUCHER_USE = 'voucher_use'
    CHALLENGE_COMPLETE = 'challenge_complete'
    ERROR = 'error'

    def __str__(self):
        return self.value
