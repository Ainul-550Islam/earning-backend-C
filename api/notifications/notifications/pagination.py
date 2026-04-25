# earning_backend/api/notifications/pagination.py
"""
Pagination classes for notification endpoints.
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


class NotificationPagination(PageNumberPagination):
    """Standard notification list pagination."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.get_page_size(self.request),
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
                'page_size': {'type': 'integer'},
                'results': schema,
            },
        }


class LargeNotificationPagination(PageNumberPagination):
    """For admin/analytics endpoints with more results."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })


class NotificationCursorPagination(CursorPagination):
    """
    Cursor-based pagination for real-time notification feeds.
    More efficient for large datasets — no OFFSET queries.
    """
    page_size = 20
    ordering = '-created_at'
    cursor_query_param = 'cursor'
    page_size_query_param = 'page_size'
    max_page_size = 50


class InAppMessagePagination(PageNumberPagination):
    """Small page size for in-app message popups."""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'unread_count': self._unread_count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })

    def paginate_queryset(self, queryset, request, view=None):
        self._unread_count = queryset.filter(is_read=False, is_dismissed=False).count()
        return super().paginate_queryset(queryset, request, view)


class AnalyticsPagination(PageNumberPagination):
    """For analytics/insight endpoints."""
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 365  # Max 1 year of daily data
