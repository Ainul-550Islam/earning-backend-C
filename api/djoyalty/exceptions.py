# api/djoyalty/exceptions.py
"""
Djoyalty custom exceptions — structured error handling।
সব exception DjoyaltyError থেকে inherit করে।
"""

from rest_framework import status


class DjoyaltyError(Exception):
    """Base exception for all djoyalty errors."""
    default_message = 'A loyalty system error occurred.'
    default_code = 'djoyalty_error'
    http_status = status.HTTP_400_BAD_REQUEST

    def __init__(self, message=None, code=None, extra=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.extra = extra or {}
        super().__init__(self.message)

    def to_dict(self):
        return {
            'error': self.code,
            'message': self.message,
            **self.extra,
        }


# ==================== POINTS ERRORS ====================

class InsufficientPointsError(DjoyaltyError):
    """Customer এর পর্যাপ্ত পয়েন্ট নেই।"""
    default_message = 'Insufficient loyalty points.'
    default_code = 'insufficient_points'
    http_status = status.HTTP_402_PAYMENT_REQUIRED

    def __init__(self, available=None, required=None):
        extra = {}
        if available is not None:
            extra['available'] = str(available)
        if required is not None:
            extra['required'] = str(required)
        super().__init__(
            message=f'Insufficient points. Available: {available}, Required: {required}',
            extra=extra,
        )


class PointsExpiryError(DjoyaltyError):
    """Points expire হয়ে গেছে।"""
    default_message = 'These points have expired.'
    default_code = 'points_expired'


class PointsTransferError(DjoyaltyError):
    """Points transfer ব্যর্থ হয়েছে।"""
    default_message = 'Points transfer failed.'
    default_code = 'transfer_failed'


class InvalidPointsAmountError(DjoyaltyError):
    """Invalid points amount (negative, zero, too large)।"""
    default_message = 'Invalid points amount.'
    default_code = 'invalid_points_amount'


class PointsReservationError(DjoyaltyError):
    """Points reserve করা সম্ভব হয়নি।"""
    default_message = 'Could not reserve points.'
    default_code = 'reservation_failed'


class PointsConversionError(DjoyaltyError):
    """Points conversion ব্যর্থ হয়েছে।"""
    default_message = 'Points conversion failed.'
    default_code = 'conversion_failed'


# ==================== CUSTOMER ERRORS ====================

class CustomerNotFoundError(DjoyaltyError):
    """Customer পাওয়া যায়নি।"""
    default_message = 'Customer not found.'
    default_code = 'customer_not_found'
    http_status = status.HTTP_404_NOT_FOUND


class CustomerSuspendedError(DjoyaltyError):
    """Customer suspend করা হয়েছে।"""
    default_message = 'Customer account is suspended.'
    default_code = 'customer_suspended'
    http_status = status.HTTP_403_FORBIDDEN


class CustomerDuplicateError(DjoyaltyError):
    """Customer ইতিমধ্যে আছে।"""
    default_message = 'Customer already exists.'
    default_code = 'customer_duplicate'
    http_status = status.HTTP_409_CONFLICT


# ==================== TIER ERRORS ====================

class TierNotFoundError(DjoyaltyError):
    """Tier পাওয়া যায়নি।"""
    default_message = 'Loyalty tier not found.'
    default_code = 'tier_not_found'
    http_status = status.HTTP_404_NOT_FOUND


class TierEvaluationError(DjoyaltyError):
    """Tier evaluation ব্যর্থ হয়েছে।"""
    default_message = 'Tier evaluation failed.'
    default_code = 'tier_evaluation_failed'


class TierDowngradeProtectedError(DjoyaltyError):
    """Tier downgrade protection active।"""
    default_message = 'Tier downgrade is currently protected.'
    default_code = 'tier_downgrade_protected'


# ==================== EARN RULE ERRORS ====================

class EarnRuleNotFoundError(DjoyaltyError):
    """Earn rule পাওয়া যায়নি।"""
    default_message = 'Earn rule not found.'
    default_code = 'earn_rule_not_found'
    http_status = status.HTTP_404_NOT_FOUND


class EarnRuleInactiveError(DjoyaltyError):
    """Earn rule active নেই।"""
    default_message = 'Earn rule is not active.'
    default_code = 'earn_rule_inactive'


class EarnRuleConditionNotMetError(DjoyaltyError):
    """Earn rule condition পূরণ হয়নি।"""
    default_message = 'Earn rule conditions are not met.'
    default_code = 'earn_rule_condition_not_met'


# ==================== REDEMPTION ERRORS ====================

class RedemptionNotFoundError(DjoyaltyError):
    """Redemption পাওয়া যায়নি।"""
    default_message = 'Redemption not found.'
    default_code = 'redemption_not_found'
    http_status = status.HTTP_404_NOT_FOUND


class RedemptionAlreadyProcessedError(DjoyaltyError):
    """Redemption ইতিমধ্যে process হয়ে গেছে।"""
    default_message = 'This redemption has already been processed.'
    default_code = 'redemption_already_processed'
    http_status = status.HTTP_409_CONFLICT


class RedemptionMinimumNotMetError(DjoyaltyError):
    """Minimum redemption threshold পূরণ হয়নি।"""
    default_message = 'Minimum redemption amount not met.'
    default_code = 'redemption_minimum_not_met'


class RedemptionLimitExceededError(DjoyaltyError):
    """Maximum redemption limit অতিক্রম করেছে।"""
    default_message = 'Redemption limit exceeded.'
    default_code = 'redemption_limit_exceeded'


# ==================== VOUCHER ERRORS ====================

class VoucherNotFoundError(DjoyaltyError):
    """Voucher পাওয়া যায়নি।"""
    default_message = 'Voucher not found.'
    default_code = 'voucher_not_found'
    http_status = status.HTTP_404_NOT_FOUND


class VoucherExpiredError(DjoyaltyError):
    """Voucher expire হয়ে গেছে।"""
    default_message = 'Voucher has expired.'
    default_code = 'voucher_expired'


class VoucherAlreadyUsedError(DjoyaltyError):
    """Voucher ইতিমধ্যে ব্যবহার হয়েছে।"""
    default_message = 'Voucher has already been used.'
    default_code = 'voucher_already_used'
    http_status = status.HTTP_409_CONFLICT


class VoucherInvalidError(DjoyaltyError):
    """Invalid voucher code।"""
    default_message = 'Invalid voucher code.'
    default_code = 'voucher_invalid'


# ==================== CAMPAIGN ERRORS ====================

class CampaignNotFoundError(DjoyaltyError):
    """Campaign পাওয়া যায়নি।"""
    default_message = 'Campaign not found.'
    default_code = 'campaign_not_found'
    http_status = status.HTTP_404_NOT_FOUND


class CampaignInactiveError(DjoyaltyError):
    """Campaign active নেই।"""
    default_message = 'Campaign is not currently active.'
    default_code = 'campaign_inactive'


class CampaignFullError(DjoyaltyError):
    """Campaign participant limit পূর্ণ।"""
    default_message = 'Campaign participant limit has been reached.'
    default_code = 'campaign_full'


class CampaignAlreadyJoinedError(DjoyaltyError):
    """Customer ইতিমধ্যে campaign এ আছে।"""
    default_message = 'Customer has already joined this campaign.'
    default_code = 'campaign_already_joined'
    http_status = status.HTTP_409_CONFLICT


# ==================== FRAUD ERRORS ====================

class FraudDetectedError(DjoyaltyError):
    """Fraud সনাক্ত হয়েছে।"""
    default_message = 'Suspicious activity detected. Action blocked.'
    default_code = 'fraud_detected'
    http_status = status.HTTP_403_FORBIDDEN


class AccountSuspendedError(DjoyaltyError):
    """Account suspend করা হয়েছে fraud এর কারণে।"""
    default_message = 'Account has been suspended due to suspicious activity.'
    default_code = 'account_suspended'
    http_status = status.HTTP_403_FORBIDDEN


# ==================== BADGE / CHALLENGE / STREAK ERRORS ====================

class BadgeAlreadyUnlockedError(DjoyaltyError):
    """Badge ইতিমধ্যে unlock হয়েছে।"""
    default_message = 'Badge already unlocked.'
    default_code = 'badge_already_unlocked'
    http_status = status.HTTP_409_CONFLICT


class ChallengeNotActiveError(DjoyaltyError):
    """Challenge active নেই।"""
    default_message = 'Challenge is not active.'
    default_code = 'challenge_not_active'


class ChallengeAlreadyCompletedError(DjoyaltyError):
    """Challenge ইতিমধ্যে complete হয়েছে।"""
    default_message = 'Challenge already completed.'
    default_code = 'challenge_already_completed'
    http_status = status.HTTP_409_CONFLICT


class StreakBrokenError(DjoyaltyError):
    """Streak ভেঙে গেছে।"""
    default_message = 'Daily streak has been broken.'
    default_code = 'streak_broken'


# ==================== GIFT CARD ERRORS ====================

class GiftCardNotFoundError(DjoyaltyError):
    """Gift card পাওয়া যায়নি।"""
    default_message = 'Gift card not found.'
    default_code = 'gift_card_not_found'
    http_status = status.HTTP_404_NOT_FOUND


class GiftCardExpiredError(DjoyaltyError):
    """Gift card expire হয়েছে।"""
    default_message = 'Gift card has expired.'
    default_code = 'gift_card_expired'


class GiftCardAlreadyUsedError(DjoyaltyError):
    """Gift card ইতিমধ্যে ব্যবহার হয়েছে।"""
    default_message = 'Gift card has already been used.'
    default_code = 'gift_card_already_used'
    http_status = status.HTTP_409_CONFLICT


class GiftCardInsufficientBalanceError(DjoyaltyError):
    """Gift card balance কম।"""
    default_message = 'Insufficient gift card balance.'
    default_code = 'gift_card_insufficient_balance'


# ==================== TENANT / PERMISSION ERRORS ====================

class TenantMismatchError(DjoyaltyError):
    """Cross-tenant access attempt।"""
    default_message = 'Cross-tenant access is not allowed.'
    default_code = 'tenant_mismatch'
    http_status = status.HTTP_403_FORBIDDEN


class PermissionDeniedError(DjoyaltyError):
    """Permission নেই।"""
    default_message = 'You do not have permission to perform this action.'
    default_code = 'permission_denied'
    http_status = status.HTTP_403_FORBIDDEN


# ==================== WEBHOOK ERRORS ====================

class WebhookDeliveryError(DjoyaltyError):
    """Webhook deliver করা যায়নি।"""
    default_message = 'Webhook delivery failed.'
    default_code = 'webhook_delivery_failed'


class WebhookSignatureError(DjoyaltyError):
    """Webhook signature invalid।"""
    default_message = 'Invalid webhook signature.'
    default_code = 'webhook_signature_invalid'
    http_status = status.HTTP_401_UNAUTHORIZED


# ==================== CONFIGURATION ERRORS ====================

class MisconfigurationError(DjoyaltyError):
    """System misconfiguration।"""
    default_message = 'Loyalty system is misconfigured.'
    default_code = 'misconfiguration'
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR


class FeatureDisabledError(DjoyaltyError):
    """Feature disabled করা আছে।"""
    default_message = 'This feature is currently disabled.'
    default_code = 'feature_disabled'
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
