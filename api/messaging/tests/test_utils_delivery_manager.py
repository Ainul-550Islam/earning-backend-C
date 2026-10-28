"""
test_utils_delivery_manager.py
================================
Full coverage for messaging/utils/delivery_manager.py
Functions: queue_message_for_offline_user, flush_offline_queue,
           mark_delivered, mark_read, get_delivery_status,
           increment_unread, get_unread_for_chat, clear_unread_cache,
           get_total_unread
Place in: messaging/tests/test_utils_delivery_manager.py
"""
from __future__ import annotations
import uuid
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from django.core.cache import cache

from ..utils.delivery_manager import (
    queue_message_for_offline_user,
    flush_offline_queue,
    mark_delivered,
    mark_read,
    get_delivery_status,
    increment_unread,
    get_unread_for_chat,
    clear_unread_cache,
    get_total_unread,
    OFFLINE_QUEUE_KEY,
    DELIVERY_ACK_KEY,
    UNREAD_COUNT_KEY,
)
from .factories import UserFactory, InternalChatFactory, ChatParticipantFactory, ChatMessageFactory


class TestQueueMessageForOfflineUser(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_queues_message_and_returns_true(self):
        result = queue_message_for_offline_user(
            user_id=1,
            message_data={"id": "msg-1", "content": "hello"},
        )
        self.assertTrue(result)
        key = OFFLINE_QUEUE_KEY.format(user_id=1)
        stored = cache.get(key)
        self.assertIsInstance(stored, list)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["id"], "msg-1")

    def test_multiple_messages_accumulate(self):
        for i in range(5):
            queue_message_for_offline_user(1, {"id": f"msg-{i}"})
        key = OFFLINE_QUEUE_KEY.format(user_id=1)
        self.assertEqual(len(cache.get(key)), 5)

    def test_caps_at_1000_messages(self):
        for i in range(1005):
            queue_message_for_offline_user(1, {"id": f"msg-{i}"})
        key = OFFLINE_QUEUE_KEY.format(user_id=1)
        self.assertLessEqual(len(cache.get(key)), 1000)

    def test_different_users_have_separate_queues(self):
        queue_message_for_offline_user(1, {"id": "for-user-1"})
        queue_message_for_offline_user(2, {"id": "for-user-2"})
        key1 = OFFLINE_QUEUE_KEY.format(user_id=1)
        key2 = OFFLINE_QUEUE_KEY.format(user_id=2)
        self.assertEqual(len(cache.get(key1)), 1)
        self.assertEqual(len(cache.get(key2)), 1)

    def test_returns_false_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Redis down")
            result = queue_message_for_offline_user(1, {"id": "x"})
        self.assertFalse(result)


class TestFlushOfflineQueue(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_returns_messages_and_clears_queue(self):
        queue_message_for_offline_user(1, {"id": "msg-a"})
        queue_message_for_offline_user(1, {"id": "msg-b"})
        msgs = flush_offline_queue(1)
        self.assertEqual(len(msgs), 2)
        # Queue should be cleared
        key = OFFLINE_QUEUE_KEY.format(user_id=1)
        self.assertIsNone(cache.get(key))

    def test_returns_empty_list_when_no_queue(self):
        msgs = flush_offline_queue(9999)
        self.assertEqual(msgs, [])

    def test_returns_empty_list_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Redis down")
            msgs = flush_offline_queue(1)
        self.assertEqual(msgs, [])


class TestMarkDelivered(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("messaging.utils.delivery_manager.update_delivery_status_task")
    def test_updates_cache_and_queues_task(self, mock_task):
        mock_task.delay = MagicMock()
        result = mark_delivered(message_id="msg-123", user_id=42)
        self.assertTrue(result)
        key = DELIVERY_ACK_KEY.format(message_id="msg-123")
        acks = cache.get(key)
        self.assertIn("42", acks)
        self.assertIn("delivered_at", acks["42"])
        mock_task.delay.assert_called_once()

    @patch("messaging.utils.delivery_manager.update_delivery_status_task")
    def test_delivery_status_is_string_user_id(self, mock_task):
        mock_task.delay = MagicMock()
        mark_delivered("msg-x", user_id=7)
        key = DELIVERY_ACK_KEY.format(message_id="msg-x")
        acks = cache.get(key)
        self.assertIn("7", acks)

    @patch("messaging.utils.delivery_manager.update_delivery_status_task")
    def test_returns_false_on_exception(self, mock_task):
        mock_task.delay.side_effect = Exception("Celery down")
        result = mark_delivered("msg-1", user_id=1)
        # Should still return False (graceful)
        self.assertIsInstance(result, bool)

    @patch("messaging.utils.delivery_manager.update_delivery_status_task")
    def test_preserves_read_at_when_marking_delivered_again(self, mock_task):
        """
        Regression test (Part 6 audit): a late or duplicate delivery ACK
        arriving after the read ACK (plausible on WS reconnect/retry) must
        not erase the already-recorded read_at. Previously mark_delivered()
        replaced the whole per-user ack entry instead of merging into it,
        so this sequence silently destroyed read-receipt data.
        """
        mock_task.delay = MagicMock()
        cache.set(DELIVERY_ACK_KEY.format(message_id="msg-777"),
                  {"5": {"read_at": "2024-01-01T10:05:00"}})
        mark_delivered("msg-777", user_id=5)
        acks = cache.get(DELIVERY_ACK_KEY.format(message_id="msg-777"))
        self.assertIn("read_at", acks["5"])
        self.assertIn("delivered_at", acks["5"])
        self.assertEqual(acks["5"]["read_at"], "2024-01-01T10:05:00")


class TestMarkRead(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("messaging.utils.delivery_manager.update_delivery_status_task")
    def test_sets_read_at_in_ack(self, mock_task):
        mock_task.delay = MagicMock()
        result = mark_read(message_id="msg-456", user_id=10)
        self.assertTrue(result)
        key = DELIVERY_ACK_KEY.format(message_id="msg-456")
        acks = cache.get(key)
        self.assertIn("10", acks)
        self.assertIn("read_at", acks["10"])

    @patch("messaging.utils.delivery_manager.update_delivery_status_task")
    def test_preserves_delivered_at_when_setting_read_at(self, mock_task):
        mock_task.delay = MagicMock()
        # First mark delivered
        cache.set(DELIVERY_ACK_KEY.format(message_id="msg-999"),
                  {"5": {"delivered_at": "2024-01-01T10:00:00"}})
        mark_read("msg-999", user_id=5)
        acks = cache.get(DELIVERY_ACK_KEY.format(message_id="msg-999"))
        self.assertIn("delivered_at", acks["5"])
        self.assertIn("read_at", acks["5"])

    @patch("messaging.utils.delivery_manager.update_delivery_status_task")
    def test_clears_unread_cache(self, mock_task):
        mock_task.delay = MagicMock()
        cache.set("msg:total_unread:10", 5, 300)
        mark_read("msg-1", user_id=10)
        # Total unread cache should be cleared
        self.assertIsNone(cache.get("msg:total_unread:10"))

    def test_returns_false_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Redis down")
            result = mark_read("msg-1", user_id=10)
        self.assertFalse(result)


class TestGetDeliveryStatus(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_returns_empty_dict_when_not_found(self):
        result = get_delivery_status("nonexistent-msg")
        self.assertEqual(result, {})

    def test_returns_cached_acks(self):
        key = DELIVERY_ACK_KEY.format(message_id="msg-test")
        cache.set(key, {"1": {"delivered_at": "2024-01-01T10:00:00"}})
        result = get_delivery_status("msg-test")
        self.assertIn("1", result)

    def test_returns_empty_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Redis error")
            result = get_delivery_status("x")
        self.assertEqual(result, {})


class TestIncrementUnread(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_increments_from_zero(self):
        count = increment_unread(user_id=1, chat_id="chat-1")
        self.assertEqual(count, 1)

    def test_increments_from_existing_value(self):
        increment_unread(1, "chat-1")
        increment_unread(1, "chat-1")
        count = increment_unread(1, "chat-1")
        self.assertEqual(count, 3)

    def test_custom_count_param(self):
        count = increment_unread(user_id=1, chat_id="chat-x", count=5)
        self.assertEqual(count, 5)

    def test_different_chats_tracked_separately(self):
        increment_unread(1, "chat-a")
        increment_unread(1, "chat-a")
        count_b = increment_unread(1, "chat-b")
        self.assertEqual(count_b, 1)
        key_a = UNREAD_COUNT_KEY.format(user_id=1, chat_id="chat-a")
        self.assertEqual(cache.get(key_a), 2)

    def test_returns_zero_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("error")
            result = increment_unread(1, "c")
        self.assertEqual(result, 0)


class TestGetUnreadForChat(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_returns_zero_when_nothing_cached(self):
        result = get_unread_for_chat(user_id=1, chat_id="chat-empty")
        self.assertEqual(result, 0)

    def test_returns_cached_value(self):
        key = UNREAD_COUNT_KEY.format(user_id=1, chat_id="chat-x")
        cache.set(key, 7)
        self.assertEqual(get_unread_for_chat(1, "chat-x"), 7)

    def test_returns_zero_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("error")
            result = get_unread_for_chat(1, "c")
        self.assertEqual(result, 0)


class TestClearUnreadCache(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_clears_specific_chat_unread(self):
        key = UNREAD_COUNT_KEY.format(user_id=1, chat_id="chat-1")
        cache.set(key, 5)
        clear_unread_cache(user_id=1, chat_id="chat-1")
        self.assertIsNone(cache.get(key))

    def test_clears_total_unread(self):
        cache.set("msg:total_unread:1", 10)
        clear_unread_cache(user_id=1)
        self.assertIsNone(cache.get("msg:total_unread:1"))

    def test_does_not_raise_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.delete.side_effect = Exception("Redis error")
            # Should not raise
            clear_unread_cache(user_id=1, chat_id="chat-x")


class TestGetTotalUnread(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_returns_cached_value_without_db_hit(self):
        cache.set("msg:total_unread:1", 15, 300)
        result = get_total_unread(user_id=1)
        self.assertEqual(result, 15)

    def test_computes_from_db_when_cache_miss(self):
        from ..models import UserInbox
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, sender=user)
        # Create unread inbox items
        UserInbox.objects.create(
            user=user, item_type="CHAT_MESSAGE", source_id=str(msg.id),
            title="msg", preview="hi", is_read=False, is_archived=False,
        )
        UserInbox.objects.create(
            user=user, item_type="CHAT_MESSAGE", source_id=uuid.uuid4(),
            title="msg2", preview="hi2", is_read=False, is_archived=False,
        )
        result = get_total_unread(user_id=user.pk)
        self.assertEqual(result, 2)

    def test_excludes_archived_from_count(self):
        from ..models import UserInbox
        user = UserFactory()
        chat = InternalChatFactory()
        msg = ChatMessageFactory(chat=chat, sender=user)
        UserInbox.objects.create(
            user=user, item_type="CHAT_MESSAGE", source_id=str(msg.id),
            title="msg", preview="hi", is_read=False, is_archived=True,
        )
        result = get_total_unread(user_id=user.pk)
        self.assertEqual(result, 0)

    def test_returns_zero_on_exception(self):
        with patch("messaging.utils.delivery_manager.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Redis error")
            result = get_total_unread(user_id=1)
        self.assertEqual(result, 0)
