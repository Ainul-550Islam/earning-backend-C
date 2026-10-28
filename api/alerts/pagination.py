"""
Custom pagination classes for alerts app
"""
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination, CursorPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AlertPagination(PageNumberPagination):
    """Custom pagination for alert endpoints"""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response_schema(self, data):
        """Get pagination response schema"""
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {'type': 'array'},
                'page_info': {
                    'type': 'object',
                    'properties': {
                        'current_page': {'type': 'integer'},
                        'total_pages': {'type': 'integer'},
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return paginated response with enhanced metadata"""
        response = super().get_paginated_response(data)
        
        # Add additional pagination metadata
        response.data['page_info'] = {
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'page_size': self.get_page_size(self.request)
        }
        
        return response


class AlertCursorPagination(CursorPagination):
    """Cursor-based pagination for real-time alert feeds"""
    
    page_size = 50
    max_page_size = 200
    cursor_query_param = 'cursor'
    ordering = '-triggered_at'
    
    def get_paginated_response_schema(self, data):
        """Get cursor pagination response schema"""
        return {
            'type': 'object',
            'properties': {
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {'type': 'array'},
                'cursor_info': {
                    'type': 'object',
                    'properties': {
                        'next_cursor': {'type': 'string', 'nullable': True},
                        'previous_cursor': {'type': 'string', 'nullable': True},
                        'has_more': {'type': 'boolean'},
                        'count': {'type': 'integer'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return cursor-based paginated response"""
        response = super().get_paginated_response(data)
        
        # Add cursor metadata
        response.data['cursor_info'] = {
            'next_cursor': self.get_next_cursor(),
            'previous_cursor': self.get_previous_cursor(),
            'has_more': self.has_more,
            'count': len(data)
        }
        
        return response
    
    def get_next_cursor(self):
        """Get next cursor for pagination"""
        if not self.page.has_next():
            return None
        
        # Use the last item's ordering field
        if hasattr(self.page[-1], self.ordering.lstrip('-')):
            return str(getattr(self.page[-1], self.ordering.lstrip('-')))
        return None
    
    def get_previous_cursor(self):
        """Get previous cursor for pagination"""
        if not self.page.has_previous():
            return None
        
        # Use the first item's ordering field
        if hasattr(self.page[0], self.ordering.lstrip('-')):
            return str(getattr(self.page[0], self.ordering.lstrip('-')))
        return None


class CachedPagination(PageNumberPagination):
    """Caching pagination for frequently accessed data"""
    
    cache_timeout = 300  # 5 minutes
    cache_key_prefix = 'alerts_pagination'
    
    def get_cache_key(self, view, request):
        """Generate cache key for pagination"""
        page_size = self.get_page_size(request)
        page_number = request.query_params.get(self.page_query_param, 1)
        
        # Include relevant query parameters
        query_params = dict(request.query_params)
        query_params.pop('page', None)
        query_params.pop('page_size', None)
        
        # Create cache key
        cache_key_parts = [
            self.cache_key_prefix,
            view.__class__.__name__,
            str(page_number),
            str(page_size),
            str(sorted(query_params.items()))
        ]
        
        return ':'.join(cache_key_parts)
    
    def paginate_queryset(self, queryset, request, view=None):
        """Paginate with caching"""
        cache_key = self.get_cache_key(view, request)
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data:
            self.page = cached_data['page']
            self.request = request
            return list(cached_data['page'].object_list)
        
        # Not in cache, paginate normally
        result = super().paginate_queryset(queryset, request, view)
        
        # Cache the result
        if self.page:
            cache.set(cache_key, {
                'page': self.page,
                'timestamp': timezone.now()
            }, timeout=self.cache_timeout)
        
        return result
    
    def get_paginated_response(self, data):
        """Return paginated response with cache info"""
        response = super().get_paginated_response(data)
        
        # Add cache metadata
        response.data['cache_info'] = {
            'cached': False,
            'cache_timeout': self.cache_timeout
        }
        
        return response


class AlertLimitOffsetPagination(LimitOffsetPagination):
    """Limit/offset pagination for alert APIs"""
    
    default_limit = 20
    max_limit = 100
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    
    def get_paginated_response_schema(self, data):
        """Get limit/offset pagination response schema"""
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {'type': 'array'},
                'offset_info': {
                    'type': 'object',
                    'properties': {
                        'current_offset': {'type': 'integer'},
                        'current_limit': {'type': 'integer'},
                        'next_offset': {'type': 'integer', 'nullable': True},
                        'has_more': {'type': 'boolean'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return limit/offset paginated response"""
        response = super().get_paginated_response(data)
        
        # Add offset metadata
        current_offset = int(self.request.query_params.get(self.offset_query_param, 0))
        current_limit = self.get_limit(self.request)
        
        response.data['offset_info'] = {
            'current_offset': current_offset,
            'current_limit': current_limit,
            'next_offset': current_offset + current_limit if len(data) == current_limit else None,
            'has_more': len(data) == current_limit
        }
        
        return response


class InfiniteScrollPagination(CursorPagination):
    """Infinite scroll pagination for alert feeds"""
    
    page_size = 50
    max_page_size = 100
    cursor_query_param = 'scroll_id'
    ordering = '-triggered_at'
    
    def get_paginated_response_schema(self, data):
        """Get infinite scroll pagination response schema"""
        return {
            'type': 'object',
            'properties': {
                'results': {'type': 'array'},
                'scroll_info': {
                    'type': 'object',
                    'properties': {
                        'next_scroll_id': {'type': 'string', 'nullable': True},
                        'has_more': {'type': 'boolean'},
                        'count': {'type': 'integer'},
                        'total_count': {'type': 'integer'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return infinite scroll response"""
        response = super().get_paginated_response(data)
        
        # Add scroll metadata
        response.data['scroll_info'] = {
            'next_scroll_id': self.get_next_cursor(),
            'has_more': self.has_more,
            'count': len(data),
            'total_count': self.count
        }
        
        return response


class DateRangePagination(PageNumberPagination):
    """Pagination with date range filtering"""
    
    def paginate_queryset(self, queryset, request, view=None):
        """Apply date range filtering before pagination"""
        # Get date range from request
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Apply date filters
        if start_date:
            queryset = queryset.filter(triggered_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(triggered_at__lte=end_date)
        
        return super().paginate_queryset(queryset, request, view)
    
    def get_paginated_response_schema(self, data):
        """Get date range pagination response schema"""
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {'type': 'array'},
                'date_range': {
                    'type': 'object',
                    'properties': {
                        'start_date': {'type': 'string'},
                        'end_date': {'type': 'string'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return date range paginated response"""
        response = super().get_paginated_response(data)
        
        # Add date range info
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        response.data['date_range'] = {
            'start_date': start_date,
            'end_date': end_date
        }
        
        return response


class GroupedPagination(PageNumberPagination):
    """Pagination that groups results by field"""
    
    grouping_field = 'rule__severity'
    group_size = 10
    
    def paginate_queryset(self, queryset, request, view=None):
        """Apply grouping before pagination"""
        # Group by specified field
        grouped_queryset = queryset.values(
            self.grouping_field
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        return super().paginate_queryset(grouped_queryset, request, view)
    
    def get_paginated_response_schema(self, data):
        """Get grouped pagination response schema"""
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {'type': 'array'},
                'group_info': {
                    'type': 'object',
                    'properties': {
                        'grouping_field': {'type': 'string'},
                        'total_groups': {'type': 'integer'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return grouped paginated response"""
        response = super().get_paginated_response(data)
        
        # Add grouping info
        response.data['group_info'] = {
            'grouping_field': self.grouping_field,
            'total_groups': self.count
        }
        
        return response


class SearchPagination(PageNumberPagination):
    """Pagination optimized for search results"""
    
    def paginate_queryset(self, queryset, request, view=None):
        """Apply search filtering before pagination"""
        search_term = request.query_params.get('search')
        
        if search_term:
            # Apply search filters
            from django.db.models import Q
            queryset = queryset.filter(
                Q(message__icontains=search_term) |
                Q(rule__name__icontains=search_term) |
                Q(rule__description__icontains=search_term)
            )
        
        return super().paginate_queryset(queryset, request, view)
    
    def get_paginated_response_schema(self, data):
        """Get search pagination response schema"""
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {'type': 'array'},
                'search_info': {
                    'type': 'object',
                    'properties': {
                        'search_term': {'type': 'string'},
                        'search_fields': {'type': 'array'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return search paginated response"""
        response = super().get_paginated_response(data)
        
        # Add search info
        search_term = self.request.query_params.get('search', '')
        response.data['search_info'] = {
            'search_term': search_term,
            'search_fields': ['message', 'rule__name', 'rule__description']
        }
        
        return response


# Utility functions for pagination
def get_pagination_class(pagination_type: str):
    """Get pagination class by type"""
    pagination_classes = {
        'page': AlertPagination,
        'cursor': AlertCursorPagination,
        'cached': CachedPagination,
        'limit_offset': AlertLimitOffsetPagination,
        'infinite_scroll': InfiniteScrollPagination,
        'date_range': DateRangePagination,
        'grouped': GroupedPagination,
        'search': SearchPagination
    }
    
    return pagination_classes.get(pagination_type, AlertPagination)


def create_custom_pagination(
    page_size: int = 20,
    max_page_size: int = 100,
    cache_timeout: int = 300,
    **kwargs
):
    """Create custom pagination class"""
    _page_size = page_size
    _max_page_size = max_page_size
    _cache_timeout = cache_timeout

    class CustomPagination(PageNumberPagination):
        page_size = _page_size
        max_page_size = _max_page_size
        cache_timeout = _cache_timeout

    # Apply additional kwargs - after the class exists, not during its body
    for key, value in kwargs.items():
        setattr(CustomPagination, key, value)

    return CustomPagination


def get_pagination_metadata(request, total_count, page_size: int = None) -> Dict[str, Any]:
    """Get pagination metadata without full pagination"""
    if page_size is None:
        page_size = int(request.query_params.get('page_size', 20))
    
    page_number = int(request.query_params.get('page', 1))
    total_pages = (total_count + page_size - 1) // page_size
    
    return {
        'current_page': page_number,
        'page_size': page_size,
        'total_count': total_count,
        'total_pages': total_pages,
        'has_next': page_number < total_pages,
        'has_previous': page_number > 1,
        'next_page': page_number + 1 if page_number < total_pages else None,
        'previous_page': page_number - 1 if page_number > 1 else None
    }


def validate_pagination_params(request, max_page_size: int = 100) -> Dict[str, Any]:
    """Validate pagination parameters"""
    errors = []
    
    # Validate page number
    page = request.query_params.get('page', '1')
    try:
        page_num = int(page)
        if page_num < 1:
            errors.append('Page number must be positive')
    except ValueError:
        errors.append('Invalid page number')
        page_num = 1
    
    # Validate page size
    page_size = request.query_params.get('page_size', '20')
    try:
        page_size_num = int(page_size)
        if page_size_num < 1:
            errors.append('Page size must be positive')
        elif page_size_num > max_page_size:
            errors.append(f'Page size cannot exceed {max_page_size}')
    except ValueError:
        errors.append('Invalid page size')
        page_size_num = 20
    
    # Validate offset for limit/offset pagination
    offset = request.query_params.get('offset', '0')
    try:
        offset_num = int(offset)
        if offset_num < 0:
            errors.append('Offset cannot be negative')
    except ValueError:
        errors.append('Invalid offset')
        offset_num = 0
    
    # Validate limit
    limit = request.query_params.get('limit', str(page_size_num))
    try:
        limit_num = int(limit)
        if limit_num < 1:
            errors.append('Limit must be positive')
        elif limit_num > max_page_size:
            errors.append(f'Limit cannot exceed {max_page_size}')
    except ValueError:
        errors.append('Invalid limit')
        limit_num = page_size_num
    
    return {
        'page': page_num,
        'page_size': page_size_num,
        'offset': offset_num,
        'limit': limit_num,
        'errors': errors,
        'is_valid': len(errors) == 0
    }
