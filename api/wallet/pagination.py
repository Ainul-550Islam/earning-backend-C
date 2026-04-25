# api/wallet/pagination.py
"""
Pagination classes for the wallet API.
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination, LimitOffsetPagination
from rest_framework.response import Response


class WalletPagePagination(PageNumberPagination):
    """Standard page pagination for wallet lists."""
    page_size              = 20
    page_size_query_param  = "page_size"
    max_page_size          = 200
    page_query_param       = "page"

    def get_paginated_response(self, data):
        return Response({
            "count":        self.page.paginator.count,
            "total_pages":  self.page.paginator.num_pages,
            "page":         self.page.number,
            "page_size":    self.get_page_size(self.request),
            "next":         self.get_next_link(),
            "previous":     self.get_previous_link(),
            "results":      data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            "type":       "object",
            "properties": {
                "count":       {"type": "integer"},
                "total_pages": {"type": "integer"},
                "next":        {"type": "string", "nullable": True},
                "previous":    {"type": "string", "nullable": True},
                "results":     schema,
            },
        }


class TransactionCursorPagination(CursorPagination):
    """
    Cursor pagination for immutable transaction log.
    Most efficient for large, append-only datasets.
    No offset drift when new records are inserted.
    """
    page_size              = 50
    ordering               = "-created_at"
    cursor_query_param     = "cursor"
    page_size_query_param  = "page_size"
    max_page_size          = 200

    def get_paginated_response(self, data):
        return Response({
            "next":     self.get_next_link(),
            "previous": self.get_previous_link(),
            "count":    len(data),
            "results":  data,
        })


class LargePagination(PageNumberPagination):
    """For admin reports needing large page sizes."""
    page_size              = 200
    page_size_query_param  = "page_size"
    max_page_size          = 1000


class SmallPagination(PageNumberPagination):
    """For summaries and dashboards."""
    page_size              = 5
    page_size_query_param  = "page_size"
    max_page_size          = 20


class LimitOffsetWalletPagination(LimitOffsetPagination):
    """Limit-offset for analytics dashboards."""
    default_limit  = 20
    max_limit      = 500

    def get_paginated_response(self, data):
        return Response({
            "count":    self.count,
            "next":     self.get_next_link(),
            "previous": self.get_previous_link(),
            "limit":    self.limit,
            "offset":   self.offset,
            "results":  data,
        })
