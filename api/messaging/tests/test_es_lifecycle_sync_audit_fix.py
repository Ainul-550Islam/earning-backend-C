"""
test_es_lifecycle_sync_audit_fix.py
=====================================
Audit finding (Part 19): expire_disappearing_messages() was flagged as
sharing the same root cause as the (already fixed) cleanup_chats.py ES
orphan bug - a bulk QuerySet .update() never runs ChatMessage.save() or
fires a signal, so nothing told Elasticsearch content had changed.

Investigating that one function surfaced the same bug in three more
places, all upstream of it in the message lifecycle:

  - send_chat_message()       -> index_message_task was NEVER queued.
    A message sent after the last manual sync_search_index / bulk_reindex
    run was invisible to search, permanently, until the next manual run.
  - ChatMessage.soft_delete()  -> delete_from_index_task was NEVER queued
    (called from delete_chat_message()). A "deleted" message's original
    content stayed searchable forever.
  - ChatMessage.mark_edited()  -> index_message_task was NEVER queued
    (called from edit_message_with_history()). Edited messages kept
    showing pre-edit content in search forever.
  - expire_disappearing_messages() -> the originally flagged instance.

All four are fixed together since they're the same bug: services.py's
new _queue_message_index / _queue_message_deindex helpers (mirroring
the existing _process_bot_triggers_async fire-and-forget shape) are now
called from send/delete/edit, and expire_disappearing_messages() gained
its own synchronous deindex + MessageSearchIndex cleanup, matching how
cleanup_chats.py already handles its sibling case.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .factories import ChatMessageFactory, ChatParticipantFactory, InternalChatFactory, UserFactory
from .. import services
from ..choices import MessageStatus
from ..models import ChatMessage, DisappearingMessageConfig, MessageSearchIndex

pytestmark = []


# ─────────────────────────────────────────────────────────────────────────────
# send_chat_message() -> index_message_task queued
# ─────────────────────────────────────────────────────────────────────────────

class TestSendMessageQueuesIndexing(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @patch("messaging.tasks.index_message_task.delay")
    def test_send_message_queues_index_task(self, mock_delay):
        message = services.send_chat_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk, content="hello world",
        )
        mock_delay.assert_called_once_with(str(message.id))

    @patch("messaging.tasks.index_message_task.delay", side_effect=Exception("broker down"))
    def test_send_message_succeeds_even_if_queueing_fails(self, mock_delay):
        """Fire-and-forget: a broker hiccup must never fail the send itself."""
        message = services.send_chat_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk, content="still sends",
        )
        self.assertIsNotNone(message.id)

    @patch("messaging.utils.search_engine.index_message", return_value=True)
    def test_send_message_actually_reaches_search_engine_index(self, mock_index):
        """End-to-end through the eagerly-executed Celery task (CELERY_TASK_ALWAYS_EAGER)."""
        message = services.send_chat_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk, content="findable now",
        )
        mock_index.assert_called_once()
        self.assertEqual(mock_index.call_args.kwargs["message_id"], str(message.id))
        self.assertEqual(mock_index.call_args.kwargs["content"], "findable now")


# ─────────────────────────────────────────────────────────────────────────────
# delete_chat_message() -> delete_from_index_task queued
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteMessageQueuesDeindexing(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="secret content")

    @patch("messaging.tasks.delete_from_index_task.delay")
    def test_delete_message_queues_deindex_task(self, mock_delay):
        services.delete_chat_message(message_id=str(self.msg.id), requesting_user_id=self.user.pk)
        mock_delay.assert_called_once_with(str(self.msg.id))

    @patch("messaging.utils.search_engine.delete_from_index", return_value=True)
    def test_delete_message_actually_reaches_search_engine_deindex(self, mock_deindex):
        services.delete_chat_message(message_id=str(self.msg.id), requesting_user_id=self.user.pk)
        mock_deindex.assert_called_once_with(str(self.msg.id))


# ─────────────────────────────────────────────────────────────────────────────
# edit_message_with_history() -> index_message_task queued (reindex)
# ─────────────────────────────────────────────────────────────────────────────

class TestEditMessageQueuesReindexing(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="original text")

    @patch("messaging.tasks.index_message_task.delay")
    def test_edit_message_queues_reindex_task(self, mock_delay):
        services.edit_message_with_history(
            message_id=str(self.msg.id), user_id=self.user.pk, new_content="edited text",
        )
        mock_delay.assert_called_once_with(str(self.msg.id))

    @patch("messaging.utils.search_engine.index_message", return_value=True)
    def test_edit_message_reindexes_with_new_content(self, mock_index):
        services.edit_message_with_history(
            message_id=str(self.msg.id), user_id=self.user.pk, new_content="edited text",
        )
        mock_index.assert_called_once()
        self.assertEqual(mock_index.call_args.kwargs["content"], "edited text")


# ─────────────────────────────────────────────────────────────────────────────
# expire_disappearing_messages() -> the originally flagged bug
# ─────────────────────────────────────────────────────────────────────────────

class TestExpireDisappearingMessagesDeindexing(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user, role="ADMIN")
        self.config = services.set_disappearing_messages(
            chat_id=str(self.chat.id), enabled_by_id=self.user.pk, ttl_seconds=1,
        )
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="disappearing secret")
        ChatMessage.objects.filter(pk=self.msg.pk).update(
            created_at=timezone.now() - timedelta(seconds=10)
        )

    @patch("messaging.utils.search_engine.delete_from_index", return_value=True)
    def test_expire_deindexes_each_expired_message(self, mock_deindex):
        expired = services.expire_disappearing_messages()
        self.assertEqual(expired, 1)
        mock_deindex.assert_called_once_with(str(self.msg.id))

    @patch("messaging.utils.search_engine.delete_from_index", return_value=True)
    def test_expire_clears_db_fallback_search_index(self, mock_deindex):
        MessageSearchIndex.objects.create(
            message=self.msg, chat=self.chat, search_text="disappearing secret",
        )
        services.expire_disappearing_messages()
        self.assertFalse(MessageSearchIndex.objects.filter(message_id=self.msg.id).exists())

    @patch("messaging.utils.search_engine.delete_from_index", side_effect=Exception("ES timeout"))
    def test_expire_still_deletes_message_even_if_deindex_fails(self, mock_deindex):
        """The DB-level disappear must not be rolled back by an ES hiccup -
        matches cleanup_chats.py's best-effort-per-message contract."""
        expired = services.expire_disappearing_messages()
        self.assertEqual(expired, 1)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, MessageStatus.DELETED)
        self.assertEqual(self.msg.content, "[This message has disappeared]")

    @patch("messaging.utils.search_engine.delete_from_index", return_value=True)
    def test_expire_ignores_non_expired_messages(self, mock_deindex):
        fresh = ChatMessageFactory(chat=self.chat, sender=self.user, content="still fresh")
        services.expire_disappearing_messages()
        mock_deindex.assert_called_once_with(str(self.msg.id))  # not fresh.id
        fresh.refresh_from_db()
        self.assertNotEqual(fresh.status, MessageStatus.DELETED)
