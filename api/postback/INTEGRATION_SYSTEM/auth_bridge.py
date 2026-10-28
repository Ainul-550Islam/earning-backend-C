"""
auth_bridge.py – Authentication Bridge for postback module.

Provides comprehensive cross-module authentication functionality including:
- Authentication token management
- Permission validation
- Role-based access control
- Cross-module permission bridging
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import jwt
import hashlib
import secrets

from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.db.models import Q
from django.conf import settings

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException, IntegrationAuthenticationException, IntegrationAuthorizationException

logger = logging.getLogger(__name__)
User = get_user_model()


class TokenType(Enum):
    """Token type enumeration."""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    SERVICE = "service"
    WEBHOOK = "webhook"
    INTEGRATION = "integration"


class PermissionType(Enum):
    """Permission type enumeration."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SYSTEM = "system"
    INTEGRATION = "integration"
    WEBHOOK = "webhook"
    ANALYTICS = "analytics"


class AuthMethod(Enum):
    """Authentication method enumeration."""
    JWT = "jwt"
    API_KEY = "api_key"
    OAUTH = "oauth"
    BASIC = "basic"
    SESSION = "session"
    SERVICE_ACCOUNT = "service_account"


@dataclass
class AuthToken:
    """Authentication token data structure."""
    token: str
    token_type: TokenType
    user_id: Optional[int] = None
    service_id: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=timezone.now)
    last_used: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'token': self.token,
            'token_type': self.token_type.value,
            'user_id': self.user_id,
            'service_id': self.service_id,
            'permissions': list(self.permissions),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'metadata': self.metadata,
        }


@dataclass
class Permission:
    """Permission data structure."""
    name: str
    description: str
    permission_type: PermissionType
    resource: str
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'permission_type': self.permission_type.value,
            'resource': self.resource,
            'conditions': self.conditions,
        }


@dataclass
class Role:
    """Role data structure."""
    name: str
    description: str
    permissions: Set[str] = field(default_factory=set)
    is_system_role: bool = False
    created_at: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'permissions': list(self.permissions),
            'is_system_role': self.is_system_role,
            'created_at': self.created_at.isoformat(),
        }


class TokenManager:
    """
    Token management for authentication.
    
    Handles token generation, validation, and lifecycle.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.secret_key = getattr(settings, 'SECRET_KEY', 'default-secret')
        self.algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
        self.access_token_expiry = getattr(settings, 'JWT_ACCESS_TOKEN_EXPIRY', 3600)  # 1 hour
        self.refresh_token_expiry = getattr(settings, 'JWT_REFRESH_TOKEN_EXPIRY', 86400)  # 24 hours
        self.api_key_expiry = getattr(settings, 'API_KEY_EXPIRY', 2592000)  # 30 days
    
    def generate_jwt_token(self, user_id: int, token_type: TokenType = TokenType.ACCESS,
                          permissions: Set[str] = None, expires_in: int = None) -> AuthToken:
        """
        Generate JWT token.
        
        Args:
            user_id: User ID
            token_type: Token type
            permissions: User permissions
            expires_in: Expiration time in seconds
            
        Returns:
            Authentication token
        """
        if expires_in is None:
            if token_type == TokenType.ACCESS:
                expires_in = self.access_token_expiry
            elif token_type == TokenType.REFRESH:
                expires_in = self.refresh_token_expiry
            else:
                expires_in = self.access_token_expiry
        
        now = timezone.now()
        expires_at = now + timedelta(seconds=expires_in)
        
        payload = {
            'user_id': user_id,
            'token_type': token_type.value,
            'permissions': list(permissions or []),
            'iat': int(now.timestamp()),
            'exp': int(expires_at.timestamp()),
            'jti': secrets.token_urlsafe(16),
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        return AuthToken(
            token=token,
            token_type=token_type,
            user_id=user_id,
            permissions=permissions or set(),
            expires_at=expires_at
        )
    
    def generate_api_key(self, user_id: int, service_name: str = None,
                        permissions: Set[str] = None) -> AuthToken:
        """
        Generate API key.
        
        Args:
            user_id: User ID
            service_name: Service name
            permissions: API key permissions
            
        Returns:
            Authentication token
        """
        # Generate secure random key
        api_key = secrets.token_urlsafe(32)
        
        # Hash for storage
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        expires_at = timezone.now() + timedelta(seconds=self.api_key_expiry)
        
        metadata = {
            'service_name': service_name,
            'key_hash': api_key_hash,
        }
        
        return AuthToken(
            token=api_key,
            token_type=TokenType.API_KEY,
            user_id=user_id,
            permissions=permissions or set(),
            expires_at=expires_at,
            metadata=metadata
        )
    
    def generate_service_token(self, service_id: str, permissions: Set[str] = None) -> AuthToken:
        """
        Generate service token.
        
        Args:
            service_id: Service ID
            permissions: Service permissions
            
        Returns:
            Authentication token
        """
        now = timezone.now()
        expires_at = now + timedelta(seconds=self.access_token_expiry)
        
        payload = {
            'service_id': service_id,
            'token_type': TokenType.SERVICE.value,
            'permissions': list(permissions or []),
            'iat': int(now.timestamp()),
            'exp': int(expires_at.timestamp()),
            'jti': secrets.token_urlsafe(16),
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        return AuthToken(
            token=token,
            token_type=TokenType.SERVICE,
            service_id=service_id,
            permissions=permissions or set(),
            expires_at=expires_at
        )
    
    def validate_token(self, token: str, token_type: TokenType = None) -> Optional[AuthToken]:
        """
        Validate token.
        
        Args:
            token: Token string
            token_type: Expected token type
            
        Returns:
            Authentication token or None
        """
        try:
            if token_type == TokenType.API_KEY:
                return self._validate_api_key(token)
            else:
                return self._validate_jwt_token(token, token_type)
        
        except Exception as e:
            self.logger.error(f"Token validation failed: {str(e)}")
            return None
    
    def _validate_jwt_token(self, token: str, token_type: TokenType = None) -> Optional[AuthToken]:
        """Validate JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type if specified
            if token_type and payload.get('token_type') != token_type.value:
                return None
            
            # Create token object
            expires_at = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
            
            return AuthToken(
                token=token,
                token_type=TokenType(payload['token_type']),
                user_id=payload.get('user_id'),
                service_id=payload.get('service_id'),
                permissions=set(payload.get('permissions', [])),
                expires_at=expires_at,
                created_at=datetime.fromtimestamp(payload['iat'], tz=timezone.utc)
            )
        
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def _validate_api_key(self, api_key: str) -> Optional[AuthToken]:
        """Validate API key."""
        # This would typically validate against database
        # For now, just check format
        if len(api_key) < 32:
            return None
        
        # Create mock token (in real implementation, would query database)
        return AuthToken(
            token=api_key,
            token_type=TokenType.API_KEY,
            permissions={'api_access'},
            expires_at=timezone.now() + timedelta(days=30)
        )
    
    def refresh_token(self, refresh_token: str) -> Optional[AuthToken]:
        """
        Refresh access token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New access token or None
        """
        token = self.validate_token(refresh_token, TokenType.REFRESH)
        if not token:
            return None
        
        # Generate new access token
        return self.generate_jwt_token(
            user_id=token.user_id,
            token_type=TokenType.ACCESS,
            permissions=token.permissions
        )


class PermissionManager:
    """
    Permission management for authorization.
    
    Handles permission validation, role management,
    and access control.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.permissions: Dict[str, Permission] = {}
        self.roles: Dict[str, Role] = {}
        self._setup_default_permissions()
        self._setup_default_roles()
    
    def _setup_default_permissions(self):
        """Setup default permissions."""
        default_permissions = [
            Permission(
                name="postback_read",
                description="Read postback data",
                permission_type=PermissionType.READ,
                resource="postback"
            ),
            Permission(
                name="postback_write",
                description="Write postback data",
                permission_type=PermissionType.WRITE,
                resource="postback"
            ),
            Permission(
                name="postback_delete",
                description="Delete postback data",
                permission_type=PermissionType.DELETE,
                resource="postback"
            ),
            Permission(
                name="webhook_manage",
                description="Manage webhooks",
                permission_type=PermissionType.WEBHOOK,
                resource="webhook"
            ),
            Permission(
                name="analytics_view",
                description="View analytics",
                permission_type=PermissionType.ANALYTICS,
                resource="analytics"
            ),
            Permission(
                name="integration_admin",
                description="Administer integrations",
                permission_type=PermissionType.INTEGRATION,
                resource="integration"
            ),
            Permission(
                name="system_admin",
                description="System administration",
                permission_type=PermissionType.SYSTEM,
                resource="system"
            ),
        ]
        
        for permission in default_permissions:
            self.permissions[permission.name] = permission
    
    def _setup_default_roles(self):
        """Setup default roles."""
        default_roles = [
            Role(
                name="viewer",
                description="Read-only access",
                permissions={"postback_read", "analytics_view"}
            ),
            Role(
                name="editor",
                description="Read and write access",
                permissions={"postback_read", "postback_write", "analytics_view"}
            ),
            Role(
                name="admin",
                description="Full access",
                permissions={
                    "postback_read", "postback_write", "postback_delete",
                    "webhook_manage", "analytics_view", "integration_admin"
                }
            ),
            Role(
                name="system_admin",
                description="System administrator",
                permissions={
                    "postback_read", "postback_write", "postback_delete",
                    "webhook_manage", "analytics_view", "integration_admin",
                    "system_admin"
                },
                is_system_role=True
            ),
        ]
        
        for role in default_roles:
            self.roles[role.name] = role
    
    def add_permission(self, permission: Permission):
        """Add permission."""
        self.permissions[permission.name] = permission
        self.logger.info(f"Permission added: {permission.name}")
    
    def add_role(self, role: Role):
        """Add role."""
        self.roles[role.name] = role
        self.logger.info(f"Role added: {role.name}")
    
    def get_user_permissions(self, user_id: int) -> Set[str]:
        """
        Get user permissions.
        
        Args:
            user_id: User ID
            
        Returns:
            Set of permission names
        """
        try:
            user = User.objects.get(id=user_id)
            
            # Get direct permissions
            direct_permissions = set()
            for perm in user.user_permissions.all():
                direct_permissions.add(f"{perm.content_type.app_label}.{perm.codename}")
            
            # Get role permissions
            role_permissions = set()
            for group in user.groups.all():
                for perm in group.permissions.all():
                    role_permissions.add(f"{perm.content_type.app_label}.{perm.codename}")
            
            # Map to internal permissions
            internal_permissions = set()
            all_permissions = direct_permissions.union(role_permissions)
            
            # Map Django permissions to internal permissions
            permission_mapping = {
                'postback.view_postbacklog': 'postback_read',
                'postback.add_postbacklog': 'postback_write',
                'postback.change_postbacklog': 'postback_write',
                'postback.delete_postbacklog': 'postback_delete',
                'api.view_webhook': 'webhook_manage',
                'api.add_webhook': 'webhook_manage',
                'api.change_webhook': 'webhook_manage',
                'api.delete_webhook': 'webhook_manage',
                'analytics.view_insight': 'analytics_view',
                'api.view_integration': 'integration_admin',
                'api.add_integration': 'integration_admin',
                'api.change_integration': 'integration_admin',
                'api.delete_integration': 'integration_admin',
            }
            
            for django_perm in all_permissions:
                if django_perm in permission_mapping:
                    internal_permissions.add(permission_mapping[django_perm])
            
            return internal_permissions
        
        except User.DoesNotExist:
            return set()
        except Exception as e:
            self.logger.error(f"Error getting user permissions: {str(e)}")
            return set()
    
    def get_service_permissions(self, service_id: str) -> Set[str]:
        """
        Get service permissions.
        
        Args:
            service_id: Service ID
            
        Returns:
            Set of permission names
        """
        # This would typically query service configuration
        # For now, return default service permissions
        service_permissions = {
            'webhook_service': {'webhook_manage', 'postback_read'},
            'analytics_service': {'analytics_view', 'postback_read'},
            'integration_service': {'integration_admin', 'postback_read', 'postback_write'},
        }
        
        return service_permissions.get(service_id, {'postback_read'})
    
    def has_permission(self, permissions: Set[str], required_permission: str,
                      resource: str = None, context: Dict[str, Any] = None) -> bool:
        """
        Check if permissions include required permission.
        
        Args:
            permissions: User permissions
            required_permission: Required permission
            resource: Resource being accessed
            context: Additional context
            
        Returns:
            True if permission granted
        """
        # Direct permission check
        if required_permission in permissions:
            return True
        
        # Check for wildcard permissions
        if 'system_admin' in permissions:
            return True
        
        # Check resource-specific permissions
        if resource:
            resource_permission = f"{resource}_admin"
            if resource_permission in permissions:
                return True
        
        # Check conditional permissions
        permission_obj = self.permissions.get(required_permission)
        if permission_obj and permission_obj.conditions:
            return self._evaluate_conditions(permission_obj.conditions, context or {})
        
        return False
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate permission conditions."""
        for condition_key, condition_value in conditions.items():
            context_value = context.get(condition_key)
            
            if context_value is None:
                return False
            
            if isinstance(condition_value, list):
                if context_value not in condition_value:
                    return False
            elif context_value != condition_value:
                return False
        
        return True


class AuthBridge:
    """
    Authentication bridge for cross-module authentication.
    
    Handles authentication, authorization, and permission
    bridging between different modules.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.token_manager = TokenManager()
        self.permission_manager = PermissionManager()
        self.active_tokens: Dict[str, AuthToken] = {}
        self._setup_auth_middleware()
    
    def _setup_auth_middleware(self):
        """Setup authentication middleware hooks."""
        # This would integrate with Django middleware
        pass
    
    def authenticate_user(self, username: str, password: str) -> Optional[AuthToken]:
        """
        Authenticate user with credentials.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            Authentication token or None
        """
        try:
            from django.contrib.auth import authenticate
            
            user = authenticate(username=username, password=password)
            if not user:
                return None
            
            # Get user permissions
            permissions = self.permission_manager.get_user_permissions(user.id)
            
            # Generate tokens
            access_token = self.token_manager.generate_jwt_token(
                user_id=user.id,
                token_type=TokenType.ACCESS,
                permissions=permissions
            )
            
            refresh_token = self.token_manager.generate_jwt_token(
                user_id=user.id,
                token_type=TokenType.REFRESH,
                permissions=permissions
            )
            
            # Store active token
            self.active_tokens[access_token.token] = access_token
            
            return access_token
        
        except Exception as e:
            self.logger.error(f"User authentication failed: {str(e)}")
            return None
    
    def authenticate_service(self, service_id: str, service_secret: str) -> Optional[AuthToken]:
        """
        Authenticate service.
        
        Args:
            service_id: Service ID
            service_secret: Service secret
            
        Returns:
            Authentication token or None
        """
        try:
            # Validate service credentials (would check against database)
            if not self._validate_service_credentials(service_id, service_secret):
                return None
            
            # Get service permissions
            permissions = self.permission_manager.get_service_permissions(service_id)
            
            # Generate service token
            token = self.token_manager.generate_service_token(
                service_id=service_id,
                permissions=permissions
            )
            
            # Store active token
            self.active_tokens[token.token] = token
            
            return token
        
        except Exception as e:
            self.logger.error(f"Service authentication failed: {str(e)}")
            return None
    
    def _validate_service_credentials(self, service_id: str, service_secret: str) -> bool:
        """Validate service credentials."""
        # This would typically validate against database
        # For now, just check format
        return len(service_id) > 0 and len(service_secret) > 0
    
    def authenticate_api_key(self, api_key: str) -> Optional[AuthToken]:
        """
        Authenticate with API key.
        
        Args:
            api_key: API key
            
        Returns:
            Authentication token or None
        """
        try:
            token = self.token_manager.validate_token(api_key, TokenType.API_KEY)
            if not token:
                return None
            
            # Store active token
            self.active_tokens[token.token] = token
            
            return token
        
        except Exception as e:
            self.logger.error(f"API key authentication failed: {str(e)}")
            return None
    
    def authorize_request(self, token: str, required_permission: str,
                          resource: str = None, context: Dict[str, Any] = None) -> bool:
        """
        Authorize request.
        
        Args:
            token: Authentication token
            required_permission: Required permission
            resource: Resource being accessed
            context: Request context
            
        Returns:
            True if authorized
        """
        try:
            # Validate token
            auth_token = self.token_manager.validate_token(token)
            if not auth_token:
                return False
            
            # Check if token is expired
            if auth_token.is_expired():
                return False
            
            # Update last used time
            auth_token.last_used = timezone.now()
            
            # Check permissions
            return self.permission_manager.has_permission(
                auth_token.permissions,
                required_permission,
                resource,
                context
            )
        
        except Exception as e:
            self.logger.error(f"Authorization failed: {str(e)}")
            return False
    
    def get_user_from_token(self, token: str) -> Optional[User]:
        """
        Get user from token.
        
        Args:
            token: Authentication token
            
        Returns:
            User object or None
        """
        try:
            auth_token = self.token_manager.validate_token(token)
            if not auth_token or not auth_token.user_id:
                return None
            
            return User.objects.get(id=auth_token.user_id)
        
        except User.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting user from token: {str(e)}")
            return None
    
    def create_api_key(self, user_id: int, service_name: str = None,
                      permissions: Set[str] = None) -> AuthToken:
        """
        Create API key for user.
        
        Args:
            user_id: User ID
            service_name: Service name
            permissions: API key permissions
            
        Returns:
            Authentication token
        """
        try:
            # Get user permissions if not provided
            if permissions is None:
                permissions = self.permission_manager.get_user_permissions(user_id)
            
            # Generate API key
            api_key = self.token_manager.generate_api_key(
                user_id=user_id,
                service_name=service_name,
                permissions=permissions
            )
            
            # Store API key (would save to database)
            self.active_tokens[api_key.token] = api_key
            
            return api_key
        
        except Exception as e:
            self.logger.error(f"API key creation failed: {str(e)}")
            raise IntegrationAuthenticationException(f"API key creation failed: {str(e)}")
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke token.
        
        Args:
            token: Token to revoke
            
        Returns:
            True if revoked
        """
        try:
            if token in self.active_tokens:
                del self.active_tokens[token]
                self.logger.info(f"Token revoked: {token[:10]}...")
                return True
            return False
        
        except Exception as e:
            self.logger.error(f"Token revocation failed: {str(e)}")
            return False
    
    def refresh_access_token(self, refresh_token: str) -> Optional[AuthToken]:
        """
        Refresh access token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New access token or None
        """
        try:
            new_token = self.token_manager.refresh_token(refresh_token)
            if new_token:
                # Store new token
                self.active_tokens[new_token.token] = new_token
                # Remove old refresh token
                self.revoke_token(refresh_token)
            
            return new_token
        
        except Exception as e:
            self.logger.error(f"Token refresh failed: {str(e)}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get authentication statistics."""
        total_tokens = len(self.active_tokens)
        
        # Count by token type
        token_types = {}
        for token in self.active_tokens.values():
            token_type = token.token_type.value
            token_types[token_type] = token_types.get(token_type, 0) + 1
        
        # Count expired tokens
        expired_tokens = len([t for t in self.active_tokens.values() if t.is_expired()])
        
        return {
            'total_active_tokens': total_tokens,
            'expired_tokens': expired_tokens,
            'token_types': token_types,
            'total_permissions': len(self.permission_manager.permissions),
            'total_roles': len(self.permission_manager.roles),
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return {
            'status': 'healthy',
            'token_manager': 'active',
            'permission_manager': 'active',
            'active_tokens': len(self.active_tokens),
            'timestamp': timezone.now().isoformat(),
        }


# Global auth bridge instance
auth_bridge = AuthBridge()


# Decorators for authentication and authorization
def require_authentication(auth_method: AuthMethod = AuthMethod.JWT):
    """
    Decorator for requiring authentication.
    
    Args:
        auth_method: Authentication method
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Extract token from request
            token = None
            
            if auth_method == AuthMethod.JWT:
                token = request.META.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
            elif auth_method == AuthMethod.API_KEY:
                token = request.META.get('HTTP_X_API_KEY', '')
            elif auth_method == AuthMethod.SESSION:
                token = request.session.get('auth_token')
            
            if not token:
                raise IntegrationAuthenticationException("Authentication required")
            
            # Validate token
            auth_token = auth_bridge.token_manager.validate_token(token)
            if not auth_token or auth_token.is_expired():
                raise IntegrationAuthenticationException("Invalid or expired token")
            
            # Add user to request
            request.auth_token = auth_token
            request.user = auth_bridge.get_user_from_token(token)
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission: str, resource: str = None):
    """
    Decorator for requiring permission.
    
    Args:
        permission: Required permission
        resource: Resource being accessed
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'auth_token'):
                raise IntegrationAuthorizationException("Authentication required")
            
            # Check authorization
            context = {
                'user_id': request.auth_token.user_id,
                'service_id': request.auth_token.service_id,
                'method': request.method,
                'path': request.path,
            }
            
            if not auth_bridge.authorize_request(
                request.auth_token.token,
                permission,
                resource,
                context
            ):
                raise IntegrationAuthorizationException(f"Permission denied: {permission}")
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# Convenience functions
def authenticate_user(username: str, password: str) -> Optional[AuthToken]:
    """Authenticate user."""
    return auth_bridge.authenticate_user(username, password)


def authenticate_service(service_id: str, service_secret: str) -> Optional[AuthToken]:
    """Authenticate service."""
    return auth_bridge.authenticate_service(service_id, service_secret)


def create_api_key(user_id: int, service_name: str = None,
                  permissions: Set[str] = None) -> AuthToken:
    """Create API key."""
    return auth_bridge.create_api_key(user_id, service_name, permissions)


def authorize_request(token: str, required_permission: str,
                    resource: str = None, context: Dict[str, Any] = None) -> bool:
    """Authorize request."""
    return auth_bridge.authorize_request(token, required_permission, resource, context)


def get_auth_statistics() -> Dict[str, Any]:
    """Get authentication statistics."""
    return auth_bridge.get_statistics()
