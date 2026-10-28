"""
services.py — DEPRECATED
=========================
This module is superseded by the services/ package (services/__init__.py).
All service functions and classes are re-exported here for backward
compatibility, but all new code should import from:

    from api.gamification.services import (
        BadgeService, StreakService, DailyChallengeService,
        LevelUpService, ContestService, PointsService,
        InsightService, SanctionService, LeaderboardRewardService,
        create_contest_cycle, award_achievement, generate_leaderboard_snapshot, ...
    )

Do NOT add new code to this file.
"""
import warnings as _warnings
_warnings.warn(
    "api.gamification.services (module file) is deprecated. "
    "Import from the api.gamification.services package instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the package so existing `from api.gamification.services import X` works
from api.gamification.services import *            # noqa: F401 F403 E402
from api.gamification.services import (            # noqa: F401 E402
    BadgeService,
    StreakService,
    DailyChallengeService,
    LevelUpService,
    ContestService,
    PointsService,
    InsightService,
    SanctionService,
    LeaderboardRewardService,
    # Legacy aliases
    AchievementService,
    LeaderboardService,
    RewardService,
    ChallengeService,
    LevelService,
)
