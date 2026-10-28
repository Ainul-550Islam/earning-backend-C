"""
Gamification Caching — Comprehensive cache management for gamification system.

This module provides advanced caching capabilities for the gamification system,
including multi-level caching, cache invalidation strategies, and performance
optimization.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ContestCycleStatus, AchievementType
)
from api.gamification.exceptions import GamificationServiceError

logger = logging.getLogger(__name__)


class CacheKey:
    """Utility class for generating cache keys."""
    
    @staticmethod
    def generate(prefix: str, *args, **kwargs) -> str:
        """Generate a cache key with prefix and arguments."""
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (str, int, float, bool)):
                key_parts.append(str(arg))
            else:
                # Hash complex objects
                key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
        
        # Add keyword arguments (sorted for consistency)
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            if isinstance(value, (str, int, float, bool)):
                key_parts.append(f"{key}:{value}")
            else:
                key_parts.append(f"{key}:{hashlib.md5(str(value).encode()).hexdigest()[:8]}")
        
        return ":".join(key_parts)
    
    @staticmethod
    def user_key(user_id: str, suffix: str = "") -> str:
        """Generate user-specific cache key."""
        parts = ["user", user_id]
        if suffix:
            parts.append(suffix)
        return ":".join(parts)
    
    @staticmethod
    def badge_key(badge_id: str, suffix: str = "") -> str:
        """Generate badge-specific cache key."""
        parts = ["badge", badge_id]
        if suffix:
            parts.append(suffix)
        return ":".join(parts)
    
    @staticmethod
    def challenge_key(challenge_id: str, suffix: str = "") -> str:
        """Generate challenge-specific cache key."""
        parts = ["challenge", challenge_id]
        if suffix:
            parts.append(suffix)
        return ":".join(parts)
    
    @staticmethod
    def streak_key(user_id: str, suffix: str = "") -> str:
        """Generate streak-specific cache key."""
        parts = ["streak", user_id]
        if suffix:
            parts.append(suffix)
        return ":".join(parts)
    
    @staticmethod
    def leaderboard_key(scope: str, suffix: str = "") -> str:
        """Generate leaderboard-specific cache key."""
        parts = ["leaderboard", scope]
        if suffix:
            parts.append(suffix)
        return ":".join(parts)
    
    @staticmethod
    def stats_key(entity_type: str, entity_id: str, suffix: str = "") -> str:
        """Generate statistics-specific cache key."""
        parts = ["stats", entity_type, entity_id]
        if suffix:
            parts.append(suffix)
        return ":".join(parts)


class CacheManager:
    """Advanced cache manager for gamification system."""
    
    def __init_(self):
        self.logger = logging.getLogger(__name__)
        self.default_timeout = getattr(settings, 'GAMIFICATION_CACHE_TIMEOUT', 300)  # 5 minutes
        self.long_timeout = getattr(settings, 'GAMIFICATION_CACHE_LONG_TIMEOUT', 3600)  # 1 hour
        self.short_timeout = getattr(settings, 'GAMIFICATION_CACHE_SHORT_TIMEOUT', 60)  # 1 minute
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        try:
            return cache.get(key, default)
        except Exception as e:
            self.logger.error(f"Error getting cache key {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            timeout = timeout or self.default_timeout
            return cache.set(key, value, timeout)
        except Exception as e:
            self.logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            return cache.delete(key)
        except Exception as e:
            self.logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        try:
            return cache.get_many(keys)
        except Exception as e:
            self.logger.error(f"Error getting multiple cache keys: {e}")
            return {}
    
    def set_many(self, mapping: Dict[str, Any], timeout: Optional[int] = None) -> bool:
        """Set multiple values in cache."""
        try:
            timeout = timeout or self.default_timeout
            return cache.set_many(mapping, timeout)
        except Exception as e:
            self.logger.error(f"Error setting multiple cache keys: {e}")
            return False
    
    def delete_many(self, keys: List[str]) -> int:
        """Delete multiple values from cache."""
        try:
            return cache.delete_many(keys)
        except Exception as e:
            self.logger.error(f"Error deleting multiple cache keys: {e}")
            return 0
    
    def clear(self) -> bool:
        """Clear all cache."""
        try:
            return cache.clear()
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return False
    
    def incr(self, key: str, delta: int = 1) -> Optional[int]:
        """Increment cache value."""
        try:
            return cache.incr(key, delta)
        except Exception as e:
            self.logger.error(f"Error incrementing cache key {key}: {e}")
            return None
    
    def decr(self, key: str, delta: int = 1) -> Optional[int]:
        """Decrement cache value."""
        try:
            return cache.decr(key, delta)
        except Exception as e:
            self.logger.error(f"Error decrementing cache key {key}: {e}")
            return None
    
    def touch(self, key: str, timeout: Optional[int] = None) -> bool:
        """Update cache expiration."""
        try:
            timeout = timeout or self.default_timeout
            return cache.touch(key, timeout)
        except Exception as e:
            self.logger.error(f"Error touching cache key {key}: {e}")
            return False
    
    def add(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Add value to cache only if key doesn't exist."""
        try:
            timeout = timeout or self.default_timeout
            return cache.add(key, value, timeout)
        except Exception as e:
            self.logger.error(f"Error adding cache key {key}: {e}")
            return False
    
    def get_or_set(self, key: str, default_func, timeout: Optional[int] = None) -> Any:
        """Get value from cache or set using default function."""
        try:
            timeout = timeout or self.default_timeout
            return cache.get_or_set(key, default_func, timeout)
        except Exception as e:
            self.logger.error(f"Error getting or setting cache key {key}: {e}")
            return default_func()


class GamificationCacheManager(CacheManager):
    """Specialized cache manager for gamification system."""
    
    def __init_(self):
        super().__init_()
        self.cache_versions = {}  # For cache invalidation
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def get_user_badge_summary(self, user_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get user badge summary from cache."""
        key = CacheKey.user_key(user_id, "badge_summary")
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_user_badge_summary(self, user_id: str, summary: Dict[str, Any]) -> bool:
        """Set user badge summary in cache."""
        key = CacheKey.user_key(user_id, "badge_summary")
        result = self.set(key, summary, self.short_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_user_streak_info(self, user_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get user streak info from cache."""
        key = CacheKey.streak_key(user_id, "info")
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_user_streak_info(self, user_id: str, streak_info: Dict[str, Any]) -> bool:
        """Set user streak info in cache."""
        key = CacheKey.streak_key(user_id, "info")
        result = self.set(key, streak_info, self.short_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_user_challenge_progress(self, user_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get user challenge progress from cache."""
        key = CacheKey.user_key(user_id, "challenge_progress")
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_user_challenge_progress(self, user_id: str, progress: Dict[str, Any]) -> bool:
        """Set user challenge progress in cache."""
        key = CacheKey.user_key(user_id, "challenge_progress")
        result = self.set(key, progress, self.short_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_user_level_info(self, user_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get user level info from cache."""
        key = CacheKey.user_key(user_id, "level_info")
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_user_level_info(self, user_id: str, level_info: Dict[str, Any]) -> bool:
        """Set user level info in cache."""
        key = CacheKey.user_key(user_id, "level_info")
        result = self.set(key, level_info, self.long_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_user_gamification_stats(self, user_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get comprehensive user gamification stats from cache."""
        key = CacheKey.user_key(user_id, "stats")
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_user_gamification_stats(self, user_id: str, stats: Dict[str, Any]) -> bool:
        """Set comprehensive user gamification stats in cache."""
        key = CacheKey.user_key(user_id, "stats")
        result = self.set(key, stats, self.short_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_leaderboard(self, scope: str, limit: int = 100, force_refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Get leaderboard from cache."""
        key = CacheKey.leaderboard_key(scope, f"limit_{limit}")
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_leaderboard(self, scope: str, leaderboard: List[Dict[str, Any]], limit: int = 100) -> bool:
        """Set leaderboard in cache."""
        key = CacheKey.leaderboard_key(scope, f"limit_{limit}")
        result = self.set(key, leaderboard, self.short_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_badge_eligibility(self, user_id: str, force_refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Get badge eligibility from cache."""
        key = CacheKey.user_key(user_id, "badge_eligibility")
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_badge_eligibility(self, user_id: str, eligibility: List[Dict[str, Any]]) -> bool:
        """Set badge eligibility in cache."""
        key = CacheKey.user_key(user_id, "badge_eligibility")
        result = self.set(key, eligibility, self.short_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_contest_results(self, contest_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get contest results from cache."""
        key = CacheKey.generate("contest_results", contest_id)
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_contest_results(self, contest_id: str, results: Dict[str, Any]) -> bool:
        """Set contest results in cache."""
        key = CacheKey.generate("contest_results", contest_id)
        result = self.set(key, results, self.long_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def get_system_stats(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get system statistics from cache."""
        key = "system_stats"
        
        if force_refresh:
            self.delete(key)
            return None
        
        result = self.get(key)
        if result is not None:
            self.cache_stats['hits'] += 1
        else:
            self.cache_stats['misses'] += 1
        
        return result
    
    def set_system_stats(self, stats: Dict[str, Any]) -> bool:
        """Set system statistics in cache."""
        key = "system_stats"
        result = self.set(key, stats, self.short_timeout)
        
        if result:
            self.cache_stats['sets'] += 1
        
        return result
    
    def invalidate_user_cache(self, user_id: str) -> int:
        """Invalidate all cache entries for a user."""
        patterns = [
            f"user:{user_id}:*",
            f"streak:{user_id}:*",
            f"stats:user:{user_id}:*"
        ]
        
        deleted_count = 0
        for pattern in patterns:
            try:
                # Get all matching keys
                matching_keys = []
                # This is a simplified approach - in production, you'd use cache.keys()
                # which may not be available in all cache backends
                for key in self.cache_stats.keys():
                    if pattern.replace("*", "") in key:
                        matching_keys.append(key)
                
                if matching_keys:
                    deleted = self.delete_many(matching_keys)
                    deleted_count += deleted
                    
            except Exception as e:
                self.logger.error(f"Error invalidating user cache pattern {pattern}: {e}")
        
        self.cache_stats['deletes'] += deleted_count
        return deleted_count
    
    def invalidate_badge_cache(self, badge_id: str) -> int:
        """Invalidate all cache entries related to a badge."""
        patterns = [
            f"badge:{badge_id}:*",
            f"*:badge_eligibility:*"  # All user eligibility caches
        ]
        
        deleted_count = 0
        for pattern in patterns:
            try:
                matching_keys = []
                for key in self.cache_stats.keys():
                    if pattern.replace("*", "") in key:
                        matching_keys.append(key)
                
                if matching_keys:
                    deleted = self.delete_many(matching_keys)
                    deleted_count += deleted
                    
            except Exception as e:
                self.logger.error(f"Error invalidating badge cache pattern {pattern}: {e}")
        
        self.cache_stats['deletes'] += deleted_count
        return deleted_count
    
    def invalidate_challenge_cache(self, challenge_id: str) -> int:
        """Invalidate all cache entries related to a challenge."""
        patterns = [
            f"challenge:{challenge_id}:*",
            f"user:*:challenge_progress:*"  # All user challenge progress caches
        ]
        
        deleted_count = 0
        for pattern in patterns:
            try:
                matching_keys = []
                for key in self.cache_stats.keys():
                    if pattern.replace("*", "") in key:
                        matching_keys.append(key)
                
                if matching_keys:
                    deleted = self.delete_many(matching_keys)
                    deleted_count += deleted
                    
            except Exception as e:
                self.logger.error(f"Error invalidating challenge cache pattern {pattern}: {e}")
        
        self.cache_stats['deletes'] += deleted_count
        return deleted_count
    
    def invalidate_streak_cache(self, user_id: str) -> int:
        """Invalidate streak cache entries for a user."""
        patterns = [
            f"streak:{user_id}:*",
            f"user:{user_id}:*"  # All user caches including stats
        ]
        
        deleted_count = 0
        for pattern in patterns:
            try:
                matching_keys = []
                for key in self.cache_stats.keys():
                    if pattern.replace("*", "") in key:
                        matching_keys.append(key)
                
                if matching_keys:
                    deleted = self.delete_many(matching_keys)
                    deleted_count += deleted
                    
            except Exception as e:
                self.logger.error(f"Error invalidating streak cache pattern {pattern}: {e}")
        
        self.cache_stats['deletes'] += deleted_count
        return deleted_count
    
    def invalidate_leaderboard_cache(self, scope: str) -> int:
        """Invalidate leaderboard cache entries."""
        patterns = [
            f"leaderboard:{scope}:*"
        ]
        
        deleted_count = 0
        for pattern in patterns:
            try:
                matching_keys = []
                for key in self.cache_stats.keys():
                    if pattern.replace("*", "") in key:
                        matching_keys.append(key)
                
                if matching_keys:
                    deleted = self.delete_many(matching_keys)
                    deleted_count += deleted
                    
            except Exception as e:
                self.logger.error(f"Error invalidating leaderboard cache pattern {pattern}: {e}")
        
        self.cache_stats['deletes'] += deleted_count
        return deleted_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_operations = sum(self.cache_stats.values())
        
        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'sets': self.cache_stats['sets'],
            'deletes': self.cache_stats['deletes'],
            'total_operations': total_operations,
            'hit_rate': (self.cache_stats['hits'] / max(1, self.cache_stats['hits'] + self.cache_stats['misses'])) * 100,
            'generated_at': timezone.now().isoformat()
        }
    
    def reset_cache_stats(self) -> None:
        """Reset cache statistics."""
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }


class CacheWarmer:
    """Cache warmer for preloading frequently accessed data."""
    
    def __init__(self, cache_manager: GamificationCacheManager):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
    
    def warm_user_cache(self, user_id: str) -> Dict[str, bool]:
        """Warm cache for a specific user."""
        results = {}
        
        try:
            # Warm user badge summary
            from api.gamification.helpers import BadgeHelper
            badge_summary = BadgeHelper.get_user_badge_summary(user_id)
            results['badge_summary'] = self.cache_manager.set_user_badge_summary(user_id, badge_summary)
            
            # Warm user streak info
            from api.gamification.helpers import StreakHelper
            streak_info = StreakHelper.get_streak_info(user_id)
            results['streak_info'] = self.cache_manager.set_user_streak_info(user_id, streak_info)
            
            # Warm user challenge progress
            from api.gamification.helpers import ChallengeHelper
            challenge_progress = ChallengeHelper.get_user_challenge_stats(user_id)
            results['challenge_progress'] = self.cache_manager.set_user_challenge_progress(user_id, challenge_progress)
            
            # Warm user level info
            from api.gamification.helpers import LevelHelper
            level_info = LevelHelper.get_user_level_info(user_id)
            results['level_info'] = self.cache_manager.set_user_level_info(user_id, level_info)
            
            # Warm user gamification stats
            from api.gamification.helpers import UserHelper
            user_stats = UserHelper.get_user_gamification_stats(user_id)
            results['gamification_stats'] = self.cache_manager.set_user_gamification_stats(user_id, user_stats)
            
            self.logger.info(f"Warmed cache for user {user_id}: {sum(results.values())}/{len(results)} items cached")
            
        except Exception as e:
            self.logger.error(f"Error warming cache for user {user_id}: {e}")
        
        return results
    
    def warm_leaderboard_cache(self, scope: str = "global", limit: int = 100) -> bool:
        """Warm leaderboard cache."""
        try:
            from api.gamification.helpers import LeaderboardHelper
            leaderboard = LeaderboardHelper.get_leaderboard(scope, limit)
            
            result = self.cache_manager.set_leaderboard(scope, leaderboard, limit)
            
            self.logger.info(f"Warmed leaderboard cache for scope {scope}: {result}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error warming leaderboard cache for scope {scope}: {e}")
            return False
    
    def warm_system_cache(self) -> Dict[str, bool]:
        """Warm system-level cache."""
        results = {}
        
        try:
            # Warm system stats
            from api.gamification.helpers import SystemHelper
            system_stats = SystemHelper.get_system_stats()
            results['system_stats'] = self.cache_manager.set_system_stats(system_stats)
            
            # Warm leaderboards
            results['global_leaderboard'] = self.warm_leaderboard_cache("global", 100)
            results['weekly_leaderboard'] = self.warm_leaderboard_cache("weekly", 50)
            
            self.logger.info(f"Warmed system cache: {sum(results.values())}/{len(results)} items cached")
            
        except Exception as e:
            self.logger.error(f"Error warming system cache: {e}")
        
        return results
    
    def warm_popular_user_caches(self, limit: int = 100) -> Dict[str, int]:
        """Warm caches for most active users."""
        results = {}
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get most recently active users
            active_users = User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=7)
            ).order_by('-last_login')[:limit]
            
            successful_warms = 0
            for user in active_users:
                user_results = self.warm_user_cache(str(user.id))
                if any(user_results.values()):
                    successful_warms += 1
            
            results['users_processed'] = len(active_users)
            results['successful_warms'] = successful_warms
            
            self.logger.info(f"Warmed caches for {successful_warms}/{len(active_users)} active users")
            
        except Exception as e:
            self.logger.error(f"Error warming popular user caches: {e}")
        
        return results


class CacheInvalidator:
    """Cache invalidation manager."""
    
    def __init__(self, cache_manager: GamificationCacheManager):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
    
    def invalidate_on_badge_award(self, user_id: str, badge_id: str) -> int:
        """Invalidate cache when user earns a badge."""
        deleted_count = 0
        
        # Invalidate user-specific caches
        deleted_count += self.cache_manager.invalidate_user_cache(user_id)
        
        # Invalidate badge-specific caches
        deleted_count += self.cache_manager.invalidate_badge_cache(badge_id)
        
        # Invalidate leaderboards (user ranking may change)
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("global")
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("weekly")
        
        # Invalidate system stats
        system_stats_key = "system_stats"
        self.cache_manager.delete(system_stats_key)
        deleted_count += 1
        
        self.logger.info(f"Invalidated {deleted_count} cache entries for badge award (user: {user_id}, badge: {badge_id})")
        
        return deleted_count
    
    def invalidate_on_streak_update(self, user_id: str) -> int:
        """Invalidate cache when user's streak is updated."""
        deleted_count = 0
        
        # Invalidate user-specific caches
        deleted_count += self.cache_manager.invalidate_user_cache(user_id)
        
        # Invalidate streak-specific caches
        deleted_count += self.cache_manager.invalidate_streak_cache(user_id)
        
        # Invalidate leaderboards (streak may affect ranking)
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("streak")
        
        self.logger.info(f"Invalidated {deleted_count} cache entries for streak update (user: {user_id})")
        
        return deleted_count
    
    def invalidate_on_challenge_completion(self, user_id: str, challenge_id: str) -> int:
        """Invalidate cache when user completes a challenge."""
        deleted_count = 0
        
        # Invalidate user-specific caches
        deleted_count += self.cache_manager.invalidate_user_cache(user_id)
        
        # Invalidate challenge-specific caches
        deleted_count += self.cache_manager.invalidate_challenge_cache(challenge_id)
        
        # Invalidate leaderboards (points may affect ranking)
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("global")
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("weekly")
        
        self.logger.info(f"Invalidated {deleted_count} cache entries for challenge completion (user: {user_id}, challenge: {challenge_id})")
        
        return deleted_count
    
    def invalidate_on_level_up(self, user_id: str) -> int:
        """Invalidate cache when user levels up."""
        deleted_count = 0
        
        # Invalidate user-specific caches
        deleted_count += self.cache_manager.invalidate_user_cache(user_id)
        
        # Invalidate level distribution stats
        level_stats_key = CacheKey.stats_key("level_distribution", "all")
        self.cache_manager.delete(level_stats_key)
        deleted_count += 1
        
        # Invalidate leaderboards (level may affect ranking)
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("global")
        
        self.logger.info(f"Invalidated {deleted_count} cache entries for level up (user: {user_id})")
        
        return deleted_count
    
    def invalidate_on_contest_end(self, contest_id: str) -> int:
        """Invalidate cache when contest ends."""
        deleted_count = 0
        
        # Invalidate contest-specific caches
        contest_results_key = CacheKey.generate("contest_results", contest_id)
        self.cache_manager.delete(contest_results_key)
        deleted_count += 1
        
        # Invalidate leaderboards
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("global")
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("weekly")
        deleted_count += self.cache_manager.invalidate_leaderboard_cache("contest")
        
        # Invalidate system stats
        system_stats_key = "system_stats"
        self.cache_manager.delete(system_stats_key)
        deleted_count += 1
        
        self.logger.info(f"Invalidated {deleted_count} cache entries for contest end (contest: {contest_id})")
        
        return deleted_count


# Global instances
gamification_cache = GamificationCacheManager()
cache_warmer = CacheWarmer(gamification_cache)
cache_invalidator = CacheInvalidator(gamification_cache)


# Convenience functions
def get_user_cached_badge_summary(user_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Get user badge summary from cache."""
    return gamification_cache.get_user_badge_summary(user_id, force_refresh)


def set_user_cached_badge_summary(user_id: str, summary: Dict[str, Any]) -> bool:
    """Set user badge summary in cache."""
    return gamification_cache.set_user_badge_summary(user_id, summary)


def get_user_cached_streak_info(user_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Get user streak info from cache."""
    return gamification_cache.get_user_streak_info(user_id, force_refresh)


def set_user_cached_streak_info(user_id: str, streak_info: Dict[str, Any]) -> bool:
    """Set user streak info in cache."""
    return gamification_cache.set_user_streak_info(user_id, streak_info)


def get_cached_leaderboard(scope: str = "global", limit: int = 100, force_refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Get leaderboard from cache."""
    return gamification_cache.get_leaderboard(scope, limit, force_refresh)


def set_cached_leaderboard(scope: str, leaderboard: List[Dict[str, Any]], limit: int = 100) -> bool:
    """Set leaderboard in cache."""
    return gamification_cache.set_leaderboard(scope, leaderboard, limit)


def invalidate_user_cache(user_id: str) -> int:
    """Invalidate all cache entries for a user."""
    return gamification_cache.invalidate_user_cache(user_id)


def invalidate_cache_on_badge_award(user_id: str, badge_id: str) -> int:
    """Invalidate cache when user earns a badge."""
    return cache_invalidator.invalidate_on_badge_award(user_id, badge_id)


def invalidate_cache_on_streak_update(user_id: str) -> int:
    """Invalidate cache when user's streak is updated."""
    return cache_invalidator.invalidate_on_streak_update(user_id)


def warm_user_cache(user_id: str) -> Dict[str, bool]:
    """Warm cache for a specific user."""
    return cache_warmer.warm_user_cache(user_id)


def get_cache_performance_stats() -> Dict[str, Any]:
    """Get cache performance statistics."""
    return gamification_cache.get_cache_stats()


def warm_system_cache() -> Dict[str, bool]:
    """Warm system-level cache."""
    return cache_warmer.warm_system_cache()
