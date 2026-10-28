# =============================================================================
# fraud_detection/feature_flags.py
# =============================================================================
"""
Feature Flags Layer for Fraud Detection System.

Provides user-specific and global fraud check toggling,
feature flag management, and dynamic configuration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Set
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.fraud_detection.exceptions import FeatureFlagError
from api.fraud_detection.constants import CACHE_KEYS, CACHE_TTL


logger = logging.getLogger(__name__)

User = get_user_model()


@dataclass
class FeatureFlag:
    """Data class for feature flag configuration."""
    name: str
    enabled: bool
    description: str
    rollout_percentage: float = 100.0
    user_whitelist: Optional[Set[Union[int, str]]] = None
    user_blacklist: Optional[Set[Union[int, str]]] = None
    conditions: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FeatureFlagManager:
    """
    Feature flag manager for fraud detection system.
    
    Provides dynamic feature flag management with user-specific
    targeting, rollout control, and condition-based activation.
    """
    
    def __init__(self):
        """Initialize feature flag manager."""
        self.cache_ttl = getattr(settings, 'FEATURE_FLAG_CACHE_TTL', 300)  # 5 minutes
        self.flags = self._load_feature_flags()
        self.global_settings = self._load_global_settings()
    
    def _load_feature_flags(self) -> Dict[str, FeatureFlag]:
        """Load feature flags from configuration."""
        default_flags = {
            'fraud_detection_enabled': FeatureFlag(
                name='fraud_detection_enabled',
                enabled=True,
                description='Enable/disable fraud detection system',
                rollout_percentage=100.0,
                user_whitelist=None,
                user_blacklist=None,
                conditions=None
            ),
            'multi_account_detection': FeatureFlag(
                name='multi_account_detection',
                enabled=True,
                description='Enable multi-account fraud detection',
                rollout_percentage=100.0,
                user_whitelist=None,
                user_blacklist=None,
                conditions={'min_account_age_days': 1}
            ),
            'device_fingerprinting': FeatureFlag(
                name='device_fingerprinting',
                enabled=True,
                description='Enable device fingerprinting analysis',
                rollout_percentage=100.0,
                user_whitelist=None,
                user_blacklist=None,
                conditions=None
            ),
            'ip_reputation_checking': FeatureFlag(
                name='ip_reputation_checking',
                enabled=True,
                description='Enable IP reputation checking',
                rollout_percentage=100.0,
                user_whitelist=None,
                user_blacklist=None,
                conditions=None
            ),
            'sanctions_screening': FeatureFlag(
                name='sanctions_screening',
                enabled=True,
                description='Enable sanctions and compliance screening',
                rollout_percentage=100.0,
                user_whitelist=None,
                user_blacklist=None,
                conditions={'min_transaction_amount': 1000}
            ),
            'real_time_monitoring': FeatureFlag(
                name='real_time_monitoring',
                enabled=True,
                description='Enable real-time fraud monitoring',
                rollout_percentage=50.0,  # Gradual rollout
                user_whitelist=None,
                user_blacklist=None,
                conditions=None
            ),
            'advanced_analytics': FeatureFlag(
                name='advanced_analytics',
                enabled=False,
                description='Enable advanced fraud analytics',
                rollout_percentage=0.0,
                user_whitelist=set(),
                user_blacklist=None,
                conditions={'user_role': ['admin', 'analyst']}
            ),
            'automated_case_creation': FeatureFlag(
                name='automated_case_creation',
                enabled=True,
                description='Enable automated fraud case creation',
                rollout_percentage=80.0,
                user_whitelist=None,
                user_blacklist=None,
                conditions={'min_risk_score': 60}
            ),
            'enhanced_reporting': FeatureFlag(
                name='enhanced_reporting',
                enabled=True,
                description='Enable enhanced fraud reporting',
                rollout_percentage=100.0,
                user_whitelist=None,
                user_blacklist=None,
                conditions=None
            ),
            'external_integrations': FeatureFlag(
                name='external_integrations',
                enabled=False,
                description='Enable external fraud database integrations',
                rollout_percentage=0.0,
                user_whitelist=set(),
                user_blacklist=None,
                conditions={'api_keys_configured': True}
            )
        }
        
        # Load from settings if available
        settings_flags = getattr(settings, 'FRAUD_FEATURE_FLAGS', {})
        
        for flag_name, flag_config in settings_flags.items():
            if flag_name in default_flags:
                # Update existing flag
                flag = default_flags[flag_name]
                flag.enabled = flag_config.get('enabled', flag.enabled)
                flag.rollout_percentage = flag_config.get('rollout_percentage', flag.rollout_percentage)
                flag.user_whitelist = set(flag_config.get('user_whitelist', flag.user_whitelist or []))
                flag.user_blacklist = set(flag_config.get('user_blacklist', flag.user_blacklist or []))
                flag.conditions = flag_config.get('conditions', flag.conditions)
                flag.metadata = flag_config.get('metadata', flag.metadata)
            else:
                # Create new flag
                default_flags[flag_name] = FeatureFlag(
                    name=flag_name,
                    enabled=flag_config.get('enabled', False),
                    description=flag_config.get('description', ''),
                    rollout_percentage=flag_config.get('rollout_percentage', 100.0),
                    user_whitelist=set(flag_config.get('user_whitelist', [])),
                    user_blacklist=set(flag_config.get('user_blacklist', [])),
                    conditions=flag_config.get('conditions', {}),
                    metadata=flag_config.get('metadata', {})
                )
        
        return default_flags
    
    def _load_global_settings(self) -> Dict[str, Any]:
        """Load global feature flag settings."""
        default_settings = {
            'cache_enabled': True,
            'audit_log_enabled': True,
            'rollout_strategy': 'user_id_hash',
            'default_rollout_percentage': 100.0,
            'feature_change_notification': True
        }
        
        return getattr(settings, 'FRAUD_FEATURE_SETTINGS', default_settings)
    
    def is_enabled(self, flag_name: str, user_id: Optional[Union[int, str]] = None,
                   context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if feature flag is enabled for user.
        
        Args:
            flag_name: Name of the feature flag
            user_id: User ID (optional)
            context: Additional context for evaluation
            
        Returns:
            True if feature is enabled
        """
        try:
            # Check cache first
            if self.global_settings['cache_enabled']:
                cache_key = f"feature_flag:{flag_name}:{user_id or 'global'}"
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Get flag configuration
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Unknown feature flag: {flag_name}")
                return False
            
            # Check if flag is globally enabled
            if not flag.enabled:
                result = False
            else:
                # Check user-specific conditions
                result = self._evaluate_flag_conditions(flag, user_id, context)
            
            # Cache the result
            if self.global_settings['cache_enabled']:
                cache.set(cache_key, result, self.cache_ttl)
            
            # Log flag evaluation for audit
            if self.global_settings['audit_log_enabled']:
                self._log_flag_evaluation(flag_name, user_id, result, context)
            
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating feature flag {flag_name}: {e}")
            return False  # Fail safely
    
    def _evaluate_flag_conditions(self, flag: FeatureFlag, 
                                 user_id: Optional[Union[int, str]],
                                 context: Optional[Dict[str, Any]]) -> bool:
        """Evaluate flag conditions for user."""
        # Check user blacklist
        if flag.user_blacklist and user_id and str(user_id) in flag.user_blacklist:
            return False
        
        # Check user whitelist
        if flag.user_whitelist and user_id and str(user_id) in flag.user_whitelist:
            return True
        
        # Check rollout percentage
        if flag.rollout_percentage < 100.0:
            if not self._is_user_in_rollout(flag, user_id):
                return False
        
        # Check custom conditions
        if flag.conditions:
            if not self._evaluate_custom_conditions(flag, user_id, context):
                return False
        
        return True
    
    def _is_user_in_rollout(self, flag: FeatureFlag, user_id: Optional[Union[int, str]]) -> bool:
        """Check if user is included in rollout percentage."""
        if not user_id:
            return False
        
        if flag.rollout_percentage >= 100.0:
            return True
        
        if flag.rollout_percentage <= 0.0:
            return False
        
        # Use consistent hashing for rollout
        import hashlib
        
        user_str = f"{flag.name}:{user_id}"
        hash_value = int(hashlib.md5(user_str.encode()).hexdigest(), 16)
        
        # Check if user falls within rollout percentage
        rollout_threshold = int((flag.rollout_percentage / 100.0) * 1000000)
        return (hash_value % 1000000) < rollout_threshold
    
    def _evaluate_custom_conditions(self, flag: FeatureFlag, 
                                  user_id: Optional[Union[int, str]],
                                  context: Optional[Dict[str, Any]]) -> bool:
        """Evaluate custom conditions for flag."""
        if not flag.conditions:
            return True
        
        try:
            # Check user role condition
            if 'user_role' in flag.conditions and user_id:
                required_roles = flag.conditions['user_role']
                if isinstance(required_roles, str):
                    required_roles = [required_roles]
                
                try:
                    user = User.objects.get(pk=user_id)
                    user_role = getattr(user, 'role', 'user')
                    if user_role not in required_roles:
                        return False
                except User.DoesNotExist:
                    return False
            
            # Check minimum account age
            if 'min_account_age_days' in flag.conditions and user_id:
                try:
                    user = User.objects.get(pk=user_id)
                    account_age = (timezone.now() - user.date_joined).days
                    if account_age < flag.conditions['min_account_age_days']:
                        return False
                except User.DoesNotExist:
                    return False
            
            # Check minimum transaction amount
            if 'min_transaction_amount' in flag.conditions and context:
                transaction_amount = context.get('transaction_amount', 0)
                if transaction_amount < flag.conditions['min_transaction_amount']:
                    return False
            
            # Check minimum risk score
            if 'min_risk_score' in flag.conditions and context:
                risk_score = context.get('risk_score', 0)
                if risk_score < flag.conditions['min_risk_score']:
                    return False
            
            # Check API keys configured
            if 'api_keys_configured' in flag.conditions:
                api_keys_configured = getattr(settings, 'FRAUD_API_KEYS_CONFIGURED', False)
                if not api_keys_configured:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating custom conditions for flag {flag.name}: {e}")
            return False
    
    def _log_flag_evaluation(self, flag_name: str, user_id: Optional[Union[int, str]],
                           result: bool, context: Optional[Dict[str, Any]]):
        """Log flag evaluation for audit purposes."""
        log_data = {
            'flag_name': flag_name,
            'user_id': user_id,
            'result': result,
            'timestamp': timezone.now().isoformat(),
            'context': context or {}
        }
        
        logger.info(f"Feature flag evaluation: {log_data}")
    
    def get_user_feature_flags(self, user_id: Union[int, str]) -> Dict[str, bool]:
        """
        Get all feature flags status for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary of flag names and their enabled status
        """
        user_flags = {}
        
        for flag_name in self.flags:
            user_flags[flag_name] = self.is_enabled(flag_name, user_id)
        
        return user_flags
    
    def get_flag_metadata(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            
        Returns:
            Flag metadata dictionary
        """
        flag = self.flags.get(flag_name)
        if not flag:
            return None
        
        return {
            'name': flag.name,
            'enabled': flag.enabled,
            'description': flag.description,
            'rollout_percentage': flag.rollout_percentage,
            'user_whitelist_count': len(flag.user_whitelist) if flag.user_whitelist else 0,
            'user_blacklist_count': len(flag.user_blacklist) if flag.user_blacklist else 0,
            'conditions': flag.conditions,
            'metadata': flag.metadata,
            'created_at': flag.created_at.isoformat() if flag.created_at else None,
            'updated_at': flag.updated_at.isoformat() if flag.updated_at else None
        }
    
    def update_flag(self, flag_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update feature flag configuration.
        
        Args:
            flag_name: Name of the feature flag
            updates: Update dictionary
            
        Returns:
            True if update successful
        """
        try:
            flag = self.flags.get(flag_name)
            if not flag:
                raise FeatureFlagError(f"Unknown feature flag: {flag_name}")
            
            # Update flag properties
            if 'enabled' in updates:
                flag.enabled = updates['enabled']
            
            if 'rollout_percentage' in updates:
                flag.rollout_percentage = max(0.0, min(100.0, updates['rollout_percentage']))
            
            if 'user_whitelist' in updates:
                flag.user_whitelist = set(updates['user_whitelist'])
            
            if 'user_blacklist' in updates:
                flag.user_blacklist = set(updates['user_blacklist'])
            
            if 'conditions' in updates:
                flag.conditions = updates['conditions']
            
            if 'metadata' in updates:
                flag.metadata = updates['metadata']
            
            flag.updated_at = timezone.now()
            
            # Clear cache for this flag
            if self.global_settings['cache_enabled']:
                cache_pattern = f"feature_flag:{flag_name}:*"
                # In practice, you'd use cache.delete_pattern() or similar
                # For now, just let cache expire naturally
            
            # Send notification if enabled
            if self.global_settings['feature_change_notification']:
                self._send_flag_change_notification(flag_name, updates)
            
            logger.info(f"Updated feature flag {flag_name}: {updates}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update feature flag {flag_name}: {e}")
            return False
    
    def create_flag(self, flag_name: str, flag_config: Dict[str, Any]) -> bool:
        """
        Create new feature flag.
        
        Args:
            flag_name: Name of the feature flag
            flag_config: Flag configuration
            
        Returns:
            True if creation successful
        """
        try:
            if flag_name in self.flags:
                raise FeatureFlagError(f"Feature flag already exists: {flag_name}")
            
            flag = FeatureFlag(
                name=flag_name,
                enabled=flag_config.get('enabled', False),
                description=flag_config.get('description', ''),
                rollout_percentage=flag_config.get('rollout_percentage', 100.0),
                user_whitelist=set(flag_config.get('user_whitelist', [])),
                user_blacklist=set(flag_config.get('user_blacklist', [])),
                conditions=flag_config.get('conditions', {}),
                metadata=flag_config.get('metadata', {}),
                created_at=timezone.now(),
                updated_at=timezone.now()
            )
            
            self.flags[flag_name] = flag
            
            logger.info(f"Created feature flag {flag_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create feature flag {flag_name}: {e}")
            return False
    
    def delete_flag(self, flag_name: str) -> bool:
        """
        Delete feature flag.
        
        Args:
            flag_name: Name of the feature flag
            
        Returns:
            True if deletion successful
        """
        try:
            if flag_name not in self.flags:
                raise FeatureFlagError(f"Unknown feature flag: {flag_name}")
            
            del self.flags[flag_name]
            
            # Clear cache
            if self.global_settings['cache_enabled']:
                cache_pattern = f"feature_flag:{flag_name}:*"
                # Clear cache entries
            
            logger.info(f"Deleted feature flag {flag_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete feature flag {flag_name}: {e}")
            return False
    
    def get_flag_statistics(self) -> Dict[str, Any]:
        """Get feature flag statistics."""
        total_flags = len(self.flags)
        enabled_flags = sum(1 for flag in self.flags.values() if flag.enabled)
        
        rollout_stats = {
            'full_rollout': 0,
            'partial_rollout': 0,
            'disabled': 0
        }
        
        for flag in self.flags.values():
            if flag.enabled:
                if flag.rollout_percentage >= 100.0:
                    rollout_stats['full_rollout'] += 1
                else:
                    rollout_stats['partial_rollout'] += 1
            else:
                rollout_stats['disabled'] += 1
        
        return {
            'total_flags': total_flags,
            'enabled_flags': enabled_flags,
            'disabled_flags': total_flags - enabled_flags,
            'rollout_statistics': rollout_stats,
            'flags_with_conditions': sum(1 for flag in self.flags.values() if flag.conditions),
            'flags_with_whitelists': sum(1 for flag in self.flags.values() if flag.user_whitelist),
            'flags_with_blacklists': sum(1 for flag in self.flags.values() if flag.user_blacklist)
        }
    
    def _send_flag_change_notification(self, flag_name: str, updates: Dict[str, Any]):
        """Send notification for flag changes."""
        try:
            # In practice, this would send notifications via appropriate channels
            notification_data = {
                'flag_name': flag_name,
                'updates': updates,
                'timestamp': timezone.now().isoformat(),
                'type': 'feature_flag_change'
            }
            
            logger.info(f"Feature flag change notification: {notification_data}")
            
        except Exception as e:
            logger.error(f"Failed to send flag change notification: {e}")


class FraudDetectionFeatureChecker:
    """
    Feature checker specifically for fraud detection functionality.
    
    Provides convenient methods for checking fraud detection features.
    """
    
    def __init__(self):
        """Initialize fraud detection feature checker."""
        self.flag_manager = FeatureFlagManager()
    
    def is_fraud_detection_enabled(self, user_id: Optional[Union[int, str]] = None,
                                  context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if fraud detection is enabled."""
        return self.flag_manager.is_enabled('fraud_detection_enabled', user_id, context)
    
    def is_multi_account_detection_enabled(self, user_id: Optional[Union[int, str]] = None,
                                         context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if multi-account detection is enabled."""
        return self.flag_manager.is_enabled('multi_account_detection', user_id, context)
    
    def is_device_fingerprinting_enabled(self, user_id: Optional[Union[int, str]] = None,
                                       context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if device fingerprinting is enabled."""
        return self.flag_manager.is_enabled('device_fingerprinting', user_id, context)
    
    def is_ip_reputation_checking_enabled(self, user_id: Optional[Union[int, str]] = None,
                                       context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if IP reputation checking is enabled."""
        return self.flag_manager.is_enabled('ip_reputation_checking', user_id, context)
    
    def is_sanctions_screening_enabled(self, user_id: Optional[Union[int, str]] = None,
                                     context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if sanctions screening is enabled."""
        return self.flag_manager.is_enabled('sanctions_screening', user_id, context)
    
    def is_real_time_monitoring_enabled(self, user_id: Optional[Union[int, str]] = None,
                                      context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if real-time monitoring is enabled."""
        return self.flag_manager.is_enabled('real_time_monitoring', user_id, context)
    
    def is_advanced_analytics_enabled(self, user_id: Optional[Union[int, str]] = None,
                                    context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if advanced analytics is enabled."""
        return self.flag_manager.is_enabled('advanced_analytics', user_id, context)
    
    def is_automated_case_creation_enabled(self, user_id: Optional[Union[int, str]] = None,
                                         context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if automated case creation is enabled."""
        return self.flag_manager.is_enabled('automated_case_creation', user_id, context)
    
    def is_enhanced_reporting_enabled(self, user_id: Optional[Union[int, str]] = None,
                                    context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if enhanced reporting is enabled."""
        return self.flag_manager.is_enabled('enhanced_reporting', user_id, context)
    
    def is_external_integrations_enabled(self, user_id: Optional[Union[int, str]] = None,
                                       context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if external integrations are enabled."""
        return self.flag_manager.is_enabled('external_integrations', user_id, context)
    
    def get_user_fraud_features(self, user_id: Union[int, str]) -> Dict[str, bool]:
        """Get all fraud detection features for user."""
        fraud_features = [
            'fraud_detection_enabled',
            'multi_account_detection',
            'device_fingerprinting',
            'ip_reputation_checking',
            'sanctions_screening',
            'real_time_monitoring',
            'advanced_analytics',
            'automated_case_creation',
            'enhanced_reporting',
            'external_integrations'
        ]
        
        user_features = {}
        for feature in fraud_features:
            user_features[feature] = self.flag_manager.is_enabled(feature, user_id)
        
        return user_features


# Global instances for easy access
feature_flag_manager = FeatureFlagManager()
fraud_feature_checker = FraudDetectionFeatureChecker()


def is_fraud_detection_enabled(user_id: Optional[Union[int, str]] = None,
                               context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Convenience function to check if fraud detection is enabled.
    
    Args:
        user_id: User ID
        context: Additional context
        
    Returns:
        True if fraud detection is enabled
    """
    return fraud_feature_checker.is_fraud_detection_enabled(user_id, context)


def get_user_fraud_features(user_id: Union[int, str]) -> Dict[str, bool]:
    """
    Convenience function to get fraud features for user.
    
    Args:
        user_id: User ID
        
    Returns:
        Dictionary of fraud feature flags
    """
    return fraud_feature_checker.get_user_fraud_features(user_id)


def update_feature_flag(flag_name: str, updates: Dict[str, Any]) -> bool:
    """
    Convenience function to update feature flag.
    
    Args:
        flag_name: Name of the feature flag
        updates: Update dictionary
        
    Returns:
        True if update successful
    """
    return feature_flag_manager.update_flag(flag_name, updates)
