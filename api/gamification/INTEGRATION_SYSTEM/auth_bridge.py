"""
Authentication Bridge — Cross-module permission and authentication bridge.

This module provides authentication and authorization bridge capabilities
for managing permissions and access control across different modules.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Set, Type
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import (
    IntegrationError, AuthenticationError, AuthorizationError,
    ValidationError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Authentication Types
# ---------------------------------------------------------------------------

class AuthType(Enum):
    """Authentication type enumeration."""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    JWT = "jwt"
    CERTIFICATE = "certificate"
    SESSION = "session"
    CUSTOM = "custom"


class PermissionType(Enum):
    """Permission type enumeration."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXECUTE = "execute"
    CUSTOM = "custom"


class RoleType(Enum):
    """Role type enumeration."""
    SYSTEM = "system"
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"
    GUEST = "guest"
    SERVICE = "service"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Authentication Data Classes
# ---------------------------------------------------------------------------

@dataclass
class AuthCredential:
    """Authentication credential."""
    
    id: str
    auth_type: AuthType
    credential_data: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    issuer: Optional[str] = None
    audience: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if credential is expired."""
        return self.expires_at and datetime.now(timezone.utc) > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if credential is valid."""
        return not self.is_expired() and bool(self.credential_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "auth_type": self.auth_type.value,
            "credential_data": self.credential_data,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "issued_at": self.issued_at.isoformat(),
            "issuer": self.issuer,
            "audience": self.audience,
            "metadata": self.metadata,
            "is_expired": self.is_expired(),
            "is_valid": self.is_valid()
        }


@dataclass
class Permission:
    """Permission definition."""
    
    id: str
    name: str
    resource: str
    action: PermissionType
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, resource: str, action: PermissionType, context: Dict[str, Any]) -> bool:
        """Check if permission matches request."""
        if not self.enabled:
            return False
        
        if self.resource != resource and self.resource != "*":
            return False
        
        if self.action != action and self.action != PermissionType.CUSTOM:
            return False
        
        # Check conditions
        for condition_key, condition_value in self.conditions.items():
            context_value = context.get(condition_key)
            if context_value != condition_value:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "resource": self.resource,
            "action": self.action.value,
            "conditions": self.conditions,
            "enabled": self.enabled,
            "metadata": self.metadata
        }


@dataclass
class Role:
    """Role definition."""
    
    id: str
    name: str
    role_type: RoleType
    permissions: List[str] = field(default_factory=list)  # Permission IDs
    parent_roles: List[str] = field(default_factory=list)  # Role IDs
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "role_type": self.role_type.value,
            "permissions": self.permissions,
            "parent_roles": self.parent_roles,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class User:
    """User definition."""
    
    id: str
    username: str
    email: Optional[str] = None
    roles: List[str] = field(default_factory=list)  # Role IDs
    credentials: List[AuthCredential] = field(default_factory=list)
    enabled: bool = True
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_role(self, role_id: str) -> bool:
        """Check if user has a role."""
        return role_id in self.roles
    
    def add_role(self, role_id: str) -> None:
        """Add a role to the user."""
        if role_id not in self.roles:
            self.roles.append(role_id)
            self.updated_at = datetime.now(timezone.utc)
    
    def remove_role(self, role_id: str) -> None:
        """Remove a role from the user."""
        if role_id in self.roles:
            self.roles.remove(role_id)
            self.updated_at = datetime.now(timezone.utc)
    
    def get_active_credentials(self) -> List[AuthCredential]:
        """Get active (non-expired) credentials."""
        return [cred for cred in self.credentials if cred.is_valid()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "roles": self.roles,
            "credentials": [cred.to_dict() for cred in self.credentials],
            "enabled": self.enabled,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class AuthContext:
    """Authentication context."""
    
    user: Optional[User] = None
    credential: Optional[AuthCredential] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_authenticated(self) -> bool:
        """Check if context is authenticated."""
        return self.user is not None and self.credential is not None and self.credential.is_valid()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user.id if self.user else None,
            "username": self.user.username if self.user else None,
            "credential_id": self.credential.id if self.credential else None,
            "auth_type": self.credential.auth_type.value if self.credential else None,
            "request_id": self.request_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat(),
            "is_authenticated": self.is_authenticated(),
            "metadata": self.metadata
        }


# ---------------------------------------------------------------------------
# Abstract Auth Provider
# ---------------------------------------------------------------------------

class BaseAuthProvider(ABC):
    """Abstract base class for authentication providers."""
    
    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[AuthCredential]:
        """Authenticate credentials."""
        pass
    
    @abstractmethod
    def validate_credential(self, credential: AuthCredential) -> bool:
        """Validate a credential."""
        pass
    
    @abstractmethod
    def refresh_credential(self, credential: AuthCredential) -> Optional[AuthCredential]:
        """Refresh a credential."""
        pass
    
    @abstractmethod
    def revoke_credential(self, credential: AuthCredential) -> bool:
        """Revoke a credential."""
        pass


# ---------------------------------------------------------------------------
# Authentication Bridge Implementation
# ---------------------------------------------------------------------------

class AuthenticationBridge:
    """Bridge for authentication and authorization."""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.roles: Dict[str, Role] = {}
        self.permissions: Dict[str, Permission] = {}
        self.providers: Dict[AuthType, BaseAuthProvider] = {}
        self.active_sessions: Dict[str, AuthContext] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def register_provider(self, auth_type: AuthType, provider: BaseAuthProvider) -> None:
        """Register an authentication provider."""
        with self._lock:
            self.providers[auth_type] = provider
            self.logger.info(f"Registered auth provider for type: {auth_type.value}")
    
    def unregister_provider(self, auth_type: AuthType) -> bool:
        """Unregister an authentication provider."""
        with self._lock:
            if auth_type in self.providers:
                del self.providers[auth_type]
                self.logger.info(f"Unregistered auth provider for type: {auth_type.value}")
                return True
            return False
    
    def create_user(
        self,
        user_id: str,
        username: str,
        email: Optional[str] = None,
        **kwargs: Any
    ) -> User:
        """Create a new user."""
        with self._lock:
            if user_id in self.users:
                raise IntegrationError(f"User '{user_id}' already exists")
            
            user = User(
                id=user_id,
                username=username,
                email=email,
                **kwargs
            )
            
            self.users[user_id] = user
            self.logger.info(f"Created user: {user_id}")
            
            return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        with self._lock:
            return self.users.get(user_id)
    
    def update_user(self, user_id: str, **updates: Any) -> bool:
        """Update a user."""
        with self._lock:
            user = self.users.get(user_id)
            if not user:
                return False
            
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            user.updated_at = datetime.now(timezone.utc)
            self.logger.info(f"Updated user: {user_id}")
            
            return True
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        with self._lock:
            if user_id in self.users:
                del self.users[user_id]
                self.logger.info(f"Deleted user: {user_id}")
                return True
            return False
    
    def create_role(
        self,
        role_id: str,
        name: str,
        role_type: RoleType,
        permissions: List[str] = None,
        **kwargs: Any
    ) -> Role:
        """Create a new role."""
        with self._lock:
            if role_id in self.roles:
                raise IntegrationError(f"Role '{role_id}' already exists")
            
            role = Role(
                id=role_id,
                name=name,
                role_type=role_type,
                permissions=permissions or [],
                **kwargs
            )
            
            self.roles[role_id] = role
            self.logger.info(f"Created role: {role_id}")
            
            return role
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Get a role by ID."""
        with self._lock:
            return self.roles.get(role_id)
    
    def assign_role_to_user(self, user_id: str, role_id: str) -> bool:
        """Assign a role to a user."""
        with self._lock:
            user = self.users.get(user_id)
            role = self.roles.get(role_id)
            
            if not user or not role:
                return False
            
            user.add_role(role_id)
            self.logger.info(f"Assigned role {role_id} to user {user_id}")
            
            return True
    
    def revoke_role_from_user(self, user_id: str, role_id: str) -> bool:
        """Revoke a role from a user."""
        with self._lock:
            user = self.users.get(user_id)
            if not user:
                return False
            
            user.remove_role(role_id)
            self.logger.info(f"Revoked role {role_id} from user {user_id}")
            
            return True
    
    def create_permission(
        self,
        permission_id: str,
        name: str,
        resource: str,
        action: PermissionType,
        **kwargs: Any
    ) -> Permission:
        """Create a new permission."""
        with self._lock:
            if permission_id in self.permissions:
                raise IntegrationError(f"Permission '{permission_id}' already exists")
            
            permission = Permission(
                id=permission_id,
                name=name,
                resource=resource,
                action=action,
                **kwargs
            )
            
            self.permissions[permission_id] = permission
            self.logger.info(f"Created permission: {permission_id}")
            
            return permission
    
    def get_permission(self, permission_id: str) -> Optional[Permission]:
        """Get a permission by ID."""
        with self._lock:
            return self.permissions.get(permission_id)
    
    def authenticate(self, auth_type: AuthType, credentials: Dict[str, Any]) -> Optional[AuthContext]:
        """Authenticate credentials and create context."""
        provider = self.providers.get(auth_type)
        if not provider:
            raise AuthenticationError(f"No provider found for auth type: {auth_type.value}")
        
        try:
            # Authenticate with provider
            credential = provider.authenticate(credentials)
            if not credential:
                return None
            
            # Find user by credential
            user = self._find_user_by_credential(credential)
            if not user:
                return None
            
            # Create auth context
            context = AuthContext(
                user=user,
                credential=credential,
                request_id=credentials.get("request_id"),
                ip_address=credentials.get("ip_address"),
                user_agent=credentials.get("user_agent"),
                metadata=credentials.get("metadata", {})
            )
            
            # Update user last login
            user.last_login = datetime.now(timezone.utc)
            
            # Store active session
            session_id = f"{user.id}_{credential.id}"
            self.active_sessions[session_id] = context
            
            self.logger.info(f"Authenticated user: {user.id} with {auth_type.value}")
            return context
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")
    
    def authorize(
        self,
        context: AuthContext,
        resource: str,
        action: PermissionType,
        context_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Authorize an action."""
        if not context.is_authenticated():
            return False
        
        user = context.user
        auth_context_data = context_data or {}
        
        # Get all permissions for user (including inherited from roles)
        user_permissions = self._get_user_permissions(user)
        
        # Check if any permission matches the request
        for permission in user_permissions:
            if permission.matches(resource, action, auth_context_data):
                return True
        
        return False
    
    def validate_session(self, session_id: str) -> Optional[AuthContext]:
        """Validate a session."""
        with self._lock:
            context = self.active_sessions.get(session_id)
            if not context:
                return None
            
            # Check if credential is still valid
            if not context.credential.is_valid():
                # Remove invalid session
                del self.active_sessions[session_id]
                return None
            
            return context
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        with self._lock:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
                self.logger.info(f"Invalidated session: {session_id}")
                return True
            return False
    
    def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        with self._lock:
            sessions_to_remove = []
            
            for session_id, context in self.active_sessions.items():
                if context.user and context.user.id == user_id:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                del self.active_sessions[session_id]
            
            self.logger.info(f"Invalidated {len(sessions_to_remove)} sessions for user: {user_id}")
            return len(sessions_to_remove)
    
    def _find_user_by_credential(self, credential: AuthCredential) -> Optional[User]:
        """Find user by credential."""
        for user in self.users.values():
            for user_credential in user.credentials:
                if user_credential.id == credential.id:
                    return user
        
        return None
    
    def _get_user_permissions(self, user: User) -> List[Permission]:
        """Get all permissions for a user (including inherited from roles)."""
        permissions = set()
        processed_roles = set()
        
        def collect_permissions(role_id: str):
            if role_id in processed_roles:
                return
            
            processed_roles.add(role_id)
            role = self.roles.get(role_id)
            if not role:
                return
            
            # Add role permissions
            for permission_id in role.permissions:
                permissions.add(permission_id)
            
            # Recursively add parent role permissions
            for parent_role_id in role.parent_roles:
                collect_permissions(parent_role_id)
        
        # Collect permissions from all user roles
        for role_id in user.roles:
            collect_permissions(role_id)
        
        # Return permission objects
        return [self.permissions[pid] for pid in permissions if pid in self.permissions]
    
    def get_user_permissions(self, user_id: str) -> List[Permission]:
        """Get all permissions for a user."""
        user = self.get_user(user_id)
        if not user:
            return []
        
        return self._get_user_permissions(user)
    
    def check_permission(
        self,
        user_id: str,
        resource: str,
        action: PermissionType,
        context_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if user has permission."""
        user = self.get_user(user_id)
        if not user:
            return False
        
        auth_context = AuthContext(user=user)
        return self.authorize(auth_context, resource, action, context_data)
    
    def get_status(self) -> Dict[str, Any]:
        """Get authentication bridge status."""
        with self._lock:
            return {
                "users_count": len(self.users),
                "roles_count": len(self.roles),
                "permissions_count": len(self.permissions),
                "providers_count": len(self.providers),
                "active_sessions_count": len(self.active_sessions),
                "enabled_users": len([u for u in self.users.values() if u.enabled]),
                "enabled_roles": len([r for r in self.roles.values() if r.enabled]),
                "enabled_permissions": len([p for p in self.permissions.values() if p.enabled]),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


# ---------------------------------------------------------------------------
# Built-in Auth Providers
# ---------------------------------------------------------------------------

class APIKeyAuthProvider(BaseAuthProvider):
    """API Key authentication provider."""
    
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[AuthCredential]:
        """Authenticate with API key."""
        api_key = credentials.get("api_key")
        if not api_key:
            return None
        
        # This would validate the API key against a database or service
        # For now, we'll create a mock credential
        return AuthCredential(
            id=f"apikey_{hash(api_key)}",
            auth_type=AuthType.API_KEY,
            credential_data={"api_key": api_key},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
    
    def validate_credential(self, credential: AuthCredential) -> bool:
        """Validate API key credential."""
        return credential.is_valid()
    
    def refresh_credential(self, credential: AuthCredential) -> Optional[AuthCredential]:
        """Refresh API key credential."""
        # API keys typically don't need refreshing
        return credential
    
    def revoke_credential(self, credential: AuthCredential) -> bool:
        """Revoke API key credential."""
        # This would revoke the API key
        return True


class JWTAuthProvider(BaseAuthProvider):
    """JWT authentication provider."""
    
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[AuthCredential]:
        """Authenticate with JWT token."""
        token = credentials.get("token")
        if not token:
            return None
        
        try:
            # This would validate and decode the JWT token
            # For now, we'll create a mock credential
            import jwt
            import hashlib
            
            # Mock decode (would use actual JWT library)
            payload = {
                "sub": "user123",
                "exp": datetime.now() + timedelta(hours=1),
                "iat": datetime.now()
            }
            
            return AuthCredential(
                id=f"jwt_{hashlib.sha256(token.encode()).hexdigest()[:16]}",
                auth_type=AuthType.JWT,
                credential_data={"token": token, "payload": payload},
                expires_at=payload.get("exp"),
                issued_at=payload.get("iat")
            )
            
        except Exception as e:
            logger.error(f"JWT authentication failed: {e}")
            return None
    
    def validate_credential(self, credential: AuthCredential) -> bool:
        """Validate JWT credential."""
        return credential.is_valid()
    
    def refresh_credential(self, credential: AuthCredential) -> Optional[AuthCredential]:
        """Refresh JWT credential."""
        # This would generate a new JWT token
        return credential
    
    def revoke_credential(self, credential: AuthCredential) -> bool:
        """Revoke JWT credential."""
        # Add token to blacklist
        return True


# Global authentication bridge instance
auth_bridge = AuthenticationBridge()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_user(
    user_id: str,
    username: str,
    email: Optional[str] = None,
    **kwargs: Any
) -> User:
    """Create a user."""
    return auth_bridge.create_user(user_id, username, email, **kwargs)


def authenticate_user(auth_type: AuthType, credentials: Dict[str, Any]) -> Optional[AuthContext]:
    """Authenticate a user."""
    return auth_bridge.authenticate(auth_type, credentials)


def check_permission(
    user_id: str,
    resource: str,
    action: PermissionType,
    context_data: Optional[Dict[str, Any]] = None
) -> bool:
    """Check user permission."""
    return auth_bridge.check_permission(user_id, resource, action, context_data)


# Initialize logging and register built-in providers
logger.info("Authentication bridge module initialized")
auth_bridge.register_provider(AuthType.API_KEY, APIKeyAuthProvider())
auth_bridge.register_provider(AuthType.JWT, JWTAuthProvider())
