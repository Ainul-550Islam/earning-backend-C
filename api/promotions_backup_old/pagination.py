# =============================================================================
# api/promotions/pagination.py
# Custom Pagination Classes
# =============================================================================

from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from collections import OrderedDict
from .constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class StandardResultsPagination(PageNumberPagination):
    """Standard page-number pagination — সব সাধারণ list endpoint এর জন্য।"""
    page_size               = DEFAULT_PAGE_SIZE
    page_size_query_param   = 'page_size'
    max_page_size           = MAX_PAGE_SIZE
    page_query_param        = 'page'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count',       self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('next',        self.get_next_link()),
            ('previous',    self.get_previous_link()),
            ('page_size',   self.get_page_size(self.request)),
            ('results',     data),
        ]))

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count':        {'type': 'integer'},
                'total_pages':  {'type': 'integer'},
                'current_page': {'type': 'integer'},
                'next':         {'type': 'string', 'nullable': True},
                'previous':     {'type': 'string', 'nullable': True},
                'page_size':    {'type': 'integer'},
                'results':      schema,
            },
        }


class SmallResultsPagination(PageNumberPagination):
    """Dropdown বা select field এর জন্য ছোট pagination।"""
    page_size               = 10
    page_size_query_param   = 'page_size'
    max_page_size           = 50


class LargeResultsPagination(PageNumberPagination):
    """Analytics বা export এর জন্য বড় pagination।"""
    page_size               = 100
    page_size_query_param   = 'page_size'
    max_page_size           = 500


class TransactionCursorPagination(CursorPagination):
    """Transaction history এর জন্য cursor-based pagination — infinite scroll।"""
