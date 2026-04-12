"""
api/monetization_tools/exceptions.py
======================================
Custom exception classes for the monetization_tools app.
"""

from rest_framework.exceptions import APIException
from rest_framework import status
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class MonetizationBaseException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('A monetization error occurred.')
    default_code = 'monetization_error'


# ---------------------------------------------------------------------------
# Ad Campaign
# ---------------------------------------------------------------------------

class CampaignBudgetExceeded(MonetizationBaseException):
    default_detail = _('Campaign budget has been exhausted.')
    default_code = 'campaign_budget_exceeded'


class CampaignNotActive(MonetizationBaseException):
    default_detail = _('Campaign is not currently active.')
    default_code = 'campaign_not_active'


class InvalidCampaignDates(MonetizationBaseException):
    default_detail = _('Invalid campaign start/end dates.')
    default_code = 'invalid_campaign_dates'


# ---------------------------------------------------------------------------
# Offer / Offerwall
# ---------------------------------------------------------------------------

class OfferNotAvailable(MonetizationBaseException):
    default_detail = _('This offer is not available.')
    default_code = 'offer_not_available'


class OfferAlreadyCompleted(MonetizationBaseException):
    default_detail = _('You have already completed this offer.')
    default_code = 'offer_already_completed'


class OfferExpired(MonetizationBaseException):
    default_detail = _('This offer has expired.')
    default_code = 'offer_expired'


class OfferGeoRestricted(MonetizationBaseException):
    default_detail = _('This offer is not available in your country.')
    default_code = 'offer_geo_restricted'


class DailyOfferLimitReached(MonetizationBaseException):
    default_detail = _('You have reached the daily offer limit.')
    default_code = 'daily_offer_limit_reached'


class OfferFraudDetected(MonetizationBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Suspicious activity detected. This completion has been flagged.')
    default_code = 'offer_fraud_detected'


# ---------------------------------------------------------------------------
# Reward / Points
# ---------------------------------------------------------------------------

class InsufficientBalance(MonetizationBaseException):
    default_detail = _('Insufficient points balance for this operation.')
    default_code = 'insufficient_balance'


class RewardAlreadyCredited(MonetizationBaseException):
    default_detail = _('Reward has already been credited.')
    default_code = 'reward_already_credited'


class InvalidRewardAmount(MonetizationBaseException):
    default_detail = _('Invalid reward amount.')
    default_code = 'invalid_reward_amount'


# ---------------------------------------------------------------------------
# Subscription / Payment
# ---------------------------------------------------------------------------

class SubscriptionAlreadyActive(MonetizationBaseException):
    default_detail = _('User already has an active subscription.')
    default_code = 'subscription_already_active'


class SubscriptionNotFound(MonetizationBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('No active subscription found.')
    default_code = 'subscription_not_found'


class PaymentFailed(MonetizationBaseException):
    default_detail = _('Payment processing failed. Please try again.')
    default_code = 'payment_failed'


class PaymentGatewayError(MonetizationBaseException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = _('Payment gateway is temporarily unavailable.')
    default_code = 'payment_gateway_error'


class InvalidPaymentAmount(MonetizationBaseException):
    default_detail = _('Invalid payment amount.')
    default_code = 'invalid_payment_amount'


class RecurringBillingFailed(MonetizationBaseException):
    default_detail = _('Recurring billing attempt failed.')
    default_code = 'recurring_billing_failed'


# ---------------------------------------------------------------------------
# Gamification
# ---------------------------------------------------------------------------

class SpinWheelDailyLimitReached(MonetizationBaseException):
    default_detail = _('You have reached the daily spin wheel limit.')
    default_code = 'spin_wheel_limit_reached'


class ScratchCardDailyLimitReached(MonetizationBaseException):
    default_detail = _('You have reached the daily scratch card limit.')
    default_code = 'scratch_card_limit_reached'


class AchievementAlreadyUnlocked(MonetizationBaseException):
    default_detail = _('This achievement has already been unlocked.')
    default_code = 'achievement_already_unlocked'


# ---------------------------------------------------------------------------
# A/B Testing
# ---------------------------------------------------------------------------

class ABTestAlreadyRunning(MonetizationBaseException):
    default_detail = _('An A/B test is already running for this ad unit.')
    default_code = 'ab_test_already_running'


class ABTestInvalidVariants(MonetizationBaseException):
    default_detail = _('Invalid A/B test variant configuration.')
    default_code = 'ab_test_invalid_variants'


# ---------------------------------------------------------------------------
# Revenue / Analytics
# ---------------------------------------------------------------------------

class RevenueCalculationError(MonetizationBaseException):
    default_detail = _('Revenue calculation failed.')
    default_code = 'revenue_calculation_error'


class InvalidDateRange(MonetizationBaseException):
    default_detail = _('Invalid date range for report.')
    default_code = 'invalid_date_range'


# ---------------------------------------------------------------------------
# Payout
# ---------------------------------------------------------------------------

class PayoutRequestFailed(MonetizationBaseException):
    default_detail = _('Payout request could not be processed.')
    default_code   = 'payout_request_failed'


class PayoutMethodNotVerified(MonetizationBaseException):
    default_detail = _('Payout method is not verified. Please verify before withdrawing.')
    default_code   = 'payout_method_not_verified'


class PayoutMinimumNotMet(MonetizationBaseException):
    default_detail = _('Amount is below minimum withdrawal threshold.')
    default_code   = 'payout_minimum_not_met'


class PayoutMaximumExceeded(MonetizationBaseException):
    default_detail = _('Amount exceeds maximum withdrawal limit.')
    default_code   = 'payout_maximum_exceeded'


class TooManyPendingPayouts(MonetizationBaseException):
    default_detail = _('You have too many pending payout requests. Wait for them to be processed.')
    default_code   = 'too_many_pending_payouts'


# ---------------------------------------------------------------------------
# Coupon
# ---------------------------------------------------------------------------

class CouponInvalid(MonetizationBaseException):
    default_detail = _('This coupon code is invalid or has expired.')
    default_code   = 'coupon_invalid'


class CouponAlreadyUsed(MonetizationBaseException):
    default_detail = _('You have already used this coupon.')
    default_code   = 'coupon_already_used'


class CouponLevelRequired(MonetizationBaseException):
    default_detail = _('Your account level is too low to use this coupon.')
    default_code   = 'coupon_level_required'


# ---------------------------------------------------------------------------
# Referral
# ---------------------------------------------------------------------------

class ReferralProgramNotActive(MonetizationBaseException):
    default_detail = _('The referral program is not currently active.')
    default_code   = 'referral_program_not_active'


class ReferralSelfReferral(MonetizationBaseException):
    default_detail = _('You cannot refer yourself.')
    default_code   = 'referral_self_referral'


class ReferralAlreadyExists(MonetizationBaseException):
    default_detail = _('This user has already been referred.')
    default_code   = 'referral_already_exists'


# ---------------------------------------------------------------------------
# Flash Sale
# ---------------------------------------------------------------------------

class FlashSaleExpired(MonetizationBaseException):
    default_detail = _('This flash sale has ended.')
    default_code   = 'flash_sale_expired'


class FlashSaleNotActive(MonetizationBaseException):
    default_detail = _('Flash sale is not currently active.')
    default_code   = 'flash_sale_not_active'


# ---------------------------------------------------------------------------
# Publisher Account
# ---------------------------------------------------------------------------

class PublisherAccountSuspended(MonetizationBaseException):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = _('Your publisher account has been suspended.')
    default_code   = 'publisher_account_suspended'


class PublisherAccountNotVerified(MonetizationBaseException):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = _('Publisher account KYC verification is required.')
    default_code   = 'publisher_not_verified'


class PublisherCreditLimitExceeded(MonetizationBaseException):
    default_detail = _('Publisher credit limit has been exceeded.')
    default_code   = 'publisher_credit_limit_exceeded'


# ---------------------------------------------------------------------------
# Fraud
# ---------------------------------------------------------------------------

class UserAccountBlocked(MonetizationBaseException):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = _('Your account has been blocked due to suspicious activity.')
    default_code   = 'user_account_blocked'


class FraudThresholdExceeded(MonetizationBaseException):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = _('Action blocked due to high fraud risk score.')
    default_code   = 'fraud_threshold_exceeded'


# ---------------------------------------------------------------------------
# Ad Creative
# ---------------------------------------------------------------------------

class CreativePendingReview(MonetizationBaseException):
    default_detail = _('This creative is pending review and cannot be served.')
    default_code   = 'creative_pending_review'


class CreativeRejected(MonetizationBaseException):
    default_detail = _('This creative has been rejected. Please upload a new one.')
    default_code   = 'creative_rejected'


# ---------------------------------------------------------------------------
# Performance / Analytics
# ---------------------------------------------------------------------------

class ReportDateRangeTooLarge(MonetizationBaseException):
    default_detail = _('Date range is too large. Maximum is 365 days.')
    default_code   = 'report_date_range_too_large'


class NoDataForPeriod(MonetizationBaseException):
    status_code    = status.HTTP_404_NOT_FOUND
    default_detail = _('No data found for the specified period.')
    default_code   = 'no_data_for_period'
