# api/support/pagination.py
"""
Custom pagination classes for support API.
Full code — no summarizing.
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


class SupportPageNumberPagination(PageNumberPagination):
    """Standard page-number pagination for support list endpoints."""
    page_size              = 20
    page_size_query_param  = 'per_page'
    max_page_size          = 100
    page_query_param       = 'page'

    def get_paginated_response(self, data):
        return Response({
            'count':    self.page.paginator.count,
            'pages':    self.page.paginator.num_pages,
            'page':     self.page.number,
            'per_page': self.get_page_size(self.request),
            'has_next': self.page.has_next(),
            'has_prev': self.page.has_previous(),
            'next':     self.get_next_link(),
            'previous': self.get_previous_link(),
            'results':  data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count':    {'type': 'integer'},
                'pages':    {'type': 'integer'},
                'page':     {'type': 'integer'},
                'per_page': {'type': 'integer'},
                'has_next': {'type': 'boolean'},
                'has_prev': {'type': 'boolean'},
                'results':  schema,
            }
        }


class SupportCursorPagination(CursorPagination):
    """
    Cursor-based pagination for high-volume endpoints.
    More efficient for large datasets (chat messages, audit logs).
    """
    page_size             = 50
    page_size_query_param = 'per_page'
    max_page_size         = 200
    ordering              = '-created_at'

    def get_paginated_response(self, data):
        return Response({
            'count':    len(data),
            'next':     self.get_next_link(),
            'previous': self.get_previous_link(),
            'results':  data,
        })


class SmallPagePagination(SupportPageNumberPagination):
    """Small pages for admin dropdowns and autocomplete."""
    page_size     = 10
    max_page_size = 50


class LargePagePagination(SupportPageNumberPagination):
    """Large pages for exports and full data fetches."""
    page_size     = 100
    max_page_size = 500


class ChatMessagePagination(SupportCursorPagination):
    """Cursor pagination for chat messages — newest last."""
    page_size = 50
    ordering  = 'created_at'  # Ascending for chat


class TicketMessagePagination(SupportCursorPagination):
    """Cursor pagination for ticket message thread."""
    page_size = 30
    ordering  = 'created_at'