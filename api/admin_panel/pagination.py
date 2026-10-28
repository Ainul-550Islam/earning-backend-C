# api/admin_panel/pagination.py
"""
Custom pagination classes for admin_panel viewsets.
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from collections import OrderedDict


# ==================== Standard Admin Pagination ====================

class AdminPagination(PageNumberPagination):
    """
    Default pagination for admin viewsets.
    Supports ?page= and ?page_size= query params.
    Returns meta with total_pages, total_count, current_page.
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200
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
                'count': {'type': 'integer', 'example': 123},
                'total_pages': {'type': 'integer', 'example': 5},
                'current_page': {'type': 'integer', 'example': 1},
                'page_size': {'type': 'integer', 'example': 25},
                'next': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'previous': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'results': schema,
            },
        }


# ==================== Large Dataset Pagination ====================

class LargeDatasetPagination(AdminPagination):
    """
    For large datasets like activity logs and exports.
    Smaller default, allows larger max.
    """
    page_size = 50
    max_page_size = 500


# ==================== Small List Pagination ====================

class SmallListPagination(AdminPagination):
    """
    For small lists like widgets, quick actions, config keys.
    """
    page_size = 10
    max_page_size = 100


# ==================== Cursor-Based Pagination ====================

class AdminCursorPagination(CursorPagination):
    """
    Cursor-based pagination for real-time activity feeds.
    More efficient for high-frequency writes.
    """
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_at'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('count', len(data)),
            ('results', data),
        ]))


# ==================== Dashboard Metrics Pagination ====================

class MetricsPagination(AdminPagination):
    """
    For dashboard metrics endpoints.
    """
    page_size = 20
    max_page_size = 100


# ==================== Report List Pagination ====================

class ReportPagination(AdminPagination):
    """
    For report lists.
    """
    page_size = 15
    max_page_size = 100


# ==================== Export List Pagination ====================

class ExportPagination(AdminPagination):
    """
    For data export history.
    """
    page_size = 20
    max_page_size = 200


# ==================== Search Results Pagination ====================

class SearchResultsPagination(AdminPagination):
    """
    For global search results.
    """
    page_size = 30
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('query', self.request.query_params.get('q', '')),
            ('results', data),
        ]))