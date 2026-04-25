# api/wallet/tests/test_rate_limiter.py
from django.test import TestCase
from django.core.cache import cache


class RateLimiterTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_within_limit_allowed(self):
        from ..rate_limiter import WalletRateLimiter
        allowed, remaining, _ = WalletRateLimiter.check(user_id=1, action="withdrawal")
        self.assertTrue(allowed)
        self.assertGreater(remaining, 0)

    def test_exceeds_limit_blocked(self):
        from ..rate_limiter import WalletRateLimiter, RATE_LIMITS
        limit = RATE_LIMITS["withdrawal"]["limit"]
        for _ in range(limit):
            WalletRateLimiter.check(user_id=99, action="withdrawal")
        allowed, remaining, _ = WalletRateLimiter.check(user_id=99, action="withdrawal")
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_reset_clears_limit(self):
        from ..rate_limiter import WalletRateLimiter, RATE_LIMITS
        limit = RATE_LIMITS["withdrawal"]["limit"]
        for _ in range(limit + 1):
            WalletRateLimiter.check(user_id=55, action="withdrawal")
        WalletRateLimiter.reset(55, "withdrawal")
        allowed, _, _ = WalletRateLimiter.check(55, "withdrawal")
        self.assertTrue(allowed)

    def test_get_status_returns_dict(self):
        from ..rate_limiter import WalletRateLimiter
        status = WalletRateLimiter.get_status(1, "transfer")
        self.assertIn("limit", status)
        self.assertIn("used", status)
        self.assertIn("remaining", status)

    def test_different_actions_independent(self):
        from ..rate_limiter import WalletRateLimiter, RATE_LIMITS
        limit = RATE_LIMITS["withdrawal"]["limit"]
        for _ in range(limit + 1):
            WalletRateLimiter.check(100, "withdrawal")
        # Transfer should still be allowed
        allowed, _, _ = WalletRateLimiter.check(100, "transfer")
        self.assertTrue(allowed)
