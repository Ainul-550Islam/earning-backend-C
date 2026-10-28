# api/referral/pagination.py
# Custom DRF pagination classes for referral module
# ============================================================

from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from collections import OrderedDict


class ReferralPagination(PageNumberPagination):
    """
    Standard referral pagination.
    Default: 20 items/page. Max: 100.
    Response includes metadata + links.
    """
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100
    page_query_param      = 'page'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count',       self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page',self.page.number),
            ('page_size',   self.get_page_size(self.request)),
            ('next',        self.get_next_link()),
            ('previous',    self.get_previous_link()),
            ('results',     data),
        ]))

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'required': ['count', 'results'],
            'properties': {
                'count':       {'type': 'integer'},
                'total_pages': {'type': 'integer'},
                'current_page':{'type': 'integer'},
                'next':        {'type': 'string', 'nullable': True, 'format': 'uri'},
                'previous':    {'type': 'string', 'nullable': True, 'format': 'uri'},
                'results':     schema,
            },
        }


class SmallReferralPagination(ReferralPagination):
    """For compact lists — 10 items/page."""
    page_size     = 10
    max_page_size = 50


class LargeReferralPagination(ReferralPagination):
    """For export-like endpoints — 50 items/page."""
    page_size     = 50
    max_page_size = 500


class LeaderboardPagination(PageNumberPagination):
    """
    Leaderboard pagination — always returns full page of 50.
    No adjustable page_size (leaderboard is fixed-size).
    """
    page_size     = 50
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count',    self.page.paginator.count),
            ('next',     self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('period',   self.request.query_params.get('period', 'weekly')),
            ('results',  data),
        ]))


class CursorReferralPagination(CursorPagination):
    """
    Cursor-based pagination for high-volume endpoints.
    More efficient than page-number for large datasets.
    Use for: commission history, earning logs.
    """
    page_size             = 20
    ordering              = '-created_at'
    cursor_query_param    = 'cursor'
    page_size_query_param = 'page_size'
    max_page_size         = 100

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('next',     self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results',  data),
        ]))


class CommissionPagination(CursorReferralPagination):
    """For commission log — cursor-based for large datasets."""
    page_size = 25
    ordering  = '-created_at'


class AdminReferralPagination(LargeReferralPagination):
    """For admin views — larger page size."""
    page_size     = 100
    max_page_size = 1000