# api/djoyalty/pagination.py
"""
Custom DRF Pagination classes for Djoyalty।
Standardized response format সহ।
"""

import logging
from collections import OrderedDict
from rest_framework.pagination import (
    PageNumberPagination,
    CursorPagination,
    LimitOffsetPagination,
)
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# ==================== STANDARD PAGE PAGINATION ====================

class DjoyaltyPagePagination(PageNumberPagination):
    """
    Standard page-based pagination।
    Query params: ?page=1&page_size=20
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
        ]))

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer', 'example': 100},
                'total_pages': {'type': 'integer', 'example': 5},
                'current_page': {'type': 'integer', 'example': 1},
                'page_size': {'type': 'integer', 'example': 20},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': schema,
            },
        }


class SmallPagePagination(DjoyaltyPagePagination):
    """
    Smaller lists এর জন্য।
    Default: 10 per page।
    """
    page_size = 10
    max_page_size = 50


class LargePagePagination(DjoyaltyPagePagination):
    """
    Exports এর জন্য।
    Default: 100 per page।
    """
    page_size = 100
    max_page_size = 500


# ==================== CURSOR PAGINATION ====================

class DjoyaltyCursorPagination(CursorPagination):
    """
    Cursor-based pagination — infinite scroll এর জন্য।
    Fast, tamper-proof।
    Default ordering: newest first।
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_at'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', None),  # cursor pagination এ count নেই
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
        ]))


class TxnCursorPagination(DjoyaltyCursorPagination):
    """Transaction list cursor pagination।"""
    ordering = '-timestamp'
    page_size = 30


class EventCursorPagination(DjoyaltyCursorPagination):
    """Event list cursor pagination।"""
    ordering = '-timestamp'
    page_size = 50


class LedgerCursorPagination(DjoyaltyCursorPagination):
    """Points ledger cursor pagination।"""
    ordering = '-created_at'
    page_size = 50


# ==================== LIMIT-OFFSET PAGINATION ====================

class DjoyaltyLimitOffsetPagination(LimitOffsetPagination):
    """
    Limit-offset pagination — API consumers এর জন্য flexible।
    Query params: ?limit=20&offset=40
    """
    default_limit = 20
    max_limit = 100
    limit_query_param = 'limit'
    offset_query_param = 'offset'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('limit', self.limit),
            ('offset', self.offset),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
        ]))


# ==================== LEADERBOARD PAGINATION ====================

class LeaderboardPagination(DjoyaltyPagePagination):
    """
    Leaderboard এর জন্য।
    Rank information সহ।
    """
    page_size = 10
    max_page_size = 50

    def get_paginated_response(self, data):
        # Rank offset add করো
        offset = (self.page.number - 1) * self.get_page_size(self.request)
        for i, item in enumerate(data):
            if isinstance(item, dict):
                item['rank'] = offset + i + 1
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
        ]))


# ==================== NO PAGINATION ====================

class NoPagination:
    """
    Pagination disable — সব results একসাথে।
    শুধু ছোট list এর জন্য ব্যবহার করো।
    """
    def paginate_queryset(self, queryset, request, view=None):
        return None

    def get_paginated_response(self, data):
        return Response(data)


# ==================== RESPONSE MIXIN ====================

class PaginatedResponseMixin:
    """
    ViewSet এ mixin হিসেবে যোগ করলে
    consistent paginated response পাওয়া যাবে।
    """
    pagination_class = DjoyaltyPagePagination

    def get_paginated_list_response(self, queryset, serializer_class=None, **kwargs):
        """
        Paginated list response তৈরি করো।
        """
        serializer_cls = serializer_class or self.get_serializer_class()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_cls(page, many=True, context=self.get_serializer_context(), **kwargs)
            return self.get_paginated_response(serializer.data)
        serializer = serializer_cls(queryset, many=True, context=self.get_serializer_context(), **kwargs)
        return Response(serializer.data)
