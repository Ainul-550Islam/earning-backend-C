"""
Gamification Search — Search functionality for gamification data.

This module provides comprehensive search capabilities for gamification models
with advanced filtering, sorting, and relevance scoring.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q, F, Func, Value, CharField, IntegerField, Case, When, FloatField, Sum, Count, Avg
from django.db.models.functions import Coalesce, Cast
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, LeaderboardSnapshot,
    UserAchievement
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ContestCycleStatus, AchievementType
)
from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


class GamificationSearchEngine:
    """Main search engine for gamification data."""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.max_results = 1000
        self.default_page_size = 20
    
    def search_badges(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = 'relevance',
        page: int = 1,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search badges with text query and filters."""
        valid_filter_keys = {'rarity', 'criteria_type', 'is_active', 'min_points', 'max_points', 'points_min', 'points_max', 'badge_type', 'active_only'}
        if filters:
            invalid = set(filters.keys()) - valid_filter_keys
            if invalid:
                raise GamificationServiceError(f'Invalid filter keys: {invalid}')
        try:
            page_size = page_size or self.default_page_size
            offset = (page - 1) * page_size
            
            # Build base queryset
            queryset = Badge.objects.filter(is_active=True)
            
            # Apply text search
            if query:
                queryset = self._apply_badge_text_search(queryset, query)
            
            # Apply filters
            if filters:
                queryset = self._apply_badge_filters(queryset, filters)
            
            # Apply sorting
            queryset = self._apply_badge_sorting(queryset, sort_by, query)
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            results = queryset[offset:offset + page_size]
            
            # Serialize results
            serialized_results = self._serialize_badges(results)
            
            return {
                'results': serialized_results,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1,
                'query': query,
                'filters': filters or {},
                'sort_by': sort_by,
            }
            
        except Exception as e:
            logger.error(f"Error searching badges: {e}")
            raise GamificationServiceError(f"Badge search failed: {e}")
    
    def search_user_badges(
        self,
        user_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = 'relevance',
        page: int = 1,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search user's badges with text query and filters."""
        try:
            page_size = page_size or self.default_page_size
            offset = (page - 1) * page_size
            
            # Build base queryset
            queryset = UserBadge.objects.filter(user_id=user_id).select_related('badge')
            
            # Apply text search
            if query:
                queryset = self._apply_user_badge_text_search(queryset, query)
            
            # Apply filters
            if filters:
                queryset = self._apply_user_badge_filters(queryset, filters)
            
            # Apply sorting
            queryset = self._apply_user_badge_sorting(queryset, sort_by, query)
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            results = queryset[offset:offset + page_size]
            
            # Serialize results
            serialized_results = self._serialize_user_badges(results)
            
            return {
                'results': serialized_results,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1,
                'query': query,
                'filters': filters or {},
                'sort_by': sort_by,
                'user_id': user_id,
            }
            
        except Exception as e:
            logger.error(f"Error searching user badges: {e}")
            raise GamificationServiceError(f"User badge search failed: {e}")
    
    def search_challenges(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = 'relevance',
        page: int = 1,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search daily challenges with text query and filters."""
        try:
            page_size = page_size or self.default_page_size
            offset = (page - 1) * page_size
            
            # Build base queryset
            queryset = DailyChallenge.objects.filter(is_active=True)
            
            # Apply text search
            if query:
                queryset = self._apply_challenge_text_search(queryset, query)
            
            # Apply filters
            if filters:
                queryset = self._apply_challenge_filters(queryset, filters)
            
            # Apply sorting
            queryset = self._apply_challenge_sorting(queryset, sort_by, query)
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            results = queryset[offset:offset + page_size]
            
            # Serialize results
            serialized_results = self._serialize_challenges(results)
            
            return {
                'results': serialized_results,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1,
                'query': query,
                'filters': filters or {},
                'sort_by': sort_by,
            }
            
        except Exception as e:
            logger.error(f"Error searching challenges: {e}")
            raise GamificationServiceError(f"Challenge search failed: {e}")
    
    def search_contests(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = 'relevance',
        page: int = 1,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search contest cycles with text query and filters."""
        try:
            page_size = page_size or self.default_page_size
            offset = (page - 1) * page_size
            
            # Build base queryset
            queryset = ContestCycle.objects.all()
            
            # Apply text search
            if query:
                queryset = self._apply_contest_text_search(queryset, query)
            
            # Apply filters
            if filters:
                queryset = self._apply_contest_filters(queryset, filters)
            
            # Apply sorting
            queryset = self._apply_contest_sorting(queryset, sort_by, query)
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            results = queryset[offset:offset + page_size]
            
            # Serialize results
            serialized_results = self._serialize_contests(results)
            
            return {
                'results': serialized_results,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1,
                'query': query,
                'filters': filters or {},
                'sort_by': sort_by,
            }
            
        except Exception as e:
            logger.error(f"Error searching contests: {e}")
            raise GamificationServiceError(f"Contest search failed: {e}")
    
    def search_achievements(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = 'relevance',
        page: int = 1,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search user achievements with text query and filters."""
        try:
            page_size = page_size or self.default_page_size
            offset = (page - 1) * page_size
            
            # Build base queryset
            queryset = UserAchievement.objects.filter(is_awarded=True).select_related('user', 'contest_cycle')
            
            # Apply text search
            if query:
                queryset = self._apply_achievement_text_search(queryset, query)
            
            # Apply filters
            if filters:
                queryset = self._apply_achievement_filters(queryset, filters)
            
            # Apply sorting
            queryset = self._apply_achievement_sorting(queryset, sort_by, query)
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            results = queryset[offset:offset + page_size]
            
            # Serialize results
            serialized_results = self._serialize_achievements(results)
            
            return {
                'results': serialized_results,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1,
                'query': query,
                'filters': filters or {},
                'sort_by': sort_by,
            }
            
        except Exception as e:
            logger.error(f"Error searching achievements: {e}")
            raise GamificationServiceError(f"Achievement search failed: {e}")
    
    def search_users(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = 'relevance',
        page: int = 1,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search users by gamification stats."""
        try:
            page_size = page_size or self.default_page_size
            offset = (page - 1) * page_size
            
            # Build base queryset with gamification stats
            queryset = (
                UserAchievement.objects
                .filter(is_awarded=True)
                .values('user_id')
                .annotate(
                    username=F('user__username'),
                    total_points=Sum('points_awarded'),
                    achievement_count=Count('id'),
                    streak_days=Coalesce(
                        Streak.objects.filter(user_id=F('user_id')).values('current_days')[:1],
                        Value(0, output_field=IntegerField())
                    )
                )
            )
            
            # Apply text search
            if query:
                queryset = self._apply_user_text_search(queryset, query)
            
            # Apply filters
            if filters:
                queryset = self._apply_user_filters(queryset, filters)
            
            # Apply sorting
            queryset = self._apply_user_sorting(queryset, sort_by, query)
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            results = queryset[offset:offset + page_size]
            
            # Serialize results
            serialized_results = self._serialize_users(results)
            
            return {
                'results': serialized_results,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1,
                'query': query,
                'filters': filters or {},
                'sort_by': sort_by,
            }
            
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            raise GamificationServiceError(f"User search failed: {e}")
    
    def _apply_badge_text_search(self, queryset, query: str):
        """Apply text search to badge queryset."""
        query_terms = query.split()
        q_objects = Q()
        
        for term in query_terms:
            q_objects |= Q(name__icontains=term)
            q_objects |= Q(description__icontains=term)
            q_objects |= Q(icon__icontains=term)
        
        return queryset.filter(q_objects)
    
    def _apply_user_badge_text_search(self, queryset, query: str):
        """Apply text search to user badge queryset."""
        query_terms = query.split()
        q_objects = Q()
        
        for term in query_terms:
            q_objects |= Q(badge__name__icontains=term)
            q_objects |= Q(badge__description__icontains=term)
            q_objects |= Q(badge__icon__icontains=term)
        
        return queryset.filter(q_objects)
    
    def _apply_challenge_text_search(self, queryset, query: str):
        """Apply text search to challenge queryset."""
        query_terms = query.split()
        q_objects = Q()
        
        for term in query_terms:
            q_objects |= Q(title__icontains=term)
            q_objects |= Q(description__icontains=term)
            q_objects |= Q(target_action__icontains=term)
        
        return queryset.filter(q_objects)
    
    def _apply_contest_text_search(self, queryset, query: str):
        """Apply text search to contest queryset."""
        query_terms = query.split()
        q_objects = Q()
        
        for term in query_terms:
            q_objects |= Q(name__icontains=term)
            q_objects |= Q(description__icontains=term)
        
        return queryset.filter(q_objects)
    
    def _apply_achievement_text_search(self, queryset, query: str):
        """Apply text search to achievement queryset."""
        query_terms = query.split()
        q_objects = Q()
        
        for term in query_terms:
            q_objects |= Q(user__username__icontains=term)
            q_objects |= Q(contest_cycle__name__icontains=term)
            q_objects |= Q(achievement_type__icontains=term)
        
        return queryset.filter(q_objects)
    
    def _apply_user_text_search(self, queryset, query: str):
        """Apply text search to user queryset."""
        query_terms = query.split()
        q_objects = Q()
        
        for term in query_terms:
            q_objects |= Q(username__icontains=term)
        
        return queryset.filter(q_objects)
    
    def _apply_badge_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to badge queryset."""
        if 'rarity' in filters:
            queryset = queryset.filter(rarity=filters['rarity'])
        
        if 'criteria_type' in filters:
            queryset = queryset.filter(criteria_type=filters['criteria_type'])
        
        if 'points_min' in filters:
            queryset = queryset.filter(points_bonus__gte=filters['points_min'])
        
        if 'points_max' in filters:
            queryset = queryset.filter(points_bonus__lte=filters['points_max'])
        
        return queryset
    
    def _apply_user_badge_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to user badge queryset."""
        if 'is_pinned' in filters:
            queryset = queryset.filter(is_pinned=filters['is_pinned'])
        
        if 'rarity' in filters:
            queryset = queryset.filter(badge__rarity=filters['rarity'])
        
        if 'earned_after' in filters:
            queryset = queryset.filter(earned_at__gte=filters['earned_after'])
        
        if 'earned_before' in filters:
            queryset = queryset.filter(earned_at__lte=filters['earned_before'])
        
        return queryset
    
    def _apply_challenge_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to challenge queryset."""
        if 'action' in filters:
            queryset = queryset.filter(target_action=filters['action'])
        
        if 'date' in filters:
            queryset = queryset.filter(date=filters['date'])
        
        if 'date_from' in filters:
            queryset = queryset.filter(date__gte=filters['date_from'])
        
        if 'date_to' in filters:
            queryset = queryset.filter(date__lte=filters['date_to'])
        
        if 'points_min' in filters:
            queryset = queryset.filter(bonus_points__gte=filters['points_min'])
        
        if 'points_max' in filters:
            queryset = queryset.filter(bonus_points__lte=filters['points_max'])
        
        return queryset
    
    def _apply_contest_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to contest queryset."""
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        
        if 'start_date_from' in filters:
            queryset = queryset.filter(start_date__gte=filters['start_date_from'])
        
        if 'start_date_to' in filters:
            queryset = queryset.filter(start_date__lte=filters['start_date_to'])
        
        if 'end_date_from' in filters:
            queryset = queryset.filter(end_date__gte=filters['end_date_from'])
        
        if 'end_date_to' in filters:
            queryset = queryset.filter(end_date__lte=filters['end_date_to'])
        
        return queryset
    
    def _apply_achievement_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to achievement queryset."""
        if 'user_id' in filters:
            queryset = queryset.filter(user_id=filters['user_id'])
        
        if 'contest_id' in filters:
            queryset = queryset.filter(contest_cycle_id=filters['contest_id'])
        
        if 'achievement_type' in filters:
            queryset = queryset.filter(achievement_type=filters['achievement_type'])
        
        if 'points_min' in filters:
            queryset = queryset.filter(points_awarded__gte=filters['points_min'])
        
        if 'points_max' in filters:
            queryset = queryset.filter(points_awarded__lte=filters['points_max'])
        
        if 'rank_min' in filters:
            queryset = queryset.filter(rank__gte=filters['rank_min'])
        
        if 'rank_max' in filters:
            queryset = queryset.filter(rank__lte=filters['rank_max'])
        
        if 'awarded_after' in filters:
            queryset = queryset.filter(awarded_at__gte=filters['awarded_after'])
        
        if 'awarded_before' in filters:
            queryset = queryset.filter(awarded_at__lte=filters['awarded_before'])
        
        return queryset
    
    def _apply_user_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to user queryset."""
        if 'points_min' in filters:
            queryset = queryset.filter(total_points__gte=filters['points_min'])
        
        if 'points_max' in filters:
            queryset = queryset.filter(total_points__lte=filters['points_max'])
        
        if 'achievements_min' in filters:
            queryset = queryset.filter(achievement_count__gte=filters['achievements_min'])
        
        if 'achievements_max' in filters:
            queryset = queryset.filter(achievement_count__lte=filters['achievements_max'])
        
        if 'streak_days_min' in filters:
            queryset = queryset.filter(streak_days__gte=filters['streak_days_min'])
        
        if 'streak_days_max' in filters:
            queryset = queryset.filter(streak_days__lte=filters['streak_days_max'])
        
        return queryset
    
    def _apply_badge_sorting(self, queryset, sort_by: str, query: str):
        """Apply sorting to badge queryset."""
        if sort_by == 'relevance' and query:
            # Simple relevance sorting - prioritize exact matches
            queryset = queryset.annotate(
                relevance_score=Case(
                    When(name__iexact=query, then=Value(100)),
                    When(name__icontains=query, then=Value(50)),
                    When(description__icontains=query, then=Value(25)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-relevance_score', 'name')
        elif sort_by == 'name':
            queryset = queryset.order_by('name')
        elif sort_by == 'points':
            queryset = queryset.order_by('-points_bonus')
        elif sort_by == 'rarity':
            queryset = queryset.order_by('-rarity')
        elif sort_by == 'created':
            queryset = queryset.order_by('-created_at')
        else:
            queryset = queryset.order_by('name')
        
        return queryset
    
    def _apply_user_badge_sorting(self, queryset, sort_by: str, query: str):
        """Apply sorting to user badge queryset."""
        if sort_by == 'relevance' and query:
            queryset = queryset.annotate(
                relevance_score=Case(
                    When(badge__name__iexact=query, then=Value(100)),
                    When(badge__name__icontains=query, then=Value(50)),
                    When(badge__description__icontains=query, then=Value(25)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-relevance_score', '-earned_at')
        elif sort_by == 'earned_at':
            queryset = queryset.order_by('-earned_at')
        elif sort_by == 'points':
            queryset = queryset.order_by('-badge__points_bonus')
        elif sort_by == 'name':
            queryset = queryset.order_by('badge__name')
        else:
            queryset = queryset.order_by('-earned_at')
        
        return queryset
    
    def _apply_challenge_sorting(self, queryset, sort_by: str, query: str):
        """Apply sorting to challenge queryset."""
        if sort_by == 'relevance' and query:
            queryset = queryset.annotate(
                relevance_score=Case(
                    When(title__iexact=query, then=Value(100)),
                    When(title__icontains=query, then=Value(50)),
                    When(description__icontains=query, then=Value(25)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-relevance_score', '-date')
        elif sort_by == 'date':
            queryset = queryset.order_by('-date')
        elif sort_by == 'points':
            queryset = queryset.order_by('-bonus_points')
        elif sort_by == 'title':
            queryset = queryset.order_by('title')
        else:
            queryset = queryset.order_by('-date')
        
        return queryset
    
    def _apply_contest_sorting(self, queryset, sort_by: str, query: str):
        """Apply sorting to contest queryset."""
        if sort_by == 'relevance' and query:
            queryset = queryset.annotate(
                relevance_score=Case(
                    When(name__iexact=query, then=Value(100)),
                    When(name__icontains=query, then=Value(50)),
                    When(description__icontains=query, then=Value(25)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-relevance_score', '-start_date')
        elif sort_by == 'start_date':
            queryset = queryset.order_by('-start_date')
        elif sort_by == 'end_date':
            queryset = queryset.order_by('-end_date')
        elif sort_by == 'name':
            queryset = queryset.order_by('name')
        else:
            queryset = queryset.order_by('-start_date')
        
        return queryset
    
    def _apply_achievement_sorting(self, queryset, sort_by: str, query: str):
        """Apply sorting to achievement queryset."""
        if sort_by == 'relevance' and query:
            queryset = queryset.annotate(
                relevance_score=Case(
                    When(user__username__iexact=query, then=Value(100)),
                    When(user__username__icontains=query, then=Value(50)),
                    When(contest_cycle__name__icontains=query, then=Value(25)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-relevance_score', '-awarded_at')
        elif sort_by == 'awarded_at':
            queryset = queryset.order_by('-awarded_at')
        elif sort_by == 'points':
            queryset = queryset.order_by('-points_awarded')
        elif sort_by == 'rank_at_award':
            queryset = queryset.order_by('rank_at_award')
        elif sort_by == 'username':
            queryset = queryset.order_by('user__username')
        else:
            queryset = queryset.order_by('-awarded_at')
        
        return queryset
    
    def _apply_user_sorting(self, queryset, sort_by: str, query: str):
        """Apply sorting to user queryset."""
        if sort_by == 'relevance' and query:
            queryset = queryset.annotate(
                relevance_score=Case(
                    When(username__iexact=query, then=Value(100)),
                    When(username__icontains=query, then=Value(50)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-relevance_score', '-total_points')
        elif sort_by == 'points':
            queryset = queryset.order_by('-total_points')
        elif sort_by == 'achievements':
            queryset = queryset.order_by('-achievement_count')
        elif sort_by == 'streak':
            queryset = queryset.order_by('-streak_days')
        elif sort_by == 'username':
            queryset = queryset.order_by('username')
        else:
            queryset = queryset.order_by('-total_points')
        
        return queryset
    
    def _serialize_badges(self, badges):
        """Serialize badge results."""
        return [
            {
                'id': str(badge.id),
                'name': badge.name,
                'description': badge.description,
                'icon': badge.icon,
                'rarity': badge.rarity,
                'criteria_type': badge.criteria_type,
                'criteria_value': badge.criteria_value,
                'points_bonus': badge.points_bonus,
                'is_active': badge.is_active,
                'sort_order': badge.sort_order,
            }
            for badge in badges
        ]
    
    def _serialize_user_badges(self, user_badges):
        """Serialize user badge results."""
        return [
            {
                'id': str(user_badge.id),
                'badge_id': str(user_badge.badge.id),
                'badge_name': user_badge.badge.name,
                'badge_description': user_badge.badge.description,
                'badge_icon': user_badge.badge.icon,
                'badge_rarity': user_badge.badge.rarity,
                'badge_points_bonus': user_badge.badge.points_bonus,
                'is_pinned': user_badge.is_pinned,
                'earned_at': user_badge.earned_at.isoformat(),
                'metadata': user_badge.metadata or {},
            }
            for user_badge in user_badges
        ]
    
    def _serialize_challenges(self, challenges):
        """Serialize challenge results."""
        return [
            {
                'id': str(challenge.id),
                'title': challenge.title,
                'description': challenge.description,
                'target_action': challenge.target_action,
                'target_count': challenge.target_count,
                'bonus_points': challenge.bonus_points,
                'date': challenge.date.isoformat(),
                'is_active': challenge.is_active,
                'metadata': challenge.metadata or {},
            }
            for challenge in challenges
        ]
    
    def _serialize_contests(self, contests):
        """Serialize contest results."""
        return [
            {
                'id': str(contest.id),
                'name': contest.name,
                'description': contest.description,
                'status': contest.status,
                'start_date': contest.start_date.isoformat(),
                'end_date': contest.end_date.isoformat(),
                'points_multiplier': float(contest.points_multiplier),
                'metadata': contest.metadata or {},
            }
            for contest in contests
        ]
    
    def _serialize_achievements(self, achievements):
        """Serialize achievement results."""
        return [
            {
                'id': str(achievement.id),
                'user_id': str(achievement.user.id),
                'username': achievement.user.username,
                'contest_id': str(achievement.contest_cycle.id) if achievement.contest_cycle else None,
                'contest_name': achievement.contest_cycle.name if achievement.contest_cycle else None,
                'achievement_type': achievement.achievement_type,
                'points_awarded': achievement.points_awarded,
                'rank_at_award': achievement.rank_at_award,
                'is_awarded': achievement.is_awarded,
                'awarded_at': achievement.awarded_at.isoformat() if achievement.awarded_at else None,
                'metadata': achievement.metadata or {},
            }
            for achievement in achievements
        ]
    
    def _serialize_users(self, users):
        """Serialize user results."""
        return [
            {
                'user_id': str(user['user_id']),
                'username': user['username'],
                'total_points': user['total_points'],
                'achievement_count': user['achievement_count'],
                'badge_count': 0,  # Not available in this context
                'streak_days': user['streak_days'],
            }
            for user in users
        ]


class SearchSuggestionEngine:
    """Engine for providing search suggestions and autocomplete."""
    
    def __init__(self):
        self.cache_timeout = 600  # 10 minutes
        self.max_suggestions = 10
    
    def get_badge_suggestions(self, query: str) -> List[str]:
        """Get badge name suggestions."""
        cache_key = f"badge_suggestions:{query.lower()}"
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            suggestions = list(
                Badge.objects
                .filter(is_active=True, name__icontains=query)
                .values_list('name', flat=True)
                .order_by('name')[:self.max_suggestions]
            )
            cache.set(cache_key, suggestions, self.cache_timeout)
        
        return suggestions
    
    def get_challenge_suggestions(self, query: str) -> List[str]:
        """Get challenge title suggestions."""
        cache_key = f"challenge_suggestions:{query.lower()}"
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            suggestions = list(
                DailyChallenge.objects
                .filter(is_active=True, title__icontains=query)
                .values_list('title', flat=True)
                .order_by('title')[:self.max_suggestions]
            )
            cache.set(cache_key, suggestions, self.cache_timeout)
        
        return suggestions
    
    def get_user_suggestions(self, query: str) -> List[str]:
        """Get username suggestions."""
        cache_key = f"user_suggestions:{query.lower()}"
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            suggestions = list(
                User.objects
                .filter(username__icontains=query)
                .values_list('username', flat=True)
                .order_by('username')[:self.max_suggestions]
            )
            cache.set(cache_key, suggestions, self.cache_timeout)
        
        return suggestions
    
    def get_popular_searches(self) -> List[str]:
        """Get popular search terms."""
        # This would typically be stored in a search analytics table
        # For now, return some common gamification terms
        return [
            'badge',
            'challenge',
            'streak',
            'level',
            'contest',
            'achievement',
            'points',
            'reward',
            'leaderboard',
        ]


class SearchAnalytics:
    """Analytics for search functionality."""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
    
    def log_search(self, user_id: str, search_type: str, query: str, filters: Dict[str, Any], results_count: int):
        """Log search query for analytics."""
        try:
            # This would typically be stored in a search analytics table
            # For now, just log the search
            logger.info(f"Search logged: user={user_id}, type={search_type}, query={query}, results={results_count}")
        except Exception as e:
            logger.error(f"Error logging search: {e}")
    
    def get_popular_searches(self, search_type: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get popular searches for a search type."""
        # This would typically be retrieved from analytics database
        # For now, return empty list
        return []
    
    def get_search_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get overall search statistics."""
        # This would typically be retrieved from analytics database
        # For now, return empty stats
        return {
            'total_searches': 0,
            'unique_users': 0,
            'avg_results_per_search': 0,
            'most_popular_type': '',
        }


# Global search engine instance
search_engine = GamificationSearchEngine()
suggestion_engine = SearchSuggestionEngine()
search_analytics = SearchAnalytics()


# Convenience functions
def search_badges(query: str, **kwargs) -> Dict[str, Any]:
    """Search badges with convenience function."""
    return search_engine.search_badges(query, **kwargs)


def search_challenges(query: str, **kwargs) -> Dict[str, Any]:
    """Search challenges with convenience function."""
    return search_engine.search_challenges(query, **kwargs)


def search_contests(query: str, **kwargs) -> Dict[str, Any]:
    """Search contests with convenience function."""
    return search_engine.search_contests(query, **kwargs)


def get_search_suggestions(search_type: str, query: str) -> List[str]:
    """Get search suggestions."""
    if search_type == 'badges':
        return suggestion_engine.get_badge_suggestions(query)
    elif search_type == 'challenges':
        return suggestion_engine.get_challenge_suggestions(query)
    elif search_type == 'users':
        return suggestion_engine.get_user_suggestions(query)
    else:
        return []
