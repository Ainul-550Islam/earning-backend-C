"""
test_utils_rate_limiter_coverage_boost.py
==========================================
Real-execution coverage for messaging/utils/rate_limiter.py.

NOTE: the existing test_utils_rate_limiter.py mostly exercises local stub
reimplementations of functions that do not exist in the real module
(check_rate_limit, token_bucket_check, get_limit_for_action, _key_for,
reset_limit are all defined inline there with a "Stub missing functions"
comment). It only calls the real module for sliding_window_check,
is_user_blocked_by_rate_limit, check_api_rate, and block_user_rate_limit.
This file targets the real module directly, including the Redis code
path, the per-IP/per-action limit functions, and every exception-handling
branch, none of which were previously exercised against real source code.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from api.messaging.utils.rate_limiter import (
    RateLimitError,
    block_user_rate_limit,
    check_api_rate,
    check_call_rate,
    check_message_rate,
    check_reaction_rate,
    is_user_blocked_by_rate_limit,
    sliding_window_check,
    _cache_fallback,
    _get_redis_client,
    _redis_sliding_window,
)
from messaging import constants


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# sliding_window_check - dispatch + cache-fallback path (no LOCATION set in
# test settings, so _get_redis_client naturally returns None here)
# ---------------------------------------------------------------------------

class TestSlidingWindowCheckDispatch:
    def test_uses_cache_fallback_when_no_redis_configured(self):
        allowed, count = sliding_window_check(key="dispatch:1", limit=5, window_seconds=60)
        assert allowed is True
        assert count == 1

    def test_returns_true_zero_on_internal_error(self):
        with patch(
            "messaging.utils.rate_limiter._get_redis_client",
            side_effect=RuntimeError("boom"),
        ):
            allowed, count = sliding_window_check(key="err:1", limit=5, window_seconds=60)
        assert allowed is True
        assert count == 0

    def test_uses_redis_path_when_client_available(self):
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [None, None, 3, None]
        fake_client = MagicMock()
        fake_client.pipeline.return_value = fake_pipe

        with patch(
            "messaging.utils.rate_limiter._get_redis_client",
            return_value=fake_client,
        ):
            allowed, count = sliding_window_check(key="redis:1", limit=5, window_seconds=60)

        assert allowed is True
        assert count == 3
        fake_client.pipeline.assert_called_once()
        fake_pipe.zadd.assert_called_once()
        fake_pipe.zremrangebyscore.assert_called_once()
        fake_pipe.zcard.assert_called_once()
        fake_pipe.expire.assert_called_once()


# ---------------------------------------------------------------------------
# _redis_sliding_window - real pipeline-building logic against a fake client
# ---------------------------------------------------------------------------

class TestRedisSlidingWindow:
    def test_allowed_when_under_limit(self):
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [None, None, 2, None]
        fake_client = MagicMock()
        fake_client.pipeline.return_value = fake_pipe

        allowed, count = _redis_sliding_window(fake_client, "k", limit=5, window_seconds=60)
        assert allowed is True
        assert count == 2

    def test_blocked_when_over_limit(self):
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [None, None, 9, None]
        fake_client = MagicMock()
        fake_client.pipeline.return_value = fake_pipe

        allowed, count = _redis_sliding_window(fake_client, "k", limit=5, window_seconds=60)
        assert allowed is False
        assert count == 9

    def test_builds_key_with_ratelimit_prefix(self):
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [None, None, 1, None]
        fake_client = MagicMock()
        fake_client.pipeline.return_value = fake_pipe

        _redis_sliding_window(fake_client, "mykey", limit=5, window_seconds=60)
        zadd_args = fake_pipe.zadd.call_args[0]
        assert zadd_args[0] == "ratelimit:mykey"


# ---------------------------------------------------------------------------
# _cache_fallback - direct
# ---------------------------------------------------------------------------

class TestCacheFallback:
    def test_first_call_allowed_with_count_one(self):
        allowed, count = _cache_fallback(cache, "fb:1", limit=3, window_seconds=60)
        assert allowed is True
        assert count == 1

    def test_increments_and_blocks_at_limit(self):
        for _ in range(3):
            _cache_fallback(cache, "fb:2", limit=3, window_seconds=60)
        allowed, count = _cache_fallback(cache, "fb:2", limit=3, window_seconds=60)
        assert allowed is False
        assert count == 3


# ---------------------------------------------------------------------------
# _get_redis_client - every branch
# ---------------------------------------------------------------------------

class TestGetRedisClient:
    def test_returns_none_when_location_not_redis(self):
        assert _get_redis_client(cache) is None

    def test_uses_django_redis_client_when_available(self):
        fake_backend = MagicMock()
        fake_backend.client.get_client.return_value = "native-redis-client"
        result = _get_redis_client(fake_backend)
        assert result == "native-redis-client"

    def test_falls_back_past_attribute_error_to_location_check(self):
        class NoClientCache:
            pass  # accessing .client raises AttributeError

        result = _get_redis_client(NoClientCache())
        assert result is None

    @override_settings(CACHES={"default": {"BACKEND": "x", "LOCATION": "redis://localhost:6379/0"}})
    def test_builds_redis_client_from_redis_location(self):
        class NoClientCache:
            pass

        result = _get_redis_client(NoClientCache())
        # redis.from_url() is lazy (no real connection attempt), so this
        # should succeed and return a real client instance.
        assert result is not None

    @override_settings(CACHES={"default": {"BACKEND": "x", "LOCATION": "redis://localhost:6379/0"}})
    def test_returns_none_when_redis_from_url_raises(self):
        class NoClientCache:
            pass

        with patch("redis.from_url", side_effect=Exception("bad url")):
            result = _get_redis_client(NoClientCache())
        assert result is None


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------

class TestRateLimitError:
    def test_stores_message_and_default_retry_after(self):
        err = RateLimitError("slow down")
        assert str(err) == "slow down"
        assert err.retry_after == 60

    def test_custom_retry_after(self):
        err = RateLimitError("slow down", retry_after=120)
        assert err.retry_after == 120


# ---------------------------------------------------------------------------
# check_message_rate / check_reaction_rate / check_call_rate / check_api_rate
# ---------------------------------------------------------------------------

class TestCheckMessageRate:
    def test_allows_under_limit(self):
        check_message_rate(user_id="msg-user-1")  # should not raise

    def test_raises_when_user_limit_exceeded(self):
        for _ in range(constants.MAX_MESSAGES_PER_MINUTE):
            check_message_rate(user_id="msg-user-2")
        with pytest.raises(RateLimitError):
            check_message_rate(user_id="msg-user-2")

    def test_checks_ip_limit_when_ip_provided(self):
        check_message_rate(user_id="msg-user-3", ip="10.0.0.5")  # should not raise

    def test_raises_when_ip_limit_exceeded(self):
        # IP limit is 5x the per-user limit; use a fresh user each call so
        # only the IP bucket accumulates toward its own (higher) ceiling.
        ip_limit = constants.MAX_MESSAGES_PER_MINUTE * 5
        for i in range(ip_limit):
            check_message_rate(user_id=f"msg-user-ip-{i}", ip="10.0.0.9")
        with pytest.raises(RateLimitError):
            check_message_rate(user_id="msg-user-ip-final", ip="10.0.0.9")


class TestCheckReactionRate:
    def test_allows_under_limit(self):
        check_reaction_rate(user_id="react-user-1")

    def test_raises_when_exceeded(self):
        for _ in range(constants.MAX_REACTIONS_PER_MINUTE):
            check_reaction_rate(user_id="react-user-2")
        with pytest.raises(RateLimitError):
            check_reaction_rate(user_id="react-user-2")


class TestCheckCallRate:
    def test_allows_under_limit(self):
        check_call_rate(user_id="call-user-1")

    def test_raises_when_exceeded(self):
        for _ in range(constants.MAX_CALLS_PER_HOUR):
            check_call_rate(user_id="call-user-2")
        with pytest.raises(RateLimitError):
            check_call_rate(user_id="call-user-2")


class TestCheckApiRate:
    def test_allows_under_limit(self):
        check_api_rate(user_id="api-user-1", endpoint="search", limit=5, window=60)

    def test_raises_when_exceeded(self):
        for _ in range(3):
            check_api_rate(user_id="api-user-2", endpoint="search", limit=3, window=60)
        with pytest.raises(RateLimitError):
            check_api_rate(user_id="api-user-2", endpoint="search", limit=3, window=60)

    def test_uses_default_limit_and_window(self):
        check_api_rate(user_id="api-user-3", endpoint="default-test")


# ---------------------------------------------------------------------------
# block_user_rate_limit / is_user_blocked_by_rate_limit
# ---------------------------------------------------------------------------

class TestBlockUserRateLimit:
    def test_blocks_user(self):
        block_user_rate_limit(user_id="block-user-1", duration_seconds=60, reason="spam")
        assert is_user_blocked_by_rate_limit("block-user-1") is True

    def test_unblocked_user_returns_false(self):
        assert is_user_blocked_by_rate_limit("never-blocked-user") is False

    def test_block_swallows_cache_errors(self):
        with patch(
            "django.core.cache.cache.set",
            side_effect=Exception("cache down"),
        ):
            block_user_rate_limit(user_id="block-user-2")  # should not raise

    def test_is_blocked_swallows_cache_errors(self):
        with patch(
            "django.core.cache.cache.get",
            side_effect=Exception("cache down"),
        ):
            result = is_user_blocked_by_rate_limit("block-user-3")
        assert result is False
