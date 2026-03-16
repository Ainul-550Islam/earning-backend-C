# api/security/permissions.py
from rest_framework import permissions
from django.contrib.auth.models import Group
from typing import List, Optional
import logging
import functools

logger = logging.getLogger(__name__)


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


class IsOwnerOrAdmin(BaseSecurityPermission):
    """
    Allows access to object owners or admin users.
    """
    
    def has_object_permission(self, request, view, obj) -> bool:
        try:
            # Admin users always have access
            if request.user.is_superuser or request.user.is_staff:
                return True
            
            # Check if user owns the object
            # Try different common field names for ownership
            owner_fields = ['user', 'owner', 'created_by', 'user_id', 'owner_id']
            
            for field in owner_fields:
                try:
                    owner = getattr(obj, field, None)
                    if owner and owner == request.user:
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Owner/Admin permission check error: {e}")
            return False


class IsReadOnlyOrAdmin(BaseSecurityPermission):
    """
    Allows read-only access to anyone, but write access only to admin users.
    """
    
    def has_permission(self, request, view) -> bool:
        try:
            # Allow all read-only requests
            if request.method in permissions.SAFE_METHODS:
                return True
            
            # Write operations require admin access
            return bool(
                request.user and 
                (request.user.is_superuser or request.user.is_staff)
            )
            
        except Exception as e:
            logger.error(f"ReadOnly/Admin permission check error: {e}")
            return False


class HasSecurityPermission(BaseSecurityPermission):
    """
    Checks for specific security permissions.
    """
    
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
        super().__init__()
    
    def has_permission(self, request, view) -> bool:
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Superusers bypass all permission checks
            if request.user.is_superuser:
                return True
            
            # Check each required permission
            for perm in self.required_permissions:
                if not request.user.has_perm(perm):
                    logger.warning(
                        f"User {request.user.username} missing permission: {perm}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Security permission check error: {e}")
            return False


class RateLimitPermission(BaseSecurityPermission):
    """
    Implements rate limiting at the permission level.
    """
    
    def __init__(self, max_requests: int = 100, time_window: int = 3600):
        self.max_requests = max_requests
        self.time_window = time_window
        super().__init__()
    
    def has_permission(self, request, view) -> bool:
        try:
            # Skip rate limiting for admin users
            if request.user and (request.user.is_superuser or request.user.is_staff):
                return True
            
            # Implement rate limiting logic here
            # You would typically use Django's cache framework
            
            return True  # Placeholder
            
        except Exception as e:
            logger.error(f"Rate limit permission check error: {e}")
            return True  # Allow on error


class IPWhitelistPermission(BaseSecurityPermission):
    """
    Allows access only from whitelisted IP addresses.
    """
    
    def __init__(self, whitelisted_ips: List[str] = None):
        self.whitelisted_ips = whitelisted_ips or []
        super().__init__()
    
    def get_client_ip(self, request) -> str:
        """Get client IP address safely"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '')
            return ip
        except Exception:
            return ''
    
    def has_permission(self, request, view) -> bool:
        try:
            client_ip = self.get_client_ip(request)
            
            # Allow localhost for development
            if client_ip in ['127.0.0.1', 'localhost', '::1']:
                return True
            
            # Check if IP is whitelisted
            if client_ip in self.whitelisted_ips:
                return True
            
            # Admin users can bypass IP restriction
            if request.user and (request.user.is_superuser or request.user.is_staff):
                logger.info(f"Admin user {request.user.username} bypassing IP restriction from {client_ip}")
                return True
            
            logger.warning(f"IP {client_ip} not in whitelist")
            return False
            
        except Exception as e:
            logger.error(f"IP whitelist permission check error: {e}")
            return False  # Deny on error for security


class TimeRestrictedPermission(BaseSecurityPermission):
    """
    Allows access only during specific hours.
    """
    
    def __init__(self, start_hour: int = 0, end_hour: int = 24):
        self.start_hour = start_hour
        self.end_hour = end_hour
        super().__init__()
    
    def has_permission(self, request, view) -> bool:
        try:
            from django.utils import timezone
            current_hour = timezone.now().hour
            
            # Admin users can bypass time restriction
            if request.user and (request.user.is_superuser or request.user.is_staff):
                return True
            
            # Check if current hour is within allowed range
            if self.start_hour <= current_hour < self.end_hour:
                return True
            
            logger.warning(
                f"Access denied outside allowed hours ({self.start_hour}-{self.end_hour}). "
                f"Current hour: {current_hour}"
            )
            return False
            
        except Exception as e:
            logger.error(f"Time restricted permission check error: {e}")
            return False


class CombinedPermission(BaseSecurityPermission):
    """
    Combines multiple permissions (all must pass).
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


# ============ PERMISSION FACTORY FUNCTIONS ============

def create_security_permission(min_level: str = 'staff') -> BaseSecurityPermission:
    """
    Factory function to create security permissions based on level.
    
    Args:
        min_level: Minimum security level required.
                   Options: 'staff', 'admin', 'security_team', 'security_admin', 'superuser'
    """
    
    permission_map = {
        'staff': IsStaffUser,
        'admin': IsAdminOrSecurityTeam,
        'security_team': IsAdminOrSecurityTeam,
        'security_admin': IsSecurityAdmin,
        'superuser': IsSuperUser,
    }
    
    permission_class = permission_map.get(min_level, IsStaffUser)
    return permission_class()


def create_custom_permission(**kwargs) -> BaseSecurityPermission:
    """
    Create custom permission based on parameters.
    """
    
    permissions = []
    
    # Add IP restriction if specified
    whitelisted_ips = kwargs.get('whitelisted_ips')
    if whitelisted_ips:
        permissions.append(IPWhitelistPermission(whitelisted_ips=whitelisted_ips))
    
    # Add time restriction if specified
    time_window = kwargs.get('time_window')
    if time_window:
        start_hour, end_hour = time_window
        permissions.append(TimeRestrictedPermission(start_hour=start_hour, end_hour=end_hour))
    
    # Add security level permission
    security_level = kwargs.get('security_level', 'staff')
    permissions.append(create_security_permission(security_level))
    
    # Add specific permissions if specified
    required_permissions = kwargs.get('required_permissions')
    if required_permissions:
        permissions.append(HasSecurityPermission(required_permissions=required_permissions))
    
    # Add rate limiting if specified
    rate_limit_params = kwargs.get('rate_limit')
    if rate_limit_params:
        permissions.append(RateLimitPermission(**rate_limit_params))
    
    # Return combined permission
    if len(permissions) == 1:
        return permissions[0]
    else:
        return CombinedPermission(*permissions)


# ============ PERMISSION DECORATORS ============

def require_permission(permission_class):
    """
    Decorator to apply permission check to function-based views.
    """
    
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            permission = permission_class()
            if permission.has_permission(request, None):
                return view_func(request, *args, **kwargs)
            else:
                from rest_framework.response import Response
                from rest_framework import status
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        return wrapped_view
    return decorator


# ============ EXPORTS ============

__all__ = [
    'BaseSecurityPermission',
    'IsStaffUser',
    'IsSuperUser',
    'IsAdminOrSecurityTeam',
    'IsSecurityAdmin',
    'IsOwnerOrAdmin',
    'IsReadOnlyOrAdmin',
    'HasSecurityPermission',
    'RateLimitPermission',
    'IPWhitelistPermission',
    'TimeRestrictedPermission',
    'CombinedPermission',
    'create_security_permission',
    'create_custom_permission',
    'require_permission'
]


# permissions.py ফাইলে এটি যোগ করুন
class IsSuperUser(permissions.BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)