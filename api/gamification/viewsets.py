"""
Gamification ViewSets — DRF ViewSets wiring models to the REST API.
All mutations go through the service layer; viewsets handle HTTP concerns only.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import IntegrityError, models
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.gamification.choices import ContestCycleStatus, LeaderboardScope
from api.gamification.constants import DEFAULT_LEADERBOARD_TOP_N
from api.gamification.exceptions import (
    GamificationServiceError,
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
    InvalidPointsError,
    DuplicateAchievementError,
    UserNotFoundError,
)
from api.gamification.filters import ContestCycleFilter, ContestRewardFilter, UserAchievementFilter
from api.gamification.models import (
    ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement,
    UserPoints, PointsTransaction, StreakFreeze, ContestParticipant, 
    GamificationConfig, GamificationInsight
)
from api.gamification.pagination import GamificationPagination
from api.gamification.throttling import GamificationRateThrottle, UserActionThrottle
from api.gamification.permissions import IsAdminOrReadOnly, IsOwnerOrAdmin
from api.gamification.serializers import (
    ContestCycleSerializer,
    ContestCycleListSerializer,
    LeaderboardSnapshotSerializer,
    ContestRewardSerializer,
    UserAchievementSerializer,
    UserPointsSerializer,
    PointsTransactionSerializer,
    StreakFreezeSerializer,
    ContestParticipantSerializer,
    GamificationConfigSerializer,
    GamificationInsightSerializer,
)
from api.gamification.serializers import (
    BadgeSerializer,
    UserBadgeSerializer,
    BadgeStatisticsSerializer,
    DailyChallengeSerializer,
    UserDailyChallengeSerializer,
    ChallengeProgressSerializer,
    ChallengeStatisticsSerializer,
    DailyChallengeCreateSerializer,
    ChallengeStartSerializer,
    StreakSerializer,
    StreakStatisticsSerializer,
    StreakMilestoneSerializer,
    LevelConfigSerializer,
    LevelProgressSerializer,
    LevelStatisticsSerializer,
    LevelConfigCreateSerializer,
    LevelRequirementsSerializer,
    GamificationSummarySerializer,
)
from api.gamification import services
from api.gamification.services import (
    BadgeService,
    DailyChallengeService,
    StreakService,
    LevelUpService,
    LeaderboardRewardService,
)
from api.gamification.models import Streak

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Badge ViewSet
# ---------------------------------------------------------------------------

class BadgeViewSet(viewsets.ViewSet):
    """ViewSet for Badge operations."""
    permission_classes = [IsAdminOrReadOnly]
    
    def list(self, request: Request) -> Response:
        """List all available badges."""
        try:
            is_active = request.query_params.get('is_active', 'true').lower() == 'true'
            rarity = request.query_params.get('rarity')
            criteria_type = request.query_params.get('criteria_type')
            
            badges = BadgeService.get_available_badges(
                is_active=is_active,
                rarity=rarity,
                criteria_type=criteria_type
            )
            
            serializer = BadgeSerializer(badges, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to list badges")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_badges(self, request: Request) -> Response:
        """Get current user's badges."""
        try:
            is_pinned = request.query_params.get('is_pinned')
            if is_pinned is not None:
                is_pinned = is_pinned.lower() == 'true'
            
            rarity = request.query_params.get('rarity')
            limit = request.query_params.get('limit')
            
            if limit is not None:
                limit = int(limit)
            
            user_badges = BadgeService.get_user_badges(
                user_id=request.user.id,
                is_pinned=is_pinned,
                rarity=rarity,
                limit=limit
            )
            
            serializer = UserBadgeSerializer(user_badges, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get user badges")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def statistics(self, request: Request) -> Response:
        """Get badge statistics for current user."""
        try:
            stats = BadgeService.get_badge_statistics(user_id=request.user.id)
            serializer = BadgeStatisticsSerializer(stats)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get badge statistics")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def check_eligibility(self, request: Request) -> Response:
        """Check badge eligibility for current user."""
        try:
            user_points = request.data.get('user_points', 0)
            streak_days = request.data.get('streak_days', 0)
            achievement_count = request.data.get('achievement_count', 0)
            contest_wins = request.data.get('contest_wins', 0)
            referral_count = request.data.get('referral_count', 0)
            
            eligible_badges = BadgeService.check_user_badge_eligibility(
                user_id=request.user.id,
                user_points=user_points,
                streak_days=streak_days,
                achievement_count=achievement_count,
                contest_wins=contest_wins,
                referral_count=referral_count
            )
            
            serializer = BadgeSerializer(eligible_badges, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to check badge eligibility")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def award_eligible(self, request: Request) -> Response:
        """Award all eligible badges to current user."""
        try:
            user_points = request.data.get('user_points', 0)
            streak_days = request.data.get('streak_days', 0)
            achievement_count = request.data.get('achievement_count', 0)
            contest_wins = request.data.get('contest_wins', 0)
            referral_count = request.data.get('referral_count', 0)
            metadata = request.data.get('metadata', {})
            
            awarded_badges = BadgeService.award_eligible_badges(
                user_id=request.user.id,
                user_points=user_points,
                streak_days=streak_days,
                achievement_count=achievement_count,
                contest_wins=contest_wins,
                referral_count=referral_count,
                metadata=metadata
            )
            
            serializer = UserBadgeSerializer(awarded_badges, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to award eligible badges")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def pin(self, request: Request) -> Response:
        """Pin a user badge."""
        try:
            user_badge_id = request.data.get('user_badge_id')
            if not user_badge_id:
                return Response(
                    {"detail": "user_badge_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_badge = BadgeService.pin_user_badge(
                user_id=request.user.id,
                user_badge_id=user_badge_id
            )
            
            serializer = UserBadgeSerializer(user_badge)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to pin badge")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def unpin(self, request: Request) -> Response:
        """Unpin a user badge."""
        try:
            user_badge_id = request.data.get('user_badge_id')
            if not user_badge_id:
                return Response(
                    {"detail": "user_badge_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_badge = BadgeService.unpin_user_badge(
                user_id=request.user.id,
                user_badge_id=user_badge_id
            )
            
            serializer = UserBadgeSerializer(user_badge)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to unpin badge")


# ---------------------------------------------------------------------------
# Daily Challenge ViewSet
# ---------------------------------------------------------------------------

class DailyChallengeViewSet(viewsets.ViewSet):
    """ViewSet for Daily Challenge operations."""
    permission_classes = [IsAdminOrReadOnly]
    
    def list(self, request: Request) -> Response:
        """List active daily challenges."""
        try:
            challenge_date = request.query_params.get('date')
            if challenge_date:
                from datetime import datetime
                challenge_date = datetime.strptime(challenge_date, '%Y-%m-%d').date()
            
            target_action = request.query_params.get('target_action')
            
            challenges = DailyChallengeService.get_active_challenges(
                challenge_date=challenge_date,
                target_action=target_action
            )
            
            serializer = DailyChallengeSerializer(challenges, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to list daily challenges")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def create_challenge(self, request: Request) -> Response:
        """Create a new daily challenge."""
        try:
            serializer = DailyChallengeCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            challenge = DailyChallengeService.create_daily_challenge(
                title=serializer.validated_data['title'],
                description=serializer.validated_data.get('description', ''),
                target_action=serializer.validated_data['target_action'],
                target_count=serializer.validated_data['target_count'],
                bonus_points=serializer.validated_data['bonus_points'],
                challenge_date=serializer.validated_data.get('challenge_date'),
                metadata=serializer.validated_data.get('metadata', {})
            )
            
            response_serializer = DailyChallengeSerializer(challenge)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to create daily challenge")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_progress(self, request: Request) -> Response:
        """Get current user's challenge progress."""
        try:
            challenge_id = request.query_params.get('challenge_id')
            challenge_date = request.query_params.get('date')
            
            if challenge_date:
                from datetime import datetime
                challenge_date = datetime.strptime(challenge_date, '%Y-%m-%d').date()
            
            user_challenges = DailyChallengeService.get_user_challenge_progress(
                user_id=request.user.id,
                challenge_id=challenge_id,
                challenge_date=challenge_date
            )
            
            serializer = UserDailyChallengeSerializer(user_challenges, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get challenge progress")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def start_challenge(self, request: Request) -> Response:
        """Start a daily challenge for current user."""
        try:
            serializer = ChallengeStartSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            user_challenge = DailyChallengeService.start_user_challenge(
                user_id=request.user.id,
                challenge_id=serializer.validated_data['challenge_id']
            )
            
            response_serializer = UserDailyChallengeSerializer(user_challenge)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to start challenge")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_progress(self, request: Request) -> Response:
        """Update progress on a daily challenge."""
        try:
            challenge_id = request.data.get('challenge_id')
            if not challenge_id:
                return Response(
                    {"detail": "challenge_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = ChallengeProgressSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            user_challenge, completed = DailyChallengeService.update_challenge_progress(
                user_id=request.user.id,
                challenge_id=challenge_id,
                increment_amount=serializer.validated_data['increment_amount'],
                action_metadata=serializer.validated_data.get('action_metadata', {})
            )
            
            response_serializer = UserDailyChallengeSerializer(user_challenge)
            return Response({
                "user_challenge": response_serializer.data,
                "completed": completed
            })
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to update challenge progress")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def auto_start(self, request: Request) -> Response:
        """Auto-start all active challenges for current user."""
        try:
            started_challenges = DailyChallengeService.auto_start_active_challenges(
                user_id=request.user.id
            )
            
            serializer = UserDailyChallengeSerializer(started_challenges, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to auto-start challenges")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def statistics(self, request: Request) -> Response:
        """Get challenge statistics for current user."""
        try:
            days = int(request.query_params.get('days', 30))
            
            stats = DailyChallengeService.get_challenge_statistics(
                user_id=request.user.id,
                days=days
            )
            
            serializer = ChallengeStatisticsSerializer(stats)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get challenge statistics")
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request: Request) -> Response:
        """Get challenge leaderboard."""
        try:
            challenge_date = request.query_params.get('date')
            if challenge_date:
                from datetime import datetime
                challenge_date = datetime.strptime(challenge_date, '%Y-%m-%d').date()
            
            limit = int(request.query_params.get('limit', 10))
            
            leaderboard = DailyChallengeService.get_leaderboard(
                challenge_date=challenge_date,
                limit=limit
            )
            
            return Response(leaderboard)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get challenge leaderboard")


# ---------------------------------------------------------------------------
# Streak ViewSet
# ---------------------------------------------------------------------------

class StreakViewSet(viewsets.ViewSet):
    """ViewSet for Streak operations."""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def my_streak(self, request: Request) -> Response:
        """Get current user's streak information."""
        try:
            streak = StreakService.get_or_create_user_streak(user_id=request.user.id)
            serializer = StreakSerializer(streak)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get user streak")
    
    @action(detail=False, methods=['post'])
    def update_activity(self, request: Request) -> Response:
        """Update user's streak activity."""
        try:
            activity_date = request.data.get('activity_date')
            if activity_date:
                from datetime import datetime
                activity_date = datetime.strptime(activity_date, '%Y-%m-%d').date()
            
            metadata = request.data.get('metadata', {})
            
            streak, was_extended, days_added = StreakService.update_user_activity(
                user_id=request.user.id,
                activity_date=activity_date,
                metadata=metadata
            )
            
            serializer = StreakSerializer(streak)
            return Response({
                "streak": serializer.data,
                "was_extended": was_extended,
                "days_added": days_added
            })
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to update streak activity")
    
    @action(detail=False, methods=['post'])
    def reset(self, request: Request) -> Response:
        """Reset user's streak."""
        try:
            reason = request.data.get('reason', 'manual_reset')
            
            streak = StreakService.reset_user_streak(
                user_id=request.user.id,
                reason=reason
            )
            
            serializer = StreakSerializer(streak)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to reset streak")
    
    @action(detail=False, methods=['get'])
    def statistics(self, request: Request) -> Response:
        """Get streak statistics for current user."""
        try:
            stats = StreakService.get_streak_statistics(user_id=request.user.id)
            serializer = StreakStatisticsSerializer(stats)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get streak statistics")
    
    @action(detail=False, methods=['get'])
    def milestones(self, request: Request) -> Response:
        """Get streak milestones for current user."""
        try:
            milestones = StreakService.get_streak_milestones(user_id=request.user.id)
            serializer = StreakMilestoneSerializer(milestones, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get streak milestones")
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request: Request) -> Response:
        """Get streak leaderboard."""
        try:
            limit = int(request.query_params.get('limit', 10))
            active_only = request.query_params.get('active_only', 'true').lower() == 'true'
            
            leaderboard = StreakService.get_streak_leaderboard(
                limit=limit,
                active_only=active_only
            )
            
            return Response(leaderboard)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get streak leaderboard")


# ---------------------------------------------------------------------------
# Level ViewSet
# ---------------------------------------------------------------------------

class LevelViewSet(viewsets.ViewSet):
    """ViewSet for Level operations."""
    permission_classes = [IsAdminOrReadOnly]
    
    def list(self, request: Request) -> Response:
        """List all available levels."""
        try:
            is_active = request.query_params.get('is_active', 'true').lower() == 'true'
            
            levels = LevelUpService.get_available_levels(is_active=is_active)
            serializer = LevelConfigSerializer(levels, many=True)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to list levels")
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def create_level(self, request: Request) -> Response:
        """Create a new level configuration."""
        try:
            serializer = LevelConfigCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            level_config = LevelUpService.create_level_config(
                level_number=serializer.validated_data['level_number'],
                points_required=serializer.validated_data['points_required'],
                title=serializer.validated_data['title'],
                description=serializer.validated_data.get('description', ''),
                perks=serializer.validated_data.get('perks', {}),
                points_multiplier=serializer.validated_data.get('points_multiplier', 1.0),
                badge_id=serializer.validated_data.get('badge_id'),
                metadata=serializer.validated_data.get('metadata', {})
            )
            
            response_serializer = LevelConfigSerializer(level_config)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to create level")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def current_level(self, request: Request) -> Response:
        """Get current user's level information."""
        try:
            # Calculate user's total points from achievements
            from api.gamification.models import UserAchievement
            from django.db.models import Sum
            
            total_points = UserAchievement.objects.filter(
                user=request.user,
                is_awarded=True
            ).aggregate(total=Sum('points_awarded'))['total'] or 0
            
            current_level = LevelUpService.get_user_level(total_points)
            progress = LevelUpService.get_level_progress(total_points)
            
            return Response({
                "total_points": total_points,
                "current_level": current_level.level_number if current_level else 0,
                "current_level_title": current_level.title if current_level else "No Level",
                "progress": progress
            })
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get current level")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def progress(self, request: Request) -> Response:
        """Get level progress for current user."""
        try:
            # Calculate user's total points from achievements
            from api.gamification.models import UserAchievement
            from django.db.models import Sum
            
            total_points = UserAchievement.objects.filter(
                user=request.user,
                is_awarded=True
            ).aggregate(total=Sum('points_awarded'))['total'] or 0
            
            progress = LevelUpService.get_level_progress(total_points)
            serializer = LevelProgressSerializer(progress)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get level progress")
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def statistics(self, request: Request) -> Response:
        """Get level statistics for current user."""
        try:
            stats = LevelUpService.get_level_statistics(user_id=request.user.id)
            serializer = LevelStatisticsSerializer(stats)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get level statistics")
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request: Request) -> Response:
        """Get level leaderboard."""
        try:
            limit = int(request.query_params.get('limit', 10))
            
            leaderboard = LevelUpService.get_level_leaderboard(limit=limit)
            return Response(leaderboard)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get level leaderboard")
    
    @action(detail=False, methods=['get'])
    def requirements(self, request: Request) -> Response:
        """Get level requirements summary."""
        try:
            summary = LevelUpService.get_level_requirements_summary()
            serializer = LevelRequirementsSerializer(summary)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get level requirements")


# ---------------------------------------------------------------------------
# Summary ViewSet
# ---------------------------------------------------------------------------

class GamificationSummaryViewSet(viewsets.ViewSet):
    """ViewSet for comprehensive gamification summary."""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def summary(self, request: Request) -> Response:
        """Get comprehensive gamification summary for current user."""
        try:
            summary = services.get_user_gamification_summary(user_id=request.user.id)
            serializer = GamificationSummarySerializer(summary)
            return Response(serializer.data)
            
        except Exception as exc:
            return _service_error_response(exc, "Failed to get gamification summary")


def _service_error_response(exc: Exception, default_msg: str = "An error occurred.") -> Response:
    """Convert a service-layer exception to a structured DRF Response."""
    message = str(exc) if str(exc) else default_msg
    logger.warning("Gamification service error: %s: %s", type(exc).__name__, message)
    return Response(
        {"detail": message, "error_type": type(exc).__name__},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ---------------------------------------------------------------------------
# ContestCycle ViewSet
# ---------------------------------------------------------------------------

class ContestCycleViewSet(viewsets.ModelViewSet):
    """
    CRUD + lifecycle actions for ContestCycle.

    List/Retrieve: public (read-only)
    Create/Update/Delete: admin only
    activate/complete/archive: admin only
    """

    queryset = ContestCycle.objects.all().order_by("-created_at")
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = GamificationPagination
    filterset_class = ContestCycleFilter

    def get_serializer_class(self):
        if self.action == "list":
            return ContestCycleListSerializer
        return ContestCycleSerializer

    def perform_create(self, serializer):
        validated = serializer.validated_data
        try:
            cycle = services.create_contest_cycle(
                name=validated["name"],
                slug=validated["slug"],
                start_date=validated["start_date"],
                end_date=validated["end_date"],
                description=validated.get("description", ""),
                points_multiplier=validated.get("points_multiplier"),
                is_featured=validated.get("is_featured", False),
                max_participants=validated.get("max_participants"),
                metadata=validated.get("metadata", {}),
                created_by_id=self.request.user.pk,
            )
        except GamificationServiceError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})
        serializer.instance = cycle

    @action(detail=True, methods=["post"], url_path="activate", permission_classes=[permissions.IsAdminUser])
    def activate(self, request: Request, pk: Any = None) -> Response:
        """Transition a DRAFT ContestCycle to ACTIVE."""
        try:
            cycle = services.activate_contest_cycle(cycle_id=pk, actor_id=request.user.pk)
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (ContestCycleStateError, GamificationServiceError) as exc:
            return _service_error_response(exc)
        serializer = ContestCycleSerializer(cycle)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="complete", permission_classes=[permissions.IsAdminUser])
    def complete(self, request: Request, pk: Any = None) -> Response:
        """Transition an ACTIVE ContestCycle to COMPLETED and generate final snapshot."""
        try:
            cycle = services.complete_contest_cycle(cycle_id=pk, actor_id=request.user.pk)
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (ContestCycleStateError, LeaderboardGenerationError, GamificationServiceError) as exc:
            return _service_error_response(exc)
        serializer = ContestCycleSerializer(cycle)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="distribute-rewards", permission_classes=[permissions.IsAdminUser])
    def distribute_rewards(self, request: Request, pk: Any = None) -> Response:
        """Distribute rewards for a COMPLETED cycle based on the latest leaderboard snapshot."""
        try:
            result = services.distribute_cycle_rewards(cycle_id=pk)
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (ContestCycleStateError, LeaderboardGenerationError, GamificationServiceError) as exc:
            return _service_error_response(exc)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="leaderboard")
    def leaderboard(self, request: Request, pk: Any = None) -> Response:
        """Return the latest finalized leaderboard snapshot for this cycle."""
        scope = request.query_params.get("scope", LeaderboardScope.GLOBAL)
        scope_ref = request.query_params.get("scope_ref", "")

        if scope not in LeaderboardScope.values:
            return Response(
                {"detail": f"Invalid scope. Valid choices: {LeaderboardScope.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            snapshot = services.get_latest_snapshot(
                cycle_id=pk, scope=scope, scope_ref=scope_ref
            )
        except GamificationServiceError as exc:
            return _service_error_response(exc)

        if snapshot is None:
            return Response(
                {"detail": "No finalized leaderboard snapshot found for this cycle."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = LeaderboardSnapshotSerializer(snapshot)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# LeaderboardSnapshot ViewSet
# ---------------------------------------------------------------------------

class LeaderboardSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to LeaderboardSnapshot records.
    Admin users may trigger manual snapshot generation.
    """

    queryset = LeaderboardSnapshot.objects.select_related("contest_cycle").order_by("-created_at")
    serializer_class = LeaderboardSnapshotSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = GamificationPagination

    def get_queryset(self):
        qs = super().get_queryset()
        cycle_id = self.request.query_params.get("cycle_id")
        if cycle_id:
            qs = qs.filter(contest_cycle_id=cycle_id)
        scope = self.request.query_params.get("scope")
        if scope:
            if scope not in LeaderboardScope.values:
                return qs.none()
            qs = qs.filter(scope=scope)
        return qs

    def retrieve(self, request, *args, **kwargs):
        """Standard retrieve augmented with is_finalized status."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data["is_finalized"] = instance.is_finalized()
        return Response(data)

    @action(detail=False, methods=["get"], url_path="finalized")
    def finalized_only(self, request: Request) -> Response:
        """Return only finalized snapshots (is_finalized guard applied)."""
        qs = self.get_queryset().filter(is_finalized=True)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        url_path="generate",
        permission_classes=[permissions.IsAdminUser],
    )
    def generate(self, request: Request) -> Response:
        """
        Manually trigger leaderboard snapshot generation.

        Body params: cycle_id (required), scope, scope_ref, top_n.
        """
        cycle_id = request.data.get("cycle_id")
        if not cycle_id:
            return Response(
                {"detail": "cycle_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scope = request.data.get("scope", LeaderboardScope.GLOBAL)
        scope_ref = request.data.get("scope_ref", "")
        top_n = request.data.get("top_n", DEFAULT_LEADERBOARD_TOP_N)

        try:
            top_n = int(top_n)
        except (TypeError, ValueError):
            return Response(
                {"detail": "top_n must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            snapshot = services.generate_leaderboard_snapshot(
                cycle_id=cycle_id,
                scope=scope,
                scope_ref=scope_ref,
                top_n=top_n,
            )
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (LeaderboardGenerationError, GamificationServiceError) as exc:
            return _service_error_response(exc)

        serializer = LeaderboardSnapshotSerializer(snapshot)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# ContestReward ViewSet
# ---------------------------------------------------------------------------

class ContestRewardViewSet(viewsets.ModelViewSet):
    queryset = ContestReward.objects.select_related("contest_cycle").order_by("rank_from")
    serializer_class = ContestRewardSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = GamificationPagination
    filterset_class = ContestRewardFilter

    def perform_create(self, serializer):
        validated = serializer.validated_data
        try:
            reward = services.create_contest_reward(
                cycle_id=validated["contest_cycle"].pk,
                title=validated["title"],
                reward_type=validated["reward_type"],
                rank_from=validated["rank_from"],
                rank_to=validated["rank_to"],
                reward_value=validated.get("reward_value"),
                description=validated.get("description", ""),
                total_budget=validated.get("total_budget"),
                image_url=validated.get("image_url", ""),
                metadata=validated.get("metadata", {}),
            )
        except (GamificationServiceError, ContestCycleNotFoundError) as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})
        serializer.instance = reward

    @action(detail=True, methods=["get"], url_path="budget")
    def budget_status(self, request, pk=None):
        """Return budget status: remaining_budget, is_exhausted, covers given rank."""
        reward = self.get_object()
        rank = request.query_params.get("rank")
        data = {
            "remaining_budget": reward.remaining_budget(),
            "is_exhausted": reward.is_exhausted(),
        }
        if rank is not None:
            try:
                data["covers_rank"] = reward.covers_rank(int(rank))
            except (ValueError, TypeError):
                data["covers_rank"] = None
        return Response(data)


# ---------------------------------------------------------------------------
# UserAchievement ViewSet
# ---------------------------------------------------------------------------

class UserAchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only listing of UserAchievement records.
    Users see only their own achievements; admins see all.
    Achievement awarding is done via service layer / tasks.
    """

    serializer_class = UserAchievementSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = GamificationPagination
    filterset_class = UserAchievementFilter

    def get_queryset(self):
        user = self.request.user
        qs = UserAchievement.objects.with_related().awarded().order_by("-awarded_at")
        if not user.is_staff:
            qs = qs.for_user(user.pk)
        return qs

    @action(detail=True, methods=["get"], url_path="cycle-scoped")
    def cycle_scoped_check(self, request: Request, pk=None) -> Response:
        """Check whether this achievement is cycle-scoped via is_cycle_scoped()."""
        achievement = self.get_object()
        return Response({"is_cycle_scoped": achievement.is_cycle_scoped(), "achievement_id": str(achievement.pk)})

    @action(detail=False, methods=["get"], url_path="my-points")
    def my_points(self, request: Request) -> Response:
        """Return the requesting user's total awarded points, optionally per cycle."""
        cycle_id = request.query_params.get("cycle_id")
        try:
            total = services.get_user_total_points(
                user_id=request.user.pk, cycle_id=cycle_id if cycle_id else None
            )
            rank = None
            if cycle_id:
                rank = services.get_user_rank_in_cycle(
                    user_id=request.user.pk, cycle_id=cycle_id
                )
        except (UserNotFoundError, ContestCycleNotFoundError, GamificationServiceError) as exc:
            return _service_error_response(exc)

        return Response(
            {
                "user_id": str(request.user.pk),
                "cycle_id": cycle_id,
                "total_points": total,
                "rank": rank,
            }
        )


# ---------------------------------------------------------------------------
# UserPoints ViewSet
# ---------------------------------------------------------------------------

class UserPointsViewSet(viewsets.ModelViewSet):
    throttle_classes = [UserActionThrottle]
    """
    ViewSet for UserPoints model.
    Provides CRUD operations for user points management.
    """
    queryset = UserPoints.objects.all()
    serializer_class = UserPointsSerializer
    permission_classes = [IsOwnerOrAdmin]
    pagination_class = GamificationPagination
    filterset_fields = ["user", "total_points", "points_this_month", "points_this_week"]
    search_fields = ["user__username", "user__email"]
    ordering_fields = ["total_points", "lifetime_points", "points_this_month", "points_this_week", "last_updated"]

    def get_queryset(self):
        """Filter by current user if not admin."""
        user = self.request.user
        if user.is_staff:
            return UserPoints.objects.all()
        return UserPoints.objects.filter(user=user)

    @action(detail=True, methods=["post"])
    def add_points(self, request, pk=None):
        logger.info("add_points called for user_points_id=%s by user=%s", pk, getattr(request.user, 'id', '?'))
        """Add points to user's balance."""
        try:
            user_points = self.get_object()
            amount = int(request.data.get("amount", 0))
            source = request.data.get("source", "manual")
            description = request.data.get("description", "")
            
            if amount <= 0:
                return Response(
                    {"error": "Amount must be positive"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_points.add_points(amount, source, description)
            
            return Response(
                {"message": f"Added {amount} points", "new_balance": user_points.total_points},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def deduct_points(self, request, pk=None):
        logger.info("deduct_points called for user_points_id=%s by user=%s", pk, getattr(request.user, 'id', '?'))
        """Deduct points from user's balance."""
        try:
            user_points = self.get_object()
            amount = int(request.data.get("amount", 0))
            source = request.data.get("source", "manual")
            description = request.data.get("description", "")
            
            if amount <= 0:
                return Response(
                    {"error": "Amount must be positive"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_points.deduct_points(amount, source, description)
            
            return Response(
                {"message": f"Deducted {amount} points", "new_balance": user_points.total_points},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def reset_monthly(self, request, pk=None):
        """Reset monthly points to zero."""
        user_points = self.get_object()
        user_points.reset_monthly_points()
        return Response({"message": "Monthly points reset"})

    @action(detail=True, methods=["post"])
    def reset_weekly(self, request, pk=None):
        """Reset weekly points to zero."""
        user_points = self.get_object()
        user_points.reset_weekly_points()
        return Response({"message": "Weekly points reset"})


# ---------------------------------------------------------------------------
# PointsTransaction ViewSet
# ---------------------------------------------------------------------------

class PointsTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for PointsTransaction model.
    Provides read-only access to point transactions.
    """
    queryset = PointsTransaction.objects.all()
    serializer_class = PointsTransactionSerializer
    permission_classes = [IsOwnerOrAdmin]
    pagination_class = GamificationPagination
    filterset_fields = ["user", "source", "amount", "is_earning"]
    search_fields = ["user__username", "description", "source_id"]
    ordering_fields = ["created_at", "amount", "balance_after"]

    def get_queryset(self):
        """Filter by current user if not admin."""
        user = self.request.user
        if user.is_staff:
            return PointsTransaction.objects.all()
        return PointsTransaction.objects.filter(user=user)

    @action(detail=False, methods=["get"])
    def user_summary(self, request):
        """Get transaction summary for a user."""
        user_id = request.query_params.get("user_id")
        if not user_id and not request.user.is_staff:
            user_id = request.user.pk
        
        try:
            transactions = PointsTransaction.objects.filter(user_id=user_id)
            total_earned = transactions.filter(amount__gt=0).aggregate(total=models.Sum("amount"))["total"] or 0
            total_deducted = abs(transactions.filter(amount__lt=0).aggregate(total=models.Sum("amount"))["total"] or 0)
            
            return Response({
                "user_id": user_id,
                "total_earned": total_earned,
                "total_deducted": total_deducted,
                "transaction_count": transactions.count()
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# StreakFreeze ViewSet
# ---------------------------------------------------------------------------

class StreakFreezeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for StreakFreeze model.
    Provides CRUD operations for streak freeze management.
    """
    queryset = StreakFreeze.objects.all()
    serializer_class = StreakFreezeSerializer
    permission_classes = [IsOwnerOrAdmin]
    pagination_class = GamificationPagination
    filterset_fields = ["user", "streak", "used_at"]
    search_fields = ["user__username", "reason"]
    ordering_fields = ["used_at", "created_at"]

    def get_queryset(self):
        """Filter by current user if not admin."""
        user = self.request.user
        if user.is_staff:
            return StreakFreeze.objects.all()
        return StreakFreeze.objects.filter(user=user)

    @action(detail=False, methods=["post"])
    def use_freeze(self, request):
        """Use a streak freeze for a specific date."""
        try:
            user = request.user
            streak_id = request.data.get("streak_id")
            used_at = request.data.get("used_at")
            reason = request.data.get("reason", "")
            
            if not streak_id or not used_at:
                return Response(
                    {"error": "streak_id and used_at are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            streak = Streak.objects.get(id=streak_id, user=user)
            freeze = StreakFreeze.objects.create(
                user=user,
                streak=streak,
                used_at=used_at,
                reason=reason
            )
            
            return Response(
                StreakFreezeSerializer(freeze).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# ContestParticipant ViewSet
# ---------------------------------------------------------------------------

class ContestParticipantViewSet(viewsets.ModelViewSet):
    throttle_classes = [GamificationRateThrottle]
    """
    ViewSet for ContestParticipant model.
    Provides CRUD operations for contest participation.
    """
    queryset = ContestParticipant.objects.all()
    serializer_class = ContestParticipantSerializer
    permission_classes = [IsOwnerOrAdmin]
    pagination_class = GamificationPagination
    filterset_fields = ["user", "contest_cycle", "is_disqualified"]
    search_fields = ["user__username", "contest_cycle__name"]
    ordering_fields = ["joined_at", "current_points", "current_rank"]

    def get_queryset(self):
        """Filter by current user if not admin."""
        user = self.request.user
        if user.is_staff:
            return ContestParticipant.objects.all()
        return ContestParticipant.objects.filter(user=user)

    @action(detail=True, methods=["post"])
    def add_points(self, request, pk=None):
        """Add points to participant's contest score."""
        try:
            participant = self.get_object()
            amount = int(request.data.get("amount", 0))
            
            if amount <= 0:
                return Response(
                    {"error": "Amount must be positive"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            participant.add_points(amount)
            
            return Response(
                {"message": f"Added {amount} points", "new_points": participant.current_points},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="rank-status")
    def rank_status(self, request, pk=None):
        """Return is_ranked() and days_in_contest() for this participant."""
        participant = self.get_object()
        return Response({
            "is_ranked": participant.is_ranked(),
            "days_in_contest": participant.days_in_contest(),
            "current_rank": participant.current_rank,
        })

    @action(detail=True, methods=["post"])
    def disqualify(self, request, pk=None):
        """Disqualify participant from contest."""
        participant = self.get_object()
        participant.disqualify()
        logger.info("disqualify: participant=%s by user=%s", pk, getattr(request.user, "id", "?"))
        return Response({"message": "Participant disqualified"})

    @action(detail=True, methods=["post"])
    def update_rank(self, request, pk=None):
        """Update participant's rank."""
        try:
            participant = self.get_object()
            new_rank = int(request.data.get("rank", 0))
            
            if new_rank <= 0:
                return Response(
                    {"error": "Rank must be positive"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            participant.update_rank(new_rank)
            
            return Response(
                {"message": f"Rank updated to {new_rank}"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# GamificationConfig ViewSet
# ---------------------------------------------------------------------------

class GamificationConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for GamificationConfig model.
    Provides CRUD operations for gamification configuration.
    """
    queryset = GamificationConfig.objects.all()
    serializer_class = GamificationConfigSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = GamificationPagination
    filterset_fields = ["tenant", "enable_contests", "enable_badges", "enable_streaks", "enable_levels"]
    search_fields = ["tenant__name"]
    ordering_fields = ["created_at", "updated_at"]

    @action(detail=True, methods=["get"], url_path="features")
    def get_features(self, request, pk=None):
        """Return enabled feature list via features_enabled() and is_points_expiry_enabled()."""
        config = self.get_object()
        return Response({
            "enabled_features": config.features_enabled(),
            "is_points_expiry_enabled": config.is_points_expiry_enabled(),
        })

    @action(detail=True, methods=["post"])
    def enable_all_features(self, request, pk=None):
        """Enable all gamification features."""
        config = self.get_object()
        config.enable_contests = True
        config.enable_badges = True
        config.enable_streaks = True
        config.enable_levels = True
        config.enable_daily_challenges = True
        config.save()
        logger.info("enable_all_features pk=%s by user=%s", pk, getattr(request.user, "id", "?"))
        return Response({"message": "All features enabled", "enabled_features": config.features_enabled()})

    @action(detail=True, methods=["post"])
    def disable_all_features(self, request, pk=None):
        """Disable all gamification features."""
        config = self.get_object()
        config.enable_contests = False
        config.enable_badges = False
        config.enable_streaks = False
        config.enable_levels = False
        config.enable_daily_challenges = False
        config.save()
        logger.info("disable_all_features pk=%s by user=%s", pk, getattr(request.user, "id", "?"))
        return Response({"message": "All features disabled", "enabled_features": config.features_enabled()})

    @action(detail=True, methods=["post"])
    def reset_to_defaults(self, request, pk=None):
        """Reset configuration to defaults."""
        config = self.get_object()
        config.enable_contests = True
        config.enable_badges = True
        config.enable_streaks = True
        config.enable_levels = True
        config.enable_daily_challenges = True
        config.points_expiry_days = None
        config.leaderboard_refresh_interval = 300
        config.save()
        logger.info("reset_to_defaults pk=%s by user=%s", pk, getattr(request.user, "id", "?"))
        return Response({"message": "Configuration reset to defaults", "enabled_features": config.features_enabled()})


# ---------------------------------------------------------------------------
# GamificationInsight ViewSet
# ---------------------------------------------------------------------------

class GamificationInsightViewSet(viewsets.ModelViewSet):
    """
    ViewSet for GamificationInsight model.
    Provides CRUD operations for gamification insights.
    """
    queryset = GamificationInsight.objects.all()
    serializer_class = GamificationInsightSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = GamificationPagination
    filterset_fields = ["date"]
    search_fields = []
    ordering_fields = ["date", "active_users", "total_points_issued"]

    @action(detail=False, methods=["post"])
    def calculate_today(self, request):
        """Calculate insights for today."""
        try:
            insight = GamificationInsight.calculate_daily_metrics()
            return Response(
                GamificationInsightSerializer(insight).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        """Recalculate insights for a specific date."""
        try:
            insight = self.get_object()
            recalculated = GamificationInsight.calculate_daily_metrics(insight.date)
            return Response(
                GamificationInsightSerializer(recalculated).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def summary_report(self, request):
        """Get summary report for a date range."""
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        
        if not start_date or not end_date:
            return Response(
                {"error": "start_date and end_date are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            insights = GamificationInsight.objects.filter(
                date__range=[start_date, end_date]
            ).order_by("date")
            
            summary = {
                "period": f"{start_date} to {end_date}",
                "total_active_users": sum(i.active_users for i in insights),
                "total_badges_awarded": sum(i.badges_awarded for i in insights),
                "total_challenges_completed": sum(i.challenges_completed for i in insights),
                "total_points_issued": sum(i.total_points_issued for i in insights),
                "average_engagement_rate": sum(i.engagement_rate for i in insights) / len(insights) if insights else 0,
                "daily_data": GamificationInsightSerializer(insights, many=True).data
            }
            
            return Response(summary)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Sanction ViewSet
# ---------------------------------------------------------------------------

class SanctionViewSet(viewsets.ViewSet):
    throttle_classes = [GamificationRateThrottle]
    """
    ViewSet for gamification sanctions management.
    Provides operations for applying, viewing, and resolving sanctions.
    """
    permission_classes = [IsAdminOrReadOnly]
    
    def list(self, request: Request) -> Response:
        """List all sanctions (admin only) or user's sanctions."""
        try:
            from api.gamification.services.SanctionService import SanctionService
            sanction_service = SanctionService()
            
            # Non-admin users can only see their own sanctions
            if not request.user.is_staff:
                user_sanctions = sanction_service.get_sanction_history(request.user)
                return Response({
                    "count": len(user_sanctions),
                    "results": user_sanctions
                })
            
            # Admin users can see all sanctions with filtering
            user_id = request.query_params.get('user_id')
            sanction_type = request.query_params.get('sanction_type')
            is_resolved = request.query_params.get('is_resolved')
            
            from api.gamification.sanctions import Sanction
            queryset = Sanction.objects.select_related('user', 'violation').order_by('-created_at')
            
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if sanction_type:
                queryset = queryset.filter(sanction_type=sanction_type)
            if is_resolved is not None:
                queryset = queryset.filter(is_resolved=is_resolved.lower() == 'true')
            
            # Serialize results
            sanctions_data = []
            for sanction in queryset:
                sanctions_data.append({
                    'id': str(sanction.id),
                    'user_id': str(sanction.user.id),
                    'username': getattr(sanction.user, 'username', str(sanction.user.id)),
                    'sanction_type': sanction.sanction_type,
                    'violation_type': sanction.violation.violation_type.value if sanction.violation else None,
                    'severity': sanction.violation.severity.value if sanction.violation else None,
                    'reason': sanction.violation.reason if sanction.violation else "",
                    'is_resolved': sanction.is_resolved,
                    'created_at': sanction.created_at.isoformat(),
                    'expires_at': sanction.expires_at.isoformat() if sanction.expires_at else None,
                    'resolved_at': sanction.resolved_at.isoformat() if sanction.resolved_at else None,
                    'sanction_data': sanction.sanction_data,
                })
            
            return Response({
                "count": len(sanctions_data),
                "results": sanctions_data
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=["post"])
    def apply(self, request: Request) -> Response:
        logger.info("sanction apply called by user=%s data=%r", getattr(request.user, 'id', '?'), request.data)
        """Apply a sanction to a user (admin only)."""
        if not request.user.is_staff:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from api.gamification.services.SanctionService import SanctionService
            sanction_service = SanctionService()
            
            user_id = request.data.get('user_id')
            violation_type = request.data.get('violation_type')
            severity = request.data.get('severity', 'medium')
            reason = request.data.get('reason', '')
            evidence = request.data.get('evidence', {})
            
            if not user_id or not violation_type:
                return Response(
                    {"error": "user_id and violation_type are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            sanction = sanction_service.apply_sanction(
                user=user_id,
                violation_type=violation_type,
                severity=severity,
                reason=reason,
                evidence=evidence,
                applied_by=request.user
            )
            
            return Response({
                "sanction_id": str(sanction.id),
                "user_id": str(sanction.user.id),
                "sanction_type": sanction.sanction_type,
                "violation_type": sanction.violation.violation_type.value,
                "severity": sanction.violation.severity.value,
                "reason": sanction.violation.reason,
                "created_at": sanction.created_at.isoformat(),
                "expires_at": sanction.expires_at.isoformat() if sanction.expires_at else None,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=["post"])
    def resolve(self, request: Request, pk: str = None) -> Response:
        """Resolve a sanction (admin only)."""
        if not request.user.is_staff:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from api.gamification.services.SanctionService import SanctionService
            sanction_service = SanctionService()
            
            resolution_notes = request.data.get('resolution_notes', '')
            
            success = sanction_service.resolve_sanction(
                sanction_id=pk,
                resolved_by=request.user,
                resolution_notes=resolution_notes
            )
            
            if success:
                return Response({"message": "Sanction resolved successfully"})
            else:
                return Response({"error": "Failed to resolve sanction"}, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=["get"])
    def active(self, request: Request) -> Response:
        """Get active sanctions for a user."""
        try:
            from api.gamification.services.SanctionService import SanctionService
            sanction_service = SanctionService()
            
            user_id = request.query_params.get('user_id')
            if not user_id:
                if request.user.is_authenticated:
                    user_id = request.user.id
                else:
                    return Response({"error": "user_id required or authentication required"}, 
                                   status=status.HTTP_400_BAD_REQUEST)
            
            active_sanctions = sanction_service.get_active_sanctions(user_id)
            
            sanctions_data = []
            for sanction in active_sanctions:
                sanctions_data.append({
                    'id': str(sanction.id),
                    'sanction_type': sanction.sanction_type,
                    'violation_type': sanction.violation.violation_type.value if sanction.violation else None,
                    'severity': sanction.violation.severity.value if sanction.violation else None,
                    'reason': sanction.violation.reason if sanction.violation else "",
                    'created_at': sanction.created_at.isoformat(),
                    'expires_at': sanction.expires_at.isoformat() if sanction.expires_at else None,
                    'sanction_data': sanction.sanction_data,
                })
            
            return Response({
                "count": len(sanctions_data),
                "results": sanctions_data
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=["get"])
    def statistics(self, request: Request) -> Response:
        """Get sanction statistics (admin only)."""
        if not request.user.is_staff:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from api.gamification.services.SanctionService import SanctionService
            sanction_service = SanctionService()
            
            from datetime import datetime
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            stats = sanction_service.get_sanction_statistics(start_date, end_date)
            return Response(stats)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=["post"])
    def cleanup(self, request: Request) -> Response:
        """Clean up expired sanctions (admin only)."""
        if not request.user.is_staff:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from api.gamification.services.SanctionService import SanctionService
            sanction_service = SanctionService()
            
            cleanup_count = sanction_service.cleanup_expired_sanctions()
            
            return Response({
                "message": f"Cleaned up {cleanup_count} expired sanctions",
                "cleaned_count": cleanup_count
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
