"""
Pagination classes for Telemetry Observability.

Wired in settings/base.py → REST_FRAMEWORK['DEFAULT_PAGINATION_CLASS'].
DRY: all pagination logic here — never re-implemented in views.

All paginators return the same envelope structure:
  {
    "count":    <total>,
    "next":     <url | null>,
    "previous": <url | null>,
    "page":     <current_page>,
    "pages":    <total_pages>,
    "results":  [...]
  }
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


# ── Base ──────────────────────────────────────────────────────────────────────

class TelemetryPageNumberPagination(PageNumberPagination):
    """
    Default page-number pagination used by all viewsets.
    Client controls page size via ?page_size=N (max: 200).
    """
    page_size              = 50
    page_size_query_param  = 'page_size'
    max_page_size          = 200
    page_query_param       = 'page'

    def get_paginated_response(self, data):
        return Response({
            'count':    self.page.paginator.count,
            'next':     self.get_next_link(),
            'previous': self.get_previous_link(),
            'page':     self.page.number,
            'pages':    self.page.paginator.num_pages,
            'results':  data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count':    {'type': 'integer'},
                'next':     {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'page':     {'type': 'integer'},
                'pages':    {'type': 'integer'},
                'results':  schema,
            },
        }


# ── Domain-specific page sizes ────────────────────────────────────────────────

class MetricPagination(TelemetryPageNumberPagination):
    """Metrics: larger pages for dashboard charting (default 100)."""
    page_size     = 100
    max_page_size = 1000


class LogPagination(TelemetryPageNumberPagination):
    """Logs: smaller pages for log viewers (default 50)."""
    page_size     = 50
    max_page_size = 500


class AlertPagination(TelemetryPageNumberPagination):
    """Alerts: small pages for alert consoles (default 25)."""
    page_size     = 25
    max_page_size = 200


class TracePagination(TelemetryPageNumberPagination):
    """Traces: medium pages (default 50)."""
    page_size     = 50
    max_page_size = 500


class HealthPagination(TelemetryPageNumberPagination):
    """Health statuses: one row per service, usually small (default 50)."""
    page_size     = 50
    max_page_size = 200


# ── Cursor pagination for time-series feeds ───────────────────────────────────

class MetricCursorPagination(CursorPagination):
    """
    Cursor-based pagination for real-time metric feeds.
    More efficient than page-number for large, fast-growing datasets.
    Use on /metrics/feed/ or WebSocket-backed endpoints.
    """
    page_size     = 100
    ordering      = '-timestamp'
    cursor_query_param = 'cursor'
