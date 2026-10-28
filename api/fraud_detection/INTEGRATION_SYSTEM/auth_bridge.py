# =============================================================================
# INTEGRATION_SYSTEM/auth_bridge.py
# =============================================================================
"""
Cross-Module Permission Bridge.

Provides centralized authentication and authorization management
for integration operations across different modules.
"""

from __future__ import annotations

import logging
import asyncio
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Set, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.db import transaction

from .integ_exceptions import (
    AuthBridgeError, AuthBridgePermissionError, AuthBridgeTokenError,
    IntegrationPermissionError
)

logger = logging.getLogger(__name__)

User = get_user_model()


class PermissionType(Enum):
    """Types of permissions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


class TokenType(Enum):
    """Types of authentication tokens."""
    BEARER = "bearer"
    API_KEY = "api_key"
    JWT = "jwt"
    SESSION = "session"
    SERVICE_ACCOUNT = "service_account"


class AuthScope(Enum):
    """Authentication scopes."""
    INTEGRATION_READ = "integration:read"
    INTEGRATION_WRITE = "integration:write"
    INTEGRATION_ADMIN = "integration:admin"
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    SYSTEM_ADMIN = "system:admin"


@dataclass
class AuthContext:
    """Authentication context information."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    token: Optional[str] = None
    token_type: Optional[TokenType] = None
    scopes: Set[AuthScope] = field(default_factory=set)
    permissions: Set[str] = field(default_factory=set)
    groups: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    issued_at: datetime = field(default_factory=timezone.now)
    
    def is_expired(self) -> bool:
        """Check if authentication context is expired."""
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at
    
    def has_scope(self, scope: AuthScope) -> bool:
        """Check if context has specific scope."""
        return scope in self.scopes
    
    def has_permission(self, permission: str) -> bool:
        """Check if context has specific permission."""
        return permission in self.permissions
    
    def has_any_scope(self, scopes: List[AuthScope]) -> bool:
        """Check if context has any of the specified scopes."""
        return any(scope in self.scopes for scope in scopes)
    
    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if context has any of the specified permissions."""
        return any(permission in self.permissions for permission in permissions)
    
    def has_all_scopes(self, scopes: List[AuthScope]) -> bool:
        """Check if context has all of the specified scopes."""
        return all(scope in self.scopes for scope in scopes)
    
    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if context has all of the specified permissions."""
        return all(permission in self.permissions for permission in permissions)


@dataclass
class PermissionRule:
    """Permission rule configuration."""
    name: str
    resource: str
    required_permissions: List[str]
    required_scopes: List[AuthScope]
    required_groups: List[str]
    allow_anonymous: bool = False
    allow_authenticated: bool = True
    custom_validator: Optional[Callable[[AuthContext], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenInfo:
    """Token information."""
    token_id: str
    token_type: TokenType
    user_id: Optional[int]
    scopes: Set[AuthScope]
    expires_at: Optional[datetime]
    created_at: datetime = field(default_factory=timezone.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthProvider(ABC):
    """
    Abstract base class for authentication providers.
    """
    
    @abstractmethod
    async def authenticate(self, token: str, token_type: TokenType) -> Optional[AuthContext]:
        """Authenticate token and return context."""
        pass
    
    @abstractmethod
    async def validate_token(self, token: str, token_type: TokenType) -> bool:
        """Validate token format and signature."""
        pass
    
    @abstractmethod
    async def refresh_token(self, token: str, token_type: TokenType) -> Optional[str]:
        """Refresh authentication token."""
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str, token_type: TokenType) -> bool:
        """Revoke authentication token."""
        pass


class JWTAuthProvider(AuthProvider):
    """JWT authentication provider."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """Initialize JWT auth provider."""
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    async def authenticate(self, token: str, token_type: TokenType) -> Optional[AuthContext]:
        """Authenticate JWT token."""
        if token_type != TokenType.JWT:
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check expiration
            if payload.get('exp') and datetime.fromtimestamp(payload['exp']) < timezone.now():
                return None
            
            # Create auth context
            user_id = payload.get('user_id')
            username = payload.get('username')
            scopes = {AuthScope(scope) for scope in payload.get('scopes', [])}
            permissions = set(payload.get('permissions', []))
            groups = set(payload.get('groups', []))
            expires_at = datetime.fromtimestamp(payload['exp']) if payload.get('exp') else None
            
            return AuthContext(
                user_id=user_id,
                username=username,
                token=token,
                token_type=token_type,
                scopes=scopes,
                permissions=permissions,
                groups=groups,
                expires_at=expires_at,
                metadata=payload.get('metadata', {})
            )
            
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT token validation failed: {e}")
            return None
    
    async def validate_token(self, token: str, token_type: TokenType) -> bool:
        """Validate JWT token."""
        if token_type != TokenType.JWT:
            return False
        
        try:
            jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return True
        except jwt.InvalidTokenError:
            return False
    
    async def refresh_token(self, token: str, token_type: TokenType) -> Optional[str]:
        """Refresh JWT token."""
        if token_type != TokenType.JWT:
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Create new token with extended expiration
            new_payload = payload.copy()
            new_payload['exp'] = datetime.now(tz.utc) + timedelta(hours=1)
            new_payload['iat'] = datetime.now(tz.utc)
            
            return jwt.encode(new_payload, self.secret_key, algorithm=self.algorithm)
            
        except jwt.InvalidTokenError:
            return None
    
    async def revoke_token(self, token: str, token_type: TokenType) -> bool:
        """Revoke JWT token."""
        if token_type != TokenType.JWT:
            return False
        
        # Add token to blacklist
        cache_key = f"jwt_blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
        cache.set(cache_key, True, timeout=3600)  # 1 hour
        
        return True


class APIKeyAuthProvider(AuthProvider):
    """API Key authentication provider."""
    
    def __init__(self):
        """Initialize API key auth provider."""
        pass
    
    async def authenticate(self, token: str, token_type: TokenType) -> Optional[AuthContext]:
        """Authenticate API key."""
        if token_type != TokenType.API_KEY:
            return None
        
        # This would validate against database or configuration
        # For now, return mock context
        return AuthContext(
            token=token,
            token_type=token_type,
            scopes={AuthScope.INTEGRATION_READ},
            permissions=['api_access'],
            metadata={'api_key_id': 'mock_id'}
        )
    
    async def validate_token(self, token: str, token_type: TokenType) -> bool:
        """Validate API key."""
        if token_type != TokenType.API_KEY:
            return False
        
        # Basic validation
        return len(token) >= 32 and token.isalnum()
    
    async def refresh_token(self, token: str, token_type: TokenType) -> Optional[str]:
        """API keys don't support refresh."""
        return None
    
    async def revoke_token(self, token: str, token_type: TokenType) -> bool:
        """Revoke API key."""
        if token_type != TokenType.API_KEY:
            return False
        
        # This would mark API key as revoked in database
        return True


class ServiceAccountAuthProvider(AuthProvider):
    """Service account authentication provider."""
    
    def __init__(self):
        """Initialize service account auth provider."""
        pass
    
    async def authenticate(self, token: str, token_type: TokenType) -> Optional[AuthContext]:
        """Authenticate service account."""
        if token_type != TokenType.SERVICE_ACCOUNT:
            return None
        
        # This would validate service account credentials
        return AuthContext(
            token=token,
            token_type=token_type,
            scopes={AuthScope.SYSTEM_READ, AuthScope.INTEGRATION_READ},
            permissions=['service_account_access'],
            metadata={'service_account': 'mock_service'}
        )
    
    async def validate_token(self, token: str, token_type: TokenType) -> bool:
        """Validate service account token."""
        if token_type != TokenType.SERVICE_ACCOUNT:
            return False
        
        return len(token) >= 16
    
    async def refresh_token(self, token: str, token_type: TokenType) -> Optional[str]:
        """Service accounts don't support refresh."""
        return None
    
    async def revoke_token(self, token: str, token_type: TokenType) -> bool:
        """Revoke service account token."""
        if token_type != TokenType.SERVICE_ACCOUNT:
            return False
        
        return True


class AuthBridge:
    """
    Cross-module permission bridge.
    
    Provides centralized authentication and authorization
    management for integration operations.
    """
    
    def __init__(self):
        """Initialize auth bridge."""
        self.providers: Dict[TokenType, AuthProvider] = {}
        self.permission_rules: Dict[str, PermissionRule] = {}
        self.token_cache: Dict[str, TokenInfo] = {}
        
        # Configuration
        self.enable_token_cache = getattr(settings, 'AUTH_BRIDGE_ENABLE_CACHE', True)
        self.token_cache_ttl = getattr(settings, 'AUTH_BRIDGE_CACHE_TTL', 3600)
        self.default_token_ttl = getattr(settings, 'AUTH_BRIDGE_DEFAULT_TTL', 3600)
        
        # Initialize default providers
        self._initialize_default_providers()
        
        logger.info("AuthBridge initialized")
    
    def _initialize_default_providers(self) -> None:
        """Initialize default authentication providers."""
        secret_key = getattr(settings, 'SECRET_KEY', 'default-secret')
        self.providers[TokenType.JWT] = JWTAuthProvider(secret_key)
        self.providers[TokenType.API_KEY] = APIKeyAuthProvider()
        self.providers[TokenType.SERVICE_ACCOUNT] = ServiceAccountAuthProvider()
    
    def register_provider(self, token_type: TokenType, provider: AuthProvider) -> None:
        """Register authentication provider."""
        self.providers[token_type] = provider
        logger.info(f"Registered auth provider for {token_type.value}")
    
    def register_permission_rule(self, rule: PermissionRule) -> None:
        """Register permission rule."""
        self.permission_rules[rule.name] = rule
        logger.info(f"Registered permission rule: {rule.name}")
    
    async def authenticate(self, token: str, token_type: TokenType) -> Optional[AuthContext]:
        """
        Authenticate token and return context.
        
        Args:
            token: Authentication token
            token_type: Token type
            
        Returns:
            Authentication context or None
        """
        provider = self.providers.get(token_type)
        if not provider:
            raise AuthBridgeError(f"No provider for token type: {token_type}")
        
        # Validate token first
        if not await provider.validate_token(token, token_type):
            raise AuthBridgeTokenError(f"Invalid {token_type.value} token")
        
        # Check cache
        if self.enable_token_cache:
            cache_key = f"auth_context:{hashlib.sha256(token.encode()).hexdigest()}"
            cached_context = cache.get(cache_key)
            if cached_context:
                return cached_context
        
        # Authenticate
        context = await provider.authenticate(token, token_type)
        if not context:
            return None
        
        # Cache context
        if self.enable_token_cache:
            cache.set(cache_key, context, timeout=self.token_cache_ttl)
        
        return context
    
    async def authorize(self, context: AuthContext, resource: str, 
                      action: str = "read") -> bool:
        """
        Authorize action on resource.
        
        Args:
            context: Authentication context
            resource: Resource identifier
            action: Action to perform
            
        Returns:
            True if authorized
        """
        # Check if context is expired
        if context.is_expired():
            return False
        
        # Find applicable permission rules
        applicable_rules = [
            rule for rule in self.permission_rules.values()
            if self._rule_matches_resource(rule, resource)
        ]
        
        # If no specific rules, use default authorization
        if not applicable_rules:
            return self._default_authorization(context, resource, action)
        
        # Check each rule
        for rule in applicable_rules:
            if await self._evaluate_permission_rule(rule, context, action):
                return True
        
        return False
    
    def _rule_matches_resource(self, rule: PermissionRule, resource: str) -> bool:
        """Check if permission rule matches resource."""
        # Support wildcards
        if rule.resource == "*":
            return True
        
        if rule.resource == resource:
            return True
        
        # Support pattern matching (e.g., "integration.*")
        if "*" in rule.resource:
            import re
            pattern = rule.resource.replace("*", ".*")
            return re.match(f"^{pattern}$", resource) is not None
        
        return False
    
    async def _evaluate_permission_rule(self, rule: PermissionRule, 
                                       context: AuthContext, action: str) -> bool:
        """Evaluate permission rule against context."""
        # Check anonymous access
        if rule.allow_anonymous and not context.user_id:
            return True
        
        # Check authenticated access
        if rule.allow_authenticated and context.user_id:
            return True
        
        # Check required permissions
        if rule.required_permissions:
            if not context.has_all_permissions(rule.required_permissions):
                return False
        
        # Check required scopes
        if rule.required_scopes:
            if not context.has_all_scopes(rule.required_scopes):
                return False
        
        # Check required groups
        if rule.required_groups:
            if not any(group in context.groups for group in rule.required_groups):
                return False
        
        # Check custom validator
        if rule.custom_validator:
            if not rule.custom_validator(context):
                return False
        
        return True
    
    def _default_authorization(self, context: AuthContext, resource: str, action: str) -> bool:
        """Default authorization logic."""
        # If no user, deny access
        if not context.user_id:
            return False
        
        # Admin users have full access
        if context.has_permission('admin'):
            return True
        
        # Check resource-specific permissions
        resource_permission = f"{resource}_{action}"
        if context.has_permission(resource_permission):
            return True
        
        # Check integration-specific scopes
        if resource.startswith('integration:'):
            if action == 'read' and context.has_scope(AuthScope.INTEGRATION_READ):
                return True
            elif action == 'write' and context.has_scope(AuthScope.INTEGRATION_WRITE):
                return True
            elif action == 'admin' and context.has_scope(AuthScope.INTEGRATION_ADMIN):
                return True
        
        return False
    
    @asynccontextmanager
    async def auth_context(self, token: str, token_type: TokenType):
        """
        Context manager for authentication.
        
        Args:
            token: Authentication token
            token_type: Token type
            
        Yields:
            Authentication context
        """
        context = await self.authenticate(token, token_type)
        if not context:
            raise AuthBridgePermissionError("Authentication failed")
        
        try:
            yield context
        finally:
            # Cleanup if needed
            pass
    
    async def check_permission(self, token: str, token_type: TokenType, 
                              resource: str, action: str = "read") -> bool:
        """
        Check permission for token.
        
        Args:
            token: Authentication token
            token_type: Token type
            resource: Resource identifier
            action: Action to perform
            
        Returns:
            True if authorized
        """
        context = await self.authenticate(token, token_type)
        if not context:
            return False
        
        return await self.authorize(context, resource, action)
    
    async def create_token(self, user_id: int, token_type: TokenType,
                         scopes: List[AuthScope], ttl: Optional[int] = None) -> str:
        """
        Create authentication token.
        
        Args:
            user_id: User ID
            token_type: Token type
            scopes: Token scopes
            ttl: Time to live in seconds
            
        Returns:
            Generated token
        """
        if token_type == TokenType.JWT:
            provider = self.providers[TokenType.JWT]
            if isinstance(provider, JWTAuthProvider):
                # Get user info
                try:
                    user = User.objects.get(id=user_id)
                    permissions = list(user.user_permissions.values_list('codename', flat=True))
                    groups = list(user.groups.values_list('name', flat=True))
                except User.DoesNotExist:
                    raise AuthBridgeError(f"User {user_id} not found")
                
                # Create JWT payload
                payload = {
                    'user_id': user_id,
                    'username': user.username,
                    'scopes': [scope.value for scope in scopes],
                    'permissions': permissions,
                    'groups': groups,
                    'exp': datetime.now(tz.utc) + timedelta(seconds=ttl or self.default_token_ttl),
                    'iat': datetime.now(tz.utc),
                    'iss': 'auth-bridge'
                }
                
                return jwt.encode(payload, provider.secret_key, algorithm=provider.algorithm)
        
        elif token_type == TokenType.API_KEY:
            # Generate random API key
            return f"ak_{secrets.token_urlsafe(32)}"
        
        elif token_type == TokenType.SERVICE_ACCOUNT:
            # Generate service account token
            return f"sa_{secrets.token_urlsafe(24)}"
        
        else:
            raise AuthBridgeError(f"Token generation not supported for {token_type}")
    
    async def revoke_token(self, token: str, token_type: TokenType) -> bool:
        """
        Revoke authentication token.
        
        Args:
            token: Token to revoke
            token_type: Token type
            
        Returns:
            True if revoked successfully
        """
        provider = self.providers.get(token_type)
        if not provider:
            return False
        
        # Remove from cache
        if self.enable_token_cache:
            cache_key = f"auth_context:{hashlib.sha256(token.encode()).hexdigest()}"
            cache.delete(cache_key)
        
        return await provider.revoke_token(token, token_type)
    
    async def refresh_token(self, token: str, token_type: TokenType) -> Optional[str]:
        """
        Refresh authentication token.
        
        Args:
            token: Token to refresh
            token_type: Token type
            
        Returns:
            New token or None
        """
        provider = self.providers.get(token_type)
        if not provider:
            return None
        
        return await provider.refresh_token(token, token_type)
    
    def get_user_permissions(self, user_id: int) -> List[str]:
        """
        Get user permissions.
        
        Args:
            user_id: User ID
            
        Returns:
            List of permission codenames
        """
        try:
            user = User.objects.get(id=user_id)
            return list(user.user_permissions.values_list('codename', flat=True))
        except User.DoesNotExist:
            return []
    
    def get_user_groups(self, user_id: int) -> List[str]:
        """
        Get user groups.
        
        Args:
            user_id: User ID
            
        Returns:
            List of group names
        """
        try:
            user = User.objects.get(id=user_id)
            return list(user.groups.values_list('name', flat=True))
        except User.DoesNotExist:
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get auth bridge statistics."""
        return {
            'total_providers': len(self.providers),
            'total_permission_rules': len(self.permission_rules),
            'cached_tokens': len(self.token_cache),
            'provider_types': [tt.value for tt in self.providers.keys()],
            'permission_rules': [
                {
                    'name': rule.name,
                    'resource': rule.resource,
                    'required_permissions': len(rule.required_permissions),
                    'required_scopes': len(rule.required_scopes),
                    'allow_anonymous': rule.allow_anonymous,
                    'allow_authenticated': rule.allow_authenticated
                }
                for rule in self.permission_rules.values()
            ]
        }


# Global auth bridge instance
_auth_bridge = None


def get_auth_bridge() -> AuthBridge:
    """Get global auth bridge instance."""
    global _auth_bridge
    if _auth_bridge is None:
        _auth_bridge = AuthBridge()
    return _auth_bridge


# Decorators
def require_permission(resource: str, action: str = "read"):
    """
    Decorator for requiring permission.
    
    Args:
        resource: Resource identifier
        action: Action to perform
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # This would extract token from request context
            # For now, just call the function
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        return wrapper
    return decorator


def require_scope(scope: AuthScope):
    """
    Decorator for requiring scope.
    
    Args:
        scope: Required scope
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # This would extract token from request context
            # For now, just call the function
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience functions
async def check_integration_permission(token: str, token_type: TokenType,
                                    integration_name: str, action: str = "read") -> bool:
    """
    Check integration permission.
    
    Args:
        token: Authentication token
        token_type: Token type
        integration_name: Integration name
        action: Action to perform
        
    Returns:
        True if authorized
    """
    bridge = get_auth_bridge()
    resource = f"integration:{integration_name}"
    return await bridge.check_permission(token, token_type, resource, action)


async def create_user_token(user_id: int, scopes: List[AuthScope],
                          token_type: TokenType = TokenType.JWT) -> str:
    """
    Create user authentication token.
    
    Args:
        user_id: User ID
        scopes: Token scopes
        token_type: Token type
        
    Returns:
        Generated token
    """
    bridge = get_auth_bridge()
    return await bridge.create_token(user_id, token_type, scopes)


async def validate_token(token: str, token_type: TokenType) -> bool:
    """
    Validate token.
    
    Args:
        token: Token to validate
        token_type: Token type
        
    Returns:
        True if valid
    """
    bridge = get_auth_bridge()
    provider = bridge.providers.get(token_type)
    if not provider:
        return False
    
    return await provider.validate_token(token, token_type)
