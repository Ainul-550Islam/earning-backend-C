"""
test_utils_device_sync.py
==========================
Full coverage for messaging/utils/device_sync.py
Functions: sync_device_on_login, get_messages_for_sync,
           broadcast_to_all_user_devices, get_aggregated_presence
Place in: messaging/tests/test_utils_device_sync.py
"""
from __future__ import annotations
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from .factories import (
    UserFactory,
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
    DeviceTokenFactory,
)
from ..models import (
    DeviceToken,
    UserPresence,
    UserInbox,
)
from ..utils.device_sync import (
    sync_device_on_login,
    get_messages_for_sync,
    broadcast_to_all_user_devices,
    get_aggregated_presence,
)


class TestSyncDeviceOnLogin(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.token = DeviceTokenFactory(user=self.user)

    def test_returns_dict_with_required_keys(self):
        result = sync_device_on_login(
            user_id=self.user.pk,
            device_token_id=self.token.pk,
        )
        self.assertIn("chats", result)
        self.assertIn("total_unread", result)
        self.assertIn("sync_timestamp", result)

    def test_chats_list_is_list(self):
        result = sync_device_on_login(self.user.pk, self.token.pk)
        self.assertIsInstance(result["chats"], list)

    def test_includes_users_active_chats(self):
        result = sync_device_on_login(self.user.pk, self.token.pk)
        chat_ids = [c["chat_id"] for c in result["chats"]]
        self.assertIn(str(self.chat.id), chat_ids)

    def test_excludes_chats_user_left(self):
        left_chat = InternalChatFactory()
        cp = ChatParticipantFactory(chat=left_chat, user=self.user)
        cp.joined_at = timezone.now() - timedelta(days=2)
        cp.left_at = timezone.now() - timedelta(days=1)
        cp.save()
        result = sync_device_on_login(self.user.pk, self.token.pk)
        chat_ids = [c["chat_id"] for c in result["chats"]]
        self.assertNotIn(str(left_chat.id), chat_ids)

    def test_updates_device_last_used_at(self):
        old_time = timezone.now() - timedelta(hours=5)
        DeviceToken.objects.filter(pk=self.token.pk).update(last_used_at=old_time)
        sync_device_on_login(self.user.pk, self.token.pk)
        self.token.refresh_from_db()
        self.assertGreater(self.token.last_used_at, old_time)

    def test_total_unread_reflects_inbox_items(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        UserInbox.objects.create(
            user=self.user, item_type="CHAT_MESSAGE",
            source_id=str(msg.id), title="New", preview="Hi",
            is_read=False, is_archived=False,
        )
        result = sync_device_on_login(self.user.pk, self.token.pk)
        self.assertGreaterEqual(result["total_unread"], 1)

    def test_no_chats_returns_empty_list(self):
        lonely_user = UserFactory()
        token = DeviceTokenFactory(user=lonely_user)
        result = sync_device_on_login(lonely_user.pk, token.pk)
        self.assertEqual(result["chats"], [])
        self.assertEqual(result["total_unread"], 0)

    def test_per_chat_unread_count_is_attributed_to_correct_chat(self):
        """
        Regression test (Part 6 audit): unread_by_chat was previously built
        by grouping UserInbox rows by source_id (a message id) and then
        looked up by chat.id - two different id spaces that never matched,
        so every chat's "unread_count" in the sync payload was always 0
        even though total_unread (a separate, coincidentally-correct sum)
        was right. This chat should show exactly 2 unread, and an unrelated
        second chat with its own unread item should not contribute to it.
        """
        other_chat = InternalChatFactory()
        ChatParticipantFactory(chat=other_chat, user=self.user)

        msg1 = ChatMessageFactory(chat=self.chat, sender=self.user)
        msg2 = ChatMessageFactory(chat=self.chat, sender=self.user)
        other_msg = ChatMessageFactory(chat=other_chat, sender=self.user)
        for msg in (msg1, msg2):
            UserInbox.objects.create(
                user=self.user, item_type="CHAT_MESSAGE", source_id=str(msg.id),
                title="msg", preview="hi", is_read=False, is_archived=False,
            )
        UserInbox.objects.create(
            user=self.user, item_type="CHAT_MESSAGE", source_id=str(other_msg.id),
            title="msg", preview="hi", is_read=False, is_archived=False,
        )

        result = sync_device_on_login(self.user.pk, self.token.pk)
        by_id = {c["chat_id"]: c["unread_count"] for c in result["chats"]}
        self.assertEqual(by_id[str(self.chat.id)], 2)
        self.assertEqual(by_id[str(other_chat.id)], 1)
        self.assertEqual(result["total_unread"], 3)

    def test_non_message_inbox_items_excluded_from_per_chat_count(self):
        """
        A BROADCAST/SYSTEM/etc inbox item's source_id points at a different
        kind of object entirely, not a ChatMessage - it must not be able to
        collide with a chat's per-chat unread_count, even though it still
        counts toward the item-type-agnostic total_unread.
        """
        UserInbox.objects.create(
            user=self.user, item_type="SYSTEM", source_id=None,
            title="System notice", preview="hi", is_read=False, is_archived=False,
        )
        result = sync_device_on_login(self.user.pk, self.token.pk)
        by_id = {c["chat_id"]: c["unread_count"] for c in result["chats"]}
        self.assertEqual(by_id.get(str(self.chat.id), 0), 0)
        self.assertEqual(result["total_unread"], 1)


class TestGetMessagesForSync(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        self.outsider = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        for i in range(5):
            ChatMessageFactory(chat=self.chat, sender=self.user, content=f"msg {i}")

    def test_returns_messages_for_participant(self):
        msgs = get_messages_for_sync(
            user_id=self.user.pk,
            chat_id=str(self.chat.id),
        )
        self.assertGreaterEqual(len(msgs), 1)

    def test_returns_empty_for_non_participant(self):
        msgs = get_messages_for_sync(
            user_id=self.outsider.pk,
            chat_id=str(self.chat.id),
        )
        self.assertEqual(msgs, [])

    def test_since_filter_returns_only_newer_messages(self):
        cutoff = timezone.now() - timedelta(days=1)
        msgs = get_messages_for_sync(
            user_id=self.user.pk,
            chat_id=str(self.chat.id),
            since=cutoff.isoformat(),
        )
        for m in msgs:
            self.assertGreater(m.created_at, cutoff)

    def test_since_far_future_returns_empty(self):
        future = (timezone.now() + timedelta(days=365)).isoformat()
        msgs = get_messages_for_sync(
            user_id=self.user.pk,
            chat_id=str(self.chat.id),
            since=future,
        )
        self.assertEqual(msgs, [])

    def test_caps_at_max_sync_messages_per_chat(self):
        from ..utils.device_sync import MAX_SYNC_MESSAGES_PER_CHAT
        for i in range(MAX_SYNC_MESSAGES_PER_CHAT + 10):
            ChatMessageFactory(chat=self.chat, sender=self.user)
        msgs = get_messages_for_sync(self.user.pk, str(self.chat.id))
        self.assertLessEqual(len(msgs), MAX_SYNC_MESSAGES_PER_CHAT)

    def test_invalid_since_string_falls_back_to_default(self):
        msgs = get_messages_for_sync(
            user_id=self.user.pk,
            chat_id=str(self.chat.id),
            since="not-a-date",
        )
        # Should still return messages (fallback to 90-day window)
        self.assertIsInstance(msgs, list)

    def test_invalid_since_string_still_excludes_messages_older_than_default_window(self):
        """
        Regression test (Part 6 audit): a `since` value that fails to parse
        previously left the query with NO time filter at all (not even the
        90-day default), because the fallback `else` only ran when `since`
        was falsy, never when it was present-but-garbage. A message from
        200 days ago must still be excluded when since="not-a-date".
        """
        from ..models import ChatMessage
        old_msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        ChatMessage.objects.filter(pk=old_msg.pk).update(
            created_at=timezone.now() - timedelta(days=200)
        )
        msgs = get_messages_for_sync(
            user_id=self.user.pk,
            chat_id=str(self.chat.id),
            since="not-a-date",
        )
        self.assertNotIn(old_msg.pk, [m.pk for m in msgs])


class TestBroadcastToAllUserDevices(TestCase):
    def setUp(self):
        self.user = UserFactory()

    @patch("messaging.utils.device_sync.send_websocket_event")
    def test_sends_to_the_real_per_user_consumer_group(self, mock_ws):
        """
        Regression test (Part 6 audit): this function used to build its own
        group name (user_devices_{user_id}_{token_pk}) instead of using
        consumers._user_devices_group(), which is the only group any
        ChatConsumer actually joins. That meant every broadcast silently
        reached zero sockets while still reporting success. Assert the
        exact group name a real consumer subscribes to is the one used.
        """
        from api.messaging.consumers import _user_devices_group
        mock_ws.return_value = True
        DeviceTokenFactory(user=self.user, is_active=True)

        broadcast_to_all_user_devices(
            user_id=self.user.pk, event_type="message.read", data={"message_id": "x"},
        )

        mock_ws.assert_called_once()
        self.assertEqual(
            mock_ws.call_args[1]["group_name"], _user_devices_group(self.user.pk)
        )

    @patch("messaging.utils.device_sync.send_websocket_event")
    def test_sends_exactly_once_regardless_of_device_count(self, mock_ws):
        """
        All of a user's sockets share one group, so Channels' group_send
        already fans out to every device - calling send_websocket_event
        once per DeviceToken (the old behavior) would duplicate delivery
        to every connected socket once the group name was corrected.
        """
        mock_ws.return_value = True
        DeviceTokenFactory(user=self.user, is_active=True)
        DeviceTokenFactory(user=self.user, is_active=True)
        DeviceTokenFactory(user=self.user, is_active=True)

        count = broadcast_to_all_user_devices(self.user.pk, "message.read", {})

        mock_ws.assert_called_once()
        self.assertEqual(count, 3)  # still reports the active-device upper bound

    @patch("messaging.utils.device_sync.send_websocket_event")
    def test_skips_inactive_devices_in_count(self, mock_ws):
        mock_ws.return_value = True
        DeviceTokenFactory(user=self.user, is_active=True)
        DeviceTokenFactory(user=self.user, is_active=False)
        count = broadcast_to_all_user_devices(
            self.user.pk, "message.read", {}
        )
        self.assertEqual(count, 1)

    @patch("messaging.utils.device_sync.send_websocket_event")
    def test_returns_zero_when_no_devices(self, mock_ws):
        count = broadcast_to_all_user_devices(self.user.pk, "event", {})
        self.assertEqual(count, 0)
        mock_ws.assert_not_called()

    @patch("messaging.utils.device_sync.send_websocket_event")
    def test_returns_zero_when_send_fails(self, mock_ws):
        mock_ws.return_value = False
        DeviceTokenFactory(user=self.user, is_active=True)
        DeviceTokenFactory(user=self.user, is_active=True)
        count = broadcast_to_all_user_devices(self.user.pk, "evt", {})
        self.assertEqual(count, 0)

    @patch("messaging.utils.device_sync.send_websocket_event")
    def test_passes_through_event_type_and_data(self, mock_ws):
        mock_ws.return_value = True
        DeviceTokenFactory(user=self.user, is_active=True)
        broadcast_to_all_user_devices(self.user.pk, "presence.update", {"status": "ONLINE"})
        self.assertEqual(mock_ws.call_args[1]["event_type"], "presence.update")
        self.assertEqual(mock_ws.call_args[1]["data"], {"status": "ONLINE"})


class TestGetAggregatedPresence(TestCase):
    def setUp(self):
        from ..constants import PRESENCE_OFFLINE_AFTER_SECONDS
        self.user = UserFactory()
        self.PRESENCE_OFFLINE_AFTER_SECONDS = PRESENCE_OFFLINE_AFTER_SECONDS

    def test_returns_online_if_device_recently_active(self):
        DeviceTokenFactory(
            user=self.user,
            is_active=True,
            last_used_at=timezone.now() - timedelta(seconds=10),
        )
        result = get_aggregated_presence(self.user.pk)
        self.assertEqual(result["status"], "ONLINE")
        self.assertGreaterEqual(result["device_count"], 1)

    def test_returns_offline_if_no_recently_active_device(self):
        DeviceTokenFactory(
            user=self.user,
            is_active=True,
            last_used_at=timezone.now() - timedelta(seconds=self.PRESENCE_OFFLINE_AFTER_SECONDS + 100),
        )
        result = get_aggregated_presence(self.user.pk)
        self.assertIn(result["status"], ["OFFLINE", "AWAY"])

    def test_aggregates_multiple_devices(self):
        DeviceTokenFactory(
            user=self.user, is_active=True,
            last_used_at=timezone.now() - timedelta(seconds=5),
        )
        DeviceTokenFactory(
            user=self.user, is_active=True,
            last_used_at=timezone.now() - timedelta(seconds=5),
        )
        result = get_aggregated_presence(self.user.pk)
        self.assertEqual(result["status"], "ONLINE")
        self.assertGreaterEqual(result["device_count"], 2)

    def test_returns_offline_with_no_devices_and_no_presence(self):
        result = get_aggregated_presence(self.user.pk)
        self.assertIn(result["status"], ["OFFLINE", "UNKNOWN"])

    def test_uses_presence_record_when_no_active_devices(self):
        presence = UserPresence.objects.create(
            user=self.user,
            status="AWAY",
            last_seen_at=timezone.now() - timedelta(minutes=30),
        )
        result = get_aggregated_presence(self.user.pk)
        self.assertIn("last_seen_at", result)
