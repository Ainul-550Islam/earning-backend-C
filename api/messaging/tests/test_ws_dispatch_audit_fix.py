"""
test_ws_dispatch_audit_fix.py
===============================
Audit finding (Part 19): Channels' consumer dispatch does
getattr(self, event["type"]) and raises ValueError - killing the
connection - for any group_send with no matching handler method. This
codebase already had one documented case of it (cpa_conversion, "Part 6
audit fix" comment in consumers.py). Cross-checking every
send_websocket_event()/group_send() call site in the module against the
real handler methods that exist turned up 6 more, all dormant only
because the signals feeding them never fired before this session's
Part 19 signal-wiring fix (test_signals_audit_fix.py) made them
reachable for the first time:

  - message_edited_with_history's receiver: mapped to a handler name
    that doesn't exist at all (message_edited vs. the real
    chat_message_edited), AND even pointed at the right name would have
    produced a differently-shaped payload than the pre-existing
    WS-native edit path. Rewritten to match that path exactly instead.
  - disappearing_config_changed, voice_message_transcribed,
    message_forwarded, link_previews_fetched, story_created: no handler
    method existed at all. Added chat_disappearing_changed,
    voice_transcribed, message_forwarded, message_link_previews (all on
    ChatConsumer) and story_created (on PresenceConsumer).
  - cpa_notification: same gap, found while auditing the CPA-signals
    path (deliver_cpa_notification_task) rather than receivers.py.

Also found and fixed while tracing this: DeviceBroadcastView (a public
HTTP endpoint) passed a client-supplied event_type straight into
group_send with no validation, so any authenticated user could crash
their own (or, if staff, any user's) other connected devices just by
POSTing an event_type that doesn't map to a real handler - now
allowlisted to the two handlers that endpoint is actually meant for.
"""
from __future__ import annotations

from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TestCase
from rest_framework.test import APIClient

from .factories import ChatMessageFactory, ChatParticipantFactory, InternalChatFactory, UserFactory
from .. import services
from ..consumers import _presence_group, _user_devices_group
from ..routing import websocket_urlpatterns

TIMEOUT = 5


async def _connected(path, user):
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), path)
    communicator.scope["user"] = user
    connected, _ = await communicator.connect(timeout=TIMEOUT)
    return communicator, connected


class TestChatConsumerNewHandlersDoNotCrash(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.group = f"chat_{str(self.chat.id).replace('-', '')}"

    async def _send_and_receive(self, event_type_dotted, extra_data):
        comm, ok = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established
        channel_layer = get_channel_layer()
        await channel_layer.group_send(self.group, {
            "type": event_type_dotted.replace(".", "_"),
            "data": extra_data,
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        await comm.disconnect()
        return resp

    async def test_chat_disappearing_changed_reaches_client(self):
        resp = await self._send_and_receive("chat.disappearing_changed", {"chat_id": str(self.chat.id), "is_enabled": True})
        self.assertEqual(resp["type"], "chat.disappearing_changed")
        self.assertTrue(resp["is_enabled"])

    async def test_voice_transcribed_reaches_client(self):
        resp = await self._send_and_receive("voice.transcribed", {"message_id": "abc", "text": "hi"})
        self.assertEqual(resp["type"], "voice.transcribed")
        self.assertEqual(resp["text"], "hi")

    async def test_message_forwarded_reaches_client(self):
        resp = await self._send_and_receive("message.forwarded", {"message_id": "abc"})
        self.assertEqual(resp["type"], "message.forwarded")

    async def test_message_link_previews_reaches_client(self):
        resp = await self._send_and_receive("message.link_previews", {"previews": []})
        self.assertEqual(resp["type"], "message.link_previews")

    async def test_cpa_notification_reaches_client(self):
        comm, ok = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established
        channel_layer = get_channel_layer()
        await channel_layer.group_send(_user_devices_group(self.user.pk), {
            "type": "cpa_notification", "data": {"id": "1", "title": "Payout sent"},
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "cpa.notification.received")
        await comm.disconnect()


class TestPresenceConsumerStoryCreatedDoesNotCrash(TestCase):
    async def test_story_created_reaches_client(self):
        user = await sync_to_async(UserFactory)()
        comm, ok = await _connected("/ws/messaging/presence/", user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # presence.connected
        channel_layer = get_channel_layer()
        await channel_layer.group_send(_presence_group(user.pk), {
            "type": "story_created", "data": {"story_id": "s1"},
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "story.created")
        await comm.disconnect()


class TestMessageEditedBroadcastMatchesWsNativeShape(TestCase):
    """The REST-edit path (services.edit_message_with_history) must
    produce the exact same event shape the WS-native edit path
    (consumers.py:_handle_edit) already produces, both dispatched via
    the real chat_message_edited handler."""

    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="original")

    async def test_rest_edit_reaches_chat_message_edited_handler_flat(self):
        comm, ok = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established
        await sync_to_async(services.edit_message_with_history)(
            message_id=str(self.msg.id), user_id=self.user.pk, new_content="edited via REST",
        )
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.message.edited")
        # Flat, not nested under "data" - matches _handle_edit's shape exactly.
        self.assertEqual(resp["message_id"], str(self.msg.id))
        self.assertEqual(resp["content"], "edited via REST")
        self.assertNotIn("data", resp)
        await comm.disconnect()


class TestDeviceBroadcastViewAllowlist(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.user)

    def test_unknown_event_type_rejected_with_400_not_crash(self):
        r = self.client_api.post("/messaging/devices/broadcast/", {
            "event_type": "chat.message.new", "data": {"content": "spoofed!"},
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("chat.cross_device.read", r.data["allowed"])

    def test_allowed_event_type_still_works(self):
        with patch("messaging.utils.device_sync.broadcast_to_all_user_devices", return_value=2) as mock_bc:
            r = self.client_api.post("/messaging/devices/broadcast/", {
                "event_type": "chat.cross_device.read", "data": {"message_id": "abc"},
            }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["notified"], 2)
        mock_bc.assert_called_once()

    def test_missing_event_type_still_400s(self):
        r = self.client_api.post("/messaging/devices/broadcast/", {"data": {}}, format="json")
        self.assertEqual(r.status_code, 400)
