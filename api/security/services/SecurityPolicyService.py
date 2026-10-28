"""
Enhanced Security Policy Service with comprehensive security model integration
Author: System Security Team
Version: 2.0.0

Advanced policy management, compliance checking, and security analytics.
"""
from django.db import models

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import SecurityPolicy
from ..utils.cache_manager import CacheManager, handle_gracefully

logger = logging.getLogger(__name__)


class SecurityPolicyService:
    """
    Service for managing security policies with defensive coding patterns
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_service_instance(cls):
        """Get singleton instance of the service"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize service with cache manager"""
        self.cache_manager = CacheManager.get_instance()
        self.logger = logging.getLogger(__name__)
    
    @handle_gracefully(default_return=None)
    def get_policy(self, policy_key: str, tenant=None, 
                  user=None) -> Optional[SecurityPolicy]:
        """
        Get a specific security policy
        """
        try:
            cache_key = f"security_policy_{policy_key}_{tenant.id if tenant else 'global'}"
            cached_result = self.cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            queryset = SecurityPolicy.objects.filter(
                policy_key=policy_key,
                is_active=True
            )
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            else:
                queryset = queryset.filter(tenant__isnull=True)
            
            policy = queryset.first()
            
            # Check if policy applies to user
            if policy and user:
                if not policy.is_applicable_to_user(user):
                    policy = None
            
            # Cache for 30 minutes
            self.cache_manager.set(cache_key, policy, timeout=1800)
            
            return policy
            
        except Exception as e:
            self.logger.error(f"Error getting policy {policy_key}: {e}")
            return None
    
    @handle_gracefully(default_return={})
    def get_policies_by_type(self, policy_type: str, tenant=None, 
                           user=None) -> Dict[str, Any]:
        """
        Get all policies of a specific type
        """
        try:
            cache_key = f"policies_{policy_type}_{tenant.id if tenant else 'global'}"
            cached_result = self.cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            queryset = SecurityPolicy.objects.filter(
                policy_type=policy_type,
                is_active=True
            )
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            else:
                queryset = queryset.filter(tenant__isnull=True)
            
            policies = list(queryset.order_by('-priority'))
            
            # Filter policies that apply to user
            if user:
                policies = [p for p in policies if p.is_applicable_to_user(user)]
            
            result = {
                'policy_type': policy_type,
                'tenant': tenant.id if tenant else 'global',
                'policies': policies,
                'count': len(policies)
            }
            
            # Cache for 30 minutes
            self.cache_manager.set(cache_key, result, timeout=1800)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting policies by type {policy_type}: {e}")
            return {}
    
    @handle_gracefully(default_return=False)
    def create_policy(self, tenant, policy_key: str, policy_name: str,
                   policy_type: str, value: Any, description: str = "",
                   is_mandatory: bool = False, priority: int = 0,
                   validation_rules: Dict[str, Any] = None,
                   created_by=None) -> Optional[SecurityPolicy]:
        """
        Create a new security policy
        """
        try:
            # Validate policy value against rules
            if validation_rules:
                is_valid, error_msg = self._validate_policy_value(value, validation_rules)
                if not is_valid:
                    self.logger.error(f"Policy validation failed: {error_msg}")
                    return None
            
            policy = SecurityPolicy.objects.create(
                tenant=tenant,
                policy_key=policy_key,
                policy_name=policy_name,
                policy_type=policy_type,
                value={'value': value},
                description=description,
                is_mandatory=is_mandatory,
                is_active=True,
                priority=priority,
                validation_rules=validation_rules or {},
                created_by=created_by
            )
            
            self.logger.info(f"Created security policy: {policy_name}")
            
            # Clear policy cache
            self._clear_policy_cache(policy_type)
            
            return policy
            
        except Exception as e:
            self.logger.error(f"Error creating policy: {e}")
            return None
    
    @handle_gracefully(default_return=False)
    def update_policy(self, policy_id: int, value: Any = None,
                   description: str = None, is_active: bool = None,
                   priority: int = None, validation_rules: Dict[str, Any] = None,
                   updated_by=None) -> bool:
        """
        Update an existing security policy
        """
        try:
            policy = SecurityPolicy.objects.get(id=policy_id)
            
            # Validate new value against rules
            if value is not None and validation_rules:
                is_valid, error_msg = self._validate_policy_value(value, validation_rules)
                if not is_valid:
                    self.logger.error(f"Policy validation failed: {error_msg}")
                    return False
            
            if value is not None:
                policy.value = {'value': value}
            if description is not None:
                policy.description = description
            if is_active is not None:
                policy.is_active = is_active
            if priority is not None:
                policy.priority = priority
            if validation_rules is not None:
                policy.validation_rules = validation_rules
            if updated_by is not None:
                policy.updated_by = updated_by
            
            policy.save()
            
            self.logger.info(f"Updated security policy: {policy.policy_name}")
            
            # Clear policy cache
            self._clear_policy_cache(policy.policy_type)
            
            return True
            
        except SecurityPolicy.DoesNotExist:
            self.logger.error(f"Policy not found: {policy_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating policy: {e}")
            return False
    
    @handle_gracefully(default_return=False)
    def delete_policy(self, policy_id: int) -> bool:
        """
        Delete a security policy
        """
        try:
            policy = SecurityPolicy.objects.get(id=policy_id)
            policy_type = policy.policy_type
            
            policy.delete()
            
            self.logger.info(f"Deleted security policy: {policy.policy_name}")
            
            # Clear policy cache
            self._clear_policy_cache(policy_type)
            
            return True
            
        except SecurityPolicy.DoesNotExist:
            self.logger.error(f"Policy not found: {policy_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error deleting policy: {e}")
            return False
    
    @handle_gracefully(default_return={})
    def get_user_policies(self, user, policy_type: str = None) -> Dict[str, Any]:
        """
        Get all policies that apply to a specific user
        """
        try:
            cache_key = f"user_policies_{user.id}_{policy_type or 'all'}"
            cached_result = self.cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            # Get user's tenant
            tenant = getattr(user, 'tenant', None)
            
            # Get all applicable policies
            queryset = SecurityPolicy.objects.filter(is_active=True)
            
            if tenant:
                queryset = queryset.filter(
                    models.Q(tenant=tenant) | models.Q(tenant__isnull=True)
                )
            else:
                queryset = queryset.filter(tenant__isnull=True)
            
            if policy_type:
                queryset = queryset.filter(policy_type=policy_type)
            
            policies = list(queryset.order_by('-priority'))
            
            # Filter policies that apply to user
            applicable_policies = []
            for policy in policies:
                if policy.is_applicable_to_user(user):
                    applicable_policies.append(policy)
            
            result = {
                'user_id': user.id,
                'tenant': tenant.id if tenant else 'global',
                'policy_type': policy_type,
                'policies': applicable_policies,
                'count': len(applicable_policies),
                'policy_values': {
                    p.policy_key: p.get_policy_value() for p in applicable_policies
                }
            }
            
            # Cache for 15 minutes
            self.cache_manager.set(cache_key, result, timeout=900)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting user policies: {e}")
            return {}
    
    @handle_gracefully(default_return=False)
    def validate_policy_compliance(self, user, policy_type: str = None) -> Dict[str, Any]:
        """
        Validate user compliance with security policies
        """
        try:
            user_policies = self.get_user_policies(user, policy_type)
            policies = user_policies.get('policies', [])
            
            compliance_result = {
                'user_id': user.id,
                'username': user.username,
                'policy_type': policy_type,
                'total_policies': len(policies),
                'compliant_policies': 0,
                'non_compliant_policies': 0,
                'compliance_issues': [],
                'recommendations': []
            }
            
            # Check each policy
            for policy in policies:
                policy_value = policy.get_policy_value()
                validation_rules = policy.validation_rules or {}
                
                is_compliant, issue = self._check_user_compliance(
                    user, policy.policy_key, policy_value, validation_rules
                )
                
                if is_compliant:
                    compliance_result['compliant_policies'] += 1
                else:
                    compliance_result['non_compliant_policies'] += 1
                    compliance_result['compliance_issues'].append({
                        'policy_key': policy.policy_key,
                        'policy_name': policy.policy_name,
                        'issue': issue,
                        'is_mandatory': policy.is_mandatory
                    })
                    
                    if policy.is_mandatory:
                        compliance_result['recommendations'].append(
                            f"Required policy '{policy.policy_name}' needs attention"
                        )
            
            compliance_result['compliance_percentage'] = (
                (compliance_result['compliant_policies'] / 
                compliance_result['total_policies'] * 100) 
                if compliance_result['total_policies'] > 0 else 100
            )
            
            return compliance_result
            
        except Exception as e:
            self.logger.error(f"Error checking policy compliance: {e}")
            return {'error': str(e)}
    
    def _validate_policy_value(self, value: Any, 
                           validation_rules: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate policy value against rules
        """
        try:
            # Type validation
            expected_type = validation_rules.get('type')
            if expected_type and not isinstance(value, eval(expected_type)):
                return False, f"Expected type {expected_type}"
            
            # Range validation
            min_val = validation_rules.get('min')
            max_val = validation_rules.get('max')
            if min_val is not None and value < min_val:
                return False, f"Value must be >= {min_val}"
            if max_val is not None and value > max_val:
                return False, f"Value must be <= {max_val}"
            
            # Pattern validation
            import re
            pattern = validation_rules.get('pattern')
            if pattern and not re.match(pattern, str(value)):
                return False, f"Value must match pattern {pattern}"
            
            return True, ""
            
        except Exception as e:
            self.logger.error(f"Error validating policy value: {e}")
            return False, "Validation error"
    
    def _check_user_compliance(self, user, policy_key: str, 
                            policy_value: Any, validation_rules: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if user complies with a specific policy
        """
        try:
            # Password policies
            if policy_key == 'password_min_length':
                # This would need to check user's current password
                # For now, return True as placeholder
                return True, ""
            
            # Session policies
            elif policy_key == 'session_timeout_minutes':
                # Check if user has active sessions older than timeout
                from ..models import UserSession
                timeout_minutes = policy_value
                cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)
                
                old_sessions = UserSession.objects.filter(
                    user=user,
                    is_active=True,
                    last_activity__lt=cutoff_time
                ).count()
                
                if old_sessions > 0:
                    return False, f"Has {old_sessions} sessions older than {timeout_minutes} minutes"
                
            # Add more policy checks as needed
            
            return True, ""
            
        except Exception as e:
            self.logger.error(f"Error checking user compliance: {e}")
            return False, "Compliance check error"
    
    def _clear_policy_cache(self, policy_type: str = None):
        """
        Clear policy cache
        """
        try:
            if policy_type:
                # Clear specific policy type cache
                patterns = [
                    f"policies_{policy_type}_*",
                    f"user_policies_*_{policy_type}"
                ]
            else:
                # Clear all policy cache
                patterns = [
                    "security_policy_*",
                    "policies_*",
                    "user_policies_*"
                ]
            
            for pattern in patterns:
                keys = self.cache_manager.get_keys(pattern)
                for key in keys:
                    self.cache_manager.delete(key)
            
        except Exception as e:
            self.logger.error(f"Error clearing policy cache: {e}")
    
    @handle_gracefully(default_return={})
    def get_policy_statistics(self, tenant=None) -> Dict[str, Any]:
        """
        Get statistics about security policies
        """
        try:
            queryset = SecurityPolicy.objects.all()
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            stats = {
                'tenant': tenant.id if tenant else 'global',
                'total_policies': queryset.count(),
                'active_policies': queryset.filter(is_active=True).count(),
                'inactive_policies': queryset.filter(is_active=False).count(),
                'mandatory_policies': queryset.filter(is_mandatory=True).count(),
                'policies_by_type': {},
                'policies_by_priority': {
                    'high': queryset.filter(priority__gte=8).count(),
                    'medium': queryset.filter(priority__gte=4, priority__lt=8).count(),
                    'low': queryset.filter(priority__lt=4).count()
                }
            }
            
            # Policy type breakdown
            for policy_type in ['password', 'session', 'authentication', 'authorization', 
                              'encryption', 'logging', 'backup', 'compliance', 'custom']:
                count = queryset.filter(policy_type=policy_type).count()
                stats['policies_by_type'][policy_type] = count
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting policy statistics: {e}")
            return {'error': str(e)}