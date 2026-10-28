"""
resources.py – Resource management for postback module.

Provides comprehensive resource functionality including:
- Resource definitions and management
- API resource classes
- Resource serialization
- Resource caching and optimization
"""
import logging
from typing import Dict, List, Optional, Any, Union, Type
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .serializers import PostbackLogSerializer, PostbackInsightSerializer, NetworkPostbackConfigSerializer
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class ResourceType(Enum):
    """Resource type enumeration."""
    MODEL = "model"
    API = "api"
    DATA = "data"
    FILE = "file"
    CACHE = "cache"


class ResourceStatus(Enum):
    """Resource status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    LOADING = "loading"


class BaseResource:
    """
    Base resource class.
    
    Provides common resource functionality that can be
    extended for specific resource types.
    """
    
    def __init__(self, name: str, resource_type: ResourceType):
        self.name = name
        self.resource_type = resource_type
        self.status = ResourceStatus.ACTIVE
        self.metadata = {}
        self.cache_timeout = 300
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_cache_key(self, *args, **kwargs) -> str:
        """
        Generate cache key for resource.
        
        Args:
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments
            
        Returns:
            Cache key string
        """
        key_parts = [self.resource_type.value, self.name]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        
        return ':'.join(key_parts)
    
    def get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        Get resource from cache.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached resource or None
        """
        return cache.get(cache_key)
    
    def set_cache(self, cache_key: str, data: Any, timeout: int = None):
        """
        Set resource in cache.
        
        Args:
            cache_key: Cache key
            data: Data to cache
            timeout: Cache timeout
        """
        timeout = timeout or self.cache_timeout
        cache.set(cache_key, data, timeout)
    
    def delete_cache(self, cache_key: str):
        """
        Delete resource from cache.
        
        Args:
            cache_key: Cache key
        """
        cache.delete(cache_key)
    
    def validate_access(self, user: User = None, **kwargs) -> bool:
        """
        Validate access to resource.
        
        Args:
            user: User requesting access
            **kwargs: Additional validation parameters
            
        Returns:
            True if access is allowed
        """
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get resource metadata.
        
        Returns:
            Resource metadata
        """
        return {
            'name': self.name,
            'type': self.resource_type.value,
            'status': self.status.value,
            'metadata': self.metadata,
            'cache_timeout': self.cache_timeout,
        }


class ModelResource(BaseResource):
    """
    Resource for Django models.
    
    Provides specialized functionality for model resources
    including CRUD operations and caching.
    """
    
    def __init__(self, name: str, model_class: Type, serializer_class: Type = None):
        super().__init__(name, ResourceType.MODEL)
        self.model_class = model_class
        self.serializer_class = serializer_class
        self.queryset = model_class.objects.all()
    
    def get_queryset(self, user: User = None, **filters):
        """
        Get filtered queryset.
        
        Args:
            user: User for filtering
            **filters: Filter parameters
            
        Returns:
            Filtered queryset
        """
        queryset = self.queryset
        
        # Apply user filtering if model has user field
        if user and hasattr(self.model_class, 'resolved_user'):
            queryset = queryset.filter(resolved_user=user)
        
        # Apply filters
        for field, value in filters.items():
            if value is not None:
                if isinstance(value, list):
                    queryset = queryset.filter(**{f"{field}__in": value})
                else:
                    queryset = queryset.filter(**{field: value})
        
        return queryset
    
    def get_object(self, pk: Any, user: User = None):
        """
        Get single object by primary key.
        
        Args:
            pk: Primary key
            user: User for access validation
            
        Returns:
            Model instance
        """
        try:
            obj = self.queryset.get(pk=pk)
            
            if not self.validate_access(user, obj=obj):
                raise PermissionError("Access denied")
            
            return obj
            
        except self.model_class.DoesNotExist:
            raise ValueError(f"{self.model_class.__name__} not found")
    
    def serialize_object(self, obj, many: bool = False):
        """
        Serialize object(s).
        
        Args:
            obj: Object(s) to serialize
            many: Whether serializing multiple objects
            
        Returns:
            Serialized data
        """
        if not self.serializer_class:
            return obj
        
        if many:
            return self.serializer_class(obj, many=True).data
        else:
            return self.serializer_class(obj).data
    
    def create_object(self, data: Dict[str, Any], user: User = None):
        """
        Create new object.
        
        Args:
            data: Object data
            user: User creating object
            
        Returns:
            Created object
        """
        if not self.validate_access(user, action='create'):
            raise PermissionError("Access denied")
        
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        
        return obj
    
    def update_object(self, pk: Any, data: Dict[str, Any], user: User = None):
        """
        Update existing object.
        
        Args:
            pk: Primary key
            data: Update data
            user: User updating object
            
        Returns:
            Updated object
        """
        obj = self.get_object(pk, user)
        
        if not self.validate_access(user, action='update', obj=obj):
            raise PermissionError("Access denied")
        
        serializer = self.serializer_class(obj, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        
        return obj
    
    def delete_object(self, pk: Any, user: User = None):
        """
        Delete object.
        
        Args:
            pk: Primary key
            user: User deleting object
        """
        obj = self.get_object(pk, user)
        
        if not self.validate_access(user, action='delete', obj=obj):
            raise PermissionError("Access denied")
        
        obj.delete()
    
    def get_list(self, user: User = None, **filters):
        """
        Get list of objects.
        
        Args:
            user: User for filtering
            **filters: Filter parameters
            
        Returns:
            List of objects
        """
        queryset = self.get_queryset(user, **filters)
        return queryset


class APIResource(BaseResource, GenericAPIView):
    """
    Resource for API endpoints.
    
    Provides specialized functionality for API resources
    including request handling and response formatting.
    """
    
    def __init__(self, name: str, serializer_class: Type = None):
        BaseResource.__init__(self, name, ResourceType.API)
        GenericAPIView.__init__(self)
        self.serializer_class = serializer_class
    
    def get_queryset(self):
        """Get queryset for API resource."""
        return self.queryset
    
    def get_object(self):
        """Get single object for API resource."""
        return super().get_object()
    
    def handle_request(self, request, *args, **kwargs):
        """
        Handle API request.
        
        Args:
            request: HTTP request
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            HTTP response
        """
        try:
            # Validate access
            if not self.validate_access(request.user, request=request):
                return Response(
                    {'error': 'Access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Handle based on method
            if request.method == 'GET':
                return self.handle_get(request, *args, **kwargs)
            elif request.method == 'POST':
                return self.handle_post(request, *args, **kwargs)
            elif request.method == 'PUT':
                return self.handle_put(request, *args, **kwargs)
            elif request.method == 'PATCH':
                return self.handle_patch(request, *args, **kwargs)
            elif request.method == 'DELETE':
                return self.handle_delete(request, *args, **kwargs)
            else:
                return Response(
                    {'error': f'Method {request.method} not allowed'},
                    status=status.HTTP_405_METHOD_NOT_ALLOWED
                )
        
        except Exception as e:
            self.logger.error(f"Error in API resource {self.name}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def handle_get(self, request, *args, **kwargs):
        """Handle GET request."""
        return self.list(request, *args, **kwargs)
    
    def handle_post(self, request, *args, **kwargs):
        """Handle POST request."""
        return self.create(request, *args, **kwargs)
    
    def handle_put(self, request, *args, **kwargs):
        """Handle PUT request."""
        return self.update(request, *args, **kwargs)
    
    def handle_patch(self, request, *args, **kwargs):
        """Handle PATCH request."""
        return self.partial_update(request, *args, **kwargs)
    
    def handle_delete(self, request, *args, **kwargs):
        """Handle DELETE request."""
        return self.destroy(request, *args, **kwargs)


class DataResource(BaseResource):
    """
    Resource for data processing and management.
    
    Provides specialized functionality for data resources
    including validation, transformation, and caching.
    """
    
    def __init__(self, name: str, data_schema: Dict[str, Any] = None):
        super().__init__(name, ResourceType.DATA)
        self.data_schema = data_schema or {}
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate data against schema.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is valid
        """
        if not self.data_schema:
            return True
        
        # Simple validation implementation
        required_fields = self.data_schema.get('required', [])
        
        for field in required_fields:
            if field not in data or data[field] is None:
                return False
        
        return True
    
    def transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data according to rules.
        
        Args:
            data: Data to transform
            
        Returns:
            Transformed data
        """
        # Simple transformation implementation
        transformed = data.copy()
        
        # Add timestamp
        transformed['processed_at'] = timezone.now().isoformat()
        
        # Add resource name
        transformed['resource'] = self.name
        
        return transformed
    
    def process_data(self, data: Dict[str, Any], cache_key: str = None):
        """
        Process and cache data.
        
        Args:
            data: Data to process
            cache_key: Cache key for processed data
            
        Returns:
            Processed data
        """
        # Validate data
        if not self.validate_data(data):
            raise ValueError("Data validation failed")
        
        # Transform data
        processed_data = self.transform_data(data)
        
        # Cache processed data
        if cache_key:
            self.set_cache(cache_key, processed_data)
        
        return processed_data
    
    def get_processed_data(self, cache_key: str):
        """
        Get processed data from cache.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Processed data or None
        """
        return self.get_from_cache(cache_key)


class FileResource(BaseResource):
    """
    Resource for file management.
    
    Provides specialized functionality for file resources
    including upload, download, and storage management.
    """
    
    def __init__(self, name: str, storage_path: str = None):
        super().__init__(name, ResourceType.FILE)
        self.storage_path = storage_path or f"uploads/{name}/"
    
    def upload_file(self, file_obj, filename: str = None, user: User = None):
        """
        Upload file to storage.
        
        Args:
            file_obj: File object
            filename: Filename
            user: User uploading file
            
        Returns:
            File information
        """
        if not self.validate_access(user, action='upload'):
            raise PermissionError("Access denied")
        
        # Generate filename if not provided
        if not filename:
            filename = file_obj.name
        
        # Add timestamp to filename
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        
        # Store file
        file_path = f"{self.storage_path}{filename}"
        
        # This would integrate with Django's file storage system
        # For now, return file information
        return {
            'filename': filename,
            'file_path': file_path,
            'size': file_obj.size,
            'content_type': file_obj.content_type,
            'uploaded_at': timezone.now().isoformat(),
        }
    
    def download_file(self, filename: str, user: User = None):
        """
        Download file from storage.
        
        Args:
            filename: Filename
            user: User downloading file
            
        Returns:
            File response
        """
        if not self.validate_access(user, action='download'):
            raise PermissionError("Access denied")
        
        file_path = f"{self.storage_path}{filename}"
        
        # This would integrate with Django's file storage system
        # For now, return file information
        return {
            'filename': filename,
            'file_path': file_path,
            'downloaded_at': timezone.now().isoformat(),
        }


class ResourceManager:
    """
    Manager for all resources.
    
    Provides centralized resource management including
    registration, discovery, and lifecycle management.
    """
    
    def __init__(self):
        self.resources: Dict[str, BaseResource] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_default_resources()
    
    def _setup_default_resources(self):
        """Setup default resources."""
        # Model resources
        self.register_model_resource('postback_logs', PostbackLog, PostbackLogSerializer)
        self.register_model_resource('postback_insights', PostbackInsight, PostbackInsightSerializer)
        self.register_model_resource('network_configs', NetworkPostbackConfig, NetworkPostbackConfigSerializer)
        
        # Data resources
        self.register_data_resource('analytics_data', {
            'required': ['network_key', 'date'],
        })
        
        # File resources
        self.register_file_resource('postback_attachments')
    
    def register_model_resource(self, name: str, model_class: Type, serializer_class: Type = None):
        """
        Register model resource.
        
        Args:
            name: Resource name
            model_class: Model class
            serializer_class: Serializer class
        """
        resource = ModelResource(name, model_class, serializer_class)
        self.resources[name] = resource
        self.logger.info(f"Registered model resource: {name}")
    
    def register_api_resource(self, name: str, serializer_class: Type = None):
        """
        Register API resource.
        
        Args:
            name: Resource name
            serializer_class: Serializer class
        """
        resource = APIResource(name, serializer_class)
        self.resources[name] = resource
        self.logger.info(f"Registered API resource: {name}")
    
    def register_data_resource(self, name: str, data_schema: Dict[str, Any] = None):
        """
        Register data resource.
        
        Args:
            name: Resource name
            data_schema: Data validation schema
        """
        resource = DataResource(name, data_schema)
        self.resources[name] = resource
        self.logger.info(f"Registered data resource: {name}")
    
    def register_file_resource(self, name: str, storage_path: str = None):
        """
        Register file resource.
        
        Args:
            name: Resource name
            storage_path: Storage path
        """
        resource = FileResource(name, storage_path)
        self.resources[name] = resource
        self.logger.info(f"Registered file resource: {name}")
    
    def get_resource(self, name: str) -> Optional[BaseResource]:
        """
        Get resource by name.
        
        Args:
            name: Resource name
            
        Returns:
            Resource instance or None
        """
        return self.resources.get(name)
    
    def list_resources(self, resource_type: ResourceType = None) -> List[str]:
        """
        List resources by type.
        
        Args:
            resource_type: Resource type filter
            
        Returns:
            List of resource names
        """
        if resource_type:
            return [
                name for name, resource in self.resources.items()
                if resource.resource_type == resource_type
            ]
        else:
            return list(self.resources.keys())
    
    def get_resource_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get resource metadata.
        
        Args:
            name: Resource name
            
        Returns:
            Resource metadata or None
        """
        resource = self.get_resource(name)
        if resource:
            return resource.get_metadata()
        return None
    
    def validate_resource_access(self, name: str, user: User = None, **kwargs) -> bool:
        """
        Validate access to resource.
        
        Args:
            name: Resource name
            user: User
            **kwargs: Additional validation parameters
            
        Returns:
            True if access is allowed
        """
        resource = self.get_resource(name)
        if resource:
            return resource.validate_access(user, **kwargs)
        return False
    
    def clear_resource_cache(self, name: str):
        """
        Clear cache for resource.
        
        Args:
            name: Resource name
        """
        resource = self.get_resource(name)
        if resource and isinstance(resource, ModelResource):
            # Clear model resource cache
            cache_pattern = f"{resource.resource_type.value}:{resource.name}:*"
            # This would require cache implementation that supports pattern deletion
            pass
    
    def get_resource_statistics(self) -> Dict[str, Any]:
        """
        Get resource statistics.
        
        Returns:
            Resource statistics
        """
        stats = {
            'total_resources': len(self.resources),
            'resource_types': {},
            'resource_status': {},
        }
        
        for resource in self.resources.values():
            # Count by type
            resource_type = resource.resource_type.value
            stats['resource_types'][resource_type] = stats['resource_types'].get(resource_type, 0) + 1
            
            # Count by status
            status = resource.status.value
            stats['resource_status'][status] = stats['resource_status'].get(status, 0) + 1
        
        return stats


# Global resource manager instance
resource_manager = ResourceManager()


# Convenience functions
def get_postback_logs_resource() -> ModelResource:
    """Get postback logs resource."""
    return resource_manager.get_resource('postback_logs')


def get_postback_insights_resource() -> ModelResource:
    """Get postback insights resource."""
    return resource_manager.get_resource('postback_insights')


def get_network_configs_resource() -> ModelResource:
    """Get network configs resource."""
    return resource_manager.get_resource('network_configs')


def get_analytics_data_resource() -> DataResource:
    """Get analytics data resource."""
    return resource_manager.get_resource('analytics_data')


def get_postback_attachments_resource() -> FileResource:
    """Get postback attachments resource."""
    return resource_manager.get_resource('postback_attachments')


# Resource decorators
def resource_access_required(resource_name: str):
    """
    Decorator for requiring resource access.
    
    Args:
        resource_name: Resource name
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if not resource_manager.validate_resource_access(resource_name, request.user):
                from rest_framework.response import Response
                return Response(
                    {'error': 'Access denied'},
                    status=403
                )
            
            return func(request, *args, **kwargs)
        
        return wrapper


def cache_resource_result(cache_key_pattern: str, timeout: int = 300):
    """
    Decorator for caching resource results.
    
    Args:
        cache_key_pattern: Cache key pattern
        timeout: Cache timeout
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            cache_key = cache_key_pattern.format(**kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = func(request, *args, **kwargs)
            
            # Cache result
            if hasattr(result, 'data'):
                cache.set(cache_key, result.data, timeout)
            else:
                cache.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


# Resource utilities
def list_available_resources() -> List[str]:
    """List all available resources."""
    return resource_manager.list_resources()


def get_resource_info(resource_name: str) -> Dict[str, Any]:
    """Get resource information."""
    metadata = resource_manager.get_resource_metadata(resource_name)
    if metadata:
        return metadata
    else:
        return {'error': f'Resource {resource_name} not found'}


def validate_resource_permissions(resource_name: str, user: User = None, **kwargs) -> bool:
    """Validate resource permissions."""
    return resource_manager.validate_resource_access(resource_name, user, **kwargs)


# Resource initialization
def initialize_resources():
    """Initialize resource system."""
    try:
        logger.info("Resource system initialized")
        
        # Additional resource initialization can be added here
        
    except Exception as e:
        logger.error(f"Error initializing resources: {str(e)}")


# Resource health check
def check_resource_health() -> Dict[str, Any]:
    """Check health of all resources."""
    health_status = {
        'overall': 'healthy',
        'resources': {},
        'issues': [],
    }
    
    for name, resource in resource_manager.resources.items():
        try:
            # Basic health check
            resource_health = {
                'name': name,
                'type': resource.resource_type.value,
                'status': resource.status.value,
                'healthy': resource.status == ResourceStatus.ACTIVE,
            }
            
            health_status['resources'][name] = resource_health
            
            if not resource_health['healthy']:
                health_status['issues'].append(f"Resource {name} is {resource_health['status']}")
        
        except Exception as e:
            health_status['resources'][name] = {
                'name': name,
                'status': 'error',
                'healthy': False,
                'error': str(e),
            }
            health_status['issues'].append(f"Resource {name} has error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
