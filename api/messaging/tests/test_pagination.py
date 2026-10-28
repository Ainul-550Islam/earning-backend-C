"""
Tests for messaging/pagination.py

Covers:
  - StandardResultsPagination  — page-number, page_size param, max_page_size cap
  - MessageCursorPagination    — cursor-based, ordering, max_page_size cap
  - LargeResultsPagination     — limit-offset, max_limit cap
  - SearchResultsPagination    — page-number, lower max cap
  - SmallResultsPagination     — fixed page_size=10, not client-overridable
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest
from django.test import RequestFactory
TestCase = unittest.TestCase

from ..pagination import (
    StandardResultsPagination,
    MessageCursorPagination,
    LargeResultsPagination,
    SearchResultsPagination,
    SmallResultsPagination,
)
from ..constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MAX_MESSAGES_FETCH, MAX_SEARCH_RESULTS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(params: dict | None = None, method: str = "GET"):
    factory = RequestFactory()
    url = "/"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"/?{qs}"
    request = factory.get(url)
    request.query_params = params or {}
    return request


# ── StandardResultsPagination ─────────────────────────────────────────────────

class TestStandardResultsPagination(TestCase):

    def test_default_page_size_matches_constant(self):
        p = StandardResultsPagination()
        self.assertEqual(p.page_size, DEFAULT_PAGE_SIZE)

    def test_max_page_size_matches_constant(self):
        p = StandardResultsPagination()
        self.assertEqual(p.max_page_size, MAX_PAGE_SIZE)

    def test_page_size_query_param_is_page_size(self):
        p = StandardResultsPagination()
        self.assertEqual(p.page_size_query_param, "page_size")

    def test_page_query_param_is_page(self):
        p = StandardResultsPagination()
        self.assertEqual(p.page_query_param, "page")

    def test_get_paginated_response_contains_count_and_results(self):
        p = StandardResultsPagination()
        mock_page = MagicMock()
        mock_page.paginator.count = 100
        mock_page.paginator.num_pages = 5
        p.page = mock_page
        p.request = _make_request()
        with patch.object(p, "get_next_link", return_value="http://next"),\
             patch.object(p, "get_previous_link", return_value=None):
            response = p.get_paginated_response(["item1", "item2"])
        self.assertEqual(response.data["count"], 100)
        self.assertEqual(response.data["total_pages"], 5)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["next"], "http://next")
        self.assertIsNone(response.data["previous"])

    def test_paginated_response_schema_contains_required_fields(self):
        p = StandardResultsPagination()
        schema = p.get_paginated_response_schema({"type": "array"})
        self.assertIn("count", schema["properties"])
        self.assertIn("results", schema["properties"])
        self.assertIn("total_pages", schema["properties"])
        self.assertIn("count", schema["required"])
        self.assertIn("results", schema["required"])


# ── MessageCursorPagination ───────────────────────────────────────────────────

class TestMessageCursorPagination(TestCase):

    def test_default_page_size_matches_constant(self):
        p = MessageCursorPagination()
        self.assertEqual(p.page_size, DEFAULT_PAGE_SIZE)

    def test_max_page_size_is_max_messages_fetch(self):
        p = MessageCursorPagination()
        self.assertEqual(p.max_page_size, MAX_MESSAGES_FETCH)

    def test_default_ordering_is_newest_first(self):
        p = MessageCursorPagination()
        self.assertEqual(p.ordering, "-created_at")

    def test_cursor_query_param_is_cursor(self):
        p = MessageCursorPagination()
        self.assertEqual(p.cursor_query_param, "cursor")

    def test_paginated_response_has_next_previous_results(self):
        p = MessageCursorPagination()
        mock_page = MagicMock()
        p.page = mock_page
        p.request = _make_request()
        with patch.object(p, "get_next_link", return_value="http://next"),\
             patch.object(p, "get_previous_link", return_value="http://prev"):
            response = p.get_paginated_response(["msg1", "msg2"])
        self.assertEqual(response.data["next"], "http://next")
        self.assertEqual(response.data["previous"], "http://prev")
        self.assertEqual(response.data["results"], ["msg1", "msg2"])

    def test_paginated_response_has_no_count_key(self):
        """Cursor pagination intentionally omits total count."""
        p = MessageCursorPagination()
        mock_page = MagicMock()
        p.page = mock_page
        p.request = _make_request()
        with patch.object(p, "get_next_link", return_value=None),\
             patch.object(p, "get_previous_link", return_value=None):
            response = p.get_paginated_response([])
        self.assertNotIn("count", response.data)


# ── LargeResultsPagination ───────────────────────────────────────────────────

class TestLargeResultsPagination(TestCase):

    def test_default_limit_matches_constant(self):
        p = LargeResultsPagination()
        self.assertEqual(p.default_limit, DEFAULT_PAGE_SIZE)

    def test_max_limit_matches_max_page_size(self):
        p = LargeResultsPagination()
        self.assertEqual(p.max_limit, MAX_PAGE_SIZE)

    def test_is_limit_offset_based(self):
        from rest_framework.pagination import LimitOffsetPagination
        self.assertTrue(issubclass(LargeResultsPagination, LimitOffsetPagination))


# ── SearchResultsPagination ───────────────────────────────────────────────────

class TestSearchResultsPagination(TestCase):

    def test_default_page_size_is_20(self):
        p = SearchResultsPagination()
        self.assertEqual(p.page_size, 20)

    def test_max_page_size_is_max_search_results(self):
        p = SearchResultsPagination()
        self.assertEqual(p.max_page_size, MAX_SEARCH_RESULTS)

    def test_max_search_results_lower_than_max_page_size(self):
        """Search pagination cap must be ≤ general page size cap."""
        self.assertLessEqual(MAX_SEARCH_RESULTS, MAX_PAGE_SIZE)

    def test_paginated_response_has_count_and_results(self):
        p = SearchResultsPagination()
        mock_page = MagicMock()
        mock_page.paginator.count = 42
        p.page = mock_page
        p.request = _make_request()
        with patch.object(p, "get_next_link", return_value=None),\
             patch.object(p, "get_previous_link", return_value=None):
            response = p.get_paginated_response(["result"])
        self.assertEqual(response.data["count"], 42)
        self.assertIn("results", response.data)


# ── SmallResultsPagination ────────────────────────────────────────────────────

class TestSmallResultsPagination(TestCase):

    def test_page_size_is_10(self):
        p = SmallResultsPagination()
        self.assertEqual(p.page_size, 10)

    def test_no_page_size_query_param(self):
        """SmallResultsPagination must not allow client to override page size."""
        p = SmallResultsPagination()
        self.assertIsNone(p.page_size_query_param)

    def test_smaller_than_standard(self):
        self.assertLess(SmallResultsPagination.page_size, StandardResultsPagination.page_size)
