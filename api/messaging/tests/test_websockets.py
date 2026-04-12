"""
WebSocket consumer tests using channels.testing.
Covers: ChatConsumer, SupportConsumer, PresenceConsumer, CallConsumer.
"""
from __future__ import annotations

import json
import pytest
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.test import TestCase, TransactionTestCase
from unittest.mock import patch, AsyncMock, MagicMock

from .factories import (
    UserFactory, InternalChatFactory, ChatParticipantFactory,
    ChatMessageFactory, SupportThreadFactory, CallSessionFactory,
)
from ..consumers import ChatConsumer, SupportConsumer, PresenceConsumer, CallConsumer
from ..routing import websocket_urlpatterns


def _make_scope(user, path: str, url_route: dict) -> dict:
    return {
        "type": "websocket",
        "path": path,
        "url_route": {"kwargs": url_route},
        "headers": [],
        "user": user,
        "session": {},
        "client": ["127.0.0.1", 12345],
    }


class TestChatConsumerConnect(TestCase):
    """Test ChatConsumer connection lifecycle."""

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_connect_success(self, mock_auth):
        mock_auth.return_value = self.user
        scope = _make_scope(self.user, f"/ws/messaging/chat/{self.chat.id}/", {"chat_id": str(self.chat.id)})
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), scope)

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "connection.established")
        self.assertEqual(response["chat_id"], str(self.chat.id))

        await communicator.disconnect()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_connect_fails_if_auth_error(self, mock_auth):
        from ..exceptions import WebSocketAuthError
        mock_auth.side_effect = WebSocketAuthError("Invalid token")
        scope = _make_scope(self.user, "/ws/messaging/chat/xxx/", {"chat_id": "xxx"})
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), scope)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_connect_fails_if_not_participant(self, mock_auth):
        outsider = UserFactory()
        mock_auth.return_value = outsider
        scope = _make_scope(outsider, f"/ws/messaging/chat/{self.chat.id}/", {"chat_id": str(self.chat.id)})
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), scope)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4003)


class TestChatConsumerMessages(TransactionTestCase):
    """Test message sending and receiving."""

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    @patch("messaging.consumers.ChatConsumer._save_message")
    @patch("messaging.consumers.ChatConsumer._check_content", return_value=(False, ""))
    @patch("messaging.consumers.ChatConsumer._check_rate_limit")
    async def test_send_message_broadcasts_to_group(
        self, mock_rl, mock_spam, mock_save, mock_auth
    ):
        mock_auth.return_value = self.user
        mock_msg = MagicMock()
        mock_msg.id = "11111111-1111-1111-1111-111111111111"
        mock_msg.content = "Hello"
        mock_msg.message_type = "TEXT"
        mock_msg.priority = "NORMAL"
        mock_msg.is_forwarded = False
        mock_msg.attachments = []
        mock_msg.mentions = []
        mock_msg.poll_data = None
        mock_msg.location_data = None
        from django.utils import timezone
        mock_msg.created_at = timezone.now()
        mock_save.return_value = mock_msg

        scope = _make_scope(self.user, f"/ws/messaging/chat/{self.chat.id}/", {"chat_id": str(self.chat.id)})
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), scope)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from()  # connection.established

        await communicator.send_json_to({
            "type": "chat.message",
            "content": "Hello",
        })

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "chat_message_new")
        self.assertEqual(response["content"], "Hello")

        await communicator.disconnect()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_send_empty_message_returns_error(self, mock_auth):
        mock_auth.return_value = self.user
        scope = _make_scope(self.user, f"/ws/messaging/chat/{self.chat.id}/", {"chat_id": str(self.chat.id)})
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), scope)
        await communicator.connect()
        await communicator.receive_json_from()  # connection.established

        await communicator.send_json_to({
            "type": "chat.message",
            "content": "   ",
        })

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["code"], "empty_content")

        await communicator.disconnect()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_typing_indicator(self, mock_auth):
        mock_auth.return_value = self.user
        scope = _make_scope(self.user, f"/ws/messaging/chat/{self.chat.id}/", {"chat_id": str(self.chat.id)})
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), scope)
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            "type": "chat.typing",
            "is_typing": True,
        })

        # Should not receive own typing (user_id filter)
        self.assertTrue(await communicator.receive_nothing())
        await communicator.disconnect()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_ack_delivered_handler(self, mock_auth):
        mock_auth.return_value = self.user
        scope = _make_scope(self.user, f"/ws/messaging/chat/{self.chat.id}/", {"chat_id": str(self.chat.id)})
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), scope)
        await communicator.connect()
        await communicator.receive_json_from()

        with patch("messaging.consumers.ChatConsumer._record_delivered") as mock_delivered:
            await communicator.send_json_to({
                "type": "chat.ack.delivered",
                "message_id": "test-msg-123",
            })
            await communicator.disconnect()


class TestPresenceConsumer(TestCase):
    def setUp(self):
        self.user = UserFactory()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    @patch("messaging.consumers.PresenceConsumer._go_online")
    async def test_connect_sets_online(self, mock_online, mock_auth):
        mock_auth.return_value = self.user
        scope = _make_scope(self.user, "/ws/messaging/presence/", {})
        communicator = WebsocketCommunicator(PresenceConsumer.as_asgi(), scope)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        mock_online.assert_called_once()

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "presence.connected")
        self.assertEqual(response["status"], "ONLINE")

        await communicator.disconnect()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    @patch("messaging.consumers.PresenceConsumer._go_online")
    async def test_ping_pong(self, mock_online, mock_auth):
        mock_auth.return_value = self.user
        scope = _make_scope(self.user, "/ws/messaging/presence/", {})
        communicator = WebsocketCommunicator(PresenceConsumer.as_asgi(), scope)
        await communicator.connect()
        await communicator.receive_json_from()  # connected

        await communicator.send_json_to({"type": "presence.ping"})
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "presence.pong")

        await communicator.disconnect()


class TestCallConsumer(TestCase):
    def setUp(self):
        self.caller = UserFactory()
        self.callee = UserFactory()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    @patch("messaging.consumers.CallConsumer._verify_room_access", return_value=True)
    async def test_connect_broadcasts_peer_joined(self, mock_access, mock_auth):
        mock_auth.return_value = self.caller
        room_id = "testroom1234"
        scope = _make_scope(self.caller, f"/ws/messaging/call/{room_id}/", {"room_id": room_id})
        communicator = WebsocketCommunicator(CallConsumer.as_asgi(), scope)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    @patch("messaging.consumers.CallConsumer._verify_room_access", return_value=True)
    async def test_relay_offer(self, mock_access, mock_auth):
        mock_auth.return_value = self.caller
        room_id = "testroom5678"
        scope = _make_scope(self.caller, f"/ws/messaging/call/{room_id}/", {"room_id": room_id})
        communicator = WebsocketCommunicator(CallConsumer.as_asgi(), scope)
        await communicator.connect()

        await communicator.send_json_to({
            "type": "call.offer",
            "sdp": "v=0\r\no=- ...",
            "to_user_id": str(self.callee.pk),
        })
        await communicator.disconnect()


class TestSupportConsumer(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.agent = UserFactory(is_staff=True)
        self.thread = SupportThreadFactory(user=self.user)

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_connect_success(self, mock_auth):
        mock_auth.return_value = self.user
        scope = _make_scope(
            self.user, f"/ws/messaging/support/{self.thread.id}/",
            {"thread_id": str(self.thread.id)}
        )
        communicator = WebsocketCommunicator(SupportConsumer.as_asgi(), scope)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "connection.established")

        await communicator.disconnect()

    @pytest.mark.asyncio
    @patch("messaging.utils.websocket_auth.authenticate_websocket_user")
    async def test_outsider_cannot_connect(self, mock_auth):
        outsider = UserFactory()
        mock_auth.return_value = outsider
        scope = _make_scope(
            outsider, f"/ws/messaging/support/{self.thread.id}/",
            {"thread_id": str(self.thread.id)}
        )
        communicator = WebsocketCommunicator(SupportConsumer.as_asgi(), scope)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4003)


class TestMessageDeliveryIntegration(TestCase):
    """Integration tests for the full message delivery pipeline."""

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_message_saved_with_sent_status(self):
        from .. import services
        msg = services.send_chat_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk, content="Test"
        )
        self.assertEqual(msg.status, "SENT")

    def test_delivery_manager_mark_delivered(self):
        from ..utils.delivery_manager import mark_delivered, get_delivery_status
        from .. import services
        msg = services.send_chat_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk, content="Test"
        )
        with patch("messaging.tasks.update_delivery_status_task.delay"):
            mark_delivered(message_id=str(msg.id), user_id=self.user.pk)
            status = get_delivery_status(str(msg.id))
            self.assertIn(str(self.user.pk), status)

    def test_offline_queue_flow(self):
        from ..utils.delivery_manager import (
            queue_message_for_offline_user, flush_offline_queue
        )
        msg_data = {"message_id": "test-123", "content": "Hello offline"}
        queue_message_for_offline_user(self.user.pk, msg_data)
        messages = flush_offline_queue(self.user.pk)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["message_id"], "test-123")

        # Queue should be empty now
        messages2 = flush_offline_queue(self.user.pk)
        self.assertEqual(len(messages2), 0)
