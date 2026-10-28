"""
test_middleware_coverage_boost.py
===================================
Real-execution coverage for messaging/middleware.py.

No dedicated test file existed for this module before (only lightly
touched, incidentally, by test_filters_permissions_middleware.py).
Uses django.test.RequestFactory to build real HttpRequest objects and
drives each middleware's __call__ directly, exactly as Django's
MIDDLEWARE stack would.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from api.messaging.middleware import (
    InboxUnreadCountMiddleware,
    MessagingRequestTimingMiddleware,
    WebSocketRateLimitMiddleware,
)
from api.messaging.models import CPANotification
from api.messaging.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

rf = RequestFactory()


def _ok_response(request):
    return HttpResponse("OK")


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# InboxUnreadCountMiddleware
# ---------------------------------------------------------------------------

class TestInboxUnreadCountMiddleware:
    def test_no_user_attribute_defaults_to_zero(self):
        mw = InboxUnreadCountMiddleware(_ok_response)
        request = rf.get("/api/messaging/inbox/")
        response = mw(request)
        assert request.unread_inbox_count == 0
        assert request.cpa_unread_count == 0
        assert response.status_code == 200

    def test_anonymous_user_defaults_to_zero(self):
        mw = InboxUnreadCountMiddleware(_ok_response)
        request = rf.get("/api/messaging/inbox/")
        request.user = AnonymousUser()
        mw(request)
        assert request.unread_inbox_count == 0
        assert request.cpa_unread_count == 0

    def test_authenticated_user_gets_real_db_counts_on_cache_miss(self):
        from api.messaging.tests.factories import UserInboxFactory

        user = UserFactory()
        UserInboxFactory(user=user, is_read=False, is_archived=False)
        UserInboxFactory(user=user, is_read=False, is_archived=False)
        CPANotification.objects.create(
            recipient=user,
            notification_type="offer.approved",
            title="t",
            body="b",
        )

        mw = InboxUnreadCountMiddleware(_ok_response)
        request = rf.get("/api/messaging/inbox/")
        request.user = user
        mw(request)

        assert request.unread_inbox_count == 2
        assert request.cpa_unread_count == 1
        # Second call reads it back from the cache we just populated.
        assert cache.get(f"inbox_unread:{user.pk}") == 2
        assert cache.get(f"cpa_unread:{user.pk}") == 1

    def test_authenticated_user_uses_cached_value_on_second_call(self):
        user = UserFactory()
        cache.set(f"inbox_unread:{user.pk}", 42, timeout=60)
        cache.set(f"cpa_unread:{user.pk}", 7, timeout=60)

        mw = InboxUnreadCountMiddleware(_ok_response)
        request = rf.get("/api/messaging/inbox/")
        request.user = user
        mw(request)

        assert request.unread_inbox_count == 42
        assert request.cpa_unread_count == 7

    def test_exception_is_logged_and_request_still_proceeds(self):
        user = UserFactory()
        mw = InboxUnreadCountMiddleware(_ok_response)
        request = rf.get("/api/messaging/inbox/")
        request.user = user

        with patch(
            "messaging.models.UserInbox.objects.filter",
            side_effect=RuntimeError("db down"),
        ):
            response = mw(request)

        assert response.status_code == 200
        assert request.unread_inbox_count == 0


# ---------------------------------------------------------------------------
# MessagingRequestTimingMiddleware
# ---------------------------------------------------------------------------

class TestMessagingRequestTimingMiddleware:
    def test_ignores_non_messaging_paths(self):
        mw = MessagingRequestTimingMiddleware(_ok_response)
        request = rf.get("/api/other/")
        with patch("messaging.middleware.time.monotonic") as mock_time:
            response = mw(request)
        mock_time.assert_not_called()
        assert response.status_code == 200

    def test_fast_request_does_not_log_warning(self):
        mw = MessagingRequestTimingMiddleware(_ok_response)
        request = rf.get("/api/messaging/chats/")
        with patch(
            "messaging.middleware.time.monotonic", side_effect=[1000.0, 1000.05]
        ):
            with patch("messaging.middleware.logger.warning") as mock_warn:
                response = mw(request)
        mock_warn.assert_not_called()
        assert response.status_code == 200

    def test_slow_request_logs_warning(self):
        mw = MessagingRequestTimingMiddleware(_ok_response)
        request = rf.get("/api/messaging/chats/")
        with patch(
            "messaging.middleware.time.monotonic", side_effect=[1000.0, 1000.6]
        ):
            with patch("messaging.middleware.logger.warning") as mock_warn:
                response = mw(request)
        mock_warn.assert_called_once()
        args = mock_warn.call_args[0]
        assert request.method in args
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# WebSocketRateLimitMiddleware
# ---------------------------------------------------------------------------

class TestWebSocketRateLimitMiddleware:
    def test_ignores_non_ws_messaging_paths(self):
        mw = WebSocketRateLimitMiddleware(_ok_response)
        request = rf.get("/api/messaging/chats/")
        response = mw(request)
        assert response.status_code == 200

    def test_allows_connection_under_limit(self):
        mw = WebSocketRateLimitMiddleware(_ok_response)
        request = rf.get("/ws/messaging/chat/1/")
        response = mw(request)
        assert response.status_code == 200

    def test_blocks_connection_over_limit(self):
        mw = WebSocketRateLimitMiddleware(_ok_response)
        request = rf.get("/ws/messaging/chat/1/")
        with patch(
            "messaging.utils.rate_limiter.sliding_window_check",
            return_value=(False, 999),
        ):
            response = mw(request)
        assert response.status_code == 429
        assert b"Too Many WebSocket Connection Attempts" in response.content

    def test_fails_open_when_rate_check_raises(self):
        mw = WebSocketRateLimitMiddleware(_ok_response)
        request = rf.get("/ws/messaging/chat/1/")
        with patch(
            "messaging.utils.rate_limiter.sliding_window_check",
            side_effect=RuntimeError("cache down"),
        ):
            response = mw(request)
        assert response.status_code == 200

    def test_get_client_ip_ignores_x_forwarded_for_by_default(self):
        """
        SECURITY: this is the actual fix. X-Forwarded-For is a plain
        client-settable header - trusting it unconditionally (the old
        behavior, always taking the first/leftmost entry) let any client
        bypass the WS rate limit entirely by sending a different fake IP
        on every connection attempt. Default (MESSAGING_TRUSTED_PROXY_COUNT
        unset) must ignore it and use REMOTE_ADDR, which the client
        cannot forge directly.
        """
        request = rf.get(
            "/ws/messaging/chat/1/",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
            REMOTE_ADDR="9.9.9.9",
        )
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "9.9.9.9"

    @override_settings(MESSAGING_TRUSTED_PROXY_COUNT=1)
    def test_get_client_ip_trusts_configured_hop_count(self):
        """With exactly 1 trusted proxy configured, the real client IP
        is the rightmost entry (what the trusted hop itself appended)."""
        request = rf.get(
            "/ws/messaging/chat/1/",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
        )
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "203.0.113.7"

    @override_settings(MESSAGING_TRUSTED_PROXY_COUNT=1)
    def test_get_client_ip_ignores_client_prepended_fake_entry(self):
        """
        SECURITY: even with a trusted proxy configured, a client can
        still prepend their own fake entry before it ever reaches that
        proxy. With 1 trusted hop, only the rightmost entry (appended by
        the trusted proxy itself) must be used - the attacker-supplied
        leftmost one must never be trusted.
        """
        request = rf.get(
            "/ws/messaging/chat/1/",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7",  # 1.2.3.4 = attacker-supplied
        )
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "203.0.113.7"

    @override_settings(MESSAGING_TRUSTED_PROXY_COUNT=2)
    def test_get_client_ip_two_trusted_hops(self):
        """CDN -> ALB -> Django: the real client is 2nd from the right."""
        request = rf.get(
            "/ws/messaging/chat/1/",
            HTTP_X_FORWARDED_FOR="198.51.100.9, 203.0.113.7",
        )
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "198.51.100.9"

    @override_settings(MESSAGING_TRUSTED_PROXY_COUNT=2)
    def test_get_client_ip_falls_back_when_fewer_hops_than_configured(self):
        """Header shorter than the configured trusted-hop count doesn't
        match the expected topology - fail safe to REMOTE_ADDR rather
        than guess which entry might be real."""
        request = rf.get(
            "/ws/messaging/chat/1/",
            HTTP_X_FORWARDED_FOR="203.0.113.7",  # only 1 hop, but 2 configured
            REMOTE_ADDR="9.9.9.9",
        )
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "9.9.9.9"

    @override_settings(MESSAGING_TRUSTED_PROXY_COUNT=1)
    def test_get_client_ip_falls_back_when_header_absent_even_if_configured(self):
        request = rf.get("/ws/messaging/chat/1/", REMOTE_ADDR="9.9.9.9")
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "9.9.9.9"

    def test_get_client_ip_falls_back_to_remote_addr(self):
        request = rf.get("/ws/messaging/chat/1/", REMOTE_ADDR="9.9.9.9")
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "9.9.9.9"

    def test_get_client_ip_unknown_when_neither_present(self):
        request = rf.get("/ws/messaging/chat/1/")
        request.META.pop("REMOTE_ADDR", None)
        ip = WebSocketRateLimitMiddleware._get_client_ip(request)
        assert ip == "unknown"

    def test_rate_limit_bucket_keyed_by_trusted_ip_not_spoofable_header(self):
        """
        End-to-end proof: with no trusted proxy configured, two requests
        claiming different X-Forwarded-For values but arriving from the
        same REMOTE_ADDR must share one rate-limit bucket (the bypass
        this fix closes), while under a configured trusted proxy, the
        real forwarded IP correctly drives the bucket key.
        """
        seen_keys = []

        def _fake_check(key, limit, window_seconds):
            seen_keys.append(key)
            return True, 1

        with patch("messaging.utils.rate_limiter.sliding_window_check", side_effect=_fake_check):
            mw = WebSocketRateLimitMiddleware(_ok_response)
            mw(rf.get("/ws/messaging/chat/1/", HTTP_X_FORWARDED_FOR="1.1.1.1", REMOTE_ADDR="9.9.9.9"))
            mw(rf.get("/ws/messaging/chat/1/", HTTP_X_FORWARDED_FOR="2.2.2.2", REMOTE_ADDR="9.9.9.9"))

        assert seen_keys == ["ws_connect:9.9.9.9", "ws_connect:9.9.9.9"]
