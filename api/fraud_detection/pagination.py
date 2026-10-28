# =============================================================================
# fraud_detection/pagination.py
# =============================================================================
"""
Custom Pagination Classes for Fraud Detection System.

Provides specialized pagination classes for fraud detection APIs
with enhanced features and performance optimizations.
"""

from __future__ import annotations
from django.db import models

import logging
from typing import Any, Dict, List, Optional, Union

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.conf import settings
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from rest_framework.pagination import CursorPagination

from api.fraud_detection.exceptions import PaginationError


logger = logging.getLogger(__name__)


class FraudDetectionPagination(pagination.PageNumberPagination):
    """Custom pagination for fraud detection with enhanced features."""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    # Cache settings
    cache_enabled = True
    cache_timeout = 300  # 5 minutes
    
    # Additional metadata
    include_total_count = True
    include_page_size_info = True
    include_filter_info = True
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return paginated response with enhanced metadata."""
        if self.page is None:
            return Response({'detail': 'Invalid page.'}, status=400)
        
        # Build response data
        response_data = {
            'results': data,
            'pagination': self.get_pagination_metadata()
        }
        
        # Add additional metadata
        if self.include_filter_info:
            response_data['filters'] = self.get_filter_info()
        
        if self.include_page_size_info:
            response_data['page_size_info'] = self.get_page_size_info()
        
        # Add performance metadata
        response_data['performance'] = self.get_performance_metadata()
        
        return Response(response_data)
    
    def get_pagination_metadata(self) -> Dict[str, Any]:
        """Get pagination metadata."""
        if not self.page:
            return {}
        
        return {
            'page_number': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'total_items': self.page.paginator.count,
            'items_per_page': self.get_page_size(self.request),
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'next_page': self.get_next_link(),
            'previous_page': self.get_previous_link(),
            'first_page': self.get_first_link(),
            'last_page': self.get_last_link(),
            'current_page': self.get_current_link()
        }
    
    def get_filter_info(self) -> Dict[str, Any]:
        """Get filter information from request."""
        filter_info = {}
        
        # Extract common filter parameters
        filter_params = [
            'status', 'severity', 'user_id', 'case_type', 'alert_type',
            'risk_level', 'created_after', 'created_before', 'search'
        ]
        
        for param in filter_params:
            value = self.request.query_params.get(param)
            if value:
                filter_info[param] = value
        
        return filter_info
    
    def get_page_size_info(self) -> Dict[str, Any]:
        """Get page size information."""
        current_size = self.get_page_size(self.request)
        
        return {
            'current_size': current_size,
            'default_size': self.page_size,
            'max_size': self.max_page_size,
            'available_sizes': [10, 20, 50, 100],
            'can_increase': current_size < self.max_page_size,
            'can_decrease': current_size > 1
        }
    
    def get_performance_metadata(self) -> Dict[str, Any]:
        """Get performance metadata."""
        return {
            'cached': self._is_cached_response(),
            'cache_timeout': self.cache_timeout if self.cache_enabled else None,
            'query_time': getattr(self.request, '_query_time', None)
        }
    
    def get_first_link(self) -> Optional[str]:
        """Get link to first page."""
        if not self.page:
            return None
        url = self.request.build_absolute_uri()
        return replace_query_param(url, self.page_query_param, 1)
    
    def get_last_link(self) -> Optional[str]:
        """Get link to last page."""
        if not self.page:
            return None
        url = self.request.build_absolute_uri()
        return replace_query_param(url, self.page_query_param, self.page.paginator.num_pages)
    
    def get_current_link(self) -> Optional[str]:
        """Get link to current page."""
        if not self.page:
            return None
        return self.request.build_absolute_uri()
    
    def paginate_queryset(self, queryset, request, view=None):
        """Paginate queryset with caching support."""
        self.request = request
        self.view = view
        
        # Check cache first
        if self.cache_enabled:
            cache_key = self._get_cache_key(request, queryset)
            cached_result = cache.get(cache_key)
            if cached_result:
                request._cached_pagination = True
                return cached_result
        
        # Standard pagination
        try:
            page_size = self.get_page_size(request)
            paginator = Paginator(queryset, page_size)
            page_number = request.query_params.get(self.page_query_param, 1)
            
            try:
                page = paginator.page(page_number)
            except PageNotAnInteger:
                page = paginator.page(1)
            except EmptyPage:
                page = paginator.page(paginator.num_pages)
            
            self.page = page
            
            # Cache result
            if self.cache_enabled:
                cache.set(cache_key, list(page), self.cache_timeout)
            
            return list(page)
            
        except Exception as e:
            logger.error(f"Pagination error: {e}")
            raise PaginationError(f"Pagination failed: {e}")
    
    def _get_cache_key(self, request, queryset) -> str:
        """Generate cache key for pagination."""
        from django.contrib.auth.hash_functions import md5
        
        # Build cache key components
        components = [
            str(queryset.query),
            str(self.get_page_size(request)),
            request.query_params.get(self.page_query_param, '1'),
            str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
        ]
        
        cache_string = '|'.join(components)
        return f"fraud_pagination:{md5(cache_string.encode()).hexdigest()}"
    
    def _is_cached_response(self) -> bool:
        """Check if response is from cache."""
        return getattr(self.request, '_cached_pagination', False)


class FraudCasePagination(FraudDetectionPagination):
    """Specialized pagination for fraud cases."""
    
    page_size = 15
    max_page_size = 50
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Add case-specific metadata."""
        response = super().get_paginated_response(data)
        
        # Add case statistics
        if hasattr(self.view, 'get_queryset'):
            try:
                queryset = self.view.get_queryset()
                case_stats = self._get_case_statistics(queryset)
                response.data['case_statistics'] = case_stats
            except Exception as e:
                logger.error(f"Error getting case statistics: {e}")
        
        return response
    
    def _get_case_statistics(self, queryset) -> Dict[str, Any]:
        """Get case statistics for current filter."""
        from django.db.models import Count, Sum, Avg
        
        stats = queryset.aggregate(
            total_count=Count('id'),
            avg_risk_score=Avg('risk_score'),
            total_financial_loss=Sum('financial_impact'),
            high_risk_count=Count('id', filter=models.Q(risk_score__gte=70))
        )
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(count=Count('id'))
        
        return {
            'total_count': stats['total_count'],
            'average_risk_score': stats['avg_risk_score'] or 0,
            'total_financial_loss': stats['total_financial_loss'] or 0,
            'high_risk_count': stats['high_risk_count'],
            'status_breakdown': list(status_breakdown)
        }


class FraudAlertPagination(FraudDetectionPagination):
    """Specialized pagination for fraud alerts."""
    
    page_size = 25
    max_page_size = 100
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Add alert-specific metadata."""
        response = super().get_paginated_response(data)
        
        # Add alert statistics
        if hasattr(self.view, 'get_queryset'):
            try:
                queryset = self.view.get_queryset()
                alert_stats = self._get_alert_statistics(queryset)
                response.data['alert_statistics'] = alert_stats
            except Exception as e:
                logger.error(f"Error getting alert statistics: {e}")
        
        return response
    
    def _get_alert_statistics(self, queryset) -> Dict[str, Any]:
        """Get alert statistics for current filter."""
        from django.db.models import Count, Avg
        
        stats = queryset.aggregate(
            total_count=Count('id'),
            avg_severity_score=Avg('severity_score'),
            unacknowledged_count=Count('id', filter=models.Q(acknowledged=False)),
            high_priority_count=Count('id', filter=models.Q(severity_score__gte=70))
        )
        
        # Type breakdown
        type_breakdown = queryset.values('alert_type').annotate(count=Count('id'))
        
        return {
            'total_count': stats['total_count'],
            'average_severity_score': stats['avg_severity_score'] or 0,
            'unacknowledged_count': stats['unacknowledged_count'],
            'high_priority_count': stats['high_priority_count'],
            'type_breakdown': list(type_breakdown)
        }


class CursorBasedPagination(CursorPagination):
    """Cursor-based pagination for large datasets."""
    
    page_size = 20
    max_page_size = 100
    cursor_query_param = 'cursor'
    ordering = '-created_at'  # Default ordering
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return cursor-based paginated response."""
        response_data = {
            'results': data,
            'pagination': {
                'has_next': self.has_next,
                'has_previous': self.has_previous,
                'next_cursor': self.get_next_cursor(),
                'previous_cursor': self.get_previous_cursor(),
                'page_size': self.page_size
            }
        }
        
        # Add ordering info
        response_data['pagination']['ordering'] = self.ordering
        
        return Response(response_data)
    
    def get_next_cursor(self) -> Optional[str]:
        """Get next cursor."""
        if not self.has_next:
            return None
        
        if self.page and len(self.page) > 0:
            last_item = self.page[-1]
            return self.encode_cursor(last_item)
        
        return None
    
    def get_previous_cursor(self) -> Optional[str]:
        """Get previous cursor."""
        if not self.has_previous:
            return None
        
        if self.page and len(self.page) > 0:
            first_item = self.page[0]
            return self.encode_cursor(first_item)
        
        return None


class FraudDetectionCursorPagination(CursorBasedPagination):
    """Enhanced cursor pagination for fraud detection."""
    
    def encode_cursor(self, item):
        """Encode cursor from item."""
        from rest_framework.pagination import _positive_int
        
        # Use timestamp as cursor
        if hasattr(item, 'created_at'):
            offset = _positive_int(item.created_at.timestamp() * 1000)
            return str(offset)
        
        # Fallback to ID
        if hasattr(item, 'pk'):
            return str(item.pk)
        
        return super().encode_cursor(item)
    
    def decode_cursor(self, cursor):
        """Decode cursor to item."""
        try:
            offset = int(cursor)
            timestamp = offset / 1000.0
            
            from datetime import datetime
            cursor_datetime = datetime.fromtimestamp(timestamp)
            
            return {'created_at__lt': cursor_datetime}
            
        except (ValueError, TypeError):
            return super().decode_cursor(cursor)


class InfiniteScrollPagination(FraudDetectionPagination):
    """Pagination optimized for infinite scroll interfaces."""
    
    page_size = 20
    max_page_size = 50
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return infinite scroll optimized response."""
        if not self.page:
            return Response({'detail': 'Invalid page.'}, status=400)
        
        response_data = {
            'results': data,
            'has_more': self.page.has_next(),
            'next_page': self.page.next_page_number() if self.page.has_next() else None,
            'current_page': self.page.number,
            'total_items': self.page.paginator.count
        }
        
        return Response(response_data)


class AnalyticsPagination(FraudDetectionPagination):
    """Pagination optimized for analytics endpoints."""
    
    page_size = 50
    max_page_size = 200
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return analytics-focused pagination response."""
        response = super().get_paginated_response(data)
        
        # Add analytics metadata
        if hasattr(self.view, 'get_analytics_metadata'):
            try:
                analytics_metadata = self.view.get_analytics_metadata()
                response.data['analytics'] = analytics_metadata
            except Exception as e:
                logger.error(f"Error getting analytics metadata: {e}")
        
        return response


class ExportPagination(FraudDetectionPagination):
    """Pagination for export endpoints with larger page sizes."""
    
    page_size = 100
    max_page_size = 1000
    cache_enabled = False  # Don't cache export data
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return export-focused pagination response."""
        response = super().get_paginated_response(data)
        
        # Add export metadata
        response.data['export'] = {
            'total_exportable': self.page.paginator.count,
            'current_batch_size': len(data),
            'batches_needed': (self.page.paginator.count + self.page_size - 1) // self.page_size,
            'current_batch': self.page.number
        }
        
        return response


class SearchPagination(FraudDetectionPagination):
    """Pagination optimized for search endpoints."""
    
    page_size = 25
    max_page_size = 100
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return search-focused pagination response."""
        response = super().get_paginated_response(data)
        
        # Add search metadata
        search_info = {
            'search_query': self.request.query_params.get('search', ''),
            'search_fields': self._get_search_fields(),
            'total_matches': self.page.paginator.count if self.page else 0
        }
        
        response.data['search'] = search_info
        
        return response
    
    def _get_search_fields(self) -> List[str]:
        """Get search fields from view."""
        if hasattr(self.view, 'search_fields'):
            return list(self.view.search_fields)
        
        # Default search fields
        return ['title', 'description', 'user__username']


class TimeSeriesPagination(FraudDetectionPagination):
    """Pagination for time-series data."""
    
    page_size = 100
    max_page_size = 500
    ordering = 'timestamp'
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return time-series pagination response."""
        response = super().get_paginated_response(data)
        
        # Add time-series metadata
        if data:
            timestamps = [item.get('timestamp') for item in data if hasattr(item, 'timestamp')]
            if timestamps:
                response.data['time_series'] = {
                    'start_time': min(timestamps),
                    'end_time': max(timestamps),
                    'data_points': len(timestamps),
                    'interval': self._calculate_interval(timestamps)
                }
        
        return response
    
    def _calculate_interval(self, timestamps: List) -> str:
        """Calculate time interval between data points."""
        if len(timestamps) < 2:
            return 'unknown'
        
        # Calculate average interval
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)
        
        avg_interval = sum(intervals) / len(intervals)
        
        if avg_interval < 3600:  # Less than 1 hour
            return 'minutes'
        elif avg_interval < 86400:  # Less than 1 day
            return 'hours'
        else:
            return 'days'


# Pagination factory
class PaginationFactory:
    """Factory for creating pagination classes."""
    
    pagination_classes = {
        'default': FraudDetectionPagination,
        'cases': FraudCasePagination,
        'alerts': FraudAlertPagination,
        'cursor': FraudDetectionCursorPagination,
        'infinite_scroll': InfiniteScrollPagination,
        'analytics': AnalyticsPagination,
        'export': ExportPagination,
        'search': SearchPagination,
        'time_series': TimeSeriesPagination
    }
    
    @classmethod
    def get_pagination_class(cls, pagination_type: str) -> type:
        """Get pagination class by type."""
        return cls.pagination_classes.get(pagination_type, cls.pagination_classes['default'])
    
    @classmethod
    def register_pagination_class(cls, name: str, pagination_class: type):
        """Register a custom pagination class."""
        cls.pagination_classes[name] = pagination_class
        logger.info(f"Registered pagination class: {name}")
    
    @classmethod
    def create_pagination(cls, pagination_type: str, **kwargs) -> pagination.PageNumberPagination:
        """Create pagination instance."""
        pagination_class = cls.get_pagination_class(pagination_type)
        return pagination_class(**kwargs)


# Pagination utilities
def get_pagination_config(pagination_type: str = 'default') -> Dict[str, Any]:
    """Get pagination configuration."""
    pagination_class = PaginationFactory.get_pagination_class(pagination_type)
    
    return {
        'class': pagination_class,
        'page_size': getattr(pagination_class, 'page_size', 20),
        'max_page_size': getattr(pagination_class, 'max_page_size', 100),
        'page_query_param': getattr(pagination_class, 'page_query_param', 'page'),
        'page_size_query_param': getattr(pagination_class, 'page_size_query_param', 'page_size')
    }


def configure_pagination(viewset, pagination_type: str = 'default'):
    """Configure pagination for a viewset."""
    pagination_config = get_pagination_config(pagination_type)
    viewset.pagination_class = pagination_config['class']
    
    # Set pagination attributes
    for attr, value in pagination_config.items():
        if attr != 'class' and hasattr(viewset.pagination_class, attr):
            setattr(viewset.pagination_class, attr, value)


# Export all pagination classes
__all__ = [
    # Base pagination
    'FraudDetectionPagination',
    
    # Specialized pagination
    'FraudCasePagination',
    'FraudAlertPagination',
    'CursorBasedPagination',
    'FraudDetectionCursorPagination',
    'InfiniteScrollPagination',
    'AnalyticsPagination',
    'ExportPagination',
    'SearchPagination',
    'TimeSeriesPagination',
    
    # Factory and utilities
    'PaginationFactory',
    'get_pagination_config',
    'configure_pagination',
]


# =============================================================================
# DRY RE-EXPORT — utils/pagination.py utility function
# Import paginate_qs from here instead of utils/pagination directly.
# =============================================================================
from api.fraud_detection.utils.pagination import paginate_qs  # noqa: F401


# ── Backwards-compat shim: utils/pagination.py now re-exports from here ───────
# (any existing imports from utils.pagination still work)
