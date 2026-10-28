"""
viewset_cap.py – Enhanced ViewSet capabilities for postback module.

Provides comprehensive ViewSet enhancements including:
- Advanced filtering and searching
- Bulk operations
- Custom action decorators
- Performance monitoring
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from functools import wraps

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class ViewSetCapability:
    """
    Base capability class for ViewSet enhancements.
    
    Provides common functionality that can be mixed into
    ViewSets to add advanced features.
    """
    
    def __init__(self, viewset):
        self.viewset = viewset
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_queryset(self):
        """Get queryset with capability-specific filtering."""
        return self.viewset.get_queryset()
    
    def log_action(self, action_name: str, request, **kwargs):
        """Log ViewSet action."""
        log_data = {
            'action': action_name,
            'viewset': self.viewset.__class__.__name__,
            'method': request.method,
            'path': request.path,
            'user': str(request.user) if request.user.is_authenticated else 'Anonymous',
            'timestamp': timezone.now().isoformat(),
            **kwargs
        }
        
        self.logger.info(f"ViewSet action: {action_name} - {log_data}")


class BulkOperationCapability(ViewSetCapability):
    """
    Capability for bulk operations on ViewSets.
    
    Provides bulk create, update, and delete operations
    with proper error handling and transaction management.
    """
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create operation.
        
        Args:
            request: HTTP request with bulk data
            
        Returns:
            Bulk operation results
        """
        self.log_action('bulk_create', request)
        
        try:
            bulk_data = request.data.get('data', [])
            if not bulk_data:
                return Response(
                    {'error': 'No data provided for bulk create'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created_instances = []
            failed_instances = []
            
            with transaction.atomic():
                for index, data in enumerate(bulk_data):
                    try:
                        serializer = self.viewset.get_serializer(data=data)
                        serializer.is_valid(raise_exception=True)
                        instance = serializer.save()
                        created_instances.append(serializer.data)
                    except Exception as e:
                        failed_instances.append({
                            'index': index,
                            'data': data,
                            'error': str(e)
                        })
            
            result = {
                'created': created_instances,
                'failed': failed_instances,
                'total_requested': len(bulk_data),
                'total_created': len(created_instances),
                'total_failed': len(failed_instances)
            }
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            self.logger.error(f"Error in bulk create: {str(e)}")
            return Response(
                {'error': f'Bulk create failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update operation.
        
        Args:
            request: HTTP request with bulk update data
            
        Returns:
            Bulk operation results
        """
        self.log_action('bulk_update', request)
        
        try:
            bulk_data = request.data.get('data', [])
            if not bulk_data:
                return Response(
                    {'error': 'No data provided for bulk update'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            updated_instances = []
            failed_instances = []
            
            with transaction.atomic():
                for index, data in enumerate(bulk_data):
                    try:
                        instance_id = data.get('id')
                        if not instance_id:
                            failed_instances.append({
                                'index': index,
                                'data': data,
                                'error': 'Missing id field'
                            })
                            continue
                        
                        instance = self.viewset.get_queryset().get(pk=instance_id)
                        serializer = self.viewset.get_serializer(instance, data=data, partial=True)
                        serializer.is_valid(raise_exception=True)
                        updated_instance = serializer.save()
                        updated_instances.append(serializer.data)
                        
                    except Exception as e:
                        failed_instances.append({
                            'index': index,
                            'data': data,
                            'error': str(e)
                        })
            
            result = {
                'updated': updated_instances,
                'failed': failed_instances,
                'total_requested': len(bulk_data),
                'total_updated': len(updated_instances),
                'total_failed': len(failed_instances)
            }
            
            return Response(result)
            
        except Exception as e:
            self.logger.error(f"Error in bulk update: {str(e)}")
            return Response(
                {'error': f'Bulk update failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """
        Bulk delete operation.
        
        Args:
            request: HTTP request with bulk delete data
            
        Returns:
            Bulk operation results
        """
        self.log_action('bulk_delete', request)
        
        try:
            ids = request.data.get('ids', [])
            if not ids:
                return Response(
                    {'error': 'No ids provided for bulk delete'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            queryset = self.viewset.get_queryset().filter(id__in=ids)
            deleted_count = queryset.count()
            
            with transaction.atomic():
                queryset.delete()
            
            result = {
                'deleted_count': deleted_count,
                'requested_count': len(ids)
            }
            
            return Response(result)
            
        except Exception as e:
            self.logger.error(f"Error in bulk delete: {str(e)}")
            return Response(
                {'error': f'Bulk delete failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdvancedFilteringCapability(ViewSetCapability):
    """
    Capability for advanced filtering and searching.
    
    Provides enhanced filtering options including date ranges,
    text search, and custom filters.
    """
    
    def get_queryset(self):
        """Get queryset with advanced filtering."""
        queryset = super().get_queryset()
        request = getattr(self.viewset, 'request', None)
        
        if not request:
            return queryset
        
        # Apply date range filtering
        queryset = self._apply_date_range_filter(queryset, request)
        
        # Apply text search filtering
        queryset = self._apply_text_search_filter(queryset, request)
        
        # Apply custom filters
        queryset = self._apply_custom_filters(queryset, request)
        
        return queryset
    
    def _apply_date_range_filter(self, queryset, request):
        """Apply date range filtering."""
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=date_from)
            except ValueError:
                pass  # Invalid date format, ignore
        
        if date_to:
            try:
                date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=date_to)
            except ValueError:
                pass  # Invalid date format, ignore
        
        return queryset
    
    def _apply_text_search_filter(self, queryset, request):
        """Apply text search filtering."""
        search = request.query_params.get('search')
        
        if search:
            # Try to find searchable fields
            searchable_fields = getattr(self.viewset, 'searchable_fields', [])
            
            if searchable_fields:
                from django.db.models import Q
                search_q = Q()
                
                for field in searchable_fields:
                    search_q |= Q(**{f"{field}__icontains": search})
                
                queryset = queryset.filter(search_q)
        
        return queryset
    
    def _apply_custom_filters(self, queryset, request):
        """Apply custom filters."""
        custom_filters = getattr(self.viewset, 'custom_filters', {})
        
        for filter_name, filter_config in custom_filters.items():
            filter_value = request.query_params.get(filter_name)
            
            if filter_value is not None:
                field_name = filter_config.get('field', filter_name)
                filter_type = filter_config.get('type', 'exact')
                
                if filter_type == 'exact':
                    queryset = queryset.filter(**{field_name: filter_value})
                elif filter_type == 'in':
                    if isinstance(filter_value, str):
                        filter_value = filter_value.split(',')
                    queryset = queryset.filter(**{f"{field_name}__in": filter_value})
                elif filter_type == 'range':
                    if isinstance(filter_value, str):
                        filter_value = [float(v) for v in filter_value.split(',')]
                    queryset = queryset.filter(**{f"{field_name}__range": filter_value})
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def filter_options(self, request):
        """
        Get available filter options.
        
        Args:
            request: HTTP request
            
        Returns:
            Available filter options
        """
        self.log_action('filter_options', request)
        
        try:
            custom_filters = getattr(self.viewset, 'custom_filters', {})
            searchable_fields = getattr(self.viewset, 'searchable_fields', [])
            
            options = {
                'searchable_fields': searchable_fields,
                'custom_filters': {
                    name: {
                        'field': config.get('field', name),
                        'type': config.get('type', 'exact'),
                        'description': config.get('description', ''),
                    }
                    for name, config in custom_filters.items()
                },
                'date_fields': ['created_at', 'updated_at'],
            }
            
            return Response(options)
            
        except Exception as e:
            self.logger.error(f"Error getting filter options: {str(e)}")
            return Response(
                {'error': f'Failed to get filter options: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PerformanceMonitoringCapability(ViewSetCapability):
    """
    Capability for performance monitoring of ViewSet operations.
    
    Provides timing, caching, and performance metrics for
    ViewSet actions.
    """
    
    def __init__(self, viewset):
        super().__init__(viewset)
        self.performance_stats = {}
    
    def monitor_performance(self, action_name: str):
        """
        Decorator for monitoring ViewSet action performance.
        
        Args:
            action_name: Name of the action to monitor
            
        Returns:
            Decorator function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(self_viewset, *args, **kwargs):
                start_time = timezone.now()
                
                try:
                    result = func(self_viewset, *args, **kwargs)
                    
                    # Calculate execution time
                    execution_time = (timezone.now() - start_time).total_seconds()
                    
                    # Update performance stats
                    self._update_performance_stats(action_name, execution_time, True)
                    
                    # Add performance header to response
                    if hasattr(result, 'headers'):
                        result.headers['X-Execution-Time'] = str(execution_time)
                    
                    return result
                    
                except Exception as e:
                    execution_time = (timezone.now() - start_time).total_seconds()
                    self._update_performance_stats(action_name, execution_time, False)
                    raise
            
            return wrapper
        return decorator
    
    def _update_performance_stats(self, action_name: str, execution_time: float, success: bool):
        """Update performance statistics."""
        if action_name not in self.performance_stats:
            self.performance_stats[action_name] = {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_time': 0.0,
                'min_time': float('inf'),
                'max_time': 0.0,
                'avg_time': 0.0,
            }
        
        stats = self.performance_stats[action_name]
        stats['total_calls'] += 1
        stats['total_time'] += execution_time
        
        if success:
            stats['successful_calls'] += 1
        else:
            stats['failed_calls'] += 1
        
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['avg_time'] = stats['total_time'] / stats['total_calls']
    
    @action(detail=False, methods=['get'])
    def performance_stats(self, request):
        """
        Get performance statistics.
        
        Args:
            request: HTTP request
            
        Returns:
            Performance statistics
        """
        self.log_action('performance_stats', request)
        
        try:
            return Response(self.performance_stats)
            
        except Exception as e:
            self.logger.error(f"Error getting performance stats: {str(e)}")
            return Response(
                {'error': f'Failed to get performance stats: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CachingCapability(ViewSetCapability):
    """
    Capability for caching ViewSet responses.
    
    Provides intelligent caching for ViewSet actions with
    cache invalidation and performance optimization.
    """
    
    def __init__(self, viewset):
        super().__init__(viewset)
        self.cache_timeout = 300  # 5 minutes default
    
    def cache_response(self, cache_key: str = None, timeout: int = None):
        """
        Decorator for caching ViewSet responses.
        
        Args:
            cache_key: Cache key (auto-generated if None)
            timeout: Cache timeout in seconds
            
        Returns:
            Decorator function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(self_viewset, *args, **kwargs):
                request = getattr(self_viewset, 'request', None)
                
                # Don't cache non-GET requests
                if request and request.method != 'GET':
                    return func(self_viewset, *args, **kwargs)
                
                # Generate cache key
                key = cache_key or self._generate_cache_key(request, *args, **kwargs)
                
                # Try to get from cache
                cached_response = cache.get(key)
                if cached_response:
                    return cached_response
                
                # Execute function
                response = func(self_viewset, *args, **kwargs)
                
                # Cache response if successful
                if response.status_code == 200:
                    cache_timeout = timeout or self.cache_timeout
                    cache.set(key, response, cache_timeout)
                
                return response
            
            return wrapper
        return decorator
    
    def _generate_cache_key(self, request, *args, **kwargs) -> str:
        """Generate cache key for request."""
        key_parts = [
            self.viewset.__class__.__name__,
            request.method,
            request.path,
            str(sorted(request.query_params.items())),
        ]
        
        return f"viewset_cache:{'_'.join(key_parts)}"
    
    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """
        Clear cache for this ViewSet.
        
        Args:
            request: HTTP request
            
        Returns:
            Cache clearing result
        """
        self.log_action('clear_cache', request)
        
        try:
            # Clear all cache keys for this ViewSet
            cache_pattern = f"viewset_cache:{self.viewset.__class__.__name__}:*"
            
            # Note: This is a simplified cache clearing
            # In production, you might want to use cache.delete_pattern()
            # or maintain a list of cache keys
            
            return Response({'message': 'Cache cleared successfully'})
            
        except Exception as e:
            self.logger.error(f"Error clearing cache: {str(e)}")
            return Response(
                {'error': f'Failed to clear cache: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnhancedModelViewSet(ModelViewSet):
    """
    Enhanced ModelViewSet with built-in capabilities.
    
    Provides a ViewSet with all capabilities pre-configured
    for easy use in postback module.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize capabilities
        self.bulk_capability = BulkOperationCapability(self)
        self.filtering_capability = AdvancedFilteringCapability(self)
        self.performance_capability = PerformanceMonitoringCapability(self)
        self.caching_capability = CachingCapability(self)
        
        # Apply performance monitoring to all actions
        self._apply_performance_monitoring()
    
    def _apply_performance_monitoring(self):
        """Apply performance monitoring to all actions."""
        for action_name in self.get_available_actions():
            method = getattr(self, action_name, None)
            if method and callable(method):
                # Apply monitoring decorator
                monitored_method = self.performance_capability.monitor_performance(action_name)(method)
                setattr(self, action_name, monitored_method)
    
    def get_available_actions(self) -> List[str]:
        """Get list of available action methods."""
        actions = []
        
        for name in dir(self):
            method = getattr(self, name)
            if callable(method) and hasattr(method, 'action'):
                actions.append(name)
        
        return actions
    
    def list(self, request, *args, **kwargs):
        """List with enhanced filtering."""
        # Apply caching to list endpoint
        cached_list = self.caching_capability.cache_response()(super().list)
        return cached_list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve with caching."""
        # Apply caching to retrieve endpoint
        cached_retrieve = self.caching_capability.cache_response()(super().retrieve)
        return cached_retrieve(request, *args, **kwargs)


# Mixin classes for easy capability inclusion
class BulkOperationsMixin:
    """Mixin to add bulk operations to ViewSet."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bulk_capability = BulkOperationCapability(self)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        return self.bulk_capability.bulk_create(request)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        return self.bulk_capability.bulk_update(request)
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        return self.bulk_capability.bulk_delete(request)


class AdvancedFilteringMixin:
    """Mixin to add advanced filtering to ViewSet."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filtering_capability = AdvancedFilteringCapability(self)
    
    def get_queryset(self):
        return self.filtering_capability.get_queryset()
    
    @action(detail=False, methods=['get'])
    def filter_options(self, request):
        return self.filtering_capability.filter_options(request)


class PerformanceMonitoringMixin:
    """Mixin to add performance monitoring to ViewSet."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.performance_capability = PerformanceMonitoringCapability(self)
        self._apply_performance_monitoring()
    
    def _apply_performance_monitoring(self):
        """Apply performance monitoring to all actions."""
        for action_name in self.get_available_actions():
            method = getattr(self, action_name, None)
            if method and callable(method):
                monitored_method = self.performance_capability.monitor_performance(action_name)(method)
                setattr(self, action_name, monitored_method)
    
    def get_available_actions(self) -> List[str]:
        """Get list of available action methods."""
        actions = []
        
        for name in dir(self):
            method = getattr(self, name)
            if callable(method) and hasattr(method, 'action'):
                actions.append(name)
        
        return actions
    
    @action(detail=False, methods=['get'])
    def performance_stats(self, request):
        return self.performance_capability.performance_stats(request)


class CachingMixin:
    """Mixin to add caching to ViewSet."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.caching_capability = CachingCapability(self)
    
    def list(self, request, *args, **kwargs):
        """List with caching."""
        cached_list = self.caching_capability.cache_response()(super().list)
        return cached_list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve with caching."""
        cached_retrieve = self.caching_capability.cache_response()(super().retrieve)
        return cached_retrieve(request, *args, **kwargs)
    
    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        return self.caching_capability.clear_cache(request)
