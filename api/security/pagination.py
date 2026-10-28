"""
Security Pagination Module
Advanced pagination classes for security module APIs
"""

import logging
from typing import Dict, List, Any, Optional, Type
from collections import OrderedDict
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.response import Response
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from datetime import datetime

logger = logging.getLogger('security.pagination')


class SecurityPageNumberPagination(PageNumberPagination):
    """Enhanced pagination for security module"""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    cache_timeout = 300  # 5 minutes
    
    def get_paginated_response(self, data):
        """Return paginated response with enhanced metadata"""
        response_data = OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
            ('page_info', self.get_page_info()),
            ('pagination_metadata', self.get_pagination_metadata()),
        ])
        
        return Response(response_data)
    
    def get_page_info(self) -> Dict[str, Any]:
        """Get detailed page information"""
        paginator = self.page.paginator
        
        return {
            'current_page': self.page.number,
            'total_pages': paginator.num_pages,
            'page_size': self.page_size,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'items_on_page': len(self.page.object_list),
            'total_items': paginator.count,
        }
    
    def get_pagination_metadata(self) -> Dict[str, Any]:
        """Get pagination metadata"""
        return {
            'page_size_query_param': self.page_size_query_param,
            'max_page_size': self.max_page_size,
            'default_page_size': self.page_size,
            'cached': getattr(self, '_cached', False),
        }
    
    def paginate_queryset(self, queryset):
        """Paginate queryset with caching support"""
        # Generate cache key
        cache_key = self.get_cache_key()
        
        # Try to get from cache
        if cache_key:
            cached_data = cache.get(cache_key)
            if cached_data:
                self._cached = True
                # Reconstruct page object from cached data
                self.page = self._create_page_from_cache(cached_data, queryset)
                return list(self.page.object_list)
        
        # Normal pagination
        result = super().paginate_queryset(queryset)
        
        # Cache the result
        if cache_key and self.page:
            cache_data = {
                'number': self.page.number,
                'object_list': list(self.page.object_list),
                'count': self.page.paginator.count,
            }
            cache.set(cache_key, cache_data, self.cache_timeout)
        
        return result
    
    def get_cache_key(self) -> Optional[str]:
        """Generate cache key for pagination"""
        if not getattr(settings, 'SECURITY_PAGINATION_CACHE', False):
            return None
        
        request = self.request
        cache_key_parts = [
            'security_pagination',
            request.user.id if request.user.is_authenticated else 'anonymous',
            request.build_absolute_uri(),
            str(self.page_size),
            str(self.page.number if hasattr(self, 'page') else 1),
        ]
        
        return ':'.join(cache_key_parts)
    
    def _create_page_from_cache(self, cached_data, queryset):
        """Create page object from cached data"""
        paginator = Paginator(queryset, self.page_size)
        return paginator.page(cached_data['number'])


class SecurityLimitOffsetPagination(LimitOffsetPagination):
    """Enhanced limit-offset pagination for security module"""
    
    default_limit = 20
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100
    cache_timeout = 300
    
    def get_paginated_response(self, data):
        """Return paginated response with enhanced metadata"""
        response_data = OrderedDict([
            ('count', self.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
            ('limit_info', self.get_limit_info()),
            ('pagination_metadata', self.get_pagination_metadata()),
        ])
        
        return Response(response_data)
    
    def get_limit_info(self) -> Dict[str, Any]:
        """Get detailed limit information"""
        return {
            'limit': self.limit,
            'offset': self.offset,
            'next_offset': self.offset + self.limit if self.offset + self.limit < self.count else None,
            'has_next': self.offset + self.limit < self.count,
            'remaining_items': max(0, self.count - self.offset - self.limit),
        }
    
    def get_pagination_metadata(self) -> Dict[str, Any]:
        """Get pagination metadata"""
        return {
            'limit_query_param': self.limit_query_param,
            'offset_query_param': self.offset_query_param,
            'max_limit': self.max_limit,
            'default_limit': self.default_limit,
            'cached': getattr(self, '_cached', False),
        }


class CursorPagination:
    """Cursor-based pagination for large datasets"""
    
    def __init__(self, page_size=20, max_page_size=100, ordering='-created_at'):
        self.page_size = page_size
        self.max_page_size = max_page_size
        self.ordering = ordering
    
    def paginate_queryset(self, queryset, request):
        """Paginate using cursor-based approach"""
        cursor = request.query_params.get('cursor')
        limit = min(
            int(request.query_params.get('limit', self.page_size)),
            self.max_page_size
        )
        
        if cursor:
            try:
                # Decode cursor and apply filtering
                queryset = self.apply_cursor(queryset, cursor)
            except Exception as e:
                logger.error(f"Invalid cursor: {e}")
                queryset = queryset.none()
        
        # Apply ordering and limit
        queryset = queryset.order_by(self.ordering)[:limit + 1]  # +1 to check if there's a next page
        
        items = list(queryset)
        has_next = len(items) > limit
        
        if has_next:
            items = items[:limit]
            next_cursor = self.encode_cursor(items[-1])
        else:
            next_cursor = None
        
        return items, next_cursor, has_next
    
    def apply_cursor(self, queryset, cursor):
        """Apply cursor filtering to queryset"""
        try:
            # Decode cursor (simplified implementation)
            cursor_data = self.decode_cursor(cursor)
            
            # Apply filtering based on cursor
            if self.ordering.startswith('-'):
                # Descending order
                field = self.ordering[1:]
                if cursor_data.get(field):
                    queryset = queryset.filter(**{f'{field}__lt': cursor_data[field]})
            else:
                # Ascending order
                field = self.ordering
                if cursor_data.get(field):
                    queryset = queryset.filter(**{f'{field}__gt': cursor_data[field]})
            
            return queryset
            
        except Exception as e:
            logger.error(f"Error applying cursor: {e}")
            return queryset.none()
    
    def encode_cursor(self, item):
        """Encode cursor from item"""
        import base64
        import json
        
        cursor_data = {}
        
        # Extract ordering field value
        if self.ordering.startswith('-'):
            field = self.ordering[1:]
        else:
            field = self.ordering
        
        if hasattr(item, field):
            cursor_data[field] = getattr(item, field)
        
        # Add timestamp for consistency
        if hasattr(item, 'created_at'):
            cursor_data['created_at'] = item.created_at.isoformat()
        
        cursor_json = json.dumps(cursor_data)
        cursor_bytes = cursor_json.encode('utf-8')
        cursor_encoded = base64.b64encode(cursor_bytes).decode('utf-8')
        
        return cursor_encoded
    
    def decode_cursor(self, cursor):
        """Decode cursor string"""
        import base64
        import json
        
        cursor_bytes = base64.b64decode(cursor.encode('utf-8'))
        cursor_json = cursor_bytes.decode('utf-8')
        
        return json.loads(cursor_json)
    
    def get_paginated_response(self, items, next_cursor, has_next, request):
        """Get paginated response"""
        return Response({
            'results': items,
            'next_cursor': next_cursor,
            'has_next': has_next,
            'limit': len(items),
            'pagination_type': 'cursor'
        })


class InfiniteScrollPagination:
    """Infinite scroll pagination for frontend consumption"""
    
    def __init__(self, page_size=20, max_page_size=100):
        self.page_size = page_size
        self.max_page_size = max_page_size
    
    def paginate_queryset(self, queryset, request):
        """Paginate for infinite scroll"""
        page = int(request.query_params.get('page', 1))
        limit = min(
            int(request.query_params.get('limit', self.page_size)),
            self.max_page_size
        )
        
        offset = (page - 1) * limit
        queryset = queryset[offset:offset + limit]
        
        items = list(queryset)
        has_more = len(items) == limit
        
        return items, has_more, page
    
    def get_paginated_response(self, items, has_more, page, request):
        """Get infinite scroll response"""
        return Response({
            'items': items,
            'has_more': has_more,
            'page': page,
            'limit': len(items),
            'pagination_type': 'infinite_scroll'
        })


class SearchPagination:
    """Pagination with search capabilities"""
    
    def __init__(self, page_size=20, max_page_size=100):
        self.page_size = page_size
        self.max_page_size = max_page_size
    
    def paginate_queryset(self, queryset, request):
        """Paginate with search support"""
        search_query = request.query_params.get('search', '').strip()
        
        if search_query:
            # Apply search (simplified)
            searchable_fields = self.get_searchable_fields(queryset.model)
            search_q = self.build_search_query(search_query, searchable_fields)
            queryset = queryset.filter(search_q)
        
        # Apply pagination
        page = int(request.query_params.get('page', 1))
        limit = min(
            int(request.query_params.get('limit', self.page_size)),
            self.max_page_size
        )
        
        offset = (page - 1) * limit
        total_count = queryset.count()
        items = list(queryset[offset:offset + limit])
        
        has_next = offset + limit < total_count
        
        return items, has_next, page, total_count, search_query
    
    def get_searchable_fields(self, model):
        """Get searchable fields for model"""
        # This is a simplified implementation
        searchable_fields = []
        for field in model._meta.fields:
            if field.__class__.__name__ in ['CharField', 'TextField']:
                searchable_fields.append(field.name)
        return searchable_fields
    
    def build_search_query(self, query, fields):
        """Build search query"""
        from django.db.models import Q
        
        search_q = Q()
        for field in fields:
            search_q |= Q(**{f'{field}__icontains': query})
        
        return search_q
    
    def get_paginated_response(self, items, has_next, page, total_count, search_query, request):
        """Get search pagination response"""
        return Response({
            'results': items,
            'has_next': has_next,
            'page': page,
            'limit': len(items),
            'total_count': total_count,
            'search_query': search_query,
            'pagination_type': 'search'
        })


class AggregatedPagination:
    """Pagination with aggregated data"""
    
    def __init__(self, page_size=20, max_page_size=100, aggregate_by=None):
        self.page_size = page_size
        self.max_page_size = max_page_size
        self.aggregate_by = aggregate_by or ['date']
    
    def paginate_queryset(self, queryset, request):
        """Paginate with aggregation"""
        page = int(request.query_params.get('page', 1))
        limit = min(
            int(request.query_params.get('limit', self.page_size)),
            self.max_page_size
        )
        
        offset = (page - 1) * limit
        
        # Apply aggregation
        aggregated_data = self.aggregate_data(queryset)
        
        # Paginate aggregated data
        total_count = len(aggregated_data)
        items = aggregated_data[offset:offset + limit]
        has_next = offset + limit < total_count
        
        return items, has_next, page, total_count
    
    def aggregate_data(self, queryset):
        """Aggregate data by specified fields"""
        if not self.aggregate_by:
            return list(queryset)
        
        # This is a simplified implementation
        # In practice, you'd use Django's aggregation functions
        aggregated = []
        
        for item in queryset:
            # Create aggregation key
            key_parts = []
            for field in self.aggregate_by:
                if hasattr(item, field):
                    value = getattr(item, field)
                    if isinstance(value, (datetime, timezone.datetime)):
                        key_parts.append(value.date().isoformat())
                    else:
                        key_parts.append(str(value))
            
            key = '|'.join(key_parts)
            
            # Find existing aggregation or create new
            existing = next((agg for agg in aggregated if agg['key'] == key), None)
            if existing:
                existing['count'] += 1
                existing['items'].append(item)
            else:
                aggregated.append({
                    'key': key,
                    'count': 1,
                    'items': [item],
                    'sample': item  # Sample item for display
                })
        
        return aggregated
    
    def get_paginated_response(self, items, has_next, page, total_count, request):
        """Get aggregated pagination response"""
        return Response({
            'results': items,
            'has_next': has_next,
            'page': page,
            'limit': len(items),
            'total_count': total_count,
            'aggregated_by': self.aggregate_by,
            'pagination_type': 'aggregated'
        })


class HybridPagination:
    """Hybrid pagination supporting multiple pagination types"""
    
    def __init__(self, default_type='page', **kwargs):
        self.default_type = default_type
        self.paginators = {
            'page': SecurityPageNumberPagination(**kwargs),
            'limit': SecurityLimitOffsetPagination(**kwargs),
            'cursor': CursorPagination(**kwargs),
            'infinite': InfiniteScrollPagination(**kwargs),
            'search': SearchPagination(**kwargs),
            'aggregated': AggregatedPagination(**kwargs),
        }
    
    def paginate_queryset(self, queryset, request):
        """Paginate using specified type"""
        pagination_type = request.query_params.get('pagination_type', self.default_type)
        
        if pagination_type not in self.paginators:
            pagination_type = self.default_type
        
        paginator = self.paginators[pagination_type]
        
        if hasattr(paginator, 'paginate_queryset'):
            return paginator.paginate_queryset(queryset, request)
        else:
            # For classes that don't have paginate_queryset method
            return self._fallback_pagination(queryset, request)
    
    def _fallback_pagination(self, queryset, request):
        """Fallback pagination method"""
        page = int(request.query_params.get('page', 1))
        limit = min(
            int(request.query_params.get('limit', 20)),
            100
        )
        
        offset = (page - 1) * limit
        total_count = queryset.count()
        items = list(queryset[offset:offset + limit])
        has_next = offset + limit < total_count
        
        return items, has_next, page, total_count
    
    def get_paginated_response(self, *args, **kwargs):
        """Get paginated response"""
        pagination_type = kwargs.get('request', {}).query_params.get('pagination_type', self.default_type)
        
        if pagination_type in self.paginators:
            paginator = self.paginators[pagination_type]
            if hasattr(paginator, 'get_paginated_response'):
                return paginator.get_paginated_response(*args, **kwargs)
        
        # Fallback response
        items, has_next, page, total_count = args[0] if args else ([], False, 1, 0)
        
        return Response({
            'results': items,
            'has_next': has_next,
            'page': page,
            'limit': len(items),
            'total_count': total_count,
            'pagination_type': pagination_type
        })


class CachedPagination:
    """Pagination with caching support"""
    
    def __init__(self, page_size=20, cache_timeout=300, cache_prefix='security_pag'):
        self.page_size = page_size
        self.cache_timeout = cache_timeout
        self.cache_prefix = cache_prefix
    
    def paginate_queryset(self, queryset, request):
        """Paginate with caching"""
        cache_key = self.get_cache_key(request)
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Normal pagination
        page = int(request.query_params.get('page', 1))
        limit = min(
            int(request.query_params.get('limit', self.page_size)),
            100
        )
        
        offset = (page - 1) * limit
        total_count = queryset.count()
        items = list(queryset[offset:offset + limit])
        has_next = offset + limit < total_count
        
        result = (items, has_next, page, total_count)
        
        # Cache the result
        cache.set(cache_key, result, self.cache_timeout)
        
        return result
    
    def get_cache_key(self, request):
        """Generate cache key"""
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        path = request.build_absolute_uri()
        page = request.query_params.get('page', 1)
        limit = request.query_params.get('limit', self.page_size)
        
        return f"{self.cache_prefix}:{user_id}:{path}:{page}:{limit}"
    
    def get_paginated_response(self, items, has_next, page, total_count, request):
        """Get cached pagination response"""
        return Response({
            'results': items,
            'has_next': has_next,
            'page': page,
            'limit': len(items),
            'total_count': total_count,
            'cached': True,
            'pagination_type': 'cached'
        })


class PaginationManager:
    """Manager for pagination configuration"""
    
    def __init__(self):
        self.default_pagination = SecurityPageNumberPagination
        self.custom_paginators = {}
    
    def register_paginator(self, name: str, paginator_class: Type, **kwargs):
        """Register custom paginator"""
        self.custom_paginators[name] = paginator_class(**kwargs)
    
    def get_paginator(self, name: str = None):
        """Get paginator by name"""
        if name and name in self.custom_paginators:
            return self.custom_paginators[name]
        return self.default_pagination
    
    def get_pagination_class(self, pagination_config: Dict[str, Any]):
        """Get pagination class from configuration"""
        pagination_type = pagination_config.get('class', 'page')
        
        if pagination_type == 'limit':
            return SecurityLimitOffsetPagination
        elif pagination_type == 'cursor':
            return CursorPagination
        elif pagination_type == 'infinite':
            return InfiniteScrollPagination
        elif pagination_type == 'search':
            return SearchPagination
        elif pagination_type == 'aggregated':
            return AggregatedPagination
        elif pagination_type == 'hybrid':
            return HybridPagination
        elif pagination_type == 'cached':
            return CachedPagination
        else:
            return SecurityPageNumberPagination


# Global pagination manager
pagination_manager = PaginationManager()

# Register default paginators
def register_default_paginators():
    """Register default pagination classes"""
    pagination_manager.register_paginator('security_page', SecurityPageNumberPagination)
    pagination_manager.register_paginator('security_limit', SecurityLimitOffsetPagination)
    pagination_manager.register_paginator('security_cursor', CursorPagination)
    pagination_manager.register_paginator('security_infinite', InfiniteScrollPagination)
    pagination_manager.register_paginator('security_search', SearchPagination)
    pagination_manager.register_paginator('security_aggregated', AggregatedPagination)
    pagination_manager.register_paginator('security_hybrid', HybridPagination)
    pagination_manager.register_paginator('security_cached', CachedPagination)


# Export pagination classes
__all__ = [
    'SecurityPageNumberPagination',
    'SecurityLimitOffsetPagination',
    'CursorPagination',
    'InfiniteScrollPagination',
    'SearchPagination',
    'AggregatedPagination',
    'HybridPagination',
    'CachedPagination',
    'PaginationManager',
    'pagination_manager',
    'register_default_paginators'
]