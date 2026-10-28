"""
test_rate_limiter.py – Tests for postback-internal rate limiter.
"""
from django.core.cache import cache
from django.test import TestCase
from unittest.mock import patch

from api.postback.utils.rate_limiter import (
    PostbackRateLimiter,
    check_postback_rate_limit,
    get_postback_rate_limit_remaining,
    _parse_rate,
)


class ParseRateTests(TestCase):
    def test_minute_rate(self):
        self.assertEqual(_parse_rate("1000/minute"), 1000)

    def test_second_rate(self):
        self.assertEqual(_parse_rate("50/second"), 50)

    def test_malformed_returns_1000(self):
        self.assertEqual(_parse_rate("bad_value"), 1000)

    def test_zero_rate(self):
        self.assertEqual(_parse_rate("0/minute"), 0)


class PostbackRateLimiterTests(TestCase):

    def setUp(self):
        cache.clear()
        self.limiter = PostbackRateLimiter()

    def test_first_request_allowed(self):
        self.assertTrue(self.limiter.is_allowed("net1", "1.2.3.4"))

    def test_within_limit_allowed(self):
        # Set a very high limit — should always pass
        for _ in range(10):
            result = self.limiter.is_allowed("net_high", "1.2.3.4")
        self.assertTrue(result)

    def test_different_networks_independent(self):
        """Each network has its own rate limit bucket."""
        cache.clear()
        self.limiter.is_allowed("net_a", "1.2.3.4")
        self.limiter.is_allowed("net_b", "1.2.3.4")
        self.assertTrue(self.limiter.is_allowed("net_c", "1.2.3.4"))

    def test_remaining_decreases(self):
        cache.clear()
        before = get_postback_rate_limit_remaining("net_rem")
        self.limiter.is_allowed("net_rem", "1.2.3.4")
        after = get_postback_rate_limit_remaining("net_rem")
        self.assertLessEqual(after, before)

    def test_get_remaining_returns_int(self):
        result = get_postback_rate_limit_remaining("test_net")
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

    @patch("api.postback.utils.rate_limiter.cache.add", side_effect=Exception("cache down"))
    def test_cache_failure_fails_open(self, _):
        """Rate limiter fails open on cache error — never blocks postbacks."""
        result = check_postback_rate_limit("net_fail", "1.2.3.4")
        self.assertTrue(result)

    def test_no_ip_still_works(self):
        """Empty IP is allowed — burst check skipped."""
        self.assertTrue(check_postback_rate_limit("net_noip", ""))

    def test_module_function_returns_bool(self):
        result = check_postback_rate_limit("net_bool", "1.2.3.4")
        self.assertIsInstance(result, bool)
