"""
Security Feature Flags Module
Feature flag management for security features
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from django.core.cache import cache
from django.conf import settings

from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.feature_flags')


class FeatureFlagType:
    """Feature flag types"""
    BOOLEAN = 'boolean'
    PERCENTAGE = 'percentage'
    WHITELIST = 'whitelist'
    BLACKLIST = 'blacklist'
    CONDITIONAL = 'conditional'


class FeatureFlagStatus:
    """Feature flag status"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ARCHIVED = 'archived'
    TESTING = 'testing'


class FeatureFlag(models.Model):
    """Feature flag model for security features"""
    
    id = models.UUIDField(primary_key=True, default=SecurityUtils.generate_uuid)
    key = models.CharField(max_length=100, unique=True, help_text="Unique key for the feature flag")
    name = models.CharField(max_length=200, help_text="Human-readable name")
    description = models.TextField(blank=True, help_text="Description of the feature")
    
    # Flag configuration
    flag_type = models.CharField(max_length=20, choices=[
        (FeatureFlagType.BOOLEAN, 'Boolean'),
        (FeatureFlagType.PERCENTAGE, 'Percentage'),
        (FeatureFlagType.WHITELIST, 'Whitelist'),
        (FeatureFlagType.BLACKLIST, 'Blacklist'),
        (FeatureFlagType.CONDITIONAL, 'Conditional'),
    ])
    
    status = models.CharField(max_length=20, choices=[
        (FeatureFlagStatus.ACTIVE, 'Active'),
        (FeatureFlagStatus.INACTIVE, 'Inactive'),
        (FeatureFlagStatus.ARCHIVED, 'Archived'),
        (FeatureFlagStatus.TESTING, 'Testing'),
    ], default=FeatureFlagStatus.INACTIVE)
    
    # Boolean flag value
    enabled = models.BooleanField(default=False)
    
    # Percentage flag value
    percentage = models.IntegerField(default=0, help_text="Percentage of users (0-100)")
    
    # List flag values
    whitelist_users = models.ManyToManyField(User, blank=True, related_name='whitelisted_flags')
    blacklist_users = models.ManyToManyField(User, blank=True, related_name='blacklisted_flags')
    whitelist_ips = models.JSONField(default=list, blank=True, help_text="List of whitelisted IP addresses")
    blacklist_ips = models.JSONField(default=list, blank=True, help_text="List of blacklisted IP addresses")
    
    # Conditional flag configuration
    conditions = models.JSONField(default=dict, blank=True, help_text="Conditions for conditional flags")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_flags')
    metadata = models.JSONField(default=dict, blank=True)
    
    # Rollout configuration
    rollout_percentage = models.IntegerField(default=0, help_text="Rollout percentage (0-100)")
    rollout_start_time = models.DateTimeField(null=True, blank=True)
    rollout_end_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'security_feature_flags'
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"
        ordering = ['key']
        indexes = [
            models.Index(fields=['key', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['flag_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.key} - {self.name}"
    
    def is_enabled_for_user(self, user: User, ip_address: str = None) -> bool:
        """Check if feature is enabled for specific user"""
        if self.status != FeatureFlagStatus.ACTIVE:
            return False
        
        # Check rollout timing
        if not self._is_in_rollout_window():
            return False
        
        # Check based on flag type
        if self.flag_type == FeatureFlagType.BOOLEAN:
            return self.enabled
        
        elif self.flag_type == FeatureFlagType.PERCENTAGE:
            return self._check_percentage_for_user(user)
        
        elif self.flag_type == FeatureFlagType.WHITELIST:
            return self._check_whitelist_for_user(user, ip_address)
        
        elif self.flag_type == FeatureFlagType.BLACKLIST:
            return not self._check_blacklist_for_user(user, ip_address)
        
        elif self.flag_type == FeatureFlagType.CONDITIONAL:
            return self._check_conditions_for_user(user, ip_address)
        
        return False
    
    def _is_in_rollout_window(self) -> bool:
        """Check if current time is within rollout window"""
        now = timezone.now()
        
        if self.rollout_start_time and now < self.rollout_start_time:
            return False
        
        if self.rollout_end_time and now > self.rollout_end_time:
            return False
        
        return True
    
    def _check_percentage_for_user(self, user: User) -> bool:
        """Check percentage-based flag for user"""
        if not user.id:
            return False
        
        # Use consistent hashing for percentage distribution
        user_hash = hash(f"{self.key}:{user.id}") % 100
        return user_hash < self.percentage
    
    def _check_whitelist_for_user(self, user: User, ip_address: str) -> bool:
        """Check whitelist-based flag"""
        # Check user whitelist
        if user and self.whitelist_users.filter(id=user.id).exists():
            return True
        
        # Check IP whitelist
        if ip_address and ip_address in self.whitelist_ips:
            return True
        
        return False
    
    def _check_blacklist_for_user(self, user: User, ip_address: str) -> bool:
        """Check blacklist-based flag"""
        # Check user blacklist
        if user and self.blacklist_users.filter(id=user.id).exists():
            return True
        
        # Check IP blacklist
        if ip_address and ip_address in self.blacklist_ips:
            return True
        
        return False
    
    def _check_conditions_for_user(self, user: User, ip_address: str) -> bool:
        """Check conditional-based flag"""
        conditions = self.conditions
        
        # User-based conditions
        if user:
            # User role conditions
            if 'user_roles' in conditions:
                user_roles = conditions['user_roles']
                if user.is_staff and 'staff' not in user_roles:
                    return False
                if user.is_superuser and 'superuser' not in user_roles:
                    return False
                if not user.is_staff and 'regular' not in user_roles:
                    return False
            
            # User date conditions
            if 'user_created_after' in conditions:
                cutoff_date = timezone.now() - timedelta(days=conditions['user_created_after'])
                if user.date_joined < cutoff_date:
                    return False
            
            # User activity conditions
            if 'min_login_count' in conditions:
                # This would require tracking login counts
                pass
        
        # IP-based conditions
        if ip_address:
            # IP range conditions
            if 'allowed_ip_ranges' in conditions:
                ip_allowed = False
                for ip_range in conditions['allowed_ip_ranges']:
                    if SecurityUtils.is_ip_in_range(ip_address, ip_range):
                        ip_allowed = True
                        break
                if not ip_allowed:
                    return False
            
            # Geographic conditions
            if 'allowed_countries' in conditions:
                geo_data = SecurityUtils.get_ip_geolocation(ip_address)
                country = geo_data.get('country', '')
                if country not in conditions['allowed_countries']:
                    return False
        
        # Time-based conditions
        if 'time_windows' in conditions:
            current_hour = timezone.now().hour
            allowed_hours = conditions['time_windows']
            if current_hour not in allowed_hours:
                return False
        
        # Default to enabled if no conditions block it
        return True
    
    def get_rollout_status(self) -> Dict[str, Any]:
        """Get rollout status"""
        now = timezone.now()
        
        status = {
            'current_percentage': self.rollout_percentage,
            'is_active': self.status == FeatureFlagStatus.ACTIVE,
            'in_rollout_window': self._is_in_rollout_window(),
            'rollout_started': self.rollout_start_time and now >= self.rollout_start_time,
            'rollout_ended': self.rollout_end_time and now >= self.rollout_end_time,
        }
        
        if self.rollout_start_time:
            status['rollout_start_time'] = self.rollout_start_time.isoformat()
        
        if self.rollout_end_time:
            status['rollout_end_time'] = self.rollout_end_time.isoformat()
        
        return status


class FeatureFlagManager:
    """Manager for feature flags"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self._flags_cache = {}
    
    def get_flag(self, key: str) -> Optional[FeatureFlag]:
        """Get feature flag by key"""
        cache_key = f"feature_flag_{key}"
        
        # Try cache first
        cached_flag = cache.get(cache_key)
        if cached_flag:
            return cached_flag
        
        # Get from database
        try:
            flag = FeatureFlag.objects.select_related('created_by').prefetch_related(
                'whitelist_users', 'blacklist_users'
            ).get(key=key)
            
            # Cache the flag
            cache.set(cache_key, flag, self.cache_timeout)
            return flag
            
        except FeatureFlag.DoesNotExist:
            return None
    
    def is_enabled(self, key: str, user: User = None, ip_address: str = None) -> bool:
        """Check if feature flag is enabled"""
        flag = self.get_flag(key)
        if not flag:
            return False
        
        return flag.is_enabled_for_user(user, ip_address)
    
    def create_flag(self, key: str, name: str, flag_type: str, **kwargs) -> FeatureFlag:
        """Create a new feature flag"""
        flag = FeatureFlag.objects.create(
            key=key,
            name=name,
            flag_type=flag_type,
            **kwargs
        )
        
        # Clear cache
        self._clear_flag_cache(key)
        
        logger.info(f"Created feature flag: {key}")
        return flag
    
    def update_flag(self, key: str, **kwargs) -> bool:
        """Update feature flag"""
        try:
            flag = self.get_flag(key)
            if not flag:
                return False
            
            for field, value in kwargs.items():
                if hasattr(flag, field):
                    setattr(flag, field, value)
            
            flag.save()
            
            # Clear cache
            self._clear_flag_cache(key)
            
            logger.info(f"Updated feature flag: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating feature flag {key}: {e}")
            return False
    
    def delete_flag(self, key: str) -> bool:
        """Delete feature flag"""
        try:
            flag = self.get_flag(key)
            if not flag:
                return False
            
            flag.delete()
            
            # Clear cache
            self._clear_flag_cache(key)
            
            logger.info(f"Deleted feature flag: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting feature flag {key}: {e}")
            return False
    
    def activate_flag(self, key: str) -> bool:
        """Activate feature flag"""
        return self.update_flag(key, status=FeatureFlagStatus.ACTIVE)
    
    def deactivate_flag(self, key: str) -> bool:
        """Deactivate feature flag"""
        return self.update_flag(key, status=FeatureFlagStatus.INACTIVE)
    
    def archive_flag(self, key: str) -> bool:
        """Archive feature flag"""
        return self.update_flag(key, status=FeatureFlagStatus.ARCHIVED)
    
    def get_all_flags(self, status: str = None) -> List[FeatureFlag]:
        """Get all feature flags"""
        queryset = FeatureFlag.objects.all()
        
        if status:
            queryset = queryset.filter(status=status)
        
        return list(queryset)
    
    def get_active_flags(self) -> List[FeatureFlag]:
        """Get all active flags"""
        return self.get_all_flags(FeatureFlagStatus.ACTIVE)
    
    def get_user_enabled_flags(self, user: User, ip_address: str = None) -> List[Dict[str, Any]]:
        """Get all flags enabled for user"""
        enabled_flags = []
        
        for flag in self.get_active_flags():
            if flag.is_enabled_for_user(user, ip_address):
                enabled_flags.append({
                    'key': flag.key,
                    'name': flag.name,
                    'type': flag.flag_type,
                    'description': flag.description
                })
        
        return enabled_flags
    
    def rollout_flag(self, key: str, percentage: int, duration_hours: int = None) -> bool:
        """Start or update flag rollout"""
        try:
            flag = self.get_flag(key)
            if not flag:
                return False
            
            updates = {
                'rollout_percentage': percentage,
                'rollout_start_time': timezone.now()
            }
            
            if duration_hours:
                updates['rollout_end_time'] = timezone.now() + timedelta(hours=duration_hours)
            
            return self.update_flag(key, **updates)
            
        except Exception as e:
            logger.error(f"Error rolling out flag {key}: {e}")
            return False
    
    def stop_rollout(self, key: str) -> bool:
        """Stop flag rollout"""
        return self.update_flag(key, rollout_end_time=timezone.now())
    
    def get_rollout_statistics(self, key: str) -> Dict[str, Any]:
        """Get rollout statistics for flag"""
        flag = self.get_flag(key)
        if not flag:
            return {}
        
        stats = flag.get_rollout_status()
        
        # Add user statistics
        if flag.flag_type == FeatureFlagType.PERCENTAGE:
            total_users = User.objects.count()
            enabled_users = int(total_users * flag.percentage / 100)
            stats['estimated_enabled_users'] = enabled_users
            stats['total_users'] = total_users
        
        return stats
    
    def _clear_flag_cache(self, key: str):
        """Clear flag cache"""
        cache_key = f"feature_flag_{key}"
        cache.delete(cache_key)
    
    def clear_all_cache(self):
        """Clear all flag cache"""
        for flag in self.get_all_flags():
            self._clear_flag_cache(flag.key)
    
    def export_flags(self) -> List[Dict[str, Any]]:
        """Export all flags"""
        flags_data = []
        
        for flag in self.get_all_flags():
            flag_data = {
                'key': flag.key,
                'name': flag.name,
                'description': flag.description,
                'flag_type': flag.flag_type,
                'status': flag.status,
                'enabled': flag.enabled,
                'percentage': flag.percentage,
                'rollout_percentage': flag.rollout_percentage,
                'conditions': flag.conditions,
                'created_at': flag.created_at.isoformat(),
                'updated_at': flag.updated_at.isoformat()
            }
            
            if flag.rollout_start_time:
                flag_data['rollout_start_time'] = flag.rollout_start_time.isoformat()
            
            if flag.rollout_end_time:
                flag_data['rollout_end_time'] = flag.rollout_end_time.isoformat()
            
            flags_data.append(flag_data)
        
        return flags_data
    
    def import_flags(self, flags_data: List[Dict[str, Any]], overwrite: bool = False) -> Dict[str, bool]:
        """Import flags"""
        results = {}
        
        for flag_data in flags_data:
            try:
                key = flag_data['key']
                
                # Check if flag exists
                existing_flag = self.get_flag(key)
                
                if existing_flag and not overwrite:
                    results[key] = False
                    continue
                
                # Prepare flag data
                create_data = {
                    'name': flag_data['name'],
                    'description': flag_data.get('description', ''),
                    'flag_type': flag_data['flag_type'],
                    'status': flag_data.get('status', FeatureFlagStatus.INACTIVE),
                    'enabled': flag_data.get('enabled', False),
                    'percentage': flag_data.get('percentage', 0),
                    'rollout_percentage': flag_data.get('rollout_percentage', 0),
                    'conditions': flag_data.get('conditions', {}),
                }
                
                # Handle datetime fields
                if 'rollout_start_time' in flag_data:
                    create_data['rollout_start_time'] = datetime.fromisoformat(flag_data['rollout_start_time'])
                
                if 'rollout_end_time' in flag_data:
                    create_data['rollout_end_time'] = datetime.fromisoformat(flag_data['rollout_end_time'])
                
                if existing_flag:
                    # Update existing flag
                    success = self.update_flag(key, **create_data)
                else:
                    # Create new flag
                    self.create_flag(key, **create_data)
                    success = True
                
                results[key] = success
                
            except Exception as e:
                logger.error(f"Error importing flag {flag_data.get('key', 'unknown')}: {e}")
                results[flag_data.get('key', 'unknown')] = False
        
        return results


class SecurityFeatureFlags:
    """Predefined security feature flags"""
    
    # Security feature flag keys
    ADVANCED_AUTHENTICATION = 'advanced_authentication'
    BIOMETRIC_AUTH = 'biometric_auth'
    TWO_FACTOR_REQUIRED = 'two_factor_required'
    DEVICE_FINGERPRINTING = 'device_fingerprinting'
    IP_WHITELISTING = 'ip_whitelisting'
    RATE_LIMITING = 'rate_limiting'
    ANOMALY_DETECTION = 'anomaly_detection'
    REAL_TIME_MONITORING = 'real_time_monitoring'
    AUTO_BAN_SYSTEM = 'auto_ban_system'
    THREAT_INTELLIGENCE = 'threat_intelligence'
    SECURITY_DASHBOARD = 'security_dashboard'
    AUDIT_LOGGING = 'audit_logging'
    ENCRYPTION_AT_REST = 'encryption_at_rest'
    SESSION_TIMEOUT = 'session_timeout'
    PASSWORD_COMPLEXITY = 'password_complexity'
    ACCOUNT_LOCKOUT = 'account_lockout'
    
    @classmethod
    def initialize_default_flags(cls, manager: FeatureFlagManager):
        """Initialize default security feature flags"""
        default_flags = [
            {
                'key': cls.ADVANCED_AUTHENTICATION,
                'name': 'Advanced Authentication',
                'description': 'Enable advanced authentication methods',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.BIOMETRIC_AUTH,
                'name': 'Biometric Authentication',
                'description': 'Enable biometric authentication options',
                'flag_type': FeatureFlagType.PERCENTAGE,
                'percentage': 50,
                'status': FeatureFlagStatus.TESTING
            },
            {
                'key': cls.TWO_FACTOR_REQUIRED,
                'name': 'Two-Factor Authentication Required',
                'description': 'Require two-factor authentication for all users',
                'flag_type': FeatureFlagType.CONDITIONAL,
                'conditions': {
                    'user_roles': ['staff', 'superuser'],
                    'min_login_count': 5
                },
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.DEVICE_FINGERPRINTING,
                'name': 'Device Fingerprinting',
                'description': 'Enable device fingerprinting for security',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.IP_WHITELISTING,
                'name': 'IP Whitelisting',
                'description': 'Enable IP-based access control',
                'flag_type': FeatureFlagType.WHITELIST,
                'status': FeatureFlagStatus.INACTIVE
            },
            {
                'key': cls.RATE_LIMITING,
                'name': 'Rate Limiting',
                'description': 'Enable advanced rate limiting',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.ANOMALY_DETECTION,
                'name': 'Anomaly Detection',
                'description': 'Enable AI-powered anomaly detection',
                'flag_type': FeatureFlagType.PERCENTAGE,
                'percentage': 25,
                'status': FeatureFlagStatus.TESTING
            },
            {
                'key': cls.REAL_TIME_MONITORING,
                'name': 'Real-time Monitoring',
                'description': 'Enable real-time security monitoring',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.AUTO_BAN_SYSTEM,
                'name': 'Automatic Ban System',
                'description': 'Enable automatic user banning system',
                'flag_type': FeatureFlagType.CONDITIONAL,
                'conditions': {
                    'user_roles': ['staff', 'superuser']
                },
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.THREAT_INTELLIGENCE,
                'name': 'Threat Intelligence',
                'description': 'Enable threat intelligence integration',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.SECURITY_DASHBOARD,
                'name': 'Security Dashboard',
                'description': 'Enable comprehensive security dashboard',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.AUDIT_LOGGING,
                'name': 'Audit Logging',
                'description': 'Enable comprehensive audit logging',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.ENCRYPTION_AT_REST,
                'name': 'Encryption at Rest',
                'description': 'Enable encryption for sensitive data at rest',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.SESSION_TIMEOUT,
                'name': 'Session Timeout',
                'description': 'Enable automatic session timeout',
                'flag_type': FeatureFlagType.CONDITIONAL,
                'conditions': {
                    'user_roles': ['regular']
                },
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.PASSWORD_COMPLEXITY,
                'name': 'Password Complexity Requirements',
                'description': 'Enable strict password complexity requirements',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            },
            {
                'key': cls.ACCOUNT_LOCKOUT,
                'name': 'Account Lockout',
                'description': 'Enable automatic account lockout after failed attempts',
                'flag_type': FeatureFlagType.BOOLEAN,
                'enabled': True,
                'status': FeatureFlagStatus.ACTIVE
            }
        ]
        
        for flag_config in default_flags:
            try:
                existing_flag = manager.get_flag(flag_config['key'])
                if not existing_flag:
                    manager.create_flag(**flag_config)
                    logger.info(f"Created default security flag: {flag_config['key']}")
            except Exception as e:
                logger.error(f"Error creating default flag {flag_config['key']}: {e}")


# Global feature flag manager
feature_flag_manager = FeatureFlagManager()

# Initialize default flags
def initialize_security_feature_flags():
    """Initialize default security feature flags"""
    SecurityFeatureFlags.initialize_default_flags(feature_flag_manager)


# Decorator for feature flags
def feature_flag_required(flag_key: str, fallback_value: Any = None):
    """Decorator to check feature flag before executing function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get user from kwargs or request
            user = kwargs.get('user')
            if not user and args:
                # First argument might be request or user
                if hasattr(args[0], 'user'):
                    user = args[0].user
                elif hasattr(args[0], '__class__') and args[0].__class__.__name__ == 'User':
                    user = args[0]
            
            # Try to get IP address
            ip_address = kwargs.get('ip_address')
            if not ip_address and args:
                if hasattr(args[0], 'META'):
                    ip_address = args[0].META.get('REMOTE_ADDR')
            
            # Check feature flag
            if feature_flag_manager.is_enabled(flag_key, user, ip_address):
                return func(*args, **kwargs)
            elif fallback_value is not None:
                return fallback_value
            else:
                from django.http import HttpResponse
                return HttpResponse("Feature not available", status=403)
        
        return wrapper
    return decorator


# Export classes and utilities
__all__ = [
    'FeatureFlagType',
    'FeatureFlagStatus',
    'FeatureFlag',
    'FeatureFlagManager',
    'feature_flag_manager',
    'SecurityFeatureFlags',
    'initialize_security_feature_flags',
    'feature_flag_required'
]