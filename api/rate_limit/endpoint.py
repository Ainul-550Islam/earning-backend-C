# api/rate_limit/endpoint.py
"""
Endpoint management for rate limit module.

Provides endpoint discovery, registration, and management functionality.
"""

import logging
from typing import Dict, Any, List, Optional, Set
from django.conf import settings
from django.urls import get_resolver
from django.utils.module_loading import import_string
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class EndpointRegistry:
    """
    Registry for managing API endpoints and their rate limit configurations.
    """
    
    def __init__(self):
        self.endpoints: Dict[str, Dict[str, Any]] = {}
        self.endpoint_groups: Dict[str, List[str]] = {}
        self._load_default_endpoints()
    
    def _load_default_endpoints(self):
        """Load default endpoint configurations."""
        # Common API endpoints with default rate limits
        default_endpoints = {
            '/api/auth/login/': {
                'name': 'login',
                'method': 'POST',
                'default_limit': 5,
                'time_window': 'minute',
                'group': 'authentication',
                'description': 'User login endpoint',
                'sensitive': True,
            },
            '/api/auth/register/': {
                'name': 'register',
                'method': 'POST',
                'default_limit': 3,
                'time_window': 'minute',
                'group': 'authentication',
                'description': 'User registration endpoint',
                'sensitive': True,
            },
            '/api/auth/token/': {
                'name': 'token_refresh',
                'method': 'POST',
                'default_limit': 10,
                'time_window': 'minute',
                'group': 'authentication',
                'description': 'Token refresh endpoint',
                'sensitive': True,
            },
            '/api/tasks/': {
                'name': 'tasks_list',
                'method': 'GET',
                'default_limit': 100,
                'time_window': 'minute',
                'group': 'tasks',
                'description': 'Tasks list endpoint',
                'sensitive': False,
            },
            '/api/tasks/create/': {
                'name': 'tasks_create',
                'method': 'POST',
                'default_limit': 20,
                'time_window': 'minute',
                'group': 'tasks',
                'description': 'Task creation endpoint',
                'sensitive': False,
            },
            '/api/offers/': {
                'name': 'offers_list',
                'method': 'GET',
                'default_limit': 200,
                'time_window': 'minute',
                'group': 'offers',
                'description': 'Offers list endpoint',
                'sensitive': False,
            },
            '/api/offers/complete/': {
                'name': 'offers_complete',
                'method': 'POST',
                'default_limit': 50,
                'time_window': 'minute',
                'group': 'offers',
                'description': 'Offer completion endpoint',
                'sensitive': False,
            },
            '/api/referrals/': {
                'name': 'referrals',
                'method': 'GET',
                'default_limit': 100,
                'time_window': 'minute',
                'group': 'referrals',
                'description': 'Referrals endpoint',
                'sensitive': False,
            },
            '/api/withdrawals/': {
                'name': 'withdrawals',
                'method': 'POST',
                'default_limit': 5,
                'time_window': 'hour',
                'group': 'financial',
                'description': 'Withdrawal endpoint',
                'sensitive': True,
            },
            '/api/deposits/': {
                'name': 'deposits',
                'method': 'POST',
                'default_limit': 10,
                'time_window': 'hour',
                'group': 'financial',
                'description': 'Deposit endpoint',
                'sensitive': True,
            },
        }
        
        for endpoint_path, config in default_endpoints.items():
            self.register_endpoint(endpoint_path, config)
    
    def register_endpoint(self, path: str, config: Dict[str, Any]):
        """
        Register an endpoint with rate limit configuration.
        
        Args:
            path: Endpoint path
            config: Endpoint configuration
        """
        # Ensure required fields
        required_fields = ['name', 'method', 'default_limit', 'time_window']
        for field in required_fields:
            if field not in config:
                config[field] = self._get_default_field_value(field)
        
        self.endpoints[path] = config
        
        # Add to group if specified
        group = config.get('group', 'default')
        if group not in self.endpoint_groups:
            self.endpoint_groups[group] = []
        
        if path not in self.endpoint_groups[group]:
            self.endpoint_groups[group].append(path)
        
        logger.info(f"Registered endpoint: {path}")
    
    def unregister_endpoint(self, path: str):
        """
        Unregister an endpoint.
        
        Args:
            path: Endpoint path
        """
        if path in self.endpoints:
            config = self.endpoints[path]
            group = config.get('group', 'default')
            
            # Remove from endpoints
            del self.endpoints[path]
            
            # Remove from group
            if group in self.endpoint_groups and path in self.endpoint_groups[group]:
                self.endpoint_groups[group].remove(path)
            
            logger.info(f"Unregistered endpoint: {path}")
    
    def _get_default_field_value(self, field: str) -> Any:
        """Get default value for a field."""
        defaults = {
            'name': 'unnamed',
            'method': 'GET',
            'default_limit': 100,
            'time_window': 'hour',
            'group': 'default',
            'description': '',
            'sensitive': False,
            'priority': 'normal',
            'enabled': True,
        }
        return defaults.get(field)
    
    def get_endpoint_config(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for an endpoint.
        
        Args:
            path: Endpoint path
            
        Returns:
            Endpoint configuration or None
        """
        return self.endpoints.get(path)
    
    def find_endpoint_by_pattern(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Find endpoint configuration by pattern matching.
        
        Args:
            path: Request path
            
        Returns:
            Matching endpoint configuration or None
        """
        # Direct match first
        if path in self.endpoints:
            return self.endpoints[path]
        
        # Pattern matching
        for endpoint_path, config in self.endpoints.items():
            if self._path_matches_pattern(path, endpoint_path):
                return config
        
        return None
    
    def _path_matches_pattern(self, request_path: str, pattern: str) -> bool:
        """
        Check if request path matches endpoint pattern.
        
        Args:
            request_path: Actual request path
            pattern: Endpoint pattern
            
        Returns:
            True if matches
        """
        # Simple pattern matching - can be enhanced with regex
        if pattern.endswith('/'):
            # Exact match or prefix match
            if request_path == pattern:
                return True
            if request_path.startswith(pattern):
                return True
        else:
            # Exact match
            if request_path == pattern:
                return True
        
        return False
    
    def get_endpoints_by_group(self, group: str) -> List[Dict[str, Any]]:
        """
        Get all endpoints in a group.
        
        Args:
            group: Group name
            
        Returns:
            List of endpoint configurations
        """
        if group not in self.endpoint_groups:
            return []
        
        endpoints = []
        for path in self.endpoint_groups[group]:
            if path in self.endpoints:
                endpoints.append(self.endpoints[path])
        
        return endpoints
    
    def get_sensitive_endpoints(self) -> List[Dict[str, Any]]:
        """
        Get all sensitive endpoints.
        
        Returns:
            List of sensitive endpoint configurations
        """
        return [
            config for config in self.endpoints.values()
            if config.get('sensitive', False)
        ]
    
    def get_enabled_endpoints(self) -> List[Dict[str, Any]]:
        """
        Get all enabled endpoints.
        
        Returns:
            List of enabled endpoint configurations
        """
        return [
            config for config in self.endpoints.values()
            if config.get('enabled', True)
        ]
    
    def update_endpoint_config(self, path: str, updates: Dict[str, Any]):
        """
        Update endpoint configuration.
        
        Args:
            path: Endpoint path
            updates: Configuration updates
        """
        if path not in self.endpoints:
            raise ValueError(f"Endpoint not registered: {path}")
        
        self.endpoints[path].update(updates)
        logger.info(f"Updated endpoint configuration: {path}")
    
    def list_groups(self) -> List[str]:
        """
        List all endpoint groups.
        
        Returns:
            List of group names
        """
        return list(self.endpoint_groups.keys())
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Registry statistics
        """
        total_endpoints = len(self.endpoints)
        enabled_endpoints = len(self.get_enabled_endpoints())
        sensitive_endpoints = len(self.get_sensitive_endpoints())
        
        return {
            'total_endpoints': total_endpoints,
            'enabled_endpoints': enabled_endpoints,
            'disabled_endpoints': total_endpoints - enabled_endpoints,
            'sensitive_endpoints': sensitive_endpoints,
            'total_groups': len(self.endpoint_groups),
        }


class EndpointDiscovery:
    """
    Discover API endpoints from Django URL configuration.
    """
    
    def __init__(self):
        self.discovered_endpoints = []
    
    def discover_endpoints(self) -> List[Dict[str, Any]]:
        """
        Discover all API endpoints from Django URL configuration.
        
        Returns:
            List of discovered endpoints
        """
        try:
            resolver = get_resolver()
            self.discovered_endpoints = []
            
            # Recursively discover endpoints
            self._discover_from_resolver(resolver.url_patterns, '')
            
            logger.info(f"Discovered {len(self.discovered_endpoints)} endpoints")
            return self.discovered_endpoints
            
        except Exception as e:
            logger.error(f"Failed to discover endpoints: {str(e)}")
            return []
    
    def _discover_from_resolver(self, patterns, prefix):
        """
        Recursively discover endpoints from URL patterns.
        
        Args:
            patterns: URL patterns
            prefix: URL prefix
        """
        from django.urls import URLPattern, URLResolver
        
        for pattern in patterns:
            if isinstance(pattern, URLPattern):
                # Endpoint pattern
                endpoint_path = prefix + str(pattern.pattern)
                
                # Extract endpoint information
                endpoint_info = {
                    'path': endpoint_path,
                    'name': pattern.name or '',
                    'callback': str(pattern.callback),
                    'methods': self._get_allowed_methods(pattern.callback),
                }
                
                self.discovered_endpoints.append(endpoint_info)
                
            elif isinstance(pattern, URLResolver):
                # Resolver pattern - recurse
                new_prefix = prefix + str(pattern.pattern)
                self._discover_from_resolver(pattern.url_patterns, new_prefix)
    
    def _get_allowed_methods(self, callback) -> List[str]:
        """
        Get allowed HTTP methods for a callback.
        
        Args:
            callback: View callback
            
        Returns:
            List of allowed methods
        """
        methods = ['GET', 'HEAD', 'OPTIONS']  # Default methods
        
        try:
            # Try to get view class
            if hasattr(callback, 'view_class'):
                view_class = callback.view_class
                
                # Check for HTTP method decorators
                if hasattr(view_class, 'http_method_names'):
                    methods = view_class.http_method_names
                
                # Check for allowed_methods
                if hasattr(view_class, 'allowed_methods'):
                    methods = view_class.allowed_methods
                
            # Check for method attributes
            if hasattr(callback, 'get'):
                methods.append('GET')
            if hasattr(callback, 'post'):
                methods.append('POST')
            if hasattr(callback, 'put'):
                methods.append('PUT')
            if hasattr(callback, 'patch'):
                methods.append('PATCH')
            if hasattr(callback, 'delete'):
                methods.append('DELETE')
            
        except Exception:
            pass
        
        return list(set(methods))
    
    def filter_api_endpoints(self, endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter endpoints to only include API endpoints.
        
        Args:
            endpoints: List of all endpoints
            
        Returns:
            List of API endpoints
        """
        api_prefixes = getattr(settings, 'RATE_LIMIT_API_PREFIXES', ['/api/', '/v1/', '/v2/'])
        
        api_endpoints = []
        for endpoint in endpoints:
            path = endpoint.get('path', '')
            
            if any(path.startswith(prefix) for prefix in api_prefixes):
                api_endpoints.append(endpoint)
        
        return api_endpoints


class EndpointRateLimitManager:
    """
    Manager for applying rate limits to endpoints.
    """
    
    def __init__(self, endpoint_registry: EndpointRegistry):
        self.endpoint_registry = endpoint_registry
        self.applied_configs = {}
    
    def apply_rate_limits_to_endpoints(self, endpoints: List[str] = None):
        """
        Apply rate limits to endpoints.
        
        Args:
            endpoints: List of endpoint paths (optional, defaults to all)
        """
        if endpoints is None:
            endpoints = list(self.endpoint_registry.endpoints.keys())
        
        for endpoint_path in endpoints:
            config = self.endpoint_registry.get_endpoint_config(endpoint_path)
            if config and config.get('enabled', True):
                self._apply_rate_limit_to_endpoint(endpoint_path, config)
    
    def _apply_rate_limit_to_endpoint(self, path: str, config: Dict[str, Any]):
        """
        Apply rate limit to a specific endpoint.
        
        Args:
            path: Endpoint path
            config: Endpoint configuration
        """
        try:
            from api.rate_limit.models import RateLimitConfig
            
            # Check if config already exists
            existing_config = RateLimitConfig.objects.filter(
                endpoint=path,
                rate_limit_type='endpoint'
            ).first()
            
            if existing_config:
                # Update existing config
                existing_config.requests_per_unit = config['default_limit']
                existing_config.time_unit = config['time_window']
                existing_config.is_active = config.get('enabled', True)
                existing_config.save(update_fields=['requests_per_unit', 'time_unit', 'is_active'])
            else:
                # Create new config
                RateLimitConfig.objects.create(
                    name=config['name'],
                    rate_limit_type='endpoint',
                    endpoint=path,
                    requests_per_unit=config['default_limit'],
                    time_unit=config['time_window'],
                    is_active=config.get('enabled', True)
                )
            
            self.applied_configs[path] = config
            logger.info(f"Applied rate limit to endpoint: {path}")
            
        except Exception as e:
            logger.error(f"Failed to apply rate limit to {path}: {str(e)}")
    
    def remove_rate_limit_from_endpoint(self, path: str):
        """
        Remove rate limit from an endpoint.
        
        Args:
            path: Endpoint path
        """
        try:
            from api.rate_limit.models import RateLimitConfig
            
            # Deactivate rate limit config
            RateLimitConfig.objects.filter(
                endpoint=path,
                rate_limit_type='endpoint'
            ).update(is_active=False)
            
            if path in self.applied_configs:
                del self.applied_configs[path]
            
            logger.info(f"Removed rate limit from endpoint: {path}")
            
        except Exception as e:
            logger.error(f"Failed to remove rate limit from {path}: {str(e)}")
    
    def get_endpoint_rate_limit_status(self, path: str) -> Dict[str, Any]:
        """
        Get rate limit status for an endpoint.
        
        Args:
            path: Endpoint path
            
        Returns:
            Rate limit status
        """
        try:
            from api.rate_limit.models import RateLimitConfig
            
            config = RateLimitConfig.objects.filter(
                endpoint=path,
                rate_limit_type='endpoint',
                is_active=True
            ).first()
            
            if config:
                return {
                    'has_rate_limit': True,
                    'config': {
                        'name': config.name,
                        'requests_per_unit': config.requests_per_unit,
                        'time_unit': config.time_unit,
                        'is_active': config.is_active,
                    }
                }
            else:
                return {'has_rate_limit': False}
                
        except Exception as e:
            logger.error(f"Failed to get rate limit status for {path}: {str(e)}")
            return {'has_rate_limit': False, 'error': str(e)}


# Global instances
endpoint_registry = EndpointRegistry()
endpoint_discovery = EndpointDiscovery()
endpoint_manager = EndpointRateLimitManager(endpoint_registry)


def auto_discover_and_apply():
    """
    Auto-discover endpoints and apply rate limits.
    """
    try:
        # Discover endpoints
        discovered = endpoint_discovery.discover_endpoints()
        api_endpoints = endpoint_discovery.filter_api_endpoints(discovered)
        
        # Register discovered endpoints
        for endpoint in api_endpoints:
            path = endpoint['path']
            
            # Skip if already registered
            if endpoint_registry.get_endpoint_config(path):
                continue
            
            # Create basic configuration
            config = {
                'name': endpoint.get('name', f"endpoint_{path.replace('/', '_').replace('-', '_')}"),
                'method': 'GET',  # Default to GET
                'default_limit': 100,  # Default limit
                'time_window': 'hour',  # Default window
                'group': 'discovered',
                'description': f"Auto-discovered endpoint: {path}",
                'sensitive': False,
            }
            
            endpoint_registry.register_endpoint(path, config)
        
        # Apply rate limits
        endpoint_manager.apply_rate_limits_to_endpoints()
        
        logger.info("Auto-discovery and rate limit application completed")
        
    except Exception as e:
        logger.error(f"Auto-discovery failed: {str(e)}")


# Auto-discover on import
if getattr(settings, 'RATE_LIMIT_AUTO_DISCOVER_ENDPOINTS', True):
    try:
        auto_discover_and_apply()
    except Exception as e:
        logger.error(f"Failed to auto-discover endpoints: {str(e)}")


# Export classes and functions
__all__ = [
    'EndpointRegistry',
    'EndpointDiscovery',
    'EndpointRateLimitManager',
    'endpoint_registry',
    'endpoint_discovery',
    'endpoint_manager',
    'auto_discover_and_apply'
]
