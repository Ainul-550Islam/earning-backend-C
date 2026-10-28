"""
api/tasks/exceptions.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Custom exception hierarchy for the task system.
All domain-specific errors are defined here so callers
can catch them by type rather than inspecting error messages.
"""

from rest_framework.exceptions import APIException
from rest_framework import status


# ══════════════════════════════════════════════════════════════════════════════
# BASE EXCEPTIONS
# ══════════════════════════════════════════════════════════════════════════════

class TaskSystemError(Exception):
    """Base exception for all task system errors."""
    default_message = 'A task system error occurred.'
    error_code      = 'TASK_SYSTEM_ERROR'

    def __init__(self, message: str = None, error_code: str = None,
                 extra: dict = None):
        self.message    = message or self.default_message
        self.error_code = error_code or self.__class__.error_code
        self.extra      = extra or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            'error':      self.error_code,
            'message':    self.message,
            'extra':      self.extra,
        }


class TaskAPIError(APIException):
    """Base DRF API exception for task endpoints."""
    status_code     = status.HTTP_400_BAD_REQUEST
    default_detail  = 'Task API error.'
    default_code    = 'task_error'


# ══════════════════════════════════════════════════════════════════════════════
# TASK EXECUTION ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class TaskNotFound(TaskSystemError):
    """Raised when a MasterTask is not found."""
    default_message = 'Task not found.'
    error_code      = 'TASK_NOT_FOUND'


class TaskNotActive(TaskSystemError):
    """Raised when a task is not active for completion."""
    default_message = 'Task is not currently active.'
    error_code      = 'TASK_NOT_ACTIVE'


class TaskAlreadyCompleted(TaskSystemError):
    """Raised when user tries to complete a task they already completed."""
    default_message = 'Task has already been completed.'
    error_code      = 'TASK_ALREADY_COMPLETED'


class TaskLimitExceeded(TaskSystemError):
    """Raised when daily/total task completion limit is hit."""
    default_message = 'Task completion limit reached.'
    error_code      = 'TASK_LIMIT_EXCEEDED'


class TaskEligibilityError(TaskSystemError):
    """Raised when user does not meet task eligibility requirements."""
    default_message = 'You are not eligible to complete this task.'
    error_code      = 'TASK_ELIGIBILITY_ERROR'


class TaskExpired(TaskSystemError):
    """Raised when task is past its expiry date."""
    default_message = 'This task has expired.'
    error_code      = 'TASK_EXPIRED'


class TaskConstraintError(TaskSystemError):
    """Raised when task constraints are not satisfied."""
    default_message = 'Task constraints not satisfied.'
    error_code      = 'TASK_CONSTRAINT_ERROR'


class TaskRewardError(TaskSystemError):
    """Raised when reward calculation or crediting fails."""
    default_message = 'Failed to process task reward.'
    error_code      = 'TASK_REWARD_ERROR'


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT & WALLET ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class InsufficientBalance(TaskSystemError):
    """Raised when wallet balance is insufficient for withdrawal."""
    default_message = 'Insufficient balance for this operation.'
    error_code      = 'INSUFFICIENT_BALANCE'


class WithdrawalError(TaskSystemError):
    """General withdrawal processing error."""
    default_message = 'Withdrawal processing failed.'
    error_code      = 'WITHDRAWAL_ERROR'


class WithdrawalBelowMinimum(TaskSystemError):
    """Raised when withdrawal is below the minimum threshold."""
    default_message = 'Withdrawal amount is below the minimum threshold.'
    error_code      = 'WITHDRAWAL_BELOW_MINIMUM'


class WithdrawalMethodInvalid(TaskSystemError):
    """Raised when payout method details are missing or invalid."""
    default_message = 'Invalid or missing payment method details.'
    error_code      = 'WITHDRAWAL_METHOD_INVALID'


class WithdrawalOnHold(TaskSystemError):
    """Raised when withdrawal is blocked due to fraud hold."""
    default_message = 'Withdrawal is currently on hold pending review.'
    error_code      = 'WITHDRAWAL_ON_HOLD'


class PaymentGatewayError(TaskSystemError):
    """Raised when a payment gateway call fails."""
    default_message = 'Payment gateway error. Please try again.'
    error_code      = 'PAYMENT_GATEWAY_ERROR'


class CryptoAddressInvalid(TaskSystemError):
    """Raised when a crypto wallet address is invalid."""
    default_message = 'Invalid cryptocurrency wallet address.'
    error_code      = 'CRYPTO_ADDRESS_INVALID'


class CryptoPriceFetchError(TaskSystemError):
    """Raised when crypto exchange rates cannot be fetched."""
    default_message = 'Failed to fetch cryptocurrency exchange rate.'
    error_code      = 'CRYPTO_PRICE_FETCH_ERROR'


class DailyPayoutAlreadyProcessed(TaskSystemError):
    """Raised when daily payout has already been processed today."""
    default_message = 'Daily payout has already been processed.'
    error_code      = 'DAILY_PAYOUT_ALREADY_PROCESSED'


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD & SECURITY ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class FraudDetected(TaskSystemError):
    """Raised when fraud is detected during a transaction."""
    default_message = 'Suspicious activity detected. Action blocked.'
    error_code      = 'FRAUD_DETECTED'


class AccountSuspended(TaskSystemError):
    """Raised when a suspended account tries to perform an action."""
    default_message = 'Your account has been suspended.'
    error_code      = 'ACCOUNT_SUSPENDED'


class IPBlocked(TaskSystemError):
    """Raised when a request comes from a blocked IP address."""
    default_message = 'Access denied from this IP address.'
    error_code      = 'IP_BLOCKED'


class RateLimitExceeded(TaskSystemError):
    """Raised when an API rate limit is hit."""
    default_message = 'Rate limit exceeded. Please slow down.'
    error_code      = 'RATE_LIMIT_EXCEEDED'


class DuplicateConversion(TaskSystemError):
    """Raised when a postback/conversion is a duplicate."""
    default_message = 'Duplicate conversion detected.'
    error_code      = 'DUPLICATE_CONVERSION'


class InvalidPostbackSignature(TaskSystemError):
    """Raised when a postback HMAC signature is invalid."""
    default_message = 'Invalid postback signature.'
    error_code      = 'INVALID_POSTBACK_SIGNATURE'


# ══════════════════════════════════════════════════════════════════════════════
# KYC ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class KYCRequired(TaskSystemError):
    """Raised when KYC verification is required for an action."""
    default_message = 'KYC verification required for this action.'
    error_code      = 'KYC_REQUIRED'


class KYCRejected(TaskSystemError):
    """Raised when KYC application was rejected."""
    default_message = 'Your KYC application was rejected.'
    error_code      = 'KYC_REJECTED'


class KYCExpired(TaskSystemError):
    """Raised when KYC verification has expired."""
    default_message = 'Your KYC verification has expired. Please re-submit.'
    error_code      = 'KYC_EXPIRED'


class KYCProviderError(TaskSystemError):
    """Raised when the KYC provider API fails."""
    default_message = 'KYC provider is currently unavailable.'
    error_code      = 'KYC_PROVIDER_ERROR'


# ══════════════════════════════════════════════════════════════════════════════
# OFFER / CPA ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class OfferNotFound(TaskSystemError):
    """Raised when an offer cannot be found."""
    default_message = 'Offer not found.'
    error_code      = 'OFFER_NOT_FOUND'


class OfferCapped(TaskSystemError):
    """Raised when an offer has hit its daily/total cap."""
    default_message = 'This offer is no longer available (cap reached).'
    error_code      = 'OFFER_CAPPED'


class OfferExpired(TaskSystemError):
    """Raised when an offer has expired."""
    default_message = 'This offer has expired.'
    error_code      = 'OFFER_EXPIRED'


class OfferGeoRestricted(TaskSystemError):
    """Raised when user's country is not eligible for an offer."""
    default_message = 'This offer is not available in your country.'
    error_code      = 'OFFER_GEO_RESTRICTED'


class PostbackVerificationFailed(TaskSystemError):
    """Raised when postback URL verification fails."""
    default_message = 'Postback URL verification failed.'
    error_code      = 'POSTBACK_VERIFICATION_FAILED'


class ClickNotFound(TaskSystemError):
    """Raised when a click_id cannot be found for attribution."""
    default_message = 'Click record not found for attribution.'
    error_code      = 'CLICK_NOT_FOUND'


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT LOCKER ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class LockerNotFound(TaskSystemError):
    """Raised when a content/link/file locker is not found."""
    default_message = 'Content locker not found.'
    error_code      = 'LOCKER_NOT_FOUND'


class LockerAccessDenied(TaskSystemError):
    """Raised when user does not have active locker access."""
    default_message = 'Content is locked. Complete an offer to access.'
    error_code      = 'LOCKER_ACCESS_DENIED'


class LockerCompletionRequired(TaskSystemError):
    """Raised when offer completion is required to unlock."""
    default_message = 'Please complete a required offer to unlock this content.'
    error_code      = 'LOCKER_COMPLETION_REQUIRED'


class InvalidUnlockToken(TaskSystemError):
    """Raised when an overlay locker access token is invalid."""
    default_message = 'Invalid or expired unlock token.'
    error_code      = 'INVALID_UNLOCK_TOKEN'


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN / ADVERTISER ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class CampaignNotFound(TaskSystemError):
    """Raised when an advertiser campaign is not found."""
    default_message = 'Campaign not found.'
    error_code      = 'CAMPAIGN_NOT_FOUND'


class CampaignPaused(TaskSystemError):
    """Raised when trying to interact with a paused campaign."""
    default_message = 'This campaign is currently paused.'
    error_code      = 'CAMPAIGN_PAUSED'


class CampaignBudgetExhausted(TaskSystemError):
    """Raised when campaign budget is fully spent."""
    default_message = 'Campaign budget has been exhausted.'
    error_code      = 'CAMPAIGN_BUDGET_EXHAUSTED'


class AdvertiserBalanceLow(TaskSystemError):
    """Raised when advertiser balance is too low for campaign activation."""
    default_message = 'Advertiser balance too low. Please add funds.'
    error_code      = 'ADVERTISER_BALANCE_LOW'


class CampaignValidationError(TaskSystemError):
    """Raised when campaign fails pre-submission validation."""
    default_message = 'Campaign validation failed.'
    error_code      = 'CAMPAIGN_VALIDATION_ERROR'


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowNotFound(TaskSystemError):
    """Raised when a workflow is not found."""
    default_message = 'Workflow not found.'
    error_code      = 'WORKFLOW_NOT_FOUND'


class WorkflowAlreadyRunning(TaskSystemError):
    """Raised when trying to start a workflow that is already running."""
    default_message = 'Workflow is already running.'
    error_code      = 'WORKFLOW_ALREADY_RUNNING'


class WorkflowStepFailed(TaskSystemError):
    """Raised when a workflow step fails."""
    default_message = 'Workflow step execution failed.'
    error_code      = 'WORKFLOW_STEP_FAILED'


class WorkflowCancelled(TaskSystemError):
    """Raised when a workflow instance has been cancelled."""
    default_message = 'Workflow has been cancelled.'
    error_code      = 'WORKFLOW_CANCELLED'


class WorkflowInstanceNotFound(TaskSystemError):
    """Raised when a workflow instance is not found."""
    default_message = 'Workflow instance not found.'
    error_code      = 'WORKFLOW_INSTANCE_NOT_FOUND'


# ══════════════════════════════════════════════════════════════════════════════
# DEAD LETTER QUEUE ERRORS
# ══════════════════════════════════════════════════════════════════════════════

class DLQEntryNotFound(TaskSystemError):
    """Raised when a DLQ entry is not found."""
    default_message = 'Dead letter queue entry not found.'
    error_code      = 'DLQ_ENTRY_NOT_FOUND'


class DLQRetryFailed(TaskSystemError):
    """Raised when DLQ retry dispatch fails."""
    default_message = 'Failed to requeue dead letter task.'
    error_code      = 'DLQ_RETRY_FAILED'


# ══════════════════════════════════════════════════════════════════════════════
# API EXCEPTIONS (DRF-compatible)
# ══════════════════════════════════════════════════════════════════════════════

class TaskNotFoundAPI(TaskAPIError):
    status_code    = status.HTTP_404_NOT_FOUND
    default_detail = 'Task not found.'
    default_code   = 'task_not_found'


class TaskForbiddenAPI(TaskAPIError):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission for this task action.'
    default_code   = 'task_forbidden'


class TaskConflictAPI(TaskAPIError):
    status_code    = status.HTTP_409_CONFLICT
    default_detail = 'Task conflict: action cannot be completed.'
    default_code   = 'task_conflict'


class PaymentRequiredAPI(TaskAPIError):
    status_code    = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment or balance is required for this action.'
    default_code   = 'payment_required'


class FraudDetectedAPI(TaskAPIError):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = 'Suspicious activity detected. Action blocked.'
    default_code   = 'fraud_detected'


class RateLimitExceededAPI(TaskAPIError):
    status_code    = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Rate limit exceeded. Please slow down.'
    default_code   = 'rate_limit_exceeded'


class ServiceUnavailableAPI(TaskAPIError):
    status_code    = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Service temporarily unavailable. Please try again.'
    default_code   = 'service_unavailable'


# ══════════════════════════════════════════════════════════════════════════════
# EXCEPTION HANDLER MAPPING
# ══════════════════════════════════════════════════════════════════════════════

EXCEPTION_HTTP_STATUS_MAP = {
    TaskNotFound:              404,
    OfferNotFound:             404,
    LockerNotFound:            404,
    CampaignNotFound:          404,
    WorkflowNotFound:          404,
    DLQEntryNotFound:          404,
    WorkflowInstanceNotFound:  404,
    TaskNotActive:             400,
    TaskAlreadyCompleted:      409,
    TaskLimitExceeded:         429,
    TaskEligibilityError:      403,
    TaskExpired:               410,
    FraudDetected:             403,
    AccountSuspended:          403,
    IPBlocked:                 403,
    RateLimitExceeded:         429,
    InsufficientBalance:       402,
    WithdrawalBelowMinimum:    400,
    WithdrawalMethodInvalid:   400,
    WithdrawalOnHold:          409,
    PaymentGatewayError:       502,
    CryptoAddressInvalid:      400,
    KYCRequired:               403,
    KYCRejected:               403,
    OfferCapped:               410,
    OfferExpired:              410,
    OfferGeoRestricted:        403,
    DuplicateConversion:       409,
    InvalidPostbackSignature:  401,
    LockerAccessDenied:        403,
    InvalidUnlockToken:        401,
    CampaignPaused:            409,
    CampaignBudgetExhausted:   402,
    WorkflowAlreadyRunning:    409,
    WorkflowStepFailed:        500,
}


def get_http_status_for_exception(exc: TaskSystemError) -> int:
    """Return appropriate HTTP status code for a TaskSystemError."""
    return EXCEPTION_HTTP_STATUS_MAP.get(type(exc), 400)


__all__ = [
    'TaskSystemError', 'TaskAPIError',
    'TaskNotFound', 'TaskNotActive', 'TaskAlreadyCompleted',
    'TaskLimitExceeded', 'TaskEligibilityError', 'TaskExpired',
    'TaskConstraintError', 'TaskRewardError',
    'InsufficientBalance', 'WithdrawalError', 'WithdrawalBelowMinimum',
    'WithdrawalMethodInvalid', 'WithdrawalOnHold', 'PaymentGatewayError',
    'CryptoAddressInvalid', 'CryptoPriceFetchError', 'DailyPayoutAlreadyProcessed',
    'FraudDetected', 'AccountSuspended', 'IPBlocked', 'RateLimitExceeded',
    'DuplicateConversion', 'InvalidPostbackSignature',
    'KYCRequired', 'KYCRejected', 'KYCExpired', 'KYCProviderError',
    'OfferNotFound', 'OfferCapped', 'OfferExpired', 'OfferGeoRestricted',
    'PostbackVerificationFailed', 'ClickNotFound',
    'LockerNotFound', 'LockerAccessDenied', 'LockerCompletionRequired', 'InvalidUnlockToken',
    'CampaignNotFound', 'CampaignPaused', 'CampaignBudgetExhausted',
    'AdvertiserBalanceLow', 'CampaignValidationError',
    'WorkflowNotFound', 'WorkflowAlreadyRunning', 'WorkflowStepFailed',
    'WorkflowCancelled', 'WorkflowInstanceNotFound',
    'DLQEntryNotFound', 'DLQRetryFailed',
    'TaskNotFoundAPI', 'TaskForbiddenAPI', 'TaskConflictAPI',
    'PaymentRequiredAPI', 'FraudDetectedAPI', 'RateLimitExceededAPI',
    'ServiceUnavailableAPI',
    'EXCEPTION_HTTP_STATUS_MAP', 'get_http_status_for_exception',
]


# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL EXCEPTIONS — Added to resolve missing imports
# ══════════════════════════════════════════════════════════════════════════════

class PostbackProcessingException(TaskSystemError):
    """Raised when postback processing fails."""
    pass


class SubmissionAlreadyProcessedError(TaskSystemError):
    """Raised when trying to process an already-processed submission."""
    pass


class DeliveryFailedException(TaskSystemError):
    """Raised when item/reward delivery fails after all retries."""
    pass


# Payout batch exceptions
class PayoutQueueError(TaskSystemError):
    """Base error for payout queue operations."""
    pass


class PayoutBatchNotFoundError(PayoutQueueError):
    """Raised when a payout batch cannot be found."""
    pass


class PayoutBatchLockedError(PayoutQueueError):
    """Raised when a payout batch is locked by another process."""
    pass


class PayoutBatchStateError(PayoutQueueError):
    """Raised when a payout batch is in an invalid state for the operation."""
    pass


class PayoutBatchLimitError(PayoutQueueError):
    """Raised when payout batch limits are exceeded."""
    pass


# Broadcast exceptions
class BroadcastNotFoundError(TaskSystemError):
    """Raised when a broadcast message cannot be found."""
    pass


class BroadcastStateError(TaskSystemError):
    """Raised when a broadcast is in an invalid state for the operation."""
    pass


class BroadcastSendError(TaskSystemError):
    """Raised when sending a broadcast fails."""
    pass
