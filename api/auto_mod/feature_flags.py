# =============================================================================
# auto_mod/feature_flags.py
# =============================================================================

"""
Feature flags management for auto moderation system.
Provides dynamic feature toggling and A/B testing capabilities.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model

from .exceptions import ModerationError

logger = logging.getLogger(__name__)

User = get_user_model()


class FeatureFlag:
    """Individual feature flag."""
    
    def __init__(self, name: str, description: str = "", enabled: bool = False,
                 rollout_percentage: float = 0.0, user_segments: List[str] = None,
                 metadata: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.enabled = enabled
        self.rollout_percentage = rollout_percentage
        self.user_segments = user_segments or []
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.updated_at = timezone.now()
    
    def is_enabled_for_user(self, user_id: Union[str, int]) -> bool:
        """Check if feature is enabled for a specific user."""
        if not self.enabled:
            return False
        
        # Check user segments
        if self.user_segments:
            if not self._user_in_segments(user_id, self.user_segments):
                return False
        
        # Check rollout percentage
        if self.rollout_percentage < 100.0:
            user_hash = self._get_user_hash(user_id)
            if (user_hash % 100) >= self.rollout_percentage:
                return False
        
        return True
    
    def _user_in_segments(self, user_id: Union[str, int], segments: List[str]) -> bool:
        """Check if user belongs to any of the specified segments."""
        try:
            user = User.objects.get(id=user_id)
            
            # Check various segment criteria
            for segment in segments:
                if segment == 'admin':
                    if user.is_staff or user.is_superuser:
                        return True
                elif segment == 'premium':
                    if hasattr(user, 'is_premium') and user.is_premium:
                        return True
                elif segment == 'beta_tester':
                    if hasattr(user, 'is_beta_tester') and user.is_beta_tester:
                        return True
                elif segment == 'new_users':
                    # Users created in last 30 days
                    if user.date_joined and user.date_joined > timezone.now() - timedelta(days=30):
                        return True
                elif segment == 'veteran_users':
                    # Users created more than 1 year ago
                    if user.date_joined and user.date_joined < timezone.now() - timedelta(days=365):
                        return True
                elif segment.startswith('custom:'):
                    # Custom segment logic
                    custom_segment = segment.split(':', 1)[1]
                    if self._check_custom_segment(user, custom_segment):
                        return True
            
            return False
            
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found for segment check")
            return False
        except Exception as exc:
            logger.error(f"Segment check failed: {exc}")
            return False
    
    def _check_custom_segment(self, user, segment_name: str) -> bool:
        """Check custom segment logic."""
        # This would be extended with custom segment logic
        # For now, return False
        return False
    
    def _get_user_hash(self, user_id: Union[str, int]) -> int:
        """Get consistent hash for user."""
        import hashlib
        user_str = str(user_id)
        return int(hashlib.md5(user_str.encode()).hexdigest(), 16) % 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'rollout_percentage': self.rollout_percentage,
            'user_segments': self.user_segments,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class FeatureFlagManager:
    """
    Manager for feature flags with caching and persistence.
    """
    
    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {}
        self.cache_timeout = 300  # 5 minutes
        self._initialize_default_flags()
        self._load_flags_from_cache()
    
    def _initialize_default_flags(self) -> None:
        """Initialize default feature flags."""
        default_flags = {
            'ai_scanning_enabled': FeatureFlag(
                name='ai_scanning_enabled',
                description='Enable AI-powered content scanning',
                enabled=True,
                rollout_percentage=100.0,
                user_segments=[],
                metadata={'category': 'scanning', 'priority': 'high'}
            ),
            'advanced_ml_models': FeatureFlag(
                name='advanced_ml_models',
                description='Use advanced ML models for content analysis',
                enabled=False,
                rollout_percentage=50.0,
                user_segments=['beta_tester', 'admin'],
                metadata={'category': 'ml', 'priority': 'medium'}
            ),
            'real_time_moderation': FeatureFlag(
                name='real_time_moderation',
                description='Enable real-time moderation processing',
                enabled=True,
                rollout_percentage=75.0,
                user_segments=['premium', 'admin'],
                metadata={'category': 'performance', 'priority': 'high'}
            ),
            'enhanced_reporting': FeatureFlag(
                name='enhanced_reporting',
                description='Enable enhanced reporting and analytics',
                enabled=True,
                rollout_percentage=100.0,
                user_segments=[],
                metadata={'category': 'analytics', 'priority': 'low'}
            ),
            'auto_appeal_processing': FeatureFlag(
                name='auto_appeal_processing',
                description='Enable automatic appeal processing',
                enabled=False,
                rollout_percentage=25.0,
                user_segments=['admin'],
                metadata={'category': 'appeals', 'priority': 'medium'}
            ),
            'content_filtering_v2': FeatureFlag(
                name='content_filtering_v2',
                description='Use version 2 of content filtering',
                enabled=False,
                rollout_percentage=10.0,
                user_segments=['beta_tester'],
                metadata={'category': 'filtering', 'priority': 'high'}
            ),
            'bulk_moderation_tools': FeatureFlag(
                name='bulk_moderation_tools',
                description='Enable bulk moderation tools for moderators',
                enabled=True,
                rollout_percentage=100.0,
                user_segments=['admin'],
                metadata={'category': 'tools', 'priority': 'medium'}
            ),
            'custom_rule_engine': FeatureFlag(
                name='custom_rule_engine',
                description='Enable custom rule engine for auto-approval',
                enabled=False,
                rollout_percentage=5.0,
                user_segments=['admin'],
                metadata={'category': 'rules', 'priority': 'low'}
            ),
        }
        
        for flag in default_flags.values():
            self.flags[flag.name] = flag
    
    def _load_flags_from_cache(self) -> None:
        """Load feature flags from cache."""
        try:
            cached_flags = cache.get('feature_flags')
            if cached_flags:
                for flag_data in cached_flags:
                    flag = FeatureFlag(**flag_data)
                    self.flags[flag.name] = flag
                logger.info(f"Loaded {len(cached_flags)} feature flags from cache")
        except Exception as exc:
            logger.error(f"Load flags from cache failed: {exc}")
    
    def _save_flags_to_cache(self) -> None:
        """Save feature flags to cache."""
        try:
            flags_data = [flag.to_dict() for flag in self.flags.values()]
            cache.set('feature_flags', flags_data, timeout=self.cache_timeout)
        except Exception as exc:
            logger.error(f"Save flags to cache failed: {exc}")
    
    def is_enabled(self, flag_name: str, user_id: Union[str, int] = None) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_name: Name of the feature flag
            user_id: Optional user ID for user-specific checks
            
        Returns:
            True if feature is enabled
        """
        try:
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            if user_id is None:
                return flag.enabled
            
            return flag.is_enabled_for_user(user_id)
            
        except Exception as exc:
            logger.error(f"Check feature flag failed: {exc}")
            return False
    
    def enable_flag(self, flag_name: str, rollout_percentage: float = 100.0,
                   user_segments: List[str] = None) -> bool:
        """
        Enable a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            rollout_percentage: Rollout percentage (0-100)
            user_segments: User segments to target
            
        Returns:
            True if successful
        """
        try:
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            flag.enabled = True
            flag.rollout_percentage = rollout_percentage
            flag.user_segments = user_segments or []
            flag.updated_at = timezone.now()
            
            self._save_flags_to_cache()
            logger.info(f"Enabled feature flag '{flag_name}' with {rollout_percentage}% rollout")
            return True
            
        except Exception as exc:
            logger.error(f"Enable feature flag failed: {exc}")
            return False
    
    def disable_flag(self, flag_name: str) -> bool:
        """
        Disable a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            
        Returns:
            True if successful
        """
        try:
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            flag.enabled = False
            flag.updated_at = timezone.now()
            
            self._save_flags_to_cache()
            logger.info(f"Disabled feature flag '{flag_name}'")
            return True
            
        except Exception as exc:
            logger.error(f"Disable feature flag failed: {exc}")
            return False
    
    def create_flag(self, name: str, description: str = "", enabled: bool = False,
                   rollout_percentage: float = 0.0, user_segments: List[str] = None,
                   metadata: Dict[str, Any] = None) -> bool:
        """
        Create a new feature flag.
        
        Args:
            name: Flag name
            description: Flag description
            enabled: Initial enabled state
            rollout_percentage: Rollout percentage
            user_segments: User segments
            metadata: Additional metadata
            
        Returns:
            True if successful
        """
        try:
            if name in self.flags:
                logger.warning(f"Feature flag '{name}' already exists")
                return False
            
            flag = FeatureFlag(
                name=name,
                description=description,
                enabled=enabled,
                rollout_percentage=rollout_percentage,
                user_segments=user_segments,
                metadata=metadata
            )
            
            self.flags[name] = flag
            self._save_flags_to_cache()
            logger.info(f"Created feature flag '{name}'")
            return True
            
        except Exception as exc:
            logger.error(f"Create feature flag failed: {exc}")
            return False
    
    def update_flag(self, flag_name: str, **kwargs) -> bool:
        """
        Update a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        try:
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            for key, value in kwargs.items():
                if hasattr(flag, key):
                    setattr(flag, key, value)
            
            flag.updated_at = timezone.now()
            self._save_flags_to_cache()
            logger.info(f"Updated feature flag '{flag_name}'")
            return True
            
        except Exception as exc:
            logger.error(f"Update feature flag failed: {exc}")
            return False
    
    def delete_flag(self, flag_name: str) -> bool:
        """
        Delete a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            
        Returns:
            True if successful
        """
        try:
            if flag_name not in self.flags:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            del self.flags[flag_name]
            self._save_flags_to_cache()
            logger.info(f"Deleted feature flag '{flag_name}'")
            return True
            
        except Exception as exc:
            logger.error(f"Delete feature flag failed: {exc}")
            return False
    
    def get_all_flags(self) -> Dict[str, FeatureFlag]:
        """Get all feature flags."""
        return self.flags.copy()
    
    def get_enabled_flags(self, user_id: Union[str, int] = None) -> Dict[str, FeatureFlag]:
        """
        Get enabled feature flags.
        
        Args:
            user_id: Optional user ID for user-specific filtering
            
        Returns:
            Dictionary of enabled flags
        """
        enabled_flags = {}
        
        for name, flag in self.flags.items():
            if user_id is None:
                if flag.enabled:
                    enabled_flags[name] = flag
            else:
                if flag.is_enabled_for_user(user_id):
                    enabled_flags[name] = flag
        
        return enabled_flags
    
    def get_flag_statistics(self) -> Dict[str, Any]:
        """Get feature flag statistics."""
        try:
            total_flags = len(self.flags)
            enabled_flags = len([f for f in self.flags.values() if f.enabled])
            disabled_flags = total_flags - enabled_flags
            
            # Count by category
            categories = {}
            for flag in self.flags.values():
                category = flag.metadata.get('category', 'other')
                categories[category] = categories.get(category, 0) + 1
            
            # Count by priority
            priorities = {}
            for flag in self.flags.values():
                priority = flag.metadata.get('priority', 'low')
                priorities[priority] = priorities.get(priority, 0) + 1
            
            return {
                'total_flags': total_flags,
                'enabled_flags': enabled_flags,
                'disabled_flags': disabled_flags,
                'categories': categories,
                'priorities': priorities,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Get flag statistics failed: {exc}")
            return {'error': str(exc)}


class FeatureFlagDecorator:
    """Decorator for feature flag protection."""
    
    def __init__(self, flag_name: str, fallback_value=None):
        self.flag_name = flag_name
        self.fallback_value = fallback_value
        self.manager = feature_flag_manager
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # Try to get user_id from kwargs or args
            user_id = kwargs.get('user_id')
            if not user_id and args:
                # Assume first argument is user_id if it's not self
                user_id = args[0]
            
            # Check if feature is enabled
            if self.manager.is_enabled(self.flag_name, user_id):
                return func(*args, **kwargs)
            else:
                return self.fallback_value
        
        return wrapper


# Global feature flag manager
feature_flag_manager = FeatureFlagManager()


# Decorators for common features
def ai_scanning_enabled(fallback_value=None):
    """Decorator for AI scanning feature."""
    return FeatureFlagDecorator('ai_scanning_enabled', fallback_value)


def advanced_ml_models_enabled(fallback_value=None):
    """Decorator for advanced ML models feature."""
    return FeatureFlagDecorator('advanced_ml_models', fallback_value)


def real_time_moderation_enabled(fallback_value=None):
    """Decorator for real-time moderation feature."""
    return FeatureFlagDecorator('real_time_moderation', fallback_value)


def enhanced_reporting_enabled(fallback_value=None):
    """Decorator for enhanced reporting feature."""
    return FeatureFlagDecorator('enhanced_reporting', fallback_value)


# Utility functions
def is_feature_enabled(flag_name: str, user_id: Union[str, int] = None) -> bool:
    """Check if a feature is enabled."""
    return feature_flag_manager.is_enabled(flag_name, user_id)


def get_user_enabled_features(user_id: Union[str, int]) -> Dict[str, Any]:
    """Get all enabled features for a user."""
    enabled_flags = feature_flag_manager.get_enabled_flags(user_id)
    return {name: flag.to_dict() for name, flag in enabled_flags.items()}


def enable_feature_for_user(flag_name: str, user_id: Union[str, int]) -> bool:
    """Enable a feature for a specific user (temporary)."""
    # This would implement user-specific feature enabling
    # For now, just check if the flag exists
    flag = feature_flag_manager.flags.get(flag_name)
    return flag is not None


def get_feature_flag_report() -> Dict[str, Any]:
    """Get comprehensive feature flag report."""
    stats = feature_flag_manager.get_flag_statistics()
    
    # Add detailed flag information
    flags_info = {}
    for name, flag in feature_flag_manager.get_all_flags().items():
        flags_info[name] = {
            'description': flag.description,
            'enabled': flag.enabled,
            'rollout_percentage': flag.rollout_percentage,
            'user_segments': flag.user_segments,
            'metadata': flag.metadata,
            'created_at': flag.created_at.isoformat(),
            'updated_at': flag.updated_at.isoformat(),
        }
    
    return {
        'statistics': stats,
        'flags': flags_info,
        'report_generated_at': timezone.now().isoformat()
    }


# Initialize logging
logger.info("Feature flags module initialized with dynamic feature toggling")
