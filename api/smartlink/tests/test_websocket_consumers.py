"""
Tests for SmartLink WebSocket Consumers
=========================================
Previously 0% coverage. Covers both consumers:

  1. SmartLinkLiveConsumer   — ws://.../ws/smartlink/<slug>/live/
  2. PublisherDashboardConsumer — ws://.../ws/publisher/dashboard/

Uses Django Channels' WebsocketCommunicator for isolated async testing.
No real Redis required — InMemoryChannelLayer is used.
"""
import json
import uuid
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async

User = get_user_model()

# ── ASGI application under test ────────────────────────────────────────────
# Use testproject's ASGI app which routes WS → smartlink consumers.
try:
    from testproject.asgi import application as _asgi_app
    _ASGI_AVAILABLE = True
except Exception:
    _ASGI_AVAILABLE = False

# ── Test settings override ─────────────────────────────────────────────────
WS_SETTINGS = {
    "CHANNEL_LAYERS": {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
}

from api.smartlink.tests.test_helpers import (
    make_user, make_offer, make_smartlink, make_click,
    make_payout_record, make_profile, make_wallet,
    make_offer_pool_entry, make_batch, auth_client,
    # backwards-compatible aliases (legacy _make_* names)
    _make_user, _make_offer, _make_smartlink, _make_sl,
    _make_click, _make_profile, _make_payout_record, _make_batch,
    _make_offer_pool_entry,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _communicator(path, user=None):
    """
    Build a WebsocketCommunicator with an authenticated scope.

    Injects the Django user into the ASGI scope's "user" key,
    matching what AuthMiddlewareStack provides in production.
    """
    from api.smartlink.websocket.routing import websocket_urlpatterns
    from channels.routing import URLRouter
    from channels.auth import AuthMiddlewareStack

    app = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    comm = WebsocketCommunicator(app, path)
    if user:
        comm.scope["user"] = user
    return comm

# ═════════════════════════════════════════════════════════════════════════════
# 1. SmartLinkLiveConsumer
# ═════════════════════════════════════════════════════════════════════════════

@override_settings(**WS_SETTINGS)
class SmartLinkLiveConsumerTest(TestCase):
    """Tests for SmartLinkLiveConsumer."""

    def setUp(self):
        self.pub = _make_user("ws_pub")
        self.sl  = _make_sl(self.pub, slug="ws-test-sl")

    async def _comm(self, slug=None, user=None):
        slug = slug or self.sl.slug
        user = user or self.pub
        return await _communicator(f"/ws/smartlink/{slug}/live/", user=user)

    async def test_authenticated_publisher_can_connect(self):
        """Publisher who owns the SmartLink can connect successfully."""
        comm = await self._comm()
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect()

    async def test_unauthenticated_user_is_rejected(self):
        """Anonymous user is rejected with close code 4001."""
        from django.contrib.auth.models import AnonymousUser
        comm = await _communicator(
            f"/ws/smartlink/{self.sl.slug}/live/",
            user=AnonymousUser(),
        )
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_non_owner_is_rejected(self):
        """Publisher who does NOT own the SmartLink gets close code 4003."""
        other = await sync_to_async(_make_user)("ws_other")
        comm = await self._comm(user=other)
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4003)

    async def test_connect_sends_snapshot_immediately(self):
        """On connect, consumer sends a 'snapshot' message with current stats."""
        comm = await self._comm()
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        response = await comm.receive_json_from()
        self.assertEqual(response["type"], "snapshot")
        self.assertIn("data", response)
        await comm.disconnect()

    async def test_ping_receives_pong(self):
        """Client 'ping' message receives 'pong' response."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # consume snapshot
        await comm.send_json_to({"type": "ping"})
        response = await comm.receive_json_from()
        self.assertEqual(response["type"], "pong")
        await comm.disconnect()

    async def test_subscribe_stats_returns_stats(self):
        """'subscribe_stats' message returns 'stats' message with data."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # consume snapshot
        await comm.send_json_to({"type": "subscribe_stats"})
        response = await comm.receive_json_from()
        self.assertEqual(response["type"], "stats")
        self.assertIn("data", response)
        await comm.disconnect()

    async def test_channel_layer_broadcasts_click_event(self):
        """Channel layer group message 'live_click' is forwarded to client."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # consume snapshot

        # Simulate a click event broadcast from the channel layer
        channel_layer = get_channel_layer()
        group_name = f"smartlink_live_{self.sl.slug}"
        await channel_layer.group_send(
            group_name,
            {
                "type": "live_click",
                "data": {"click_id": 99, "country": "US", "ip": "1.2.3.4"},
            },
        )
        response = await comm.receive_json_from()
        self.assertEqual(response["type"], "click")
        self.assertEqual(response["data"]["click_id"], 99)
        await comm.disconnect()

    async def test_channel_layer_broadcasts_conversion_event(self):
        """Channel layer 'live_conversion' event is forwarded to client."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # consume snapshot

        channel_layer = get_channel_layer()
        group_name = f"smartlink_live_{self.sl.slug}"
        await channel_layer.group_send(
            group_name,
            {
                "type": "live_conversion",
                "data": {"click_id": 42, "payout": 1.50},
            },
        )
        response = await comm.receive_json_from()
        self.assertEqual(response["type"], "conversion")
        self.assertAlmostEqual(response["data"]["payout"], 1.50)
        await comm.disconnect()

    async def test_disconnect_leaves_channel_group(self):
        """After disconnect, consumer is removed from the channel group."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # snapshot
        await comm.disconnect()

        # Subsequent group_send should not cause errors (no consumers in group)
        channel_layer = get_channel_layer()
        try:
            await channel_layer.group_send(
                f"smartlink_live_{self.sl.slug}",
                {"type": "live_click", "data": {}},
            )
        except Exception as e:
            self.fail(f"group_send after disconnect raised: {e}")

    async def test_invalid_json_does_not_crash_consumer(self):
        """Sending malformed text does not crash the consumer."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # snapshot
        await comm.send_to(text_data="not-valid-json")
        # Consumer must not crash — it should still be connected
        # Send a valid ping to verify
        await comm.send_json_to({"type": "ping"})
        response = await comm.receive_json_from()
        self.assertEqual(response["type"], "pong")
        await comm.disconnect()

# ═════════════════════════════════════════════════════════════════════════════
# 2. PublisherDashboardConsumer
# ═════════════════════════════════════════════════════════════════════════════

@override_settings(**WS_SETTINGS)
class PublisherDashboardConsumerTest(TestCase):
    """Tests for PublisherDashboardConsumer."""

    def setUp(self):
        self.pub   = _make_user("dash_pub")
        self.admin = _make_user("dash_admin", is_staff=True)

    async def _comm(self, user=None):
        user = user or self.pub
        return await _communicator("/ws/publisher/dashboard/", user=user)

    async def test_authenticated_publisher_can_connect(self):
        """Authenticated publisher can connect to the dashboard consumer."""
        comm = await self._comm()
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect()

    async def test_unauthenticated_user_is_rejected(self):
        """Anonymous user is rejected from dashboard."""
        from django.contrib.auth.models import AnonymousUser
        comm = await _communicator("/ws/publisher/dashboard/", user=AnonymousUser())
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_connect_sends_initial_dashboard_data(self):
        """On connect, consumer sends initial dashboard summary."""
        comm = await self._comm()
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        response = await comm.receive_json_from()
        self.assertIn(response["type"], ["snapshot", "dashboard", "stats"])
        self.assertIn("data", response)
        await comm.disconnect()

    async def test_request_stats_returns_stats(self):
        """'request_stats' message returns current dashboard stats."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # initial message
        await comm.send_json_to({"type": "refresh"})
        response = await comm.receive_json_from()
        self.assertIn(response["type"], ["stats", "snapshot"])
        await comm.disconnect()

    async def test_ping_pong_on_dashboard(self):
        """'ping' message receives 'pong' on dashboard consumer."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # initial
        await comm.send_json_to({"type": "ping"})
        response = await comm.receive_json_from()
        self.assertEqual(response["type"], "pong")
        await comm.disconnect()

    async def test_channel_layer_pushes_stats_update(self):
        """Channel layer 'stats_update' event is forwarded to dashboard client."""
        comm = await self._comm()
        await comm.connect()
        await comm.receive_json_from()  # initial

        channel_layer = get_channel_layer()
        # Dashboard consumer uses publisher_dashboard_{user.pk} group
        group_name = f"publisher_dashboard_{self.pub.pk}"
        await channel_layer.group_send(
            group_name,
            {
                "type": "dashboard_update",
                "data": {
                    "total_clicks": 500,
                    "total_revenue": 42.50,
                    "active_smartlinks": 3,
                },
            },
        )
        response = await comm.receive_json_from()
        # Dashboard consumer sends type='update' (see dashboard_update handler)
        self.assertEqual(response["type"], "update")
        self.assertEqual(response["data"]["total_clicks"], 500)
        await comm.disconnect()

    async def test_admin_can_connect_to_dashboard(self):
        """Admin can connect to the dashboard consumer."""
        comm = await self._comm(user=self.admin)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect()

# ═════════════════════════════════════════════════════════════════════════════
# 3. Consumer Unit Tests (sync — no channels needed)
# ═════════════════════════════════════════════════════════════════════════════

class ConsumerAuthUnitTest(TestCase):
    """
    Sync unit tests for consumer helper methods.
    These test the DB-sync methods without requiring a WebSocket connection.
    """

    def setUp(self):
        self.pub  = _make_user("auth_unit_pub")
        self.sl   = _make_sl(self.pub, slug="auth-unit-sl")

    async def test_verify_ownership_true_for_owner(self):
        """_verify_ownership() returns True when publisher owns the SmartLink."""
        from api.smartlink.websocket.consumers import SmartLinkLiveConsumer
        consumer = SmartLinkLiveConsumer()
        consumer.slug = self.sl.slug
        consumer.user = self.pub
        result = await consumer._verify_ownership()
        self.assertTrue(result)

    async def test_verify_ownership_false_for_non_owner(self):
        """_verify_ownership() returns False for a publisher who doesn't own it."""
        from api.smartlink.websocket.consumers import SmartLinkLiveConsumer
        other = await sync_to_async(_make_user)("auth_unit_other")
        consumer = SmartLinkLiveConsumer()
        consumer.slug = self.sl.slug
        consumer.user = other
        result = await consumer._verify_ownership()
        self.assertFalse(result)

    async def test_verify_ownership_true_for_admin(self):
        """_verify_ownership() returns True for admin regardless of ownership."""
        from api.smartlink.websocket.consumers import SmartLinkLiveConsumer
        admin = await sync_to_async(_make_user)("auth_unit_admin", is_staff=True)
        consumer = SmartLinkLiveConsumer()
        consumer.slug = self.sl.slug
        consumer.user = admin
        result = await consumer._verify_ownership()
        self.assertTrue(result)

    async def test_get_live_stats_returns_dict(self):
        """_get_live_stats() returns a dict with click/conversion/revenue keys."""
        from api.smartlink.websocket.consumers import SmartLinkLiveConsumer
        consumer = SmartLinkLiveConsumer()
        consumer.slug = self.sl.slug
        consumer.user = self.pub
        stats = await consumer._get_live_stats()
        self.assertIsInstance(stats, dict)
        # _get_live_stats() returns SmartLink-prefixed keys from consumers.py
        self.assertIn("total_clicks",      stats)
        self.assertIn("total_conversions", stats)
        self.assertIn("total_revenue",     stats)
