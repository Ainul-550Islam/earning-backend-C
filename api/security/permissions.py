# api/security/permissions.py
"""
Optimized Security Permissions with consolidated classes
Author: System Security Team
Version: 3.0.0 - Cleaned & Optimized
"""

from rest_framework import permissions
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.utils import timezone
from typing import List, Optional, Union
import logging
import functools
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



logger = logging.getLogger(__name__)

# Import security models for enhanced permission checking
try:
    from .models import (
        DeviceInfo, SecurityLog, UserBan, IPBlacklist, 
        ThreatIntelligence, SecurityIncident, TrustedDevice,
        PasswordHistory, SecurityPolicy, SecurityInsight
    )
    SECURITY_MODELS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Security models import failed: {e}")
    SECURITY_MODELS_AVAILABLE = False


class BaseSecurityPermission(permissions.BasePermission):
    """
    Base permission class with defensive coding
    """
    
    def _log_permission_check(self, request, view, result: bool) -> None:
        """Log permission check results"""
        try:
            if not result:
                logger.warning(
                    f"Permission denied for user {request.user.username} "
                    f"on view {view.__class__.__name__}"
                )
        except Exception as e:
            logger.debug(f"Permission log error: {e}")


class IsStaffUser(BaseSecurityPermission):
    """
    Allows access only to staff users.
    """
    
    def has_permission(self, request, view) -> bool:
        try:
            result = bool(request.user and request.user.is_staff)
            self._log_permission_check(request, view, result)
            return result
        except Exception as e:
            logger.error(f"Staff permission check error: {e}")
            return False  # Fail safe - deny access


class IsSuperUser(BaseSecurityPermission):
    """
    Allows access only to superusers.
    Consolidated from duplicate implementations.
    """
    
    def has_permission(self, request, view) -> bool:
        try:
            result = bool(request.user and request.user.is_superuser)
            self._log_permission_check(request, view, result)
            return result
        except Exception as e:
            logger.error(f"Superuser permission check error: {e}")
            return False


class IsAdminOrSecurityTeam(BaseSecurityPermission):
    """
    Allows access to admin users or security team members.
    Consolidated from duplicate implementations.
    """
    
    def has_permission(self, request, view) -> bool:
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Admin users always have access
            if request.user.is_superuser or request.user.is_staff:
                return True
            
            # Check for security team groups
            security_groups = ['Security Admin', 'Security Team', 'Security Manager']
            
            # Use getattr() for safe attribute access
            user_groups = getattr(request.user, 'groups', None)
            if user_groups:
                group_names = user_groups.values_list('name', flat=True)
                for group_name in group_names:
                    if group_name in security_groups:
                        return True
            
            # Check for security permissions
            security_permissions = [
                'security.manage_security',
                'security.view_security_logs',
                'security.manage_users',
                'security.manage_bans'
            ]
            
            for perm in security_permissions:
                if request.user.has_perm(perm):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Admin/Security team permission check error: {e}")
            return False


class IsSecurityAdmin(BaseSecurityPermission):
    """
    Allows access only to security administrators.
    Consolidated from duplicate implementations.
    More restrictive than IsAdminOrSecurityTeam.
    """
    
    def has_permission(self, request, view) -> bool:
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Superusers always have access
            if request.user.is_superuser:
                return True
            
            # Staff users need security admin permission
            if request.user.is_staff:
                return request.user.has_perm('security.manage_security')
            
            # Check for Security Admin group
            user_groups = getattr(request.user, 'groups', None)
            if user_groups:
                group_names = user_groups.values_list('name', flat=True)
                if 'Security Admin' in group_names:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Security admin permission check error: {e}")
            return False


class IsOwnerOrStaff(BaseSecurityPermission):
    """
    Allows access if user is owner of object or staff.
    """
    
    def has_object_permission(self, request, view, obj) -> bool:
        try:
            # Staff users can access any object
            if request.user and request.user.is_staff:
                return True
            
            # Check if user is owner
            if hasattr(obj, 'user') and obj.user == request.user:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Owner/Staff permission check error: {e}")
            return False


class IsOwnerOrReadOnly(BaseSecurityPermission):
    """
    Allows read-only access to any user, but write access only to owner.
    """
    
    def has_object_permission(self, request, view, obj) -> bool:
        try:
            # Read permissions are allowed for any authenticated user
            if request.method in permissions.SAFE_METHODS:
                return True
            
            # Write permissions require ownership
            if hasattr(obj, 'user') and obj.user == request.user:
                return True
            
            # Staff users can write to any object
            if request.user and request.user.is_staff:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Owner/ReadOnly permission check error: {e}")
            return False


class CanManageDevices(BaseSecurityPermission):
    """
    Allows access to users who can manage devices.
    Consolidated from duplicate implementations.
    """
    
    def has_permission(self, request, view) -> bool:
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Staff and superusers can manage devices
            if request.user.is_superuser or request.user.is_staff:
                return True
            
            # Check for device management permission
            if request.user.has_perm('security.manage_devices'):
                return True
            
            # Check for device management groups
            device_groups = ['Device Manager', 'Security Admin', 'Security Team']
            
            user_groups = getattr(request.user, 'groups', None)
            if user_groups:
                group_names = user_groups.values_list('name', flat=True)
                for group_name in group_names:
                    if group_name in device_groups:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Device management permission check error: {e}")
            return False


class HasSecurityPermission(BaseSecurityPermission):
    """
    Generic permission checker for security permissions.
    """
    
    def __init__(self, permission: str):
        self.permission = permission
    
    def has_permission(self, request, view) -> bool:
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            return request.user.has_perm(self.permission)
            
        except Exception as e:
            logger.error(f"Security permission check error: {e}")
            return False


class TimeRestrictedPermission(BaseSecurityPermission):
    """
    Allows access only during specific time periods.
    """
    
    def __init__(self, allowed_hours: List[int] = None):
        self.allowed_hours = allowed_hours or list(range(9, 18))  # 9 AM to 6 PM default
    
    def has_permission(self, request, view) -> bool:
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Superusers bypass time restrictions
            if request.user.is_superuser:
                return True
            
            current_hour = timezone.now().hour
            return current_hour in self.allowed_hours
            
        except Exception as e:
            logger.error(f"Time restriction permission check error: {e}")
            return False


class IPWhitelistPermission(BaseSecurityPermission):
    """
    Allows access only from whitelisted IP addresses.
    """
    
    def __init__(self, allowed_ips: List[str] = None):
        self.allowed_ips = allowed_ips or []
    
    def has_permission(self, request, view) -> bool:
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Superusers bypass IP restrictions
            if request.user.is_superuser:
                return True
            
            client_ip = self._get_client_ip(request)
            return client_ip in self.allowed_ips
            
        except Exception as e:
            logger.error(f"IP whitelist permission check error: {e}")
            return False
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CombinedPermission(BaseSecurityPermission):
    """
    Combines multiple permission classes.
    """
    
    def __init__(self, *permission_classes):
        self.permission_classes = permission_classes
    
    def has_permission(self, request, view) -> bool:
        try:
            for permission_class in self.permission_classes:
                permission = permission_class()
                if not permission.has_permission(request, view):
                    return False
            return True
            
        except Exception as e:
            logger.error(f"Combined permission check error: {e}")
            return False


# Utility functions for creating permissions
def create_security_permission(permission: str) -> HasSecurityPermission:
    """Create a security permission instance."""
    return HasSecurityPermission(permission)


def create_custom_permission(check_func, message: str = "Custom permission check failed"):
    """Create a custom permission with a check function."""
    class CustomPermission(BaseSecurityPermission):
        def has_permission(self, request, view):
            try:
                return check_func(request, view)
            except Exception as e:
                logger.error(f"Custom permission check error: {e}")
                return False
    
    return CustomPermission()


def create_enhanced_security_permission(
    required_permissions: List[str],
    require_all: bool = False
) -> BaseSecurityPermission:
    """Create an enhanced security permission."""
    
    class EnhancedSecurityPermission(BaseSecurityPermission):
        def has_permission(self, request, view):
            try:
                if not request.user or not request.user.is_authenticated:
                    return False
                
                if require_all:
                    return all(request.user.has_perm(perm) for perm in required_permissions)
                else:
                    return any(request.user.has_perm(perm) for perm in required_permissions)
                    
            except Exception as e:
                logger.error(f"Enhanced security permission check error: {e}")
                return False
    
    return EnhancedSecurityPermission()


def create_security_context_permission(context: str):
    """Create a context-based security permission."""
    
    class SecurityContextPermission(BaseSecurityPermission):
        def has_permission(self, request, view):
            try:
                if not request.user or not request.user.is_authenticated:
                    return False
                
                # Check if user has context-specific permission
                context_permission = f"security.{context}"
                return request.user.has_perm(context_permission)
                
            except Exception as e:
                logger.error(f"Security context permission check error: {e}")
                return False
    
    return SecurityContextPermission()


# Decorators for permission checking
def require_permission(permission: str):
    """Decorator to require a specific permission."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            permission_obj = HasSecurityPermission(permission)
            if not permission_obj.has_permission(request, view_func):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(f"Permission '{permission}' required")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_enhanced_permission(
    required_permissions: List[str],
    require_all: bool = False
):
    """Decorator to require enhanced permissions."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            permission_obj = create_enhanced_security_permission(
                required_permissions, require_all
            )
            if not permission_obj.has_permission(request, view_func):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Enhanced permission required")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Export all permission classes and utility functions
__all__ = [
    'BaseSecurityPermission',
    'IsStaffUser',
    'IsSuperUser',
    'IsAdminOrSecurityTeam',
    'IsSecurityAdmin',
    'IsOwnerOrStaff',
    'IsOwnerOrReadOnly',
    'CanManageDevices',
    'HasSecurityPermission',
    'TimeRestrictedPermission',
    'IPWhitelistPermission',
    'CombinedPermission',
    'create_security_permission',
    'create_custom_permission',
    'create_enhanced_security_permission',
    'create_security_context_permission',
    'require_permission',
    'require_enhanced_permission'
]