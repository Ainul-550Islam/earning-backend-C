"""
Auth Bridge - Cross-Module Permission Management

Authentication and authorization bridge for managing permissions
across different modules and services with role-based access control.
"""

import logging
import threading
from typing import Dict, Any, List, Optional, Callable, Union, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationStatus
from .integ_exceptions import IntegrationError, AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class PermissionType(Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXECUTE = "execute"
    APPROVE = "approve"
    MANAGE = "manage"


class ResourceType(Enum):
    """Resource types."""
    RATE_LIMIT_CONFIG = "rate_limit_config"
    USER_PROFILE = "user_profile"
    ABUSE_REPORT = "abuse_report"
    IP_BLOCK = "ip_block"
    SYSTEM_CONFIG = "system_config"
    AUDIT_LOG = "audit_log"
    COMPLIANCE_REPORT = "compliance_report"
    INTEGRATION_CONFIG = "integration_config"


class AccessLevel(Enum):
    """Access levels."""
    NONE = 0
    READ_ONLY = 1
    READ_WRITE = 2
    ADMIN = 3
    SUPER_ADMIN = 4


@dataclass
class Permission:
    """Permission definition."""
    name: str
    resource_type: ResourceType
    permission_type: PermissionType
    description: str = ""
    is_system: bool = False
    created_at: datetime = field(default_factory=timezone.now)


@dataclass
class Role:
    """Role definition."""
    name: str
    description: str
    permissions: Set[str] = field(default_factory=set)
    is_system: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)


@dataclass
class UserPermission:
    """User permission assignment."""
    user_id: str
    permissions: Set[str] = field(default_factory=set)
    roles: Set[str] = field(default_factory=set)
    granted_at: datetime = field(default_factory=timezone.now)
    granted_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessRequest:
    """Access request record."""
    request_id: str
    user_id: str
    resource_type: ResourceType
    permission_type: PermissionType
    resource_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=timezone.now)
    expires_at: Optional[datetime] = None


class AuthBridge:
    """Authentication and authorization bridge."""
    
    def __init__(self):
        self.permissions: Dict[str, Permission] = {}
        self.roles: Dict[str, Role] = {}
        self.user_permissions: Dict[str, UserPermission] = {}
        self.access_cache: Dict[str, Dict[str, Any]] = {}
        self.permission_handlers: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        
        # Initialize system permissions and roles
        self._initialize_system_permissions()
        self._initialize_system_roles()
    
    def _initialize_system_permissions(self):
        """Initialize system permissions."""
        system_permissions = [
            # Rate limit permissions
            Permission("rate_limit.read", ResourceType.RATE_LIMIT_CONFIG, PermissionType.READ, "Read rate limit configurations"),
            Permission("rate_limit.write", ResourceType.RATE_LIMIT_CONFIG, PermissionType.WRITE, "Write rate limit configurations"),
            Permission("rate_limit.delete", ResourceType.RATE_LIMIT_CONFIG, PermissionType.DELETE, "Delete rate limit configurations"),
            Permission("rate_limit.admin", ResourceType.RATE_LIMIT_CONFIG, PermissionType.ADMIN, "Admin rate limit configurations"),
            
            # User profile permissions
            Permission("user_profile.read", ResourceType.USER_PROFILE, PermissionType.READ, "Read user profiles"),
            Permission("user_profile.write", ResourceType.USER_PROFILE, PermissionType.WRITE, "Write user profiles"),
            Permission("user_profile.delete", ResourceType.USER_PROFILE, PermissionType.DELETE, "Delete user profiles"),
            Permission("user_profile.admin", ResourceType.USER_PROFILE, PermissionType.ADMIN, "Admin user profiles"),
            
            # Abuse report permissions
            Permission("abuse_report.read", ResourceType.ABUSE_REPORT, PermissionType.READ, "Read abuse reports"),
            Permission("abuse_report.write", ResourceType.ABUSE_REPORT, PermissionType.WRITE, "Write abuse reports"),
            Permission("abuse_report.delete", ResourceType.ABUSE_REPORT, PermissionType.DELETE, "Delete abuse reports"),
            Permission("abuse_report.approve", ResourceType.ABUSE_REPORT, PermissionType.APPROVE, "Approve abuse reports"),
            
            # IP block permissions
            Permission("ip_block.read", ResourceType.IP_BLOCK, PermissionType.READ, "Read IP blocks"),
            Permission("ip_block.write", ResourceType.IP_BLOCK, PermissionType.WRITE, "Write IP blocks"),
            Permission("ip_block.delete", ResourceType.IP_BLOCK, PermissionType.DELETE, "Delete IP blocks"),
            Permission("ip_block.admin", ResourceType.IP_BLOCK, PermissionType.ADMIN, "Admin IP blocks"),
            
            # System config permissions
            Permission("system_config.read", ResourceType.SYSTEM_CONFIG, PermissionType.READ, "Read system configurations"),
            Permission("system_config.write", ResourceType.SYSTEM_CONFIG, PermissionType.WRITE, "Write system configurations"),
            Permission("system_config.admin", ResourceType.SYSTEM_CONFIG, PermissionType.ADMIN, "Admin system configurations"),
            
            # Audit log permissions
            Permission("audit_log.read", ResourceType.AUDIT_LOG, PermissionType.READ, "Read audit logs"),
            Permission("audit_log.delete", ResourceType.AUDIT_LOG, PermissionType.DELETE, "Delete audit logs"),
            Permission("audit_log.admin", ResourceType.AUDIT_LOG, PermissionType.ADMIN, "Admin audit logs"),
            
            # Compliance report permissions
            Permission("compliance_report.read", ResourceType.COMPLIANCE_REPORT, PermissionType.READ, "Read compliance reports"),
            Permission("compliance_report.write", ResourceType.COMPLIANCE_REPORT, PermissionType.WRITE, "Write compliance reports"),
            Permission("compliance_report.approve", ResourceType.COMPLIANCE_REPORT, PermissionType.APPROVE, "Approve compliance reports"),
            
            # Integration config permissions
            Permission("integration_config.read", ResourceType.INTEGRATION_CONFIG, PermissionType.READ, "Read integration configurations"),
            Permission("integration_config.write", ResourceType.INTEGRATION_CONFIG, PermissionType.WRITE, "Write integration configurations"),
            Permission("integration_config.admin", ResourceType.INTEGRATION_CONFIG, PermissionType.ADMIN, "Admin integration configurations"),
            
            # Super admin permissions
            Permission("super_admin", ResourceType.SYSTEM_CONFIG, PermissionType.ADMIN, "Super admin access", True),
        ]
        
        for perm in system_permissions:
            perm.is_system = True
            self.permissions[perm.name] = perm
    
    def _initialize_system_roles(self):
        """Initialize system roles."""
        system_roles = [
            Role("viewer", "Read-only access to all resources", {
                "rate_limit.read", "user_profile.read", "abuse_report.read",
                "ip_block.read", "system_config.read", "audit_log.read",
                "compliance_report.read", "integration_config.read"
            }, True),
            
            Role("operator", "Operational access to rate limiting", {
                "rate_limit.read", "rate_limit.write", "user_profile.read",
                "abuse_report.read", "abuse_report.write", "ip_block.read",
                "ip_block.write", "audit_log.read", "compliance_report.read"
            }, True),
            
            Role("analyst", "Security analyst access", {
                "rate_limit.read", "user_profile.read", "abuse_report.read",
                "abuse_report.write", "abuse_report.approve", "ip_block.read",
                "ip_block.write", "audit_log.read", "compliance_report.read",
                "compliance_report.write"
            }, True),
            
            Role("admin", "Administrator access", {
                "rate_limit.read", "rate_limit.write", "rate_limit.admin",
                "user_profile.read", "user_profile.write", "user_profile.admin",
                "abuse_report.read", "abuse_report.write", "abuse_report.delete",
                "ip_block.read", "ip_block.write", "ip_block.admin",
                "system_config.read", "audit_log.read", "audit_log.delete",
                "compliance_report.read", "compliance_report.write",
                "integration_config.read", "integration_config.write"
            }, True),
            
            Role("super_admin", "Super administrator access", {
                "super_admin"
            }, True),
        ]
        
        for role in system_roles:
            role.is_system = True
            self.roles[role.name] = role
    
    def register_permission(self, permission: Permission):
        """Register a new permission."""
        with self._lock:
            self.permissions[permission.name] = permission
            logger.info(f"Registered permission: {permission.name}")
    
    def register_role(self, role: Role):
        """Register a new role."""
        with self._lock:
            self.roles[role.name] = role
            logger.info(f"Registered role: {role.name}")
    
    def grant_permission_to_user(self, user_id: str, permission_name: str, 
                                granted_by: str = None, expires_at: datetime = None):
        """Grant permission to user."""
        with self._lock:
            if permission_name not in self.permissions:
                raise AuthorizationError(f"Permission not found: {permission_name}")
            
            if user_id not in self.user_permissions:
                self.user_permissions[user_id] = UserPermission(user_id=user_id, granted_by=granted_by)
            
            self.user_permissions[user_id].permissions.add(permission_name)
            self.user_permissions[user_id].granted_at = timezone.now()
            
            if expires_at:
                self.user_permissions[user_id].expires_at = expires_at
            
            # Clear cache
            self._clear_user_cache(user_id)
            
            logger.info(f"Granted permission {permission_name} to user {user_id}")
    
    def revoke_permission_from_user(self, user_id: str, permission_name: str):
        """Revoke permission from user."""
        with self._lock:
            if user_id in self.user_permissions:
                self.user_permissions[user_id].permissions.discard(permission_name)
                
                # Clear cache
                self._clear_user_cache(user_id)
                
                logger.info(f"Revoked permission {permission_name} from user {user_id}")
    
    def grant_role_to_user(self, user_id: str, role_name: str, 
                          granted_by: str = None, expires_at: datetime = None):
        """Grant role to user."""
        with self._lock:
            if role_name not in self.roles:
                raise AuthorizationError(f"Role not found: {role_name}")
            
            if user_id not in self.user_permissions:
                self.user_permissions[user_id] = UserPermission(user_id=user_id, granted_by=granted_by)
            
            self.user_permissions[user_id].roles.add(role_name)
            self.user_permissions[user_id].granted_at = timezone.now()
            
            if expires_at:
                self.user_permissions[user_id].expires_at = expires_at
            
            # Clear cache
            self._clear_user_cache(user_id)
            
            logger.info(f"Granted role {role_name} to user {user_id}")
    
    def revoke_role_from_user(self, user_id: str, role_name: str):
        """Revoke role from user."""
        with self._lock:
            if user_id in self.user_permissions:
                self.user_permissions[user_id].roles.discard(role_name)
                
                # Clear cache
                self._clear_user_cache(user_id)
                
                logger.info(f"Revoked role {role_name} from user {user_id}")
    
    def check_permission(self, user_id: str, permission_name: str, 
                         resource_id: str = None, context: Dict[str, Any] = None) -> bool:
        """Check if user has permission."""
        try:
            # Check cache first
            cache_key = f"auth_check:{user_id}:{permission_name}:{resource_id or 'all'}"
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Get user permissions
            user_perms = self._get_user_permissions(user_id)
            
            # Check if permission is expired
            if user_perms.expires_at and user_perms.expires_at <= timezone.now():
                return False
            
            # Check direct permission
            if permission_name in user_perms.permissions:
                result = True
            else:
                # Check role permissions
                result = False
                for role_name in user_perms.roles:
                    role = self.roles.get(role_name)
                    if role and role.is_active and permission_name in role.permissions:
                        result = True
                        break
            
            # Check custom permission handler
            if not result and permission_name in self.permission_handlers:
                handler = self.permission_handlers[permission_name]
                result = handler(user_id, permission_name, resource_id, context)
            
            # Cache result
            cache.set(cache_key, result, timeout=300)  # 5 minutes
            
            return result
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            return False
    
    def check_access_level(self, user_id: str, resource_type: ResourceType, 
                          resource_id: str = None, context: Dict[str, Any] = None) -> AccessLevel:
        """Check user's access level for resource type."""
        # Check permissions in order of increasing access
        if self.check_permission(user_id, f"{resource_type.value}.read", resource_id, context):
            if self.check_permission(user_id, f"{resource_type.value}.write", resource_id, context):
                if self.check_permission(user_id, f"{resource_type.value}.admin", resource_id, context):
                    return AccessLevel.ADMIN
                else:
                    return AccessLevel.READ_WRITE
            else:
                return AccessLevel.READ_ONLY
        else:
            return AccessLevel.NONE
    
    def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """Get all user permissions and roles."""
        user_perms = self._get_user_permissions(user_id)
        
        # Get all permissions from roles
        all_permissions = set(user_perms.permissions)
        for role_name in user_perms.roles:
            role = self.roles.get(role_name)
            if role and role.is_active:
                all_permissions.update(role.permissions)
        
        return {
            'user_id': user_id,
            'direct_permissions': list(user_perms.permissions),
            'roles': list(user_perms.roles),
            'all_permissions': list(all_permissions),
            'granted_at': user_perms.granted_at.isoformat(),
            'granted_by': user_perms.granted_by,
            'expires_at': user_perms.expires_at.isoformat() if user_perms.expires_at else None,
            'metadata': user_perms.metadata
        }
    
    def _get_user_permissions(self, user_id: str) -> UserPermission:
        """Get user permissions object."""
        if user_id not in self.user_permissions:
            self.user_permissions[user_id] = UserPermission(user_id=user_id)
        
        return self.user_permissions[user_id]
    
    def _clear_user_cache(self, user_id: str):
        """Clear user permission cache."""
        # Clear all cache entries for this user
        cache_pattern = f"auth_check:{user_id}:*"
        
        # This would ideally use cache.delete_many_pattern, but we'll simulate it
        for key in list(self.access_cache.keys()):
            if key.startswith(f"auth_check:{user_id}:"):
                cache.delete(key)
                self.access_cache.pop(key, None)
    
    def register_permission_handler(self, permission_name: str, handler: Callable):
        """Register custom permission handler."""
        self.permission_handlers[permission_name] = handler
        logger.info(f"Registered permission handler: {permission_name}")
    
    def get_permission_info(self, permission_name: str) -> Optional[Dict[str, Any]]:
        """Get permission information."""
        permission = self.permissions.get(permission_name)
        if not permission:
            return None
        
        return {
            'name': permission.name,
            'resource_type': permission.resource_type.value,
            'permission_type': permission.permission_type.value,
            'description': permission.description,
            'is_system': permission.is_system,
            'created_at': permission.created_at.isoformat()
        }
    
    def get_role_info(self, role_name: str) -> Optional[Dict[str, Any]]:
        """Get role information."""
        role = self.roles.get(role_name)
        if not role:
            return None
        
        return {
            'name': role.name,
            'description': role.description,
            'permissions': list(role.permissions),
            'is_system': role.is_system,
            'is_active': role.is_active,
            'created_at': role.created_at.isoformat(),
            'updated_at': role.updated_at.isoformat()
        }
    
    def list_permissions(self, resource_type: ResourceType = None) -> List[Dict[str, Any]]:
        """List all permissions."""
        permissions = []
        
        for permission in self.permissions.values():
            if resource_type is None or permission.resource_type == resource_type:
                permissions.append(self.get_permission_info(permission.name))
        
        return permissions
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """List all roles."""
        return [self.get_role_info(role_name) for role_name in self.roles.keys()]
    
    def cleanup_expired_permissions(self) -> int:
        """Clean up expired user permissions."""
        current_time = timezone.now()
        expired_users = []
        
        for user_id, user_perms in self.user_permissions.items():
            if user_perms.expires_at and user_perms.expires_at <= current_time:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_permissions[user_id]
            self._clear_user_cache(user_id)
        
        logger.info(f"Cleaned up {len(expired_users)} expired user permissions")
        return len(expired_users)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get auth bridge statistics."""
        total_permissions = len(self.permissions)
        total_roles = len(self.roles)
        total_users = len(self.user_permissions)
        
        # Count active users
        current_time = timezone.now()
        active_users = sum(
            1 for user_perms in self.user_permissions.values()
            if not user_perms.expires_at or user_perms.expires_at > current_time
        )
        
        # Count permissions by type
        permissions_by_type = {}
        for permission in self.permissions.values():
            resource_type = permission.resource_type.value
            if resource_type not in permissions_by_type:
                permissions_by_type[resource_type] = 0
            permissions_by_type[resource_type] += 1
        
        return {
            'total_permissions': total_permissions,
            'total_roles': total_roles,
            'total_users': total_users,
            'active_users': active_users,
            'expired_users': total_users - active_users,
            'permissions_by_type': permissions_by_type,
            'custom_handlers': len(self.permission_handlers)
        }


# Decorators for permission checking
def require_permission(permission_name: str, resource_id_param: str = None):
    """Decorator to require specific permission."""
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Get user from request
            user_id = getattr(request, 'user_id', None)
            if not user_id and hasattr(request, 'user') and request.user.is_authenticated:
                user_id = str(request.user.id)
            
            if not user_id:
                raise AuthenticationError("User not authenticated")
            
            # Get resource ID
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = kwargs[resource_id_param]
            
            # Check permission
            if not auth_bridge.check_permission(user_id, permission_name, resource_id):
                raise AuthorizationError(f"Permission denied: {permission_name}")
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_access_level(resource_type: ResourceType, min_level: AccessLevel, 
                       resource_id_param: str = None):
    """Decorator to require minimum access level."""
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Get user from request
            user_id = getattr(request, 'user_id', None)
            if not user_id and hasattr(request, 'user') and request.user.is_authenticated:
                user_id = str(request.user.id)
            
            if not user_id:
                raise AuthenticationError("User not authenticated")
            
            # Get resource ID
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = kwargs[resource_id_param]
            
            # Check access level
            user_level = auth_bridge.check_access_level(user_id, resource_type, resource_id)
            if user_level.value < min_level.value:
                raise AuthorizationError(f"Access level insufficient: {user_level.value} < {min_level.value}")
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(role_name: str):
    """Decorator to require specific role."""
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Get user from request
            user_id = getattr(request, 'user_id', None)
            if not user_id and hasattr(request, 'user') and request.user.is_authenticated:
                user_id = str(request.user.id)
            
            if not user_id:
                raise AuthenticationError("User not authenticated")
            
            # Check if user has role
            user_perms = auth_bridge._get_user_permissions(user_id)
            if role_name not in user_perms.roles:
                raise AuthorizationError(f"Role required: {role_name}")
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# Global auth bridge instance
auth_bridge = AuthBridge()


# Convenience functions
def create_permission(name: str, resource_type: ResourceType, permission_type: PermissionType,
                    description: str = "") -> Permission:
    """Create a new permission."""
    return Permission(
        name=name,
        resource_type=resource_type,
        permission_type=permission_type,
        description=description
    )


def create_role(name: str, description: str, permissions: List[str]) -> Role:
    """Create a new role."""
    return Role(
        name=name,
        description=description,
        permissions=set(permissions)
    )


def grant_default_permissions(user_id: str, role_name: str = "viewer"):
    """Grant default permissions to user."""
    auth_bridge.grant_role_to_user(user_id, role_name, granted_by="system")


def is_super_admin(user_id: str) -> bool:
    """Check if user is super admin."""
    return auth_bridge.check_permission(user_id, "super_admin")


def is_admin(user_id: str) -> bool:
    """Check if user is admin."""
    return (auth_bridge.check_permission(user_id, "super_admin") or
            any(role in ["admin", "super_admin"] for role in auth_bridge._get_user_permissions(user_id).roles))
