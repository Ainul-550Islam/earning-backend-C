"""
test_consumers_audit_fix.py
=============================
Audit finding (Part 19): ChatConsumer.receive_json() already had an
isinstance(content, dict) guard and a comprehensive try/except around
its handler dispatch (from an earlier session's WebSocket coverage
pass). SupportConsumer, PresenceConsumer, and CallConsumer never got
the same treatment:
  - SupportConsumer: content.get("type") ran BEFORE the try/except, so
    non-dict input raised AttributeError outside the handler and
    crashed the connection uncleanly anyway.
  - PresenceConsumer: no isinstance guard AND no try/except at all -
    any exception in any handler crashed the connection.
  - CallConsumer: same as PresenceConsumer, plus needed a new _error()
    helper (previously inlined once, only for the unknown-type case).

Fixed all three to match ChatConsumer's pattern. These tests connect
for real (WebsocketCommunicator + URLRouter, same approach as
test_consumers_integration.py) and send malformed (non-dict) payloads
to prove the connection survives and gets a clean error instead of
dying.
"""
from __future__ import annotations

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TestCase

from .factories import CallSessionFactory, ChatParticipantFactory, InternalChatFactory, UserFactory
from ..models import SupportThread
from ..routing import websocket_urlpatterns

TIMEOUT = 5


async def _connected(path, user):
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), path)
    communicator.scope["user"] = user
    connected, _ = await communicator.connect(timeout=TIMEOUT)
    return communicator, connected


class TestSupportConsumerMalformedInput(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.thread = SupportThread.objects.create(user=self.user, subject="Help please")

    async def test_non_dict_payload_returns_clean_error_not_crash(self):
        comm, ok = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established
        await comm.send_to(text_data='"just a string, not an object"')
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "invalid_format")
        # Connection must still be alive after the malformed message.
        await comm.send_json_to({"type": "support.typing"})
        await comm.disconnect()

    async def test_list_payload_returns_clean_error_not_crash(self):
        comm, ok = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established
        await comm.send_to(text_data="[1, 2, 3]")
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "invalid_format")
        await comm.disconnect()


class TestPresenceConsumerMalformedInput(TestCase):
    def setUp(self):
        self.user = UserFactory()

    async def test_non_dict_payload_returns_clean_error_not_crash(self):
        comm, ok = await _connected("/ws/messaging/presence/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # presence.connected
        await comm.send_to(text_data="42")
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "invalid_format")
        # Connection must still work afterward.
        await comm.send_json_to({"type": "presence.ping"})
        resp2 = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp2["type"], "presence.pong")
        await comm.disconnect()

    async def test_unknown_type_now_returns_error_instead_of_silence(self):
        """Consistency fix: every other consumer already errors on an
        unrecognized type; PresenceConsumer silently did nothing."""
        comm, ok = await _connected("/ws/messaging/presence/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # presence.connected
        await comm.send_json_to({"type": "presence.made_up_type"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "unknown_type")
        await comm.disconnect()

    async def test_handler_exception_returns_clean_error_not_crash(self):
        from unittest.mock import patch
        comm, ok = await _connected("/ws/messaging/presence/", self.user)
        self.assertTrue(ok)
        await comm.receive_json_from(timeout=TIMEOUT)  # presence.connected
        with patch(
            "messaging.consumers.PresenceConsumer._go_online",
            side_effect=RuntimeError("boom"),
        ):
            await comm.send_json_to({"type": "presence.ping"})
            resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "error")
        await comm.disconnect()


class TestCallConsumerMalformedInput(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.call = CallSessionFactory(chat=self.chat, initiated_by=self.user, status="RINGING")
        self.call.participants.add(self.user)

    async def test_non_dict_payload_returns_clean_error_not_crash(self):
        comm, ok = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.user)
        self.assertTrue(ok)
        await comm.send_to(text_data="null")
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "invalid_format")
        await comm.disconnect()

    async def test_still_functions_after_malformed_message(self):
        comm, ok = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.user)
        self.assertTrue(ok)
        await comm.send_to(text_data='"oops"')
        await comm.receive_json_from(timeout=TIMEOUT)  # the error response
        # call.end should still work normally afterward
        await comm.send_json_to({"type": "call.end"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "call.ended")
        await comm.disconnect()
