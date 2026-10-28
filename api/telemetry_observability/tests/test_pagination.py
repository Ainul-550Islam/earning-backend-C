"""
Tests for pagination.py — envelope shape and page size control.
"""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework.test import APIRequestFactory

from ..pagination import (
    TelemetryPageNumberPagination,
    MetricPagination, LogPagination,
    AlertPagination, TracePagination, HealthPagination,
    MetricCursorPagination,
)


def make_paginator(cls=TelemetryPageNumberPagination, page_size=None):
    p = cls()
    if page_size:
        p.page_size = page_size
    return p


class TestTelemetryPageNumberPagination:
    def test_default_page_size(self):
        p = TelemetryPageNumberPagination()
        assert p.page_size == 50

    def test_max_page_size(self):
        p = TelemetryPageNumberPagination()
        assert p.max_page_size == 200

    def test_page_size_query_param(self):
        p = TelemetryPageNumberPagination()
        assert p.page_size_query_param == 'page_size'

    def test_paginated_response_envelope(self):
        """Response must include count, next, previous, page, pages, results."""
        factory = APIRequestFactory()
        request = factory.get('/test/?page=1')
        from rest_framework.request import Request
        drf_request = Request(request)

        paginator = TelemetryPageNumberPagination()
        # Simulate paginate_queryset
        from django.core.paginator import Paginator
        data    = list(range(100))
        django_paginator = Paginator(data, 10)
        paginator.page   = django_paginator.page(1)
        paginator.request = drf_request

        response = paginator.get_paginated_response(list(range(10)))
        assert 'count'    in response.data
        assert 'next'     in response.data
        assert 'previous' in response.data
        assert 'page'     in response.data
        assert 'pages'    in response.data
        assert 'results'  in response.data

    def test_schema_includes_all_keys(self):
        p = TelemetryPageNumberPagination()
        schema = p.get_paginated_response_schema({'type': 'array'})
        props  = schema['properties']
        assert 'count'    in props
        assert 'next'     in props
        assert 'previous' in props
        assert 'page'     in props
        assert 'pages'    in props
        assert 'results'  in props


class TestDomainSpecificPaginators:
    def test_metric_pagination_larger_page(self):
        p = MetricPagination()
        assert p.page_size     == 100
        assert p.max_page_size == 1000

    def test_log_pagination(self):
        p = LogPagination()
        assert p.page_size == 50
        assert p.max_page_size == 500

    def test_alert_pagination_smaller_page(self):
        p = AlertPagination()
        assert p.page_size == 25

    def test_trace_pagination(self):
        p = TracePagination()
        assert p.page_size == 50

    def test_health_pagination(self):
        p = HealthPagination()
        assert p.page_size == 50


class TestMetricCursorPagination:
    def test_cursor_pagination_ordering(self):
        p = MetricCursorPagination()
        assert p.ordering == '-timestamp'

    def test_cursor_pagination_page_size(self):
        p = MetricCursorPagination()
        assert p.page_size == 100

    def test_cursor_query_param(self):
        p = MetricCursorPagination()
        assert p.cursor_query_param == 'cursor'
