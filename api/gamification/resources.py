"""
Gamification Resources — API resource definitions for gamification data.

This module provides resource classes for handling gamification API resources
with proper serialization, validation, and response formatting.
"""

from __future__ import annotations
from django.db.models import Sum

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, LeaderboardSnapshot,
    UserAchievement
)
from api.gamification.services import (
    BadgeService, DailyChallengeService, StreakService, LevelUpService
)
from api.gamification.serializers import (
    BadgeSerializer, UserBadgeSerializer, DailyChallengeSerializer,
    UserDailyChallengeSerializer, StreakSerializer, LevelConfigSerializer,
    UserAchievementSerializer, LeaderboardSnapshotSerializer
)
from api.gamification.pagination import (
    GamificationPagination, BadgePagination, LeaderboardPagination,
    ChallengePagination, AchievementPagination
)
from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseGamificationResource(APIView):
    """Base class for gamification API resources."""
    
    permission_classes = [IsAuthenticated]
    pagination_class = GamificationPagination
    
    def handle_error(self, error: Exception) -> Response:
        """Handle errors consistently."""
        if isinstance(error, GamificationServiceError):
            return Response({
                'error': str(error),
                'error_type': 'GamificationServiceError',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(error, ValidationError):
            return Response({
                'error': str(error),
                'error_type': 'ValidationError',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        else:
            logger.error(f"Unexpected error in gamification resource: {error}")
            return Response({
                'error': 'An unexpected error occurred',
                'error_type': 'InternalError',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_user_id(self, request: Request) -> str:
        """Get user ID from request."""
        return str(request.user.id)


class BadgeResource(BaseGamificationResource):
    """Resource for badge-related operations."""
    
    pagination_class = BadgePagination
    
    def get(self, request: Request) -> Response:
        """Get available badges."""
        try:
            # Get query parameters
            is_active = request.query_params.get('is_active', 'true').lower() == 'true'
            rarity = request.query_params.get('rarity')
            criteria_type = request.query_params.get('criteria_type')
            
            # Get badges
            badges = BadgeService.get_available_badges(
                is_active=is_active,
                rarity=rarity,
                criteria_type=criteria_type
            )
            
            # Paginate results
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(badges, request)
            
            if page is not None:
                serializer = BadgeSerializer(page, many=True)
                
                # Add badge statistics
                paginator.badge_stats = {
                    'total_badges': len(badges),
                    'active_badges': len([b for b in badges if b.is_active]),
                    'rarity_distribution': self._get_rarity_distribution(badges)
                }
                
                return paginator.get_paginated_response(serializer.data)
            
            # Return unpaginated response
            serializer = BadgeSerializer(badges, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'count': len(badges),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    def _get_rarity_distribution(self, badges: List[Badge]) -> Dict[str, int]:
        """Get rarity distribution statistics."""
        distribution = {}
        for badge in badges:
            rarity = badge.rarity or 'unknown'
            distribution[rarity] = distribution.get(rarity, 0) + 1
        return distribution


class UserBadgeResource(BaseGamificationResource):
    """Resource for user badge operations."""
    
    pagination_class = BadgePagination
    
    def get(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Get user's badges."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Get query parameters
            is_pinned = request.query_params.get('is_pinned')
            if is_pinned is not None:
                is_pinned = is_pinned.lower() == 'true'
            
            rarity = request.query_params.get('rarity')
            
            # Get user badges
            user_badges = BadgeService.get_user_badges(
                user_id=target_user_id,
                is_pinned=is_pinned,
                rarity=rarity
            )
            
            # Paginate results
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(user_badges, request)
            
            if page is not None:
                serializer = UserBadgeSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            # Return unpaginated response
            serializer = UserBadgeSerializer(user_badges, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'count': len(user_badges),
                'user_id': target_user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    def post(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Award badges to user."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Parse request data
            user_points = request.data.get('user_points', 0)
            streak_days = request.data.get('streak_days', 0)
            achievement_count = request.data.get('achievement_count', 0)
            contest_wins = request.data.get('contest_wins', 0)
            referral_count = request.data.get('referral_count', 0)
            metadata = request.data.get('metadata', {})
            
            # Award badges
            awarded_badges = BadgeService.award_eligible_badges(
                user_id=target_user_id,
                user_points=user_points,
                streak_days=streak_days,
                achievement_count=achievement_count,
                contest_wins=contest_wins,
                referral_count=referral_count,
                metadata=metadata
            )
            
            serializer = UserBadgeSerializer(awarded_badges, many=True)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'count': len(awarded_badges),
                'user_id': target_user_id,
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return self.handle_error(e)


class StreakResource(BaseGamificationResource):
    """Resource for streak operations."""
    
    def get(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Get user's streak."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Get or create user streak
            streak = StreakService.get_or_create_user_streak(user_id=target_user_id)
            
            serializer = StreakSerializer(streak)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'user_id': target_user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    def post(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Update user's streak activity."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Parse request data
            activity_date = request.data.get('activity_date')
            if activity_date:
                activity_date = datetime.fromisoformat(activity_date).date()
            
            metadata = request.data.get('metadata', {})
            
            # Update activity
            streak, was_extended, days_added = StreakService.update_user_activity(
                user_id=target_user_id,
                activity_date=activity_date,
                metadata=metadata
            )
            
            serializer = StreakSerializer(streak)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'user_id': target_user_id,
                'was_extended': was_extended,
                'days_added': days_added,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)


class ChallengeResource(BaseGamificationResource):
    """Resource for daily challenge operations."""
    
    pagination_class = ChallengePagination
    
    def get(self, request: Request) -> Response:
        """Get active daily challenges."""
        try:
            # Get query parameters
            challenge_date = request.query_params.get('date')
            if challenge_date:
                challenge_date = datetime.fromisoformat(challenge_date).date()
            
            target_action = request.query_params.get('target_action')
            
            # Get challenges
            challenges = DailyChallengeService.get_active_challenges(
                challenge_date=challenge_date,
                target_action=target_action
            )
            
            # Paginate results
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(challenges, request)
            
            if page is not None:
                serializer = DailyChallengeSerializer(page, many=True)
                
                # Add challenge statistics
                paginator.challenge_stats = {
                    'total_challenges': len(challenges),
                    'active_challenges': len([c for c in challenges if c.is_active]),
                    'action_distribution': self._get_action_distribution(challenges)
                }
                
                return paginator.get_paginated_response(serializer.data)
            
            # Return unpaginated response
            serializer = DailyChallengeSerializer(challenges, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'count': len(challenges),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    def _get_action_distribution(self, challenges: List[DailyChallenge]) -> Dict[str, int]:
        """Get action type distribution statistics."""
        distribution = {}
        for challenge in challenges:
            action = challenge.target_action or 'unknown'
            distribution[action] = distribution.get(action, 0) + 1
        return distribution


class UserChallengeResource(BaseGamificationResource):
    """Resource for user challenge operations."""
    
    pagination_class = ChallengePagination
    
    def get(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Get user's challenge progress."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Get query parameters
            challenge_id = request.query_params.get('challenge_id')
            challenge_date = request.query_params.get('date')
            if challenge_date:
                challenge_date = datetime.fromisoformat(challenge_date).date()
            
            # Get progress
            user_challenges = DailyChallengeService.get_user_challenge_progress(
                user_id=target_user_id,
                challenge_id=challenge_id,
                challenge_date=challenge_date
            )
            
            # Paginate results
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(user_challenges, request)
            
            if page is not None:
                serializer = UserDailyChallengeSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            # Return unpaginated response
            serializer = UserDailyChallengeSerializer(user_challenges, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'count': len(user_challenges),
                'user_id': target_user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    def post(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Start or update challenge progress."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            action = request.data.get('action')  # 'start' or 'update'
            challenge_id = request.data.get('challenge_id')
            
            if not challenge_id:
                return Response({
                    'error': 'challenge_id is required',
                    'error_type': 'ValidationError'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if action == 'start':
                # Start challenge
                user_challenge = DailyChallengeService.start_user_challenge(
                    user_id=target_user_id,
                    challenge_id=challenge_id
                )
                serializer = UserDailyChallengeSerializer(user_challenge)
                
                return Response({
                    'success': True,
                    'data': serializer.data,
                    'user_id': target_user_id,
                    'timestamp': timezone.now().isoformat()
                }, status=status.HTTP_201_CREATED)
                
            elif action == 'update':
                # Update progress
                increment_amount = request.data.get('increment_amount', 1)
                action_metadata = request.data.get('action_metadata', {})
                
                user_challenge, completed = DailyChallengeService.update_challenge_progress(
                    user_id=target_user_id,
                    challenge_id=challenge_id,
                    increment_amount=increment_amount,
                    action_metadata=action_metadata
                )
                
                serializer = UserDailyChallengeSerializer(user_challenge)
                
                return Response({
                    'success': True,
                    'data': serializer.data,
                    'completed': completed,
                    'user_id': target_user_id,
                    'timestamp': timezone.now().isoformat()
                })
            else:
                return Response({
                    'error': 'Invalid action. Must be "start" or "update"',
                    'error_type': 'ValidationError'
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return self.handle_error(e)


class LevelResource(BaseGamificationResource):
    """Resource for level operations."""
    
    def get(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Get user's level information."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Get user's total points from achievements
            from django.db.models import Sum
            
            total_points = UserAchievement.objects.filter(
                user_id=target_user_id,
                is_awarded=True
            ).aggregate(total=Sum('points_awarded'))['total'] or 0
            
            # Get current level and progress
            current_level = LevelUpService.get_user_level(total_points)
            progress = LevelUpService.get_level_progress(total_points)
            
            response_data = {
                'success': True,
                'data': {
                    'total_points': total_points,
                    'current_level': current_level.level_number if current_level else 0,
                    'current_level_title': current_level.title if current_level else "No Level",
                    'current_level_description': current_level.description if current_level else "",
                    'points_to_next_level': progress.get('points_to_next_level', 0),
                    'progress_percentage': progress.get('progress_percentage', 0),
                    'points_multiplier': current_level.points_multiplier if current_level else 1.0,
                    'perks': current_level.perks if current_level else {}
                },
                'user_id': target_user_id,
                'timestamp': timezone.now().isoformat()
            }
            
            return Response(response_data)
            
        except Exception as e:
            return self.handle_error(e)


class LeaderboardResource(BaseGamificationResource):
    """Resource for leaderboard operations."""
    
    pagination_class = LeaderboardPagination
    
    def get(self, request: Request) -> Response:
        """Get leaderboard data."""
        try:
            # Get query parameters
            contest_id = request.query_params.get('contest_id')
            scope = request.query_params.get('scope', 'ALL_USERS')
            limit = int(request.query_params.get('limit', 100))
            
            # Get leaderboard data
            if contest_id:
                # Contest-specific leaderboard
                try:
                    contest = ContestCycle.objects.get(id=contest_id)
                    snapshot = LeaderboardSnapshot.objects.filter(
                        contest_cycle=contest,
                        status='FINALIZED'
                    ).order_by('-created_at').first()
                    
                    if not snapshot:
                        return Response({
                            'error': 'No finalized leaderboard found for this contest',
                            'error_type': 'NotFoundError'
                        }, status=status.HTTP_404_NOT_FOUND)
                    
                    leaderboard_data = snapshot.snapshot_data or []
                    
                except ContestCycle.DoesNotExist:
                    return Response({
                        'error': 'Contest not found',
                        'error_type': 'NotFoundError'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Global leaderboard (all-time)
                leaderboard_data = self._get_global_leaderboard(limit)
            
            # Paginate results
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(leaderboard_data, request)
            
            if page is not None:
                return paginator.get_paginated_response(page)
            
            # Return unpaginated response
            return Response({
                'success': True,
                'data': leaderboard_data,
                'count': len(leaderboard_data),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    def _get_global_leaderboard(self, limit: int) -> List[Dict[str, Any]]:
        """Get global leaderboard data."""
        # This is a simplified implementation
        # In practice, you'd use a more efficient query with proper indexing
        leaderboard_data = []
        
        # Get top users by total points
        top_users = (
            UserAchievement.objects
            .filter(is_awarded=True)
            .values('user_id', 'user__username')
            .annotate(total_points=Sum('points_awarded'))
            .order_by('-total_points')[:limit]
        )
        
        for rank, user_data in enumerate(top_users, 1):
            leaderboard_data.append({
                'rank': rank,
                'user_id': user_data['user_id'],
                'username': user_data['user__username'],
                'total_points': user_data['total_points'],
                'achievement_count': UserAchievement.objects.filter(
                    user_id=user_data['user_id'],
                    is_awarded=True
                ).count()
            })
        
        return leaderboard_data


class AchievementResource(BaseGamificationResource):
    """Resource for achievement operations."""
    
    pagination_class = AchievementPagination
    
    def get(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Get user's achievements."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Get query parameters
            contest_id = request.query_params.get('contest_id')
            achievement_type = request.query_params.get('achievement_type')
            
            # Get achievements
            queryset = UserAchievement.objects.filter(user_id=target_user_id, is_awarded=True)
            
            if contest_id:
                queryset = queryset.filter(contest_cycle_id=contest_id)
            
            if achievement_type:
                queryset = queryset.filter(achievement_type=achievement_type)
            
            achievements = queryset.order_by('-awarded_at')
            
            # Paginate results
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(achievements, request)
            
            if page is not None:
                serializer = UserAchievementSerializer(page, many=True)
                
                # Add achievement statistics
                paginator.achievement_stats = {
                    'total_achievements': achievements.count(),
                    'total_points': achievements.aggregate(total=Sum('points_awarded'))['total'] or 0,
                    'type_distribution': self._get_type_distribution(achievements)
                }
                
                return paginator.get_paginated_response(serializer.data)
            
            # Return unpaginated response
            serializer = UserAchievementSerializer(achievements, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'count': len(achievements),
                'user_id': target_user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    def _get_type_distribution(self, achievements) -> Dict[str, int]:
        """Get achievement type distribution."""
        distribution = {}
        for achievement in achievements:
            achievement_type = achievement.achievement_type or 'unknown'
            distribution[achievement_type] = distribution.get(achievement_type, 0) + 1
        return distribution


class SummaryResource(BaseGamificationResource):
    """Resource for gamification summary data."""
    
    def get(self, request: Request, user_id: Optional[str] = None) -> Response:
        """Get comprehensive gamification summary."""
        try:
            # Use authenticated user if no user_id provided
            target_user_id = user_id or self.get_user_id(request)
            
            # Get summary data
            from api.gamification import services
            
            summary = services.get_user_gamification_summary(user_id=target_user_id)
            
            return Response({
                'success': True,
                'data': summary,
                'user_id': target_user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)


class StatsResource(BaseGamificationResource):
    """Resource for gamification statistics."""
    
    permission_classes = [IsAdminUser]  # Admin only
    
    def get(self, request: Request) -> Response:
        """Get system-wide gamification statistics."""
        try:
            from django.db.models import Count, Sum, Avg
            
            # System statistics
            stats = {
                'badges': {
                    'total': Badge.objects.count(),
                    'active': Badge.objects.filter(is_active=True).count(),
                    'awarded': UserBadge.objects.count(),
                },
                'challenges': {
                    'total': DailyChallenge.objects.count(),
                    'active': DailyChallenge.objects.filter(is_active=True).count(),
                    'completed': UserDailyChallenge.objects.filter(is_completed=True).count(),
                },
                'streaks': {
                    'total': Streak.objects.count(),
                    'active': Streak.objects.filter(is_active=True).count(),
                    'average_days': Streak.objects.aggregate(avg=Avg('current_days'))['avg'] or 0,
                },
                'achievements': {
                    'total': UserAchievement.objects.count(),
                    'awarded': UserAchievement.objects.filter(is_awarded=True).count(),
                    'total_points': UserAchievement.objects.filter(
                        is_awarded=True
                    ).aggregate(total=Sum('points_awarded'))['total'] or 0,
                },
                'users': {
                    'with_badges': UserBadge.objects.values('user').distinct().count(),
                    'with_achievements': UserAchievement.objects.filter(
                        is_awarded=True
                    ).values('user').distinct().count(),
                    'with_streaks': Streak.objects.values('user').distinct().count(),
                }
            }
            
            return Response({
                'success': True,
                'data': stats,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)


# Resource registry for easy access
GAMIFICATION_RESOURCES = {
    'badges': BadgeResource,
    'user_badges': UserBadgeResource,
    'streaks': StreakResource,
    'challenges': ChallengeResource,
    'user_challenges': UserChallengeResource,
    'levels': LevelResource,
    'leaderboard': LeaderboardResource,
    'achievements': AchievementResource,
    'summary': SummaryResource,
    'stats': StatsResource,
}


def get_resource_class(resource_name: str) -> Optional[type]:
    """Get resource class by name."""
    return GAMIFICATION_RESOURCES.get(resource_name)


def create_resource_response(
    resource_name: str,
    request: Request,
    *args,
    **kwargs
) -> Response:
    """Create response using resource class."""
    resource_class = get_resource_class(resource_name)
    if not resource_class:
        raise ValueError(f"Unknown resource: {resource_name}")
    
    resource = resource_class()
    return resource.get(request, *args, **kwargs)
