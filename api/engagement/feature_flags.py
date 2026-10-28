# engagement/feature_flags.py
"""
Feature flag system for engagement gamification.
Provides dynamic feature toggling and A/B testing capabilities.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


class FeatureFlagType(Enum):
    """Types of feature flags."""
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    TENANT_LIST = "tenant_list"
    ENVIRONMENT = "environment"
    DATE_RANGE = "date_range"
    CONDITIONAL = "conditional"


class FeatureFlagStatus(Enum):
    """Status of feature flags."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"


@dataclass
class FeatureFlag:
    """Feature flag definition."""
    key: str
    name: str
    description: str
    flag_type: FeatureFlagType
    status: FeatureFlagStatus = FeatureFlagStatus.INACTIVE
    rollout_percentage: int = 0
    user_ids: Set[int] = field(default_factory=set)
    tenant_ids: Set[int] = field(default_factory=set)
    environments: List[str] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    
    def is_active(self) -> bool:
        """Check if feature flag is active."""
        return self.status == FeatureFlagStatus.ACTIVE
    
    def is_expired(self) -> bool:
        """Check if feature flag is expired."""
        if self.end_date and timezone.now() > self.end_date:
            return True
        return False
    
    def is_scheduled(self) -> bool:
        """Check if feature flag is scheduled for future activation."""
        if self.start_date and timezone.now() < self.start_date:
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert feature flag to dictionary."""
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'flag_type': self.flag_type.value,
            'status': self.status.value,
            'rollout_percentage': self.rollout_percentage,
            'user_ids': list(self.user_ids),
            'tenant_ids': list(self.tenant_ids),
            'environments': self.environments,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'conditions': self.conditions,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class BaseFeatureEvaluator(ABC):
    """Base class for feature flag evaluators."""
    
    @abstractmethod
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate feature flag for given context."""
        pass


class BooleanEvaluator(BaseFeatureEvaluator):
    """Evaluator for boolean feature flags."""
    
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate boolean feature flag."""
        return flag.is_active()


class PercentageEvaluator(BaseFeatureEvaluator):
    """Evaluator for percentage-based feature flags."""
    
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate percentage feature flag."""
        if not flag.is_active():
            return False
        
        user_id = context.get('user_id')
        if not user_id:
            return False
        
        # Use user ID to determine if user falls within rollout percentage
        hash_value = hash(f"{flag.key}_{user_id}") % 100
        return hash_value < flag.rollout_percentage


class UserListEvaluator(BaseFeatureEvaluator):
    """Evaluator for user list feature flags."""
    
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate user list feature flag."""
        if not flag.is_active():
            return False
        
        user_id = context.get('user_id')
        if not user_id:
            return False
        
        return user_id in flag.user_ids


class TenantListEvaluator(BaseFeatureEvaluator):
    """Evaluator for tenant list feature flags."""
    
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate tenant list feature flag."""
        if not flag.is_active():
            return False
        
        tenant_id = context.get('tenant_id')
        if not tenant_id:
            return False
        
        return tenant_id in flag.tenant_ids


class EnvironmentEvaluator(BaseFeatureEvaluator):
    """Evaluator for environment-based feature flags."""
    
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate environment feature flag."""
        if not flag.is_active():
            return False
        
        current_env = getattr(settings, 'ENVIRONMENT', 'development')
        return current_env in flag.environments


class DateRangeEvaluator(BaseFeatureEvaluator):
    """Evaluator for date range feature flags."""
    
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate date range feature flag."""
        if not flag.is_active():
            return False
        
        now = timezone.now()
        
        # Check start date
        if flag.start_date and now < flag.start_date:
            return False
        
        # Check end date
        if flag.end_date and now > flag.end_date:
            return False
        
        return True


class ConditionalEvaluator(BaseFeatureEvaluator):
    """Evaluator for conditional feature flags."""
    
    def evaluate(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """Evaluate conditional feature flag."""
        if not flag.is_active():
            return False
        
        conditions = flag.conditions
        if not conditions:
            return True
        
        return self._evaluate_conditions(conditions, context)
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate complex conditions."""
        for condition_key, condition_value in conditions.items():
            if condition_key not in context:
                return False
            
            context_value = context[condition_key]
            
            # Handle different condition types
            if isinstance(condition_value, dict):
                if not self._evaluate_complex_condition(condition_value, context_value):
                    return False
            elif context_value != condition_value:
                return False
        
        return True
    
    def _evaluate_complex_condition(self, condition: Dict[str, Any], value: Any) -> bool:
        """Evaluate complex condition."""
        operator = condition.get('operator', 'equals')
        expected = condition.get('value')
        
        if operator == 'equals':
            return value == expected
        elif operator == 'not_equals':
            return value != expected
        elif operator == 'greater_than':
            return value > expected
        elif operator == 'less_than':
            return value < expected
        elif operator == 'greater_equal':
            return value >= expected
        elif operator == 'less_equal':
            return value <= expected
        elif operator == 'in':
            return value in expected
        elif operator == 'not_in':
            return value not in expected
        elif operator == 'contains':
            return expected in str(value)
        elif operator == 'regex':
            import re
            pattern = condition.get('pattern', '')
            return bool(re.match(pattern, str(value)))
        
        return False


class FeatureFlagManager:
    """Manager for feature flags."""
    
    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {}
        self.evaluators = {
            FeatureFlagType.BOOLEAN: BooleanEvaluator(),
            FeatureFlagType.PERCENTAGE: PercentageEvaluator(),
            FeatureFlagType.USER_LIST: UserListEvaluator(),
            FeatureFlagType.TENANT_LIST: TenantListEvaluator(),
            FeatureFlagType.ENVIRONMENT: EnvironmentEvaluator(),
            FeatureFlagType.DATE_RANGE: DateRangeEvaluator(),
            FeatureFlagType.CONDITIONAL: ConditionalEvaluator(),
        }
        self._load_default_flags()
    
    def _load_default_flags(self):
        """Load default feature flags."""
        default_flags = [
            FeatureFlag(
                key="daily_checkin_enabled",
                name="Daily Check-in",
                description="Enable daily check-in functionality",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ACTIVE
            ),
            FeatureFlag(
                key="spin_wheel_enabled",
                name="Spin Wheel",
                description="Enable spin wheel functionality",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ACTIVE
            ),
            FeatureFlag(
                key="achievements_enabled",
                name="Achievements",
                description="Enable achievements system",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ACTIVE
            ),
            FeatureFlag(
                key="leaderboard_enabled",
                name="Leaderboard",
                description="Enable leaderboard functionality",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ACTIVE
            ),
            FeatureFlag(
                key="shop_enabled",
                name="Shop",
                description="Enable shop functionality",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ACTIVE
            ),
            FeatureFlag(
                key="quests_enabled",
                name="Quests",
                description="Enable quests system",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ACTIVE
            ),
            FeatureFlag(
                key="notifications_enabled",
                name="Notifications",
                description="Enable notification system",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ACTIVE
            ),
            FeatureFlag(
                key="social_features_enabled",
                name="Social Features",
                description="Enable social features (friends, feed, etc.)",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.INACTIVE
            ),
            FeatureFlag(
                key="referral_system_enabled",
                name="Referral System",
                description="Enable referral system",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.INACTIVE
            ),
            FeatureFlag(
                key="premium_features_enabled",
                name="Premium Features",
                description="Enable premium features for selected users",
                flag_type=FeatureFlagType.USER_LIST,
                status=FeatureFlagStatus.ACTIVE,
                user_ids=set()  # Will be populated with premium user IDs
            ),
            FeatureFlag(
                key="beta_features_enabled",
                name="Beta Features",
                description="Enable beta features for percentage of users",
                flag_type=FeatureFlagType.PERCENTAGE,
                status=FeatureFlagStatus.INACTIVE,
                rollout_percentage=10
            ),
            FeatureFlag(
                key="seasonal_events_enabled",
                name="Seasonal Events",
                description="Enable seasonal events during specific dates",
                flag_type=FeatureFlagType.DATE_RANGE,
                status=FeatureFlagStatus.INACTIVE,
                start_date=timezone.now() + timedelta(days=30),  # Start in 30 days
                end_date=timezone.now() + timedelta(days=60)    # End in 60 days
            ),
            FeatureFlag(
                key="analytics_enabled",
                name="Analytics",
                description="Enable analytics tracking",
                flag_type=FeatureFlagType.ENVIRONMENT,
                status=FeatureFlagStatus.ACTIVE,
                environments=['production', 'staging']
            ),
            FeatureFlag(
                key="debug_mode_enabled",
                name="Debug Mode",
                description="Enable debug mode for developers",
                flag_type=FeatureFlagType.CONDITIONAL,
                status=FeatureFlagStatus.INACTIVE,
                conditions={
                    'user_role': {'operator': 'in', 'value': ['admin', 'developer']},
                    'environment': {'operator': 'in', 'value': ['development', 'testing']}
                }
            ),
        ]
        
        for flag in default_flags:
            self.flags[flag.key] = flag
    
    def is_enabled(self, flag_key: str, user=None, tenant=None, context: Dict[str, Any] = None) -> bool:
        """Check if a feature flag is enabled."""
        flag = self.flags.get(flag_key)
        if not flag:
            return False
        
        # Check if flag is active
        if not flag.is_active():
            return False
        
        # Check if flag is expired
        if flag.is_expired():
            return False
        
        # Check if flag is scheduled for future
        if flag.is_scheduled():
            return False
        
        # Build evaluation context
        eval_context = {
            'flag_key': flag_key,
            'flag_type': flag.flag_type.value,
            'timestamp': timezone.now().isoformat(),
        }
        
        if user:
            eval_context.update({
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined.isoformat(),
                'has_premium': getattr(user, 'has_premium', False),
                'user_role': getattr(user, 'role', 'user'),
            })
        
        if tenant:
            eval_context.update({
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'tenant_slug': tenant.slug,
            })
        
        if context:
            eval_context.update(context)
        
        # Evaluate flag
        evaluator = self.evaluators.get(flag.flag_type)
        if evaluator:
            return evaluator.evaluate(flag, eval_context)
        
        return False
    
    def add_flag(self, flag: FeatureFlag) -> bool:
        """Add a new feature flag."""
        if flag.key in self.flags:
            return False
        
        self.flags[flag.key] = flag
        self._cache_flag(flag)
        return True
    
    def update_flag(self, flag_key: str, **kwargs) -> bool:
        """Update an existing feature flag."""
        flag = self.flags.get(flag_key)
        if not flag:
            return False
        
        # Update flag properties
        for key, value in kwargs.items():
            if hasattr(flag, key):
                setattr(flag, key, value)
        
        flag.updated_at = timezone.now()
        self._cache_flag(flag)
        return True
    
    def remove_flag(self, flag_key: str) -> bool:
        """Remove a feature flag."""
        if flag_key not in self.flags:
            return False
        
        del self.flags[flag_key]
        cache.delete(f"feature_flag:{flag_key}")
        return True
    
    def get_flag(self, flag_key: str) -> Optional[FeatureFlag]:
        """Get a feature flag by key."""
        return self.flags.get(flag_key)
    
    def list_flags(self, status: Optional[FeatureFlagStatus] = None, 
                  flag_type: Optional[FeatureFlagType] = None) -> List[FeatureFlag]:
        """List feature flags with optional filtering."""
        flags = list(self.flags.values())
        
        if status:
            flags = [f for f in flags if f.status == status]
        
        if flag_type:
            flags = [f for f in flags if f.flag_type == flag_type]
        
        return flags
    
    def get_user_flags(self, user) -> Dict[str, bool]:
        """Get all feature flags enabled for a user."""
        user_flags = {}
        
        for flag_key, flag in self.flags.items():
            user_flags[flag_key] = self.is_enabled(flag_key, user=user)
        
        return user_flags
    
    def get_tenant_flags(self, tenant) -> Dict[str, bool]:
        """Get all feature flags enabled for a tenant."""
        tenant_flags = {}
        
        for flag_key, flag in self.flags.items():
            tenant_flags[flag_key] = self.is_enabled(flag_key, tenant=tenant)
        
        return tenant_flags
    
    def enable_flag(self, flag_key: str) -> bool:
        """Enable a feature flag."""
        return self.update_flag(flag_key, status=FeatureFlagStatus.ACTIVE)
    
    def disable_flag(self, flag_key: str) -> bool:
        """Disable a feature flag."""
        return self.update_flag(flag_key, status=FeatureFlagStatus.INACTIVE)
    
    def archive_flag(self, flag_key: str) -> bool:
        """Archive a feature flag."""
        return self.update_flag(flag_key, status=FeatureFlagStatus.ARCHIVED)
    
    def set_rollout_percentage(self, flag_key: str, percentage: int) -> bool:
        """Set rollout percentage for a feature flag."""
        if not (0 <= percentage <= 100):
            return False
        
        return self.update_flag(flag_key, rollout_percentage=percentage)
    
    def add_user_to_flag(self, flag_key: str, user_id: int) -> bool:
        """Add user to feature flag whitelist."""
        flag = self.flags.get(flag_key)
        if not flag or flag.flag_type != FeatureFlagType.USER_LIST:
            return False
        
        flag.user_ids.add(user_id)
        flag.updated_at = timezone.now()
        self._cache_flag(flag)
        return True
    
    def remove_user_from_flag(self, flag_key: str, user_id: int) -> bool:
        """Remove user from feature flag whitelist."""
        flag = self.flags.get(flag_key)
        if not flag or flag.flag_type != FeatureFlagType.USER_LIST:
            return False
        
        flag.user_ids.discard(user_id)
        flag.updated_at = timezone.now()
        self._cache_flag(flag)
        return True
    
    def add_tenant_to_flag(self, flag_key: str, tenant_id: int) -> bool:
        """Add tenant to feature flag whitelist."""
        flag = self.flags.get(flag_key)
        if not flag or flag.flag_type != FeatureFlagType.TENANT_LIST:
            return False
        
        flag.tenant_ids.add(tenant_id)
        flag.updated_at = timezone.now()
        self._cache_flag(flag)
        return True
    
    def remove_tenant_from_flag(self, flag_key: str, tenant_id: int) -> bool:
        """Remove tenant from feature flag whitelist."""
        flag = self.flags.get(flag_key)
        if not flag or flag.flag_type != FeatureFlagType.TENANT_LIST:
            return False
        
        flag.tenant_ids.discard(tenant_id)
        flag.updated_at = timezone.now()
        self._cache_flag(flag)
        return True
    
    def _cache_flag(self, flag: FeatureFlag):
        """Cache feature flag."""
        cache_key = f"feature_flag:{flag.key}"
        cache.set(cache_key, flag.to_dict(), timeout=300)
    
    def _load_cached_flags(self):
        """Load feature flags from cache."""
        # This would load flags from cache or database
        # For now, flags are loaded in memory
        pass
    
    def get_flag_statistics(self) -> Dict[str, Any]:
        """Get feature flag statistics."""
        total_flags = len(self.flags)
        active_flags = len([f for f in self.flags.values() if f.is_active()])
        expired_flags = len([f for f in self.flags.values() if f.is_expired()])
        scheduled_flags = len([f for f in self.flags.values() if f.is_scheduled()])
        
        flags_by_type = {}
        for flag_type in FeatureFlagType:
            flags_by_type[flag_type.value] = len([
                f for f in self.flags.values() 
                if f.flag_type == flag_type
            ])
        
        flags_by_status = {}
        for status in FeatureFlagStatus:
            flags_by_status[status.value] = len([
                f for f in self.flags.values() 
                if f.status == status
            ])
        
        return {
            'total_flags': total_flags,
            'active_flags': active_flags,
            'expired_flags': expired_flags,
            'scheduled_flags': scheduled_flags,
            'flags_by_type': flags_by_type,
            'flags_by_status': flags_by_status,
        }


# Global feature flag manager instance
feature_flag_manager = FeatureFlagManager()


# ── Feature Flag Decorators ─────────────────────────────────────────────────────

def feature_flag(flag_key: str, fallback_value: Any = False):
    """Decorator to check feature flag before executing function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get user from kwargs or function arguments
            user = None
            tenant = None
            
            # Check if user is in kwargs
            if 'user' in kwargs:
                user = kwargs['user']
            elif 'request' in kwargs:
                user = kwargs['request'].user
            
            # Check if tenant is in kwargs
            if 'tenant' in kwargs:
                tenant = kwargs['tenant']
            elif 'request' in kwargs:
                tenant = getattr(kwargs['request'].user, 'tenant', None)
            
            # Check feature flag
            if feature_flag_manager.is_enabled(flag_key, user=user, tenant=tenant):
                return func(*args, **kwargs)
            elif fallback_value is not None:
                return fallback_value
            
            # Return None or raise exception
            return None
        
        return wrapper
    return decorator


def require_feature_flag(flag_key: str, error_message: str = None):
    """Decorator to require feature flag to be enabled."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get user from kwargs or function arguments
            user = None
            tenant = None
            
            # Check if user is in kwargs
            if 'user' in kwargs:
                user = kwargs['user']
            elif 'request' in kwargs:
                user = kwargs['request'].user
            
            # Check if tenant is in kwargs
            if 'tenant' in kwargs:
                tenant = kwargs['tenant']
            elif 'request' in kwargs:
                tenant = getattr(kwargs['request'].user, 'tenant', None)
            
            # Check feature flag
            if not feature_flag_manager.is_enabled(flag_key, user=user, tenant=tenant):
                error_msg = error_message or f"Feature {flag_key} is not enabled"
                raise ValueError(error_msg)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def conditional_feature_flag(flag_key: str, enabled_func: callable, disabled_func: callable):
    """Decorator to execute different functions based on feature flag."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get user from kwargs or function arguments
            user = None
            tenant = None
            
            # Check if user is in kwargs
            if 'user' in kwargs:
                user = kwargs['user']
            elif 'request' in kwargs:
                user = kwargs['request'].user
            
            # Check if tenant is in kwargs
            if 'tenant' in kwargs:
                tenant = kwargs['tenant']
            elif 'request' in kwargs:
                tenant = getattr(kwargs['request'].user, 'tenant', None)
            
            # Check feature flag and execute appropriate function
            if feature_flag_manager.is_enabled(flag_key, user=user, tenant=tenant):
                return enabled_func(*args, **kwargs)
            else:
                return disabled_func(*args, **kwargs)
        
        return wrapper
    return decorator


# ── Feature Flag Utilities ─────────────────────────────────────────────────────

class FeatureFlagUtils:
    """Utility functions for feature flags."""
    
    @staticmethod
    def create_flag(key: str, name: str, description: str, 
                   flag_type: FeatureFlagType, **kwargs) -> FeatureFlag:
        """Create a new feature flag."""
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=flag_type,
            **kwargs
        )
    
    @staticmethod
    def create_boolean_flag(key: str, name: str, description: str, 
                           enabled: bool = False, **kwargs) -> FeatureFlag:
        """Create a boolean feature flag."""
        status = FeatureFlagStatus.ACTIVE if enabled else FeatureFlagStatus.INACTIVE
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=FeatureFlagType.BOOLEAN,
            status=status,
            **kwargs
        )
    
    @staticmethod
    def create_percentage_flag(key: str, name: str, description: str, 
                             rollout_percentage: int = 0, **kwargs) -> FeatureFlag:
        """Create a percentage-based feature flag."""
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=FeatureFlagType.PERCENTAGE,
            rollout_percentage=rollout_percentage,
            **kwargs
        )
    
    @staticmethod
    def create_user_list_flag(key: str, name: str, description: str, 
                              user_ids: List[int] = None, **kwargs) -> FeatureFlag:
        """Create a user list feature flag."""
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=FeatureFlagType.USER_LIST,
            user_ids=set(user_ids or []),
            **kwargs
        )
    
    @staticmethod
    def create_tenant_list_flag(key: str, name: str, description: str, 
                                tenant_ids: List[int] = None, **kwargs) -> FeatureFlag:
        """Create a tenant list feature flag."""
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=FeatureFlagType.TENANT_LIST,
            tenant_ids=set(tenant_ids or []),
            **kwargs
        )
    
    @staticmethod
    def create_environment_flag(key: str, name: str, description: str, 
                               environments: List[str] = None, **kwargs) -> FeatureFlag:
        """Create an environment-based feature flag."""
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=FeatureFlagType.ENVIRONMENT,
            environments=environments or [],
            **kwargs
        )
    
    @staticmethod
    def create_date_range_flag(key: str, name: str, description: str, 
                               start_date: datetime = None, end_date: datetime = None, **kwargs) -> FeatureFlag:
        """Create a date range feature flag."""
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=FeatureFlagType.DATE_RANGE,
            start_date=start_date,
            end_date=end_date,
            **kwargs
        )
    
    @staticmethod
    def create_conditional_flag(key: str, name: str, description: str, 
                                conditions: Dict[str, Any] = None, **kwargs) -> FeatureFlag:
        """Create a conditional feature flag."""
        return FeatureFlag(
            key=key,
            name=name,
            description=description,
            flag_type=FeatureFlagType.CONDITIONAL,
            conditions=conditions or {},
            **kwargs
        )
    
    @staticmethod
    def export_flags(flags: List[FeatureFlag] = None) -> str:
        """Export feature flags to JSON."""
        if flags is None:
            flags = list(feature_flag_manager.flags.values())
        
        return json.dumps([flag.to_dict() for flag in flags], indent=2)
    
    @staticmethod
    def import_flags(json_data: str) -> int:
        """Import feature flags from JSON."""
        try:
            data = json.loads(json_data)
            imported_count = 0
            
            for flag_data in data:
                flag = FeatureFlag(
                    key=flag_data['key'],
                    name=flag_data['name'],
                    description=flag_data['description'],
                    flag_type=FeatureFlagType(flag_data['flag_type']),
                    status=FeatureFlagStatus(flag_data['status']),
                    rollout_percentage=flag_data.get('rollout_percentage', 0),
                    user_ids=set(flag_data.get('user_ids', [])),
                    tenant_ids=set(flag_data.get('tenant_ids', [])),
                    environments=flag_data.get('environments', []),
                    start_date=datetime.fromisoformat(flag_data['start_date']) if flag_data.get('start_date') else None,
                    end_date=datetime.fromisoformat(flag_data['end_date']) if flag_data.get('end_date') else None,
                    conditions=flag_data.get('conditions', {}),
                    metadata=flag_data.get('metadata', {}),
                    created_at=datetime.fromisoformat(flag_data['created_at']),
                    updated_at=datetime.fromisoformat(flag_data['updated_at']),
                )
                
                if feature_flag_manager.add_flag(flag):
                    imported_count += 1
            
            return imported_count
            
        except Exception as exc:
            logger.error(f"Failed to import feature flags: {exc}")
            return 0
    
    @staticmethod
    def validate_flag(flag: FeatureFlag) -> List[str]:
        """Validate feature flag configuration."""
        errors = []
        
        # Validate key
        if not flag.key or not flag.key.replace('_', '').replace('-', '').isalnum():
            errors.append("Flag key must contain only alphanumeric characters, hyphens, and underscores")
        
        # Validate rollout percentage
        if flag.flag_type == FeatureFlagType.PERCENTAGE:
            if not (0 <= flag.rollout_percentage <= 100):
                errors.append("Rollout percentage must be between 0 and 100")
        
        # Validate date range
        if flag.flag_type == FeatureFlagType.DATE_RANGE:
            if flag.start_date and flag.end_date and flag.start_date >= flag.end_date:
                errors.append("Start date must be before end date")
        
        # Validate conditions
        if flag.flag_type == FeatureFlagType.CONDITIONAL and not flag.conditions:
            errors.append("Conditional flags must have at least one condition")
        
        return errors


# ── Feature Flag Middleware ─────────────────────────────────────────────────────

class FeatureFlagMiddleware:
    """Middleware to add feature flags to request context."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Add feature flags to request
        request.feature_flags = {}
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.feature_flags = feature_flag_manager.get_user_flags(request.user)
        
        response = self.get_response(request)
        return response


# ── Feature Flag Management Commands ─────────────────────────────────────────────

class FeatureFlagCommands:
    """Management commands for feature flags."""
    
    @staticmethod
    def list_flags():
        """List all feature flags."""
        flags = feature_flag_manager.list_flags()
        
        print(f"Total flags: {len(flags)}")
        print("\nFeature Flags:")
        print("-" * 80)
        
        for flag in sorted(flags, key=lambda f: f.key):
            status_icon = "✅" if flag.is_active() else "❌"
            print(f"{status_icon} {flag.key:30} | {flag.flag_type.value:15} | {flag.status.value:10}")
            print(f"    {flag.description}")
        
        print("\nStatistics:")
        stats = feature_flag_manager.get_flag_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    @staticmethod
    def enable_flag(flag_key: str):
        """Enable a feature flag."""
        if feature_flag_manager.enable_flag(flag_key):
            print(f"✅ Feature flag '{flag_key}' enabled successfully")
        else:
            print(f"❌ Feature flag '{flag_key}' not found")
    
    @staticmethod
    def disable_flag(flag_key: str):
        """Disable a feature flag."""
        if feature_flag_manager.disable_flag(flag_key):
            print(f"❌ Feature flag '{flag_key}' disabled successfully")
        else:
            print(f"❌ Feature flag '{flag_key}' not found")
    
    @staticmethod
    def check_flag(flag_key: str, user_id: int = None):
        """Check if a feature flag is enabled."""
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                print(f"❌ User with ID {user_id} not found")
                return
        
        enabled = feature_flag_manager.is_enabled(flag_key, user=user)
        status = "✅ Enabled" if enabled else "❌ Disabled"
        
        print(f"Feature flag '{flag_key}': {status}")
        
        if user:
            print(f"User: {user.username} (ID: {user.id})")
    
    @staticmethod
    def export_flags(output_file: str = None):
        """Export feature flags to file."""
        json_data = FeatureFlagUtils.export_flags()
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(json_data)
            print(f"✅ Feature flags exported to {output_file}")
        else:
            print(json_data)
    
    @staticmethod
    def import_flags(input_file: str):
        """Import feature flags from file."""
        try:
            with open(input_file, 'r') as f:
                json_data = f.read()
            
            count = FeatureFlagUtils.import_flags(json_data)
            print(f"✅ Imported {count} feature flags from {input_file}")
            
        except FileNotFoundError:
            print(f"❌ File {input_file} not found")
        except Exception as exc:
            print(f"❌ Failed to import flags: {exc}")
