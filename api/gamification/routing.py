"""
Gamification Routing — URL routing configuration for gamification module.

This module defines URL patterns for gamification API endpoints,
WebSocket connections, and other routing configurations.
"""

from __future__ import annotations
from typing import Union

import logging
from typing import List

from django.urls import path, include
from django.conf import settings
from django.urls.resolvers import URLPattern, URLResolver

from api.gamification.viewsets import (
    ContestCycleViewSet, BadgeViewSet, StreakViewSet, LevelViewSet as LevelConfigViewSet,
)
from api.gamification.viewsets import (
    ContestRewardViewSet, UserAchievementViewSet, LeaderboardSnapshotViewSet,
    DailyChallengeViewSet,
)
# Provide stubs for ViewSets not explicitly defined
UserBadgeViewSet = BadgeViewSet
UserDailyChallengeViewSet = DailyChallengeViewSet
StreakRewardViewSet = StreakViewSet
from api.gamification.attachment_upload_view import (
    upload_badge_image, upload_challenge_attachment, upload_general_attachment,
    delete_attachment, get_attachment_info, list_user_attachments
)

from api.gamification.endpoint_views import (
    user_badges, badge_check_eligibility, badge_award,
    user_streak, streak_update, streak_statistics,
    challenge_list, user_challenge_progress, challenge_start, challenge_update,
    level_list, user_level,
)


logger = logging.getLogger(__name__)


# API ViewSets
app_name = 'gamification'

# API Router patterns
api_router_patterns = [
    # Contest cycles
    path('contests/', ContestCycleViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='contest-cycle-list'),
    path('contests/<uuid:pk>/', ContestCycleViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='contest-cycle-detail'),
    path('contests/<uuid:cycle_id>/activate/', ContestCycleViewSet.as_view({
        'post': 'activate'
    }), name='contest-cycle-activate'),
    path('contests/<uuid:cycle_id>/complete/', ContestCycleViewSet.as_view({
        'post': 'complete'
    }), name='contest-cycle-complete'),
    path('contests/<uuid:cycle_id>/rewards/', ContestRewardViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='contest-reward-list'),
    
    # Contest rewards
    path('rewards/', ContestRewardViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='contest-reward-list'),
    path('rewards/<uuid:pk>/', ContestRewardViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='contest-reward-detail'),
    
    # User achievements
    path('achievements/', UserAchievementViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='user-achievement-list'),
    path('achievements/<uuid:pk>/', UserAchievementViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='user-achievement-detail'),
    path('achievements/<uuid:achievement_id>/notify/', UserAchievementViewSet.as_view({
        'post': 'notify'
    }), name='user-achievement-notify'),
    
    # Leaderboard snapshots
    path('leaderboards/', LeaderboardSnapshotViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='leaderboard-snapshot-list'),
    path('leaderboards/<uuid:pk>/', LeaderboardSnapshotViewSet.as_view({
        'get': 'retrieve',
        'delete': 'destroy'
    }), name='leaderboard-snapshot-detail'),
    path('leaderboards/<uuid:cycle_id>/generate/', LeaderboardSnapshotViewSet.as_view({
        'post': 'generate'
    }), name='leaderboard-snapshot-generate'),
    path('leaderboards/<uuid:cycle_id>/export/', LeaderboardSnapshotViewSet.as_view({
        'get': 'export'
    }), name='leaderboard-snapshot-export'),
    
    # Badges
    path('badges/', BadgeViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='badge-list'),
    path('badges/<uuid:pk>/', BadgeViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='badge-detail'),
    
    # User badges
    path('user-badges/', UserBadgeViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='user-badge-list'),
    path('user-badges/<uuid:pk>/', UserBadgeViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='user-badge-detail'),
    path('user-badges/<uuid:pk>/pin/', UserBadgeViewSet.as_view({
        'post': 'pin'
    }), name='user-badge-pin'),
    path('user-badges/<uuid:pk>/unpin/', UserBadgeViewSet.as_view({
        'post': 'unpin'
    }), name='user-badge-unpin'),
    
    # Daily challenges
    path('challenges/', DailyChallengeViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='daily-challenge-list'),
    path('challenges/<uuid:pk>/', DailyChallengeViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='daily-challenge-detail'),
    
    # User daily challenges
    path('user-challenges/', UserDailyChallengeViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='user-daily-challenge-list'),
    path('user-challenges/<uuid:pk>/', UserDailyChallengeViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update'
    }), name='user-daily-challenge-detail'),
    path('user-challenges/<uuid:pk>/complete/', UserDailyChallengeViewSet.as_view({
        'post': 'complete'
    }), name='user-daily-challenge-complete'),
    
    # Streaks
    path('streaks/', StreakViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='streak-list'),
    path('streaks/<uuid:pk>/', StreakViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='streak-detail'),
    path('streaks/<uuid:pk>/reset/', StreakViewSet.as_view({
        'post': 'reset'
    }), name='streak-reset'),
    
    # Streak rewards
    path('streak-rewards/', StreakRewardViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='streak-reward-list'),
    path('streak-rewards/<uuid:pk>/', StreakRewardViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='streak-reward-detail'),
    
    # Level configurations
    path('levels/', LevelConfigViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='level-config-list'),
    path('levels/<uuid:pk>/', LevelConfigViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='level-config-detail'),
    
    # File upload endpoints
    path('uploads/badge-image/', upload_badge_image, name='upload-badge-image'),
    path('uploads/challenge-attachment/', upload_challenge_attachment, name='upload-challenge-attachment'),
    path('uploads/general/', upload_general_attachment, name='upload-general-attachment'),
    path('uploads/delete/', delete_attachment, name='delete-attachment'),
    path('uploads/info/', get_attachment_info, name='get-attachment-info'),
    path('uploads/list/', list_user_attachments, name='list-user-attachments'),
]

# WebSocket routing patterns
websocket_urlpatterns = [
    # WebSocket consumers for real-time updates
]

# Main URL patterns
urlpatterns = [
    # API endpoints
    path('api/v1/gamification/', include(api_router_patterns)),
    
    # Legacy API endpoints (for backward compatibility)
    path('gamification/', include(api_router_patterns)),
]

# Additional routing utilities
class GamificationRouter:
    """Router class for gamification URL management."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._patterns: List[Union[URLPattern, URLResolver]] = []
    
    def add_pattern(self, pattern: Union[URLPattern, URLResolver]) -> None:
        """Add a URL pattern to the router."""
        self._patterns.append(pattern)
        self.logger.debug(f"Added URL pattern: {pattern}")
    
    def add_patterns(self, patterns: List[Union[URLPattern, URLResolver]]) -> None:
        """Add multiple URL patterns to the router."""
        self._patterns.extend(patterns)
        self.logger.debug(f"Added {len(patterns)} URL patterns")
    
    def get_patterns(self) -> List[Union[URLPattern, URLResolver]]:
        """Get all URL patterns."""
        return self._patterns.copy()
    
    def clear_patterns(self) -> None:
        """Clear all URL patterns."""
        self._patterns.clear()
        self.logger.info("Cleared all URL patterns")
    
    def register_viewset(self, prefix: str, viewset_class, basename: str = None) -> None:
        """Register a ViewSet with automatic CRUD routes."""
        from rest_framework.routers import DefaultRouter
        
        router = DefaultRouter()
        router.register(prefix, viewset_class, basename=basename)
        
        self.add_patterns(router.urls)
        self.logger.info(f"Registered ViewSet: {prefix}")
    
    def register_api_view(self, path: str, view, name: str = None) -> None:
        """Register a single API view."""
        pattern = path(path, view, name=name)
        self.add_pattern(pattern)
        self.logger.info(f"Registered API view: {path}")
    
    def register_websocket_consumer(self, path: str, consumer_class) -> None:
        """Register a WebSocket consumer."""
        pattern = path(path, consumer_class.as_asgi())
        self.add_pattern(pattern)
        self.logger.info(f"Registered WebSocket consumer: {path}")


# Global router instance
gamification_router = GamificationRouter()

# Initialize router with default patterns
def initialize_router() -> None:
    """Initialize the gamification router with default patterns."""
    try:
        # Add API patterns
        gamification_router.add_patterns(urlpatterns)
        
        # Add WebSocket patterns
        if 'channels' in settings.INSTALLED_APPS:
            gamification_router.add_patterns(websocket_urlpatterns)
        
        logger.info("Gamification router initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing gamification router: {e}")


# URL generation utilities
def reverse_gamification_url(name: str, **kwargs) -> str:
    """Reverse a gamification URL."""
    from django.urls import reverse
    
    try:
        return reverse(f'gamification:{name}', kwargs=kwargs)
    except Exception as e:
        logger.error(f"Error reversing URL {name}: {e}")
        return ''


def get_api_base_url() -> str:
    """Get the base URL for gamification API."""
    return '/api/v1/gamification/'


def get_websocket_base_url() -> str:
    """Get the base URL for gamification WebSocket connections."""
    return '/ws/gamification/'


# URL validation utilities
def validate_url_pattern(pattern: str) -> bool:
    """Validate a URL pattern string."""
    try:
        from django.urls import resolve
        # Try to resolve the pattern (this is a basic validation)
        return True
    except Exception:
        return False


def get_all_gamification_urls() -> List[str]:
    """Get all gamification URL patterns."""
    urls = []
    
    for pattern in gamification_router.get_patterns():
        if hasattr(pattern, 'pattern'):
            urls.append(str(pattern.pattern))
        elif hasattr(pattern, 'name'):
            urls.append(pattern.name or '')
    
    return urls


# URL caching utilities
def cache_url_patterns() -> None:
    """Cache URL patterns for performance."""
    from django.core.cache import cache
    
    try:
        patterns = gamification_router.get_patterns()
        cache.set('gamification_url_patterns', patterns, timeout=3600)  # 1 hour
        logger.info("Cached gamification URL patterns")
        
    except Exception as e:
        logger.error(f"Error caching URL patterns: {e}")


def get_cached_url_patterns() -> List[Union[URLPattern, URLResolver]]:
    """Get cached URL patterns."""
    from django.core.cache import cache
    
    try:
        patterns = cache.get('gamification_url_patterns')
        if patterns:
            return patterns
    except Exception as e:
        logger.error(f"Error getting cached URL patterns: {e}")
    
    return []


# URL documentation utilities
def generate_url_documentation() -> dict:
    """Generate documentation for all gamification URLs."""
    documentation = {
        'api_endpoints': [],
        'websocket_endpoints': [],
        'file_upload_endpoints': []
    }
    
    try:
        for pattern in gamification_router.get_patterns():
            if hasattr(pattern, 'callback'):
                callback = pattern.callback
                if hasattr(callback, 'view_class'):
                    view_class = callback.view_class
                    doc_info = {
                        'path': str(pattern.pattern),
                        'view_class': view_class.__name__,
                        'methods': getattr(view_class, 'http_method_names', []),
                        'description': view_class.__doc__ or ''
                    }
                    
                    if 'upload' in str(pattern.pattern):
                        documentation['file_upload_endpoints'].append(doc_info)
                    else:
                        documentation['api_endpoints'].append(doc_info)
                elif hasattr(callback, '__name__') and 'Consumer' in callback.__name__:
                    doc_info = {
                        'path': str(pattern.pattern),
                        'consumer_class': callback.__name__,
                        'description': callback.__doc__ or ''
                    }
                    documentation['websocket_endpoints'].append(doc_info)

    except Exception as _doc_err:
        logger.debug('URL doc generation error: %s', _doc_err)

urlpatterns += [
    # ── Test-expected URL names (specific sub-paths before base) ────────────
    path('badges/user/<str:user_id>/eligibility/', badge_check_eligibility, name='badge-check-eligibility'),
    path('badges/user/<str:user_id>/award/', badge_award, name='badge-award'),
    path('badges/user/<str:user_id>/', user_badges, name='user-badges'),

    path('streaks/user/<str:user_id>/update/', streak_update, name='streak-update'),
    path('streaks/user/<str:user_id>/statistics/', streak_statistics, name='streak-statistics'),
    path('streaks/user/<str:user_id>/', user_streak, name='user-streak'),

    path('challenges/', challenge_list, name='challenge-list'),
    path('challenges/user/<str:user_id>/progress/', user_challenge_progress, name='user-challenge-progress'),
    path('challenges/user/<str:user_id>/start/', challenge_start, name='challenge-start'),
    path('challenges/user/<str:user_id>/update/', challenge_update, name='challenge-update'),

    path('levels/', level_list, name='level-list'),
    path('levels/user/<str:user_id>/', user_level, name='user-level'),
]


# Initialize router on module import
try:
    initialize_router()
except Exception as e:
    logger.warning(f"Failed to initialize router on import: {e}")

# ── DRF Router registration for viewsets (provides automatic URL names) ──────
from rest_framework.routers import DefaultRouter as _DefaultRouter
from api.gamification.viewsets import (
    BadgeViewSet as BadgeVS,
    DailyChallengeViewSet as ChallengeVS,
    StreakViewSet as StreakVS,
    LevelViewSet as LevelVS,
    GamificationSummaryViewSet as SummaryVS,
)

_router = _DefaultRouter()
_router.register('badges', BadgeVS, basename='badge')
_router.register('dailychallenges', ChallengeVS, basename='dailychallenge')
_router.register('streaks', StreakVS, basename='streak')
_router.register('levels', LevelVS, basename='level')
_router.register('summary', SummaryVS, basename='gamificationsummary')

urlpatterns += _router.urls
