"""
Security Endpoint Module
Enhanced endpoint management and configuration for security APIs
"""
from django.conf import settings
from django.utils import timezone
import json

import logging
from typing import Dict, List, Any, Optional, Type, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from django.urls import path, re_path, include
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .registry import security_registry, ComponentType
from .permissions import IsSecurityAdmin
from .utils import SecurityUtils

logger = logging.getLogger('security.endpoint')


class EndpointMethod(Enum):
    """HTTP methods for endpoints"""
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    DELETE = 'DELETE'
    HEAD = 'HEAD'
    OPTIONS = 'OPTIONS'


class EndpointType(Enum):
    """Types of security endpoints"""
    API = 'api'
    WEBHOOK = 'webhook'
    ADMIN = 'admin'
    HEALTH = 'health'
    METRICS = 'metrics'
    CALLBACK = 'callback'
    AUTH = 'auth'
    VALIDATION = 'validation'
    NOTIFICATION = 'notification'


@dataclass
class EndpointConfig:
    """Configuration for a security endpoint"""
    name: str
    path: str
    method: EndpointMethod
    endpoint_type: EndpointType
    handler: Union[Callable, Type[View]]
    description: str = ''
    permissions: List[str] = field(default_factory=list)
    rate_limit: Optional[Dict[str, Any]] = None
    cache_config: Optional[Dict[str, Any]] = None
    middleware: List[str] = field(default_factory=list)
    enabled: bool = True
    version: str = 'v1'
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate endpoint configuration"""
        if not self.name:
            raise ValueError("Endpoint name cannot be empty")
        if not self.path:
            raise ValueError("Endpoint path cannot be empty")
        if not self.handler:
            raise ValueError("Endpoint handler is required")


class SecurityEndpoint:
    """Security endpoint wrapper"""
    
    def __init__(self, config: EndpointConfig):
        self.config = config
        self._setup_handler()
    
    def _setup_handler(self):
        """Setup the endpoint handler with decorators"""
        handler = self.config.handler
        
        # Apply permissions
        if self.config.permissions:
            permission_classes = [IsAuthenticated]
            if 'admin' in self.config.permissions:
                permission_classes.append(IsSecurityAdmin)
            
            handler = permission_classes(permission_classes)(handler)
        
        # Apply rate limiting
        if self.config.rate_limit:
            from .decorators import rate_limit
            handler = rate_limit(**self.config.rate_limit)(handler)
        
        # Apply caching
        if self.config.cache_config:
            from .decorators import cache_response
            handler = cache_response(**self.config.cache_config)(handler)
        
        # Apply middleware
        for middleware_name in self.config.middleware:
            middleware = self._get_middleware(middleware_name)
            if middleware:
                handler = middleware(handler)
        
        self.handler = handler
    
    def _get_middleware(self, middleware_name: str) -> Optional[Callable]:
        """Get middleware by name"""
        middleware_map = {
            'csrf_exempt': csrf_exempt,
            'method_decorator': method_decorator,
        }
        
        return middleware_map.get(middleware_name)
    
    def get_url_pattern(self) -> Union[str, re_path]:
        """Get Django URL pattern for this endpoint"""
        if self.config.path.startswith('^'):
            return re_path(self.config.path, self.handler, name=self.config.name)
        else:
            return path(self.config.path, self.handler, name=self.config.name)
    
    def get_info(self) -> Dict[str, Any]:
        """Get endpoint information"""
        return {
            'name': self.config.name,
            'path': self.config.path,
            'method': self.config.method.value,
            'type': self.config.endpoint_type.value,
            'description': self.config.description,
            'permissions': self.config.permissions,
            'enabled': self.config.enabled,
            'version': self.config.version,
            'tags': self.config.tags,
            'metadata': self.config.metadata,
        }


class EndpointRegistry:
    """Registry for security endpoints"""
    
    def __init__(self):
        self._endpoints: Dict[str, SecurityEndpoint] = {}
        self._type_index: Dict[EndpointType, List[SecurityEndpoint]] = {}
        self._version_index: Dict[str, List[SecurityEndpoint]] = {}
        self._tag_index: Dict[str, List[SecurityEndpoint]] = {}
    
    def register(self, endpoint: SecurityEndpoint) -> None:
        """Register a security endpoint"""
        try:
            # Check for conflicts
            if endpoint.config.name in self._endpoints:
                logger.warning(f"Endpoint {endpoint.config.name} already registered, updating...")
            
            # Add to main registry
            self._endpoints[endpoint.config.name] = endpoint
            
            # Update type index
            if endpoint.config.endpoint_type not in self._type_index:
                self._type_index[endpoint.config.endpoint_type] = []
            self._type_index[endpoint.config.endpoint_type].append(endpoint)
            
            # Update version index
            if endpoint.config.version not in self._version_index:
                self._version_index[endpoint.config.version] = []
            self._version_index[endpoint.config.version].append(endpoint)
            
            # Update tag index
            for tag in endpoint.config.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = []
                self._tag_index[tag].append(endpoint)
            
            logger.info(f"Registered endpoint: {endpoint.config.name}")
            
        except Exception as e:
            logger.error(f"Failed to register endpoint {endpoint.config.name}: {e}")
            raise
    
    def unregister(self, name: str) -> bool:
        """Unregister a security endpoint"""
        try:
            if name not in self._endpoints:
                logger.warning(f"Endpoint {name} not found in registry")
                return False
            
            endpoint = self._endpoints[name]
            
            # Remove from main registry
            del self._endpoints[name]
            
            # Remove from type index
            if endpoint.config.endpoint_type in self._type_index:
                self._type_index[endpoint.config.endpoint_type] = [
                    ep for ep in self._type_index[endpoint.config.endpoint_type]
                    if ep.config.name != name
                ]
            
            # Remove from version index
            if endpoint.config.version in self._version_index:
                self._version_index[endpoint.config.version] = [
                    ep for ep in self._version_index[endpoint.config.version]
                    if ep.config.name != name
                ]
            
            # Remove from tag index
            for tag in endpoint.config.tags:
                if tag in self._tag_index:
                    self._tag_index[tag] = [
                        ep for ep in self._tag_index[tag]
                        if ep.config.name != name
                    ]
            
            logger.info(f"Unregistered endpoint: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister endpoint {name}: {e}")
            return False
    
    def get_endpoint(self, name: str) -> Optional[SecurityEndpoint]:
        """Get endpoint by name"""
        return self._endpoints.get(name)
    
    def get_endpoints_by_type(self, endpoint_type: EndpointType) -> List[SecurityEndpoint]:
        """Get all endpoints of a specific type"""
        return self._type_index.get(endpoint_type, [])
    
    def get_endpoints_by_version(self, version: str) -> List[SecurityEndpoint]:
        """Get all endpoints of a specific version"""
        return self._version_index.get(version, [])
    
    def get_endpoints_by_tag(self, tag: str) -> List[SecurityEndpoint]:
        """Get all endpoints with a specific tag"""
        return self._tag_index.get(tag, [])
    
    def get_enabled_endpoints(self) -> Dict[str, SecurityEndpoint]:
        """Get all enabled endpoints"""
        return {
            name: endpoint for name, endpoint in self._endpoints.items()
            if endpoint.config.enabled
        }
    
    def get_url_patterns(self) -> List:
        """Get Django URL patterns for all enabled endpoints"""
        patterns = []
        
        for endpoint in self.get_enabled_endpoints().values():
            patterns.append(endpoint.get_url_pattern())
        
        return patterns
    
    def get_endpoint_info(self) -> Dict[str, Any]:
        """Get registry information"""
        return {
            'total_endpoints': len(self._endpoints),
            'enabled_endpoints': len(self.get_enabled_endpoints()),
            'endpoints_by_type': {
                endpoint_type.value: len(endpoints)
                for endpoint_type, endpoints in self._type_index.items()
            },
            'endpoints_by_version': {
                version: len(endpoints)
                for version, endpoints in self._version_index.items()
            },
            'endpoints_by_tag': {
                tag: len(endpoints)
                for tag, endpoints in self._tag_index.items()
            }
        }


# Built-in endpoint handlers
@api_view(['GET'])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def health_check(request):
    """Health check endpoint"""
    try:
        # Check database connectivity
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    # Check cache connectivity
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        cache.get('health_check')
        cache_status = "healthy"
    except Exception:
        cache_status = "unhealthy"
    
    # Overall status
    overall_status = "healthy" if db_status == "healthy" and cache_status == "healthy" else "unhealthy"
    
    return Response({
        'status': overall_status,
        'timestamp': timezone.now().isoformat(),
        'services': {
            'database': db_status,
            'cache': cache_status,
        },
        'version': getattr(settings, 'SECURITY_VERSION', '1.0.0')
    })

@permission_classes([IsAuthenticated, IsSecurityAdmin])
def security_metrics(request):
    """Security metrics endpoint"""
    try:
        from .models import SecurityLog, SecurityIncident
        
        # Get metrics
        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)
        last_7d = now - timezone.timedelta(days=7)
        
        metrics = {
            'security_logs': {
                'total': SecurityLog.objects.count(),
                'last_24h': SecurityLog.objects.filter(created_at__gte=last_24h).count(),
                'last_7d': SecurityLog.objects.filter(created_at__gte=last_7d).count(),
            },
            'security_incidents': {
                'total': SecurityIncident.objects.count(),
                'open': SecurityIncident.objects.filter(status='open').count(),
                'last_24h': SecurityIncident.objects.filter(opened_at__gte=last_24h).count(),
                'last_7d': SecurityIncident.objects.filter(opened_at__gte=last_7d).count(),
            },
            'timestamp': now.isoformat(),
        }
        
        return Response(metrics)
        
    except Exception as e:
        logger.error(f"Error getting security metrics: {e}")
        return Response({
            'error': 'Failed to get metrics',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@permission_classes([IsAuthenticated])
def validate_token(request):
    """Token validation endpoint"""
    try:
        token = request.data.get('token')
        if not token:
            return Response({
                'valid': False,
                'error': 'Token required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate token format
        if len(token) < 32:
            return Response({
                'valid': False,
                'error': 'Invalid token format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Additional validation logic here
        is_valid = SecurityUtils.validate_api_key(token)
        
        return Response({
            'valid': is_valid,
            'token_length': len(token),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        return Response({
            'valid': False,
            'error': 'Validation failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SecurityNotificationView(View):
    """Security notification endpoint"""
    
    def post(self, request):
        """Handle security notifications"""
        try:
            data = json.loads(request.body)
            
            # Validate notification data
            required_fields = ['type', 'message', 'priority']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            # Process notification
            notification_data = {
                'type': data['type'],
                'message': data['message'],
                'priority': data['priority'],
                'timestamp': timezone.now().isoformat(),
                'metadata': data.get('metadata', {}),
            }
            
            # Store notification or send to external service
            self._process_notification(notification_data)
            
            return JsonResponse({
                'status': 'success',
                'notification_id': SecurityUtils.generate_secure_token(16)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            logger.error(f"Error processing notification: {e}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)
    
    def _process_notification(self, notification_data):
        """Process notification data"""
        # Implementation depends on notification system
        logger.info(f"Processing security notification: {notification_data['type']}")


# Global endpoint registry
endpoint_registry = EndpointRegistry()


def register_endpoint(name: str, path: str, method: Union[EndpointMethod, str],
                     endpoint_type: Union[EndpointType, str], handler: Union[Callable, Type[View]],
                     **kwargs):
    """Decorator for registering security endpoints"""
    def decorator(func_or_class):
        # Convert string enums to enum values
        if isinstance(method, str):
            method = EndpointMethod(method.upper())
        if isinstance(endpoint_type, str):
            endpoint_type = EndpointType(endpoint_type.lower())
        
        # Create endpoint configuration
        config = EndpointConfig(
            name=name,
            path=path,
            method=method,
            endpoint_type=endpoint_type,
            handler=func_or_class,
            **kwargs
        )
        
        # Create and register endpoint
        endpoint = SecurityEndpoint(config)
        endpoint_registry.register(endpoint)
        
        return func_or_class
    
    return decorator


# Auto-register built-in endpoints
def register_builtin_endpoints():
    """Register built-in security endpoints"""
    
    # Health check endpoint
    health_config = EndpointConfig(
        name='health_check',
        path='health/',
        method=EndpointMethod.GET,
        endpoint_type=EndpointType.HEALTH,
        handler=health_check,
        description='System health check',
        permissions=['authenticated'],
        tags=['health', 'system']
    )
    endpoint_registry.register(SecurityEndpoint(health_config))
    
    # Security metrics endpoint
    metrics_config = EndpointConfig(
        name='security_metrics',
        path='metrics/',
        method=EndpointMethod.GET,
        endpoint_type=EndpointType.METRICS,
        handler=security_metrics,
        description='Security metrics and statistics',
        permissions=['admin'],
        tags=['metrics', 'admin']
    )
    endpoint_registry.register(SecurityEndpoint(metrics_config))
    
    # Token validation endpoint
    validation_config = EndpointConfig(
        name='validate_token',
        path='validate-token/',
        method=EndpointMethod.POST,
        endpoint_type=EndpointType.VALIDATION,
        handler=validate_token,
        description='Validate security token',
        permissions=['authenticated'],
        tags=['validation', 'auth']
    )
    endpoint_registry.register(SecurityEndpoint(validation_config))
    
    # Security notification endpoint
    notification_config = EndpointConfig(
        name='security_notification',
        path='notification/',
        method=EndpointMethod.POST,
        endpoint_type=EndpointType.NOTIFICATION,
        handler=SecurityNotificationView.as_view(),
        description='Security notification handler',
        permissions=['authenticated'],
        tags=['notification']
    )
    endpoint_registry.register(SecurityEndpoint(notification_config))


# URL pattern generator
def generate_security_urls():
    """Generate Django URL patterns for security endpoints"""
    urlpatterns = []
    
    # Add all registered endpoints
    urlpatterns.extend(endpoint_registry.get_url_patterns())
    
    # Add endpoint info endpoint
    urlpatterns.append(
        path('endpoints/', EndpointInfoView.as_view(), name='security_endpoints_info')
    )
    
    return urlpatterns


class EndpointInfoView(View):
    """View for endpoint information"""
    
    def get(self, request):
        """Get endpoint registry information"""
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        if not getattr(request.user, 'is_security_admin', False) and not request.user.is_superuser:
            return JsonResponse({'error': 'Admin access required'}, status=403)
        
        return JsonResponse(endpoint_registry.get_endpoint_info())


# Export classes and utilities
__all__ = [
    'EndpointMethod',
    'EndpointType',
    'EndpointConfig',
    'SecurityEndpoint',
    'EndpointRegistry',
    'endpoint_registry',
    'register_endpoint',
    'register_builtin_endpoints',
    'generate_security_urls',
    'health_check',
    'security_metrics',
    'validate_token',
    'SecurityNotificationView',
    'EndpointInfoView'
]