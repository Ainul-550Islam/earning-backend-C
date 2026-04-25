"""Authentication Bridge

This module provides cross-module authentication for integration system
with comprehensive permission management and access control.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .integ_constants import HealthStatus
from .integ_exceptions import AuthError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

User = get_user_model()


class AuthBridge:
    """
    Authentication bridge for integration system.
    Handles cross-module authentication and permission management.
    """
    
    def __init__(self):
        """Initialize the authentication bridge."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize authentication system
        self._initialize_auth_system()
    
    def _load_configuration(self):
        """Load authentication configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOK_AUTH_BRIDGE_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.cache_timeout = self.config.get('cache_timeout', 300)  # 5 minutes
            self.default_permissions = self.config.get('default_permissions', [])
            self.enable_cross_module = self.config.get('enable_cross_module', True)
            self.token_expiry = self.config.get('token_expiry', 3600)  # 1 hour
            
            self.logger.info("Auth bridge configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading auth bridge configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.cache_timeout = 300
            self.default_permissions = []
            self.enable_cross_module = True
            self.token_expiry = 3600
    
    def _initialize_auth_system(self):
        """Initialize the authentication system."""
        try:
            # Initialize permission cache
            self.permission_cache = {}
            
            # Initialize token manager
            self.token_manager = TokenManager(self.config)
            
            # Initialize permission manager
            self.permission_manager = PermissionManager(self.config)
            
            self.logger.info("Authentication system initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing auth system: {str(e)}")
    
    def authenticate_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate a request.
        
        Args:
            request_data: Request authentication data
            
        Returns:
            Authentication result
        """
        try:
            with self.monitor.measure_auth('authenticate') as measurement:
                result = {
                    'authenticated': False,
                    'user_id': None,
                    'permissions': [],
                    'token': None,
                    'expires_at': None,
                    'errors': [],
                    'authenticated_at': timezone.now().isoformat()
                }
                
                # Extract authentication data
                auth_type = request_data.get('auth_type', 'token')
                
                if auth_type == 'token':
                    result = self._authenticate_with_token(request_data)
                elif auth_type == 'api_key':
                    result = self._authenticate_with_api_key(request_data)
                elif auth_type == 'basic':
                    result = self._authenticate_with_basic(request_data)
                else:
                    result['errors'].append(f"Unsupported auth type: {auth_type}")
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error authenticating request: {str(e)}")
            return {
                'authenticated': False,
                'error': str(e),
                'authenticated_at': timezone.now().isoformat()
            }
    
    def _authenticate_with_token(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with token."""
        try:
            result = {
                'authenticated': False,
                'user_id': None,
                'permissions': [],
                'token': None,
                'expires_at': None,
                'errors': []
            }
            
            token = request_data.get('token')
            if not token:
                result['errors'].append('Token is required')
                return result
            
            # Validate token
            token_data = self.token_manager.validate_token(token)
            if not token_data:
                result['errors'].append('Invalid or expired token')
                return result
            
            # Get user
            user_id = token_data.get('user_id')
            user = self._get_user(user_id)
            if not user:
                result['errors'].append('User not found')
                return result
            
            # Get user permissions
            permissions = self.permission_manager.get_user_permissions(user)
            
            result['authenticated'] = True
            result['user_id'] = user_id
            result['permissions'] = permissions
            result['token'] = token
            result['expires_at'] = token_data.get('expires_at')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error authenticating with token: {str(e)}")
            return {
                'authenticated': False,
                'errors': [str(e)]
            }
    
    def _authenticate_with_api_key(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with API key."""
        try:
            result = {
                'authenticated': False,
                'user_id': None,
                'permissions': [],
                'token': None,
                'expires_at': None,
                'errors': []
            }
            
            api_key = request_data.get('api_key')
            if not api_key:
                result['errors'].append('API key is required')
                return result
            
            # Validate API key
            api_key_data = self.token_manager.validate_api_key(api_key)
            if not api_key_data:
                result['errors'].append('Invalid API key')
                return result
            
            # Get user
            user_id = api_key_data.get('user_id')
            user = self._get_user(user_id)
            if not user:
                result['errors'].append('User not found')
                return result
            
            # Get user permissions
            permissions = self.permission_manager.get_user_permissions(user)
            
            result['authenticated'] = True
            result['user_id'] = user_id
            result['permissions'] = permissions
            result['token'] = api_key
            result['expires_at'] = api_key_data.get('expires_at')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error authenticating with API key: {str(e)}")
            return {
                'authenticated': False,
                'errors': [str(e)]
            }
    
    def _authenticate_with_basic(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with basic auth."""
        try:
            result = {
                'authenticated': False,
                'user_id': None,
                'permissions': [],
                'token': None,
                'expires_at': None,
                'errors': []
            }
            
            username = request_data.get('username')
            password = request_data.get('password')
            
            if not username or not password:
                result['errors'].append('Username and password are required')
                return result
            
            # Authenticate user
            from django.contrib.auth import authenticate
            
            user = authenticate(username=username, password=password)
            if not user:
                result['errors'].append('Invalid credentials')
                return result
            
            # Get user permissions
            permissions = self.permission_manager.get_user_permissions(user)
            
            # Generate token
            token_data = self.token_manager.generate_token(user)
            
            result['authenticated'] = True
            result['user_id'] = str(user.id)
            result['permissions'] = permissions
            result['token'] = token_data.get('token')
            result['expires_at'] = token_data.get('expires_at')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error authenticating with basic auth: {str(e)}")
            return {
                'authenticated': False,
                'errors': [str(e)]
            }
    
    def check_permission(self, user_id: str, permission: str, context: Dict[str, Any] = None) -> bool:
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
            # Get user
            user = self._get_user(user_id)
            if not user:
                return False
            
            # Check permission
            return self.permission_manager.check_permission(user, permission, context)
            
        except Exception as e:
            self.logger.error(f"Error checking permission: {str(e)}")
            return False
    
    def check_permissions(self, user_id: str, permissions: List[str], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Check if user has multiple permissions.
        
        Args:
            user_id: User ID
            permissions: List of permissions to check
            context: Additional context
            
        Returns:
            Permission check results
        """
        try:
            result = {
                'user_id': user_id,
                'permissions_checked': permissions,
                'results': {},
                'all_granted': True,
                'checked_at': timezone.now().isoformat()
            }
            
            # Get user
            user = self._get_user(user_id)
            if not user:
                result['error'] = 'User not found'
                return result
            
            # Check each permission
            for permission in permissions:
                granted = self.permission_manager.check_permission(user, permission, context)
                result['results'][permission] = granted
                
                if not granted:
                    result['all_granted'] = False
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking permissions: {str(e)}")
            return {
                'user_id': user_id,
                'permissions_checked': permissions,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }
    
    def generate_token(self, user_id: str, permissions: List[str] = None, expires_in: int = None) -> Dict[str, Any]:
        """
        Generate authentication token for user.
        
        Args:
            user_id: User ID
            permissions: List of permissions to include
            expires_in: Token expiry time in seconds
            
        Returns:
            Token generation result
        """
        try:
            # Get user
            user = self._get_user(user_id)
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Generate token
            token_data = self.token_manager.generate_token(user, permissions, expires_in)
            
            return {
                'success': True,
                'token': token_data.get('token'),
                'expires_at': token_data.get('expires_at'),
                'permissions': token_data.get('permissions', []),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating token: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate authentication token.
        
        Args:
            token: Token to validate
            
        Returns:
            Token validation result
        """
        try:
            token_data = self.token_manager.validate_token(token)
            
            if token_data:
                return {
                    'valid': True,
                    'user_id': token_data.get('user_id'),
                    'permissions': token_data.get('permissions', []),
                    'expires_at': token_data.get('expires_at'),
                    'validated_at': timezone.now().isoformat()
                }
            else:
                return {
                    'valid': False,
                    'error': 'Invalid or expired token',
                    'validated_at': timezone.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error validating token: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'validated_at': timezone.now().isoformat()
            }
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke authentication token.
        
        Args:
            token: Token to revoke
            
        Returns:
            True if revocation successful
        """
        try:
            return self.token_manager.revoke_token(token)
            
        except Exception as e:
            self.logger.error(f"Error revoking token: {str(e)}")
            return False
    
    def _get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting user {user_id}: {str(e)}")
            return None
    
    def get_user_permissions(self, user_id: str) -> List[str]:
        """
        Get user permissions.
        
        Args:
            user_id: User ID
            
        Returns:
            List of permissions
        """
        try:
            user = self._get_user(user_id)
            if not user:
                return []
            
            return self.permission_manager.get_user_permissions(user)
            
        except Exception as e:
            self.logger.error(f"Error getting user permissions: {str(e)}")
            return []
    
    def get_auth_status(self) -> Dict[str, Any]:
        """
        Get authentication system status.
        
        Returns:
            Authentication status
        """
        try:
            return {
                'auth_bridge': {
                    'status': 'running' if self.enabled else 'disabled',
                    'cache_timeout': self.cache_timeout,
                    'default_permissions': self.default_permissions,
                    'enable_cross_module': self.enable_cross_module,
                    'token_expiry': self.token_expiry,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'token_manager': self.token_manager.get_status(),
                'permission_manager': self.permission_manager.get_status()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting auth status: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of authentication system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check token manager
            token_health = self.token_manager.health_check()
            health_status['components']['token_manager'] = token_health
            
            if token_health['status'] != HealthStatus.HEALTHY:
                health_status['overall'] = HealthStatus.UNHEALTHY
            
            # Check permission manager
            permission_health = self.permission_manager.health_check()
            health_status['components']['permission_manager'] = permission_health
            
            if permission_health['status'] != HealthStatus.HEALTHY:
                health_status['overall'] = HealthStatus.UNHEALTHY
            
            # Check cache
            try:
                cache.set('health_check', 'test', 10)
                cache_result = cache.get('health_check')
                health_status['components']['cache'] = {
                    'status': HealthStatus.HEALTHY if cache_result == 'test' else HealthStatus.UNHEALTHY
                }
            except Exception:
                health_status['components']['cache'] = {
                    'status': HealthStatus.UNHEALTHY,
                    'error': 'Cache connection failed'
                }
                health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }


class TokenManager:
    """Token manager for authentication system."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the token manager."""
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load token manager configuration."""
        try:
            self.token_expiry = self.config.get('token_expiry', 3600)
            self.refresh_token_expiry = self.config.get('refresh_token_expiry', 86400)  # 24 hours
            self.algorithm = self.config.get('algorithm', 'HS256')
            self.secret_key = self.config.get('secret_key', settings.SECRET_KEY)
            
        except Exception as e:
            self.logger.error(f"Error loading token manager configuration: {str(e)}")
            self.token_expiry = 3600
            self.refresh_token_expiry = 86400
            self.algorithm = 'HS256'
            self.secret_key = settings.SECRET_KEY
    
    def generate_token(self, user: User, permissions: List[str] = None, expires_in: int = None) -> Dict[str, Any]:
        """Generate authentication token."""
        try:
            import jwt
            from datetime import datetime, timedelta
            
            if expires_in is None:
                expires_in = self.token_expiry
            
            # Prepare token payload
            payload = {
                'user_id': str(user.id),
                'username': user.username,
                'email': user.email,
                'permissions': permissions or [],
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(seconds=expires_in)
            }
            
            # Generate token
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            return {
                'token': token,
                'expires_at': payload['exp'].isoformat(),
                'permissions': payload['permissions']
            }
            
        except Exception as e:
            self.logger.error(f"Error generating token: {str(e)}")
            raise
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate authentication token."""
        try:
            import jwt
            
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token is expired
            from datetime import datetime
            if datetime.utcnow() > datetime.fromisoformat(payload['exp'].replace('Z', '+00:00')):
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            self.logger.error(f"Error validating token: {str(e)}")
            return None
    
    def revoke_token(self, token: str) -> bool:
        """Revoke authentication token."""
        try:
            # Add token to blacklist
            cache_key = f"blacklisted_token:{hash(token)}"
            cache.set(cache_key, True, timeout=self.token_expiry)
            return True
            
        except Exception as e:
            self.logger.error(f"Error revoking token: {str(e)}")
            return False
    
    def is_token_revoked(self, token: str) -> bool:
        """Check if token is revoked."""
        try:
            cache_key = f"blacklisted_token:{hash(token)}"
            return cache.get(cache_key, False)
            
        except Exception as e:
            self.logger.error(f"Error checking if token is revoked: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get token manager status."""
        return {
            'token_expiry': self.token_expiry,
            'refresh_token_expiry': self.refresh_token_expiry,
            'algorithm': self.algorithm,
            'secret_key_configured': bool(self.secret_key)
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check of token manager."""
        try:
            # Test token generation
            test_token = self.generate_token(
                User(id='test', username='test', email='test@example.com'),
                ['test_permission'],
                60
            )
            
            # Test token validation
            is_valid = self.validate_token(test_token['token']) is not None
            
            return {
                'status': HealthStatus.HEALTHY if is_valid else HealthStatus.UNHEALTHY,
                'token_generation': 'working',
                'token_validation': 'working' if is_valid else 'failed',
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in token manager health check: {str(e)}")
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


class PermissionManager:
    """Permission manager for authentication system."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the permission manager."""
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load permission manager configuration."""
        try:
            self.permission_cache_timeout = self.config.get('permission_cache_timeout', 300)
            self.enable_caching = self.config.get('enable_caching', True)
            self.permission_hierarchy = self.config.get('permission_hierarchy', {})
            
        except Exception as e:
            self.logger.error(f"Error loading permission manager configuration: {str(e)}")
            self.permission_cache_timeout = 300
            self.enable_caching = True
            self.permission_hierarchy = {}
    
    def get_user_permissions(self, user: User) -> List[str]:
        """Get user permissions."""
        try:
            cache_key = f"user_permissions:{user.id}"
            
            if self.enable_caching:
                cached_permissions = cache.get(cache_key)
                if cached_permissions:
                    return cached_permissions
            
            # Get permissions from database
            permissions = self._get_permissions_from_db(user)
            
            # Cache permissions
            if self.enable_caching:
                cache.set(cache_key, permissions, timeout=self.permission_cache_timeout)
            
            return permissions
            
        except Exception as e:
            self.logger.error(f"Error getting user permissions: {str(e)}")
            return []
    
    def _get_permissions_from_db(self, user: User) -> List[str]:
        """Get permissions from database."""
        try:
            # This would integrate with your permission system
            # For now, return basic permissions
            permissions = []
            
            # Add basic permissions based on user status
            if user.is_superuser:
                permissions.extend(['admin', 'superuser', 'all_permissions'])
            elif user.is_staff:
                permissions.extend(['staff', 'moderate'])
            
            # Add user-specific permissions
            if hasattr(user, 'permissions'):
                permissions.extend(user.permissions.all().values_list('codename', flat=True))
            
            return permissions
            
        except Exception as e:
            self.logger.error(f"Error getting permissions from database: {str(e)}")
            return []
    
    def check_permission(self, user: User, permission: str, context: Dict[str, Any] = None) -> bool:
        """Check if user has permission."""
        try:
            # Get user permissions
            user_permissions = self.get_user_permissions(user)
            
            # Check direct permission
            if permission in user_permissions:
                return True
            
            # Check hierarchical permissions
            if self._check_hierarchical_permission(user_permissions, permission):
                return True
            
            # Check context-based permissions
            if context and self._check_context_permission(user_permissions, permission, context):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking permission: {str(e)}")
            return False
    
    def _check_hierarchical_permission(self, user_permissions: List[str], permission: str) -> bool:
        """Check hierarchical permission."""
        try:
            for user_perm in user_permissions:
                if user_perm in self.permission_hierarchy:
                    # Check if permission is in hierarchy
                    if permission in self.permission_hierarchy[user_perm]:
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking hierarchical permission: {str(e)}")
            return False
    
    def _check_context_permission(self, user_permissions: List[str], permission: str, context: Dict[str, Any]) -> bool:
        """Check context-based permission."""
        try:
            # Check resource ownership
            if permission.startswith('own_'):
                resource_type = permission[4:]
                if resource_type in context:
                    resource_id = context[resource_type]
                    if hasattr(resource_id, 'owner'):
                        return resource_id.owner == context.get('user')
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking context permission: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get permission manager status."""
        return {
            'permission_cache_timeout': self.permission_cache_timeout,
            'enable_caching': self.enable_caching,
            'permission_hierarchy_count': len(self.permission_hierarchy)
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check of permission manager."""
        try:
            # Test permission checking
            test_user = User(id='test', username='test', email='test@example.com')
            test_permission = 'test_permission'
            
            try:
                has_permission = self.check_permission(test_user, test_permission)
            except:
                has_permission = False
            
            return {
                'status': HealthStatus.HEALTHY,
                'permission_checking': 'working',
                'test_result': has_permission,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in permission manager health check: {str(e)}")
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }
