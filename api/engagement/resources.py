# engagement/resources.py
"""
Resource definitions for engagement system.
Provides API resource classes and data structures.
"""
from datetime import date
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta

from .schemas import (
    CheckInSchema, SpinWheelSchema, QuestSchema, UserQuestSchema,
    AchievementSchema, UserAchievementSchema, ShopItemSchema,
    ShopPurchaseSchema, LeaderboardSchema, NotificationSchema,
    UserProfileResponseSchema, PaginatedResponseSchema
)
from .services import (
    CheckInService, SpinService, QuestService, AchievementService,
    ShopService, LeaderboardService, NotificationService, AnalyticsService
)
from .exceptions import EngagementError
from .decorators import engagement_endpoint


class BaseResource:
    """Base resource class for engagement API resources."""
    
    def __init__(self, request=None, user=None):
        self.request = request
        self.user = user or (request.user if request else None)
        self.tenant = getattr(self.user, 'tenant', None) if self.user else None
    
    def get_cache_key(self, *args):
        """Generate cache key for resource."""
        key_parts = [self.__class__.__name__]
        if self.user:
            key_parts.append(f"user_{self.user.id}")
        if self.tenant:
            key_parts.append(f"tenant_{self.tenant.id}")
        key_parts.extend(str(arg) for arg in args)
        return ":".join(key_parts)
    
    def cache_get(self, key, default=None):
        """Get value from cache."""
        return cache.get(key, default)
    
    def cache_set(self, key, value, timeout=300):
        """Set value in cache."""
        cache.set(key, value, timeout)
    
    def cache_delete(self, key):
        """Delete value from cache."""
        cache.delete(key)


class CheckInResource(BaseResource):
    """Resource for check-in operations."""
    
    @engagement_endpoint
    def today_checkin(self, use_shield=False):
        """Perform today's check-in."""
        try:
            result = CheckInService.process(
                self.user,
                use_shield=use_shield,
                tenant=self.tenant
            )
            
            # Cache the result
            cache_key = self.get_cache_key('today_checkin', timezone.now().date())
            self.cache_set(cache_key, result, timeout=86400)
            
            return {
                'success': True,
                'data': result,
                'message': 'Check-in completed successfully'
            }
            
        except EngagementError as exc:
            return {
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }
    
    def get_streak_info(self):
        """Get current streak information."""
        try:
            cache_key = self.get_cache_key('streak_info')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            streak = CheckInService.get_current_streak(self.user)
            history = CheckInService.get_streak_history(self.user, days=30)
            
            result = {
                'current_streak': streak,
                'history': history,
                'longest_streak': CheckInService.get_longest_streak(self.user),
                'total_checkins': CheckInService.get_total_checkins(self.user)
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_calendar_data(self, year=None, month=None):
        """Get check-in calendar data."""
        try:
            if year is None:
                year = timezone.now().year
            if month is None:
                month = timezone.now().month
            
            cache_key = self.get_cache_key('calendar', year, month)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            start_date = date(year, month, 1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            calendar_data = CheckInService.get_calendar_data(
                self.user,
                start_date,
                end_date,
                tenant=self.tenant
            )
            
            result = {
                'year': year,
                'month': month,
                'calendar_data': calendar_data
            }
            
            self.cache_set(cache_key, result, timeout=3600)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class SpinWheelResource(BaseResource):
    """Resource for spin wheel operations."""
    
    @engagement_endpoint
    def spin(self, use_boost=False):
        """Perform a spin."""
        try:
            result = SpinService.spin(
                self.user,
                use_boost=use_boost,
                tenant=self.tenant
            )
            
            # Invalidate cache
            cache_key = self.get_cache_key('remaining_spins', timezone.now().date())
            self.cache_delete(cache_key)
            
            return {
                'success': True,
                'data': result,
                'message': 'Spin completed successfully'
            }
            
        except EngagementError as exc:
            return {
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }
    
    def get_remaining_spins(self):
        """Get remaining spins for today."""
        try:
            cache_key = self.get_cache_key('remaining_spins', timezone.now().date())
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            remaining = SpinService.get_remaining_spins(self.user)
            history = SpinService.get_spin_history(self.user, limit=10)
            
            result = {
                'remaining_spins': remaining,
                'max_spins_per_day': 10,  # From constants
                'recent_spins': history,
                'total_spins': SpinService.get_total_spins(self.user)
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_spin_history(self, limit=20):
        """Get spin history."""
        try:
            cache_key = self.get_cache_key('spin_history', limit)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            history = SpinService.get_spin_history(self.user, limit=limit)
            
            result = {
                'history': history,
                'total_spins': SpinService.get_total_spins(self.user),
                'total_coins_won': SpinService.get_total_coins_won(self.user)
            }
            
            self.cache_set(cache_key, result, timeout=600)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class QuestResource(BaseResource):
    """Resource for quest operations."""
    
    @engagement_endpoint
    def complete_quest(self, quest_id, progress=None):
        """Complete a quest."""
        try:
            from .models.quest import Quest
            
            quest = Quest.objects.get(id=quest_id)
            result = QuestService.complete_quest(
                self.user,
                quest,
                progress=progress,
                tenant=self.tenant
            )
            
            # Invalidate cache
            cache_key = self.get_cache_key('available_quests')
            self.cache_delete(cache_key)
            
            return {
                'success': True,
                'data': result,
                'message': 'Quest completed successfully'
            }
            
        except EngagementError as exc:
            return {
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }
    
    def get_available_quests(self, quest_type='daily'):
        """Get available quests."""
        try:
            cache_key = self.get_cache_key('available_quests', quest_type)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            quests = QuestService.get_available_quests(
                self.user,
                quest_type=quest_type,
                tenant=self.tenant
            )
            
            result = {
                'quests': quests,
                'quest_type': quest_type,
                'total_available': len(quests)
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_quest_progress(self):
        """Get quest progress summary."""
        try:
            cache_key = self.get_cache_key('quest_progress')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            progress = QuestService.get_progress_summary(self.user, tenant=self.tenant)
            
            result = {
                'progress': progress,
                'summary': {
                    'total_quests': progress.get('total', 0),
                    'completed_quests': progress.get('completed', 0),
                    'active_quests': progress.get('active', 0),
                    'completion_rate': progress.get('completion_rate', 0)
                }
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class AchievementResource(BaseResource):
    """Resource for achievement operations."""
    
    def get_unlocked_achievements(self):
        """Get unlocked achievements."""
        try:
            cache_key = self.get_cache_key('unlocked_achievements')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            achievements = AchievementService.get_unlocked_achievements(
                self.user,
                tenant=self.tenant
            )
            
            result = {
                'achievements': achievements,
                'total_unlocked': len(achievements)
            }
            
            self.cache_set(cache_key, result, timeout=600)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_achievement_progress(self, achievement_id):
        """Get progress for specific achievement."""
        try:
            from .models.achievement import Achievement
            
            achievement = Achievement.objects.get(id=achievement_id)
            progress = AchievementService.get_progress(
                self.user,
                achievement,
                tenant=self.tenant
            )
            
            return {
                'success': True,
                'data': progress
            }
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_achievement_stats(self):
        """Get achievement statistics."""
        try:
            cache_key = self.get_cache_key('achievement_stats')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            stats = AchievementService.get_stats(self.user, tenant=self.tenant)
            
            result = {
                'stats': stats,
                'summary': {
                    'total_achievements': stats.get('total', 0),
                    'unlocked_count': stats.get('unlocked', 0),
                    'locked_count': stats.get('locked', 0),
                    'unlock_rate': stats.get('unlock_rate', 0)
                }
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class ShopResource(BaseResource):
    """Resource for shop operations."""
    
    @engagement_endpoint
    def purchase_item(self, item_id, quantity=1):
        """Purchase an item."""
        try:
            from .models.shop import ShopItem
            
            item = ShopItem.objects.get(id=item_id)
            result = ShopService.purchase(
                self.user,
                item,
                quantity,
                tenant=self.tenant
            )
            
            # Invalidate cache
            cache_key = self.get_cache_key('inventory')
            self.cache_delete(cache_key)
            
            return {
                'success': True,
                'data': result,
                'message': 'Purchase completed successfully'
            }
            
        except EngagementError as exc:
            return {
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }
    
    def get_shop_items(self, item_type=None):
        """Get available shop items."""
        try:
            cache_key = self.get_cache_key('shop_items', item_type)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            items = ShopService.get_available_items(
                item_type=item_type,
                tenant=self.tenant
            )
            
            result = {
                'items': items,
                'total_items': len(items),
                'item_type': item_type
            }
            
            self.cache_set(cache_key, result, timeout=600)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_user_inventory(self):
        """Get user inventory."""
        try:
            cache_key = self.get_cache_key('inventory')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            inventory = ShopService.get_inventory(self.user, tenant=self.tenant)
            
            result = {
                'inventory': inventory,
                'total_items': len(inventory)
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_user_balance(self):
        """Get user coin balance."""
        try:
            cache_key = self.get_cache_key('balance')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            balance = ShopService.get_balance(self.user)
            
            result = {
                'balance': float(balance),
                'currency': 'coins'
            }
            
            self.cache_set(cache_key, result, timeout=60)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class LeaderboardResource(BaseResource):
    """Resource for leaderboard operations."""
    
    def get_top_players(self, period='daily', limit=100):
        """Get top players."""
        try:
            cache_key = self.get_cache_key('top_players', period, limit)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            leaderboard = LeaderboardService.get_top_players(
                period=period,
                limit=limit,
                tenant=self.tenant
            )
            
            result = {
                'leaderboard': leaderboard,
                'period': period,
                'total_players': len(leaderboard)
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_user_rank(self, period='daily'):
        """Get user's rank."""
        try:
            cache_key = self.get_cache_key('user_rank', period)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            rank = LeaderboardService.get_user_rank(
                self.user,
                period=period,
                tenant=self.tenant
            )
            
            result = {
                'rank': rank,
                'period': period
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_around_user(self, period='daily', count=5):
        """Get players around user's rank."""
        try:
            cache_key = self.get_cache_key('around_user', period, count)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            around_players = LeaderboardService.get_around_user(
                self.user,
                period=period,
                count=count,
                tenant=self.tenant
            )
            
            result = {
                'around_players': around_players,
                'period': period,
                'count': count
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class NotificationResource(BaseResource):
    """Resource for notification operations."""
    
    def get_notifications(self, unread_only=False, limit=20):
        """Get notifications."""
        try:
            cache_key = self.get_cache_key('notifications', unread_only, limit)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            notifications = NotificationService.get_notifications(
                self.user,
                unread_only=unread_only,
                limit=limit,
                tenant=self.tenant
            )
            
            result = {
                'notifications': notifications,
                'total_count': len(notifications),
                'unread_only': unread_only
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_unread_count(self):
        """Get unread notifications count."""
        try:
            cache_key = self.get_cache_key('unread_count')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            count = NotificationService.unread_count(self.user, tenant=self.tenant)
            
            result = {
                'unread_count': count
            }
            
            self.cache_set(cache_key, result, timeout=60)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    @engagement_endpoint
    def mark_as_read(self, notification_id):
        """Mark notification as read."""
        try:
            NotificationService.mark_as_read(
                self.user,
                notification_id,
                tenant=self.tenant
            )
            
            # Invalidate cache
            cache_key = self.get_cache_key('unread_count')
            self.cache_delete(cache_key)
            
            return {
                'success': True,
                'message': 'Notification marked as read'
            }
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    @engagement_endpoint
    def mark_all_as_read(self):
        """Mark all notifications as read."""
        try:
            NotificationService.mark_all_as_read(self.user, tenant=self.tenant)
            
            # Invalidate cache
            cache_key = self.get_cache_key('unread_count')
            self.cache_delete(cache_key)
            
            return {
                'success': True,
                'message': 'All notifications marked as read'
            }
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class UserProfileResource(BaseResource):
    """Resource for user profile data."""
    
    def get_profile(self):
        """Get complete user profile."""
        try:
            cache_key = self.get_cache_key('profile')
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Get user stats
            user_stats = AnalyticsService.get_user_stats(self.user, tenant=self.tenant)
            
            # Get recent activity
            recent_activity = self._get_recent_activity()
            
            # Get achievements
            achievements = AchievementService.get_unlocked_achievements(
                self.user,
                tenant=self.tenant,
                limit=5
            )
            
            # Get active quests
            active_quests = QuestService.get_available_quests(
                self.user,
                tenant=self.tenant,
                limit=5
            )
            
            result = {
                'user': {
                    'id': self.user.id,
                    'username': self.user.username,
                    'email': self.user.email,
                    'date_joined': self.user.date_joined.isoformat(),
                    'has_premium': getattr(self.user, 'has_premium', False),
                    'level': user_stats.get('level', 1),
                    'total_xp': user_stats.get('total_xp', 0),
                    'total_coins': user_stats.get('total_coins', 0)
                },
                'stats': user_stats,
                'achievements': achievements,
                'active_quests': active_quests,
                'recent_activity': recent_activity
            }
            
            self.cache_set(cache_key, result, timeout=300)
            return result
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }
    
    def _get_recent_activity(self, limit=10):
        """Get recent user activity."""
        try:
            # Get recent check-ins
            recent_checkins = CheckInService.get_recent_checkins(self.user, limit=5)
            
            # Get recent spins
            recent_spins = SpinService.get_spin_history(self.user, limit=5)
            
            # Get recent quest completions
            recent_quests = QuestService.get_recent_completions(self.user, limit=5)
            
            # Combine and sort by date
            activity = []
            
            for checkin in recent_checkins:
                activity.append({
                    'type': 'checkin',
                    'date': checkin.date.isoformat(),
                    'data': {
                        'coins_earned': float(checkin.coins_earned),
                        'xp_earned': checkin.xp_earned,
                        'streak': checkin.consecutive_days
                    }
                })
            
            for spin in recent_spins:
                activity.append({
                    'type': 'spin',
                    'date': spin.spun_at.isoformat(),
                    'data': {
                        'coins_won': float(spin.coins_won),
                        'xp_earned': spin.xp_earned,
                        'is_boosted': spin.is_boosted
                    }
                })
            
            # Sort by date and limit
            activity.sort(key=lambda x: x['date'], reverse=True)
            return activity[:limit]
            
        except Exception:
            return []


# ── Resource Registry ─────────────────────────────────────────────────────

class ResourceRegistry:
    """Registry for all engagement resources."""
    
    def __init__(self):
        self.resources = {}
        self._register_resources()
    
    def _register_resources(self):
        """Register all resources."""
        self.resources.update({
            'checkin': CheckInResource,
            'spin': SpinWheelResource,
            'quest': QuestResource,
            'achievement': AchievementResource,
            'shop': ShopResource,
            'leaderboard': LeaderboardResource,
            'notification': NotificationResource,
            'profile': UserProfileResource,
        })
    
    def get_resource(self, resource_name):
        """Get resource by name."""
        resource_class = self.resources.get(resource_name)
        if resource_class:
            return resource_class
        raise ValueError(f"Unknown resource: {resource_name}")
    
    def list_resources(self):
        """List all available resources."""
        return list(self.resources.keys())


# Global resource registry instance
resource_registry = ResourceRegistry()


# ── Resource Utility Functions ─────────────────────────────────────────────

def get_resource(resource_name, request=None, user=None):
    """Get resource instance."""
    resource_class = resource_registry.get_resource(resource_name)
    return resource_class(request=request, user=user)


def format_response(success=True, data=None, message=None, error=None, code=None):
    """Format API response."""
    response = {'success': success}
    
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    if error:
        response['error'] = error
    if code:
        response['code'] = code
    
    return response


def format_error_response(error, code=None, status_code=400):
    """Format error response."""
    return format_response(
        success=False,
        error=str(error),
        code=code or 'ERROR'
    ), status_code


def format_paginated_response(data, page=1, page_size=20, total_count=None):
    """Format paginated response."""
    if total_count is None:
        total_count = len(data)
    
    total_pages = (total_count + page_size - 1) // page_size
    has_next = page < total_pages
    has_previous = page > 1
    
    pagination = {
        'page': page,
        'page_size': page_size,
        'total_count': total_count,
        'total_pages': total_pages,
        'has_next': has_next,
        'has_previous': has_previous
    }
    
    return format_response(
        success=True,
        data=data,
        pagination=pagination
    )


# ── Resource Decorators ─────────────────────────────────────────────────────

def resource_method(method_name):
    """Decorator to register resource methods."""
    def decorator(func):
        func.resource_method = True
        func.method_name = method_name
        return func
    return decorator


def cached_resource(timeout=300):
    """Decorator to cache resource responses."""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            cache_key = self.get_cache_key(func.__name__, *args)
            cached_result = self.cache_get(cache_key)
            
            if cached_result:
                return cached_result
            
            result = func(self, *args, **kwargs)
            self.cache_set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator


def validate_resource_data(serializer_class):
    """Decorator to validate resource data."""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if hasattr(self, 'request') and self.request:
                serializer = serializer_class(data=self.request.data)
                if not serializer.is_valid():
                    return format_error_response(
                        error='Validation failed',
                        code='VALIDATION_ERROR',
                        status_code=400
                    )
                
                self.validated_data = serializer.validated_data
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
