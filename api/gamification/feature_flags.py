"""
Gamification Feature Flags — Feature toggling for gamification system.

This module provides feature flag management for enabling/disabling gamification
features, A/B testing, and gradual rollouts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

logger = logging.getLogger(__name__)


class FeatureFlag:
    """Represents a feature flag."""
    
    def __init__(self, key: str, description: str, enabled: bool = False,
                 conditions: Optional[Dict[str, Any]] = None, rollout_percentage: float = 100.0,
                 tags: Optional[List[str]] = None, created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.key = key
        self.description = description
        self.enabled = enabled
        self.conditions = conditions or {}
        self.rollout_percentage = rollout_percentage
        self.tags = tags or []
        self.created_at = created_at or timezone.now()
        self.updated_at = updated_at or timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert feature flag to dictionary."""
        return {
            'key': self.key,
            'description': self.description,
            'enabled': self.enabled,
            'conditions': self.conditions,
            'rollout_percentage': self.rollout_percentage,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def is_enabled_for_user(self, user_id: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if feature is enabled for specific user."""
        if not self.enabled:
            return False
        
        # Check rollout percentage
        if self.rollout_percentage < 100.0:
            user_hash = hash(user_id + self.key) % 100
            if user_hash >= self.rollout_percentage:
                return False
        
        # Check conditions
        if self.conditions:
            return self._evaluate_conditions(user_id, context or {})
        
        return True
    
    def _evaluate_conditions(self, user_id: str, context: Dict[str, Any]) -> bool:
        """Evaluate feature flag conditions."""
        conditions = self.conditions
        
        # User ID conditions
        if 'user_ids' in conditions:
            allowed_users = set(conditions['user_ids'])
            if user_id not in allowed_users:
                return False
        
        # User role conditions
        if 'user_roles' in conditions:
            user_roles = context.get('user_roles', [])
            allowed_roles = set(conditions['user_roles'])
            if not set(user_roles) & allowed_roles:
                return False
        
        # Date range conditions
        if 'date_range' in conditions:
            date_range = conditions['date_range']
            start_date = datetime.fromisoformat(date_range['start'])
            end_date = datetime.fromisoformat(date_range['end'])
            now = timezone.now()
            if not (start_date <= now <= end_date):
                return False
        
        # Percentage conditions (additional to rollout)
        if 'percentage' in conditions:
            percentage = conditions['percentage']
            user_hash = hash(user_id + self.key + str(percentage)) % 100
            if user_hash >= percentage:
                return False
        
        # Custom conditions
        if 'custom' in conditions:
            for custom_condition in conditions['custom']:
                if not self._evaluate_custom_condition(custom_condition, user_id, context):
                    return False
        
        return True
    
    def _evaluate_custom_condition(self, condition: Dict[str, Any], user_id: str, context: Dict[str, Any]) -> bool:
        """Evaluate custom condition."""
        condition_type = condition.get('type')
        
        if condition_type == 'property':
            property_name = condition.get('property')
            operator = condition.get('operator')
            value = condition.get('value')
            
            if property_name not in context:
                return False
            
            user_value = context[property_name]
            
            if operator == 'equals':
                return user_value == value
            elif operator == 'not_equals':
                return user_value != value
            elif operator == 'greater_than':
                return user_value > value
            elif operator == 'less_than':
                return user_value < value
            elif operator == 'in':
                return user_value in value
            elif operator == 'not_in':
                return user_value not in value
        
        elif condition_type == 'function':
            function_name = condition.get('function')
            
            if function_name == 'is_premium_user':
                return context.get('is_premium', False)
            elif function_name == 'is_admin_user':
                return context.get('is_admin', False)
            elif function_name == 'has_completed_onboarding':
                return context.get('onboarding_completed', False)
        
        return True


class FeatureFlagManager:
    """Manager for feature flags."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache_timeout = getattr(settings, 'FEATURE_FLAG_CACHE_TIMEOUT', 300)  # 5 minutes
        self.cache_key_prefix = 'feature_flag:'
        self._flags: Dict[str, FeatureFlag] = {}
        self._load_default_flags()
    
    def _load_default_flags(self):
        """Load default feature flags."""
        default_flags = {
            # Badge system flags
            'badge_system_enabled': FeatureFlag(
                key='badge_system_enabled',
                description='Enable badge system functionality',
                enabled=True,
                tags=['badges', 'core']
            ),
            
            'advanced_badges': FeatureFlag(
                key='advanced_badges',
                description='Enable advanced badge features',
                enabled=True,
                rollout_percentage=50.0,
                tags=['badges', 'advanced']
            ),
            
            'badge_recommendations': FeatureFlag(
                key='badge_recommendations',
                description='Enable AI-powered badge recommendations',
                enabled=False,
                tags=['badges', 'ai', 'recommendations']
            ),
            
            # Streak system flags
            'streak_system_enabled': FeatureFlag(
                key='streak_system_enabled',
                description='Enable streak tracking system',
                enabled=True,
                tags=['streaks', 'core']
            ),
            
            'streak_milestones': FeatureFlag(
                key='streak_milestones',
                description='Enable streak milestone rewards',
                enabled=True,
                tags=['streaks', 'rewards']
            ),
            
            'streak_heatmap': FeatureFlag(
                key='streak_heatmap',
                description='Enable streak heatmap visualization',
                enabled=True,
                rollout_percentage=75.0,
                tags=['streaks', 'visualization']
            ),
            
            # Challenge system flags
            'challenge_system_enabled': FeatureFlag(
                key='challenge_system_enabled',
                description='Enable daily challenge system',
                enabled=True,
                tags=['challenges', 'core']
            ),
            
            'ai_challenges': FeatureFlag(
                key='ai_challenges',
                description='Enable AI-generated challenges',
                enabled=False,
                tags=['challenges', 'ai', 'experimental']
            ),
            
            'challenge_recommendations': FeatureFlag(
                key='challenge_recommendations',
                description='Enable personalized challenge recommendations',
                enabled=True,
                rollout_percentage=30.0,
                tags=['challenges', 'recommendations']
            ),
            
            # Level system flags
            'level_system_enabled': FeatureFlag(
                key='level_system_enabled',
                description='Enable level progression system',
                enabled=True,
                tags=['levels', 'core']
            ),
            
            'level_perks': FeatureFlag(
                key='level_perks',
                description='Enable level-based perks and rewards',
                enabled=True,
                tags=['levels', 'rewards']
            ),
            
            # Contest system flags
            'contest_system_enabled': FeatureFlag(
                key='contest_system_enabled',
                description='Enable contest system',
                enabled=True,
                tags=['contests', 'core']
            ),
            
            'contest_leaderboards': FeatureFlag(
                key='contest_leaderboards',
                description='Enable contest leaderboards',
                enabled=True,
                tags=['contests', 'leaderboards']
            ),
            
            'contest_ai_analytics': FeatureFlag(
                key='contest_ai_analytics',
                description='Enable AI-powered contest analytics',
                enabled=False,
                tags=['contests', 'ai', 'analytics']
            ),
            
            # Search and discovery flags
            'advanced_search': FeatureFlag(
                key='advanced_search',
                description='Enable advanced search functionality',
                enabled=True,
                rollout_percentage=60.0,
                tags=['search', 'discovery']
            ),
            
            'search_suggestions': FeatureFlag(
                key='search_suggestions',
                description='Enable search suggestions and autocomplete',
                enabled=True,
                tags=['search', 'ux']
            ),
            
            # AI integration flags
            'ai_integration_enabled': FeatureFlag(
                key='ai_integration_enabled',
                description='Enable OpenAI integration features',
                enabled=False,
                tags=['ai', 'integration']
            ),
            
            'ai_personalization': FeatureFlag(
                key='ai_personalization',
                description='Enable AI-powered personalization',
                enabled=False,
                rollout_percentage=20.0,
                tags=['ai', 'personalization']
            ),
            
            'ai_content_generation': FeatureFlag(
                key='ai_content_generation',
                description='Enable AI content generation',
                enabled=False,
                tags=['ai', 'content']
            ),
            
            # Knowledge base flags
            'knowledge_base_integration': FeatureFlag(
                key='knowledge_base_integration',
                description='Enable knowledge base integration',
                enabled=True,
                tags=['knowledge_base', 'integration']
            ),
            
            'learning_paths': FeatureFlag(
                key='learning_paths',
                description='Enable learning path generation',
                enabled=True,
                rollout_percentage=40.0,
                tags=['knowledge_base', 'learning']
            ),
            
            # Analytics and monitoring flags
            'advanced_analytics': FeatureFlag(
                key='advanced_analytics',
                description='Enable advanced analytics features',
                enabled=True,
                tags=['analytics', 'monitoring']
            ),
            
            'real_time_analytics': FeatureFlag(
                key='real_time_analytics',
                description='Enable real-time analytics dashboard',
                enabled=False,
                rollout_percentage=25.0,
                tags=['analytics', 'real_time']
            ),
            
            # Notification flags
            'push_notifications': FeatureFlag(
                key='push_notifications',
                description='Enable push notifications',
                enabled=False,
                tags=['notifications', 'push']
            ),
            
            'email_notifications': FeatureFlag(
                key='email_notifications',
                description='Enable email notifications',
                enabled=True,
                tags=['notifications', 'email']
            ),
            
            # Webhook flags
            'webhook_system_enabled': FeatureFlag(
                key='webhook_system_enabled',
                description='Enable webhook system',
                enabled=True,
                tags=['webhooks', 'integration']
            ),
            
            'webhook_retries': FeatureFlag(
                key='webhook_retries',
                description='Enable webhook retry mechanism',
                enabled=True,
                tags=['webhooks', 'reliability']
            ),
            
            # Performance flags
            'caching_enabled': FeatureFlag(
                key='caching_enabled',
                description='Enable caching for performance',
                enabled=True,
                tags=['performance', 'caching']
            ),
            
            'async_processing': FeatureFlag(
                key='async_processing',
                description='Enable async background processing',
                enabled=False,
                rollout_percentage=15.0,
                tags=['performance', 'async']
            ),
            
            # Security flags
            'rate_limiting_enabled': FeatureFlag(
                key='rate_limiting_enabled',
                description='Enable rate limiting',
                enabled=True,
                tags=['security', 'rate_limiting']
            ),
            
            'sanctions_system': FeatureFlag(
                key='sanctions_system',
                description='Enable sanctions and rule enforcement',
                enabled=True,
                tags=['security', 'sanctions']
            ),
            
            # Experimental flags
            'gamification_2_0': FeatureFlag(
                key='gamification_2_0',
                description='Enable gamification 2.0 features',
                enabled=False,
                rollout_percentage=5.0,
                tags=['experimental', 'v2']
            ),
            
            'blockchain_rewards': FeatureFlag(
                key='blockchain_rewards',
                description='Enable blockchain-based rewards',
                enabled=False,
                tags=['experimental', 'blockchain']
            ),
        }
        
        self._flags.update(default_flags)
    
    def get_flag(self, key: str) -> Optional[FeatureFlag]:
        """Get feature flag by key."""
        # Try cache first
        cache_key = f"{self.cache_key_prefix}{key}"
        cached_flag = cache.get(cache_key)
        
        if cached_flag:
            return FeatureFlag(**cached_flag)
        
        # Try memory
        if key in self._flags:
            flag = self._flags[key]
            # Cache it
            cache.set(cache_key, flag.to_dict(), self.cache_timeout)
            return flag
        
        return None
    
    def set_flag(self, key: str, enabled: bool, conditions: Optional[Dict[str, Any]] = None,
                 rollout_percentage: float = 100.0, tags: Optional[List[str]] = None) -> FeatureFlag:
        """Set or update a feature flag."""
        existing_flag = self.get_flag(key)
        
        if existing_flag:
            # Update existing flag
            existing_flag.enabled = enabled
            if conditions is not None:
                existing_flag.conditions = conditions
            if rollout_percentage is not None:
                existing_flag.rollout_percentage = rollout_percentage
            if tags is not None:
                existing_flag.tags = tags
            existing_flag.updated_at = timezone.now()
            
            flag = existing_flag
        else:
            # Create new flag
            flag = FeatureFlag(
                key=key,
                description=f"Feature flag for {key}",
                enabled=enabled,
                conditions=conditions,
                rollout_percentage=rollout_percentage,
                tags=tags
            )
            self._flags[key] = flag
        
        # Update cache
        cache_key = f"{self.cache_key_prefix}{key}"
        cache.set(cache_key, flag.to_dict(), self.cache_timeout)
        
        self.logger.info(f"Feature flag '{key}' set to enabled={enabled}")
        
        return flag
    
    def delete_flag(self, key: str) -> bool:
        """Delete a feature flag."""
        if key in self._flags:
            del self._flags[key]
            
            # Remove from cache
            cache_key = f"{self.cache_key_prefix}{key}"
            cache.delete(cache_key)
            
            self.logger.info(f"Feature flag '{key}' deleted")
            return True
        
        return False
    
    def is_enabled(self, key: str, user_id: Optional[str] = None,
                  context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if feature flag is enabled."""
        flag = self.get_flag(key)
        
        if not flag:
            return False
        
        if user_id:
            return flag.is_enabled_for_user(user_id, context)
        
        return flag.enabled
    
    def get_enabled_flags(self, user_id: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None, tags: Optional[List[str]] = None) -> Dict[str, bool]:
        """Get all enabled flags for user."""
        enabled_flags = {}
        
        for key, flag in self._flags.items():
            if tags and not set(flag.tags) & set(tags):
                continue
            
            if user_id:
                enabled_flags[key] = flag.is_enabled_for_user(user_id, context)
            else:
                enabled_flags[key] = flag.enabled
        
        return enabled_flags
    
    def get_flags_by_tag(self, tag: str) -> List[FeatureFlag]:
        """Get all flags with specific tag."""
        return [flag for flag in self._flags.values() if tag in flag.tags]
    
    def get_all_flags(self) -> Dict[str, FeatureFlag]:
        """Get all feature flags."""
        return self._flags.copy()
    
    def bulk_update_flags(self, updates: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Bulk update multiple feature flags."""
        results = {}
        
        for key, update_data in updates.items():
            try:
                flag = self.set_flag(
                    key=key,
                    enabled=update_data.get('enabled', False),
                    conditions=update_data.get('conditions'),
                    rollout_percentage=update_data.get('rollout_percentage', 100.0),
                    tags=update_data.get('tags')
                )
                results[key] = True
            except Exception as e:
                self.logger.error(f"Error updating flag '{key}': {e}")
                results[key] = False
        
        return results
    
    def export_flags(self, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Export feature flags configuration."""
        flags_to_export = []
        
        for flag in self._flags.values():
            if tags and not set(flag.tags) & set(tags):
                continue
            
            flags_to_export.append(flag.to_dict())
        
        return flags_to_export
    
    def import_flags(self, flags_data: List[Dict[str, Any]], overwrite: bool = False) -> Dict[str, bool]:
        """Import feature flags configuration."""
        results = {}
        
        for flag_data in flags_data:
            key = flag_data['key']
            
            try:
                if not overwrite and key in self._flags:
                    results[key] = False
                    continue
                
                flag = FeatureFlag(
                    key=key,
                    description=flag_data.get('description', ''),
                    enabled=flag_data.get('enabled', False),
                    conditions=flag_data.get('conditions', {}),
                    rollout_percentage=flag_data.get('rollout_percentage', 100.0),
                    tags=flag_data.get('tags', []),
                    created_at=datetime.fromisoformat(flag_data.get('created_at', timezone.now().isoformat())),
                    updated_at=datetime.fromisoformat(flag_data.get('updated_at', timezone.now().isoformat()))
                )
                
                self._flags[key] = flag
                
                # Update cache
                cache_key = f"{self.cache_key_prefix}{key}"
                cache.set(cache_key, flag.to_dict(), self.cache_timeout)
                
                results[key] = True
                
            except Exception as e:
                self.logger.error(f"Error importing flag '{key}': {e}")
                results[key] = False
        
        return results
    
    def clear_cache(self) -> int:
        """Clear all feature flag cache."""
        cache_keys = cache.keys(f"{self.cache_key_prefix}*")
        deleted_count = cache.delete_many(cache_keys)
        
        self.logger.info(f"Cleared {deleted_count} feature flag cache entries")
        
        return deleted_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get feature flag statistics."""
        total_flags = len(self._flags)
        enabled_flags = sum(1 for flag in self._flags.values() if flag.enabled)
        
        # Count by tags
        tag_counts = {}
        for flag in self._flags.values():
            for tag in flag.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Count by rollout percentage ranges
        rollout_ranges = {
            '0-25': 0,
            '26-50': 0,
            '51-75': 0,
            '76-99': 0,
            '100': 0
        }
        
        for flag in self._flags.values():
            if flag.rollout_percentage == 100:
                rollout_ranges['100'] += 1
            elif flag.rollout_percentage <= 25:
                rollout_ranges['0-25'] += 1
            elif flag.rollout_percentage <= 50:
                rollout_ranges['26-50'] += 1
            elif flag.rollout_percentage <= 75:
                rollout_ranges['51-75'] += 1
            else:
                rollout_ranges['76-99'] += 1
        
        return {
            'total_flags': total_flags,
            'enabled_flags': enabled_flags,
            'disabled_flags': total_flags - enabled_flags,
            'enabled_percentage': (enabled_flags / total_flags * 100) if total_flags > 0 else 0,
            'tag_distribution': tag_counts,
            'rollout_distribution': rollout_ranges,
            'generated_at': timezone.now().isoformat()
        }


class FeatureFlagContext:
    """Context provider for feature flag evaluation."""
    
    def __init__(self, user_id: str, user_data: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.user_data = user_data or {}
        self._context_cache = {}
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete context for feature flag evaluation."""
        if not self._context_cache:
            self._context_cache = {
                'user_id': self.user_id,
                'user_roles': self.user_data.get('roles', []),
                'is_premium': self.user_data.get('is_premium', False),
                'is_admin': self.user_data.get('is_admin', False),
                'is_staff': self.user_data.get('is_staff', False),
                'onboarding_completed': self.user_data.get('onboarding_completed', False),
                'registration_date': self.user_data.get('registration_date'),
                'last_login': self.user_data.get('last_login'),
                'total_points': self.user_data.get('total_points', 0),
                'current_level': self.user_data.get('current_level', 1),
                'current_streak': self.user_data.get('current_streak', 0),
                'country': self.user_data.get('country'),
                'language': self.user_data.get('language'),
                'timezone': self.user_data.get('timezone'),
                'device_type': self.user_data.get('device_type'),
                'platform': self.user_data.get('platform'),
            }
        
        return self._context_cache
    
    def update_user_data(self, **kwargs):
        """Update user data."""
        self.user_data.update(kwargs)
        self._context_cache.clear()  # Clear cache to force refresh


# Global feature flag manager instance
feature_flag_manager = FeatureFlagManager()


# Decorators for feature flags
def feature_flag_required(flag_key: str, fallback_value: Any = None):
    """Decorator to require feature flag to be enabled."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id')
            context = kwargs.get('context', {})
            
            if not feature_flag_manager.is_enabled(flag_key, user_id, context):
                return fallback_value
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def feature_flag_enabled(flag_key: str, enabled_value: Any = None, disabled_value: Any = None):
    """Decorator to return different values based on feature flag."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id')
            context = kwargs.get('context', {})
            
            if feature_flag_manager.is_enabled(flag_key, user_id, context):
                return enabled_value if enabled_value is not None else func(*args, **kwargs)
            else:
                return disabled_value if disabled_value is not None else func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience functions for common feature flag operations
def is_feature_enabled(flag_key: str, user_id: Optional[str] = None,
                     context: Optional[Dict[str, Any]] = None) -> bool:
    """Check if feature flag is enabled."""
    return feature_flag_manager.is_enabled(flag_key, user_id, context)


def get_user_enabled_features(user_id: str, user_data: Optional[Dict[str, Any]] = None,
                           tags: Optional[List[str]] = None) -> Dict[str, bool]:
    """Get enabled features for user."""
    context = FeatureFlagContext(user_id, user_data).get_context()
    return feature_flag_manager.get_enabled_flags(user_id, context, tags)


def enable_feature_flag(key: str, enabled: bool = True, **kwargs) -> FeatureFlag:
    """Enable or disable a feature flag."""
    return feature_flag_manager.set_flag(key, enabled, **kwargs)


def create_feature_flag(key: str, description: str, enabled: bool = False,
                       **kwargs) -> FeatureFlag:
    """Create a new feature flag."""
    return feature_flag_manager.set_flag(
        key=key,
        enabled=enabled,
        tags=kwargs.get('tags', []),
        conditions=kwargs.get('conditions', {}),
        rollout_percentage=kwargs.get('rollout_percentage', 100.0)
    )


def get_feature_flags_by_tag(tag: str) -> List[FeatureFlag]:
    """Get all feature flags with specific tag."""
    return feature_flag_manager.get_flags_by_tag(tag)


def bulk_update_feature_flags(updates: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
    """Bulk update multiple feature flags."""
    return feature_flag_manager.bulk_update_flags(updates)


def export_feature_configuration(tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Export feature flag configuration."""
    return feature_flag_manager.export_flags(tags)


def import_feature_configuration(flags_data: List[Dict[str, Any]], overwrite: bool = False) -> Dict[str, bool]:
    """Import feature flag configuration."""
    return feature_flag_manager.import_flags(flags_data, overwrite)


def get_feature_flag_statistics() -> Dict[str, Any]:
    """Get feature flag statistics."""
    return feature_flag_manager.get_statistics()


# Feature flag presets for common scenarios
class FeatureFlagPresets:
    """Predefined feature flag configurations."""
    
    @staticmethod
    def development_environment() -> Dict[str, Dict[str, Any]]:
        """Development environment preset - all features enabled."""
        return {
            flag_key: {'enabled': True, 'rollout_percentage': 100.0}
            for flag_key in feature_flag_manager.get_all_flags().keys()
        }
    
    @staticmethod
    def staging_environment() -> Dict[str, Dict[str, Any]]:
        """Staging environment preset - most features enabled with limited rollout."""
        return {
            'badge_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'streak_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'challenge_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'level_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'contest_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'webhook_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'rate_limiting_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'sanctions_system': {'enabled': True, 'rollout_percentage': 100.0},
            'caching_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'advanced_search': {'enabled': True, 'rollout_percentage': 100.0},
            'knowledge_base_integration': {'enabled': True, 'rollout_percentage': 100.0},
            'advanced_analytics': {'enabled': True, 'rollout_percentage': 100.0},
            'email_notifications': {'enabled': True, 'rollout_percentage': 100.0},
            # Experimental features with limited rollout
            'ai_integration_enabled': {'enabled': True, 'rollout_percentage': 10.0},
            'ai_personalization': {'enabled': True, 'rollout_percentage': 5.0},
            'real_time_analytics': {'enabled': True, 'rollout_percentage': 20.0},
            'async_processing': {'enabled': True, 'rollout_percentage': 30.0},
        }
    
    @staticmethod
    def production_environment() -> Dict[str, Dict[str, Any]]:
        """Production environment preset - stable features only."""
        return {
            'badge_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'streak_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'challenge_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'level_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'contest_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'webhook_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'rate_limiting_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'sanctions_system': {'enabled': True, 'rollout_percentage': 100.0},
            'caching_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'email_notifications': {'enabled': True, 'rollout_percentage': 100.0},
            # Gradual rollout features
            'advanced_badges': {'enabled': True, 'rollout_percentage': 80.0},
            'streak_heatmap': {'enabled': True, 'rollout_percentage': 90.0},
            'challenge_recommendations': {'enabled': True, 'rollout_percentage': 60.0},
            'advanced_search': {'enabled': True, 'rollout_percentage': 70.0},
            'search_suggestions': {'enabled': True, 'rollout_percentage': 85.0},
            'knowledge_base_integration': {'enabled': True, 'rollout_percentage': 75.0},
            'learning_paths': {'enabled': True, 'rollout_percentage': 50.0},
            # Disabled experimental features
            'ai_integration_enabled': {'enabled': False, 'rollout_percentage': 0.0},
            'ai_personalization': {'enabled': False, 'rollout_percentage': 0.0},
            'ai_challenges': {'enabled': False, 'rollout_percentage': 0.0},
            'ai_content_generation': {'enabled': False, 'rollout_percentage': 0.0},
            'ai_recommendations': {'enabled': False, 'rollout_percentage': 0.0},
            'contest_ai_analytics': {'enabled': False, 'rollout_percentage': 0.0},
            'real_time_analytics': {'enabled': False, 'rollout_percentage': 0.0},
            'push_notifications': {'enabled': False, 'rollout_percentage': 0.0},
            'async_processing': {'enabled': False, 'rollout_percentage': 0.0},
            'gamification_2_0': {'enabled': False, 'rollout_percentage': 0.0},
            'blockchain_rewards': {'enabled': False, 'rollout_percentage': 0.0},
        }
    
    @staticmethod
    def beta_testing() -> Dict[str, Dict[str, Any]]:
        """Beta testing preset - new features for beta users."""
        return {
            'badge_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'streak_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'challenge_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'level_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'contest_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'webhook_system_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'rate_limiting_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'sanctions_system': {'enabled': True, 'rollout_percentage': 100.0},
            'caching_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'advanced_badges': {'enabled': True, 'rollout_percentage': 100.0},
            'streak_milestones': {'enabled': True, 'rollout_percentage': 100.0},
            'streak_heatmap': {'enabled': True, 'rollout_percentage': 100.0},
            'challenge_recommendations': {'enabled': True, 'rollout_percentage': 100.0},
            'level_perks': {'enabled': True, 'rollout_percentage': 100.0},
            'contest_leaderboards': {'enabled': True, 'rollout_percentage': 100.0},
            'advanced_search': {'enabled': True, 'rollout_percentage': 100.0},
            'search_suggestions': {'enabled': True, 'rollout_percentage': 100.0},
            'knowledge_base_integration': {'enabled': True, 'rollout_percentage': 100.0},
            'learning_paths': {'enabled': True, 'rollout_percentage': 100.0},
            'advanced_analytics': {'enabled': True, 'rollout_percentage': 100.0},
            'email_notifications': {'enabled': True, 'rollout_percentage': 100.0},
            'webhook_retries': {'enabled': True, 'rollout_percentage': 100.0},
            # Beta features
            'ai_integration_enabled': {'enabled': True, 'rollout_percentage': 100.0},
            'ai_personalization': {'enabled': True, 'rollout_percentage': 100.0},
            'ai_challenges': {'enabled': True, 'rollout_percentage': 100.0},
            'ai_recommendations': {'enabled': True, 'rollout_percentage': 100.0},
            'contest_ai_analytics': {'enabled': True, 'rollout_percentage': 100.0},
            'real_time_analytics': {'enabled': True, 'rollout_percentage': 100.0},
            'push_notifications': {'enabled': True, 'rollout_percentage': 100.0},
            'async_processing': {'enabled': True, 'rollout_percentage': 100.0},
            'gamification_2_0': {'enabled': True, 'rollout_percentage': 100.0},
        }
    
    @staticmethod
    def apply_preset(preset_name: str) -> Dict[str, bool]:
        """Apply a preset configuration."""
        presets = {
            'development': FeatureFlagPresets.development_environment,
            'staging': FeatureFlagPresets.staging_environment,
            'production': FeatureFlagPresets.production_environment,
            'beta': FeatureFlagPresets.beta_testing,
        }
        
        if preset_name not in presets:
            raise ValueError(f"Unknown preset: {preset_name}")
        
        preset_config = presets[preset_name]
        return bulk_update_feature_flags(preset_config)
