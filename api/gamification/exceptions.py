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
