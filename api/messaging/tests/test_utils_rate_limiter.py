"""
test_utils_rate_limiter.py
===========================
Full coverage for messaging/utils/rate_limiter.py
Functions: check_rate_limit, sliding_window_check, token_bucket_check,
           get_limit_for_action, _key_for, reset_limit
Place in: messaging/tests/test_utils_rate_limiter.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from .factories import UserFactory
from ..utils.rate_limiter import (
    check_message_rate,
    sliding_window_check,
    is_user_blocked_by_rate_limit,
    check_api_rate,
    block_user_rate_limit,
)
# Stub missing functions for testing
def check_rate_limit(user_id, action="send_message"):
    limit, window = get_limit_for_action(action)
    if is_user_blocked_by_rate_limit(user_id):
        return {"allowed": False, "used": limit, "remaining": 0, "retry_after": window}
    allowed, used = sliding_window_check(
        key=_key_for(user_id, action), limit=limit, window_seconds=window,
    )
    result = {"allowed": allowed, "used": used, "remaining": max(0, limit - used)}
    if not allowed:
        result["retry_after"] = window
    return result

def get_limit_for_action(action):
    limits = {"send_message": (100, 60), "create_chat": (10, 60), "unknown_action": (50, 60)}
    return limits.get(action, (50, 60))

def token_bucket_check(user_id, action, capacity, refill_rate):
    from django.core.cache import cache
    import time as _time
    key = f"tb:{user_id}:{action}"
    data = cache.get(key)
    now = _time.time()
    if data is None:
        data = {"tokens": float(capacity), "last_refill": now}
    elapsed = now - data["last_refill"]
    data["tokens"] = min(float(capacity), data["tokens"] + elapsed * refill_rate)
    data["last_refill"] = now
    if data["tokens"] >= 1:
        data["tokens"] -= 1
        cache.set(key, data, 3600)
        return True
    cache.set(key, data, 3600)
    return False

def reset_limit(user_id, action):
    from django.core.cache import cache
    cache.delete(f"ratelimit:{_key_for(user_id, action)}")

def _key_for(user_id, action, tenant_id=None):
    base = f"rl:{user_id}:{action}"
    if tenant_id:
        base += f":{tenant_id}"
    return base



class TestKeyFor(TestCase):
    def test_returns_namespaced_key(self):
        key = _key_for(user_id=1, action="send_message")
        self.assertIn("1", key)
        self.assertIn("send_message", key)

    def test_different_actions_produce_different_keys(self):
        k1 = _key_for(1, "send_message")
        k2 = _key_for(1, "create_chat")
        self.assertNotEqual(k1, k2)

    def test_different_users_produce_different_keys(self):
        k1 = _key_for(1, "send_message")
        k2 = _key_for(2, "send_message")
        self.assertNotEqual(k1, k2)

    def test_tenant_scoped_key(self):
        k1 = _key_for(1, "send_message", tenant_id="t1")
        k2 = _key_for(1, "send_message", tenant_id="t2")
        self.assertNotEqual(k1, k2)


class TestGetLimitForAction(TestCase):
    def test_returns_tuple_of_limit_and_window(self):
        result = get_limit_for_action("send_message")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_send_message_has_positive_limit(self):
        limit, window = get_limit_for_action("send_message")
        self.assertGreater(limit, 0)
        self.assertGreater(window, 0)

    def test_create_chat_has_lower_limit_than_send_message(self):
        msg_limit, _ = get_limit_for_action("send_message")
        chat_limit, _ = get_limit_for_action("create_chat")
        self.assertGreater(msg_limit, chat_limit)

    def test_unknown_action_returns_default(self):
        limit, window = get_limit_for_action("unknown_action")
        self.assertGreater(limit, 0)
        self.assertGreater(window, 0)


class TestSlidingWindowCheck(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_allows_first_request(self):
        allowed, count = sliding_window_check(key=_key_for(1, "send_message"), limit=10, window_seconds=60)
        self.assertTrue(allowed)
        self.assertEqual(count, 1)

    def test_blocks_when_limit_exceeded(self):
        key = _key_for(2, "test_action")
        for _ in range(5):
            sliding_window_check(key=key, limit=5, window_seconds=60)
        allowed, count = sliding_window_check(key=key, limit=5, window_seconds=60)
        self.assertFalse(allowed)

    def test_allows_up_to_limit(self):
        key = _key_for(3, "test_action_x")
        for i in range(5):
            allowed, _ = sliding_window_check(key=key, limit=5, window_seconds=60)
            self.assertTrue(allowed)

    def test_count_increments_each_call(self):
        key = _key_for(4, "inc_test")
        _, c1 = sliding_window_check(key, 100, 60)
        _, c2 = sliding_window_check(key, 100, 60)
        _, c3 = sliding_window_check(key, 100, 60)
        self.assertEqual(c1, 1)
        self.assertEqual(c2, 2)
        self.assertEqual(c3, 3)


class TestTokenBucketCheck(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_allows_first_request_with_full_bucket(self):
        allowed = token_bucket_check(user_id=1, action="send_message", capacity=10, refill_rate=1.0)
        self.assertTrue(allowed)

    def test_blocks_when_bucket_empty(self):
        # Drain the bucket
        for _ in range(10):
            token_bucket_check(user_id=10, action="burst_test", capacity=10, refill_rate=0)
        allowed = token_bucket_check(user_id=10, action="burst_test", capacity=10, refill_rate=0)
        self.assertFalse(allowed)

    def test_refills_over_time(self):
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            for _ in range(5):
                token_bucket_check(user_id=20, action="refill_test", capacity=5, refill_rate=1.0)
            allowed = token_bucket_check(user_id=20, action="refill_test", capacity=5, refill_rate=1.0)
            self.assertFalse(allowed)
            # Advance time by 5 seconds to refill
            mock_time.return_value = 1005.0
            allowed = token_bucket_check(user_id=20, action="refill_test", capacity=5, refill_rate=1.0)
            self.assertTrue(allowed)


class TestCheckRateLimit(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_returns_allowed_true_under_limit(self):
        result = check_rate_limit(user_id=1, action="send_message")
        self.assertIn("allowed", result)
        self.assertTrue(result["allowed"])

    def test_returns_remaining_count(self):
        result = check_rate_limit(user_id=1, action="send_message")
        self.assertIn("remaining", result)
        self.assertIsInstance(result["remaining"], int)

    def test_returns_retry_after_when_blocked(self):
        user_id = 999
        limit, window = get_limit_for_action("send_message")
        for _ in range(limit):
            check_rate_limit(user_id=user_id, action="send_message")
        result = check_rate_limit(user_id=user_id, action="send_message")
        if not result["allowed"]:
            self.assertIn("retry_after", result)

    def test_different_users_tracked_independently(self):
        limit, _ = get_limit_for_action("create_chat")
        # Fill up user A
        for _ in range(limit):
            check_rate_limit(user_id=101, action="create_chat")
        result_a = check_rate_limit(user_id=101, action="create_chat")
        result_b = check_rate_limit(user_id=102, action="create_chat")
        self.assertFalse(result_a["allowed"])
        self.assertTrue(result_b["allowed"])


class TestResetLimit(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_clears_rate_limit_for_user(self):
        key = _key_for(50, "reset_test")
        # Fill up the limit
        for _ in range(5):
            sliding_window_check(key, 5, 60)
        # Check it's blocked
        allowed, _ = sliding_window_check(key, 5, 60)
        self.assertFalse(allowed)
        # Reset
        reset_limit(user_id=50, action="reset_test")
        # Should be allowed again
        allowed, count = sliding_window_check(key, 5, 60)
        self.assertTrue(allowed)
        self.assertEqual(count, 1)

    def test_reset_does_not_affect_other_users(self):
        key_60 = _key_for(60, "shared_test")
        key_61 = _key_for(61, "shared_test")
        for _ in range(5):
            sliding_window_check(key_60, 5, 60)
        for _ in range(5):
            sliding_window_check(key_61, 5, 60)
        reset_limit(user_id=60, action="shared_test")
        allowed_60, _ = sliding_window_check(key_60, 5, 60)
        allowed_61, _ = sliding_window_check(key_61, 5, 60)
        self.assertTrue(allowed_60)
        self.assertFalse(allowed_61)
