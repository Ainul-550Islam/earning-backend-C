# engagement/exceptions.py
from rest_framework.exceptions import APIException
from rest_framework import status


class EngagementError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "engagement_error"

    def __init__(self, detail=None, code=None):
        super().__init__(detail or self.default_detail, code)


class AlreadyCheckedInError(EngagementError):
    default_detail = "Already checked in today."
    default_code   = "already_checked_in"


class MaxSpinsReachedError(EngagementError):
    default_detail = "Maximum spins reached for today."
    default_code   = "max_spins_reached"


class InsufficientCoinsError(EngagementError):
    default_detail = "Insufficient coin balance."
    default_code   = "insufficient_coins"


class ItemNotAvailableError(EngagementError):
    default_detail = "Item is not available."
    default_code   = "item_not_available"


class QuestExpiredError(EngagementError):
    default_detail = "Quest has expired."
    default_code   = "quest_expired"


class ChallengeNotActiveError(EngagementError):
    default_detail = "Challenge is not active."
    default_code   = "challenge_not_active"


class ReferralSelfError(EngagementError):
    default_detail = "Cannot refer yourself."
    default_code   = "referral_self"


class AlreadyReferredError(EngagementError):
    default_detail = "User has already been referred."
    default_code   = "already_referred"
