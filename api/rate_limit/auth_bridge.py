# api/rate_limit/auth_bridge.py
"""
Authentication bridge for rate limit module.

Provides cross-module permission management and authentication integration.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission
import jwt
import hashlib

from api.rate_limit.integ_exceptions import IntegrationAuthBridgeError

logger = logging.getLogger(__name__)
User = get_user_model()


class AuthBridge:
    """
    Bridge for authentication and authorization across modules.
    """
    
    def __init__(self):
        self.auth_systems: Dict[str, Dict[str, Any]] = {}
        self.permission_cache_timeout = 300  # 5 minutes
        self.token_cache_timeout = 3600  # 1 hour
        self._initialize_auth_systems()
    
    def _initialize_auth_systems(self):
        """Initialize authentication systems."""
        # Django auth system
        self.register_auth_system('django', {
            'type': 'django',
            'enabled': True,
            'user_model': User,
            'supports_permissions': True,
            'supports_groups': True
        })
        
        # JWT auth system
        self.register_auth_system('jwt', {
            'type': 'jwt',
            'enabled': True,
            'algorithm': 'HS256',
            'token_expiry': 3600,
            'refresh_expiry': 86400
        })
        
        # API key auth system
        self.register_auth_system('api_key', {
            'type': 'api_key',
            'enabled': True,
            'header_name': 'X-API-Key',
            'query_param': 'api_key'
        })
        
        # OAuth2 auth system
        self.register_auth_system('oauth2', {
            'type': 'oauth2',
            'enabled': False,  # Requires configuration
            'provider': None
        })
    
    def register_auth_system(self, name: str, config: Dict[str, Any]):
        """
        Register an authentication system.
        
        Args:
            name: Auth system name
            config: Auth system configuration
        """
        self.auth_systems[name] = config
        logger.info(f"Registered auth system: {name}")
    
    def unregister_auth_system(self, name: str):
        """
        Unregister an authentication system.
        
        Args:
            name: Auth system name
        """
        if name in self.auth_systems:
            del self.auth_systems[name]
            logger.info(f"Unregistered auth system: {name}")
    
    def authenticate_user(self, auth_type: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate user using specified auth type.
        
        Args:
            auth_type: Authentication type
            credentials: Authentication credentials
            
        Returns:
            Authentication result
        """
        try:
            auth_system = self.auth_systems.get(auth_type)
            if not auth_system or not auth_system.get('enabled', False):
                raise IntegrationAuthBridgeError(f"Auth system not enabled: {auth_type}")
            
            if auth_type == 'django':
                return self._authenticate_django(credentials)
            elif auth_type == 'jwt':
                return self._authenticate_jwt(credentials)
            elif auth_type == 'api_key':
                return self._authenticate_api_key(credentials)
            elif auth_type == 'oauth2':
                return self._authenticate_oauth2(credentials)
            else:
                raise IntegrationAuthBridgeError(f"Unsupported auth type: {auth_type}")
                
        except Exception as e:
            logger.error(f"Authentication failed for {auth_type}: {str(e)}")
            raise IntegrationAuthBridgeError(f"Authentication failed: {str(e)}")
    
    def _authenticate_django(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate using Django auth system."""
        try:
            username = credentials.get('username')
            password = credentials.get('password')
            
            if not username or not password:
                raise IntegrationAuthBridgeError("Username and password required")
            
            user = User.objects.filter(username=username).first()
            
            if user and user.check_password(password):
                return {
                    'success': True,
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'auth_type': 'django'
                }
            else:
                return {
                    'success': False,
                    'error': 'Invalid credentials'
                }
                
        except Exception as e:
            raise IntegrationAuthBridgeError(f"Django authentication failed: {str(e)}")
    
    def _authenticate_jwt(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate using JWT token."""
        try:
            token = credentials.get('token')
            if not token:
                raise IntegrationAuthBridgeError("JWT token required")
            
            # Get JWT secret from settings
            secret_key = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
            algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
            
            # Decode token
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            
            # Check token expiry
            exp = payload.get('exp')
            if exp and timezone.now().timestamp() > exp:
                raise IntegrationAuthBridgeError("Token has expired")
            
            # Get user
            user_id = payload.get('user_id')
            if not user_id:
                raise IntegrationAuthBridgeError("Invalid token payload")
            
            user = User.objects.filter(id=user_id, is_active=True).first()
            if not user:
                raise IntegrationAuthBridgeError("User not found or inactive")
            
            return {
                'success': True,
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'auth_type': 'jwt',
                'token_payload': payload
            }
            
        except jwt.ExpiredSignatureError:
            raise IntegrationAuthBridgeError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise IntegrationAuthBridgeError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise IntegrationAuthBridgeError(f"JWT authentication failed: {str(e)}")
    
    def _authenticate_api_key(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate using API key."""
        try:
            api_key = credentials.get('api_key')
            if not api_key:
                raise IntegrationAuthBridgeError("API key required")
            
            # Hash the API key for comparison
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Check cache first
            cache_key = f"api_key_auth:{api_key_hash}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Look up API key in database (mock implementation)
            # In a real implementation, you'd have an APIKey model
            user = User.objects.filter(is_active=True).first()
            
            if user:  # Mock successful auth
                result = {
                    'success': True,
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'auth_type': 'api_key'
                }
                
                # Cache result
                cache.set(cache_key, result, timeout=self.token_cache_timeout)
                
                return result
            else:
                return {
                    'success': False,
                    'error': 'Invalid API key'
                }
                
        except Exception as e:
            raise IntegrationAuthBridgeError(f"API key authentication failed: {str(e)}")
    
    def _authenticate_oauth2(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate using OAuth2."""
        # Mock OAuth2 implementation
        return {
            'success': False,
            'error': 'OAuth2 not implemented'
        }
    
    def check_permission(self, user_id: int, permission: str, context: Dict[str, Any] = None) -> bool:
        """
        Check if user has permission.
        
        Args:
            user_id: User ID
            permission: Permission to check
            context: Additional context
            
        Returns:
            True if user has permission
        """
        try:
            # Check cache first
            cache_key = f"user_permission:{user_id}:{permission}"
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            user = User.objects.filter(id=user_id, is_active=True).first()
            if not user:
                return False
            
            # Check Django permissions
            if user.has_perm(permission):
                cache.set(cache_key, True, timeout=self.permission_cache_timeout)
                return True
            
            # Check custom rate limit permissions
            if self._check_rate_limit_permission(user, permission, context):
                cache.set(cache_key, True, timeout=self.permission_cache_timeout)
                return True
            
            cache.set(cache_key, False, timeout=self.permission_cache_timeout)
            return False
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            return False
    
    def _check_rate_limit_permission(self, user: User, permission: str, context: Dict[str, Any]) -> bool:
        """Check rate limit specific permissions."""
        try:
            # Rate limit manager permissions
            if permission == 'rate_limit.manage':
                return user.is_staff or user.groups.filter(name='rate_limit_managers').exists()
            
            # Rate limit admin permissions
            elif permission == 'rate_limit.admin':
                return user.is_superuser or user.groups.filter(name='rate_limit_admins').exists()
            
            # View analytics permissions
            elif permission == 'rate_limit.view_analytics':
                return user.is_staff or user.groups.filter(name='analytics_viewers').exists()
            
            # Manage exceptions permissions
            elif permission == 'rate_limit.manage_exceptions':
                return user.is_staff or user.groups.filter(name='exception_managers').exists()
            
            # View logs permissions
            elif permission == 'rate_limit.view_logs':
                return user.is_staff or user.groups.filter(name='log_viewers').exists()
            
            # IP management permissions
            elif permission == 'rate_limit.manage_ip':
                return user.is_staff or user.groups.filter(name='ip_managers').exists()
            
            # Abuse management permissions
            elif permission == 'rate_limit.manage_abuse':
                return user.is_staff or user.groups.filter(name='abuse_managers').exists()
            
            return False
            
        except Exception as e:
            logger.error(f"Rate limit permission check failed: {str(e)}")
            return False
    
    def get_user_permissions(self, user_id: int) -> List[str]:
        """
        Get all permissions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of permissions
        """
        try:
            user = User.objects.filter(id=user_id, is_active=True).first()
            if not user:
                return []
            
            permissions = set()
            
            # Get Django permissions
            user_permissions = user.user_permissions.all()
            for perm in user_permissions:
                permissions.add(f"{perm.content_type.app_label}.{perm.codename}")
            
            # Get group permissions
            group_permissions = Permission.objects.filter(group__user=user)
            for perm in group_permissions:
                permissions.add(f"{perm.content_type.app_label}.{perm.codename}")
            
            # Add rate limit specific permissions
            rate_limit_perms = self._get_rate_limit_permissions(user)
            permissions.update(rate_limit_perms)
            
            return list(permissions)
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {str(e)}")
            return []
    
    def _get_rate_limit_permissions(self, user: User) -> List[str]:
        """Get rate limit specific permissions for user."""
        permissions = []
        
        if user.is_staff:
            permissions.extend([
                'rate_limit.view_analytics',
                'rate_limit.view_logs'
            ])
        
        if user.is_superuser:
            permissions.extend([
                'rate_limit.manage',
                'rate_limit.admin',
                'rate_limit.manage_exceptions',
                'rate_limit.manage_ip',
                'rate_limit.manage_abuse'
            ])
        
        # Check group memberships
        user_groups = user.groups.all()
        
        for group in user_groups:
            if group.name == 'rate_limit_managers':
                permissions.append('rate_limit.manage')
            elif group.name == 'rate_limit_admins':
                permissions.extend(['rate_limit.manage', 'rate_limit.admin'])
            elif group.name == 'analytics_viewers':
                permissions.append('rate_limit.view_analytics')
            elif group.name == 'exception_managers':
                permissions.append('rate_limit.manage_exceptions')
            elif group.name == 'log_viewers':
                permissions.append('rate_limit.view_logs')
            elif group.name == 'ip_managers':
                permissions.append('rate_limit.manage_ip')
            elif group.name == 'abuse_managers':
                permissions.append('rate_limit.manage_abuse')
        
        return permissions
    
    def create_auth_token(self, user_id: int, token_type: str = 'jwt', expiry: int = None) -> Dict[str, Any]:
        """
        Create authentication token for user.
        
        Args:
            user_id: User ID
            token_type: Type of token
            expiry: Token expiry in seconds
            
        Returns:
            Token information
        """
        try:
            user = User.objects.filter(id=user_id, is_active=True).first()
            if not user:
                raise IntegrationAuthBridgeError("User not found or inactive")
            
            if token_type == 'jwt':
                return self._create_jwt_token(user, expiry)
            elif token_type == 'api_key':
                return self._create_api_key(user, expiry)
            else:
                raise IntegrationAuthBridgeError(f"Unsupported token type: {token_type}")
                
        except Exception as e:
            logger.error(f"Token creation failed: {str(e)}")
            raise IntegrationAuthBridgeError(f"Token creation failed: {str(e)}")
    
    def _create_jwt_token(self, user: User, expiry: int = None) -> Dict[str, Any]:
        """Create JWT token."""
        try:
            secret_key = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
            algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
            default_expiry = getattr(settings, 'JWT_DEFAULT_EXPIRY', 3600)
            
            token_expiry = expiry or default_expiry
            
            payload = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'iat': timezone.now().timestamp(),
                'exp': (timezone.now() + timedelta(seconds=token_expiry)).timestamp()
            }
            
            token = jwt.encode(payload, secret_key, algorithm=algorithm)
            
            return {
                'success': True,
                'token': token,
                'token_type': 'jwt',
                'expires_at': (timezone.now() + timedelta(seconds=token_expiry)).isoformat(),
                'user_id': user.id
            }
            
        except Exception as e:
            raise IntegrationAuthBridgeError(f"JWT token creation failed: {str(e)}")
    
    def _create_api_key(self, user: User, expiry: int = None) -> Dict[str, Any]:
        """Create API key."""
        try:
            import secrets
            
            api_key = secrets.token_urlsafe(32)
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Store API key in cache (in production, store in database)
            cache_key = f"api_key:{api_key_hash}"
            cache_data = {
                'user_id': user.id,
                'created_at': timezone.now().isoformat(),
                'expires_at': (timezone.now() + timedelta(seconds=expiry)).isoformat() if expiry else None
            }
            
            cache_timeout = expiry or 86400 * 365  # 1 year default
            cache.set(cache_key, cache_data, timeout=cache_timeout)
            
            return {
                'success': True,
                'api_key': api_key,
                'token_type': 'api_key',
                'expires_at': cache_data['expires_at'],
                'user_id': user.id
            }
            
        except Exception as e:
            raise IntegrationAuthBridgeError(f"API key creation failed: {str(e)}")
    
    def revoke_token(self, token: str, token_type: str = 'jwt') -> Dict[str, Any]:
        """
        Revoke authentication token.
        
        Args:
            token: Token to revoke
            token_type: Type of token
            
        Returns:
            Revocation result
        """
        try:
            if token_type == 'jwt':
                # Add token to blacklist
                cache_key = f"jwt_blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
                cache.set(cache_key, True, timeout=86400)  # 24 hours
                
                return {
                    'success': True,
                    'message': 'JWT token revoked',
                    'token_type': 'jwt'
                }
            
            elif token_type == 'api_key':
                # Remove API key from cache
                api_key_hash = hashlib.sha256(token.encode()).hexdigest()
                cache_key = f"api_key:{api_key_hash}"
                cache.delete(cache_key)
                
                return {
                    'success': True,
                    'message': 'API key revoked',
                    'token_type': 'api_key'
                }
            
            else:
                raise IntegrationAuthBridgeError(f"Unsupported token type: {token_type}")
                
        except Exception as e:
            logger.error(f"Token revocation failed: {str(e)}")
            raise IntegrationAuthBridgeError(f"Token revocation failed: {str(e)}")
    
    def validate_token(self, token: str, token_type: str = 'jwt') -> Dict[str, Any]:
        """
        Validate authentication token.
        
        Args:
            token: Token to validate
            token_type: Type of token
            
        Returns:
            Validation result
        """
        try:
            if token_type == 'jwt':
                # Check blacklist
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                cache_key = f"jwt_blacklist:{token_hash}"
                
                if cache.get(cache_key):
                    return {
                        'valid': False,
                        'error': 'Token is blacklisted'
                    }
                
                # Validate token
                try:
                    secret_key = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
                    algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
                    
                    payload = jwt.decode(token, secret_key, algorithms=[algorithm])
                    
                    return {
                        'valid': True,
                        'payload': payload,
                        'token_type': 'jwt'
                    }
                    
                except jwt.ExpiredSignatureError:
                    return {
                        'valid': False,
                        'error': 'Token has expired'
                    }
                except jwt.InvalidTokenError as e:
                    return {
                        'valid': False,
                        'error': f'Invalid token: {str(e)}'
                    }
            
            elif token_type == 'api_key':
                api_key_hash = hashlib.sha256(token.encode()).hexdigest()
                cache_key = f"api_key:{api_key_hash}"
                cache_data = cache.get(cache_key)
                
                if cache_data:
                    # Check expiry
                    expires_at = cache_data.get('expires_at')
                    if expires_at:
                        expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        if timezone.now() > expiry_time:
                            return {
                                'valid': False,
                                'error': 'API key has expired'
                            }
                    
                    return {
                        'valid': True,
                        'user_id': cache_data['user_id'],
                        'created_at': cache_data['created_at'],
                        'token_type': 'api_key'
                    }
                else:
                    return {
                        'valid': False,
                        'error': 'API key not found'
                    }
            
            else:
                raise IntegrationAuthBridgeError(f"Unsupported token type: {token_type}")
                
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            raise IntegrationAuthBridgeError(f"Token validation failed: {str(e)}")
    
    def get_auth_statistics(self) -> Dict[str, Any]:
        """Get authentication statistics."""
        try:
            stats = {
                'auth_systems': {},
                'active_tokens': 0,
                'blacklisted_tokens': 0
            }
            
            # Auth system statistics
            for name, config in self.auth_systems.items():
                stats['auth_systems'][name] = {
                    'type': config['type'],
                    'enabled': config['enabled']
                }
            
            # Token statistics (simplified)
            jwt_blacklist_keys = cache.keys("jwt_blacklist:*")
            stats['blacklisted_tokens'] = len(jwt_blacklist_keys)
            
            api_key_keys = cache.keys("api_key:*")
            stats['active_tokens'] = len(api_key_keys)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get auth statistics: {str(e)}")
            return {'error': str(e)}


# DRF Authentication classes
class JWTAuthentication(BaseAuthentication):
    """JWT authentication for DRF."""
    
    def authenticate(self, request):
        """Authenticate request using JWT."""
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return None
            
            token = auth_header.split(' ')[1]
            
            # Validate token
            auth_bridge = AuthBridge()
            result = auth_bridge.validate_token(token, 'jwt')
            
            if result['valid']:
                user_id = result['payload']['user_id']
                user = User.objects.filter(id=user_id, is_active=True).first()
                
                if user:
                    return (user, result['payload'])
            
            return None
            
        except Exception as e:
            logger.error(f"JWT authentication failed: {str(e)}")
            return None


class APIKeyAuthentication(BaseAuthentication):
    """API key authentication for DRF."""
    
    def authenticate(self, request):
        """Authenticate request using API key."""
        try:
            # Get API key from header or query parameter
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                api_key = request.query_params.get('api_key')
            
            if not api_key:
                return None
            
            # Validate API key
            auth_bridge = AuthBridge()
            result = auth_bridge.validate_token(api_key, 'api_key')
            
            if result['valid']:
                user_id = result['user_id']
                user = User.objects.filter(id=user_id, is_active=True).first()
                
                if user:
                    return (user, {'auth_type': 'api_key'})
            
            return None
            
        except Exception as e:
            logger.error(f"API key authentication failed: {str(e)}")
            return None


# DRF Permission classes
class RateLimitPermission(BasePermission):
    """Base permission class for rate limiting."""
    
    def has_permission(self, request, view):
        """Check if user has permission."""
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            permission = getattr(view, 'required_permission', None)
            if not permission:
                return True
            
            auth_bridge = AuthBridge()
            return auth_bridge.check_permission(request.user.id, permission)
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            return False


class RateLimitManagePermission(RateLimitPermission):
    """Permission for managing rate limits."""
    
    def has_permission(self, request, view):
        """Check if user can manage rate limits."""
        if not super().has_permission(request, view):
            return False
        
        auth_bridge = AuthBridge()
        return auth_bridge.check_permission(request.user.id, 'rate_limit.manage')


class RateLimitAdminPermission(RateLimitPermission):
    """Permission for rate limit administration."""
    
    def has_permission(self, request, view):
        """Check if user is rate limit admin."""
        if not super().has_permission(request, view):
            return False
        
        auth_bridge = AuthBridge()
        return auth_bridge.check_permission(request.user.id, 'rate_limit.admin')


# Global auth bridge instance
auth_bridge = AuthBridge()


# Export classes and functions
__all__ = [
    'AuthBridge',
    'JWTAuthentication',
    'APIKeyAuthentication',
    'RateLimitPermission',
    'RateLimitManagePermission',
    'RateLimitAdminPermission',
    'auth_bridge'
]
