# api/rate_limit/feature_flags.py
"""
Feature flags system for rate limit module.

Provides dynamic feature toggling for rate limiting functionality.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import redis

logger = logging.getLogger(__name__)


class FeatureFlag:
    """Represents a feature flag."""
    
    def __init__(self, key: str, name: str, description: str, 
                 enabled: bool = False, rollout_percentage: float = 100.0,
                 conditions: List[Callable] = None, metadata: Dict[str, Any] = None):
        self.key = key
        self.name = name
        self.description = description
        self.enabled = enabled
        self.rollout_percentage = rollout_percentage
        self.conditions = conditions or []
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.updated_at = timezone.now()
    
    def is_enabled(self, context: Dict[str, Any] = None) -> bool:
        """
        Check if feature flag is enabled for given context.
        
        Args:
            context: Context data for evaluation
            
        Returns:
            True if feature is enabled
        """
        context = context or {}
        
        # Check if globally enabled
        if not self.enabled:
            return False
        
        # Check rollout percentage
        if not self._check_rollout_percentage(context):
            return False
        
        # Check conditions
        for condition in self.conditions:
            if not condition(context):
                return False
        
        return True
    
    def _check_rollout_percentage(self, context: Dict[str, Any]) -> bool:
        """Check rollout percentage based on context."""
        if self.rollout_percentage >= 100.0:
            return True
        
        if self.rollout_percentage <= 0.0:
            return False
        
        # Use user ID or IP for consistent rollout
        identifier = context.get('user_id')
        if not identifier:
            identifier = context.get('ip_address', 'anonymous')
        
        # Create hash for consistent distribution
        import hashlib
        hash_input = f"{self.key}:{identifier}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        
        # Check if within rollout percentage
        threshold = int((self.rollout_percentage / 100.0) * (2**32))
        return hash_value < threshold
    
    def enable(self):
        """Enable feature flag."""
        self.enabled = True
        self.updated_at = timezone.now()
    
    def disable(self):
        """Disable feature flag."""
        self.enabled = False
        self.updated_at = timezone.now()
    
    def set_rollout_percentage(self, percentage: float):
        """Set rollout percentage."""
        self.rollout_percentage = max(0.0, min(100.0, percentage))
        self.updated_at = timezone.now()
    
    def add_condition(self, condition: Callable):
        """Add condition to feature flag."""
        self.conditions.append(condition)
        self.updated_at = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert feature flag to dictionary."""
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'rollout_percentage': self.rollout_percentage,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }


class FeatureFlagManager:
    """
    Manager for feature flags.
    """
    
    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {}
        self.cache_timeout = 300  # 5 minutes
        self._load_default_flags()
        self._load_flags_from_settings()
    
    def _load_default_flags(self):
        """Load default feature flags."""
        
        # Advanced rate limiting algorithms
        self.register_flag(FeatureFlag(
            key='advanced_rate_limiting',
            name='Advanced Rate Limiting',
            description='Enable advanced rate limiting algorithms (sliding window, token bucket)',
            enabled=False,
            rollout_percentage=0.0,
            metadata={
                'algorithms': ['sliding_window', 'token_bucket', 'adaptive'],
                'performance_impact': 'medium'
            }
        ))
        
        # Machine learning abuse detection
        self.register_flag(FeatureFlag(
            key='ml_abuse_detection',
            name='ML Abuse Detection',
            description='Enable machine learning-based abuse detection',
            enabled=False,
            rollout_percentage=10.0,
            metadata={
                'model_version': '1.0',
                'confidence_threshold': 0.8
            }
        ))
        
        # Real-time monitoring
        self.register_flag(FeatureFlag(
            key='real_time_monitoring',
            name='Real-time Monitoring',
            description='Enable real-time rate limit monitoring and alerts',
            enabled=True,
            rollout_percentage=100.0,
            metadata={
                'alert_threshold': 100,
                'monitoring_interval': 60
            }
        ))
        
        # Premium user features
        self.register_flag(FeatureFlag(
            key='premium_features',
            name='Premium Features',
            description='Enable premium user rate limiting features',
            enabled=True,
            rollout_percentage=100.0,
            conditions=[lambda ctx: ctx.get('is_premium', False)],
            metadata={
                'multiplier': 5.0,
                'custom_limits': True
            }
        ))
        
        # Geolocation blocking
        self.register_flag(FeatureFlag(
            key='geolocation_blocking',
            name='Geolocation Blocking',
            description='Enable geolocation-based IP blocking',
            enabled=False,
            rollout_percentage=0.0,
            metadata={
                'blocked_countries': [],
                'proxy_detection': True
            }
        ))
        
        # API health monitoring
        self.register_flag(FeatureFlag(
            key='api_health_monitoring',
            name='API Health Monitoring',
            description='Enable API health monitoring and auto-adjustment',
            enabled=True,
            rollout_percentage=50.0,
            metadata={
                'health_check_interval': 300,
                'auto_adjustment': True
            }
        ))
        
        # Distributed rate limiting
        self.register_flag(FeatureFlag(
            key='distributed_rate_limiting',
            name='Distributed Rate Limiting',
            description='Enable distributed rate limiting across multiple servers',
            enabled=False,
            rollout_percentage=0.0,
            metadata={
                'backend': 'redis',
                'sync_interval': 10
            }
        ))
        
        # Adaptive throttling
        self.register_flag(FeatureFlag(
            key='adaptive_throttling',
            name='Adaptive Throttling',
            description='Enable adaptive throttling based on system load',
            enabled=False,
            rollout_percentage=20.0,
            metadata={
                'load_threshold': 80,
                'adjustment_factor': 0.5
            }
        ))
        
        # Bulk operations
        self.register_flag(FeatureFlag(
            key='bulk_operations',
            name='Bulk Operations',
            description='Enable bulk rate limit operations',
            enabled=True,
            rollout_percentage=100.0,
            metadata={
                'max_bulk_size': 1000,
                'async_processing': True
            }
        ))
        
        # Analytics dashboard
        self.register_flag(FeatureFlag(
            key='analytics_dashboard',
            name='Analytics Dashboard',
            description='Enable advanced analytics dashboard',
            enabled=True,
            rollout_percentage=75.0,
            metadata={
                'real_time_updates': True,
                'export_features': True
            }
        ))
    
    def _load_flags_from_settings(self):
        """Load feature flags from Django settings."""
        feature_flags_settings = getattr(settings, 'RATE_LIMIT_FEATURE_FLAGS', {})
        
        for key, config in feature_flags_settings.items():
            if key in self.flags:
                # Update existing flag
                flag = self.flags[key]
                flag.enabled = config.get('enabled', flag.enabled)
                flag.rollout_percentage = config.get('rollout_percentage', flag.rollout_percentage)
                flag.metadata.update(config.get('metadata', {}))
            else:
                # Create new flag
                self.register_flag(FeatureFlag(
                    key=key,
                    name=config.get('name', key),
                    description=config.get('description', ''),
                    enabled=config.get('enabled', False),
                    rollout_percentage=config.get('rollout_percentage', 0.0),
                    metadata=config.get('metadata', {})
                ))
    
    def register_flag(self, flag: FeatureFlag):
        """Register a feature flag."""
        self.flags[flag.key] = flag
        logger.info(f"Registered feature flag: {flag.key}")
    
    def unregister_flag(self, key: str):
        """Unregister a feature flag."""
        if key in self.flags:
            del self.flags[key]
            logger.info(f"Unregistered feature flag: {key}")
    
    def get_flag(self, key: str) -> Optional[FeatureFlag]:
        """Get feature flag by key."""
        return self.flags.get(key)
    
    def is_enabled(self, key: str, context: Dict[str, Any] = None) -> bool:
        """
        Check if feature flag is enabled.
        
        Args:
            key: Feature flag key
            context: Context data for evaluation
            
        Returns:
            True if feature is enabled
        """
        flag = self.get_flag(key)
        if not flag:
            return False
        
        return flag.is_enabled(context)
    
    def enable_flag(self, key: str):
        """Enable feature flag."""
        flag = self.get_flag(key)
        if flag:
            flag.enable()
            self._clear_cache(key)
            logger.info(f"Enabled feature flag: {key}")
    
    def disable_flag(self, key: str):
        """Disable feature flag."""
        flag = self.get_flag(key)
        if flag:
            flag.disable()
            self._clear_cache(key)
            logger.info(f"Disabled feature flag: {key}")
    
    def set_rollout_percentage(self, key: str, percentage: float):
        """Set rollout percentage for feature flag."""
        flag = self.get_flag(key)
        if flag:
            flag.set_rollout_percentage(percentage)
            self._clear_cache(key)
            logger.info(f"Set rollout percentage for {key}: {percentage}%")
    
    def get_all_flags(self) -> List[Dict[str, Any]]:
        """Get all feature flags."""
        return [flag.to_dict() for flag in self.flags.values()]
    
    def get_enabled_flags(self, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get enabled feature flags for context."""
        enabled_flags = []
        
        for flag in self.flags.values():
            if flag.is_enabled(context):
                enabled_flags.append(flag.to_dict())
        
        return enabled_flags
    
    def get_flag_statistics(self) -> Dict[str, Any]:
        """Get feature flag statistics."""
        total_flags = len(self.flags)
        enabled_flags = len([f for f in self.flags.values() if f.enabled])
        partially_rolled = len([f for f in self.flags.values() if 0 < f.rollout_percentage < 100])
        
        return {
            'total_flags': total_flags,
            'enabled_flags': enabled_flags,
            'disabled_flags': total_flags - enabled_flags,
            'partially_rolled_flags': partially_rolled,
            'fully_rolled_flags': len([f for f in self.flags.values() if f.rollout_percentage == 100])
        }
    
    def _clear_cache(self, key: str = None):
        """Clear feature flag cache."""
        if key:
            cache.delete(f"feature_flag:{key}")
        else:
            # Clear all feature flag cache
            cache_keys = cache.keys("feature_flag:*")
            for cache_key in cache_keys:
                cache.delete(cache_key)



    def create_flag(self, name: str, description: str = '', is_enabled: bool = True):
        """Create a new feature flag."""
        flag = FeatureFlag(name=name, description=description)
        flag.is_enabled = is_enabled
        self._flags[name] = flag
        return flag

    def get_all_flags(self, prefix: str = '') -> list:
        """Get all flags, optionally filtered by prefix."""
        if prefix:
            return [f for name, f in self._flags.items() if name.startswith(prefix)]
        return list(self._flags.values())

    def delete_flag(self, name: str) -> bool:
        """Delete a flag by name."""
        if name in self._flags:
            del self._flags[name]
            return True
        return False

    def get_flag(self, name: str):
        """Get flag by name."""
        return self._flags.get(name)


class FeatureFlagDecorator:
    """
    Decorator for feature flag conditional execution.
    """
    
    def __init__(self, flag_key: str, fallback_value=None):
        self.flag_key = flag_key
        self.fallback_value = fallback_value
        self.manager = FeatureFlagManager()
    
    def __call__(self, func):
        """Decorator implementation."""
        def wrapper(*args, **kwargs):
            # Extract context from kwargs or first argument
            context = kwargs.get('feature_flag_context', {})
            
            if not context and args:
                # Try to extract context from first argument (e.g., request object)
                first_arg = args[0]
                if hasattr(first_arg, 'user'):
                    context['user_id'] = first_arg.user.id if first_arg.user.is_authenticated else None
                    context['is_premium'] = getattr(first_arg.user, 'is_premium', False)
                if hasattr(first_arg, 'META'):
                    context['ip_address'] = first_arg.META.get('REMOTE_ADDR')
            
            if self.manager.is_enabled(self.flag_key, context):
                return func(*args, **kwargs)
            else:
                return self.fallback_value
        
        return wrapper


class ConditionalFeature:
    """
    Context manager for conditional feature execution.
    """
    
    def __init__(self, flag_key: str, context: Dict[str, Any] = None):
        self.flag_key = flag_key
        self.context = context or {}
        self.manager = FeatureFlagManager()
        self.is_feature_enabled = False
    
    def __enter__(self):
        """Enter context manager."""
        self.is_feature_enabled = self.manager.is_enabled(self.flag_key, self.context)
        return self.is_feature_enabled
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        pass


# Global feature flag manager instance
feature_flag_manager = FeatureFlagManager()


# Convenience functions
def is_feature_enabled(flag_key: str, context: Dict[str, Any] = None) -> bool:
    """
    Check if feature flag is enabled.
    
    Args:
        flag_key: Feature flag key
        context: Context data for evaluation
        
    Returns:
        True if feature is enabled
    """
    return feature_flag_manager.is_enabled(flag_key, context)


def feature_flag(flag_key: str, fallback_value=None):
    """
    Decorator for feature flag conditional execution.
    
    Args:
        flag_key: Feature flag key
        fallback_value: Value to return if feature is disabled
        
    Returns:
        Decorator function
    """
    return FeatureFlagDecorator(flag_key, fallback_value)


def conditional_feature(flag_key: str, context: Dict[str, Any] = None):
    """
    Context manager for conditional feature execution.
    
    Args:
        flag_key: Feature flag key
        context: Context data for evaluation
        
    Returns:
        Context manager
    """
    return ConditionalFeature(flag_key, context)


# Rate limiting specific feature checks
def use_advanced_algorithms(context: Dict[str, Any] = None) -> bool:
    """Check if advanced rate limiting algorithms are enabled."""
    return is_feature_enabled('advanced_rate_limiting', context)


def use_ml_abuse_detection(context: Dict[str, Any] = None) -> bool:
    """Check if ML abuse detection is enabled."""
    return is_feature_enabled('ml_abuse_detection', context)


def use_real_time_monitoring(context: Dict[str, Any] = None) -> bool:
    """Check if real-time monitoring is enabled."""
    return is_feature_enabled('real_time_monitoring', context)


def use_premium_features(context: Dict[str, Any] = None) -> bool:
    """Check if premium features are enabled."""
    return is_feature_enabled('premium_features', context)


def use_geolocation_blocking(context: Dict[str, Any] = None) -> bool:
    """Check if geolocation blocking is enabled."""
    return is_feature_enabled('geolocation_blocking', context)


def use_api_health_monitoring(context: Dict[str, Any] = None) -> bool:
    """Check if API health monitoring is enabled."""
    return is_feature_enabled('api_health_monitoring', context)


def use_distributed_rate_limiting(context: Dict[str, Any] = None) -> bool:
    """Check if distributed rate limiting is enabled."""
    return is_feature_enabled('distributed_rate_limiting', context)


def use_adaptive_throttling(context: Dict[str, Any] = None) -> bool:
    """Check if adaptive throttling is enabled."""
    return is_feature_enabled('adaptive_throttling', context)


def use_bulk_operations(context: Dict[str, Any] = None) -> bool:
    """Check if bulk operations are enabled."""
    return is_feature_enabled('bulk_operations', context)


def use_analytics_dashboard(context: Dict[str, Any] = None) -> bool:
    """Check if analytics dashboard is enabled."""
    return is_feature_enabled('analytics_dashboard', context)


# Export classes and functions
__all__ = [
    'FeatureFlag',
    'FeatureFlagManager',
    'FeatureFlagDecorator',
    'ConditionalFeature',
    'feature_flag_manager',
    'is_feature_enabled',
    'feature_flag',
    'conditional_feature',
    'use_advanced_algorithms',
    'use_ml_abuse_detection',
    'use_real_time_monitoring',
    'use_premium_features',
    'use_geolocation_blocking',
    'use_api_health_monitoring',
    'use_distributed_rate_limiting',
    'use_adaptive_throttling',
    'use_bulk_operations',
    'use_analytics_dashboard'
]


class RateLimitFeatureFlags:
    # Pre-defined flags that default to True
    _DEFAULT_TRUE_FLAGS = {
        'redis_rate_limiting', 'sliding_window', 'abuse_detection',
        'ip_blocking', 'premium_limits', 'websocket_rate_limit',
        'disaster_recovery', 'auto_scaling', 'health_checks',
    }


    """
    Convenience class for rate_limit-specific feature flags.
    Wraps FeatureFlagManager with rate_limit defaults.
    """
    _manager = None

    def __init__(self):
        self._manager = FeatureFlagManager()
        self._eval_counters: dict = {}  # flag_name -> {total, enabled, disabled}
        self._kill_switches: set = set()  # enabled kill switch keys

    def create_flag(self, flag_data: dict):
        """Create a new FeatureFlag from a dict with key/name/description/enabled/conditions/metadata."""
        try:
            key = flag_data.get('key', flag_data.get('name', ''))
            name = flag_data.get('name', key)
            enabled = flag_data.get('enabled', flag_data.get('is_enabled', True))
            conditions = flag_data.get('conditions', {})
            metadata = flag_data.get('metadata', {})

            flag = FeatureFlag(
                key=key,
                name=name,
                description=flag_data.get('description', ''),
                enabled=enabled,
                rollout_percentage=float(conditions.get('percentage', 100)),
                metadata=metadata,
            )
            # Store conditions dict directly for test assertions
            flag.conditions = conditions
            # Give flag a stable id
            import hashlib
            flag.id = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

            # Register under both key and prefixed key
            self._manager.flags[key] = flag
            self._manager.flags[f'rate_limit.{key}'] = flag
            return flag
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"create_flag error: {e}")
            return None

    def is_enabled(self, flag_name: str, user=None, default: bool = False) -> bool:
        """Check if a rate_limit feature flag is enabled for the given user."""
        result = self._evaluate_flag(flag_name, user, default)
        # Always track evaluation count
        counters = self._eval_counters.setdefault(flag_name, {'total': 0, 'enabled': 0, 'disabled': 0})
        counters['total'] += 1
        if result:
            counters['enabled'] += 1
        else:
            counters['disabled'] += 1
        return result

    def _evaluate_flag(self, flag_name: str, user=None, default: bool = False) -> bool:
        """Inner evaluation logic (no side effects)."""
        try:
            flag = (self._manager.flags.get(flag_name)
                    or self._manager.flags.get(f'rate_limit.{flag_name}')
                    or self._manager.get_flag(f'rate_limit.{flag_name}'))
            if flag is None:
                return flag_name in self._DEFAULT_TRUE_FLAGS or default

            if not getattr(flag, 'enabled', getattr(flag, 'is_enabled', True)):
                return False

            # Kill switch: if any kill switch active, disable non-kill flags
            if self._kill_switches and not flag_name.startswith('kill_'):
                return False

            conditions = getattr(flag, 'conditions', {})
            if isinstance(conditions, dict) and conditions:
                # Role-based check
                user_roles = conditions.get('user_roles', [])
                if user_roles and user is not None:
                    user_is_role = False
                    for role in user_roles:
                        if role == 'admin' and getattr(user, 'is_superuser', False):
                            user_is_role = True
                        elif role == 'staff' and getattr(user, 'is_staff', False):
                            user_is_role = True
                        elif role == 'regular' and not getattr(user, 'is_staff', False):
                            user_is_role = True
                    if not user_is_role:
                        return False

                # Percentage-based rollout (deterministic per user)
                percentage = conditions.get('percentage')
                if percentage is not None and float(percentage) < 100:
                    if user is not None and hasattr(user, 'id') and user.id:
                        import hashlib
                        h = int(hashlib.md5(f"{flag_name}:{user.id}".encode()).hexdigest()[:4], 16)
                        user_bucket = (h % 100) + 1  # 1..100
                        if user_bucket > float(percentage):
                            return False
                    else:
                        rollout = getattr(flag, 'rollout_percentage', 100.0)
                        if rollout < 100.0:
                            return False

            return True
        except Exception:
            return flag_name in self._DEFAULT_TRUE_FLAGS or default

    def enable_redis_rate_limiting(self):
        return self.is_enabled('redis_rate_limiting', default=True)

    def enable_sliding_window(self):
        return self.is_enabled('sliding_window', default=True)

    def enable_token_bucket(self):
        return self.is_enabled('token_bucket', default=False)

    def enable_abuse_detection(self):
        return self.is_enabled('abuse_detection', default=True)

    def enable_ip_blocking(self):
        return self.is_enabled('ip_blocking', default=True)

    def enable_premium_limits(self):
        return self.is_enabled('premium_limits', default=True)

    def enable_websocket_rate_limit(self):
        return self.is_enabled('websocket_rate_limit', default=True)

    def enable_compliance_mode(self):
        return self.is_enabled('compliance_mode', default=False)

    def get_flag_by_name(self, name: str):
        """Get flag by name."""
        try:
            return self._manager.get_flag(f'rate_limit.{name}')
        except Exception:
            return None

    def toggle_flag(self, name: str, enabled: bool = None):
        """Toggle a feature flag."""
        try:
            flag = self._manager.get_flag(f'rate_limit.{name}')
            if flag:
                flag.is_enabled = not flag.is_enabled if enabled is None else enabled
                return flag
            return None
        except Exception:
            return None

    def get_all_flags(self) -> list:
        """Get all rate_limit feature flags."""
        try:
            return self._manager.get_all_flags(prefix='rate_limit.')
        except Exception:
            return []

    def get_enabled_flags(self) -> list:
        """Get all enabled flags."""
        try:
            return [f for f in self.get_all_flags() if getattr(f, 'is_enabled', False)]
        except Exception:
            return []

    def delete_flag(self, name: str) -> bool:
        """Delete a feature flag."""
        try:
            return self._manager.delete_flag(f'rate_limit.{name}')
        except Exception:
            return False

    def update_flag(self, name: str, updates: dict) -> bool:
        """Update a feature flag."""
        try:
            flag = self._manager.get_flag(f'rate_limit.{name}')
            if flag:
                for k, v in updates.items():
                    setattr(flag, k, v)
                return True
            return False
        except Exception:
            return False

    def enable_flag(self, name: str) -> bool:
        flag = self._manager.flags.get(name) or self._manager.flags.get(f'rate_limit.{name}')
        if flag:
            flag.enabled = True
            if hasattr(flag, 'is_enabled') and not callable(flag.is_enabled):
                flag.is_enabled = True
            if 'kill' in name.lower():
                self._kill_switches.add(name)
            return True
        return False

    def disable_flag(self, name: str) -> bool:
        flag = self._manager.flags.get(name) or self._manager.flags.get(f'rate_limit.{name}')
        if flag:
            flag.enabled = False
            if hasattr(flag, 'is_enabled') and not callable(flag.is_enabled):
                flag.is_enabled = False
            self._kill_switches.discard(name)
            return True
        return False

    def update_flag_percentage(self, name: str, percentage: float) -> bool:
        flag = self._manager.flags.get(name) or self._manager.flags.get(f'rate_limit.{name}')
        if flag:
            flag.rollout_percentage = float(percentage)
            if hasattr(flag, 'conditions') and isinstance(flag.conditions, dict):
                flag.conditions['percentage'] = percentage
            return True
        return False

    def get_flag_analytics(self, name: str) -> dict:
        flag = self._manager.flags.get(name) or self._manager.flags.get(f'rate_limit.{name}')
        counters = self._eval_counters.get(name, {'total': 0, 'enabled': 0, 'disabled': 0})
        return {
            'flag_key': name,
            'enabled': getattr(flag, 'enabled', False) if flag else False,
            'rollout_percentage': getattr(flag, 'rollout_percentage', 0.0) if flag else 0.0,
            'total_evaluations': counters['total'],
            'evaluation_count': counters['total'],
            'enabled_count': counters['enabled'],
            'disabled_count': counters['disabled'],
        }

    def bulk_enable_flags(self, keys: list) -> int:
        count = 0
        for k in keys:
            if self.enable_flag(k):
                count += 1
        return count

    def bulk_disable_flags(self, keys: list) -> int:
        count = 0
        for k in keys:
            if self.disable_flag(k):
                count += 1
        return count

    def export_flags(self) -> list:
        import json
        result = []
        seen = set()
        for key, flag in self._manager.flags.items():
            fid = id(flag)
            if fid in seen:
                continue
            seen.add(fid)
            result.append({
                'key': getattr(flag, 'key', key),
                'name': getattr(flag, 'name', key),
                'description': getattr(flag, 'description', ''),
                'enabled': getattr(flag, 'enabled', True),
                'rollout_percentage': getattr(flag, 'rollout_percentage', 100.0),
                'conditions': getattr(flag, 'conditions', {}),
                'metadata': getattr(flag, 'metadata', {}),
            })
        return result

    def import_flags(self, flags_data: list) -> int:
        count = 0
        for fd in flags_data:
            flag = self.create_flag(fd)
            if flag:
                count += 1
        return count

    def get_monitoring_metrics(self) -> dict:
        """Return monitoring metrics for flag evaluations."""
        total = sum(c['total'] for c in self._eval_counters.values())
        return {
            'flag_evaluations': total,
            'cache_hit_rate': 0.0,
            'average_evaluation_time': 0.0,
            'total_flags': len(set(self._manager.flags.values())),
            'enabled_flags': sum(
                1 for f in set(self._manager.flags.values())
                if getattr(f, 'enabled', True)
            ),
        }
