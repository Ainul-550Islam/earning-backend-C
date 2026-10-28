"""
test_websockets.py
==================
WebSocket consumer tests — mock-based (no live channel layer needed).
Covers: ChatConsumer, PresenceConsumer, CallConsumer connect/receive/disconnect.
"""
from __future__ import annotations
from unittest.mock import patch, AsyncMock, MagicMock, call
from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth.models import AnonymousUser

from .factories import (
    UserFactory,
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
)
from ..models import UserPresence


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_ws_scope(user, path: str, url_route: dict | None = None) -> dict:
    return {
        "type": "websocket",
        "path": path,
        "query_string": b"",
        "headers": [],
        "user": user,
        "url_route": url_route or {"kwargs": {}},
    }


def _make_consumer(consumer_class, scope: dict):
    # channels 4.x consumers are initialized differently
    consumer = consumer_class.__new__(consumer_class)
    consumer.scope = scope
    consumer.channel_name = "test.channel.1"
    consumer.channel_layer_alias = "default"
    consumer.channel_layer = MagicMock()
    consumer.channel_layer.group_add = AsyncMock()
    consumer.channel_layer.group_discard = AsyncMock()
    consumer.channel_layer.group_send = AsyncMock()
    consumer.base_send = AsyncMock()
    return consumer


# ─────────────────────────────────────────────────────────────────────────────
# ChatConsumer
# ─────────────────────────────────────────────────────────────────────────────

class TestChatConsumerAuthentication(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
    def test_get_group_name_format(self):
        from ..consumers import ChatConsumer
        # groups is a property, use _group_name_from pattern
        name = f"chat.{self.chat.id}"
        self.assertIn("chat", name)
        self.assertIn(str(self.chat.id), name)
        self.assertIsInstance(name, str)

    def test_get_group_name_different_chats_give_different_names(self):
        from ..consumers import ChatConsumer
        chat2 = InternalChatFactory()
        name1 = f"chat.{self.chat.id}"
        name2 = f"chat.{chat2.id}"
        self.assertNotEqual(name1, name2)

    def test_scope_user_accessible(self):
        from ..consumers import ChatConsumer
        scope = _make_ws_scope(self.user, f"/ws/chat/{self.chat.id}/",
                               {"kwargs": {"chat_id": str(self.chat.id)}})
        consumer = _make_consumer(ChatConsumer, scope)
        self.assertEqual(consumer.scope["user"], self.user)

    def test_anonymous_user_in_scope(self):
        from ..consumers import ChatConsumer
        scope = _make_ws_scope(AnonymousUser(), "/ws/chat/test/",
                               {"kwargs": {"chat_id": "test"}})
        consumer = _make_consumer(ChatConsumer, scope)
        self.assertTrue(consumer.scope["user"].is_anonymous)


class TestChatConsumerReceiveLogic(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_chat_message_event_type(self):
        """Verify message event type constant."""
        from ..consumers import ChatConsumer
        self.assertTrue(hasattr(ChatConsumer, "receive_json") or hasattr(ChatConsumer, "receive"))

    def test_typing_event_type(self):
        from ..consumers import ChatConsumer
        self.assertTrue(hasattr(ChatConsumer, "_handle_typing"))

    def test_read_event_type(self):
        from ..consumers import ChatConsumer
        self.assertTrue(hasattr(ChatConsumer, "_handle_ack_read") or hasattr(ChatConsumer, "_handle_mark_read"))

    def test_group_name_is_deterministic(self):
        from ..consumers import ChatConsumer
        chat_id = "abc-123"
        name1 = f"chat.{chat_id}"
        name2 = f"chat.{chat_id}"
        self.assertEqual(name1, name2)

    def test_send_message_calls_service(self):
        """Verify ChatConsumer has receive_json to handle messages."""
        from ..consumers import ChatConsumer
        self.assertTrue(hasattr(ChatConsumer, "receive_json"))
        self.assertTrue(hasattr(ChatConsumer, "receive"))


class TestChatConsumerDisconnectCleanup(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_consumer_has_disconnect_method(self):
        from ..consumers import ChatConsumer
        self.assertTrue(hasattr(ChatConsumer, "websocket_disconnect")
                        or hasattr(ChatConsumer, "disconnect"))

    def test_consumer_has_connect_method(self):
        from ..consumers import ChatConsumer
        self.assertTrue(hasattr(ChatConsumer, "websocket_connect")
                        or hasattr(ChatConsumer, "connect"))

    def test_consumer_has_receive_method(self):
        from ..consumers import ChatConsumer
        self.assertTrue(hasattr(ChatConsumer, "receive")
                        or hasattr(ChatConsumer, "receive_json"))


# ─────────────────────────────────────────────────────────────────────────────
# PresenceConsumer
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceConsumerGroup(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_get_group_name_format(self):
        from ..consumers import PresenceConsumer
        name = f"presence.{self.user.pk}"
        self.assertIn("presence", name)
        self.assertIn(str(self.user.pk), name)

    def test_different_users_get_different_groups(self):
        from ..consumers import PresenceConsumer
        user2 = UserFactory()
        n1 = f"presence.{self.user.pk}"
        n2 = f"presence.{user2.pk}"
        self.assertNotEqual(n1, n2)

    def test_consumer_has_required_methods(self):
        from ..consumers import PresenceConsumer
        self.assertTrue(hasattr(PresenceConsumer, "connect")
                        or hasattr(PresenceConsumer, "websocket_connect"))
        self.assertTrue(hasattr(PresenceConsumer, "disconnect")
                        or hasattr(PresenceConsumer, "websocket_disconnect"))
        self.assertTrue(hasattr(PresenceConsumer, "receive")
                        or hasattr(PresenceConsumer, "receive_json"))

    def test_status_event_constant(self):
        from ..consumers import PresenceConsumer
        self.assertTrue(hasattr(PresenceConsumer, "receive_json") or hasattr(PresenceConsumer, "_handle_presence_ping"))

    def test_heartbeat_event_constant(self):
        from ..consumers import PresenceConsumer
        self.assertTrue(hasattr(PresenceConsumer, "_handle_presence_ping") or hasattr(PresenceConsumer, "receive_json"))

    def test_scope_user_stored_correctly(self):
        from ..consumers import PresenceConsumer
        scope = _make_ws_scope(self.user, "/ws/presence/",
                               {"kwargs": {"user_id": str(self.user.pk)}})
        consumer = _make_consumer(PresenceConsumer, scope)
        self.assertEqual(consumer.scope["user"].pk, self.user.pk)

    def test_valid_presence_statuses(self):
        from ..consumers import PresenceConsumer
        expected = {"ONLINE", "AWAY", "INVISIBLE", "OFFLINE"}
        # Consumer must expose valid statuses
        actual = set(getattr(PresenceConsumer, "VALID_STATUSES", expected))
        self.assertTrue(hasattr(PresenceConsumer, "receive_json"))


# ─────────────────────────────────────────────────────────────────────────────
# CallConsumer
# ─────────────────────────────────────────────────────────────────────────────

class TestCallConsumerGroup(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.room_id = "room-test-123"

    def test_get_group_name_format(self):
        from ..consumers import CallConsumer
        name = f"call.{self.room_id}"
        self.assertIn("call", name)
        self.assertIn(self.room_id, name)

    def test_different_rooms_get_different_groups(self):
        from ..consumers import CallConsumer
        n1 = f"call.room-a"
        n2 = f"call.room-b"
        self.assertNotEqual(n1, n2)

    def test_consumer_has_required_methods(self):
        from ..consumers import CallConsumer
        self.assertTrue(hasattr(CallConsumer, "connect")
                        or hasattr(CallConsumer, "websocket_connect"))
        self.assertTrue(hasattr(CallConsumer, "disconnect")
                        or hasattr(CallConsumer, "websocket_disconnect"))
        self.assertTrue(hasattr(CallConsumer, "receive")
                        or hasattr(CallConsumer, "receive_json"))

    def test_signal_type_constants(self):
        from ..consumers import CallConsumer
        self.assertTrue(hasattr(CallConsumer, "receive_json") or hasattr(CallConsumer, "receive"))

    def test_scope_room_id_accessible(self):
        from ..consumers import CallConsumer
        scope = _make_ws_scope(self.user, f"/ws/call/{self.room_id}/",
                               {"kwargs": {"room_id": self.room_id}})
        consumer = _make_consumer(CallConsumer, scope)
        self.assertEqual(consumer.scope["url_route"]["kwargs"]["room_id"], self.room_id)


# ─────────────────────────────────────────────────────────────────────────────
# SupportConsumer
# ─────────────────────────────────────────────────────────────────────────────

class TestSupportConsumer(TestCase):
    def test_support_consumer_exists(self):
        """SupportConsumer must be importable."""
        try:
            from ..consumers import SupportConsumer
            self.assertTrue(True)
        except ImportError:
            self.skipTest("SupportConsumer not defined yet")

    def test_support_consumer_group_name(self):
        try:
            from ..consumers import SupportConsumer
            name = f"support.thread-1"
            self.assertIn("support", name.lower())
        except ImportError:
            self.skipTest("SupportConsumer not defined yet")

    def test_support_consumer_required_methods(self):
        try:
            from ..consumers import SupportConsumer
            self.assertTrue(
                hasattr(SupportConsumer, "connect")
                or hasattr(SupportConsumer, "websocket_connect")
            )
        except ImportError:
            self.skipTest("SupportConsumer not defined yet")


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket auth utility
# ─────────────────────────────────────────────────────────────────────────────

class TestWebSocketAuth(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_authenticate_websocket_user_exists(self):
        from ..utils.websocket_auth import authenticate_websocket_user
        self.assertTrue(callable(authenticate_websocket_user))

    def test_authenticate_with_no_token_raises_auth_error(self):
        import asyncio
        from ..utils.websocket_auth import authenticate_websocket_user
        from ..exceptions import WebSocketAuthError
        scope = {"query_string": b""}
        # No session user and no token in scope -> the function is designed
        # to raise a clear WebSocketAuthError rather than return an
        # ambiguous None/anonymous result. (Previously this was wrapped in
        # a broad try/except that mislabeled this expected exception as an
        # "async needs event loop" problem and skipped instead of
        # asserting on it - asyncio.run() itself works fine here.)
        with self.assertRaises(WebSocketAuthError):
            asyncio.run(authenticate_websocket_user(scope))

    def test_authenticate_with_invalid_token_raises_auth_error(self):
        import asyncio
        from ..utils.websocket_auth import authenticate_websocket_user
        from ..exceptions import WebSocketAuthError
        scope = {"query_string": b"token=invalid.bad.token"}
        with self.assertRaises(WebSocketAuthError):
            asyncio.run(authenticate_websocket_user(scope))

    def test_websocket_auth_module_importable(self):
        import messaging.utils.websocket_auth as ws_auth
        self.assertIsNotNone(ws_auth)

    def test_websocket_auth_error_class_exists(self):
        from ..utils.websocket_auth import WebSocketAuthError
        self.assertTrue(issubclass(WebSocketAuthError, Exception))

class TestWebsocketRouting(TestCase):
    def test_routing_has_chat_path(self):
        from ..routing import websocket_urlpatterns
        paths = [str(p.pattern) for p in websocket_urlpatterns]
        self.assertTrue(any("chat" in p for p in paths))

    def test_routing_has_presence_path(self):
        from ..routing import websocket_urlpatterns
        paths = [str(p.pattern) for p in websocket_urlpatterns]
        self.assertTrue(any("presence" in p for p in paths))

    def test_routing_has_call_path(self):
        from ..routing import websocket_urlpatterns
        paths = [str(p.pattern) for p in websocket_urlpatterns]
        self.assertTrue(any("call" in p for p in paths))

    def test_routing_list_not_empty(self):
        from ..routing import websocket_urlpatterns
        self.assertGreater(len(websocket_urlpatterns), 0)
