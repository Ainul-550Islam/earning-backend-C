"""
Real WebSocket protocol integration tests for messaging.consumers.

Audit finding: test_consumers.py and test_websockets.py (1437 tests between
them) never actually drove a consumer's connect/receive_json/disconnect
lifecycle - every test was structural (hasattr(Consumer, "connect"),
_chat_group(id) == f"...", etc.). Zero usage of channels.testing.
WebsocketCommunicator existed anywhere in the suite. consumers.py sat at
26% line coverage as a direct result - the single largest blind spot in
the module.

These tests use the real InMemoryChannelLayer (configured in conftest.py)
and the real URLRouter from messaging.routing, so routing, auth, group
membership, and broadcast fan-out are all exercised as they would be in
production - not mocked.
"""
from __future__ import annotations

import asyncio

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TestCase

from .factories import (
    CallSessionFactory,
    ChatParticipantFactory,
    GroupChatFactory,
    InternalChatFactory,
    SupportThreadFactory,
    UserFactory,
)
from ..choices import ChatStatus, MessageType, SupportThreadStatus
from ..models import (
    ChatMessage,
    ChatParticipant,
    MessageReaction,
    PollVote,
    SupportMessage,
    UserPresence,
)
from ..routing import websocket_urlpatterns

TIMEOUT = 5


async def _connected(path, user):
    """Build a communicator through the real router, inject `user`
    into scope (as AuthMiddlewareStack would), and connect it."""
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), path)
    communicator.scope["user"] = user
    connected, _ = await communicator.connect(timeout=TIMEOUT)
    return communicator, connected


class TestChatConsumerConnect(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        self.participant = ChatParticipantFactory(chat=self.chat, user=self.user)

    async def test_connect_succeeds_for_participant(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)

        msg = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(msg["type"], "connection.established")
        self.assertEqual(msg["chat_id"], str(self.chat.id))
        self.assertEqual(msg["pending_count"], 0)
        await comm.disconnect()

    async def test_connect_sets_presence_online(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)

        presence = await UserPresence.objects.aget(user=self.user)
        self.assertEqual(presence.status, "ONLINE")
        await comm.disconnect()

    async def test_connect_rejected_for_non_participant(self):
        outsider = await sync_to_async(UserFactory)()
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", outsider)
        self.assertFalse(connected)

    async def test_connect_rejected_for_archived_chat(self):
        self.chat.status = ChatStatus.ARCHIVED
        await self.chat.asave(update_fields=["status"])
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertFalse(connected)

    async def test_connect_rejected_unauthenticated(self):
        from django.contrib.auth.models import AnonymousUser
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", AnonymousUser())
        self.assertFalse(connected)


class TestChatConsumerCpaConversion(TestCase):
    """
    Regression tests (Part 6 audit): utils/postback_tracker.py's
    notify_conversion_via_ws() has always group_sent event_type=
    "cpa.conversion" to the correct per-user group
    (user_devices_{affiliate_id}, matching consumers._user_devices_group()
    exactly), but no consumer anywhere defined a matching cpa_conversion()
    handler method. Channels' AsyncConsumer.dispatch() does
    getattr(self, event["type"]) and raises ValueError when nothing
    matches, so this event was never actually deliverable to any connected
    client - unlike its sibling reaction_added/device_sync_* handlers,
    which do exist. These use the real channel layer/router (not a mock)
    so they exercise the actual dispatch path that was broken.
    """

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        self.participant = ChatParticipantFactory(chat=self.chat, user=self.user)

    async def test_cpa_conversion_delivered_to_connected_affiliate(self):
        from ..utils.postback_tracker import notify_conversion_via_ws
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)  # discard connection.established

        result = await sync_to_async(notify_conversion_via_ws)(
            affiliate_id=self.user.pk,
            conversion_id="conv-1",
            offer_id=42,
            offer_name="Gaming App",
            payout_amount="$3.00",
            click_id="click-abc",
        )
        self.assertTrue(result)

        evt = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(evt["type"], "cpa.conversion.received")
        self.assertEqual(evt["conversion_id"], "conv-1")
        self.assertEqual(evt["offer_id"], "42")
        self.assertEqual(evt["offer_name"], "Gaming App")
        self.assertEqual(evt["payout_amount"], "$3.00")
        self.assertEqual(evt["click_id"], "click-abc")
        await comm.disconnect()

    async def test_conversion_not_delivered_to_a_different_users_socket(self):
        from ..utils.postback_tracker import notify_conversion_via_ws
        other = await sync_to_async(UserFactory)()
        await sync_to_async(ChatParticipantFactory)(chat=self.chat, user=other)
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", other)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)  # discard connection.established

        await sync_to_async(notify_conversion_via_ws)(
            affiliate_id=self.user.pk,  # conversion belongs to self.user, not `other`
            conversion_id="conv-2", offer_id=1, offer_name="x", payout_amount="$1.00",
        )
        # `other` is on a different personal group - nothing further should arrive
        self.assertTrue(await comm.receive_nothing(timeout=0.3))
        await comm.disconnect()


class TestChatConsumerDisconnect(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    async def test_disconnect_sets_presence_offline(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)
        await comm.disconnect()

        presence = await UserPresence.objects.aget(user=self.user)
        self.assertEqual(presence.status, "OFFLINE")


class TestChatConsumerMessaging(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.chat = GroupChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatParticipantFactory(chat=self.chat, user=self.other)

    async def _both_connected(self):
        sender, ok1 = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(ok1)
        await sender.receive_json_from(timeout=TIMEOUT)
        listener, ok2 = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.other)
        self.assertTrue(ok2)
        await listener.receive_json_from(timeout=TIMEOUT)
        return sender, listener

    async def test_send_text_message_broadcasts_and_acks_sender(self):
        sender, listener = await self._both_connected()
        await sender.send_json_to({"type": "chat.message", "content": "hello there"})

        ack = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(ack["type"], "chat.message.sent_ack")
        self.assertIn("message_id", ack)

        broadcast = await listener.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(broadcast["type"], "chat_message_new")
        self.assertEqual(broadcast["content"], "hello there")

        exists = await ChatMessage.objects.filter(pk=ack["message_id"]).aexists()
        self.assertTrue(exists)
        await sender.disconnect()
        await listener.disconnect()

    async def test_empty_text_message_rejected(self):
        sender, listener = await self._both_connected()
        await sender.send_json_to({"type": "chat.message", "content": "   "})
        err = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(err["type"], "error")
        self.assertEqual(err["code"], "empty_content")
        await sender.disconnect()
        await listener.disconnect()

    async def test_unknown_message_type_returns_error(self):
        sender, listener = await self._both_connected()
        await sender.send_json_to({"type": "not.a.real.type"})
        err = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(err["type"], "error")
        self.assertEqual(err["code"], "unknown_type")
        await sender.disconnect()
        await listener.disconnect()

    async def test_non_dict_payload_rejected(self):
        sender, listener = await self._both_connected()
        await sender.send_to(text_data="[1, 2, 3]")
        err = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(err["code"], "invalid_format")
        await sender.disconnect()
        await listener.disconnect()

    async def test_oversized_payload_rejected(self):
        sender, listener = await self._both_connected()
        await sender.send_json_to({"type": "chat.message", "content": "x" * 70000})
        err = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(err["code"], "payload_too_large")
        await sender.disconnect()
        await listener.disconnect()

    async def test_typing_indicator_seen_by_other_not_self(self):
        sender, listener = await self._both_connected()
        await sender.send_json_to({"type": "chat.typing", "is_typing": True})

        typed = await listener.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(typed["type"], "chat.typing")
        self.assertEqual(typed["user_id"], str(self.user.pk))

        self.assertTrue(await sender.receive_nothing(timeout=0.3))
        await sender.disconnect()
        await listener.disconnect()

    async def test_edit_message_broadcasts_to_both(self):
        sender, listener = await self._both_connected()
        msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.user, content="original", message_type=MessageType.TEXT,
        )
        await sender.send_json_to({
            "type": "chat.message.edit", "message_id": str(msg.id), "content": "edited!",
        })
        for comm in (sender, listener):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            self.assertEqual(evt["type"], "chat.message.edited")
            self.assertEqual(evt["content"], "edited!")
        await sender.disconnect()
        await listener.disconnect()

    async def test_delete_message_broadcasts_to_both(self):
        sender, listener = await self._both_connected()
        msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.user, content="to delete", message_type=MessageType.TEXT,
        )
        await sender.send_json_to({"type": "chat.message.delete", "message_id": str(msg.id)})
        for comm in (sender, listener):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            self.assertEqual(evt["type"], "chat.message.deleted")
        await sender.disconnect()
        await listener.disconnect()

    async def test_reaction_add_and_remove(self):
        """
        NOTE: adding/removing a reaction currently triggers TWO separate
        broadcasts to every connected client for the same action:
          1. chat.reaction.added / chat.reaction.removed - fired by the
             message_reaction_added/removed Django signal receivers in
             receivers.py (via send_websocket_event), carrying just
             message_id/user_id/emoji.
          2. chat.reaction.update (action="add"/"remove") - fired directly
             by ChatConsumer._handle_reaction_add/_remove, carrying
             aggregated per-emoji counts.
        This may be intentional (two different frontend concerns: a
        notify-style event vs. a live reaction-count update) or accidental
        duplication - the receivers.py docstring claims it "notifies the
        message sender" but the implementation actually broadcasts to the
        whole chat group, not just the sender, which doesn't match either
        reading cleanly. Flagged for a deliberate decision; not silently
        changed here. This test pins down current behavior precisely so a
        future change to either path is a visible, deliberate diff.
        """
        sender, listener = await self._both_connected()
        msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.other, content="react to me", message_type=MessageType.TEXT,
        )
        await sender.send_json_to({
            "type": "chat.reaction.add", "message_id": str(msg.id), "emoji": "thumbsup",
        })
        for comm in (sender, listener):
            evt_types = set()
            for _ in range(2):
                evt = await comm.receive_json_from(timeout=TIMEOUT)
                evt_types.add(evt["type"])
            self.assertEqual(evt_types, {"chat.reaction.added", "chat.reaction.update"})

        exists = await MessageReaction.objects.filter(message=msg, user=self.user, emoji="thumbsup").aexists()
        self.assertTrue(exists)

        await sender.send_json_to({
            "type": "chat.reaction.remove", "message_id": str(msg.id), "emoji": "thumbsup",
        })
        for comm in (sender, listener):
            evt_types = set()
            for _ in range(2):
                evt = await comm.receive_json_from(timeout=TIMEOUT)
                evt_types.add(evt["type"])
            self.assertEqual(evt_types, {"chat.reaction.removed", "chat.reaction.update"})
        await sender.disconnect()
        await listener.disconnect()

    async def test_poll_vote_broadcasts_results(self):
        sender, listener = await self._both_connected()
        poll_msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.other, content="Pick one:", message_type=MessageType.POLL,
            poll_data={"options": [{"id": "opt_0", "text": "Yes"}, {"id": "opt_1", "text": "No"}]},
        )
        await sender.send_json_to({
            "type": "chat.poll.vote", "message_id": str(poll_msg.id), "option_id": "opt_0",
        })
        for comm in (sender, listener):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            self.assertEqual(evt["type"], "chat.poll.update")
            self.assertEqual(evt["option_id"], "opt_0")

        exists = await PollVote.objects.filter(message=poll_msg, user=self.user).aexists()
        self.assertTrue(exists)
        await sender.disconnect()
        await listener.disconnect()

    async def test_ack_delivered_notifies_original_sender_only(self):
        """Regression test for the 'or True' bug: chat_delivery_ack must only
        reach the original sender's connection, not every participant."""
        sender, listener = await self._both_connected()
        msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.user, content="track me", message_type=MessageType.TEXT,
        )
        await listener.send_json_to({"type": "chat.ack.delivered", "message_id": str(msg.id)})

        ack = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(ack["type"], "chat.delivery.ack")
        self.assertEqual(ack["message_id"], str(msg.id))

        self.assertTrue(await listener.receive_nothing(timeout=0.3))
        await sender.disconnect()
        await listener.disconnect()

    async def test_ack_read_broadcasts_receipt(self):
        sender, listener = await self._both_connected()
        msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.user, content="read me", message_type=MessageType.TEXT,
        )
        await listener.send_json_to({"type": "chat.ack.read", "message_id": str(msg.id)})
        for comm in (sender, listener):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            self.assertEqual(evt["type"], "chat.read.receipt")
            self.assertIn(str(msg.id), evt["message_ids"])
        await sender.disconnect()
        await listener.disconnect()

    async def test_mark_read_inbox_items(self):
        sender, listener = await self._both_connected()
        await sender.send_json_to({"type": "chat.mark_read", "item_ids": []})
        resp = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.marked_read")
        await sender.disconnect()
        await listener.disconnect()

    async def test_report_message(self):
        sender, listener = await self._both_connected()
        msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.other, content="reportable", message_type=MessageType.TEXT,
        )
        await sender.send_json_to({
            "type": "chat.report", "message_id": str(msg.id), "reason": "spam",
        })
        resp = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.reported")
        await sender.disconnect()
        await listener.disconnect()

    async def test_sync_request_returns_messages(self):
        sender, listener = await self._both_connected()
        await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.other, content="missed while offline",
            message_type=MessageType.TEXT,
        )
        await sender.send_json_to({"type": "chat.sync.request", "since": None})
        resp = await sender.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.sync.response")
        self.assertGreaterEqual(resp["count"], 1)
        await sender.disconnect()
        await listener.disconnect()

    async def test_forward_message_to_another_chat(self):
        sender, listener = await self._both_connected()
        target_chat = await sync_to_async(InternalChatFactory)()
        await ChatParticipant.objects.acreate(chat=target_chat, user=self.user, role="MEMBER")
        target_comm, ok = await _connected(f"/ws/messaging/chat/{target_chat.id}/", self.user)
        self.assertTrue(ok)
        await target_comm.receive_json_from(timeout=TIMEOUT)

        msg = await ChatMessage.objects.acreate(
            chat=self.chat, sender=self.other, content="forward me", message_type=MessageType.TEXT,
        )
        await sender.send_json_to({
            "type": "chat.message.forward",
            "message_id": str(msg.id),
            "target_chat_id": str(target_chat.id),
        })
        fwd = await target_comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(fwd["type"], "chat_message_new")
        self.assertTrue(fwd["is_forwarded"])
        await sender.disconnect()
        await listener.disconnect()
        await target_comm.disconnect()


class TestChatConsumerRateLimiting(TestCase):
    """
    Regression test for a confirmed bug: messaging.utils.rate_limiter used
    to define its own `RateLimitError(Exception)`, unrelated to
    messaging.exceptions.RateLimitError(MessagingError) which
    ChatConsumer.receive_json actually catches. check_message_rate() (the
    function _check_rate_limit() calls) raised the *utils* version, so
    `except RateLimitError` in receive_json never matched it - every
    WebSocket rate-limit violation fell through to the generic
    `except Exception` branch and was reported to the client as
    {"code": "server_error"} instead of {"code": "rate_limit",
    "retry_after": ...}. Fixed by unifying to one exception class. This
    drives the real send-message flow past the limit end-to-end (not just
    unit-testing the exception class) to prove the fix holds through the
    actual consumer dispatch path.
    """
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory()
        self.chat = GroupChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    async def test_exceeding_message_rate_limit_reports_rate_limit_not_server_error(self):
        from ..constants import MAX_MESSAGES_PER_MINUTE
        from unittest.mock import patch

        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established

        # notify_new_chat_message.delay() and fetch_link_previews_task.
        # apply_async() are both incidental to what this test verifies
        # (rate-limit enforcement, not notification/preview dispatch) -
        # chat_message_sent has two receivers (on_chat_message_sent and
        # on_chat_message_sent_postprocess), and in this standalone test
        # environment every Celery dispatch call attempts a real
        # connection to an unconfigured broker. Fine for a single
        # message; sending 30 in a tight loop compounds that cost enough
        # to occasionally exceed the receive timeout below. Mocked so
        # this test's timing reflects only the thing it's actually
        # testing.
        with patch("messaging.tasks.notify_new_chat_message.delay"), \
             patch("messaging.tasks.fetch_link_previews_task.apply_async"):
            # Send up to the limit - all should succeed. A lone connected
            # client both gets its own direct ack AND the group broadcast
            # (it's a member of its own chat's group), so drain two
            # messages per send rather than assuming a fixed order.
            for i in range(MAX_MESSAGES_PER_MINUTE):
                await comm.send_json_to({"type": "chat.message", "content": f"msg {i}"})
                first = await comm.receive_json_from(timeout=TIMEOUT)
                second = await comm.receive_json_from(timeout=TIMEOUT)
                types = {first["type"], second["type"]}
                self.assertEqual(types, {"chat.message.sent_ack", "chat_message_new"})

            # One more push over the limit - must be reported as a proper
            # rate_limit error, not swallowed into a generic server_error.
            # The rate check fails before any ack/broadcast is generated,
            # so exactly one message comes back.
            await comm.send_json_to({"type": "chat.message", "content": "one too many"})
            resp = await comm.receive_json_from(timeout=TIMEOUT)

        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "rate_limit")
        self.assertIn("retry_after", resp)
        await comm.disconnect()


class TestPresenceConsumer(TestCase):
    def setUp(self):
        self.user = UserFactory()

    async def test_connect_goes_online(self):
        comm, connected = await _connected("/ws/messaging/presence/", self.user)
        self.assertTrue(connected)
        msg = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(msg["type"], "presence.connected")
        presence = await UserPresence.objects.aget(user=self.user)
        self.assertEqual(presence.status, "ONLINE")
        await comm.disconnect()

    async def test_ping_pong(self):
        comm, connected = await _connected("/ws/messaging/presence/", self.user)
        await comm.receive_json_from(timeout=TIMEOUT)
        await comm.send_json_to({"type": "presence.ping"})
        pong = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(pong["type"], "presence.pong")
        await comm.disconnect()

    async def test_set_busy_status(self):
        comm, connected = await _connected("/ws/messaging/presence/", self.user)
        await comm.receive_json_from(timeout=TIMEOUT)
        await comm.send_json_to({"type": "presence.busy"})
        await asyncio.sleep(0.1)
        presence = await UserPresence.objects.aget(user=self.user)
        self.assertEqual(presence.status, "BUSY")
        await comm.disconnect()

    async def test_set_custom_status(self):
        comm, connected = await _connected("/ws/messaging/presence/", self.user)
        await comm.receive_json_from(timeout=TIMEOUT)
        await comm.send_json_to({
            "type": "presence.custom_status", "custom_status": "In a meeting", "emoji": "calendar",
        })
        await asyncio.sleep(0.1)
        presence = await UserPresence.objects.aget(user=self.user)
        self.assertEqual(presence.custom_status, "In a meeting")
        await comm.disconnect()

    async def test_disconnect_goes_offline(self):
        comm, connected = await _connected("/ws/messaging/presence/", self.user)
        await comm.receive_json_from(timeout=TIMEOUT)
        await comm.disconnect()
        presence = await UserPresence.objects.aget(user=self.user)
        self.assertEqual(presence.status, "OFFLINE")


class TestCallConsumer(TestCase):
    def setUp(self):
        self.caller = UserFactory()
        self.callee = UserFactory()
        self.call = CallSessionFactory(initiated_by=self.caller)

    async def _add_participants(self, *users):
        for u in users:
            await self.call.participants.aadd(u)

    async def test_connect_rejected_if_not_a_participant(self):
        comm, connected = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.caller)
        self.assertFalse(connected)

    async def test_connect_succeeds_for_participant_and_notifies_peer(self):
        await self._add_participants(self.caller, self.callee)
        callee_comm, ok1 = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.callee)
        self.assertTrue(ok1)

        caller_comm, ok2 = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.caller)
        self.assertTrue(ok2)

        joined = await callee_comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(joined["type"], "call.peer_joined")
        self.assertEqual(joined["user_id"], str(self.caller.pk))
        await caller_comm.disconnect()
        await callee_comm.disconnect()

    async def test_offer_relayed_to_peer_not_echoed_to_sender(self):
        await self._add_participants(self.caller, self.callee)
        callee_comm, _ = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.callee)
        caller_comm, _ = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.caller)
        await callee_comm.receive_json_from(timeout=TIMEOUT)

        await caller_comm.send_json_to({"type": "call.offer", "sdp": "v=0..."})
        relayed = await callee_comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(relayed["type"], "call.offer")
        self.assertEqual(relayed["payload"]["sdp"], "v=0...")

        self.assertTrue(await caller_comm.receive_nothing(timeout=0.3))
        await caller_comm.disconnect()
        await callee_comm.disconnect()

    async def test_mute_relayed_to_all_including_sender(self):
        await self._add_participants(self.caller, self.callee)
        callee_comm, _ = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.callee)
        caller_comm, _ = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.caller)
        await callee_comm.receive_json_from(timeout=TIMEOUT)

        await caller_comm.send_json_to({"type": "call.mute", "muted": True})
        relayed = await callee_comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(relayed["type"], "call.mute")
        await caller_comm.disconnect()
        await callee_comm.disconnect()

    async def test_end_call_broadcasts_to_all(self):
        await self._add_participants(self.caller, self.callee)
        callee_comm, _ = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.callee)
        caller_comm, _ = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.caller)
        await callee_comm.receive_json_from(timeout=TIMEOUT)

        await caller_comm.send_json_to({"type": "call.end"})
        ended = await callee_comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(ended["type"], "call.ended")
        await caller_comm.disconnect()
        await callee_comm.disconnect()


class TestSupportConsumer(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.agent = UserFactory(is_staff=True)
        self.thread = SupportThreadFactory(user=self.user, status=SupportThreadStatus.OPEN)

    async def test_user_connect_succeeds_not_agent(self):
        comm, connected = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        self.assertTrue(connected)
        msg = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertFalse(msg["is_agent"])
        await comm.disconnect()

    async def test_agent_connect_succeeds_is_agent(self):
        comm, connected = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.agent)
        self.assertTrue(connected)
        msg = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertTrue(msg["is_agent"])
        await comm.disconnect()

    async def test_unrelated_user_rejected(self):
        outsider = await sync_to_async(UserFactory)()
        comm, connected = await _connected(f"/ws/messaging/support/{self.thread.id}/", outsider)
        self.assertFalse(connected)

    async def test_user_reply_broadcasts_to_agent(self):
        user_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        await user_comm.receive_json_from(timeout=TIMEOUT)
        agent_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.agent)
        await agent_comm.receive_json_from(timeout=TIMEOUT)

        await user_comm.send_json_to({"type": "support.message", "content": "Need help"})
        for comm in (user_comm, agent_comm):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            self.assertEqual(evt["type"], "support_message_new")
            self.assertEqual(evt["content"], "Need help")

        exists = await SupportMessage.objects.filter(thread=self.thread, content="Need help").aexists()
        self.assertTrue(exists)
        await user_comm.disconnect()
        await agent_comm.disconnect()

    async def test_internal_note_only_visible_to_posting_agent(self):
        user_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        await user_comm.receive_json_from(timeout=TIMEOUT)
        agent_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.agent)
        await agent_comm.receive_json_from(timeout=TIMEOUT)

        await agent_comm.send_json_to({
            "type": "support.message", "content": "internal note", "is_internal_note": True,
        })
        note = await agent_comm.receive_json_from(timeout=TIMEOUT)
        self.assertTrue(note["is_internal_note"])

        self.assertTrue(await user_comm.receive_nothing(timeout=0.3))
        await user_comm.disconnect()
        await agent_comm.disconnect()

    async def test_non_agent_internal_note_flag_ignored(self):
        """A regular user cannot mark their own message as an internal note."""
        user_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        await user_comm.receive_json_from(timeout=TIMEOUT)
        agent_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.agent)
        await agent_comm.receive_json_from(timeout=TIMEOUT)

        await user_comm.send_json_to({
            "type": "support.message", "content": "fake internal", "is_internal_note": True,
        })
        evt = await agent_comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(evt["content"], "fake internal")
        self.assertFalse(evt["is_internal_note"])
        await user_comm.disconnect()
        await agent_comm.disconnect()

    async def test_agent_status_change_allowed(self):
        agent_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.agent)
        await agent_comm.receive_json_from(timeout=TIMEOUT)
        user_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        await user_comm.receive_json_from(timeout=TIMEOUT)

        await agent_comm.send_json_to({"type": "support.status.change", "status": "IN_PROGRESS"})
        for comm in (agent_comm, user_comm):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            self.assertEqual(evt["type"], "support.status.changed")
            self.assertEqual(evt["new_status"], "IN_PROGRESS")
        await agent_comm.disconnect()
        await user_comm.disconnect()

    async def test_non_agent_status_change_silently_ignored(self):
        user_comm, _ = await _connected(f"/ws/messaging/support/{self.thread.id}/", self.user)
        await user_comm.receive_json_from(timeout=TIMEOUT)

        await user_comm.send_json_to({"type": "support.status.change", "status": "CLOSED"})
        self.assertTrue(await user_comm.receive_nothing(timeout=0.3))
        await user_comm.disconnect()
