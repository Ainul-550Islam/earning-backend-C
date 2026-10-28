# api/djoyalty/exceptions.py
"""
Djoyalty -- custom exceptions।
সব business logic errors এখানে defined।
"""
from decimal import Decimal


class DjoyaltyBaseError(Exception):
    """Base exception for all Djoyalty errors।"""
    default_message = 'A loyalty system error occurred.'
    error_code = 'DJOYALTY_ERROR'

    def __init__(self, message=None, **kwargs):
        self.message = message or self.default_message
        self.kwargs = kwargs
        super().__init__(self.message)

    def __str__(self):
        return self.message


# ─── Points Errors ───

class InsufficientPointsError(DjoyaltyBaseError):
    """Customer এর কাছে পর্যাপ্ত points নেই।"""
    default_message = 'Insufficient points balance.'
    error_code = 'INSUFFICIENT_POINTS'

    def __init__(self, available=0, required=0, message=None):
        self.available = available
        self.required = required
        msg = message or f'Insufficient points. Available: {available}, Required: {required}.'
        super().__init__(msg)


class PointsReservationError(DjoyaltyBaseError):
    """Points reservation সংক্রান্ত error।"""
    default_message = 'Points reservation error.'
    error_code = 'POINTS_RESERVATION_ERROR'


class PointsTransferError(DjoyaltyBaseError):
    """Points transfer সংক্রান্ত error।"""
    default_message = 'Points transfer error.'
    error_code = 'POINTS_TRANSFER_ERROR'


class PointsConversionError(DjoyaltyBaseError):
    """Points conversion সংক্রান্ত error।"""
    default_message = 'Points conversion error.'
    error_code = 'POINTS_CONVERSION_ERROR'


class PointsExpiryError(DjoyaltyBaseError):
    """Points expiry processing error।"""
    default_message = 'Points expiry processing error.'
    error_code = 'POINTS_EXPIRY_ERROR'


class PointsAdjustmentError(DjoyaltyBaseError):
    """Admin adjustment error।"""
    default_message = 'Points adjustment error.'
    error_code = 'POINTS_ADJUSTMENT_ERROR'


# ─── Tier Errors ───

class TierNotFoundError(DjoyaltyBaseError):
    """Requested tier পাওয়া যায়নি।"""
    default_message = 'Loyalty tier not found.'
    error_code = 'TIER_NOT_FOUND'


class TierEvaluationError(DjoyaltyBaseError):
    """Tier evaluation error।"""
    default_message = 'Tier evaluation failed.'
    error_code = 'TIER_EVALUATION_ERROR'


# ─── Redemption Errors ───

class RedemptionError(DjoyaltyBaseError):
    """Base redemption error।"""
    default_message = 'Redemption error.'
    error_code = 'REDEMPTION_ERROR'


class RedemptionMinimumNotMetError(RedemptionError):
    """Minimum redemption points threshold পূরণ হয়নি।"""
    default_message = 'Minimum redemption points not met.'
    error_code = 'REDEMPTION_MINIMUM_NOT_MET'


class RedemptionAlreadyProcessedError(RedemptionError):
    """Already approved/rejected redemption পুনরায় process করার চেষ্টা।"""
    default_message = 'This redemption has already been processed.'
    error_code = 'REDEMPTION_ALREADY_PROCESSED'


class RedemptionRuleNotFoundError(RedemptionError):
    """Redemption rule পাওয়া যায়নি।"""
    default_message = 'Redemption rule not found.'
    error_code = 'REDEMPTION_RULE_NOT_FOUND'


# ─── Voucher Errors ───

class VoucherNotFoundError(DjoyaltyBaseError):
    """Voucher পাওয়া যায়নি।"""
    default_message = 'Voucher not found.'
    error_code = 'VOUCHER_NOT_FOUND'


class VoucherExpiredError(DjoyaltyBaseError):
    """Voucher এর মেয়াদ শেষ।"""
    default_message = 'This voucher has expired.'
    error_code = 'VOUCHER_EXPIRED'


class VoucherAlreadyUsedError(DjoyaltyBaseError):
    """Voucher ইতিমধ্যে ব্যবহার করা হয়েছে।"""
    default_message = 'This voucher has already been used.'
    error_code = 'VOUCHER_ALREADY_USED'


class VoucherInvalidError(DjoyaltyBaseError):
    """Voucher invalid।"""
    default_message = 'Invalid voucher.'
    error_code = 'VOUCHER_INVALID'


# ─── Gift Card Errors ───

class GiftCardNotFoundError(DjoyaltyBaseError):
    """Gift card পাওয়া যায়নি।"""
    default_message = 'Gift card not found.'
    error_code = 'GIFT_CARD_NOT_FOUND'


class GiftCardExpiredError(DjoyaltyBaseError):
    """Gift card এর মেয়াদ শেষ।"""
    default_message = 'This gift card has expired.'
    error_code = 'GIFT_CARD_EXPIRED'


class GiftCardAlreadyUsedError(DjoyaltyBaseError):
    """Gift card ইতিমধ্যে ব্যবহার করা হয়েছে।"""
    default_message = 'This gift card has already been fully used.'
    error_code = 'GIFT_CARD_ALREADY_USED'


class GiftCardInsufficientBalanceError(DjoyaltyBaseError):
    """Gift card এ পর্যাপ্ত balance নেই।"""
    default_message = 'Insufficient gift card balance.'
    error_code = 'GIFT_CARD_INSUFFICIENT_BALANCE'


# ─── Campaign Errors ───

class CampaignInactiveError(DjoyaltyBaseError):
    """Campaign active নেই।"""
    default_message = 'This campaign is not currently active.'
    error_code = 'CAMPAIGN_INACTIVE'


class CampaignAlreadyJoinedError(DjoyaltyBaseError):
    """Customer ইতিমধ্যে এই campaign এ joined।"""
    default_message = 'You have already joined this campaign.'
    error_code = 'CAMPAIGN_ALREADY_JOINED'


class CampaignNotFoundError(DjoyaltyBaseError):
    """Campaign পাওয়া যায়নি।"""
    default_message = 'Campaign not found.'
    error_code = 'CAMPAIGN_NOT_FOUND'


# ─── Challenge Errors ───

class ChallengeNotActiveError(DjoyaltyBaseError):
    """Challenge active নেই।"""
    default_message = 'This challenge is not currently active.'
    error_code = 'CHALLENGE_NOT_ACTIVE'


class ChallengeAlreadyCompletedError(DjoyaltyBaseError):
    """Challenge ইতিমধ্যে complete।"""
    default_message = 'This challenge has already been completed.'
    error_code = 'CHALLENGE_ALREADY_COMPLETED'


class ChallengeNotFoundError(DjoyaltyBaseError):
    """Challenge পাওয়া যায়নি।"""
    default_message = 'Challenge not found.'
    error_code = 'CHALLENGE_NOT_FOUND'


# ─── Badge Errors ───

class BadgeAlreadyUnlockedError(DjoyaltyBaseError):
    """Badge ইতিমধ্যে unlocked।"""
    default_message = 'This badge has already been unlocked.'
    error_code = 'BADGE_ALREADY_UNLOCKED'


class BadgeNotFoundError(DjoyaltyBaseError):
    """Badge পাওয়া যায়নি।"""
    default_message = 'Badge not found.'
    error_code = 'BADGE_NOT_FOUND'


# ─── Customer Errors ───

class CustomerNotFoundError(DjoyaltyBaseError):
    """Customer পাওয়া যায়নি।"""
    default_message = 'Customer not found.'
    error_code = 'CUSTOMER_NOT_FOUND'


class CustomerInactiveError(DjoyaltyBaseError):
    """Customer inactive।"""
    default_message = 'This customer account is inactive.'
    error_code = 'CUSTOMER_INACTIVE'


class CustomerAlreadyExistsError(DjoyaltyBaseError):
    """Customer ইতিমধ্যে exists।"""
    default_message = 'A customer with this code already exists.'
    error_code = 'CUSTOMER_ALREADY_EXISTS'


# ─── Fraud Errors ───

class FraudDetectedError(DjoyaltyBaseError):
    """Fraud detected -- transaction blocked।"""
    default_message = 'This transaction has been flagged for fraud.'
    error_code = 'FRAUD_DETECTED'


class DailyLimitExceededError(DjoyaltyBaseError):
    """Daily limit exceeded।"""
    default_message = 'Daily points limit exceeded.'
    error_code = 'DAILY_LIMIT_EXCEEDED'


# ─── Subscription Errors ───

class SubscriptionNotActiveError(DjoyaltyBaseError):
    """Subscription active নেই।"""
    default_message = 'Loyalty subscription is not active.'
    error_code = 'SUBSCRIPTION_NOT_ACTIVE'


class SubscriptionAlreadyExistsError(DjoyaltyBaseError):
    """Customer এর ইতিমধ্যে active subscription আছে।"""
    default_message = 'An active subscription already exists for this customer.'
    error_code = 'SUBSCRIPTION_EXISTS'


# ─── Tenant Errors ───

class TenantNotFoundError(DjoyaltyBaseError):
    """Tenant পাওয়া যায়নি।"""
    default_message = 'Tenant not found.'
    error_code = 'TENANT_NOT_FOUND'


# ─── Earn Rule Errors ───

class EarnRuleNotFoundError(DjoyaltyBaseError):
    """Earn rule পাওয়া যায়নি।"""
    default_message = 'Earn rule not found.'
    error_code = 'EARN_RULE_NOT_FOUND'


class EarnRuleInactiveError(DjoyaltyBaseError):
    """Earn rule inactive।"""
    default_message = 'Earn rule is not active.'
    error_code = 'EARN_RULE_INACTIVE'


# ─── Partner Errors ───

class PartnerNotFoundError(DjoyaltyBaseError):
    """Partner merchant পাওয়া যায়নি।"""
    default_message = 'Partner merchant not found.'
    error_code = 'PARTNER_NOT_FOUND'


class PartnerInactiveError(DjoyaltyBaseError):
    """Partner merchant inactive।"""
    default_message = 'Partner merchant is not active.'
    error_code = 'PARTNER_INACTIVE'


class InvalidAPIKeyError(DjoyaltyBaseError):
    """Invalid API key।"""
    default_message = 'Invalid or missing API key.'
    error_code = 'INVALID_API_KEY'
