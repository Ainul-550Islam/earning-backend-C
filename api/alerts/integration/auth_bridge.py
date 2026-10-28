"""
Integration Auth Bridge - Cross-module permission bridge for integration system
Provides safe authentication and authorization with existing alerts architecture
"""
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_constants import (
    CACHE_KEYS,
    CACHE_TIMEOUTS
)

logger = logging.getLogger(__name__)


class IntegrationAuthBridge:
    """
    Authentication and authorization bridge for integration system
    Maintains existing security logic and adds integration-specific permissions
    """
    
    def __init__(self):
        self.permission_cache = {}
        self.auth_stats = {
            'total_auth_checks': 0,
            'successful_auth_checks': 0,
            'failed_auth_checks': 0,
            'auth_checks_by_type': {},
            'last_auth_check': None
        }
        # Permission rows are created by AlertsConfig's post_migrate hook, not at import time.
    
    def _initialize_integration_permissions(self):
        """
        Initialize integration-specific permissions
        """
        try:
            # Create content type for integration if it doesn't exist
            integration_content_type, created = ContentType.objects.get_or_create(
                app_label='alerts',
                model='integration',
            )
            
            # Define integration permissions
            permissions = [
                ('can_create_integration', 'Can create integration'),
                ('can_view_integration', 'Can view integration'),
                ('can_edit_integration', 'Can edit integration'),
                ('can_delete_integration', 'Can delete integration'),
                ('can_manage_integration_config', 'Can manage integration configuration'),
                ('can_trigger_integration', 'Can trigger integration'),
                ('can_view_integration_logs', 'Can view integration logs'),
                ('can_manage_integration_fallbacks', 'Can manage integration fallbacks'),
            ]
            
            # Create permissions if they don't exist
            for codename, name in permissions:
                Permission.objects.get_or_create(
                    codename=codename,
                    name=name,
                    content_type=integration_content_type,
                    defaults={'content_type': integration_content_type}
                )
            
            logger.info("Integration permissions initialized")
            
        except Exception as e:
            logger.error(f"Error initializing integration permissions: {e}")
    
    def check_integration_permission(self, user: User, permission: str, 
                                   integration_id: str = None) -> bool:
        """
        Check if user has integration permission
        """
        try:
            self.auth_stats['total_auth_checks'] += 1
            self.auth_stats['last_auth_check'] = django_tz.now().isoformat()
            
            # Update auth check type stats
            self.auth_stats['auth_checks_by_type'][permission] = \
                self.auth_stats['auth_checks_by_type'].get(permission, 0) + 1
            
            # Check cache first
            cache_key = f"integration_perm:{user.id}:{permission}"
            if integration_id:
                cache_key += f":{integration_id}"
            
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                if cached_result:
                    self.auth_stats['successful_auth_checks'] += 1
                else:
                    self.auth_stats['failed_auth_checks'] += 1
                return cached_result
            
            # Check permission
            has_permission = self._check_permission_impl(user, permission, integration_id)
            
            # Cache result
            cache.set(cache_key, has_permission, timeout=CACHE_TIMEOUTS['integration'])
            
            # Update stats
            if has_permission:
                self.auth_stats['successful_auth_checks'] += 1
            else:
                self.auth_stats['failed_auth_checks'] += 1
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Error checking integration permission: {e}")
            self.auth_stats['failed_auth_checks'] += 1
            return False
    
    def _check_permission_impl(self, user: User, permission: str, 
                             integration_id: str = None) -> bool:
        """
        Implementation of permission check
        """
        try:
            # Check if user is superuser
            if user.is_superuser:
                return True
            
            # Check if user is staff (for admin permissions)
            if user.is_staff and permission.startswith('can_') and 'manage' in permission:
                return True
            
            # Check specific integration permissions
            if permission == 'can_create_integration':
                return self._can_create_integration(user)
            elif permission == 'can_view_integration':
                return self._can_view_integration(user, integration_id)
            elif permission == 'can_edit_integration':
                return self._can_edit_integration(user, integration_id)
            elif permission == 'can_delete_integration':
                return self._can_delete_integration(user, integration_id)
            elif permission == 'can_manage_integration_config':
                return self._can_manage_integration_config(user, integration_id)
            elif permission == 'can_trigger_integration':
                return self._can_trigger_integration(user, integration_id)
            elif permission == 'can_view_integration_logs':
                return self._can_view_integration_logs(user)
            elif permission == 'can_manage_integration_fallbacks':
                return self._can_manage_integration_fallbacks(user)
            else:
                # Check Django permission
                return user.has_perm(f'alerts.{permission}')
                
        except Exception as e:
            logger.error(f"Error in permission check implementation: {e}")
            return False
    
    def _can_create_integration(self, user: User) -> bool:
        """
        Check if user can create integration
        """
        try:
            # Staff users can create integrations
            if user.is_staff:
                return True
            
            # Check specific permission
            return user.has_perm('alerts.can_create_integration')
            
        except Exception as e:
            logger.error(f"Error checking create integration permission: {e}")
            return False
    
    def _can_view_integration(self, user: User, integration_id: str = None) -> bool:
        """
        Check if user can view integration
        """
        try:
            # Staff users can view all integrations
            if user.is_staff:
                return True
            
            # Check specific permission
            if user.has_perm('alerts.can_view_integration'):
                return True
            
            # Check if user owns the integration (if integration_id provided)
            if integration_id:
                return self._check_integration_ownership(user, integration_id)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking view integration permission: {e}")
            return False
    
    def _can_edit_integration(self, user: User, integration_id: str = None) -> bool:
        """
        Check if user can edit integration
        """
        try:
            # Staff users can edit all integrations
            if user.is_staff:
                return True
            
            # Check specific permission
            if user.has_perm('alerts.can_edit_integration'):
                return True
            
            # Check if user owns the integration (if integration_id provided)
            if integration_id:
                return self._check_integration_ownership(user, integration_id)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking edit integration permission: {e}")
            return False
    
    def _can_delete_integration(self, user: User, integration_id: str = None) -> bool:
        """
        Check if user can delete integration
        """
        try:
            # Only staff users can delete integrations
            if user.is_staff:
                return True
            
            # Check specific permission
            if user.has_perm('alerts.can_delete_integration'):
                return True
            
            # Check if user owns the integration (if integration_id provided)
            if integration_id:
                return self._check_integration_ownership(user, integration_id)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking delete integration permission: {e}")
            return False
    
    def _can_manage_integration_config(self, user: User, integration_id: str = None) -> bool:
        """
        Check if user can manage integration configuration
        """
        try:
            # Staff users can manage all configurations
            if user.is_staff:
                return True
            
            # Check specific permission
            if user.has_perm('alerts.can_manage_integration_config'):
                return True
            
            # Check if user owns the integration (if integration_id provided)
            if integration_id:
                return self._check_integration_ownership(user, integration_id)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking manage integration config permission: {e}")
            return False
    
    def _can_trigger_integration(self, user: User, integration_id: str = None) -> bool:
        """
        Check if user can trigger integration
        """
        try:
            # Staff users can trigger all integrations
            if user.is_staff:
                return True
            
            # Check specific permission
            if user.has_perm('alerts.can_trigger_integration'):
                return True
            
            # Check if user owns the integration (if integration_id provided)
            if integration_id:
                return self._check_integration_ownership(user, integration_id)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking trigger integration permission: {e}")
            return False
    
    def _can_view_integration_logs(self, user: User) -> bool:
        """
        Check if user can view integration logs
        """
        try:
            # Staff users can view all logs
            if user.is_staff:
                return True
            
            # Check specific permission
            return user.has_perm('alerts.can_view_integration_logs')
            
        except Exception as e:
            logger.error(f"Error checking view integration logs permission: {e}")
            return False
    
    def _can_manage_integration_fallbacks(self, user: User) -> bool:
        """
        Check if user can manage integration fallbacks
        """
        try:
            # Only staff users can manage fallbacks
            if user.is_staff:
                return True
            
            # Check specific permission
            return user.has_perm('alerts.can_manage_integration_fallbacks')
            
        except Exception as e:
            logger.error(f"Error checking manage integration fallbacks permission: {e}")
            return False
    
    def _check_integration_ownership(self, user: User, integration_id: str) -> bool:
        """
        Check if user owns the integration
        """
        try:
            # This is a simplified implementation
            # In production, you would have an Integration model with owner field
            from api.alerts.integration.integ_registry import integration_registry
            
            integration = integration_registry.get_integration(integration_id)
            if integration and integration.get('owner_id') == user.id:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking integration ownership: {e}")
            return False
    
    def grant_integration_permission(self, user: User, permission: str) -> bool:
        """
        Grant integration permission to user
        """
        try:
            # Get the permission object
            try:
                perm = Permission.objects.get(codename=permission, content_type__app_label='alerts')
            except Permission.DoesNotExist:
                logger.error(f"Permission not found: {permission}")
                return False
            
            # Grant permission to user
            user.user_permissions.add(perm)
            
            # Clear cache for this user
            self._clear_user_permission_cache(user)
            
            logger.info(f"Granted permission {permission} to user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error granting integration permission: {e}")
            return False
    
    def revoke_integration_permission(self, user: User, permission: str) -> bool:
        """
        Revoke integration permission from user
        """
        try:
            # Get the permission object
            try:
                perm = Permission.objects.get(codename=permission, content_type__app_label='alerts')
            except Permission.DoesNotExist:
                logger.error(f"Permission not found: {permission}")
                return False
            
            # Revoke permission from user
            user.user_permissions.remove(perm)
            
            # Clear cache for this user
            self._clear_user_permission_cache(user)
            
            logger.info(f"Revoked permission {permission} from user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking integration permission: {e}")
            return False
    
    def _clear_user_permission_cache(self, user: User):
        """
        Clear permission cache for user
        """
        try:
            # Clear all permission cache entries for this user
            cache_pattern = f"integration_perm:{user.id}:*"
            
            # This is a simplified approach - in production you might use
            # a more sophisticated cache invalidation strategy
            cache_keys = cache.keys(cache_pattern)
            for key in cache_keys:
                cache.delete(key)
            
        except Exception as e:
            logger.error(f"Error clearing user permission cache: {e}")
    
    def get_user_permissions(self, user: User) -> List[str]:
        """
        Get all integration permissions for user
        """
        try:
            permissions = []
            
            # Get Django permissions
            user_perms = user.user_permissions.filter(
                content_type__app_label='alerts',
                codename__startswith='can_'
            )
            
            for perm in user_perms:
                permissions.append(perm.codename)
            
            # Add staff permissions if applicable
            if user.is_staff:
                permissions.extend([
                    'can_view_integration',
                    'can_edit_integration',
                    'can_delete_integration',
                    'can_manage_integration_config',
                    'can_trigger_integration'
                ])
            
            # Add superuser permissions if applicable
            if user.is_superuser:
                permissions.extend([
                    'can_create_integration',
                    'can_view_integration',
                    'can_edit_integration',
                    'can_delete_integration',
                    'can_manage_integration_config',
                    'can_trigger_integration',
                    'can_view_integration_logs',
                    'can_manage_integration_fallbacks'
                ])
            
            return list(set(permissions))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return []
    
    def get_auth_statistics(self) -> Dict[str, Any]:
        """
        Get authentication statistics
        """
        try:
            total_auth_checks = self.auth_stats['total_auth_checks']
            successful_auth_checks = self.auth_stats['successful_auth_checks']
            
            success_rate = (successful_auth_checks / max(total_auth_checks, 1)) * 100
            
            return {
                'total_auth_checks': total_auth_checks,
                'successful_auth_checks': successful_auth_checks,
                'failed_auth_checks': self.auth_stats['failed_auth_checks'],
                'success_rate': success_rate,
                'auth_checks_by_type': self.auth_stats['auth_checks_by_type'],
                'last_auth_check': self.auth_stats['last_auth_check'],
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting auth statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }


# Global auth bridge instance
integration_auth_bridge = IntegrationAuthBridge()


# Decorator for permission checking
def require_integration_permission(permission: str, integration_id_param: str = None):
    """
    Decorator for requiring integration permission
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            try:
                user = request.user
                
                if not user.is_authenticated:
                    return {
                        'success': False,
                        'error': 'Authentication required'
                    }
                
                # Get integration ID from kwargs if needed
                integration_id = None
                if integration_id_param and integration_id_param in kwargs:
                    integration_id = kwargs[integration_id_param]
                
                # Check permission
                if not integration_auth_bridge.check_integration_permission(user, permission, integration_id):
                    return {
                        'success': False,
                        'error': f'Permission denied: {permission}'
                    }
                
                # Execute function
                return func(request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in permission decorator: {e}")
                return {
                    'success': False,
                    'error': 'Permission check failed'
                }
        return wrapper
    return decorator


# Utility functions
def check_integration_permission(user: User, permission: str, 
                              integration_id: str = None) -> bool:
    """
    Check integration permission
    """
    return integration_auth_bridge.check_integration_permission(user, permission, integration_id)


def grant_integration_permission(user: User, permission: str) -> bool:
    """
    Grant integration permission
    """
    return integration_auth_bridge.grant_integration_permission(user, permission)


def revoke_integration_permission(user: User, permission: str) -> bool:
    """
    Revoke integration permission
    """
    return integration_auth_bridge.revoke_integration_permission(user, permission)


def get_user_integration_permissions(user: User) -> List[str]:
    """
    Get user integration permissions
    """
    return integration_auth_bridge.get_user_permissions(user)


def get_auth_statistics() -> Dict[str, Any]:
    """
    Get authentication statistics
    """
    return integration_auth_bridge.get_auth_statistics()
