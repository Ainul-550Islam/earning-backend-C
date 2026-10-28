# engagement/integration_system/auth_bridge.py
"""
Authentication bridge for cross-module permission management.
Provides unified authentication and authorization across integration modules.
"""
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
import hmac
import jwt
import time
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .integ_constants import (
    ERROR_CODES, SUCCESS_CODES, SECURITY_CONFIG, CACHE_KEYS
)
from .integ_exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """Authentication types."""
    API_KEY = "api_key"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER = "bearer"
    CUSTOM = "custom"


class PermissionType(Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    INTEGRATION = "integration"
    WEBHOOK = "webhook"
    SYSTEM = "system"


class TokenType(Enum):
    """Token types."""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    SESSION = "session"


@dataclass
class AuthConfig:
    """Authentication configuration."""
    id: str
    name: str
    auth_type: AuthType
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    permissions: Set[PermissionType] = field(default_factory=set)
    token_expiry: int = 3600  # seconds
    refresh_token_expiry: int = 86400  # seconds
    max_concurrent_sessions: int = 5
    rate_limit: int = 1000  # requests per hour
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)


@dataclass
class AuthContext:
    """Authentication context."""
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    integration_id: Optional[str] = None
    permissions: Set[PermissionType] = field(default_factory=set)
    token_type: TokenType = TokenType.ACCESS
    expires_at: Optional[datetime] = None
    issued_at: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthResult:
    """Authentication result."""
    success: bool
    context: Optional[AuthContext] = None
    token: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAuthProvider(ABC):
    """Base authentication provider."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any], context: Dict[str, Any] = None) -> AuthResult:
        """Authenticate credentials."""
        pass
    
    @abstractmethod
    def generate_token(self, auth_context: AuthContext) -> str:
        """Generate authentication token."""
        pass
    
    @abstractmethod
    def validate_token(self, token: str) -> AuthResult:
        """Validate authentication token."""
        pass
    
    @abstractmethod
    def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh authentication token."""
        pass
    
    @abstractmethod
    def revoke_token(self, token: str) -> bool:
        """Revoke authentication token."""
        pass
    
    def can_handle(self, auth_type: AuthType) -> bool:
        """Check if provider can handle auth type."""
        return True


class ApiKeyAuthProvider(BaseAuthProvider):
    """API key authentication provider."""
    
    def authenticate(self, credentials: Dict[str, Any], context: Dict[str, Any] = None) -> AuthResult:
        """Authenticate with API key."""
        try:
            api_key = credentials.get('api_key')
            if not api_key:
                return AuthResult(
                    success=False,
                    error_message="API key is required",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Validate API key format
            if not self._validate_api_key_format(api_key):
                return AuthResult(
                    success=False,
                    error_message="Invalid API key format",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Get API key from database
            api_key_record = self._get_api_key_record(api_key)
            if not api_key_record:
                return AuthResult(
                    success=False,
                    error_message="Invalid API key",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Check if API key is active
            if not api_key_record.get('active', True):
                return AuthResult(
                    success=False,
                    error_message="API key is inactive",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Check rate limit
            if self._check_rate_limit(api_key):
                return AuthResult(
                    success=False,
                    error_message="Rate limit exceeded",
                    error_code=ERROR_CODES['RATE_LIMIT_EXCEEDED']
                )
            
            # Create auth context
            auth_context = AuthContext(
                user_id=str(api_key_record.get('user_id')),
                tenant_id=str(api_key_record.get('tenant_id')),
                integration_id=str(api_key_record.get('integration_id')),
                permissions=set(api_key_record.get('permissions', [])),
                token_type=TokenType.API_KEY,
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            return AuthResult(
                success=True,
                context=auth_context,
                token=api_key
            )
            
        except Exception as exc:
            self.logger.error(f"API key authentication failed: {exc}")
            return AuthResult(
                success=False,
                error_message="Authentication failed",
                error_code=ERROR_CODES['AUTHENTICATION_FAILED']
            )
    
    def generate_token(self, auth_context: AuthContext) -> str:
        """Generate API key token."""
        try:
            # Generate random API key
            import secrets
            api_key = f"ak_{secrets.token_urlsafe(32)}"
            
            # Store API key
            self._store_api_key(api_key, auth_context)
            
            return api_key
            
        except Exception as exc:
            self.logger.error(f"Failed to generate API key: {exc}")
            raise AuthenticationError(f"Failed to generate API key: {exc}")
    
    def validate_token(self, token: str) -> AuthResult:
        """Validate API key token."""
        return self.authenticate({'api_key': token})
    
    def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh API key (not supported for API keys)."""
        return AuthResult(
            success=False,
            error_message="API key refresh not supported",
            error_code=ERROR_CODES['AUTHENTICATION_FAILED']
        )
    
    def revoke_token(self, token: str) -> bool:
        """Revoke API key."""
        try:
            return self._revoke_api_key(token)
        except Exception as exc:
            self.logger.error(f"Failed to revoke API key: {exc}")
            return False
    
    def can_handle(self, auth_type: AuthType) -> bool:
        """Check if provider can handle auth type."""
        return auth_type == AuthType.API_KEY
    
    def _validate_api_key_format(self, api_key: str) -> bool:
        """Validate API key format."""
        return api_key.startswith('ak_') and len(api_key) >= 35
    
    def _get_api_key_record(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get API key record from storage."""
        # This would get API key from database
        # For now, return mock data
        cache_key = f"api_key:{api_key}"
        return cache.get(cache_key)
    
    def _store_api_key(self, api_key: str, auth_context: AuthContext):
        """Store API key in storage."""
        cache_key = f"api_key:{api_key}"
        api_key_data = {
            'user_id': auth_context.user_id,
            'tenant_id': auth_context.tenant_id,
            'integration_id': auth_context.integration_id,
            'permissions': list(auth_context.permissions),
            'active': True,
            'created_at': timezone.now().isoformat()
        }
        cache.set(cache_key, api_key_data, timeout=86400)  # 24 hours
    
    def _revoke_api_key(self, api_key: str) -> bool:
        """Revoke API key."""
        cache_key = f"api_key:{api_key}"
        cache.delete(cache_key)
        return True
    
    def _check_rate_limit(self, api_key: str) -> bool:
        """Check rate limit for API key."""
        rate_limit_key = f"rate_limit:{api_key}"
        current_count = cache.get(rate_limit_key, 0)
        
        if current_count >= 1000:  # 1000 requests per hour
            return True
        
        # Increment counter
        cache.set(rate_limit_key, current_count + 1, timeout=3600)
        return False


class JwtAuthProvider(BaseAuthProvider):
    """JWT authentication provider."""
    
    def __init__(self, name: str, secret_key: str = None):
        super().__init__(name)
        self.secret_key = secret_key or settings.SECRET_KEY
        self.algorithm = 'HS256'
    
    def authenticate(self, credentials: Dict[str, Any], context: Dict[str, Any] = None) -> AuthResult:
        """Authenticate with username/password and generate JWT."""
        try:
            username = credentials.get('username')
            password = credentials.get('password')
            
            if not username or not password:
                return AuthResult(
                    success=False,
                    error_message="Username and password are required",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Validate user credentials
            user = self._validate_user_credentials(username, password)
            if not user:
                return AuthResult(
                    success=False,
                    error_message="Invalid credentials",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Create auth context
            auth_context = AuthContext(
                user_id=str(user.id),
                tenant_id=str(user.tenant_id) if hasattr(user, 'tenant_id') else None,
                permissions=self._get_user_permissions(user),
                token_type=TokenType.ACCESS,
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            # Generate JWT token
            token = self.generate_token(auth_context)
            
            return AuthResult(
                success=True,
                context=auth_context,
                token=token
            )
            
        except Exception as exc:
            self.logger.error(f"JWT authentication failed: {exc}")
            return AuthResult(
                success=False,
                error_message="Authentication failed",
                error_code=ERROR_CODES['AUTHENTICATION_FAILED']
            )
    
    def generate_token(self, auth_context: AuthContext) -> str:
        """Generate JWT token."""
        try:
            payload = {
                'user_id': auth_context.user_id,
                'tenant_id': auth_context.tenant_id,
                'permissions': list(auth_context.permissions),
                'token_type': auth_context.token_type.value,
                'iat': int(auth_context.issued_at.timestamp()),
                'exp': int(auth_context.expires_at.timestamp()) if auth_context.expires_at else None,
                'jti': f"jwt_{int(time.time())}"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            return token
            
        except Exception as exc:
            self.logger.error(f"Failed to generate JWT token: {exc}")
            raise AuthenticationError(f"Failed to generate JWT token: {exc}")
    
    def validate_token(self, token: str) -> AuthResult:
        """Validate JWT token."""
        try:
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token is blacklisted
            if self._is_token_blacklisted(token):
                return AuthResult(
                    success=False,
                    error_message="Token is blacklisted",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Create auth context
            auth_context = AuthContext(
                user_id=payload.get('user_id'),
                tenant_id=payload.get('tenant_id'),
                permissions=set(payload.get('permissions', [])),
                token_type=TokenType(payload.get('token_type', 'access')),
                issued_at=timezone.fromtimestamp(payload.get('iat', 0)),
                expires_at=timezone.fromtimestamp(payload.get('exp', 0)) if payload.get('exp') else None
            )
            
            return AuthResult(
                success=True,
                context=auth_context,
                token=token
            )
            
        except jwt.ExpiredSignatureError:
            return AuthResult(
                success=False,
                error_message="Token has expired",
                error_code=ERROR_CODES['AUTHENTICATION_FAILED']
            )
        except jwt.InvalidTokenError as exc:
            self.logger.error(f"Invalid JWT token: {exc}")
            return AuthResult(
                success=False,
                error_message="Invalid token",
                error_code=ERROR_CODES['AUTHENTICATION_FAILED']
            )
        except Exception as exc:
            self.logger.error(f"JWT validation failed: {exc}")
            return AuthResult(
                success=False,
                error_message="Token validation failed",
                error_code=ERROR_CODES['AUTHENTICATION_FAILED']
            )
    
    def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh JWT token."""
        try:
            # Validate refresh token
            result = self.validate_token(refresh_token)
            if not result.success:
                return result
            
            auth_context = result.context
            if auth_context.token_type != TokenType.REFRESH:
                return AuthResult(
                    success=False,
                    error_message="Invalid refresh token",
                    error_code=ERROR_CODES['AUTHENTICATION_FAILED']
                )
            
            # Create new auth context
            new_auth_context = AuthContext(
                user_id=auth_context.user_id,
                tenant_id=auth_context.tenant_id,
                permissions=auth_context.permissions,
                token_type=TokenType.ACCESS,
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            # Generate new token
            new_token = self.generate_token(new_auth_context)
            
            return AuthResult(
                success=True,
                context=new_auth_context,
                token=new_token
            )
            
        except Exception as exc:
            self.logger.error(f"JWT refresh failed: {exc}")
            return AuthResult(
                success=False,
                error_message="Token refresh failed",
                error_code=ERROR_CODES['AUTHENTICATION_FAILED']
            )
    
    def revoke_token(self, token: str) -> bool:
        """Revoke JWT token."""
        try:
            # Add token to blacklist
            blacklist_key = f"blacklist:{token}"
            cache.set(blacklist_key, True, timeout=86400)  # 24 hours
            return True
        except Exception as exc:
            self.logger.error(f"Failed to revoke JWT token: {exc}")
            return False
    
    def can_handle(self, auth_type: AuthType) -> bool:
        """Check if provider can handle auth type."""
        return auth_type == AuthType.JWT
    
    def _validate_user_credentials(self, username: str, password: str) -> Optional[Any]:
        """Validate user credentials."""
        try:
            User = get_user_model()
            user = User.objects.get(username=username)
            
            if user.check_password(password):
                return user
            return None
        except User.DoesNotExist:
            return None
        except Exception as exc:
            self.logger.error(f"User validation failed: {exc}")
            return None
    
    def _get_user_permissions(self, user) -> Set[PermissionType]:
        """Get user permissions."""
        # This would get user permissions from database
        # For now, return basic permissions
        permissions = {PermissionType.READ}
        
        if user.is_staff:
            permissions.add(PermissionType.WRITE)
            permissions.add(PermissionType.ADMIN)
        
        if user.is_superuser:
            permissions.add(PermissionType.SYSTEM)
        
        return permissions
    
    def _is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        blacklist_key = f"blacklist:{token}"
        return cache.get(blacklist_key, False)


class AuthBridge:
    """Authentication bridge for unified auth management."""
    
    def __init__(self):
        self.providers: Dict[AuthType, BaseAuthProvider] = {}
        self.auth_configs: Dict[str, AuthConfig] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.AuthBridge")
        
        # Register default providers
        self._register_default_providers()
    
    def _register_default_providers(self):
        """Register default authentication providers."""
        self.providers[AuthType.API_KEY] = ApiKeyAuthProvider('api_key')
        self.providers[AuthType.JWT] = JwtAuthProvider('jwt')
    
    def register_provider(self, auth_type: AuthType, provider: BaseAuthProvider):
        """Register authentication provider."""
        self.providers[auth_type] = provider
        self.logger.info(f"Registered auth provider for {auth_type}")
    
    def add_auth_config(self, config: AuthConfig) -> bool:
        """Add authentication configuration."""
        try:
            with self._lock:
                self.auth_configs[config.id] = config
                self.logger.info(f"Added auth config: {config.id}")
                return True
        except Exception as exc:
            self.logger.error(f"Failed to add auth config {config.id}: {exc}")
            return False
    
    def authenticate(self, auth_type: AuthType, credentials: Dict[str, Any], 
                   context: Dict[str, Any] = None) -> AuthResult:
        """Authenticate credentials."""
        provider = self.providers.get(auth_type)
        if not provider:
            return AuthResult(
                success=False,
                error_message=f"No provider for auth type: {auth_type}",
                error_code=ERROR_CODES['AUTHENTICATION_FAILED']
            )
        
        return provider.authenticate(credentials, context)
    
    def validate_token(self, token: str, token_type: TokenType = TokenType.ACCESS) -> AuthResult:
        """Validate authentication token."""
        # Try each provider
        for provider in self.providers.values():
            result = provider.validate_token(token)
            if result.success:
                return result
        
        return AuthResult(
            success=False,
            error_message="Invalid token",
            error_code=ERROR_CODES['AUTHENTICATION_FAILED']
        )
    
    def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh authentication token."""
        for provider in self.providers.values():
            result = provider.refresh_token(refresh_token)
            if result.success:
                return result
        
        return AuthResult(
            success=False,
            error_message="Token refresh failed",
            error_code=ERROR_CODES['AUTHENTICATION_FAILED']
        )
    
    def revoke_token(self, token: str) -> bool:
        """Revoke authentication token."""
        success_count = 0
        
        for provider in self.providers.values():
            if provider.revoke_token(token):
                success_count += 1
        
        return success_count > 0
    
    def check_permission(self, auth_context: AuthContext, permission: PermissionType) -> bool:
        """Check if user has permission."""
        if not auth_context or not auth_context.permissions:
            return False
        
        return permission in auth_context.permissions
    
    def check_permissions(self, auth_context: AuthContext, permissions: List[PermissionType]) -> bool:
        """Check if user has all permissions."""
        if not auth_context or not auth_context.permissions:
            return False
        
        return all(perm in auth_context.permissions for perm in permissions)
    
    def has_any_permission(self, auth_context: AuthContext, permissions: List[PermissionType]) -> bool:
        """Check if user has any of the specified permissions."""
        if not auth_context or not auth_context.permissions:
            return False
        
        return any(perm in auth_context.permissions for perm in permissions)
    
    def get_user_context(self, user_id: str) -> Optional[AuthContext]:
        """Get user authentication context."""
        try:
            # This would get user context from database or cache
            cache_key = f"user_context:{user_id}"
            context_data = cache.get(cache_key)
            
            if context_data:
                return AuthContext(
                    user_id=context_data['user_id'],
                    tenant_id=context_data.get('tenant_id'),
                    permissions=set(context_data.get('permissions', [])),
                    token_type=TokenType(context_data.get('token_type', 'access')),
                    expires_at=datetime.fromisoformat(context_data['expires_at']) if context_data.get('expires_at') else None
                )
            
            return None
        except Exception as exc:
            self.logger.error(f"Failed to get user context: {exc}")
            return None
    
    def cache_user_context(self, auth_context: AuthContext, timeout: int = 3600):
        """Cache user authentication context."""
        try:
            cache_key = f"user_context:{auth_context.user_id}"
            context_data = {
                'user_id': auth_context.user_id,
                'tenant_id': auth_context.tenant_id,
                'permissions': list(auth_context.permissions),
                'token_type': auth_context.token_type.value,
                'expires_at': auth_context.expires_at.isoformat() if auth_context.expires_at else None
            }
            cache.set(cache_key, context_data, timeout=timeout)
        except Exception as exc:
            self.logger.error(f"Failed to cache user context: {exc}")


class PermissionManager:
    """Manager for permission checking and enforcement."""
    
    def __init__(self, auth_bridge: AuthBridge):
        self.auth_bridge = auth_bridge
        self.logger = logging.getLogger(f"{__name__}.PermissionManager")
    
    def require_permission(self, permission: PermissionType):
        """Decorator to require specific permission."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Get auth context from request or kwargs
                auth_context = kwargs.get('auth_context')
                if not auth_context:
                    raise AuthorizationError(
                        f"Permission {permission} required but no auth context found",
                        permission=permission.value
                    )
                
                if not self.auth_bridge.check_permission(auth_context, permission):
                    raise AuthorizationError(
                        f"Permission {permission} denied",
                        permission=permission.value
                    )
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_permissions(self, permissions: List[PermissionType], require_all: bool = True):
        """Decorator to require multiple permissions."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                auth_context = kwargs.get('auth_context')
                if not auth_context:
                    raise AuthorizationError(
                        "Permissions required but no auth context found"
                    )
                
                if require_all:
                    if not self.auth_bridge.check_permissions(auth_context, permissions):
                        raise AuthorizationError(
                            f"Required permissions denied: {', '.join(p.value for p in permissions)}"
                        )
                else:
                    if not self.auth_bridge.has_any_permission(auth_context, permissions):
                        raise AuthorizationError(
                            f"No required permissions found: {', '.join(p.value for p in permissions)}"
                        )
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def check_integration_permission(self, integration_id: str, auth_context: AuthContext) -> bool:
        """Check if user has permission for specific integration."""
        if not auth_context:
            return False
        
        # Check admin permissions
        if PermissionType.ADMIN in auth_context.permissions:
            return True
        
        # Check if user owns the integration
        if auth_context.integration_id == integration_id:
            return True
        
        # Check integration-specific permissions
        return PermissionType.INTEGRATION in auth_context.permissions
    
    def filter_by_permission(self, items: List[Any], auth_context: AuthContext, 
                           permission_check: Callable) -> List[Any]:
        """Filter items based on user permissions."""
        if not auth_context:
            return []
        
        filtered_items = []
        for item in items:
            if permission_check(item, auth_context):
                filtered_items.append(item)
        
        return filtered_items


# DRF Authentication class
class IntegrationAuthentication(BaseAuthentication):
    """DRF authentication for integration system."""
    
    def __init__(self):
        self.auth_bridge = AuthBridge()
        self.logger = logging.getLogger(f"{__name__}.IntegrationAuthentication")
    
    def authenticate(self, request):
        """Authenticate request."""
        try:
            # Get token from header
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            
            if not auth_header:
                return None
            
            # Parse header
            parts = auth_header.split(' ', 1)
            if len(parts) != 2:
                return None
            
            scheme, token = parts
            
            if scheme.lower() == 'bearer':
                # JWT token
                result = self.auth_bridge.validate_token(token)
            elif scheme.lower() == 'apikey':
                # API key
                result = self.auth_bridge.validate_token(token)
            else:
                return None
            
            if result.success and result.context:
                # Get user object
                user = self._get_user_from_context(result.context)
                if user:
                    return (user, result.context)
            
            return None
            
        except Exception as exc:
            self.logger.error(f"Authentication failed: {exc}")
            raise AuthenticationFailed(str(exc))
    
    def _get_user_from_context(self, auth_context: AuthContext):
        """Get user object from auth context."""
        try:
            User = get_user_model()
            return User.objects.get(id=auth_context.user_id)
        except User.DoesNotExist:
            return None
        except Exception as exc:
            self.logger.error(f"Failed to get user from context: {exc}")
            return None


# Global instances
auth_bridge = AuthBridge()
permission_manager = PermissionManager(auth_bridge)


# Auth utilities
class AuthUtils:
    """Utilities for authentication and authorization."""
    
    @staticmethod
    def create_auth_config(config_id: str, name: str, auth_type: AuthType, 
                          permissions: List[PermissionType], **kwargs) -> AuthConfig:
        """Create authentication configuration."""
        return AuthConfig(
            id=config_id,
            name=name,
            auth_type=auth_type,
            permissions=set(permissions),
            **kwargs
        )
    
    @staticmethod
    def generate_api_key(user_id: str, permissions: List[PermissionType] = None) -> str:
        """Generate API key for user."""
        auth_context = AuthContext(
            user_id=user_id,
            permissions=set(permissions or [PermissionType.READ]),
            token_type=TokenType.API_KEY
        )
        
        provider = auth_bridge.providers.get(AuthType.API_KEY)
        if provider:
            return provider.generate_token(auth_context)
        
        raise AuthenticationError("API key provider not available")
    
    @staticmethod
    def generate_jwt_token(user_id: str, permissions: List[PermissionType] = None) -> str:
        """Generate JWT token for user."""
        auth_context = AuthContext(
            user_id=user_id,
            permissions=set(permissions or [PermissionType.READ]),
            token_type=TokenType.ACCESS,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        provider = auth_bridge.providers.get(AuthType.JWT)
        if provider:
            return provider.generate_token(auth_context)
        
        raise AuthenticationError("JWT provider not available")
    
    @staticmethod
    def validate_request_permissions(request, required_permissions: List[PermissionType]) -> bool:
        """Validate request permissions."""
        try:
            # Get auth context from request
            if hasattr(request, 'auth_context'):
                auth_context = request.auth_context
            else:
                # Try to get from DRF authentication
                auth, auth_context = request.auth, getattr(request, 'auth_context', None)
                if not auth_context:
                    return False
            
            return auth_bridge.check_permissions(auth_context, required_permissions)
        except Exception:
            return False
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password."""
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify password."""
        from django.contrib.auth.hashers import check_password
        return check_password(password, hashed_password)
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate session token."""
        import secrets
        return f"session_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def create_permission_context(user_id: str, tenant_id: str = None, 
                                permissions: List[PermissionType] = None) -> Dict[str, Any]:
        """Create permission context for templates/APIs."""
        return {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'permissions': [p.value for p in (permissions or [])],
            'can_read': PermissionType.READ in (permissions or []),
            'can_write': PermissionType.WRITE in (permissions or []),
            'can_delete': PermissionType.DELETE in (permissions or []),
            'can_admin': PermissionType.ADMIN in (permissions or []),
            'can_integration': PermissionType.INTEGRATION in (permissions or []),
            'can_webhook': PermissionType.WEBHOOK in (permissions or []),
            'can_system': PermissionType.SYSTEM in (permissions or []),
        }


# Decorators
def require_permission(permission: PermissionType):
    """Decorator to require specific permission."""
    return permission_manager.require_permission(permission)


def require_permissions(permissions: List[PermissionType], require_all: bool = True):
    """Decorator to require multiple permissions."""
    return permission_manager.require_permissions(permissions, require_all)


def with_auth_context():
    """Decorator to add auth context to function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get auth context from request
            if 'request' in kwargs:
                request = kwargs['request']
                if hasattr(request, 'auth_context'):
                    kwargs['auth_context'] = request.auth_context
                elif hasattr(request, 'user') and request.user.is_authenticated:
                    # Create basic auth context
                    kwargs['auth_context'] = AuthContext(
                        user_id=str(request.user.id),
                        permissions=set([PermissionType.READ])
                    )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
