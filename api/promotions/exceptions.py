# =============================================================================
# api/promotions/exceptions.py
# Custom Exception Classes — DRF এর সাথে পুরোপুরি compatible
# =============================================================================

from rest_framework import status
from rest_framework.exceptions import APIException
from django.utils.translation import gettext_lazy as _


# ─── Base ─────────────────────────────────────────────────────────────────────

class PromotionBaseException(APIException):
    """সব promotion exception এর parent।"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('একটি error হয়েছে।')
    default_code = 'promotion_error'


# ─── Campaign Exceptions ──────────────────────────────────────────────────────

class CampaignNotFoundException(PromotionBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Campaign খুঁজে পাওয়া যায়নি।')
    default_code = 'campaign_not_found'


class CampaignNotActiveException(PromotionBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Campaign বর্তমানে active নেই।')
    default_code = 'campaign_not_active'


class CampaignFullException(PromotionBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Campaign এর সব slot পূর্ণ হয়ে গেছে।')
    default_code = 'campaign_full'


class CampaignBudgetExhaustedException(PromotionBaseException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = _('Campaign এর বাজেট শেষ হয়ে গেছে।')
    default_code = 'campaign_budget_exhausted'


class CampaignPermissionDeniedException(PromotionBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('এই campaign পরিচালনার অনুমতি নেই।')
    default_code = 'campaign_permission_denied'


class InvalidCampaignTransitionException(PromotionBaseException):
    """Campaign status এর invalid transition।"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('এই status পরিবর্তন করা সম্ভব নয়।')
    default_code = 'invalid_campaign_transition'

    def __init__(self, from_status: str, to_status: str):
        detail = _(f'Campaign status "{from_status}" থেকে "{to_status}" তে পরিবর্তন করা যাবে না।')
        super().__init__(detail=detail)


# ─── Submission Exceptions ────────────────────────────────────────────────────

class SubmissionNotFoundException(PromotionBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Submission খুঁজে পাওয়া যায়নি।')
    default_code = 'submission_not_found'


class DuplicateSubmissionException(PromotionBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('আপনি ইতিমধ্যে এই campaign এ কাজ জমা দিয়েছেন।')
    default_code = 'duplicate_submission'


class SubmissionCooldownException(PromotionBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('Cooldown period এখনো শেষ হয়নি। পরে আবার চেষ্টা করুন।')
    default_code = 'submission_cooldown'

    def __init__(self, retry_after_seconds: int = None):
        super().__init__()
        if retry_after_seconds:
            self.detail = _(f'{retry_after_seconds} সেকেন্ড পরে আবার চেষ্টা করুন।')


class SubmissionAlreadyReviewedException(PromotionBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('এই submission ইতিমধ্যে review করা হয়েছে।')
    default_code = 'submission_already_reviewed'


class InvalidProofException(PromotionBaseException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _('জমা দেওয়া proof গ্রহণযোগ্য নয়।')
    default_code = 'invalid_proof'


class MissingProofStepException(PromotionBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('সব required step এর proof জমা দিতে হবে।')
    default_code = 'missing_proof_step'

    def __init__(self, missing_step_ids: list = None):
        if missing_step_ids:
            detail = _(f'Step {missing_step_ids} এর proof দেওয়া হয়নি।')
            super().__init__(detail=detail)
        else:
            super().__init__()


# ─── Dispute Exceptions ───────────────────────────────────────────────────────

class DisputeNotFoundException(PromotionBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Dispute খুঁজে পাওয়া যায়নি।')
    default_code = 'dispute_not_found'


class DisputeAlreadyExistsException(PromotionBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('এই submission এর বিরুদ্ধে ইতিমধ্যে একটি dispute আছে।')
    default_code = 'dispute_already_exists'


class DisputeNotAllowedException(PromotionBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('শুধুমাত্র rejected submission এর বিরুদ্ধে dispute করা যাবে।')
    default_code = 'dispute_not_allowed'


# ─── Finance / Wallet Exceptions ─────────────────────────────────────────────

class InsufficientBalanceException(PromotionBaseException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = _('পর্যাপ্ত balance নেই।')
    default_code = 'insufficient_balance'

    def __init__(self, required: str = None, available: str = None):
        if required and available:
            detail = _(f'প্রয়োজন: ${required}, উপলব্ধ: ${available}')
            super().__init__(detail=detail)
        else:
            super().__init__()


class EscrowReleaseException(PromotionBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Escrow release করা সম্ভব হয়নি।')
    default_code = 'escrow_release_failed'


class WithdrawalLimitException(PromotionBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Withdrawal amount সীমার বাইরে।')
    default_code = 'withdrawal_limit_exceeded'


class CurrencyRateNotFoundException(PromotionBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = _('এই currency এর বর্তমান rate পাওয়া যাচ্ছে না।')
    default_code = 'currency_rate_not_found'


# ─── Security / Fraud Exceptions ─────────────────────────────────────────────

class BlacklistedException(PromotionBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('আপনার অ্যাকাউন্ট বা ডিভাইস নিষিদ্ধ করা হয়েছে।')
    default_code = 'blacklisted'

    def __init__(self, reason: str = None):
        if reason:
            super().__init__(detail=_(f'নিষিদ্ধ: {reason}'))
        else:
            super().__init__()


class FraudDetectedException(PromotionBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('সন্দেহজনক কার্যক্রম সনাক্ত হয়েছে। আপনার submission গ্রহণ করা হয়নি।')
    default_code = 'fraud_detected'


class IPLimitExceededException(PromotionBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('এই IP থেকে সর্বোচ্চ সংখ্যক submission হয়ে গেছে।')
    default_code = 'ip_limit_exceeded'


class DeviceLimitExceededException(PromotionBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('এই device থেকে সর্বোচ্চ সংখ্যক submission হয়ে গেছে।')
    default_code = 'device_limit_exceeded'


class TargetingMismatchException(PromotionBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('আপনার location, device বা level এই campaign এর জন্য eligible নয়।')
    default_code = 'targeting_mismatch'


# ─── Reward / Reputation Exceptions ──────────────────────────────────────────

class RewardPolicyNotFoundException(PromotionBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('আপনার দেশের জন্য কোনো reward policy পাওয়া যায়নি।')
    default_code = 'reward_policy_not_found'


class ReputationTooLowException(PromotionBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('এই campaign এ অংশ নিতে আপনার reputation score যথেষ্ট নয়।')
    default_code = 'reputation_too_low'

    def __init__(self, required: int = None, current: int = None):
        if required and current is not None:
            detail = _(f'প্রয়োজনীয় score: {required}, আপনার score: {current}')
            super().__init__(detail=detail)
        else:
            super().__init__()
