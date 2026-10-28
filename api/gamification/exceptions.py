"""
Gamification Exceptions — Domain-specific exception hierarchy.

All exceptions inherit from GamificationServiceError so callers can
catch the base class or any specific subclass.
"""


class GamificationServiceError(Exception):
    """Base exception for all gamification service layer errors."""


class ContestCycleNotFoundError(GamificationServiceError):
    """Raised when a ContestCycle lookup by pk fails."""


class ContestCycleStateError(GamificationServiceError):
    """Raised when a requested state transition is not permitted."""


class InvalidPointsError(GamificationServiceError):
    """Raised when a points value is None, non-numeric, or out of range."""


class DuplicateAchievementError(GamificationServiceError):
    """Raised on concurrent creation of the same (user, type, cycle) achievement."""


class RewardAlreadyClaimedError(GamificationServiceError):
    """Raised when a ContestReward budget is exhausted."""


class LeaderboardGenerationError(GamificationServiceError):
    """Raised when leaderboard snapshot generation fails."""


class UserNotFoundError(GamificationServiceError):
    """Raised when a User lookup by pk fails."""


# ---------------------------------------------------------------------------
# New Exceptions for Added Models
# ---------------------------------------------------------------------------

class InsufficientPointsError(GamificationServiceError):
    """Raised when user doesn't have enough points for an operation."""


class PointsTransactionError(GamificationServiceError):
    """Raised when points transaction creation or processing fails."""


class StreakFreezeError(GamificationServiceError):
    """Raised when streak freeze operation fails."""


class StreakFreezeLimitExceededError(GamificationServiceError):
    """Raised when user exceeds freeze usage limits."""


class ContestParticipantError(GamificationServiceError):
    """Raised when contest participant operation fails."""


class ContestFullError(GamificationServiceError):
    """Raised when contest has reached maximum participants."""


class ContestNotActiveError(GamificationServiceError):
    """Raised when trying to join a non-active contest."""


class ParticipantDisqualifiedError(GamificationServiceError):
    """Raised when disqualified participant tries to perform actions."""


class GamificationConfigError(GamificationServiceError):
    """Raised when gamification config operation fails."""


class FeatureNotEnabledError(GamificationServiceError):
    """Raised when trying to use a disabled gamification feature."""


class GamificationInsightError(GamificationServiceError):
    """Raised when insight calculation or retrieval fails."""


class InvalidDateRangeError(GamificationServiceError):
    """Raised when date range for insights is invalid."""


class RateLimitExceededError(GamificationServiceError):
    """Raised when user exceeds rate limits for gamification operations."""


class InvalidSourceError(GamificationServiceError):
    """Raised when points transaction source is invalid."""


class PointsExpiryError(GamificationServiceError):
    """Raised when points expire or expiry processing fails."""


class LeaderboardRefreshError(GamificationServiceError):
    """Raised when leaderboard refresh operation fails."""


class ConfigurationValidationError(GamificationServiceError):
    """Raised when gamification config validation fails."""


class InsightCalculationTimeoutError(GamificationServiceError):
    """Raised when insight calculation takes too long."""


class ComplianceError(GamificationServiceError):
    """Raised when a compliance rule is violated."""
    pass


class PrivacyError(GamificationServiceError):
    """Raised when a privacy rule is violated."""
    pass
