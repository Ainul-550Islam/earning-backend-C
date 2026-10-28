"""
Gamification Pagination — Custom pagination classes for gamification APIs.

This module provides specialized pagination classes for different gamification
endpoints with customizable page sizes, ordering, and metadata.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.request import Request

logger = logging.getLogger(__name__)


class GamificationPagination(PageNumberPagination):
    """Standard pagination for gamification endpoints."""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response_schema(self, schema):
        """Get paginated response schema."""
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 100
                },
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'results': schema,
                'page_info': {
                    'type': 'object',
                    'properties': {
                        'current_page': {'type': 'integer'},
                        'total_pages': {'type': 'integer'},
                        'page_size': {'type': 'integer'},
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'}
                    }
                }
            }
        }
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return paginated response with enhanced metadata."""
        response_data = {
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'page_info': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'page_size': self.page_size,
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            }
        }
        return Response(response_data)


class BadgePagination(GamificationPagination):
    """Pagination optimized for badge listings."""
    
    page_size = 12
    max_page_size = 48
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Add badge-specific metadata."""
        response = super().get_paginated_response(data)
        
        # Add badge statistics if available
        if hasattr(self, 'badge_stats'):
            response.data['badge_stats'] = self.badge_stats
        
        return response


class LeaderboardPagination(LimitOffsetPagination):
    """Pagination optimized for leaderboards."""
    
    default_limit = 50
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 1000
    
    def get_paginated_response_schema(self, schema):
        """Get paginated response schema for leaderboards."""
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 500
                },
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'results': schema,
                'leaderboard_info': {
                    'type': 'object',
                    'properties': {
                        'current_rank': {'type': 'integer'},
                        'total_entries': {'type': 'integer'},
                        'showing_range': {
                            'type': 'string',
                            'example': '1-50 of 500'
                        }
                    }
                }
            }
        }
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return paginated response with leaderboard-specific metadata."""
        offset = self.offset
        limit = self.limit
        count = self.count
        
        response_data = {
            'count': count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'leaderboard_info': {
                'current_rank': offset + 1 if offset < count else None,
                'total_entries': count,
                'showing_range': f"{offset + 1}-{min(offset + limit, count)} of {count}" if count > 0 else "0 of 0"
            }
        }
        return Response(response_data)


class ChallengePagination(GamificationPagination):
    """Pagination optimized for daily challenges."""
    
    page_size = 7  # One week of challenges
    max_page_size = 30  # One month
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Add challenge-specific metadata."""
        response = super().get_paginated_response(data)
        
        # Add challenge statistics
        if hasattr(self, 'challenge_stats'):
            response.data['challenge_stats'] = self.challenge_stats
        
        return response


class AchievementPagination(GamificationPagination):
    """Pagination optimized for user achievements."""
    
    page_size = 25
    max_page_size = 100
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Add achievement-specific metadata."""
        response = super().get_paginated_response(data)
        
        # Add achievement statistics
        if hasattr(self, 'achievement_stats'):
            response.data['achievement_stats'] = self.achievement_stats
        
        return response


class InfiniteScrollPagination(LimitOffsetPagination):
    """Pagination for infinite scroll interfaces."""
    
    default_limit = 20
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100
    
    def get_paginated_response_schema(self, schema):
        """Get paginated response schema for infinite scroll."""
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 100
                },
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'results': schema,
                'has_more': {
                    'type': 'boolean',
                    'description': 'Whether there are more items to load'
                }
            }
        }
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return response optimized for infinite scroll."""
        has_more = self.offset + self.limit < self.count
        
        response_data = {
            'count': self.count,
            'next': self.get_next_link(),
            'results': data,
            'has_more': has_more
        }
        return Response(response_data)


class CursorPagination:
    """Cursor-based pagination for large datasets."""
    
    def __init__(self, page_size: int = 20, ordering: str = '-created_at'):
        self.page_size = page_size
        self.ordering = ordering
        self.cursor_query_param = 'cursor'
    
    def paginate_queryset(self, queryset: List[Any], request: Request) -> List[Any]:
        """Paginate queryset using cursor."""
        cursor = request.query_params.get(self.cursor_query_param)
        
        if cursor:
            # Parse cursor and filter queryset
            try:
                cursor_data = self._decode_cursor(cursor)
                queryset = self._apply_cursor(queryset, cursor_data)
            except Exception as e:
                logger.error(f"Error parsing cursor: {e}")
                # Fall back to first page
                pass
        
        return list(queryset[:self.page_size + 1])  # +1 to check if there's a next page
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return cursor-based paginated response."""
        has_next = len(data) > self.page_size
        results = data[:self.page_size]
        
        # Generate next cursor if there are more items
        next_cursor = None
        if has_next and results:
            last_item = results[-1]
            next_cursor = self._encode_cursor(last_item)
        
        response_data = {
            'results': results,
            'next_cursor': next_cursor,
            'has_more': has_next
        }
        return Response(response_data)
    
    def _decode_cursor(self, cursor: str) -> Dict[str, Any]:
        """Decode cursor string."""
        import base64
        import json
        
        try:
            decoded = base64.b64decode(cursor).decode('utf-8')
            return json.loads(decoded)
        except Exception as e:
            raise ValueError(f"Invalid cursor format: {e}")
    
    def _encode_cursor(self, item: Any) -> str:
        """Encode cursor from item."""
        import base64
        import json
        
        cursor_data = {
            'id': str(item.id),
            'created_at': item.created_at.isoformat() if hasattr(item, 'created_at') else None,
        }
        
        encoded = json.dumps(cursor_data).encode('utf-8')
        return base64.b64encode(encoded).decode('utf-8')
    
    def _apply_cursor(self, queryset: List[Any], cursor_data: Dict[str, Any]) -> List[Any]:
        """Apply cursor filtering to queryset."""
        # This is a simplified implementation
        # In practice, you'd use database-specific cursor pagination
        item_id = cursor_data.get('id')
        
        if item_id:
            # Find the position of the cursor item and return items after it
            for i, item in enumerate(queryset):
                if str(item.id) == item_id:
                    return queryset[i + 1:]
        
        return queryset


class HybridPagination:
    """Hybrid pagination supporting multiple pagination types."""
    
    def __init__(self, default_type: str = 'page'):
        self.default_type = default_type
        self.pagination_types = {
            'page': GamificationPagination,
            'offset': LimitOffsetPagination,
            'cursor': CursorPagination,
            'infinite': InfiniteScrollPagination,
        }
    
    def get_pagination_class(self, request: Request) -> type:
        """Get pagination class based on request parameters."""
        pagination_type = request.query_params.get('pagination_type', self.default_type)
        
        if pagination_type in self.pagination_types:
            return self.pagination_types[pagination_type]
        
        return self.pagination_types[self.default_type]
    
    def paginate(self, queryset: List[Any], request: Request) -> Response:
        """Paginate using the appropriate pagination class."""
        pagination_class = self.get_pagination_class(request)
        
        if pagination_class in [CursorPagination]:
            # Handle cursor-based pagination
            paginator = pagination_class()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            return paginator.get_paginated_response(paginated_queryset)
        else:
            # Handle standard DRF pagination
            paginator = pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            if page is not None:
                serializer = getattr(self, 'serializer_class', None)
                if serializer:
                    data = serializer(page, many=True).data
                else:
                    data = page
                return paginator.get_paginated_response(data)
            
            # Return unpaginated response if pagination is disabled
            return Response(queryset)


class MetadataPagination(GamificationPagination):
    """Pagination with rich metadata support."""
    
    def __init__(self, metadata_fields: Optional[List[str]] = None):
        super().__init__()
        self.metadata_fields = metadata_fields or []
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Return response with custom metadata."""
        response = super().get_paginated_response(data)
        
        # Add custom metadata
        metadata = {}
        
        for field in self.metadata_fields:
            if hasattr(self, field):
                metadata[field] = getattr(self, field)
        
        if metadata:
            response.data['metadata'] = metadata
        
        return response


class SearchPagination(GamificationPagination):
    """Pagination optimized for search results."""
    
    page_size = 20
    max_page_size = 100
    
    def get_paginated_response(self, data: List[Any]) -> Response:
        """Add search-specific metadata."""
        response = super().get_paginated_response(data)
        
        # Add search statistics
        if hasattr(self, 'search_stats'):
            response.data['search_info'] = {
                'query': self.search_stats.get('query', ''),
                'total_results': self.search_stats.get('total_results', 0),
                'search_time': self.search_stats.get('search_time', 0),
                'filters_applied': self.search_stats.get('filters_applied', []),
            }
        
        return response


# Utility functions for pagination
def get_pagination_class_for_model(model_name: str) -> type:
    """Get appropriate pagination class for a model."""
    pagination_mapping = {
        'Badge': BadgePagination,
        'UserBadge': BadgePagination,
        'LeaderboardSnapshot': LeaderboardPagination,
        'DailyChallenge': ChallengePagination,
        'UserDailyChallenge': ChallengePagination,
        'UserAchievement': AchievementPagination,
    }
    
    return pagination_mapping.get(model_name, GamificationPagination)


def create_pagination_response(
    queryset: List[Any],
    request: Request,
    pagination_class: Optional[type] = None,
    serializer_class: Optional[type] = None
) -> Response:
    """Create paginated response with optional serializer."""
    if pagination_class is None:
        pagination_class = GamificationPagination
    
    paginator = pagination_class()
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        if serializer_class:
            data = serializer_class(page, many=True).data
        else:
            data = page
        return paginator.get_paginated_response(data)
    
    # Return unpaginated response
    if serializer_class:
        data = serializer_class(queryset, many=True).data
    else:
        data = queryset
    
    return Response(data)
