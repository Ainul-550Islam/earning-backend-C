# api/rate_limit/pagination.py
"""
Pagination classes for rate limit module.

Provides custom pagination for rate limiting APIs.
"""

import logging
from typing import Dict, Any, Optional, List
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

logger = logging.getLogger(__name__)


class RateLimitPagination(PageNumberPagination):
    """
    Custom pagination for rate limit endpoints.
    """
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data) -> Response:
        """
        Return paginated response with rate limit metadata.
        
        Args:
            data: Paginated data
            
        Returns:
            Response with pagination metadata
        """
        return Response({
            'success': True,
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page': self.page.number,
            'page_size': self.page_size,
            'total_pages': self.page.paginator.num_pages,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'results': data
        })
    
    def get_page_size(self, request):
        """
        Get page size from request with validation.
        
        Args:
            request: HTTP request
            
        Returns:
            Page size
        """
        page_size = super().get_page_size(request)
        
        # Validate page size
        if page_size > self.max_page_size:
            page_size = self.max_page_size
        
        return page_size


class RateLimitCursorPagination(LimitOffsetPagination):
    """
    Cursor-based pagination for rate limit endpoints.
    """
    
    default_limit = 20
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100
    
    def get_paginated_response(self, data) -> Response:
        """
        Return cursor-based paginated response.
        
        Args:
            data: Paginated data
            
        Returns:
            Response with cursor pagination metadata
        """
        return Response({
            'success': True,
            'count': self.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'limit': self.limit,
            'offset': self.offset,
            'results': data
        })


class RateLimitAnalyticsPagination(PageNumberPagination):
    """
    Pagination optimized for rate limit analytics.
    """
    
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    
    def get_paginated_response(self, data) -> Response:
        """
        Return paginated response with analytics metadata.
        
        Args:
            data: Paginated data
            
        Returns:
            Response with analytics pagination metadata
        """
        # Calculate additional analytics metadata
        paginator = self.page.paginator
        
        response_data = {
            'success': True,
            'count': paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page': self.page.number,
            'page_size': self.page_size,
            'total_pages': paginator.num_pages,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'results': data,
            'analytics': {
                'items_per_page': self.page_size,
                'current_page_items': len(data),
                'total_items': paginator.count,
                'pages_remaining': paginator.num_pages - self.page.number,
                'progress_percentage': (self.page.number / paginator.num_pages) * 100 if paginator.num_pages > 0 else 0
            }
        }
        
        return Response(response_data)


class TimeSeriesPagination:
    """
    Pagination for time-series data.
    """
    
    def __init__(self, time_field: str = 'timestamp'):
        self.time_field = time_field
        self.default_window = 'hour'
        self.supported_windows = ['minute', 'hour', 'day', 'week', 'month']
    
    def paginate_queryset(self, queryset, window: str = None, limit: int = 1000):
        """
        Paginate time-series data by time windows.
        
        Args:
            queryset: QuerySet to paginate
            window: Time window (minute, hour, day, week, month)
            limit: Maximum number of records per window
            
        Returns:
            Paginated queryset
        """
        if window not in self.supported_windows:
            window = self.default_window
        
        # Truncate timestamp to the specified window
        from django.db.models.functions import Trunc
        
        trunc_mapping = {
            'minute': Trunc(self.time_field, 'minute'),
            'hour': Trunc(self.time_field, 'hour'),
            'day': Trunc(self.time_field, 'day'),
            'week': Trunc(self.time_field, 'week'),
            'month': Trunc(self.time_field, 'month')
        }
        
        truncated_queryset = queryset.annotate(
            time_window=trunc_mapping[window]
        )
        
        # Limit records per window
        if limit:
            truncated_queryset = truncated_queryset[:limit]
        
        return truncated_queryset
    
    def get_paginated_response(self, data, window: str, total_count: int) -> Response:
        """
        Return paginated time-series response.
        
        Args:
            data: Paginated data
            window: Time window used
            total_count: Total number of records
            
        Returns:
            Response with time-series pagination metadata
        """
        return Response({
            'success': True,
            'time_window': window,
            'total_count': total_count,
            'returned_count': len(data),
            'results': data
        })


class InfiniteScrollPagination(PageNumberPagination):
    """
    Pagination optimized for infinite scroll interfaces.
    """
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50
    
    def get_paginated_response(self, data) -> Response:
        """
        Return response optimized for infinite scroll.
        
        Args:
            data: Paginated data
            
        Returns:
            Response with infinite scroll metadata
        """
        has_more = self.page.has_next()
        
        return Response({
            'success': True,
            'results': data,
            'has_more': has_more,
            'next_page': self.page.number + 1 if has_more else None,
            'page_size': self.page_size,
            'total_count': self.page.paginator.count
        })
    
    def get_next_link(self):
        """
        Override to return None for infinite scroll (has_more indicates if more data exists).
        
        Returns:
            None
        """
        return None


class RateLimitLogPagination(PageNumberPagination):
    """
    Pagination specifically for rate limit logs with filtering support.
    """
    
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    
    def get_paginated_response_schema(self, schema):
        """
        Get OpenAPI schema for rate limit log pagination.
        
        Args:
            schema: Response schema
            
        Returns:
            Enhanced schema
        """
        return {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean', 'example': True},
                'count': {'type': 'integer', 'example': 1000},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'page': {'type': 'integer', 'example': 1},
                'page_size': {'type': 'integer', 'example': 50},
                'total_pages': {'type': 'integer', 'example': 20},
                'has_next': {'type': 'boolean', 'example': True},
                'has_previous': {'type': 'boolean', 'example': False},
                'results': schema,
                'filters': {
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string', 'enum': ['allowed', 'blocked', 'throttled']},
                        'user_id': {'type': 'integer'},
                        'ip_address': {'type': 'string'},
                        'endpoint': {'type': 'string'},
                        'date_from': {'type': 'string', 'format': 'date'},
                        'date_to': {'type': 'string', 'format': 'date'}
                    }
                }
            }
        }


class BulkOperationPagination:
    """
    Pagination for bulk operations.
    """
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
    
    def paginate_queryset(self, queryset):
        """
        Paginate queryset for bulk operations.
        
        Args:
            queryset: QuerySet to paginate
            
        Returns:
            Generator yielding batches
        """
        total_count = queryset.count()
        offset = 0
        
        while offset < total_count:
            batch = queryset[offset:offset + self.batch_size]
            yield batch, offset, total_count
            offset += self.batch_size
    
    def get_batch_info(self, current_offset: int, total_count: int) -> Dict[str, Any]:
        """
        Get batch information.
        
        Args:
            current_offset: Current offset
            total_count: Total count
            
        Returns:
            Batch information
        """
        current_batch = (current_offset // self.batch_size) + 1
        total_batches = (total_count + self.batch_size - 1) // self.batch_size
        progress = (current_offset / total_count * 100) if total_count > 0 else 0
        
        return {
            'current_batch': current_batch,
            'total_batches': total_batches,
            'batch_size': self.batch_size,
            'processed': current_offset,
            'total': total_count,
            'progress_percentage': progress,
            'remaining': total_count - current_offset
        }


class SearchResultsPagination(PageNumberPagination):
    """
    Pagination for search results with relevance scoring.
    """
    
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data) -> Response:
        """
        Return paginated search response.
        
        Args:
            data: Paginated search results
            
        Returns:
            Response with search metadata
        """
        return Response({
            'success': True,
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page': self.page.number,
            'page_size': self.page_size,
            'total_pages': self.page.paginator.num_pages,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'results': data,
            'search_info': {
                'results_per_page': self.page_size,
                'current_page_results': len(data),
                'total_results': self.page.paginator.count,
                'showing_from': ((self.page.number - 1) * self.page_size) + 1,
                'showing_to': min(self.page.number * self.page_size, self.page.paginator.count)
            }
        })


class ExportPagination:
    """
    Pagination for data export operations.
    """
    
    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size
    
    def paginate_for_export(self, queryset):
        """
        Paginate queryset for export operations.
        
        Args:
            queryset: QuerySet to paginate
            
        Returns:
            Generator yielding chunks
        """
        total_count = queryset.count()
        offset = 0
        
        while offset < total_count:
            chunk = queryset[offset:offset + self.chunk_size]
            yield chunk, offset, total_count
            offset += self.chunk_size
    
    def get_export_progress(self, current_offset: int, total_count: int) -> Dict[str, Any]:
        """
        Get export progress information.
        
        Args:
            current_offset: Current offset
            total_count: Total count
            
        Returns:
            Export progress information
        """
        progress = (current_offset / total_count * 100) if total_count > 0 else 0
        processed = min(current_offset, total_count)
        
        return {
            'processed': processed,
            'total': total_count,
            'progress_percentage': progress,
            'remaining': total_count - processed,
            'completed': progress >= 100
        }


# Export pagination classes
__all__ = [
    'RateLimitPagination',
    'RateLimitCursorPagination',
    'RateLimitAnalyticsPagination',
    'TimeSeriesPagination',
    'InfiniteScrollPagination',
    'RateLimitLogPagination',
    'BulkOperationPagination',
    'SearchResultsPagination',
    'ExportPagination'
]
