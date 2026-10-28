"""
viewset.py — DEPRECATED
=======================
This file is superseded by viewsets.py which contains the canonical ViewSet
implementations. All classes here are re-exported from viewsets.py for
backward compatibility. Do NOT add new code here.

Import from viewsets.py directly:
    from api.gamification.viewsets import BadgeViewSet, StreakViewSet, ...
"""
import warnings

warnings.warn(
    "api.gamification.viewset is deprecated. Import from api.gamification.viewsets instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export canonical implementations for any legacy import paths
from api.gamification.viewsets import (  # noqa: F401 E402
    ContestCycleViewSet,
    ContestRewardViewSet,
    UserAchievementViewSet,
    LeaderboardSnapshotViewSet,
    BadgeViewSet,
    DailyChallengeViewSet,
    StreakViewSet,
    LevelViewSet as LevelConfigViewSet,
    GamificationResponseMixin,
)

# These were only in viewset.py — they now have their canonical home in viewsets.py
# but we keep aliases here so nothing breaks
from api.gamification.viewsets import LevelViewSet as LevelConfigViewSet  # noqa: F811
try:
    from api.gamification.viewsets import UserBadgeViewSet          # noqa: F401
    from api.gamification.viewsets import UserDailyChallengeViewSet # noqa: F401
    from api.gamification.viewsets import StreakRewardViewSet       # noqa: F401
except ImportError:
    pass  # These may not exist in viewsets.py; callers should update their imports
