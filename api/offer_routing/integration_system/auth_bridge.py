"""
Auth Bridge

Cross-module permission system for integration system
to provide unified authentication and authorization.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import json
import hashlib
import hmac
from ..constants import (
    IntegrationType, IntegrationStatus, IntegrationLogLevel,
    INTEGRATION_TYPES, INTEGRATION_STATUSES, INTEGRATION_LOG_LEVELS,
    ERROR_CODES
)
from ..exceptions import (
    IntegrationError, AuthenticationError, AuthorizationError
)

logger = logging.getLogger(__name__)


class AuthBridge:
    """
    Authentication bridge for integration system.
    
    Provides unified authentication and authorization for:
    - Cross-module permission management
    - Token-based authentication
    - Role-based access control
    - API key management
    - Session management
    """
    
    def __init__(self):
        self.auth_strategies = {
            'token': self._token_auth,
            'api_key': self._api_key_auth,
            'oauth': self._oauth_auth,
            'session': self._session_auth,
            'certificate': self._certificate_auth
        }
        self.permission_manager = PermissionManager()
        self.token_store = TokenStore()
        self.session_store = SessionStore()
        self.auth_stats = {
            'total_authentications': 0,
            'successful_authentications': 0,
            'failed_authentications': 0,
            'avg_auth_time_ms': 0.0
        }
    
    def authenticate_integration(self, integration_id: str, auth_data: Dict[str, Any], 
                              auth_type: IntegrationType) -> Dict[str, Any]:
        """
        Authenticate integration using specified authentication type.
        
        Args:
            integration_id: Integration identifier
            auth_data: Authentication data
            auth_type: Type of authentication
            
        Returns:
            Authentication result with token and permissions
        """
        try:
            start_time = datetime.now()
            
            # Validate authentication data
            validation_result = self._validate_auth_data(auth_data, auth_type)
            if not validation_result['success']:
                return validation_result
            
            # Get authentication strategy
            auth_strategy = self.auth_strategies.get(auth_type.value)
            if not auth_strategy:
                return {
                    'success': False,
                    'error': f'Unsupported authentication type: {auth_type}',
                    'error_code': 'UNSUPPORTED_AUTH_TYPE'
                }
            
            # Execute authentication
            auth_result = auth_strategy(integration_id, auth_data)
            
            # Update authentication stats
            self._update_auth_stats(start_time, auth_result['success'])
            
            if auth_result['success']:
                # Store token and permissions
                token = auth_result.get('token')
                permissions = auth_result.get('permissions', [])
                
                # Store in token store
                self.token_store.store_token(integration_id, token, permissions)
                
                # Update permission manager
                self.permission_manager.set_integration_permissions(integration_id, permissions)
                
                return {
                    'success': True,
                    'integration_id': integration_id,
                    'token': token,
                    'permissions': permissions,
                    'expires_at': auth_result.get('expires_at'),
                    'auth_type': auth_type.value,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': auth_result.get('error', 'Authentication failed'),
                    'error_code': auth_result.get('error_code', 'AUTH_FAILED'),
                    'integration_id': integration_id,
                    'auth_type': auth_type.value,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error authenticating integration {integration_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'AUTH_ERROR',
                'integration_id': integration_id,
                'timestamp': datetime.now().isoformat()
            }
    
    def authorize_integration_action(self, integration_id: str, action: str, 
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authorize integration action based on permissions.
        
        Args:
            integration_id: Integration identifier
            action: Action to authorize
            context: Request context
            
        Returns:
            Authorization result with decision and reason
        """
        try:
            start_time = datetime.now()
            
            # Get integration permissions
            permissions = self.permission_manager.get_integration_permissions(integration_id)
            
            # Check if integration is active
            if not self._is_integration_active(integration_id):
                return {
                    'authorized': False,
                    'reason': 'Integration is not active',
                    'error_code': 'INTEGRATION_INACTIVE'
                }
            
            # Check action authorization
            auth_result = self._authorize_action(action, permissions, context)
            
            # Update authorization stats
            self._update_auth_stats(start_time, auth_result['authorized'])
            
            return {
                'authorized': auth_result['authorized'],
                'integration_id': integration_id,
                'action': action,
                'reason': auth_result.get('reason'),
                'permissions_checked': auth_result.get('permissions_checked', []),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error authorizing integration action {integration_id}: {e}")
            return {
                'authorized': False,
                'reason': f'Authorization error: {str(e)}',
                'error_code': 'AUTHORIZATION_ERROR',
                'integration_id': integration_id,
                'timestamp': datetime.now().isoformat()
            }
    
    def validate_token(self, token: str, integration_id: str) -> Dict[str, Any]:
        """
        Validate authentication token for integration.
        
        Args:
            token: Authentication token
            integration_id: Integration identifier
            
        Returns:
            Token validation result
        """
        try:
            # Check token format
            if not token or not isinstance(token, str):
                return {
                    'valid': False,
                    'error': 'Invalid token format',
                    'error_code': 'INVALID_TOKEN_FORMAT'
                }
            
            # Get stored token
            stored_token = self.token_store.get_token(integration_id)
            
            if not stored_token:
                return {
                    'valid': False,
                    'error': 'Token not found',
                    'error_code': 'TOKEN_NOT_FOUND'
                }
            
            # Compare tokens
            if not self._compare_tokens(token, stored_token['token']):
                return {
                    'valid': False,
                    'error': 'Invalid token',
                    'error_code': 'INVALID_TOKEN'
                }
            
            # Check token expiration
            if stored_token.get('expires_at'):
                expires_at = datetime.fromisoformat(stored_token['expires_at'])
                if datetime.now() > expires_at:
                    return {
                        'valid': False,
                        'error': 'Token expired',
                        'error_code': 'TOKEN_EXPIRED'
                    }
            
            return {
                'valid': True,
                'integration_id': integration_id,
                'permissions': stored_token.get('permissions', []),
                'expires_at': stored_token.get('expires_at'),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating token for {integration_id}: {e}")
            return {
                'valid': False,
                'error': str(e),
                'error_code': 'TOKEN_VALIDATION_ERROR'
            }
    
    def refresh_token(self, integration_id: str, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh authentication token for integration.
        
        Args:
            integration_id: Integration identifier
            refresh_token: Refresh token
            
        Returns:
            Token refresh result
        """
        try:
            # Validate refresh token
            if not refresh_token:
                return {
                    'success': False,
                    'error': 'Refresh token is required',
                    'error_code': 'MISSING_REFRESH_TOKEN'
                }
            
            # Get stored refresh token
            stored_refresh_token = self.token_store.get_refresh_token(integration_id)
            
            if not stored_refresh_token or not self._compare_tokens(refresh_token, stored_refresh_token):
                return {
                    'success': False,
                    'error': 'Invalid refresh token',
                    'error_code': 'INVALID_REFRESH_TOKEN'
                }
            
            # Generate new token pair
            new_token = self._generate_token_pair(integration_id)
            
            # Store new tokens
            self.token_store.store_token(integration_id, new_token['access_token'], new_token['permissions'])
            self.token_store.store_refresh_token(integration_id, new_token['refresh_token'])
            
            return {
                'success': True,
                'integration_id': integration_id,
                'access_token': new_token['access_token'],
                'refresh_token': new_token['refresh_token'],
                'permissions': new_token['permissions'],
                'expires_at': new_token['expires_at'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error refreshing token for {integration_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'TOKEN_REFRESH_ERROR'
            }
    
    def revoke_token(self, integration_id: str, token: str) -> Dict[str, Any]:
        """
        Revoke authentication token for integration.
        
        Args:
            integration_id: Integration identifier
            token: Token to revoke
            
        Returns:
            Token revocation result
        """
        try:
            # Validate token
            validation_result = self.validate_token(token, integration_id)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Invalid token',
                    'error_code': 'INVALID_TOKEN'
                }
            
            # Remove token from store
            self.token_store.revoke_token(integration_id, token)
            
            # Clear permissions
            self.permission_manager.clear_integration_permissions(integration_id)
            
            return {
                'success': True,
                'integration_id': integration_id,
                'message': 'Token revoked successfully',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error revoking token for {integration_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'TOKEN_REVOCATION_ERROR'
            }
    
    def _token_auth(self, integration_id: str, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Token-based authentication."""
        try:
            username = auth_data.get('username')
            password = auth_data.get('password')
            
            # Validate credentials
            if not username or not password:
                return {
                    'success': False,
                    'error': 'Username and password are required',
                    'error_code': 'MISSING_CREDENTIALS'
                }
            
            # Authenticate against user store (this would integrate with your auth system)
            # For now, simulate authentication
            if username == 'admin' and password == 'password':
                token = self._generate_token(integration_id)
                return {
                    'success': True,
                    'token': token,
                    'permissions': ['admin', 'read', 'write'],
                    'expires_at': token['expires_at']
                }
            else:
                return {
                    'success': False,
                    'error': 'Invalid credentials',
                    'error_code': 'INVALID_CREDENTIALS'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Token auth error: {str(e)}',
                'error_code': 'TOKEN_AUTH_ERROR'
            }
    
    def _api_key_auth(self, integration_id: str, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """API key authentication."""
        try:
            api_key = auth_data.get('api_key')
            
            if not api_key:
                return {
                    'success': False,
                    'error': 'API key is required',
                    'error_code': 'MISSING_API_KEY'
                }
            
            # Validate API key format
            if not self._is_valid_api_key(api_key):
                return {
                    'success': False,
                    'error': 'Invalid API key format',
                    'error_code': 'INVALID_API_KEY'
                }
            
            # Generate token
            token = self._generate_token(integration_id)
            
            return {
                'success': True,
                'token': token,
                'permissions': ['api_access'],
                'expires_at': token['expires_at']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'API key auth error: {str(e)}',
                'error_code': 'API_KEY_AUTH_ERROR'
            }
    
    def _oauth_auth(self, integration_id: str, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """OAuth authentication."""
        try:
            # OAuth flow implementation
            # This would integrate with OAuth providers
            return {
                'success': False,
                'error': 'OAuth not implemented',
                'error_code': 'OAUTH_NOT_IMPLEMENTED'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'OAuth auth error: {str(e)}',
                'error_code': 'OAUTH_AUTH_ERROR'
            }
    
    def _session_auth(self, integration_id: str, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Session-based authentication."""
        try:
            session_id = auth_data.get('session_id')
            
            if not session_id:
                return {
                    'success': False,
                    'error': 'Session ID is required',
                    'error_code': 'MISSING_SESSION_ID'
                }
            
            # Get session from store
            session = self.session_store.get_session(session_id)
            
            if not session:
                return {
                    'success': False,
                    'error': 'Invalid session',
                    'error_code': 'INVALID_SESSION'
                }
            
            # Check session expiration
            if session.get('expires_at') and datetime.now() > datetime.fromisoformat(session['expires_at']):
                return {
                    'success': False,
                    'error': 'Session expired',
                    'error_code': 'SESSION_EXPIRED'
                }
            
            return {
                'success': True,
                'session_id': session_id,
                'permissions': session.get('permissions', []),
                'expires_at': session.get('expires_at')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Session auth error: {str(e)}',
                'error_code': 'SESSION_AUTH_ERROR'
            }
    
    def _certificate_auth(self, integration_id: str, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Certificate-based authentication."""
        try:
            certificate = auth_data.get('certificate')
            private_key = auth_data.get('private_key')
            
            if not certificate or not private_key:
                return {
                    'success': False,
                    'error': 'Certificate and private key are required',
                    'error_code': 'MISSING_CERTIFICATE'
                }
            
            # Validate certificate
            if not self._is_valid_certificate(certificate):
                return {
                    'success': False,
                    'error': 'Invalid certificate',
                    'error_code': 'INVALID_CERTIFICATE'
                }
            
            # Generate token
            token = self._generate_token(integration_id)
            
            return {
                'success': True,
                'token': token,
                'permissions': ['certificate_access'],
                'expires_at': token['expires_at']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Certificate auth error: {str(e)}',
                'error_code': 'CERTIFICATE_AUTH_ERROR'
            }
    
    def _validate_auth_data(self, auth_data: Dict[str, Any], auth_type: IntegrationType) -> Dict[str, Any]:
        """Validate authentication data."""
        try:
            # Basic structure validation
            if not isinstance(auth_data, dict):
                return {
                    'success': False,
                    'error': 'Authentication data must be a dictionary',
                    'error_code': 'INVALID_AUTH_DATA_TYPE'
                }
            
            # Type-specific validation
            if auth_type == IntegrationType.WEBHOOK:
                return self._validate_webhook_auth_data(auth_data)
            elif auth_type == IntegrationType.API:
                return self._validate_api_auth_data(auth_data)
            elif auth_type == IntegrationType.DATABASE:
                return self._validate_database_auth_data(auth_data)
            
            return {
                'success': True,
                'message': 'Authentication data is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Validation error: {str(e)}',
                'error_code': 'VALIDATION_ERROR'
            }
    
    def _validate_webhook_auth_data(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate webhook authentication data."""
        try:
            required_fields = ['url', 'secret']
            missing_fields = [field for field in required_fields if field not in auth_data]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_WEBHOOK_FIELDS'
                }
            
            # URL validation
            url = auth_data.get('url', '')
            if not self._is_valid_url(url):
                return {
                    'success': False,
                    'error': f'Invalid webhook URL: {url}',
                    'error_code': 'INVALID_WEBHOOK_URL'
                }
            
            return {
                'success': True,
                'message': 'Webhook authentication data is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Webhook validation error: {str(e)}',
                'error_code': 'WEBHOOK_VALIDATION_ERROR'
            }
    
    def _validate_api_auth_data(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API authentication data."""
        try:
            required_fields = ['base_url', 'auth_type']
            missing_fields = [field for field in required_fields if field not in auth_data]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_API_FIELDS'
                }
            
            return {
                'success': True,
                'message': 'API authentication data is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'API validation error: {str(e)}',
                'error_code': 'API_VALIDATION_ERROR'
            }
    
    def _validate_database_auth_data(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate database authentication data."""
        try:
            required_fields = ['connection_string', 'database_type']
            missing_fields = [field for field in required_fields if field not in auth_data]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_DATABASE_FIELDS'
                }
            
            return {
                'success': True,
                'message': 'Database authentication data is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Database validation error: {str(e)}',
                'error_code': 'DATABASE_VALIDATION_ERROR'
            }
    
    def _authorize_action(self, action: str, permissions: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Authorize action based on permissions."""
        try:
            # Define action permissions mapping
            action_permissions = {
                'read': ['read'],
                'write': ['write'],
                'delete': ['delete'],
                'admin': ['admin'],
                'execute': ['execute'],
                'configure': ['configure']
            }
            
            required_permissions = action_permissions.get(action, [])
            
            if not required_permissions:
                return {
                    'authorized': False,
                    'reason': f'Unknown action: {action}',
                    'permissions_checked': []
                }
            
            # Check if user has required permissions
            has_permission = any(perm in permissions for perm in required_permissions)
            
            if has_permission:
                return {
                    'authorized': True,
                    'reason': 'Action authorized',
                    'permissions_checked': required_permissions
                }
            else:
                return {
                    'authorized': False,
                    'reason': f'Insufficient permissions for action: {action}',
                    'permissions_checked': required_permissions
                }
                
        except Exception as e:
            return {
                'authorized': False,
                'reason': f'Authorization error: {str(e)}',
                'permissions_checked': []
            }
    
    def _is_integration_active(self, integration_id: str) -> bool:
        """Check if integration is active."""
        try:
            # This would check integration status
            # For now, return True
            return True
        except Exception as e:
            logger.error(f"Error checking integration status: {e}")
            return False
    
    def _generate_token(self, integration_id: str) -> Dict[str, Any]:
        """Generate authentication token."""
        try:
            # Generate random token
            import secrets
            token = secrets.token_urlsafe(32)
            
            # Calculate expiration
            expires_at = datetime.now() + timedelta(hours=24)
            
            return {
                'token': token,
                'expires_at': expires_at.isoformat(),
                'integration_id': integration_id
            }
        except Exception as e:
            logger.error(f"Error generating token: {e}")
            return {}
    
    def _generate_token_pair(self, integration_id: str) -> Dict[str, Any]:
        """Generate access and refresh token pair."""
        try:
            access_token = self._generate_token(integration_id)
            refresh_token = secrets.token_urlsafe(64)
            
            return {
                'access_token': access_token['token'],
                'refresh_token': refresh_token,
                'permissions': ['read', 'write'],
                'expires_at': access_token['expires_at']
            }
        except Exception as e:
            logger.error(f"Error generating token pair: {e}")
            return {}
    
    def _compare_tokens(self, token1: str, token2: str) -> bool:
        """Compare two tokens securely."""
        try:
            # Use constant-time comparison
            return hmac.compare_digest(token1.encode(), token2.encode())
        except Exception as e:
            logger.error(f"Error comparing tokens: {e}")
            return False
    
    def _is_valid_api_key(self, api_key: str) -> bool:
        """Validate API key format."""
        try:
            # Basic API key validation
            if len(api_key) < 16:
                return False
            
            # Check for valid characters
            import re
            if not re.match(r'^[a-zA-Z0-9_\-]+$', api_key):
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return False
    
    def _is_valid_certificate(self, certificate: str) -> bool:
        """Validate certificate format."""
        try:
            # Basic certificate validation
            if not certificate or len(certificate) < 100:
                return False
            
            # Check for certificate headers
            if not certificate.startswith('-----BEGIN CERTIFICATE-----'):
                return False
            
            if not certificate.endswith('-----END CERTIFICATE-----'):
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error validating certificate: {e}")
            return False
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            import re
            url_pattern = re.compile(
                r'^https?://'  # http or https
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
                r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
                r'(?::\d+)?'  # port
                r'(?:/?|[/?]\S+)$',  # path
                re.IGNORECASE
            )
            return bool(url_pattern.match(url))
        except:
            return False
    
    def _update_auth_stats(self, start_time: datetime, success: bool):
        """Update authentication statistics."""
        try:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.auth_stats['total_authentications'] += 1
            
            if success:
                self.auth_stats['successful_authentications'] += 1
            else:
                self.auth_stats['failed_authentications'] += 1
            
            # Update average time
            current_avg = self.auth_stats['avg_auth_time_ms']
            total_auth = self.auth_stats['total_authentications']
            self.auth_stats['avg_auth_time_ms'] = (
                (current_avg * (total_auth - 1) + execution_time) / total_auth
            )
            
        except Exception as e:
            logger.error(f"Error updating auth stats: {e}")
    
    def get_auth_stats(self) -> Dict[str, Any]:
        """Get authentication statistics."""
        return self.auth_stats
    
    def reset_auth_stats(self) -> bool:
        """Reset authentication statistics."""
        try:
            self.auth_stats = {
                'total_authentications': 0,
                'successful_authentications': 0,
                'failed_authentications': 0,
                'avg_auth_time_ms': 0.0
            }
            
            logger.info("Reset authentication statistics")
            return True
        except Exception as e:
            logger.error(f"Error resetting auth stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on auth bridge."""
        try:
            # Test authentication strategies
            strategy_health = {}
            for strategy_name, strategy_func in self.auth_strategies.items():
                try:
                    # Test strategy with mock data
                    test_result = strategy_func('test_integration', {'test': 'data'})
                    strategy_health[strategy_name] = {
                        'status': 'healthy' if test_result else 'unhealthy',
                        'last_test': datetime.now().isoformat()
                    }
                except Exception as e:
                    strategy_health[strategy_name] = {
                        'status': 'error',
                        'error': str(e),
                        'last_test': datetime.now().isoformat()
                    }
            
            return {
                'status': 'healthy' if all(s['status'] == 'healthy' for s in strategy_health.values()) else 'degraded',
                'strategies': strategy_health,
                'auth_stats': self.auth_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in auth bridge health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


class PermissionManager:
    """Permission management for cross-module access control."""
    
    def __init__(self):
        self.integration_permissions = {}
        self.role_permissions = {
            'admin': ['read', 'write', 'delete', 'configure'],
            'user': ['read'],
            'service': ['read', 'write']
        }
    
    def set_integration_permissions(self, integration_id: str, permissions: List[str]):
        """Set permissions for integration."""
        self.integration_permissions[integration_id] = permissions
    
    def get_integration_permissions(self, integration_id: str) -> List[str]:
        """Get permissions for integration."""
        return self.integration_permissions.get(integration_id, [])
    
    def clear_integration_permissions(self, integration_id: str):
        """Clear permissions for integration."""
        if integration_id in self.integration_permissions:
            del self.integration_permissions[integration_id]
    
    def check_permission(self, integration_id: str, permission: str, role: str = 'user') -> bool:
        """Check if integration has permission."""
        integration_perms = self.get_integration_permissions(integration_id)
        role_perms = self.role_permissions.get(role, [])
        
        return permission in integration_perms and permission in role_perms


class TokenStore:
    """Token storage for authentication."""
    
    def __init__(self):
        self.tokens = {}
        self.refresh_tokens = {}
    
    def store_token(self, integration_id: str, token: str, permissions: List[str]):
        """Store authentication token."""
        self.tokens[integration_id] = {
            'token': token,
            'permissions': permissions,
            'created_at': datetime.now().isoformat()
        }
    
    def get_token(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """Get stored token."""
        return self.tokens.get(integration_id)
    
    def revoke_token(self, integration_id: str, token: str):
        """Revoke authentication token."""
        if integration_id in self.tokens:
            del self.tokens[integration_id]
    
    def store_refresh_token(self, integration_id: str, refresh_token: str):
        """Store refresh token."""
        self.refresh_tokens[integration_id] = {
            'refresh_token': refresh_token,
            'created_at': datetime.now().isoformat()
        }
    
    def get_refresh_token(self, integration_id: str) -> Optional[str]:
        """Get stored refresh token."""
        token_data = self.refresh_tokens.get(integration_id)
        return token_data['refresh_token'] if token_data else None


class SessionStore:
    """Session storage for authentication."""
    
    def __init__(self):
        self.sessions = {}
    
    def create_session(self, user_id: str, permissions: List[str]) -> str:
        """Create new session."""
        import secrets
        session_id = secrets.token_urlsafe(32)
        
        self.sessions[session_id] = {
            'user_id': user_id,
            'permissions': permissions,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=8)).isoformat()
        }
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str):
        """Delete session."""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Global instances
auth_bridge = AuthBridge()
permission_manager = PermissionManager()
token_store = TokenStore()
session_store = SessionStore()
