"""
Gamification URLs — DRF Router registration.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    ContestCycleViewSet,
    LeaderboardSnapshotViewSet,
    ContestRewardViewSet,
    UserAchievementViewSet,
)

router = DefaultRouter()
router.register(r"contest-cycles", ContestCycleViewSet, basename="contestcycle")
router.register(r"leaderboard-snapshots", LeaderboardSnapshotViewSet, basename="leaderboardsnapshot")
router.register(r"rewards", ContestRewardViewSet, basename="contestreward")
router.register(r"achievements", UserAchievementViewSet, basename="userachievement")

urlpatterns = [
    path("", include(router.urls)),
]
