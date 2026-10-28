"""
api/tasks/pagination.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Custom DRF pagination classes for the task system.
"""

from rest_framework.pagination import (
    PageNumberPagination, CursorPagination, LimitOffsetPagination
)
from rest_framework.response import Response
from django.utils import timezone


class StandardTaskPagination(PageNumberPagination):
    """
    Standard pagination for most task endpoints.
    Default: 20 items per page. Max: 100.
    """
    page_size              = 20
    page_size_query_param  = 'page_size'
    max_page_size          = 100
    page_query_param       = 'page'

    def get_paginated_response(self, data):
        return Response({
            'pagination': {
                'count':    self.page.paginator.count,
                'page':     self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'page_size': self.get_page_size(self.request),
                'next':     self.get_next_link(),
                'previous': self.get_previous_link(),
            },
            'results': data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'count':        {'type': 'integer'},
                        'page':         {'type': 'integer'},
                        'total_pages':  {'type': 'integer'},
                        'page_size':    {'type': 'integer'},
                        'next':         {'type': 'string', 'nullable': True},
                        'previous':     {'type': 'string', 'nullable': True},
                    },
                },
                'results': schema,
            },
        }


class LargeBatchPagination(PageNumberPagination):
    """
    Larger page sizes for admin/bulk endpoints.
    Default: 100. Max: 1000.
    """
    page_size              = 100
    page_size_query_param  = 'page_size'
    max_page_size          = 1000
    page_query_param       = 'page'


class MonitoringPagination(PageNumberPagination):
    """
    Pagination for monitoring data (performance logs, queue depths).
    Default: 50. Max: 200.
    """
    page_size              = 50
    page_size_query_param  = 'page_size'
    max_page_size          = 200


class CursorTaskPagination(CursorPagination):
    """
    Cursor-based pagination for real-time streams (event logs, notifications).
    Efficient for large datasets where offset becomes slow.
    """
    page_size              = 20
    page_size_query_param  = 'page_size'
    max_page_size          = 100
    ordering               = '-created_at'
    cursor_query_param     = 'cursor'

    def get_paginated_response(self, data):
        return Response({
            'pagination': {
                'next':     self.get_next_link(),
                'previous': self.get_previous_link(),
                'page_size': self.get_page_size(self.request),
            },
            'results': data,
        })


class AnalyticsPagination(LimitOffsetPagination):
    """
    Limit/offset pagination for analytics endpoints.
    Allows arbitrary slicing of time-series data.
    Default: 30 data points. Max: 365.
    """
    default_limit  = 30
    max_limit      = 365
    limit_query_param  = 'limit'
    offset_query_param = 'offset'

    def get_paginated_response(self, data):
        return Response({
            'pagination': {
                'count':   self.count,
                'limit':   self.limit,
                'offset':  self.offset,
                'next':    self.get_next_link(),
                'previous': self.get_previous_link(),
            },
            'results': data,
        })


class LeaderboardPagination(PageNumberPagination):
    """
    Pagination for leaderboard endpoints.
    Default: top 100. Max: 1000.
    """
    page_size             = 100
    page_size_query_param = 'page_size'
    max_page_size         = 1000
    ordering              = '-total_earned'


class DLQPagination(PageNumberPagination):
    """
    Pagination for Dead Letter Queue entries.
    Default: 50. Max: 200.
    Shows oldest first (FIFO) for processing.
    """
    page_size             = 50
    page_size_query_param = 'page_size'
    max_page_size         = 200


class ReportPagination(LimitOffsetPagination):
    """
    Pagination for report downloads.
    Default: 1000 rows. Max: 50000.
    """
    default_limit  = 1000
    max_limit      = 50000


__all__ = [
    'StandardTaskPagination', 'LargeBatchPagination', 'MonitoringPagination',
    'CursorTaskPagination', 'AnalyticsPagination', 'LeaderboardPagination',
    'DLQPagination', 'ReportPagination',
]
