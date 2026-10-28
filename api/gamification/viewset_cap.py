"""
Gamification Capital ViewSets — Uppercase Django REST Framework ViewSets.

This module provides ViewSets with capital letter naming convention for
consistency with the existing codebase patterns.
"""

from __future__ import annotations
from typing import Type

import logging
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.gamification.exceptions import GamificationServiceError
from api.gamification.models import (
    ContestCycle, ContestReward, UserAchievement, LeaderboardSnapshot,
    Badge, UserBadge, DailyChallenge, UserDailyChallenge, Streak, StreakReward, LevelConfig
)
from api.gamification.permissions import IsOwnerOrAdmin, IsAdminOrReadOnly
from api.gamification.serializers import (
    ContestCycleSerializer, ContestRewardSerializer, UserAchievementSerializer,
    LeaderboardSnapshotSerializer, BadgeSerializer, UserBadgeSerializer,
    DailyChallengeSerializer, UserDailyChallengeSerializer, StreakSerializer,
    StreakRewardSerializer, LevelConfigSerializer
)
from api.gamification.services import (
    ContestCycleService, RewardService, AchievementService, LeaderboardService,
    BadgeService, ChallengeService, StreakService, LevelService
)

User = get_user_model()
logger = logging.getLogger(__name__)


class CONTESTCYCLEVIEWSET(viewsets.ModelViewSet):
    """ViewSet for ContestCycle model with capital naming."""
    
    queryset = ContestCycle.objects.all()
    serializer_class = ContestCycleSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return ContestCycleSerializer
        elif self.action in ['update', 'partial_update']:
            return ContestCycleSerializer
        return ContestCycleSerializer
    
    @action(detail=True, methods=['post'])
    def ACTIVATE(self, request, pk=None):
        """Activate a contest cycle."""
        try:
            cycle = self.get_object()
            service = ContestCycleService()
            activated_cycle = service.activate_cycle(cycle.id, request.user.id)
            
            serializer = self.get_serializer(activated_cycle)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def COMPLETE(self, request, pk=None):
        """Complete a contest cycle."""
        try:
            cycle = self.get_object()
            service = ContestCycleService()
            completed_cycle = service.complete_cycle(cycle.id, request.user.id)
            
            serializer = self.get_serializer(completed_cycle)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def LEADERBOARD(self, request, pk=None):
        """Get leaderboard for this contest cycle."""
        try:
            cycle = self.get_object()
            service = LeaderboardService()
            leaderboard = service.get_leaderboard_for_cycle(cycle.id)
            
            return Response(leaderboard)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def GENERATE_LEADERBOARD(self, request, pk=None):
        """Generate leaderboard snapshot for this contest cycle."""
        try:
            cycle = self.get_object()
            service = LeaderboardService()
            snapshot = service.generate_snapshot(cycle.id, request.user.id)
            
            serializer = LeaderboardSnapshotSerializer(snapshot)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CONTESTREWARDVIEWSET(viewsets.ModelViewSet):
    """ViewSet for ContestReward model with capital naming."""
    
    queryset = ContestReward.objects.all()
    serializer_class = ContestRewardSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_queryset(self):
        """Filter rewards by contest cycle if provided."""
        queryset = super().get_queryset()
        cycle_id = self.request.query_params.get('contest_cycle_id')
        if cycle_id:
            queryset = queryset.filter(contest_cycle_id=cycle_id)
        return queryset
    
    @action(detail=True, methods=['post'])
    def CLAIM(self, request, pk=None):
        """Claim a reward for the current user."""
        try:
            reward = self.get_object()
            service = RewardService()
            
            # Check if user is eligible for this reward
            user_achievement = service.check_user_eligibility(request.user.id, reward)
            
            if not user_achievement:
                return Response(
                    {'error': 'User not eligible for this reward'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Claim the reward
            claimed_reward = service.claim_reward(user_achievement.id, reward.id, request.user.id)
            
            serializer = UserAchievementSerializer(claimed_reward)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class USERACHIEVEMENTVIEWSET(viewsets.ModelViewSet):
    """ViewSet for UserAchievement model with capital naming."""
    
    queryset = UserAchievement.objects.all()
    serializer_class = UserAchievementSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter achievements by user if not admin."""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        
        # Filter by contest cycle if provided
        cycle_id = self.request.query_params.get('contest_cycle_id')
        if cycle_id:
            queryset = queryset.filter(contest_cycle_id=cycle_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def NOTIFY(self, request, pk=None):
        """Send notification for this achievement."""
        try:
            achievement = self.get_object()
            service = AchievementService()
            
            # Check if user can notify this achievement
            if achievement.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service.send_notification(achievement.id, request.user.id)
            
            return Response({'status': 'notification sent'})
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def MY_ACHIEVEMENTS(self, request):
        """Get current user's achievements."""
        achievements = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(achievements, many=True)
        return Response(serializer.data)


class LEADERBOARDSNAPSHOTVIEWSET(viewsets.ModelViewSet):
    """ViewSet for LeaderboardSnapshot model with capital naming."""
    
    queryset = LeaderboardSnapshot.objects.all()
    serializer_class = LeaderboardSnapshotSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_queryset(self):
        """Filter snapshots by contest cycle if provided."""
        queryset = super().get_queryset()
        cycle_id = self.request.query_params.get('contest_cycle_id')
        if cycle_id:
            queryset = queryset.filter(contest_cycle_id=cycle_id)
        return queryset
    
    @action(detail=True, methods=['get'])
    def EXPORT(self, request, pk=None):
        """Export leaderboard snapshot data."""
        try:
            snapshot = self.get_object()
            service = LeaderboardService()
            
            export_format = request.query_params.get('format', 'csv')
            export_data = service.export_snapshot(snapshot.id, export_format)
            
            return Response(export_data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BADGEVIEWSET(viewsets.ModelViewSet):
    """ViewSet for Badge model with capital naming."""
    
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    @action(detail=True, methods=['post'])
    def AWARD_TO_USER(self, request, pk=None):
        """Award this badge to a user."""
        try:
            badge = self.get_object()
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response(
                    {'error': 'user_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = BadgeService()
            user_badge = service.award_badge(user_id, badge.id, request.user.id)
            
            serializer = UserBadgeSerializer(user_badge)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def AVAILABLE(self, request):
        """Get badges available for the current user."""
        try:
            service = BadgeService()
            available_badges = service.get_available_badges(request.user.id)
            
            serializer = BadgeSerializer(available_badges, many=True)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class USERBADGEVIEWSET(viewsets.ModelViewSet):
    """ViewSet for UserBadge model with capital naming."""
    
    queryset = UserBadge.objects.all()
    serializer_class = UserBadgeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter badges by user if not admin."""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset
    
    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def PIN(self, request, pk=None):
        """Pin this badge to user's profile."""
        try:
            user_badge = self.get_object()
            
            # Check if user can pin this badge
            if user_badge.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = BadgeService()
            service.pin_badge(user_badge.id, request.user.id)
            
            serializer = self.get_serializer(user_badge)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def UNPIN(self, request, pk=None):
        """Unpin this badge from user's profile."""
        try:
            user_badge = self.get_object()
            
            # Check if user can unpin this badge
            if user_badge.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = BadgeService()
            service.unpin_badge(user_badge.id, request.user.id)
            
            serializer = self.get_serializer(user_badge)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class DAILYCHALLENGEVIEWSET(viewsets.ModelViewSet):
    """ViewSet for DailyChallenge model with capital naming."""
    
    queryset = DailyChallenge.objects.all()
    serializer_class = DailyChallengeSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    @action(detail=False, methods=['get'])
    def TODAY(self, request):
        """Get today's challenge."""
        try:
            service = ChallengeService()
            today_challenge = service.get_today_challenge()
            
            if today_challenge:
                serializer = self.get_serializer(today_challenge)
                return Response(serializer.data)
            else:
                return Response({'message': 'No challenge available today'})
                
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class USERDAILYCHALLENGEVIEWSET(viewsets.ModelViewSet):
    """ViewSet for UserDailyChallenge model with capital naming."""
    
    queryset = UserDailyChallenge.objects.all()
    serializer_class = UserDailyChallengeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter challenges by user if not admin."""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset
    
    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def COMPLETE(self, request, pk=None):
        """Complete this daily challenge."""
        try:
            user_challenge = self.get_object()
            
            # Check if user can complete this challenge
            if user_challenge.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = ChallengeService()
            completed_challenge = service.complete_challenge(
                user_challenge.id, request.user.id
            )
            
            serializer = self.get_serializer(completed_challenge)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class STREAKVIEWSET(viewsets.ModelViewSet):
    """ViewSet for Streak model with capital naming."""
    
    queryset = Streak.objects.all()
    serializer_class = StreakSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter streaks by user if not admin."""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset
    
    def perform_create(self, serializer):
        """Set user on creation."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def RESET(self, request, pk=None):
        """Reset this streak."""
        try:
            streak = self.get_object()
            
            # Check if user can reset this streak
            if streak.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = StreakService()
            reset_streak = service.reset_streak(streak.id, request.user.id)
            
            serializer = self.get_serializer(reset_streak)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def MY_STREAK(self, request):
        """Get current user's streak."""
        try:
            service = StreakService()
            user_streak = service.get_user_streak(request.user.id)
            
            if user_streak:
                serializer = self.get_serializer(user_streak)
                return Response(serializer.data)
            else:
                return Response({'message': 'No active streak'})
                
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class STREAKREWARDVIEWSET(viewsets.ModelViewSet):
    """ViewSet for StreakReward model with capital naming."""
    
    queryset = StreakReward.objects.all()
    serializer_class = StreakRewardSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    @action(detail=True, methods=['post'])
    def CLAIM(self, request, pk=None):
        """Claim this streak reward for the current user."""
        try:
            reward = self.get_object()
            service = StreakService()
            
            claimed_reward = service.claim_streak_reward(
                request.user.id, reward.id, request.user.id
            )
            
            serializer = UserBadgeSerializer(claimed_reward)
            return Response(serializer.data)
            
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LEVELCONFIGVIEWSET(viewsets.ModelViewSet):
    """ViewSet for LevelConfig model with capital naming."""
    
    queryset = LevelConfig.objects.all()
    serializer_class = LevelConfigSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    @action(detail=False, methods=['get'])
    def USER_LEVEL(self, request):
        """Get current user's level."""
        try:
            service = LevelService()
            user_level = service.get_user_level(request.user.id)
            
            if user_level:
                serializer = LevelConfigSerializer(user_level)
                return Response(serializer.data)
            else:
                return Response({'message': 'No level found'})
                
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def NEXT_LEVEL(self, request):
        """Get next level for the current user."""
        try:
            service = LevelService()
            next_level = service.get_next_level(request.user.id)
            
            if next_level:
                serializer = LevelConfigSerializer(next_level)
                return Response(serializer.data)
            else:
                return Response({'message': 'Already at max level'})
                
        except GamificationServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ---------------------------------------------------------------------------
# Capital ViewSet Registry
# ---------------------------------------------------------------------------

CAPITAL_VIEWSET_REGISTRY = {
    'contest_cycle': CONTESTCYCLEVIEWSET,
    'contest_reward': CONTESTREWARDVIEWSET,
    'user_achievement': USERACHIEVEMENTVIEWSET,
    'leaderboard_snapshot': LEADERBOARDSNAPSHOTVIEWSET,
    'badge': BADGEVIEWSET,
    'user_badge': USERBADGEVIEWSET,
    'daily_challenge': DAILYCHALLENGEVIEWSET,
    'user_daily_challenge': USERDAILYCHALLENGEVIEWSET,
    'streak': STREAKVIEWSET,
    'streak_reward': STREAKREWARDVIEWSET,
    'level_config': LEVELCONFIGVIEWSET,
}


def get_capital_viewset(viewset_name: str) -> Optional[Type]:
    """Get a capital ViewSet by name."""
    return CAPITAL_VIEWSET_REGISTRY.get(viewset_name)


def list_capital_viewsets() -> List[str]:
    """List all capital ViewSet names."""
    return list(CAPITAL_VIEWSET_REGISTRY.keys())


def register_capital_viewset(name: str, viewset_class: Type) -> None:
    """Register a capital ViewSet."""
    CAPITAL_VIEWSET_REGISTRY[name] = viewset_class
    logger.info(f"Registered capital ViewSet: {name}")


# Initialize logging
logger.info("Gamification capital ViewSets module initialized")
