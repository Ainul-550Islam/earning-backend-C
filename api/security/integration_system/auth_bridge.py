"""
Auth Bridge Module
Cross-module permission and authentication bridge
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import AuthType

User = get_user_model()
logger = logging.getLogger('security.integration.auth_bridge')


class PermissionBridge:
    """Bridge for cross-module permissions"""
    
    def __init__(self):
        self.permission_mappings = {}
        self.module_permissions = {}
        self.role_permissions = {}
        self.cache_timeout = 300  # 5 minutes
        self.enabled = True
    
    def register_module_permissions(self, module_name: str, permissions: Dict[str, str]):
        """Register permissions for a module"""
        self.module_permissions[module_name] = permissions
        logger.info(f"Registered permissions for module: {module_name}")
    
    def register_role_permissions(self, role_name: str, permissions: List[str]):
        """Register permissions for a role"""
        self.role_permissions[role_name] = permissions
        logger.info(f"Registered permissions for role: {role_name}")
    
    def add_permission_mapping(self, source_permission: str, target_permissions: List[str]):
        """Add permission mapping"""
        self.permission_mappings[source_permission] = target_permissions
        logger.info(f"Added permission mapping: {source_permission}")
    
    def check_permission(self, user: User, permission: str, module: str = None) -> bool:
        """Check if user has permission"""
        if not self.enabled:
            return True  # Allow all if disabled
        
        cache_key = f"auth_bridge_permission:{user.id}:{permission}:{module or 'global'}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        # Check direct permission
        if self._check_direct_permission(user, permission):
            cache.set(cache_key, True, self.cache_timeout)
            return True
        
        # Check mapped permissions
        mapped_permissions = self.permission_mappings.get(permission, [])
        for mapped_perm in mapped_permissions:
            if self._check_direct_permission(user, mapped_perm):
                cache.set(cache_key, True, self.cache_timeout)
                return True
        
        # Check module permissions
        if module and module in self.module_permissions:
            module_perms = self.module_permissions[module]
            if permission in module_perms.values():
                cache.set(cache_key, True, self.cache_timeout)
                return True
        
        cache.set(cache_key, False, self.cache_timeout)
        return False
    
    def _check_direct_permission(self, user: User, permission: str) -> bool:
        """Check direct permission"""
        try:
            # Check Django permission
            if user.has_perm(permission):
                return True
            
            # Check if user is superuser
            if user.is_superuser:
                return True
            
            # Check role-based permissions
            for role_name, role_perms in self.role_permissions.items():
                if hasattr(user, 'roles') and role_name in user.roles:
                    if permission in role_perms:
                        return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error checking permission {permission} for user {user.id}: {e}")
            return False
    
    def get_user_permissions(self, user: User, module: str = None) -> List[str]:
        """Get all permissions for user"""
        permissions = set()
        
        # Get Django permissions
        user_perms = user.get_all_permissions()
        permissions.update(user_perms)
        
        # Add mapped permissions
        for perm in list(permissions):
            mapped_perms = self.permission_mappings.get(perm, [])
            permissions.update(mapped_perms)
        
        # Add module permissions
        if module and module in self.module_permissions:
            module_perms = self.module_permissions[module]
            for perm_name, perm_codename in module_perms.items():
                if user.has_perm(perm_codename):
                    permissions.add(perm_name)
        
        return list(permissions)
    
    def clear_permission_cache(self, user: User = None):
        """Clear permission cache"""
        if user:
            # Clear specific user cache
            cache_pattern = f"auth_bridge_permission:{user.id}:*"
            # This would require cache.delete_pattern in Redis
            # For now, just log
            logger.info(f"Cleared permission cache for user {user.id}")
        else:
            # Clear all permission cache
            logger.info("Cleared all permission cache")


class AuthenticationBridge:
    """Bridge for cross-module authentication"""
    
    def __init__(self):
        self.auth_providers = {}
        self.auth_mappings = {}
        self.token_store = {}
        self.session_store = {}
        self.cache_timeout = 3600  # 1 hour
        self.enabled = True
    
    def register_auth_provider(self, provider_name: str, provider_config: Dict[str, Any]):
        """Register authentication provider"""
        self.auth_providers[provider_name] = provider_config
        logger.info(f"Registered auth provider: {provider_name}")
    
    def add_auth_mapping(self, source_provider: str, target_provider: str, mapping_config: Dict[str, Any]):
        """Add authentication mapping"""
        mapping_key = f"{source_provider}->{target_provider}"
        self.auth_mappings[mapping_key] = mapping_config
        logger.info(f"Added auth mapping: {mapping_key}")
    
    def authenticate_user(self, credentials: Dict[str, Any], provider: str = None) -> Dict[str, Any]:
        """Authenticate user with provider"""
        if not self.enabled:
            return {
                'status': 'error',
                'message': 'Authentication bridge disabled'
            }
        
        if not provider:
            # Try default provider
            provider = 'django'
        
        provider_config = self.auth_providers.get(provider)
        if not provider_config:
            return {
                'status': 'error',
                'message': f'Auth provider not found: {provider}'
            }
        
        try:
            # Authenticate with provider
            auth_result = self._authenticate_with_provider(credentials, provider, provider_config)
            
            if auth_result['status'] == 'success':
                # Create authentication token
                token = self._create_auth_token(auth_result['user'], provider)
                
                # Store token
                self.token_store[token] = {
                    'user_id': auth_result['user'].id,
                    'provider': provider,
                    'created_at': timezone.now(),
                    'expires_at': timezone.now() + timedelta(hours=self.cache_timeout / 3600)
                }
                
                return {
                    'status': 'success',
                    'user': auth_result['user'],
                    'token': token,
                    'provider': provider
                }
            else:
                return auth_result
        
        except Exception as e:
            logger.error(f"Error authenticating with provider {provider}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _authenticate_with_provider(self, credentials: Dict[str, Any], provider: str, 
                                  config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with specific provider"""
        if provider == 'django':
            return self._authenticate_django(credentials)
        elif provider == 'ldap':
            return self._authenticate_ldap(credentials, config)
        elif provider == 'oauth':
            return self._authenticate_oauth(credentials, config)
        elif provider == 'saml':
            return self._authenticate_saml(credentials, config)
        else:
            return {
                'status': 'error',
                'message': f'Unsupported provider: {provider}'
            }
    
    def _authenticate_django(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with Django"""
        from django.contrib.auth import authenticate
        
        username = credentials.get('username')
        password = credentials.get('password')
        
        if not username or not password:
            return {
                'status': 'error',
                'message': 'Username and password required'
            }
        
        user = authenticate(username=username, password=password)
        
        if user:
            return {
                'status': 'success',
                'user': user
            }
        else:
            return {
                'status': 'error',
                'message': 'Invalid credentials'
            }
    
    def _authenticate_ldap(self, credentials: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with LDAP"""
        # This would implement LDAP authentication
        # For now, return error
        return {
            'status': 'error',
            'message': 'LDAP authentication not implemented'
        }
    
    def _authenticate_oauth(self, credentials: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with OAuth"""
        # This would implement OAuth authentication
        # For now, return error
        return {
            'status': 'error',
            'message': 'OAuth authentication not implemented'
        }
    
    def _authenticate_saml(self, credentials: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with SAML"""
        # This would implement SAML authentication
        # For now, return error
        return {
            'status': 'error',
            'message': 'SAML authentication not implemented'
        }
    
    def _create_auth_token(self, user: User, provider: str) -> str:
        """Create authentication token"""
        import secrets
        
        token_data = f"{user.id}:{provider}:{timezone.now().isoformat()}:{secrets.token_hex(16)}"
        token = SecurityUtils.generate_hash(token_data)
        
        return token
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate authentication token"""
        if not self.enabled:
            return {
                'status': 'error',
                'message': 'Authentication bridge disabled'
            }
        
        token_data = self.token_store.get(token)
        
        if not token_data:
            return {
                'status': 'error',
                'message': 'Invalid token'
            }
        
        # Check if token expired
        if timezone.now() > token_data['expires_at']:
            del self.token_store[token]
            return {
                'status': 'error',
                'message': 'Token expired'
            }
        
        try:
            user = User.objects.get(id=token_data['user_id'])
            return {
                'status': 'success',
                'user': user,
                'provider': token_data['provider']
            }
        
        except User.DoesNotExist:
            return {
                'status': 'error',
                'message': 'User not found'
            }
    
    def revoke_token(self, token: str) -> bool:
        """Revoke authentication token"""
        if token in self.token_store:
            del self.token_store[token]
            logger.info(f"Revoked token: {token[:10]}...")
            return True
        return False
    
    def get_user_sessions(self, user: User) -> List[Dict[str, Any]]:
        """Get user sessions"""
        sessions = []
        
        for token, token_data in self.token_store.items():
            if token_data['user_id'] == user.id:
                sessions.append({
                    'token': token[:10] + '...',
                    'provider': token_data['provider'],
                    'created_at': token_data['created_at'].isoformat(),
                    'expires_at': token_data['expires_at'].isoformat()
                })
        
        return sessions
    
    def revoke_user_sessions(self, user: User) -> int:
        """Revoke all user sessions"""
        revoked_count = 0
        
        tokens_to_remove = []
        for token, token_data in self.token_store.items():
            if token_data['user_id'] == user.id:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self.token_store[token]
            revoked_count += 1
        
        logger.info(f"Revoked {revoked_count} sessions for user {user.id}")
        return revoked_count


class CrossModuleAuthBridge:
    """Cross-module authentication and authorization bridge"""
    
    def __init__(self):
        self.permission_bridge = PermissionBridge()
        self.auth_bridge = AuthenticationBridge()
        self.module_access = {}
        self.integration_access = {}
        self.enabled = True
    
    def register_module_access(self, module_name: str, access_config: Dict[str, Any]):
        """Register module access configuration"""
        self.module_access[module_name] = access_config
        logger.info(f"Registered module access: {module_name}")
    
    def register_integration_access(self, integration_name: str, access_config: Dict[str, Any]):
        """Register integration access configuration"""
        self.integration_access[integration_name] = access_config
        logger.info(f"Registered integration access: {integration_name}")
    
    def check_module_access(self, user: User, module_name: str, action: str = 'read') -> bool:
        """Check module access"""
        if not self.enabled:
            return True
        
        # Check if module exists
        if module_name not in self.module_access:
            return False
        
        access_config = self.module_access[module_name]
        
        # Check if action is allowed
        allowed_actions = access_config.get('allowed_actions', [])
        if action not in allowed_actions:
            return False
        
        # Check permissions
        required_permissions = access_config.get('required_permissions', [])
        for permission in required_permissions:
            if not self.permission_bridge.check_permission(user, permission, module_name):
                return False
        
        # Check roles
        required_roles = access_config.get('required_roles', [])
        if required_roles:
            if not hasattr(user, 'roles'):
                return False
            
            if not any(role in user.roles for role in required_roles):
                return False
        
        return True
    
    def check_integration_access(self, user: User, integration_name: str, action: str = 'execute') -> bool:
        """Check integration access"""
        if not self.enabled:
            return True
        
        # Check if integration exists
        if integration_name not in self.integration_access:
            return False
        
        access_config = self.integration_access[integration_name]
        
        # Check if action is allowed
        allowed_actions = access_config.get('allowed_actions', [])
        if action not in allowed_actions:
            return False
        
        # Check permissions
        required_permissions = access_config.get('required_permissions', [])
        for permission in required_permissions:
            if not self.permission_bridge.check_permission(user, permission):
                return False
        
        # Check roles
        required_roles = access_config.get('required_roles', [])
        if required_roles:
            if not hasattr(user, 'roles'):
                return False
            
            if not any(role in user.roles for role in required_roles):
                return False
        
        return True
    
    def get_user_module_access(self, user: User) -> Dict[str, List[str]]:
        """Get user's module access"""
        access = {}
        
        for module_name, access_config in self.module_access.items():
            allowed_actions = []
            
            for action in access_config.get('allowed_actions', []):
                if self.check_module_access(user, module_name, action):
                    allowed_actions.append(action)
            
            if allowed_actions:
                access[module_name] = allowed_actions
        
        return access
    
    def get_user_integration_access(self, user: User) -> Dict[str, List[str]]:
        """Get user's integration access"""
        access = {}
        
        for integration_name, access_config in self.integration_access.items():
            allowed_actions = []
            
            for action in access_config.get('allowed_actions', []):
                if self.check_integration_access(user, integration_name, action):
                    allowed_actions.append(action)
            
            if allowed_actions:
                access[integration_name] = allowed_actions
        
        return access
    
    def authenticate_and_authorize(self, credentials: Dict[str, Any], module: str = None, 
                                  integration: str = None, action: str = 'read') -> Dict[str, Any]:
        """Authenticate and authorize user"""
        # Authenticate
        auth_result = self.auth_bridge.authenticate_user(credentials)
        
        if auth_result['status'] != 'success':
            return auth_result
        
        user = auth_result['user']
        
        # Authorize
        if module:
            if not self.check_module_access(user, module, action):
                return {
                    'status': 'error',
                    'message': f'Access denied to module {module} for action {action}'
                }
        
        if integration:
            if not self.check_integration_access(user, integration, action):
                return {
                    'status': 'error',
                    'message': f'Access denied to integration {integration} for action {action}'
                }
        
        return {
            'status': 'success',
            'user': user,
            'token': auth_result['token'],
            'authorized': True
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status"""
        return {
            'enabled': self.enabled,
            'permission_bridge': {
                'modules_count': len(self.permission_bridge.module_permissions),
                'roles_count': len(self.permission_bridge.role_permissions),
                'mappings_count': len(self.permission_bridge.permission_mappings)
            },
            'auth_bridge': {
                'providers_count': len(self.auth_bridge.auth_providers),
                'mappings_count': len(self.auth_bridge.auth_mappings),
                'active_tokens': len(self.auth_bridge.token_store)
            },
            'module_access_count': len(self.module_access),
            'integration_access_count': len(self.integration_access)
        }
    
    def enable(self):
        """Enable bridge"""
        self.enabled = True
        self.permission_bridge.enable()
        self.auth_bridge.enable()
        logger.info("Cross-module auth bridge enabled")
    
    def disable(self):
        """Disable bridge"""
        self.enabled = False
        self.permission_bridge.disable()
        self.auth_bridge.disable()
        logger.info("Cross-module auth bridge disabled")


# Global bridge instance
cross_module_auth_bridge = CrossModuleAuthBridge()


# Create default configurations
def create_default_auth_configurations():
    """Create default authentication and authorization configurations"""
    
    # Register module permissions
    cross_module_auth_bridge.permission_bridge.register_module_permissions('security', {
        'view_security_logs': 'security.view_securitylog',
        'manage_security_incidents': 'security.manage_securityincident',
        'view_threat_intelligence': 'security.view_threatintelligence',
        'manage_users': 'auth.change_user'
    })
    
    cross_module_auth_bridge.permission_bridge.register_module_permissions('audit_logs', {
        'view_audit_logs': 'audit_logs.view_auditlog',
        'export_audit_logs': 'audit_logs.export_auditlog',
        'manage_audit_config': 'audit_logs.change_auditlogconfig'
    })
    
    cross_module_auth_bridge.permission_bridge.register_module_permissions('behavior_analytics', {
        'view_analytics': 'behavior_analytics.view_analytics',
        'manage_user_paths': 'behavior_analytics.manage_userpath',
        'export_data': 'behavior_analytics.export_data'
    })
    
    # Register role permissions
    cross_module_auth_bridge.permission_bridge.register_role_permissions('admin', [
        'view_security_logs',
        'manage_security_incidents',
        'view_threat_intelligence',
        'manage_users',
        'view_audit_logs',
        'export_audit_logs',
        'manage_audit_config',
        'view_analytics',
        'manage_user_paths',
        'export_data'
    ])
    
    cross_module_auth_bridge.permission_bridge.register_role_permissions('analyst', [
        'view_security_logs',
        'view_threat_intelligence',
        'view_audit_logs',
        'export_audit_logs',
        'view_analytics',
        'export_data'
    ])
    
    cross_module_auth_bridge.permission_bridge.register_role_permissions('viewer', [
        'view_security_logs',
        'view_threat_intelligence',
        'view_audit_logs',
        'view_analytics'
    ])
    
    # Register module access
    cross_module_auth_bridge.register_module_access('security', {
        'allowed_actions': ['read', 'write', 'delete'],
        'required_permissions': ['view_security_logs'],
        'required_roles': ['admin', 'analyst']
    })
    
    cross_module_auth_bridge.register_module_access('audit_logs', {
        'allowed_actions': ['read', 'export'],
        'required_permissions': ['view_audit_logs'],
        'required_roles': ['admin', 'analyst']
    })
    
    cross_module_auth_bridge.register_module_access('behavior_analytics', {
        'allowed_actions': ['read', 'export'],
        'required_permissions': ['view_analytics'],
        'required_roles': ['admin', 'analyst']
    })
    
    # Register integration access
    cross_module_auth_bridge.register_integration_access('webhook_integration', {
        'allowed_actions': ['execute', 'configure'],
        'required_permissions': ['manage_security_incidents'],
        'required_roles': ['admin']
    })
    
    cross_module_auth_bridge.register_integration_access('data_bridge', {
        'allowed_actions': ['execute', 'configure'],
        'required_permissions': ['manage_security_incidents'],
        'required_roles': ['admin']
    })
    
    logger.info("Created default auth configurations")


# Initialize default configurations
create_default_auth_configurations()


# Export symbols
__all__ = [
    'PermissionBridge',
    'AuthenticationBridge',
    'CrossModuleAuthBridge',
    'cross_module_auth_bridge',
    'create_default_auth_configurations'
]