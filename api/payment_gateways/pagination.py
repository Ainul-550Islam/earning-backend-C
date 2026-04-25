# api/payment_gateways/pagination.py
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size             = 25
    page_size_query_param = 'page_size'
    max_page_size         = 200

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'count':   self.page.paginator.count,
            'pages':   self.page.paginator.num_pages,
            'next':    self.get_next_link(),
            'previous':self.get_previous_link(),
            'data':    data,
        })


class TransactionPagination(StandardPagination):
    page_size = 20


class SmallPagination(StandardPagination):
    page_size = 10


class LargePagination(StandardPagination):
    page_size     = 100
    max_page_size = 1000


class CursorTransactionPagination(CursorPagination):
    """Cursor-based pagination for real-time transaction feeds."""
    page_size      = 20
    ordering       = '-created_at'
    cursor_query_param = 'cursor'
