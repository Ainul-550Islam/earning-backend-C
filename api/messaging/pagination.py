"""
Messaging Pagination — Custom DRF pagination classes.

All page-size values are pulled from constants.py so there is one
authoritative place to change limits.

Usage (settings.py):
    REST_FRAMEWORK = {
        "DEFAULT_PAGINATION_CLASS": "messaging.pagination.StandardResultsPagination",
        "PAGE_SIZE": 20,
    }

Or per-viewset:
    class InternalChatViewSet(viewsets.GenericViewSet):
        pagination_class = StandardResultsPagination

Wire up:
    Add to settings.py REST_FRAMEWORK dict:
        "DEFAULT_PAGINATION_CLASS": "messaging.pagination.StandardResultsPagination",
        "PAGE_SIZE": 20,
"""
from __future__ import annotations

from rest_framework.pagination import (
    PageNumberPagination,
    CursorPagination,
    LimitOffsetPagination,
)
from rest_framework.response import Response

from .constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MAX_MESSAGES_FETCH,
    MAX_SEARCH_RESULTS,
)


# ── 1. Standard page-number pagination ───────────────────────────────────────

class StandardResultsPagination(PageNumberPagination):
    """
    Default pagination for all list endpoints.

    Client can override page size with ?page_size=N (capped at MAX_PAGE_SIZE).
    Response envelope:
        {
            "count":    <total>,
            "next":     "<url|null>",
            "previous": "<url|null>",
            "results":  [...]
        }
    """

    page_size            = DEFAULT_PAGE_SIZE   # 20
    page_size_query_param = "page_size"
    max_page_size        = MAX_PAGE_SIZE       # 100
    page_query_param     = "page"
    last_page_strings    = ("last",)

    def get_paginated_response(self, data):
        return Response({
            "count":    self.page.paginator.count,
            "next":     self.get_next_link(),
            "previous": self.get_previous_link(),
            "total_pages": self.page.paginator.num_pages,
            "results":  data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["count", "results"],
            "properties": {
                "count":       {"type": "integer", "example": 100},
                "next":        {"type": "string",  "nullable": True, "format": "uri"},
                "previous":    {"type": "string",  "nullable": True, "format": "uri"},
                "total_pages": {"type": "integer", "example": 5},
                "results":     schema,
            },
        }


# ── 2. Cursor pagination for real-time chat messages ─────────────────────────

class MessageCursorPagination(CursorPagination):
    """
    Cursor-based pagination for chat message lists.

    Cursor pagination is stable under concurrent inserts — ideal for
    chat where new messages arrive between page requests.

    Default order: newest first (descending created_at).
    Client flips to oldest-first by passing ?ordering=created_at.

    Response envelope adds `oldest_unread_cursor` when the view
    injects it (optional; omitted otherwise).
    """

    page_size            = DEFAULT_PAGE_SIZE   # 20 messages per page
    page_size_query_param = "page_size"
    max_page_size        = MAX_MESSAGES_FETCH  # 200 hard cap
    ordering             = "-created_at"       # newest first by default
    cursor_query_param   = "cursor"

    def get_paginated_response(self, data):
        return Response({
            "next":     self.get_next_link(),
            "previous": self.get_previous_link(),
            "results":  data,
        })


# ── 3. Limit-offset pagination for admin / search endpoints ──────────────────

class LargeResultsPagination(LimitOffsetPagination):
    """
    Limit-offset pagination for admin list views and search results.

    Allows clients to request larger batches (up to MAX_PAGE_SIZE) and
    use offset-based navigation — useful for data-export workflows.
    """

    default_limit = DEFAULT_PAGE_SIZE   # 20
    max_limit     = MAX_PAGE_SIZE       # 100


class SearchResultsPagination(PageNumberPagination):
    """
    Pagination for full-text search results.

    Lower page size because search hits are expensive.
    Hard-capped at MAX_SEARCH_RESULTS (50) regardless of ?page_size.
    """

    page_size            = 20
    page_size_query_param = "page_size"
    max_page_size        = MAX_SEARCH_RESULTS  # 50

    def get_paginated_response(self, data):
        return Response({
            "count":    self.page.paginator.count,
            "next":     self.get_next_link(),
            "previous": self.get_previous_link(),
            "results":  data,
        })


# ── 4. Small page pagination for inline / nested lists ───────────────────────

class SmallResultsPagination(PageNumberPagination):
    """
    Pagination for nested resource lists (e.g. reactions, poll votes).

    Returns 10 items per page; not configurable by the client.
    """

    page_size = 10
