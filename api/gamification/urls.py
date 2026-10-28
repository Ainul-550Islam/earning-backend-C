"""
Gamification URLs — DRF Router registration.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from api.gamification.choices import LeaderboardScope
from api.gamification.constants import DEFAULT_LEADERBOARD_TOP_N
from api.gamification.exceptions import (
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
)
from api.gamification.services import (
    ContestCycleService,
    LeaderboardService,
    RewardService,
    AchievementService,
)
from api.gamification.viewsets import (
    SanctionViewSet,
    ContestCycleViewSet,
    LeaderboardSnapshotViewSet,
    ContestRewardViewSet,
    UserAchievementViewSet,
    BadgeViewSet,
    DailyChallengeViewSet,
    StreakViewSet,
    LevelViewSet,
    GamificationSummaryViewSet,
    UserPointsViewSet,
    PointsTransactionViewSet,
    StreakFreezeViewSet,
    ContestParticipantViewSet,
    GamificationConfigViewSet,
    GamificationInsightViewSet,
)

router = DefaultRouter()
router.register(r"contest-cycles", ContestCycleViewSet, basename="contestcycle")
router.register(r"leaderboard-snapshots", LeaderboardSnapshotViewSet, basename="leaderboardsnapshot")
router.register(r"rewards", ContestRewardViewSet, basename="contestreward")
router.register(r"achievements", UserAchievementViewSet, basename="userachievement")
router.register(r"badges", BadgeViewSet, basename="badge")
router.register(r"daily-challenges", DailyChallengeViewSet, basename="dailychallenge")
router.register(r"streaks", StreakViewSet, basename="streak")
router.register(r"levels", LevelViewSet, basename="level")
router.register(r"summary", GamificationSummaryViewSet, basename="gamificationsummary")
router.register(r"user-points", UserPointsViewSet, basename="userpoints")
router.register(r"points-transactions", PointsTransactionViewSet, basename="pointstransaction")
router.register(r"streak-freezes", StreakFreezeViewSet, basename="streakfreeze")
router.register(r"contest-participants", ContestParticipantViewSet, basename="contestparticipant")
router.register(r"gamification-config", GamificationConfigViewSet, basename="gamificationconfig")
router.register(r"gamification-insights", GamificationInsightViewSet, basename="gamificationinsight")

router.register(r"sanctions", SanctionViewSet, basename="sanction")

urlpatterns = [
    path("", include(router.urls)),
]
