"""
Gamification API Endpoints — Custom API endpoint definitions and handlers.

This module provides specialized API endpoints for gamification features
with custom routing, authentication, and response handling.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, LeaderboardSnapshot
)
from api.gamification.services import (
    BadgeService, DailyChallengeService, StreakService, LevelUpService
)
from api.gamification.serializers import (
    BadgeSerializer, UserBadgeSerializer, DailyChallengeSerializer,
    UserDailyChallengeSerializer, StreakSerializer, LevelConfigSerializer
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.throttling import GamificationRateThrottle

User = get_user_model()
logger = logging.getLogger(__name__)


class GamificationEndpoint:
    """Base class for gamification endpoints."""
    
    def __init__(self):
        self.rate_limit = GamificationRateThrottle()
    
    def handle_error(self, error: Exception) -> JsonResponse:
        """Handle endpoint errors consistently."""
        if isinstance(error, GamificationServiceError):
            return JsonResponse({
                'error': str(error),
                'error_type': 'GamificationServiceError',
                'timestamp': timezone.now().isoformat()
            }, status=400)
        elif isinstance(error, ValidationError):
            return JsonResponse({
                'error': str(error),
                'error_type': 'ValidationError',
                'timestamp': timezone.now().isoformat()
            }, status=400)
        else:
            logger.error(f"Unexpected error in gamification endpoint: {error}")
            return JsonResponse({
                'error': 'An unexpected error occurred',
                'error_type': 'InternalError',
                'timestamp': timezone.now().isoformat()
            }, status=500)


class BadgeEndpoint(GamificationEndpoint):
    """Badge-related API endpoints."""
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_available_badges(self, request):
        """Get all available badges."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get query parameters
            is_active = request.GET.get('is_active', 'true').lower() == 'true'
            rarity = request.GET.get('rarity')
            criteria_type = request.GET.get('criteria_type')
            
            # Get badges
            badges = BadgeService.get_available_badges(
                is_active=is_active,
                rarity=rarity,
                criteria_type=criteria_type
            )
            
            # Serialize response
            serializer = BadgeSerializer(badges, many=True)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'count': len(badges),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_user_badges(self, request, user_id: str):
        """Get user's earned badges."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get query parameters
            is_pinned = request.GET.get('is_pinned')
            if is_pinned is not None:
                is_pinned = is_pinned.lower() == 'true'
            
            rarity = request.GET.get('rarity')
            limit = request.GET.get('limit')
            if limit is not None:
                limit = int(limit)
            
            # Get user badges
            user_badges = BadgeService.get_user_badges(
                user_id=user_id,
                is_pinned=is_pinned,
                rarity=rarity,
                limit=limit
            )
            
            # Serialize response
            serializer = UserBadgeSerializer(user_badges, many=True)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'count': len(user_badges),
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["POST"])
    def check_eligibility(self, request, user_id: str):
        """Check user's badge eligibility."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Parse request data
            import json
            data = json.loads(request.body)
            
            user_points = data.get('user_points', 0)
            streak_days = data.get('streak_days', 0)
            achievement_count = data.get('achievement_count', 0)
            contest_wins = data.get('contest_wins', 0)
            referral_count = data.get('referral_count', 0)
            
            # Check eligibility
            eligible_badges = BadgeService.check_user_badge_eligibility(
                user_id=user_id,
                user_points=user_points,
                streak_days=streak_days,
                achievement_count=achievement_count,
                contest_wins=contest_wins,
                referral_count=referral_count
            )
            
            # Serialize response
            serializer = BadgeSerializer(eligible_badges, many=True)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'count': len(eligible_badges),
                'user_id': user_id,
                'criteria': {
                    'user_points': user_points,
                    'streak_days': streak_days,
                    'achievement_count': achievement_count,
                    'contest_wins': contest_wins,
                    'referral_count': referral_count
                },
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["POST"])
    def award_badges(self, request, user_id: str):
        """Award eligible badges to user."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Parse request data
            import json
            data = json.loads(request.body)
            
            user_points = data.get('user_points', 0)
            streak_days = data.get('streak_days', 0)
            achievement_count = data.get('achievement_count', 0)
            contest_wins = data.get('contest_wins', 0)
            referral_count = data.get('referral_count', 0)
            metadata = data.get('metadata', {})
            
            # Award badges
            awarded_badges = BadgeService.award_eligible_badges(
                user_id=user_id,
                user_points=user_points,
                streak_days=streak_days,
                achievement_count=achievement_count,
                contest_wins=contest_wins,
                referral_count=referral_count,
                metadata=metadata
            )
            
            # Serialize response
            serializer = UserBadgeSerializer(awarded_badges, many=True)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'count': len(awarded_badges),
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)


class StreakEndpoint(GamificationEndpoint):
    """Streak-related API endpoints."""
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_user_streak(self, request, user_id: str):
        """Get user's current streak."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get or create user streak
            streak = StreakService.get_or_create_user_streak(user_id=user_id)
            
            # Serialize response
            serializer = StreakSerializer(streak)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["POST"])
    def update_activity(self, request, user_id: str):
        """Update user's streak activity."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Parse request data
            import json
            data = json.loads(request.body)
            
            activity_date = data.get('activity_date')
            if activity_date:
                activity_date = datetime.fromisoformat(activity_date).date()
            
            metadata = data.get('metadata', {})
            
            # Update activity
            streak, was_extended, days_added = StreakService.update_user_activity(
                user_id=user_id,
                activity_date=activity_date,
                metadata=metadata
            )
            
            # Serialize response
            serializer = StreakSerializer(streak)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'user_id': user_id,
                'was_extended': was_extended,
                'days_added': days_added,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_streak_statistics(self, request, user_id: str):
        """Get user's streak statistics."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get statistics
            stats = StreakService.get_streak_statistics(user_id=user_id)
            
            return JsonResponse({
                'success': True,
                'data': stats,
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)


class ChallengeEndpoint(GamificationEndpoint):
    """Daily challenge-related API endpoints."""
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_active_challenges(self, request):
        """Get active daily challenges."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get query parameters
            challenge_date = request.GET.get('date')
            if challenge_date:
                challenge_date = datetime.fromisoformat(challenge_date).date()
            
            target_action = request.GET.get('target_action')
            
            # Get challenges
            challenges = DailyChallengeService.get_active_challenges(
                challenge_date=challenge_date,
                target_action=target_action
            )
            
            # Serialize response
            serializer = DailyChallengeSerializer(challenges, many=True)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'count': len(challenges),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_user_progress(self, request, user_id: str):
        """Get user's challenge progress."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get query parameters
            challenge_id = request.GET.get('challenge_id')
            challenge_date = request.GET.get('date')
            if challenge_date:
                challenge_date = datetime.fromisoformat(challenge_date).date()
            
            # Get progress
            user_challenges = DailyChallengeService.get_user_challenge_progress(
                user_id=user_id,
                challenge_id=challenge_id,
                challenge_date=challenge_date
            )
            
            # Serialize response
            serializer = UserDailyChallengeSerializer(user_challenges, many=True)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'count': len(user_challenges),
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["POST"])
    def start_challenge(self, request, user_id: str):
        """Start a daily challenge for user."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Parse request data
            import json
            data = json.loads(request.body)
            
            challenge_id = data.get('challenge_id')
            if not challenge_id:
                return JsonResponse({
                    'error': 'challenge_id is required',
                    'error_type': 'ValidationError'
                }, status=400)
            
            # Start challenge
            user_challenge = DailyChallengeService.start_user_challenge(
                user_id=user_id,
                challenge_id=challenge_id
            )
            
            # Serialize response
            serializer = UserDailyChallengeSerializer(user_challenge)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["POST"])
    def update_progress(self, request, user_id: str):
        """Update challenge progress."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Parse request data
            import json
            data = json.loads(request.body)
            
            challenge_id = data.get('challenge_id')
            increment_amount = data.get('increment_amount', 1)
            action_metadata = data.get('action_metadata', {})
            
            if not challenge_id:
                return JsonResponse({
                    'error': 'challenge_id is required',
                    'error_type': 'ValidationError'
                }, status=400)
            
            # Update progress
            user_challenge, completed = DailyChallengeService.update_challenge_progress(
                user_id=user_id,
                challenge_id=challenge_id,
                increment_amount=increment_amount,
                action_metadata=action_metadata
            )
            
            # Serialize response
            serializer = UserDailyChallengeSerializer(user_challenge)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'completed': completed,
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)


class LevelEndpoint(GamificationEndpoint):
    """Level-related API endpoints."""
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_available_levels(self, request):
        """Get all available levels."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get query parameters
            is_active = request.GET.get('is_active', 'true').lower() == 'true'
            
            # Get levels
            levels = LevelUpService.get_available_levels(is_active=is_active)
            
            # Serialize response
            serializer = LevelConfigSerializer(levels, many=True)
            
            return JsonResponse({
                'success': True,
                'data': serializer.data,
                'count': len(levels),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)
    
    @csrf_exempt
    @require_http_methods(["GET"])
    def get_user_level(self, request, user_id: str):
        """Get user's current level."""
        try:
            # Apply rate limiting
            if not self.rate_limit.allow_request(request):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'error_type': 'RateLimitError'
                }, status=429)
            
            # Get user's total points from achievements
            from api.gamification.models import UserAchievement
            from django.db.models import Sum
            
            total_points = UserAchievement.objects.filter(
                user_id=user_id,
                is_awarded=True
            ).aggregate(total=Sum('points_awarded'))['total'] or 0
            
            # Get current level and progress
            current_level = LevelUpService.get_user_level(total_points)
            progress = LevelUpService.get_level_progress(total_points)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'total_points': total_points,
                    'current_level': current_level.level_number if current_level else 0,
                    'current_level_title': current_level.title if current_level else "No Level",
                    'progress': progress
                },
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_error(e)


# REST Framework API Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def badge_summary(request):
    """Get user's badge summary."""
    try:
        from api.gamification.services import BadgeService
        
        stats = BadgeService.get_badge_statistics(user_id=request.user.id)
        
        return Response({
            'success': True,
            'data': stats,
            'user_id': str(request.user.id),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in badge_summary: {e}")
        return Response({
            'error': str(e),
            'error_type': 'InternalError',
            'timestamp': timezone.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gamification_dashboard(request):
    """Get comprehensive gamification dashboard data."""
    try:
        from api.gamification import services
        
        # Get comprehensive summary
        summary = services.get_user_gamification_summary(user_id=request.user.id)
        
        return Response({
            'success': True,
            'data': summary,
            'user_id': str(request.user.id),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in gamification_dashboard: {e}")
        return Response({
            'error': str(e),
            'error_type': 'InternalError',
            'timestamp': timezone.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_stats(request):
    """Get system-wide gamification statistics."""
    try:
        from api.gamification.models import Badge, UserBadge, UserAchievement
        from django.db.models import Count, Sum, Avg
        
        # System statistics
        stats = {
            'total_badges': Badge.objects.count(),
            'active_badges': Badge.objects.filter(is_active=True).count(),
            'total_user_badges': UserBadge.objects.count(),
            'total_achievements': UserAchievement.objects.count(),
            'total_points_awarded': UserAchievement.objects.filter(
                is_awarded=True
            ).aggregate(total=Sum('points_awarded'))['total'] or 0,
            'average_points_per_achievement': UserAchievement.objects.filter(
                is_awarded=True
            ).aggregate(avg=Avg('points_awarded'))['avg'] or 0,
            'users_with_badges': UserBadge.objects.values('user').distinct().count(),
            'users_with_achievements': UserAchievement.objects.filter(
                is_awarded=True
            ).values('user').distinct().count(),
        }
        
        return Response({
            'success': True,
            'data': stats,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in system_stats: {e}")
        return Response({
            'error': str(e),
            'error_type': 'InternalError',
            'timestamp': timezone.now().isoformat()
        }, status=500)


# URL routing helper
def get_gamification_urlpatterns():
    """Get URL patterns for gamification endpoints."""
    from django.urls import path
    
    urlpatterns = [
        # Badge endpoints
        path('badges/', BadgeEndpoint().get_available_badges, name='badge-list'),
        path('badges/<uuid:user_id>/', BadgeEndpoint().get_user_badges, name='user-badges'),
        path('badges/<uuid:user_id>/check-eligibility/', BadgeEndpoint().check_eligibility, name='badge-check-eligibility'),
        path('badges/<uuid:user_id>/award/', BadgeEndpoint().award_badges, name='badge-award'),
        
        # Streak endpoints
        path('streaks/<uuid:user_id>/', StreakEndpoint().get_user_streak, name='user-streak'),
        path('streaks/<uuid:user_id>/update/', StreakEndpoint().update_activity, name='streak-update'),
        path('streaks/<uuid:user_id>/statistics/', StreakEndpoint().get_streak_statistics, name='streak-statistics'),
        
        # Challenge endpoints
        path('challenges/', ChallengeEndpoint().get_active_challenges, name='challenge-list'),
        path('challenges/<uuid:user_id>/progress/', ChallengeEndpoint().get_user_progress, name='user-challenge-progress'),
        path('challenges/<uuid:user_id>/start/', ChallengeEndpoint().start_challenge, name='challenge-start'),
        path('challenges/<uuid:user_id>/update/', ChallengeEndpoint().update_progress, name='challenge-update'),
        
        # Level endpoints
        path('levels/', LevelEndpoint().get_available_levels, name='level-list'),
        path('levels/<uuid:user_id>/', LevelEndpoint().get_user_level, name='user-level'),
    ]
    
    return urlpatterns
