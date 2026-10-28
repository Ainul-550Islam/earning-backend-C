# api/djoyalty/pagination.py
"""
Djoyalty -- custom DRF pagination classes।
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from .constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, LEDGER_PAGE_SIZE


class DjoyaltyPagePagination(PageNumberPagination):
    """
    Standard page-number pagination for most endpoints।
    """
    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = 'page_size'
    max_page_size = MAX_PAGE_SIZE
    page_query_param = 'page'


class LedgerCursorPagination(CursorPagination):
    """
    Cursor-based pagination for PointsLedger -- large datasets এর জন্য।
    Consistent ordering guarantee করে।
    """
    page_size = LEDGER_PAGE_SIZE
    ordering = '-created_at'
    cursor_query_param = 'cursor'


class SmallPagePagination(PageNumberPagination):
    """
    Small page size -- dropdown/autocomplete এর জন্য।
    """
    page_size = 10
    max_page_size = 50


class LargeBatchPagination(PageNumberPagination):
    """
    Large batch pagination -- admin exports এর জন্য।
    """
    page_size = 100
    max_page_size = 1000
    page_size_query_param = 'page_size'
