"""
Pagination Classes for Offer Routing System

This module provides pagination classes for handling large datasets,
including cursor-based pagination, standard page pagination, and optimized
querying for routing logs, analytics data, and performance metrics.
"""

import math
import base64
import hashlib
from django.core.paginator import Paginator, EmptyPage
from django.core.cache import cache
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class RoutingCursorPagination(CursorPagination):
    """
    Cursor-based pagination for routing decisions and analytics.
    
    Optimized for large datasets with stable performance
    and real-time data streaming.
    """
    
    page_size = 100
    max_page_size = 1000
    cursor_query_param = 'cursor'
    page_size_query_param = 'page_size'
    ordering = '-created_at'
    
    def get_paginated_response_schema(self):
        """Get pagination schema for API documentation."""
        return {
            'type': 'object',
            'properties': {
                'next': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'previous': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object'
                    }
                },
                'count': {
                    'type': 'integer',
                    'minimum': 0
                },
                'page_info': {
                    'type': 'object',
                    'properties': {
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'},
                        'page_size': {'type': 'integer'},
                        'current_cursor': {'type': 'string'}
                    }
                }
            }
        }
    
    def encode_cursor(self, item):
        """Encode cursor from item."""
        if not hasattr(item, 'created_at'):
            return None
        
        # Use timestamp for cursor
        timestamp = item.created_at.isoformat()
        
        # Add item ID for uniqueness
        item_id = str(item.id)
        
        # Create cursor string
        cursor_data = f"{timestamp}:{item_id}"
        
        # Encode for URL safety
        cursor_bytes = cursor_data.encode('utf-8')
        cursor_b64 = base64.b64encode(cursor_bytes).decode('utf-8')
        
        return cursor_b64
    
    def decode_cursor(self, cursor):
        """Decode cursor to get ordering parameters."""
        if not cursor:
            return None
        
        try:
            # Decode from base64
            cursor_b64 = cursor.encode('utf-8')
            cursor_bytes = base64.b64decode(cursor_b64).decode('utf-8')
            
            # Split timestamp and ID
            parts = cursor_bytes.split(':', 1)
            
            if len(parts) != 2:
                return None
            
            timestamp, item_id = parts
            
            return {
                'timestamp': timestamp,
                'item_id': item_id
            }
            
        except Exception as e:
            logger.error(f"Error decoding cursor: {e}")
            return None
    
    def get_queryset(self):
        """Get queryset with cursor ordering."""
        queryset = super().get_queryset()
        
        # Apply ordering
        if self.ordering:
            queryset = queryset.order_by(self.ordering)
        
        return queryset
    
    def paginate_queryset(self, queryset, request, view=None):
        """Paginate queryset using cursor."""
        # Get cursor from request
        cursor = request.query_params.get(self.cursor_query_param)
        page_size = self.get_page_size(request)
        
        # Decode cursor
        cursor_data = self.decode_cursor(cursor)
        
        # Apply cursor filtering
        if cursor_data:
            # Parse timestamp from cursor
            try:
                timestamp = timezone.datetime.fromisoformat(cursor_data['timestamp'])
                
                # Filter items created before cursor timestamp
                if self.ordering.startswith('-'):
                    queryset = queryset.filter(created_at__lt=timestamp)
                else:
                    queryset = queryset.filter(created_at__gt=timestamp)
                
                # Add ID filtering for stability
                if 'item_id' in cursor_data:
                    if self.ordering.startswith('-'):
                        queryset = queryset.filter(
                            created_at__lt=timestamp,
                            id__gt=cursor_data['item_id']
                        )
                    else:
                        queryset = queryset.filter(
                            created_at__gt=timestamp,
                            id__lt=cursor_data['item_id']
                        )
                        
            except Exception as e:
                logger.error(f"Error applying cursor filter: {e}")
        
        # Apply page size limit
        queryset = queryset[:page_size]
        
        return list(queryset)
    
    def get_paginated_response_data(self, data):
        """Get paginated response data."""
        # Get next cursor
        next_cursor = None
        if data and len(data) >= self.page_size:
            next_cursor = self.encode_cursor(data[-1])
        
        # Get previous cursor
        previous_cursor = None
        if data and self.request.query_params.get('include_previous'):
            previous_cursor = self.encode_cursor(data[0])
        
        return {
            'next': self.get_next_link(next_cursor) if next_cursor else None,
            'previous': self.get_previous_link(previous_cursor) if previous_cursor else None,
            'results': data,
            'count': len(data),
            'page_info': {
                'has_next': bool(next_cursor),
                'has_previous': bool(previous_cursor),
                'page_size': self.page_size,
                'current_cursor': self.request.query_params.get(self.cursor_query_param)
            }
        }


class RoutingPageNumberPagination(PageNumberPagination):
    """
    Standard page-based pagination for routing system.
    
    Provides traditional pagination with customizable page size
    and optimized database queries.
    """
    
    page_size = 50
    max_page_size = 500
    page_query_param = 'page'
    page_size_query_param = 'page_size'
    last_page_strings = ('last',)
    
    def get_paginated_response_schema(self):
        """Get pagination schema for API documentation."""
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'minimum': 0
                },
                'next': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'previous': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object'
                    }
                },
                'num_pages': {
                    'type': 'integer',
                    'minimum': 1
                },
                'current_page': {
                    'type': 'integer',
                    'minimum': 1
                }
            }
        }
    
    def get_queryset(self):
        """Get optimized queryset."""
        queryset = super().get_queryset()
        
        # Apply select_related for optimization
        if hasattr(queryset.model, '_meta'):
            related_fields = []
            for field in queryset.model._meta.fields:
                if field.is_relation:
                    related_fields.append(field.name)
            
            if related_fields:
                queryset = queryset.select_related(*related_fields)
        
        return queryset


class AnalyticsPagination(PageNumberPagination):
    """
    Specialized pagination for analytics data.
    
    Optimized for time-series data and aggregated statistics
    with date range filtering and caching.
    """
    
    page_size = 100
    max_page_size = 1000
    page_query_param = 'page'
    page_size_query_param = 'page_size'
    
    def get_paginated_response_schema(self):
        """Get pagination schema for analytics API."""
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'minimum': 0
                },
                'next': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'previous': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object'
                    }
                },
                'aggregations': {
                    'type': 'object',
                    'description': 'Aggregated statistics for current page'
                }
            }
        }
    
    def paginate_queryset(self, queryset, request, view=None):
        """Paginate analytics queryset with optimizations."""
        # Get date range from request
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        # Apply date filtering
        if date_from:
            try:
                date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(date__lte=date_to)
            except ValueError:
                pass
        
        # Apply aggregation
        aggregation_type = request.query_params.get('aggregation')
        if aggregation_type == 'daily':
            queryset = queryset.extra({
                'date': 'DATE(date)'
            }).values('date').annotate(
                count=models.Count('id'),
                avg_score=models.Avg('score'),
                total_conversions=models.Sum('conversions')
            ).order_by('-date')
        
        elif aggregation_type == 'hourly':
            queryset = queryset.extra({
                'hour': 'EXTRACT(HOUR FROM created_at)',
                'date': 'DATE(created_at)'
            }).values('date', 'hour').annotate(
                count=models.Count('id'),
                avg_score=models.Avg('score'),
                total_conversions=models.Sum('conversions')
            }).order_by('-date', '-hour')
        
        return super().paginate_queryset(queryset, request, view)


class DecisionLogPagination(RoutingCursorPagination):
    """
    Specialized pagination for routing decision logs.
    
    Optimized for high-volume decision log queries
    with caching and performance monitoring.
    """
    
    page_size = 200
    max_page_size = 2000
    ordering = '-created_at'
    
    def get_queryset(self):
        """Get optimized decision log queryset."""
        from .models import RoutingDecisionLog
        
        queryset = super().get_queryset()
        
        # Apply select_related for optimization
        queryset = queryset.select_related('user')
        
        # Apply filtering from request
        if hasattr(self, 'request') and self.request:
            # Filter by user
            user_id = self.request.query_params.get('user_id')
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            
            # Filter by date range
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            
            if date_from:
                try:
                    date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__gte=date_from)
                except ValueError:
                    pass
            
            if date_to:
                try:
                    date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__lte=date_to)
                except ValueError:
                    pass
            
            # Filter by cache hit
            cache_hit = self.request.query_params.get('cache_hit')
            if cache_hit is not None:
                queryset = queryset.filter(cache_hit=cache_hit.lower() == 'true')
            
            # Filter by response time range
            min_response_time = self.request.query_params.get('min_response_time')
            max_response_time = self.request.query_params.get('max_response_time')
            
            if min_response_time:
                try:
                    queryset = queryset.filter(response_time_ms__gte=int(min_response_time))
                except ValueError:
                    pass
            
            if max_response_time:
                try:
                    queryset = queryset.filter(response_time_ms__lte=int(max_response_time))
                except ValueError:
                    pass
        
        return queryset
    
    def get_paginated_response_data(self, data):
        """Get paginated response with additional metadata."""
        response_data = super().get_paginated_response_data(data)
        
        # Add decision log specific metadata
        if data:
            # Calculate statistics
            response_times = [item['response_time_ms'] for item in data if item.get('response_time_ms')]
            cache_hits = [item for item in data if item.get('cache_hit')]
            
            if response_times:
                response_data['metadata'] = {
                    'avg_response_time': sum(response_times) / len(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'cache_hit_rate': len(cache_hits) / len(data) * 100,
                    'total_decisions': len(data)
                }
        
        return response_data


class PerformanceStatsPagination(AnalyticsPagination):
    """
    Specialized pagination for performance statistics.
    
    Optimized for aggregated performance data
    with date range filtering and metric calculations.
    """
    
    page_size = 50
    max_page_size = 500
    
    def get_queryset(self):
        """Get optimized performance stats queryset."""
        from .models import RoutePerformanceStat
        
        queryset = super().get_queryset()
        
        # Apply filtering from request
        if hasattr(self, 'request') and self.request:
            # Filter by date range
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            
            if date_from:
                try:
                    date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(date__gte=date_from)
                except ValueError:
                    pass
            
            if date_to:
                try:
                    date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(date__lte=date_to)
                except ValueError:
                    pass
            
            # Filter by tenant
            tenant_id = self.request.query_params.get('tenant_id')
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
            
            # Filter by performance metrics
            min_impressions = self.request.query_params.get('min_impressions')
            max_impressions = self.request.query_params.get('max_impressions')
            
            if min_impressions:
                try:
                    queryset = queryset.filter(impressions__gte=int(min_impressions))
                except ValueError:
                    pass
            
            if max_impressions:
                try:
                    queryset = queryset.filter(impressions__lte=int(max_impressions))
                except ValueError:
                    pass
        
        return queryset


class OfferHistoryPagination(RoutingCursorPagination):
    """
    Specialized pagination for user offer history.
    
    Optimized for user-specific offer interaction data
    with privacy controls and filtering options.
    """
    
    page_size = 100
    max_page_size = 1000
    ordering = '-created_at'
    
    def get_queryset(self):
        """Get optimized offer history queryset."""
        from .models import UserOfferHistory
        
        queryset = super().get_queryset()
        
        # Apply filtering from request
        if hasattr(self, 'request') and self.request:
            # Filter by user
            user_id = self.request.query_params.get('user_id')
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            
            # Filter by offer
            offer_id = self.request.query_params.get('offer_id')
            if offer_id:
                queryset = queryset.filter(offer_id=offer_id)
            
            # Filter by interaction type
            interaction_type = self.request.query_params.get('interaction_type')
            if interaction_type:
                queryset = queryset.filter(interaction_type=interaction_type)
            
            # Filter by date range
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            
            if date_from:
                try:
                    date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__gte=date_from)
                except ValueError:
                    pass
            
            if date_to:
                try:
                    date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__lte=date_to)
                except ValueError:
                    pass
        
        return queryset


# Utility functions for pagination
def get_pagination_class(pagination_type='cursor'):
    """Get appropriate pagination class based on type."""
    pagination_classes = {
        'cursor': RoutingCursorPagination,
        'page': RoutingPageNumberPagination,
        'analytics': AnalyticsPagination,
        'decision_logs': DecisionLogPagination,
        'performance_stats': PerformanceStatsPagination,
        'offer_history': OfferHistoryPagination
    }
    
    return pagination_classes.get(pagination_type, RoutingCursorPagination)


def create_cache_key(request, pagination_type='cursor'):
    """Create cache key for pagination results."""
    try:
        # Create unique key from request parameters
        params = {
            'pagination_type': pagination_type,
            'page_size': request.query_params.get('page_size', '100'),
            'filters': dict(request.query_params)
        }
        
        # Hash parameters for cache key
        params_str = str(sorted(params.items()))
        cache_key = hashlib.md5(params_str.encode()).hexdigest()
        
        return f"pagination:{pagination_type}:{cache_key}"
        
    except Exception as e:
        logger.error(f"Error creating cache key: {e}")
        return f"pagination:{pagination_type}:default"


def get_cached_pagination_response(request, queryset, pagination_class, timeout=300):
    """Get paginated response with caching."""
    try:
        # Check cache first
        cache_key = create_cache_key(request, pagination_class.__name__.lower())
        cached_response = cache.get(cache_key)
        
        if cached_response:
            logger.debug(f"Pagination cache hit: {cache_key}")
            return cached_response
        
        # Create paginator
        paginator = pagination_class()
        paginator.request = request
        paginated_data = paginator.paginate_queryset(queryset)
        
        # Create response
        response = paginator.get_paginated_response(paginated_data)
        
        # Cache response
        cache.set(cache_key, response.data, timeout)
        
        logger.debug(f"Pagination cache set: {cache_key}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in cached pagination: {e}")
        
        # Fallback to non-cached pagination
        paginator = pagination_class()
        paginator.request = request
        return paginator.get_paginated_response(
            paginator.paginate_queryset(queryset)
        )


# Pagination configuration
PAGINATION_SETTINGS = {
    'default_page_size': 50,
    'max_page_size': 1000,
    'cache_timeout': 300,  # 5 minutes
    'cursor_timeout': 3600,  # 1 hour
    'enable_cache': True,
    'cache_prefix': 'routing_pagination'
}
