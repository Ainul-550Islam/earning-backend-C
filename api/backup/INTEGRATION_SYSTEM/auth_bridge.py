"""
Auth Bridge
Authentication and authorization bridge for cross-module permissions
"""

import logging
from typing import Dict, Any, Optional, List, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import hashlib
import jwt
from abc import ABC, abstractmethod

from .integ_exceptions import IntegrationException, AuthBridgeException, AuthenticationException, AuthorizationException

logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Authentication methods"""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    BASIC_AUTH = "basic_auth"
    CERTIFICATE = "certificate"
    SAML = "saml"
    LDAP = "ldap"
    CUSTOM = "custom"


class PermissionType(Enum):
    """Permission types"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXECUTE = "execute"
    INTEGRATE = "integrate"
    MANAGE = "manage"
    MONITOR = "monitor"


class AuthScope(Enum):
    """Authentication scopes"""
    SYSTEM = "system"
    MODULE = "module"
    TENANT = "tenant"
    USER = "user"
    GLOBAL = "global"
    LIMITED = "limited"


@dataclass
class AuthCredentials:
    """Authentication credentials"""
    auth_method: AuthMethod
    credentials: Dict[str, Any]
    expires_at: Optional[datetime] = None
    issued_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if credentials are expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert credentials to dictionary"""
        return {
            'auth_method': self.auth_method.value,
            'credentials': self.credentials,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'issued_at': self.issued_at.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class AuthUser:
    """Authenticated user information"""
    user_id: str
    username: str
    email: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    permissions: Set[PermissionType] = field(default_factory=set)
    tenant_id: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def has_permission(self, permission: PermissionType) -> bool:
        """Check if user has permission"""
        return permission in self.permissions
    
    def has_role(self, role: str) -> bool:
        """Check if user has role"""
        return role in self.roles
    
    def is_in_group(self, group: str) -> bool:
        """Check if user is in group"""
        return group in self.groups


@dataclass
class AuthContext:
    """Authentication context"""
    request_id: str
    source_system: str
    target_system: str
    operation: str
    user: Optional[AuthUser] = None
    credentials: Optional[AuthCredentials] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthPolicy:
    """Authentication and authorization policy"""
    policy_id: str
    name: str
    auth_methods: List[AuthMethod]
    required_permissions: Set[PermissionType]
    allowed_roles: List[str]
    allowed_groups: List[str]
    ip_whitelist: List[str] = field(default_factory=list)
    ip_blacklist: List[str] = field(default_factory=list)
    time_restrictions: Dict[str, Any] = field(default_factory=dict)
    rate_limits: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 5
    conditions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AuthResult:
    """Authentication/authorization result"""
    success: bool
    user: Optional[AuthUser] = None
    credentials: Optional[AuthCredentials] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    permissions_granted: Set[PermissionType] = field(default_factory=set)
    auth_method_used: Optional[AuthMethod] = None
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAuthProvider(ABC):
    """Abstract base class for authentication providers"""
    
    @abstractmethod
    async def authenticate(self, credentials: AuthCredentials, context: AuthContext) -> AuthUser:
        """Authenticate user with credentials"""
        pass
    
    @abstractmethod
    def can_handle(self, auth_method: AuthMethod) -> bool:
        """Check if provider can handle authentication method"""
        pass
    
    @abstractmethod
    async def refresh_credentials(self, credentials: AuthCredentials) -> AuthCredentials:
        """Refresh authentication credentials"""
        pass


class APIKeyAuthProvider(BaseAuthProvider):
    """API Key authentication provider"""
    
    def __init__(self, api_keys: Dict[str, Dict[str, Any]]):
        self.api_keys = api_keys
    
    def can_handle(self, auth_method: AuthMethod) -> bool:
        return auth_method == AuthMethod.API_KEY
    
    async def authenticate(self, credentials: AuthCredentials, context: AuthContext) -> AuthUser:
        """Authenticate with API key"""
        api_key = credentials.credentials.get('api_key')
        
        if not api_key:
            raise AuthenticationException("API key not provided")
        
        key_info = self.api_keys.get(api_key)
        if not key_info:
            raise AuthenticationException("Invalid API key")
        
        # Check if key is expired
        if key_info.get('expires_at'):
            expires_at = datetime.fromisoformat(key_info['expires_at'])
            if datetime.utcnow() > expires_at:
                raise AuthenticationException("API key expired")
        
        # Check IP restrictions
        if key_info.get('ip_whitelist') and context.ip_address:
            if context.ip_address not in key_info['ip_whitelist']:
                raise AuthenticationException("IP address not allowed")
        
        # Create user
        user = AuthUser(
            user_id=key_info['user_id'],
            username=key_info.get('username', 'api_user'),
            email=key_info.get('email'),
            roles=key_info.get('roles', []),
            permissions=set(PermissionType(p) for p in key_info.get('permissions', [])),
            tenant_id=key_info.get('tenant_id'),
            groups=key_info.get('groups', []),
            attributes=key_info.get('attributes', {})
        )
        
        return user
    
    async def refresh_credentials(self, credentials: AuthCredentials) -> AuthCredentials:
        """Refresh API key credentials (no-op for API keys)"""
        return credentials


class JWTAuthProvider(BaseAuthProvider):
    """JWT authentication provider"""
    
    def __init__(self, secret_key: str, algorithm: str = 'HS256'):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def can_handle(self, auth_method: AuthMethod) -> bool:
        return auth_method == AuthMethod.JWT
    
    async def authenticate(self, credentials: AuthCredentials, context: AuthContext) -> AuthUser:
        """Authenticate with JWT token"""
        token = credentials.credentials.get('token')
        
        if not token:
            raise AuthenticationException("JWT token not provided")
        
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Validate required claims
            if 'user_id' not in payload:
                raise AuthenticationException("Invalid JWT token: missing user_id")
            
            if 'exp' in payload and datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
                raise AuthenticationException("JWT token expired")
            
            # Create user
            user = AuthUser(
                user_id=payload['user_id'],
                username=payload.get('username', 'jwt_user'),
                email=payload.get('email'),
                roles=payload.get('roles', []),
                permissions=set(PermissionType(p) for p in payload.get('permissions', [])),
                tenant_id=payload.get('tenant_id'),
                groups=payload.get('groups', []),
                attributes=payload.get('attributes', {}),
                last_login=datetime.fromtimestamp(payload.get('iat', 0)) if 'iat' in payload else None
            )
            
            return user
            
        except jwt.InvalidTokenError as e:
            raise AuthenticationException(f"Invalid JWT token: {str(e)}")
    
    async def refresh_credentials(self, credentials: AuthCredentials) -> AuthCredentials:
        """Refresh JWT credentials"""
        # In a real implementation, this would use refresh tokens
        return credentials


class OAuth2AuthProvider(BaseAuthProvider):
    """OAuth2 authentication provider"""
    
    def __init__(self, client_id: str, client_secret: str, token_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
    
    def can_handle(self, auth_method: AuthMethod) -> bool:
        return auth_method == AuthMethod.OAUTH2
    
    async def authenticate(self, credentials: AuthCredentials, context: AuthContext) -> AuthUser:
        """Authenticate with OAuth2"""
        access_token = credentials.credentials.get('access_token')
        
        if not access_token:
            raise AuthenticationException("OAuth2 access token not provided")
        
        # In a real implementation, this would validate the token with the OAuth2 provider
        # For now, we'll create a mock user
        
        user = AuthUser(
            user_id='oauth_user',
            username='oauth_user',
            email='oauth@example.com',
            roles=['user'],
            permissions={PermissionType.READ},
            attributes={'oauth_provider': 'default'}
        )
        
        return user
    
    async def refresh_credentials(self, credentials: AuthCredentials) -> AuthCredentials:
        """Refresh OAuth2 credentials"""
        refresh_token = credentials.credentials.get('refresh_token')
        
        if not refresh_token:
            raise AuthenticationException("OAuth2 refresh token not provided")
        
        # In a real implementation, this would exchange the refresh token for a new access token
        return credentials


class AuthBridge:
    """
    Authentication and authorization bridge for cross-module permissions
    """
    
    def __init__(self):
        self.auth_providers: Dict[AuthMethod, BaseAuthProvider] = {}
        self.auth_policies: Dict[str, AuthPolicy] = {}
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        self.permission_cache: Dict[str, Set[PermissionType]] = {}
        self.auth_stats = {
            'total_auth_requests': 0,
            'successful_auths': 0,
            'failed_auths': 0,
            'auths_by_method': {},
            'auths_by_system': {}
        }
        
        # Initialize default providers
        self._initialize_default_providers()
    
    def _initialize_default_providers(self):
        """Initialize default authentication providers"""
        # These would be configured with actual credentials in a real implementation
        self.auth_providers[AuthMethod.API_KEY] = APIKeyAuthProvider({})
        self.auth_providers[AuthMethod.JWT] = JWTAuthProvider('default-secret')
        self.auth_providers[AuthMethod.OAUTH2] = OAuth2AuthProvider('client_id', 'client_secret', 'token_url')
    
    def register_provider(self, auth_method: AuthMethod, provider: BaseAuthProvider):
        """Register an authentication provider"""
        self.auth_providers[auth_method] = provider
    
    def register_policy(self, policy: AuthPolicy):
        """Register an authentication policy"""
        self.auth_policies[policy.policy_id] = policy
    
    async def authenticate(self, credentials: AuthCredentials, context: AuthContext) -> AuthResult:
        """
        Authenticate user with credentials
        
        Args:
            credentials: Authentication credentials
            context: Authentication context
            
        Returns:
            Authentication result
        """
        start_time = datetime.utcnow()
        
        try:
            # Update statistics
            self.auth_stats['total_auth_requests'] += 1
            
            # Get authentication provider
            provider = self.auth_providers.get(credentials.auth_method)
            if not provider:
                raise AuthenticationException(f"No provider found for auth method: {credentials.auth_method}")
            
            # Check if credentials are expired
            if credentials.is_expired():
                raise AuthenticationException("Credentials have expired")
            
            # Authenticate user
            user = await provider.authenticate(credentials, context)
            
            # Create session
            session_id = self._create_session(user, context)
            
            # Update statistics
            self.auth_stats['successful_auths'] += 1
            method_name = credentials.auth_method.value
            self.auth_stats['auths_by_method'][method_name] = (
                self.auth_stats['auths_by_method'].get(method_name, 0) + 1
            )
            self.auth_stats['auths_by_system'][context.source_system] = (
                self.auth_stats['auths_by_system'].get(context.source_system, 0) + 1
            )
            
            return AuthResult(
                success=True,
                user=user,
                credentials=credentials,
                auth_method_used=credentials.auth_method,
                processing_time=(datetime.utcnow() - start_time).total_seconds(),
                metadata={'session_id': session_id}
            )
            
        except Exception as e:
            # Update statistics
            self.auth_stats['failed_auths'] += 1
            
            return AuthResult(
                success=False,
                error=str(e),
                error_code=self._get_error_code(e),
                processing_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def authorize(self, user: AuthUser, context: AuthContext, 
                       required_permissions: Set[PermissionType]) -> AuthResult:
        """
        Authorize user for operation
        
        Args:
            user: Authenticated user
            context: Authentication context
            required_permissions: Required permissions
            
        Returns:
            Authorization result
        """
        start_time = datetime.utcnow()
        
        try:
            # Check user permissions
            granted_permissions = set()
            
            for permission in required_permissions:
                if user.has_permission(permission):
                    granted_permissions.add(permission)
            
            # Check if all required permissions are granted
            if len(granted_permissions) != len(required_permissions):
                missing_permissions = required_permissions - granted_permissions
                raise AuthorizationException(f"Missing required permissions: {missing_permissions}")
            
            # Check policies
            await self._check_policies(user, context)
            
            return AuthResult(
                success=True,
                user=user,
                permissions_granted=granted_permissions,
                processing_time=(datetime.utcnow() - start_time).total_seconds()
            )
            
        except Exception as e:
            return AuthResult(
                success=False,
                error=str(e),
                error_code=self._get_error_code(e),
                processing_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def authenticate_and_authorize(self, credentials: AuthCredentials, 
                                       context: AuthContext,
                                       required_permissions: Set[PermissionType]) -> AuthResult:
        """
        Combined authentication and authorization
        
        Args:
            credentials: Authentication credentials
            context: Authentication context
            required_permissions: Required permissions
            
        Returns:
            Authentication/authorization result
        """
        # Authenticate first
        auth_result = await self.authenticate(credentials, context)
        
        if not auth_result.success:
            return auth_result
        
        # Then authorize
        authz_result = await self.authorize(auth_result.user, context, required_permissions)
        
        # Combine results
        return AuthResult(
            success=authz_result.success,
            user=auth_result.user,
            credentials=auth_result.credentials,
            error=authz_result.error,
            error_code=authz_result.error_code,
            permissions_granted=authz_result.permissions_granted,
            auth_method_used=auth_result.auth_method_used,
            processing_time=auth_result.processing_time + authz_result.processing_time,
            metadata={**auth_result.metadata, **authz_result.metadata}
        )
    
    async def refresh_credentials(self, credentials: AuthCredentials) -> AuthCredentials:
        """Refresh authentication credentials"""
        provider = self.auth_providers.get(credentials.auth_method)
        if not provider:
            raise AuthenticationException(f"No provider found for auth method: {credentials.auth_method}")
        
        return await provider.refresh_credentials(credentials)
    
    def validate_session(self, session_id: str) -> Optional[AuthUser]:
        """Validate user session"""
        session = self.user_sessions.get(session_id)
        if not session:
            return None
        
        # Check if session is expired
        if session.get('expires_at') and datetime.utcnow() > session['expires_at']:
            del self.user_sessions[session_id]
            return None
        
        # Return user
        return session['user']
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke user session"""
        if session_id in self.user_sessions:
            del self.user_sessions[session_id]
            return True
        return False
    
    def _create_session(self, user: AuthUser, context: AuthContext) -> str:
        """Create user session"""
        import uuid
        
        session_id = str(uuid.uuid4())
        
        # Session expires after 24 hours
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        self.user_sessions[session_id] = {
            'user': user,
            'context': context,
            'created_at': datetime.utcnow(),
            'expires_at': expires_at,
            'last_accessed': datetime.utcnow()
        }
        
        return session_id
    
    async def _check_policies(self, user: AuthUser, context: AuthContext):
        """Check authentication policies"""
        for policy in self.auth_policies.values():
            if not policy.enabled:
                continue
            
            # Check if policy applies to this context
            if not self._policy_applies(policy, context):
                continue
            
            # Check required permissions
            if policy.required_permissions:
                for permission in policy.required_permissions:
                    if not user.has_permission(permission):
                        raise AuthorizationException(f"Policy {policy.name}: missing permission {permission}")
            
            # Check roles
            if policy.allowed_roles:
                if not any(user.has_role(role) for role in policy.allowed_roles):
                    raise AuthorizationException(f"Policy {policy.name}: user not in allowed roles")
            
            # Check groups
            if policy.allowed_groups:
                if not any(user.is_in_group(group) for group in policy.allowed_groups):
                    raise AuthorizationException(f"Policy {policy.name}: user not in allowed groups")
            
            # Check IP restrictions
            if policy.ip_whitelist and context.ip_address:
                if context.ip_address not in policy.ip_whitelist:
                    raise AuthorizationException(f"Policy {policy.name}: IP address not in whitelist")
            
            if policy.ip_blacklist and context.ip_address:
                if context.ip_address in policy.ip_blacklist:
                    raise AuthorizationException(f"Policy {policy.name}: IP address in blacklist")
            
            # Check time restrictions
            if policy.time_restrictions:
                if not self._check_time_restrictions(policy.time_restrictions):
                    raise AuthorizationException(f"Policy {policy.name}: time restriction violated")
    
    def _policy_applies(self, policy: AuthPolicy, context: AuthContext) -> bool:
        """Check if policy applies to context"""
        for condition in policy.conditions:
            field = condition.get('field')
            operator = condition.get('operator', 'equals')
            value = condition.get('value')
            
            context_value = getattr(context, field, None)
            
            if operator == 'equals' and context_value != value:
                return False
            elif operator == 'not_equals' and context_value == value:
                return False
            elif operator == 'in' and context_value not in value:
                return False
            elif operator == 'not_in' and context_value in value:
                return False
        
        return True
    
    def _check_time_restrictions(self, time_restrictions: Dict[str, Any]) -> bool:
        """Check time restrictions"""
        current_time = datetime.utcnow()
        current_hour = current_time.hour
        current_day = current_time.weekday()
        
        # Check allowed hours
        if 'allowed_hours' in time_restrictions:
            allowed_hours = time_restrictions['allowed_hours']
            if current_hour not in allowed_hours:
                return False
        
        # Check allowed days
        if 'allowed_days' in time_restrictions:
            allowed_days = time_restrictions['allowed_days']
            if current_day not in allowed_days:
                return False
        
        return True
    
    def _get_error_code(self, error: Exception) -> str:
        """Get error code from exception"""
        if isinstance(error, AuthenticationException):
            return 'AUTH_ERROR'
        elif isinstance(error, AuthorizationException):
            return 'AUTHZ_ERROR'
        else:
            return 'UNKNOWN_ERROR'
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get authentication statistics"""
        stats = self.auth_stats.copy()
        
        # Calculate success rate
        if stats['total_auth_requests'] > 0:
            stats['success_rate'] = (stats['successful_auths'] / stats['total_auth_requests']) * 100
        else:
            stats['success_rate'] = 0
        
        # Add session statistics
        stats['active_sessions'] = len(self.user_sessions)
        stats['expired_sessions'] = len([
            s for s in self.user_sessions.values()
            if s.get('expires_at') and datetime.utcnow() > s['expires_at']
        ])
        
        return stats


# Global auth bridge instance
_auth_bridge = None


def get_auth_bridge() -> AuthBridge:
    """Get the global auth bridge instance"""
    global _auth_bridge
    if _auth_bridge is None:
        _auth_bridge = AuthBridge()
    return _auth_bridge


def initialize_auth_bridge() -> AuthBridge:
    """Initialize the global auth bridge"""
    global _auth_bridge
    _auth_bridge = AuthBridge()
    return _auth_bridge


# Export main classes and functions
__all__ = [
    'AuthBridge',
    'AuthCredentials',
    'AuthUser',
    'AuthContext',
    'AuthPolicy',
    'AuthResult',
    'BaseAuthProvider',
    'APIKeyAuthProvider',
    'JWTAuthProvider',
    'OAuth2AuthProvider',
    'AuthMethod',
    'PermissionType',
    'AuthScope',
    'get_auth_bridge',
    'initialize_auth_bridge',
]
