# api/referral/exceptions.py
# Custom exceptions for the referral module
# Use these in services, views, tasks — never raise generic Exception
# ============================================================

from rest_framework.exceptions import APIException
from rest_framework import status


# ── Base ──────────────────────────────────────────────────────────────────────

class ReferralBaseException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'referral_error'
    default_detail = 'A referral error occurred.'


# ── Referral Relationship ─────────────────────────────────────────────────────

class SelfReferralError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'self_referral'
    default_detail = 'A user cannot refer themselves.'


class AlreadyReferredError(ReferralBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'already_referred'
    default_detail = 'This user already has a referrer.'


class ReferralNotFoundError(ReferralBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = 'referral_not_found'
    default_detail = 'Referral relationship not found.'


class ReferralAlreadyExistsError(ReferralBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'referral_exists'
    default_detail = 'This referral already exists.'


# ── Referral Code ─────────────────────────────────────────────────────────────

class InvalidReferralCodeError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'invalid_code'
    default_detail = 'Invalid or expired referral code.'


class CodeAlreadyTakenError(ReferralBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'code_taken'
    default_detail = 'This referral code is already taken.'


class CodeExpiredError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'code_expired'
    default_detail = 'This referral code has expired.'


# ── Commission ────────────────────────────────────────────────────────────────

class CommissionError(ReferralBaseException):
    default_code = 'commission_error'
    default_detail = 'Commission processing failed.'


class CommissionHeldError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'commission_held'
    default_detail = 'This commission is currently on hold.'


class CommissionAlreadyReleasedError(ReferralBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'already_released'
    default_detail = 'This commission has already been released.'


class ClawbackError(ReferralBaseException):
    default_code = 'clawback_error'
    default_detail = 'Commission clawback failed.'


class InsufficientBalanceError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'insufficient_balance'
    default_detail = 'Insufficient referral balance for this operation.'


class PayoutBelowMinimumError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'below_minimum'
    default_detail = 'Payout amount is below the minimum threshold.'


# ── Fraud ─────────────────────────────────────────────────────────────────────

class ReferralBlockedError(ReferralBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'referral_blocked'
    default_detail = 'This referral has been blocked due to suspicious activity.'


class FraudDetectedError(ReferralBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'fraud_detected'
    default_detail = 'Fraud detected. Referral blocked.'


class BlacklistedError(ReferralBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'blacklisted'
    default_detail = 'This IP/email/device is blacklisted from the referral program.'


# ── Campaign / Settings ───────────────────────────────────────────────────────

class ReferralProgramInactiveError(ReferralBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = 'program_inactive'
    default_detail = 'The referral program is currently inactive.'


class CampaignBudgetExceededError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'budget_exceeded'
    default_detail = 'Campaign budget has been exceeded.'


class CampaignExpiredError(ReferralBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'campaign_expired'
    default_detail = 'This referral campaign has ended.'


# ── Rate Limit ────────────────────────────────────────────────────────────────

class ReferralRateLimitError(ReferralBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = 'rate_limit'
    default_detail = 'Too many referral requests. Please slow down.'


class DailyInviteLimitError(ReferralBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = 'invite_limit'
    default_detail = 'Daily invitation limit reached.'


# ── Permission ────────────────────────────────────────────────────────────────

class NotReferralAdminError(ReferralBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'not_admin'
    default_detail = 'Referral admin access required.'


class NotOwnerError(ReferralBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'not_owner'
    default_detail = 'You do not own this referral resource.'


# ── Service Unavailable ───────────────────────────────────────────────────────

class WalletServiceUnavailableError(ReferralBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = 'wallet_unavailable'
    default_detail = 'Wallet service is currently unavailable.'


class NotificationServiceUnavailableError(ReferralBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = 'notification_unavailable'
    default_detail = 'Notification service is unavailable.'


# ── Validation ────────────────────────────────────────────────────────────────

class ReferralValidationError(ReferralBaseException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = 'validation_error'
    default_detail = 'Referral data validation failed.'


# ── Python exceptions (non-DRF) ──────────────────────────────────────────────

class ReferralConfigError(Exception):
    """Raised when referral configuration is missing or invalid."""
    pass


class MigrationConflictError(Exception):
    """Raised on data sync conflicts between referral and other modules."""
    pass