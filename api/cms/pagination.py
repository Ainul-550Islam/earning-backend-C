# api/cms/pagination.py
"""Custom pagination classes for CMS."""
import logging
from typing import Any, Dict, List, Optional, Union
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
from django.http import Http404
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination, CursorPagination
from rest_framework.response import Response
from rest_framework.utils import serializer_helpers

logger = logging.getLogger(__name__)


# ── Original Pagination Classes (Enhanced) ─────────────────────────────────────

class CMSPagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'total_pages': {'type': 'integer'},
                'current_page': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': schema,
            }
        }


class CMSSmallPagination(CMSPagePagination):
    page_size = 10
    max_page_size = 50


class CMSLargePagination(CMSPagePagination):
    page_size = 50
    max_page_size = 200


class CMSCursorPagination(CursorPagination):
    """Cursor-based pagination for high-traffic feeds (offers, notifications)."""
    page_size = 20
    max_page_size = 100
    cursor_query_param = 'cursor'
    ordering = '-created_at'


# ── Enhanced Pagination Classes ─────────────────────────────────────

class BaseCMSPagination:
    """Base pagination class for CMS with common functionality."""
    
    def __init__(self):
        self.page_size = getattr(settings, 'CMS_DEFAULT_PAGE_SIZE', 20)
        self.max_page_size = getattr(settings, 'CMS_MAX_PAGE_SIZE', 100)
        self.page_query_param = 'page'
        self.page_size_query_param = 'page_size'
    
    def get_page_size(self, request) -> int:
        """Get page size from request."""
        try:
            page_size = int(request.query_params.get(self.page_size_query_param, self.page_size))
            if page_size <= 0:
                return self.page_size
            return min(page_size, self.max_page_size)
        except (ValueError, TypeError):
            return self.page_size
    
    def get_page_number(self, request) -> int:
        """Get page number from request."""
        try:
            return int(request.query_params.get(self.page_query_param, 1))
        except (ValueError, TypeError):
            return 1


class CMSLimitOffsetPagination(LimitOffsetPagination):
    """Enhanced limit offset pagination for CMS."""
    
    default_limit = 20
    max_limit = 100
    
    def get_limit(self, request):
        """Get limit with validation."""
        limit = super().get_limit(request)
        return min(limit, self.max_limit)
    
    def get_paginated_response(self, data):
        """Get paginated response with additional metadata."""
        return Response({
            'count': self.count,
            'limit': self.limit,
            'offset': self.offset,
            'has_next': self.offset + self.limit < self.count,
            'has_previous': self.offset > 0,
            'next_offset': self.offset + self.limit if self.offset + self.limit < self.count else None,
            'previous_offset': max(0, self.offset - self.limit) if self.offset > 0 else None,
            'results': data
        })


# ── Specialized Pagination Classes ─────────────────────────────────────

class CMSSurveyPagination(CMSPagePagination):
    """Pagination optimized for surveys."""
    
    page_size = 10
    max_page_size = 50
    
    def get_paginated_response(self, data):
        """Get paginated response with survey-specific metadata."""
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'next_page': self.page.next_page_number() if self.page.has_next() else None,
            'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
            'results': data,
            'metadata': {
                'type': 'surveys',
                'total_surveys': self.page.paginator.count,
                'surveys_per_page': self.page_size
            }
        })


class CMSRewardPagination(CMSPagePagination):
    """Pagination optimized for rewards."""
    
    page_size = 25
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Get paginated response with reward-specific metadata."""
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'next_page': self.page.next_page_number() if self.page.has_next() else None,
            'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
            'results': data,
            'metadata': {
                'type': 'rewards',
                'total_transactions': self.page.paginator.count,
                'transactions_per_page': self.page_size
            }
        })


class CMSUserPagination(CMSPagePagination):
    """Pagination optimized for users."""
    
    page_size = 30
    max_page_size = 200
    
    def get_paginated_response(self, data):
        """Get paginated response with user-specific metadata."""
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'next_page': self.page.next_page_number() if self.page.has_next() else None,
            'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
            'results': data,
            'metadata': {
                'type': 'users',
                'total_users': self.page.paginator.count,
                'users_per_page': self.page_size
            }
        })


class CMSAnalyticsPagination(CMSPagePagination):
    """Pagination optimized for analytics data."""
    
    page_size = 50
    max_page_size = 500
    
    def get_paginated_response(self, data):
        """Get paginated response with analytics-specific metadata."""
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'next_page': self.page.next_page_number() if self.page.has_next() else None,
            'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
            'results': data,
            'metadata': {
                'type': 'analytics',
                'total_records': self.page.paginator.count,
                'records_per_page': self.page_size
            }
        })


# ── Infinite Scroll Pagination ─────────────────────────────────────

class CMSInfiniteScrollPagination(CursorPagination):
    """Pagination for infinite scroll interfaces."""
    
    page_size = 20
    max_page_size = 100
    cursor_query_param = 'after'
    ordering = '-created_at'
    
    def get_paginated_response(self, data):
        """Get paginated response optimized for infinite scroll."""
        return Response({
            'data': data,
            'paging': {
                'next': self.get_next_link(),
                'has_next': self.has_next,
                'page_size': self.page_size
            }
        })


# ── Search Results Pagination ─────────────────────────────────────

class CMSSearchPagination(CMSPagePagination):
    """Pagination optimized for search results."""
    
    page_size = 15
    max_page_size = 50
    
    def get_paginated_response(self, data):
        """Get paginated response with search-specific metadata."""
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'next_page': self.page.next_page_number() if self.page.has_next() else None,
            'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
            'results': data,
            'search_metadata': {
                'total_results': self.page.paginator.count,
                'results_per_page': self.page_size,
                'showing_from': (self.page.number - 1) * self.page_size + 1,
                'showing_to': min(self.page.number * self.page_size, self.page.paginator.count)
            }
        })


# ── Pagination Utilities ─────────────────────────────────────

class PaginationUtils:
    """Utilities for pagination."""
    
    @staticmethod
    def get_pagination_config(request, default_page_size=20, max_page_size=100) -> Dict[str, int]:
        """Get pagination configuration from request."""
        try:
            page_size = int(request.query_params.get('page_size', default_page_size))
            page_size = max(1, min(page_size, max_page_size))
        except (ValueError, TypeError):
            page_size = default_page_size
        
        try:
            page = int(request.query_params.get('page', 1))
            page = max(1, page)
        except (ValueError, TypeError):
            page = 1
        
        return {
            'page': page,
            'page_size': page_size,
            'offset': (page - 1) * page_size
        }
    
    @staticmethod
    def create_pagination_metadata(count: int, page: int, page_size: int) -> Dict[str, Any]:
        """Create pagination metadata."""
        total_pages = (count + page_size - 1) // page_size
        
        return {
            'count': count,
            'total_pages': total_pages,
            'current_page': page,
            'page_size': page_size,
            'has_next': page < total_pages,
            'has_previous': page > 1,
            'next_page': page + 1 if page < total_pages else None,
            'previous_page': page - 1 if page > 1 else None,
            'showing_from': (page - 1) * page_size + 1,
            'showing_to': min(page * page_size, count)
        }
    
    @staticmethod
    def paginate_queryset(queryset, page: int, page_size: int) -> tuple:
        """Paginate queryset and return page and metadata."""
        from django.core.paginator import Paginator
        
        paginator = Paginator(queryset, page_size)
        
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        
        metadata = PaginationUtils.create_pagination_metadata(
            paginator.count, page_obj.number, page_size
        )
        
        return page_obj, metadata


# ── Pagination Configuration ─────────────────────────────────────

class PaginationConfig:
    """Configuration for pagination system."""
    
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    DEFAULT_PAGE_QUERY_PARAM = 'page'
    DEFAULT_PAGE_SIZE_QUERY_PARAM = 'page_size'
    
    # Pagination types
    PAGE_NUMBER = 'page_number'
    LIMIT_OFFSET = 'limit_offset'
    CURSOR = 'cursor'
    INFINITE_SCROLL = 'infinite_scroll'
    
    # Specialized pagination classes
    SURVEY_PAGINATION = 'survey'
    REWARD_PAGINATION = 'reward'
    USER_PAGINATION = 'user'
    ANALYTICS_PAGINATION = 'analytics'
    SEARCH_PAGINATION = 'search'
    
    @classmethod
    def get_pagination_class(cls, pagination_type: str):
        """Get pagination class by type."""
        pagination_classes = {
            cls.PAGE_NUMBER: CMSPagePagination,
            cls.LIMIT_OFFSET: CMSLimitOffsetPagination,
            cls.CURSOR: CMSCursorPagination,
            cls.INFINITE_SCROLL: CMSInfiniteScrollPagination,
            cls.SURVEY_PAGINATION: CMSSurveyPagination,
            cls.REWARD_PAGINATION: CMSRewardPagination,
            cls.USER_PAGINATION: CMSUserPagination,
            cls.ANALYTICS_PAGINATION: CMSAnalyticsPagination,
            cls.SEARCH_PAGINATION: CMSSearchPagination,
        }
        
        return pagination_classes.get(pagination_type, CMSPagePagination)
    
    @classmethod
    def get_settings_config(cls) -> Dict[str, Any]:
        """Get configuration from Django settings."""
        from django.conf import settings
        
        return {
            'default_page_size': getattr(settings, 'CMS_DEFAULT_PAGE_SIZE', cls.DEFAULT_PAGE_SIZE),
            'max_page_size': getattr(settings, 'CMS_MAX_PAGE_SIZE', cls.MAX_PAGE_SIZE),
            'page_query_param': getattr(settings, 'CMS_PAGE_QUERY_PARAM', cls.DEFAULT_PAGE_QUERY_PARAM),
            'page_size_query_param': getattr(settings, 'CMS_PAGE_SIZE_QUERY_PARAM', cls.DEFAULT_PAGE_SIZE_QUERY_PARAM),
        }
    ordering = '-created_at'
    cursor_query_param = 'cursor'


class LeaderboardPagination(CMSPagePagination):
    page_size = 10
    max_page_size = 100


class TransactionHistoryPagination(CMSCursorPagination):
    page_size = 30
    ordering = '-created_at'


class ConversionLogPagination(CMSPagePagination):
    page_size = 50
    max_page_size = 500
