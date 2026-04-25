"""
api/ad_networks/pagination.py
Pagination classes for ad networks module
SaaS-ready with tenant support
"""

import logging
from typing import Dict, List, Any, Optional

from django.core.paginator import Paginator
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.utils import replace_query_param

from .constants import CACHE_TIMEOUTS

logger = logging.getLogger(__name__)


class AdNetworksPagination(PageNumberPagination):
    """Custom pagination for ad networks"""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Return paginated response with metadata"""
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'total_items': self.page.paginator.count,
                'page_size': self.page_size,
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
                'next_page': self.page.next_page_number() if self.page.has_next() else None,
                'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
                'next_page_url': self.get_next_link(),
                'previous_page_url': self.get_previous_link(),
            },
            'timestamp': timezone.now().isoformat()
        })
    
    def get_page_size(self, request):
        """Get page size from request"""
        if hasattr(request, 'query_params'):
            page_size = request.query_params.get(self.page_size_query_param)
            if page_size:
                try:
                    page_size = int(page_size)
                    if page_size > 0:
                        return min(page_size, self.max_page_size)
                except ValueError:
                    pass
        return super().get_page_size(request)


class OfferPagination(AdNetworksPagination):
    """Pagination for offers"""
    
    page_size = 10
    max_page_size = 50
    
    def get_paginated_response(self, data):
        """Return paginated response for offers"""
        response = super().get_paginated_response(data)
        
        # Add offer-specific metadata
        response.data['offer_stats'] = {
            'total_offers': self.page.paginator.count,
            'offers_per_page': len(data),
            'showing_range': {
                'start': (self.page.number - 1) * self.page_size + 1,
                'end': min(self.page.number * self.page_size, self.page.paginator.count)
            }
        }
        
        return response


class ConversionPagination(AdNetworksPagination):
    """Pagination for conversions"""
    
    page_size = 25
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Return paginated response for conversions"""
        response = super().get_paginated_response(data)
        
        # Add conversion-specific metadata
        total_payout = sum(item.get('payout', 0) for item in data)
        response.data['conversion_stats'] = {
            'total_conversions': self.page.paginator.count,
            'conversions_per_page': len(data),
            'total_payout': total_payout,
            'average_payout': total_payout / len(data) if data else 0
        }
        
        return response


class RewardPagination(AdNetworksPagination):
    """Pagination for rewards"""
    
    page_size = 20
    max_page_size = 50
    
    def get_paginated_response(self, data):
        """Return paginated response for rewards"""
        response = super().get_paginated_response(data)
        
        # Add reward-specific metadata
        total_amount = sum(item.get('amount', 0) for item in data)
        response.data['reward_stats'] = {
            'total_rewards': self.page.paginator.count,
            'rewards_per_page': len(data),
            'total_amount': total_amount,
            'average_amount': total_amount / len(data) if data else 0
        }
        
        return response


class UserEngagementPagination(AdNetworksPagination):
    """Pagination for user engagements"""
    
    page_size = 15
    max_page_size = 50
    
    def get_paginated_response(self, data):
        """Return paginated response for user engagements"""
        response = super().get_paginated_response(data)
        
        # Add engagement-specific metadata
        completed_count = sum(1 for item in data if item.get('status') == 'completed')
        response.data['engagement_stats'] = {
            'total_engagements': self.page.paginator.count,
            'engagements_per_page': len(data),
            'completed_engagements': completed_count,
            'completion_rate': (completed_count / len(data) * 100) if data else 0
        }
        
        return response


class NetworkPagination(AdNetworksPagination):
    """Pagination for networks"""
    
    page_size = 30
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Return paginated response for networks"""
        response = super().get_paginated_response(data)
        
        # Add network-specific metadata
        active_count = sum(1 for item in data if item.get('status') == 'active')
        response.data['network_stats'] = {
            'total_networks': self.page.paginator.count,
            'networks_per_page': len(data),
            'active_networks': active_count,
            'active_rate': (active_count / len(data) * 100) if data else 0
        }
        
        return response


class CursorPagination(LimitOffsetPagination):
    """Cursor-based pagination for large datasets"""
    
    default_limit = 20
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100
    
    def get_paginated_response(self, data):
        """Return paginated response with cursor"""
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'next_offset': self.get_next_offset(),
                'previous_offset': self.get_previous_offset(),
                'limit': self.limit,
                'has_next': self.get_next_link() is not None,
                'has_previous': self.get_previous_link() is not None,
                'total_count': self.count,
            },
            'timestamp': timezone.now().isoformat()
        })
    
    def get_next_offset(self):
        """Get next offset"""
        if self.offset + self.limit >= self.count:
            return None
        return self.offset + self.limit
    
    def get_previous_offset(self):
        """Get previous offset"""
        if self.offset - self.limit < 0:
            return None
        return max(0, self.offset - self.limit)


class CachedPagination(AdNetworksPagination):
    """Pagination with caching support"""
    
    cache_timeout = 300  # 5 minutes
    cache_key_prefix = 'ad_networks_pagination'
    
    def get_cache_key(self, request):
        """Generate cache key for pagination"""
        tenant_id = getattr(request, 'tenant_id', 'default')
        page = request.query_params.get(self.page_query_param, 1)
        page_size = request.query_params.get(self.page_size_query_param, self.page_size)
        
        # Include relevant query parameters in cache key
        query_params = dict(request.query_params)
        query_params.pop(self.page_query_param, None)
        query_params.pop(self.page_size_query_param, None)
        
        # Create cache key
        cache_key_parts = [
            self.cache_key_prefix,
            tenant_id,
            str(page),
            str(page_size),
            str(hash(frozenset(query_params.items())))
        ]
        
        return '_'.join(cache_key_parts)
    
    def get_paginated_response(self, data):
        """Return paginated response with caching"""
        response = super().get_paginated_response(data)
        
        # Add cache information
        response.data['cache_info'] = {
            'cached': False,
            'cache_timeout': self.cache_timeout,
            'cache_key': self.get_cache_key(self.request)
        }
        
        return response
    
    def paginate_queryset(self, queryset):
        """Paginate with caching support"""
        cache_key = self.get_cache_key(self.request)
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data:
            self.cached_data = cached_data
            return cached_data['items']
        
        # If not cached, paginate normally
        items = super().paginate_queryset(queryset)
        
        # Cache the result
        cache_data = {
            'items': items,
            'count': self.page.paginator.count,
            'num_pages': self.page.paginator.num_pages
        }
        cache.set(cache_key, cache_data, self.cache_timeout)
        
        return items


class InfiniteScrollPagination(AdNetworksPagination):
    """Pagination for infinite scroll"""
    
    page_size = 20
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Return response for infinite scroll"""
        has_more = self.page.has_next()
        
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'has_more': has_more,
                'next_page': self.page.next_page_number() if has_more else None,
                'current_page': self.page.number,
                'page_size': len(data),
                'total_items': self.page.paginator.count,
            },
            'timestamp': timezone.now().isoformat()
        })


class AnalyticsPagination(AdNetworksPagination):
    """Pagination for analytics data"""
    
    page_size = 50
    max_page_size = 200
    
    def get_paginated_response(self, data):
        """Return paginated response for analytics"""
        response = super().get_paginated_response(data)
        
        # Add analytics-specific metadata
        if data:
            # Calculate aggregates from data
            numeric_fields = {}
            for field in ['payout', 'amount', 'reward_amount', 'conversion_value']:
                values = [item.get(field, 0) for item in data if isinstance(item.get(field), (int, float))]
                if values:
                    numeric_fields[field] = {
                        'sum': sum(values),
                        'average': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values)
                    }
            
            response.data['analytics'] = {
                'aggregates': numeric_fields,
                'items_count': len(data)
            }
        
        return response


class ExportPagination(AdNetworksPagination):
    """Pagination for export operations"""
    
    page_size = 1000  # Large page size for exports
    max_page_size = 5000
    
    def get_paginated_response(self, data):
        """Return paginated response for exports"""
        response = super().get_paginated_response(data)
        
        # Add export-specific metadata
        response.data['export_info'] = {
            'total_items': self.page.paginator.count,
            'items_per_page': len(data),
            'progress_percentage': (self.page.number / self.page.paginator.num_pages * 100) if self.page.paginator.num_pages > 0 else 0,
            'estimated_remaining_pages': self.page.paginator.num_pages - self.page.number,
            'is_last_page': not self.page.has_next()
        }
        
        return response


class HybridPagination:
    """Hybrid pagination supporting both page-based and cursor-based"""
    
    def __init__(self, use_cursor: bool = False, page_size: int = 20):
        self.use_cursor = use_cursor
        self.page_size = page_size
        self.cursor_pagination = CursorPagination()
        self.page_pagination = AdNetworksPagination()
        self.cursor_pagination.default_limit = page_size
        self.page_pagination.page_size = page_size
    
    def paginate_queryset(self, request, queryset):
        """Paginate queryset based on method"""
        if self.use_cursor:
            return self.cursor_pagination.paginate_queryset(request, queryset)
        else:
            return self.page_pagination.paginate_queryset(request, queryset)
    
    def get_paginated_response(self, data):
        """Get paginated response based on method"""
        if self.use_cursor:
            return self.cursor_pagination.get_paginated_response(data)
        else:
            return self.page_pagination.get_paginated_response(data)


class SmartPagination(AdNetworksPagination):
    """Smart pagination that adapts based on data size"""
    
    def get_page_size(self, request):
        """Get adaptive page size"""
        base_page_size = super().get_page_size(request)
        
        # Adjust page size based on total count if available
        if hasattr(self, 'page') and self.page:
            total_count = self.page.paginator.count
            
            if total_count < 50:
                return min(base_page_size, 10)
            elif total_count < 200:
                return min(base_page_size, 25)
            elif total_count < 1000:
                return min(base_page_size, 50)
            else:
                return base_page_size
        
        return base_page_size
    
    def get_paginated_response(self, data):
        """Return smart paginated response"""
        response = super().get_paginated_response(data)
        
        # Add smart pagination metadata
        if hasattr(self, 'page') and self.page:
            total_count = self.page.paginator.count
            current_page = self.page.number
            page_size = len(data)
            
            # Recommendations
            recommendations = []
            if total_count > 1000 and current_page == 1:
                recommendations.append("Consider using filters to narrow down results")
            
            if page_size < self.max_page_size and total_count > page_size * 5:
                recommendations.append(f"Consider increasing page size to {min(page_size * 2, self.max_page_size)} for better performance")
            
            response.data['recommendations'] = recommendations
            
            # Performance hints
            response.data['performance'] = {
                'query_efficient': total_count < 10000,
                'cache_recommended': total_count > 5000,
                'filter_recommended': total_count > 1000
            }
        
        return response


# Helper functions
def get_pagination_class(pagination_type: str = 'default') -> type:
    """Get pagination class by type"""
    pagination_classes = {
        'default': AdNetworksPagination,
        'offer': OfferPagination,
        'conversion': ConversionPagination,
        'reward': RewardPagination,
        'engagement': UserEngagementPagination,
        'network': NetworkPagination,
        'cursor': CursorPagination,
        'cached': CachedPagination,
        'infinite_scroll': InfiniteScrollPagination,
        'analytics': AnalyticsPagination,
        'export': ExportPagination,
        'smart': SmartPagination
    }
    
    return pagination_classes.get(pagination_type, AdNetworksPagination)


def paginate_response(data, request, pagination_class: type = AdNetworksPagination,
                    **pagination_kwargs):
    """Helper function to paginate response"""
    paginator = pagination_class(**pagination_kwargs)
    paginator.request = request
    
    # Create a simple paginator for the data
    from django.core.paginator import Paginator
    django_paginator = Paginator(data, paginator.page_size)
    page_number = request.query_params.get(paginator.page_query_param, 1)
    
    try:
        page_obj = django_paginator.page(page_number)
        paginator.page = page_obj
        return paginator.get_paginated_response(list(page_obj.object_list))
    except Exception as e:
        logger.error(f"Error paginating response: {str(e)}")
        return Response({
            'success': False,
            'error': 'Pagination error',
            'data': data
        })


# Export all pagination classes
__all__ = [
    # Base pagination
    'AdNetworksPagination',
    
    # Specific pagination classes
    'OfferPagination',
    'ConversionPagination',
    'RewardPagination',
    'UserEngagementPagination',
    'NetworkPagination',
    'CursorPagination',
    'CachedPagination',
    'InfiniteScrollPagination',
    'AnalyticsPagination',
    'ExportPagination',
    
    # Advanced pagination
    'HybridPagination',
    'SmartPagination',
    
    # Helper functions
    'get_pagination_class',
    'paginate_response'
]
