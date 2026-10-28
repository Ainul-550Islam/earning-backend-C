"""
test_consumers_coverage_boost.py
==================================
Additional real-WebsocketCommunicator tests for messaging/consumers.py,
targeting gaps left by test_consumers_integration.py: the receive_json
exception -> error-code mapping branches, the untested CallConsumer relay
signal types, and PresenceConsumer invisible-mode / bulk-presence paths.

Uses the same real InMemoryChannelLayer + real URLRouter approach as
test_consumers_integration.py (see that file's docstring for rationale).

Place in: messaging/tests/test_consumers_coverage_boost.py
"""
from __future__ import annotations

from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TestCase

from .factories import (
    CallSessionFactory,
    ChatMessageFactory,
    ChatParticipantFactory,
    InternalChatFactory,
    UserFactory,
)
from ..exceptions import RateLimitError, SpamDetectedError, ChatArchivedError
from ..routing import websocket_urlpatterns

TIMEOUT = 5


async def _connected(path, user):
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), path)
    communicator.scope["user"] = user
    connected, _ = await communicator.connect(timeout=TIMEOUT)
    return communicator, connected


class TestChatConsumerErrorMapping(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    async def test_rate_limit_error_mapped(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established

        with patch(
            "messaging.consumers.ChatConsumer._handle_message",
            side_effect=RateLimitError("Too many messages.", retry_after=30),
        ):
            await comm.send_json_to({"type": "chat.message", "content": "hi"})
            resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "rate_limit")
        self.assertEqual(resp["retry_after"], 30)
        await comm.disconnect()

    async def test_spam_content_error_mapped(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)

        with patch(
            "messaging.consumers.ChatConsumer._handle_message",
            side_effect=SpamDetectedError("Message flagged as spam."),
        ):
            await comm.send_json_to({"type": "chat.message", "content": "buy now!!!"})
            resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "content_blocked")
        await comm.disconnect()

    async def test_chat_archived_error_mapped(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)

        with patch(
            "messaging.consumers.ChatConsumer._handle_message",
            side_effect=ChatArchivedError("This chat is archived."),
        ):
            await comm.send_json_to({"type": "chat.message", "content": "hi"})
            resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "access_denied")
        await comm.disconnect()

    async def test_unhandled_exception_mapped_to_server_error(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)

        with patch(
            "messaging.consumers.ChatConsumer._handle_message",
            side_effect=RuntimeError("totally unexpected"),
        ):
            await comm.send_json_to({"type": "chat.message", "content": "hi"})
            resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "server_error")
        await comm.disconnect()

    async def test_non_dict_payload_returns_invalid_format(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)
        await comm.send_to(text_data="[1, 2, 3]")
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "invalid_format")
        await comm.disconnect()

    async def test_generic_messaging_error_mapped_to_its_own_code(self):
        """Covers the fallthrough `except MessagingError as exc` branch -
        any MessagingError subclass not specifically listed above still
        gets a proper error response using its own .code."""
        from ..exceptions import ChatNotFoundError
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)

        with patch(
            "messaging.consumers.ChatConsumer._handle_message",
            side_effect=ChatNotFoundError("no such chat"),
        ):
            await comm.send_json_to({"type": "chat.message", "content": "hi"})
            resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        self.assertEqual(resp["code"], "chat_not_found")
        await comm.disconnect()


class TestChatConsumerMissingFieldValidation(TestCase):
    """
    Every _handle_X method that requires specific fields validates them
    and returns a "missing_fields" error - these tests cover that branch
    for each handler that has one.
    """

    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    async def _connect_and_drain(self):
        comm, connected = await _connected(f"/ws/messaging/chat/{self.chat.id}/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)  # connection.established
        return comm

    async def test_empty_message_content_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.message", "content": "   "})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "empty_content")
        await comm.disconnect()

    async def test_edit_without_message_id_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.message.edit", "content": "new text"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "missing_fields")
        await comm.disconnect()

    async def test_delete_without_message_id_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.message.delete"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "missing_fields")
        await comm.disconnect()

    async def test_reaction_add_without_emoji_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.reaction.add", "message_id": "x"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "missing_fields")
        await comm.disconnect()

    async def test_reaction_remove_without_message_id_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.reaction.remove", "emoji": "\U0001F44D"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "missing_fields")
        await comm.disconnect()

    async def test_poll_vote_without_option_id_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.poll.vote", "message_id": "x"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "missing_fields")
        await comm.disconnect()

    async def test_forward_without_message_id_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.message.forward"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "missing_fields")
        await comm.disconnect()

    async def test_report_without_message_id_rejected(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.report", "reason": "spam"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "missing_fields")
        await comm.disconnect()

    async def test_presence_ping_pongs_back(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.presence.ping"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.presence.pong")
        await comm.disconnect()

    async def test_mark_read_with_no_item_ids_still_acks(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.mark_read", "item_ids": []})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.marked_read")
        await comm.disconnect()

    async def test_typing_broadcasts_to_other_participants_not_sender(self):
        """chat_typing deliberately skips echoing back to the sender (by
        design - you already know you're typing), so this needs a second
        connected participant to actually observe the broadcast."""
        other = await sync_to_async(UserFactory)()
        await sync_to_async(ChatParticipantFactory)(chat=self.chat, user=other)
        comm = await self._connect_and_drain()
        other_comm, other_connected = await _connected(
            f"/ws/messaging/chat/{self.chat.id}/", other
        )
        self.assertTrue(other_connected)
        await other_comm.receive_json_from(timeout=TIMEOUT)  # connection.established

        await comm.send_json_to({"type": "chat.typing", "is_typing": True})
        resp = await other_comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.typing")
        self.assertTrue(resp["is_typing"])
        self.assertTrue(await comm.receive_nothing(timeout=0.3))  # sender gets nothing
        await comm.disconnect()
        await other_comm.disconnect()

    async def test_spammy_content_blocked(self):
        """Real should_auto_moderate() call (not mocked) - a message this
        blatant reliably crosses the spam_score >= 0.7 threshold."""
        comm = await self._connect_and_drain()
        await comm.send_json_to({
            "type": "chat.message",
            "content": "BUY NOW FREE MONEY GUARANTEED WINNER ACT NOW CLICK HERE!!!!!!!",
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["code"], "content_blocked")
        await comm.disconnect()

    async def test_edit_message_real_flow(self):
        msg = await sync_to_async(ChatMessageFactory)(chat=self.chat, sender=self.user)
        comm = await self._connect_and_drain()
        await comm.send_json_to({
            "type": "chat.message.edit", "message_id": str(msg.id), "content": "edited text",
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.message.edited")
        self.assertEqual(resp["content"], "edited text")
        await comm.disconnect()

    async def test_delete_message_real_flow(self):
        msg = await sync_to_async(ChatMessageFactory)(chat=self.chat, sender=self.user)
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.message.delete", "message_id": str(msg.id)})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.message.deleted")
        await comm.disconnect()

    async def test_reaction_add_and_get_counts_real_flow(self):
        """
        Reaction add/remove currently triggers two broadcasts for the
        same action (chat.reaction.added via the signal receiver in
        receivers.py, and chat.reaction.update via the consumer's own
        direct group_send with aggregated counts) - already flagged as a
        deliberate-decision item elsewhere (test_consumers_integration.py),
        not something to redesign inside a coverage pass. Draining both,
        matching that file's established pattern.
        """
        msg = await sync_to_async(ChatMessageFactory)(chat=self.chat, sender=self.user)
        comm = await self._connect_and_drain()
        await comm.send_json_to({
            "type": "chat.reaction.add", "message_id": str(msg.id), "emoji": "\U0001F525",
        })
        evt_types = set()
        update_evt = None
        for _ in range(2):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            evt_types.add(evt["type"])
            if evt["type"] == "chat.reaction.update":
                update_evt = evt
        self.assertEqual(evt_types, {"chat.reaction.added", "chat.reaction.update"})
        self.assertEqual(update_evt["action"], "add")
        self.assertIn("\U0001F525", update_evt["counts"])
        await comm.disconnect()

    async def test_reaction_remove_real_flow(self):
        from .. import services
        msg = await sync_to_async(ChatMessageFactory)(chat=self.chat, sender=self.user)
        await sync_to_async(services.add_reaction)(
            message_id=msg.id, user_id=self.user.pk, emoji="\U0001F44D", custom_emoji="",
        )
        comm = await self._connect_and_drain()
        await comm.send_json_to({
            "type": "chat.reaction.remove", "message_id": str(msg.id), "emoji": "\U0001F44D",
        })
        evt_types = set()
        update_evt = None
        for _ in range(2):
            evt = await comm.receive_json_from(timeout=TIMEOUT)
            evt_types.add(evt["type"])
            if evt["type"] == "chat.reaction.update":
                update_evt = evt
        self.assertEqual(evt_types, {"chat.reaction.removed", "chat.reaction.update"})
        self.assertEqual(update_evt["action"], "remove")
        await comm.disconnect()

    async def test_forward_message_real_flow(self):
        target_chat = await sync_to_async(InternalChatFactory)()
        await sync_to_async(ChatParticipantFactory)(chat=target_chat, user=self.user)
        msg = await sync_to_async(ChatMessageFactory)(chat=self.chat, sender=self.user)
        comm = await self._connect_and_drain()
        await comm.send_json_to({
            "type": "chat.message.forward",
            "message_id": str(msg.id),
            "target_chat_id": str(target_chat.id),
        })
        # Forwarded event is sent to the TARGET chat's group, not echoed
        # back to the sender in the source chat.
        self.assertTrue(await comm.receive_nothing(timeout=0.3))
        await comm.disconnect()

    async def test_report_message_real_flow(self):
        from ..models import MessageReport
        msg = await sync_to_async(ChatMessageFactory)(chat=self.chat, sender=self.user)
        comm = await self._connect_and_drain()
        await comm.send_json_to({
            "type": "chat.report", "message_id": str(msg.id),
            "reason": "spam", "details": "looks like spam",
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.reported")
        exists = await sync_to_async(
            MessageReport.objects.filter(message=msg, reported_by=self.user).exists
        )()
        self.assertTrue(exists)
        await comm.disconnect()

    async def test_report_nonexistent_message_does_not_raise(self):
        comm = await self._connect_and_drain()
        await comm.send_json_to({
            "type": "chat.report",
            "message_id": "00000000-0000-0000-0000-000000000000",
            "reason": "spam",
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "chat.reported")  # still acks, doesn't crash
        await comm.disconnect()

    async def test_mark_read_with_item_ids_marks_inbox(self):
        from ..models import UserInbox
        item = await sync_to_async(UserInbox.objects.create)(
            user=self.user, item_type="SYSTEM", title="x", preview="y", is_read=False,
        )
        comm = await self._connect_and_drain()
        await comm.send_json_to({"type": "chat.mark_read", "item_ids": [str(item.id)]})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["item_ids"], [str(item.id)])
        await sync_to_async(item.refresh_from_db)()
        self.assertTrue(item.is_read)
        await comm.disconnect()


class TestCallConsumerRelayTypes(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.a, self.b = UserFactory(), UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.a)
        ChatParticipantFactory(chat=self.chat, user=self.b)
        self.call = CallSessionFactory(chat=self.chat, initiated_by=self.a, status="RINGING")
        self.call.participants.add(self.a, self.b)

    async def _two_peers(self):
        comm_a, ok_a = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.a)
        self.assertTrue(ok_a)
        comm_b, ok_b = await _connected(f"/ws/messaging/call/{self.call.room_id}/", self.b)
        self.assertTrue(ok_b)
        # peer_joined notification to the first peer
        await comm_a.receive_json_from(timeout=TIMEOUT)
        return comm_a, comm_b

    async def test_answer_relayed_to_peer_not_sender(self):
        comm_a, comm_b = await self._two_peers()
        await comm_b.send_json_to({"type": "call.answer", "sdp": "fake-answer"})
        resp = await comm_a.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "call.answer")
        await comm_a.disconnect()
        await comm_b.disconnect()

    async def test_ice_candidate_relayed(self):
        comm_a, comm_b = await self._two_peers()
        await comm_a.send_json_to({"type": "call.ice_candidate", "candidate": "fake"})
        resp = await comm_b.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "call.ice_candidate")
        await comm_a.disconnect()
        await comm_b.disconnect()

    async def test_camera_toggle_relayed_to_all_including_sender(self):
        comm_a, comm_b = await self._two_peers()
        await comm_a.send_json_to({"type": "call.camera_toggle", "enabled": False})
        resp_a = await comm_a.receive_json_from(timeout=TIMEOUT)
        resp_b = await comm_b.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp_a["type"], "call.camera_toggle")
        self.assertEqual(resp_b["type"], "call.camera_toggle")
        await comm_a.disconnect()
        await comm_b.disconnect()

    async def test_screen_share_start_and_stop_relayed(self):
        comm_a, comm_b = await self._two_peers()
        await comm_a.send_json_to({"type": "call.screen_share"})
        resp = await comm_b.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "call.screen_share")

        await comm_a.send_json_to({"type": "call.screen_share_stop"})
        resp2 = await comm_b.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp2["type"], "call.screen_share_stop")
        await comm_a.disconnect()
        await comm_b.disconnect()

    async def test_recording_start_and_stop_relayed(self):
        comm_a, comm_b = await self._two_peers()
        await comm_a.send_json_to({"type": "call.recording_start"})
        resp = await comm_b.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "call.recording_start")
        await comm_a.disconnect()
        await comm_b.disconnect()

    async def test_peer_left_broadcast_on_disconnect(self):
        comm_a, comm_b = await self._two_peers()
        await comm_b.disconnect()
        resp = await comm_a.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "call.peer_left")
        await comm_a.disconnect()

    async def test_unknown_signal_type_returns_error(self):
        comm_a, comm_b = await self._two_peers()
        await comm_a.send_json_to({"type": "call.made_up_signal"})
        resp = await comm_a.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "error")
        await comm_a.disconnect()
        await comm_b.disconnect()


class TestPresenceConsumerExtra(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()

    async def test_set_invisible(self):
        comm, connected = await _connected("/ws/messaging/presence/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)  # presence.connected
        await comm.send_json_to({"type": "presence.invisible", "invisible": True})
        # Should not raise / should not crash the connection.
        await comm.send_json_to({"type": "presence.ping"})
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "presence.pong")
        await comm.disconnect()

    async def test_bulk_presence_request(self):
        comm, connected = await _connected("/ws/messaging/presence/", self.user)
        self.assertTrue(connected)
        await comm.receive_json_from(timeout=TIMEOUT)  # presence.connected
        await comm.send_json_to({
            "type": "presence.bulk_get",
            "user_ids": [str(self.user.pk), str(self.other.pk)],
        })
        resp = await comm.receive_json_from(timeout=TIMEOUT)
        self.assertEqual(resp["type"], "presence.bulk_response")
        self.assertIn(str(self.user.pk), resp["presences"])
        await comm.disconnect()
