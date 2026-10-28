"""
feature_flags.py – Feature flag management for postback module.

Provides comprehensive feature flag functionality including:
- Dynamic feature toggling
- User-based targeting
- A/B testing support
- Rollout management
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class FeatureStatus(Enum):
    """Feature status enumeration."""
    DISABLED = "disabled"
    ENABLED = "enabled"
    ROLLOUT = "rollout"
    TESTING = "testing"


class TargetingType(Enum):
    """Targeting type enumeration."""
    ALL_USERS = "all_users"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    USER_GROUPS = "user_groups"
    IP_RANGES = "ip_ranges"
    NETWORK_KEYS = "network_keys"


@dataclass
class FeatureFlag:
    """Feature flag data structure."""
    name: str
    description: str
    status: FeatureStatus
    targeting_type: TargetingType
    targeting_config: Dict[str, Any] = field(default_factory=dict)
    rollout_percentage: float = 0.0
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    enabled_at: Optional[datetime] = None
    disabled_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.status == FeatureStatus.ENABLED and not self.enabled_at:
            self.enabled_at = self.created_at
        
        if self.status == FeatureStatus.DISABLED and not self.disabled_at:
            self.disabled_at = self.updated_at
    
    def is_enabled(self, context: Dict[str, Any] = None) -> bool:
        """
        Check if feature is enabled for given context.
        
        Args:
            context: Evaluation context
            
        Returns:
            True if feature is enabled
        """
        if self.status == FeatureStatus.DISABLED:
            return False
        
        if self.status == FeatureStatus.ENABLED:
            return True
        
        if self.status == FeatureStatus.ROLLOUT:
            return self._evaluate_rollout(context)
        
        if self.status == FeatureStatus.TESTING:
            return self._evaluate_targeting(context)
        
        return False
    
    def _evaluate_rollout(self, context: Dict[str, Any] = None) -> bool:
        """Evaluate rollout based on percentage."""
        if self.rollout_percentage >= 100.0:
            return True
        
        if self.rollout_percentage <= 0.0:
            return False
        
        # Get user identifier for consistent hashing
        user_id = self._get_user_identifier(context)
        if not user_id:
            # Fallback to random for anonymous users
            import random
            return random.random() * 100 < self.rollout_percentage
        
        # Consistent hash based on user ID
        hash_value = hash(user_id) % 100
        return hash_value < self.rollout_percentage
    
    def _evaluate_targeting(self, context: Dict[str, Any] = None) -> bool:
        """Evaluate targeting rules."""
        if not context:
            return False
        
        if self.targeting_type == TargetingType.ALL_USERS:
            return True
        
        elif self.targeting_type == TargetingType.PERCENTAGE:
            return self._evaluate_percentage_targeting(context)
        
        elif self.targeting_type == TargetingType.USER_LIST:
            return self._evaluate_user_list_targeting(context)
        
        elif self.targeting_type == TargetingType.USER_GROUPS:
            return self._evaluate_user_groups_targeting(context)
        
        elif self.targeting_type == TargetingType.IP_RANGES:
            return self._evaluate_ip_ranges_targeting(context)
        
        elif self.targeting_type == TargetingType.NETWORK_KEYS:
            return self._evaluate_network_keys_targeting(context)
        
        return False
    
    def _get_user_identifier(self, context: Dict[str, Any]) -> Optional[str]:
        """Get user identifier for consistent hashing."""
        user = context.get('user')
        if user and hasattr(user, 'id'):
            return str(user.id)
        
        user_id = context.get('user_id')
        if user_id:
            return str(user_id)
        
        return None
    
    def _evaluate_percentage_targeting(self, context: Dict[str, Any]) -> bool:
        """Evaluate percentage targeting."""
        percentage = self.targeting_config.get('percentage', 0)
        if percentage >= 100.0:
            return True
        
        if percentage <= 0.0:
            return False
        
        user_id = self._get_user_identifier(context)
        if not user_id:
            import random
            return random.random() * 100 < percentage
        
        hash_value = hash(user_id) % 100
        return hash_value < percentage
    
    def _evaluate_user_list_targeting(self, context: Dict[str, Any]) -> bool:
        """Evaluate user list targeting."""
        user_ids = self.targeting_config.get('user_ids', [])
        if not user_ids:
            return False
        
        user_id = self._get_user_identifier(context)
        return user_id in user_ids
    
    def _evaluate_user_groups_targeting(self, context: Dict[str, Any]) -> bool:
        """Evaluate user groups targeting."""
        target_groups = self.targeting_config.get('user_groups', [])
        if not target_groups:
            return False
        
        user = context.get('user')
        if not user or not hasattr(user, 'groups'):
            return False
        
        user_groups = [group.name for group in user.groups.all()]
        return any(group in user_groups for group in target_groups)
    
    def _evaluate_ip_ranges_targeting(self, context: Dict[str, Any]) -> bool:
        """Evaluate IP ranges targeting."""
        ip_ranges = self.targeting_config.get('ip_ranges', [])
        if not ip_ranges:
            return False
        
        ip_address = context.get('ip_address')
        if not ip_address:
            return False
        
        import ipaddress
        
        try:
            ip = ipaddress.ip_address(ip_address)
            
            for ip_range in ip_ranges:
                if '/' in ip_range:
                    # CIDR range
                    network = ipaddress.ip_network(ip_range, strict=False)
                    if ip in network:
                        return True
                else:
                    # Exact match
                    if ip_address == ip_range:
                        return True
        except ValueError:
            pass
        
        return False
    
    def _evaluate_network_keys_targeting(self, context: Dict[str, Any]) -> bool:
        """Evaluate network keys targeting."""
        target_networks = self.targeting_config.get('network_keys', [])
        if not target_networks:
            return False
        
        network_key = context.get('network_key')
        return network_key in target_networks
    
    def enable(self):
        """Enable feature flag."""
        self.status = FeatureStatus.ENABLED
        self.enabled_at = timezone.now()
        self.updated_at = timezone.now()
    
    def disable(self):
        """Disable feature flag."""
        self.status = FeatureStatus.DISABLED
        self.disabled_at = timezone.now()
        self.updated_at = timezone.now()
    
    def set_rollout(self, percentage: float):
        """Set rollout percentage."""
        self.status = FeatureStatus.ROLLOUT
        self.rollout_percentage = max(0.0, min(100.0, percentage))
        self.updated_at = timezone.now()
    
    def set_testing(self, targeting_type: TargetingType, targeting_config: Dict[str, Any]):
        """Set testing configuration."""
        self.status = FeatureStatus.TESTING
        self.targeting_type = targeting_type
        self.targeting_config = targeting_config
        self.updated_at = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'targeting_type': self.targeting_type.value,
            'targeting_config': self.targeting_config,
            'rollout_percentage': self.rollout_percentage,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'enabled_at': self.enabled_at.isoformat() if self.enabled_at else None,
            'disabled_at': self.disabled_at.isoformat() if self.disabled_at else None,
            'metadata': self.metadata,
        }


class FeatureFlagManager:
    """
    Manager for feature flags.
    
    Handles feature flag storage, evaluation, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.flags: Dict[str, FeatureFlag] = {}
        self._setup_default_flags()
        self._load_flags_from_storage()
    
    def _setup_default_flags(self):
        """Setup default feature flags."""
        default_flags = [
            FeatureFlag(
                name="advanced_analytics",
                description="Enable advanced analytics features",
                status=FeatureStatus.ENABLED,
                targeting_type=TargetingType.ALL_USERS,
            ),
            FeatureFlag(
                name="real_time_processing",
                description="Enable real-time postback processing",
                status=FeatureStatus.ROLLOUT,
                targeting_type=TargetingType.ALL_USERS,
                rollout_percentage=50.0,
            ),
            FeatureFlag(
                name="fraud_detection",
                description="Enable advanced fraud detection",
                status=FeatureStatus.ENABLED,
                targeting_type=TargetingType.ALL_USERS,
            ),
            FeatureFlag(
                name="beta_features",
                description="Enable beta features for testing",
                status=FeatureStatus.TESTING,
                targeting_type=TargetingType.USER_GROUPS,
                targeting_config={'user_groups': ['beta_testers', 'internal']},
            ),
            FeatureFlag(
                name="enhanced_caching",
                description="Enable enhanced caching mechanisms",
                status=FeatureStatus.DISABLED,
                targeting_type=TargetingType.ALL_USERS,
            ),
        ]
        
        for flag in default_flags:
            self.flags[flag.name] = flag
    
    def _load_flags_from_storage(self):
        """Load flags from storage (database, cache, etc.)."""
        # This would load from database or configuration
        # For now, use in-memory flags
        pass
    
    def create_flag(self, name: str, description: str, status: FeatureStatus = FeatureStatus.DISABLED,
                   targeting_type: TargetingType = TargetingType.ALL_USERS, 
                   targeting_config: Dict[str, Any] = None) -> FeatureFlag:
        """
        Create new feature flag.
        
        Args:
            name: Feature flag name
            description: Feature description
            status: Initial status
            targeting_type: Targeting type
            targeting_config: Targeting configuration
            
        Returns:
            Created feature flag
        """
        if name in self.flags:
            raise PostbackException(f"Feature flag {name} already exists")
        
        flag = FeatureFlag(
            name=name,
            description=description,
            status=status,
            targeting_type=targeting_type,
            targeting_config=targeting_config or {},
        )
        
        self.flags[name] = flag
        self._save_flag_to_storage(flag)
        
        self.logger.info(f"Created feature flag: {name}")
        return flag
    
    def update_flag(self, name: str, **kwargs) -> FeatureFlag:
        """
        Update feature flag.
        
        Args:
            name: Feature flag name
            **kwargs: Fields to update
            
        Returns:
            Updated feature flag
        """
        if name not in self.flags:
            raise PostbackException(f"Feature flag {name} not found")
        
        flag = self.flags[name]
        
        for field, value in kwargs.items():
            if hasattr(flag, field):
                setattr(flag, field, value)
        
        flag.updated_at = timezone.now()
        self._save_flag_to_storage(flag)
        
        self.logger.info(f"Updated feature flag: {name}")
        return flag
    
    def delete_flag(self, name: str) -> bool:
        """
        Delete feature flag.
        
        Args:
            name: Feature flag name
            
        Returns:
            True if deleted
        """
        if name not in self.flags:
            return False
        
        del self.flags[name]
        self._delete_flag_from_storage(name)
        
        self.logger.info(f"Deleted feature flag: {name}")
        return True
    
    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """
        Get feature flag by name.
        
        Args:
            name: Feature flag name
            
        Returns:
            Feature flag or None
        """
        return self.flags.get(name)
    
    def list_flags(self, status: FeatureStatus = None) -> List[FeatureFlag]:
        """
        List feature flags.
        
        Args:
            status: Filter by status
            
        Returns:
            List of feature flags
        """
        flags = list(self.flags.values())
        
        if status:
            flags = [flag for flag in flags if flag.status == status]
        
        return flags
    
    def is_enabled(self, name: str, context: Dict[str, Any] = None) -> bool:
        """
        Check if feature flag is enabled.
        
        Args:
            name: Feature flag name
            context: Evaluation context
            
        Returns:
            True if enabled
        """
        flag = self.get_flag(name)
        if not flag:
            return False
        
        return flag.is_enabled(context)
    
    def enable_flag(self, name: str) -> bool:
        """
        Enable feature flag.
        
        Args:
            name: Feature flag name
            
        Returns:
            True if enabled
        """
        flag = self.get_flag(name)
        if not flag:
            return False
        
        flag.enable()
        self._save_flag_to_storage(flag)
        
        self.logger.info(f"Enabled feature flag: {name}")
        return True
    
    def disable_flag(self, name: str) -> bool:
        """
        Disable feature flag.
        
        Args:
            name: Feature flag name
            
        Returns:
            True if disabled
        """
        flag = self.get_flag(name)
        if not flag:
            return False
        
        flag.disable()
        self._save_flag_to_storage(flag)
        
        self.logger.info(f"Disabled feature flag: {name}")
        return True
    
    def set_rollout(self, name: str, percentage: float) -> bool:
        """
        Set rollout percentage for feature flag.
        
        Args:
            name: Feature flag name
            percentage: Rollout percentage
            
        Returns:
            True if set
        """
        flag = self.get_flag(name)
        if not flag:
            return False
        
        flag.set_rollout(percentage)
        self._save_flag_to_storage(flag)
        
        self.logger.info(f"Set rollout for {name}: {percentage}%")
        return True
    
    def set_testing(self, name: str, targeting_type: TargetingType, targeting_config: Dict[str, Any]) -> bool:
        """
        Set testing configuration for feature flag.
        
        Args:
            name: Feature flag name
            targeting_type: Targeting type
            targeting_config: Targeting configuration
            
        Returns:
            True if set
        """
        flag = self.get_flag(name)
        if not flag:
            return False
        
        flag.set_testing(targeting_type, targeting_config)
        self._save_flag_to_storage(flag)
        
        self.logger.info(f"Set testing for {name}: {targeting_type.value}")
        return True
    
    def get_flag_statistics(self) -> Dict[str, Any]:
        """Get feature flag statistics."""
        total_flags = len(self.flags)
        enabled_flags = len([f for f in self.flags.values() if f.status == FeatureStatus.ENABLED])
        disabled_flags = len([f for f in self.flags.values() if f.status == FeatureStatus.DISABLED])
        rollout_flags = len([f for f in self.flags.values() if f.status == FeatureStatus.ROLLOUT])
        testing_flags = len([f for f in self.flags.values() if f.status == FeatureStatus.TESTING])
        
        targeting_types = {}
        for flag in self.flags.values():
            targeting_type = flag.targeting_type.value
            targeting_types[targeting_type] = targeting_types.get(targeting_type, 0) + 1
        
        return {
            'total_flags': total_flags,
            'enabled_flags': enabled_flags,
            'disabled_flags': disabled_flags,
            'rollout_flags': rollout_flags,
            'testing_flags': testing_flags,
            'targeting_types': targeting_types,
            'flags': [
                {
                    'name': flag.name,
                    'status': flag.status.value,
                    'targeting_type': flag.targeting_type.value,
                    'rollout_percentage': flag.rollout_percentage,
                    'created_at': flag.created_at.isoformat(),
                    'updated_at': flag.updated_at.isoformat(),
                }
                for flag in self.flags.values()
            ],
        }
    
    def _save_flag_to_storage(self, flag: FeatureFlag):
        """Save flag to storage."""
        cache_key = f"feature_flag_{flag.name}"
        cache.set(cache_key, flag.to_dict(), timeout=3600)  # 1 hour
    
    def _delete_flag_from_storage(self, name: str):
        """Delete flag from storage."""
        cache_key = f"feature_flag_{name}"
        cache.delete(cache_key)


class FeatureFlagDecorator:
    """
    Decorator for feature flag conditional execution.
    
    Allows functions to be conditionally executed based on feature flags.
    """
    
    def __init__(self, flag_name: str, fallback_return: Any = None, context_provider: Callable = None):
        """
        Initialize decorator.
        
        Args:
            flag_name: Feature flag name
            fallback_return: Return value when flag is disabled
            context_provider: Function to provide evaluation context
        """
        self.flag_name = flag_name
        self.fallback_return = fallback_return
        self.context_provider = context_provider
        self.manager = feature_flag_manager
    
    def __call__(self, func):
        """Decorator call."""
        def wrapper(*args, **kwargs):
            # Get context
            context = {}
            if self.context_provider:
                context = self.context_provider(*args, **kwargs)
            
            # Check if feature is enabled
            if self.manager.is_enabled(self.flag_name, context):
                return func(*args, **kwargs)
            else:
                return self.fallback_return
        
        return wrapper


# Global feature flag manager instance
feature_flag_manager = FeatureFlagManager()


# Convenience functions
def is_feature_enabled(flag_name: str, context: Dict[str, Any] = None) -> bool:
    """Check if feature flag is enabled."""
    return feature_flag_manager.is_enabled(flag_name, context)


def create_feature_flag(name: str, description: str, status: FeatureStatus = FeatureStatus.DISABLED,
                      targeting_type: TargetingType = TargetingType.ALL_USERS, 
                      targeting_config: Dict[str, Any] = None) -> FeatureFlag:
    """Create feature flag."""
    return feature_flag_manager.create_flag(name, description, status, targeting_type, targeting_config)


def enable_feature_flag(flag_name: str) -> bool:
    """Enable feature flag."""
    return feature_flag_manager.enable_flag(flag_name)


def disable_feature_flag(flag_name: str) -> bool:
    """Disable feature flag."""
    return feature_flag_manager.disable_flag(flag_name)


def set_feature_rollout(flag_name: str, percentage: float) -> bool:
    """Set feature rollout percentage."""
    return feature_flag_manager.set_rollout(flag_name, percentage)


def set_feature_testing(flag_name: str, targeting_type: TargetingType, targeting_config: Dict[str, Any]) -> bool:
    """Set feature testing configuration."""
    return feature_flag_manager.set_testing(flag_name, targeting_type, targeting_config)


def get_feature_flag_statistics() -> Dict[str, Any]:
    """Get feature flag statistics."""
    return feature_flag_manager.get_flag_statistics()


# Decorators
def feature_flag(flag_name: str, fallback_return: Any = None, context_provider: Callable = None):
    """
    Decorator for feature flag conditional execution.
    
    Args:
        flag_name: Feature flag name
        fallback_return: Return value when flag is disabled
        context_provider: Function to provide evaluation context
        
    Returns:
        Decorator function
    """
    return FeatureFlagDecorator(flag_name, fallback_return, context_provider)


def beta_feature(fallback_return: Any = None):
    """
    Decorator for beta features.
    
    Args:
        fallback_return: Return value when not in beta
        
    Returns:
        Decorator function
    """
    return feature_flag("beta_features", fallback_return)


def analytics_feature(fallback_return: Any = None):
    """
    Decorator for analytics features.
    
    Args:
        fallback_return: Return value when analytics is disabled
        
    Returns:
        Decorator function
    """
    return feature_flag("advanced_analytics", fallback_return)


def real_time_feature(fallback_return: Any = None):
    """
    Decorator for real-time features.
    
    Args:
        fallback_return: Return value when real-time is disabled
        
    Returns:
        Decorator function
    """
    return feature_flag("real_time_processing", fallback_return)


# Context providers
def user_context_provider(*args, **kwargs) -> Dict[str, Any]:
    """Provide user context for feature flag evaluation."""
    # Extract user from function arguments
    for arg in args:
        if hasattr(arg, 'user') and arg.user:
            return {'user': arg.user, 'user_id': arg.user.id}
        elif hasattr(arg, 'id') and isinstance(arg, User):
            return {'user': arg, 'user_id': arg.id}
    
    # Check kwargs for user
    if 'user' in kwargs:
        user = kwargs['user']
        return {'user': user, 'user_id': user.id}
    
    if 'request' in kwargs and hasattr(kwargs['request'], 'user'):
        user = kwargs['request'].user
        if user.is_authenticated:
            return {'user': user, 'user_id': user.id}
    
    return {}


def request_context_provider(*args, **kwargs) -> Dict[str, Any]:
    """Provide request context for feature flag evaluation."""
    context = {}
    
    # Extract request from arguments
    for arg in args:
        if hasattr(arg, 'META'):
            context['ip_address'] = arg.META.get('REMOTE_ADDR')
            context['user_agent'] = arg.META.get('HTTP_USER_AGENT')
            break
    
    # Check kwargs
    if 'request' in kwargs:
        request = kwargs['request']
        context['ip_address'] = request.META.get('REMOTE_ADDR')
        context['user_agent'] = request.META.get('HTTP_USER_AGENT')
    
    # Add user context
    user_context = user_context_provider(*args, **kwargs)
    context.update(user_context)
    
    return context


def postback_context_provider(*args, **kwargs) -> Dict[str, Any]:
    """Provide postback context for feature flag evaluation."""
    context = request_context_provider(*args, **kwargs)
    
    # Add postback-specific context
    if 'postback_data' in kwargs:
        postback_data = kwargs['postback_data']
        context['network_key'] = postback_data.get('network_key')
        context['lead_id'] = postback_data.get('lead_id')
        context['offer_id'] = postback_data.get('offer_id')
    
    return context


# Feature flag utilities
def evaluate_all_flags(context: Dict[str, Any] = None) -> Dict[str, bool]:
    """
    Evaluate all feature flags.
    
    Args:
        context: Evaluation context
        
    Returns:
        Dictionary of flag names to enabled status
    """
    results = {}
    
    for flag_name in feature_flag_manager.flags.keys():
        results[flag_name] = feature_flag_manager.is_enabled(flag_name, context)
    
    return results


def get_enabled_flags(context: Dict[str, Any] = None) -> List[str]:
    """
    Get list of enabled feature flags.
    
    Args:
        context: Evaluation context
        
    Returns:
        List of enabled flag names
    """
    enabled = []
    
    for flag_name, flag in feature_flag_manager.flags.items():
        if flag.is_enabled(context):
            enabled.append(flag_name)
    
    return enabled


def get_disabled_flags(context: Dict[str, Any] = None) -> List[str]:
    """
    Get list of disabled feature flags.
    
    Args:
        context: Evaluation context
        
    Returns:
        List of disabled flag names
    """
    disabled = []
    
    for flag_name, flag in feature_flag_manager.flags.items():
        if not flag.is_enabled(context):
            disabled.append(flag_name)
    
    return disabled


# Feature flag health check
def check_feature_flag_health() -> Dict[str, Any]:
    """Check feature flag system health."""
    health_status = {
        'overall': 'healthy',
        'feature_flag_manager': 'healthy',
        'flags': {},
        'issues': [],
    }
    
    # Test feature flag manager
    try:
        stats = feature_flag_manager.get_flag_statistics()
        health_status['feature_flag_manager'] = 'healthy'
        health_status['flags'] = {
            'total_flags': stats['total_flags'],
            'enabled_flags': stats['enabled_flags'],
            'disabled_flags': stats['disabled_flags'],
        }
    except Exception as e:
        health_status['feature_flag_manager'] = 'error'
        health_status['issues'].append(f"Feature flag manager error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
