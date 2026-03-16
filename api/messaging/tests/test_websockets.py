"""
Messaging Tests — WebSocket consumers and service layer tests.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from ..choices import (
    ChatStatus, MessageStatus, MessageType,
    BroadcastStatus, SupportThreadStatus,
    InboxItemType,
)
from ..exceptions import (
    ChatNotFoundError, ChatAccessDeniedError, ChatArchivedError,
    BroadcastStateError, SupportThreadClosedError, SupportThreadLimitError,
    RateLimitError, UserNotFoundError,
)
from ..models import InternalChat, ChatMessage, AdminBroadcast, SupportThread, UserInbox
from .. import services
from .factories import (
    UserFactory, StaffUserFactory, InternalChatFactory, GroupChatFactory,
    ChatParticipantFactory, ChatMessageFactory,
    AdminBroadcastFactory, SupportThreadFactory, SupportMessageFactory,
    UserInboxFactory,
)


# ---------------------------------------------------------------------------
# InternalChat Model Tests
# ---------------------------------------------------------------------------

class InternalChatModelTest(TestCase):

    def test_direct_chat_created(self):
        user = UserFactory()
        chat = InternalChatFactory(created_by=user)
        self.assertIsNotNone(chat.id)
        self.assertFalse(chat.is_group)

    def test_group_chat_without_name_raises(self):
        with self.assertRaises(ValidationError):
            InternalChatFactory(is_group=True, name="")

    def test_archive_active_chat(self):
        chat = InternalChatFactory(status=ChatStatus.ACTIVE)
        chat.archive()
        chat.refresh_from_db()
        self.assertEqual(chat.status, ChatStatus.ARCHIVED)

    def test_archive_idempotent(self):
        chat = InternalChatFactory(status=ChatStatus.ARCHIVED)
        chat.archive()  # should not raise
        self.assertEqual(chat.status, ChatStatus.ARCHIVED)

    def test_cannot_archive_deleted_chat(self):
        chat = InternalChatFactory(status=ChatStatus.DELETED)
        with self.assertRaises(ChatArchivedError):
            chat.archive()

    def test_soft_delete(self):
        chat = InternalChatFactory()
        chat.soft_delete()
        chat.refresh_from_db()
        self.assertEqual(chat.status, ChatStatus.DELETED)

    def test_assert_active_raises_on_archived(self):
        chat = InternalChatFactory(status=ChatStatus.ARCHIVED)
        with self.assertRaises(ChatArchivedError):
            chat.assert_active()


# ---------------------------------------------------------------------------
# ChatMessage Model Tests
# ---------------------------------------------------------------------------

class ChatMessageModelTest(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_text_message_without_content_raises(self):
        with self.assertRaises(ValidationError):
            ChatMessageFactory(chat=self.chat, sender=self.user, content="", message_type=MessageType.TEXT)

    def test_system_message_with_sender_raises(self):
        with self.assertRaises(ValidationError):
            ChatMessageFactory(chat=self.chat, sender=self.user, message_type=MessageType.SYSTEM)

    def test_soft_delete_replaces_content(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="Hello!")
        msg.soft_delete(deleted_by_id=self.user.pk)
        msg.refresh_from_db()
        self.assertEqual(msg.status, MessageStatus.DELETED)
        self.assertEqual(msg.content, "[This message was deleted]")
        self.assertEqual(msg.attachments, [])

    def test_soft_delete_idempotent(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="Hello!")
        msg.soft_delete()
        msg.soft_delete()  # second call no-op
        self.assertEqual(msg.status, MessageStatus.DELETED)

    def test_mark_edited(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="Original")
        msg.mark_edited("Updated content")
        msg.refresh_from_db()
        self.assertTrue(msg.is_edited)
        self.assertEqual(msg.content, "Updated content")
        self.assertIsNotNone(msg.edited_at)

    def test_mark_edited_deleted_message_raises(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="Hello")
        msg.soft_delete()
        with self.assertRaises(ValidationError):
            msg.mark_edited("New content")

    def test_mark_edited_empty_content_raises(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="Hello")
        with self.assertRaises(ValidationError):
            msg.mark_edited("   ")


# ---------------------------------------------------------------------------
# Service: create_direct_chat
# ---------------------------------------------------------------------------

class CreateDirectChatServiceTest(TestCase):

    def test_creates_chat_between_two_users(self):
        u1 = UserFactory()
        u2 = UserFactory()
        chat = services.create_direct_chat(u1.pk, u2.pk)
        self.assertFalse(chat.is_group)
        self.assertEqual(chat.participants.count(), 2)

    def test_idempotent_returns_existing(self):
        u1 = UserFactory()
        u2 = UserFactory()
        chat1 = services.create_direct_chat(u1.pk, u2.pk)
        chat2 = services.create_direct_chat(u1.pk, u2.pk)
        self.assertEqual(chat1.id, chat2.id)

    def test_same_user_raises(self):
        u1 = UserFactory()
        with self.assertRaises(Exception):
            services.create_direct_chat(u1.pk, u1.pk)

    def test_nonexistent_user_raises(self):
        u1 = UserFactory()
        with self.assertRaises(UserNotFoundError):
            services.create_direct_chat(u1.pk, 99999999)


# ---------------------------------------------------------------------------
# Service: send_chat_message
# ---------------------------------------------------------------------------

class SendChatMessageServiceTest(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory(status=ChatStatus.ACTIVE)
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_sends_text_message(self):
        msg = services.send_chat_message(
            chat_id=self.chat.pk,
            sender_id=self.user.pk,
            content="Hello world!",
        )
        self.assertEqual(msg.content, "Hello world!")
        self.assertEqual(msg.message_type, MessageType.TEXT)
        self.assertEqual(msg.sender_id, self.user.pk)

    def test_archived_chat_raises(self):
        self.chat.status = ChatStatus.ARCHIVED
        self.chat.save()
        with self.assertRaises(ChatArchivedError):
            services.send_chat_message(
                chat_id=self.chat.pk,
                sender_id=self.user.pk,
                content="Hello",
            )

    def test_non_participant_raises(self):
        stranger = UserFactory()
        with self.assertRaises(ChatAccessDeniedError):
            services.send_chat_message(
                chat_id=self.chat.pk,
                sender_id=stranger.pk,
                content="Hello",
            )

    def test_empty_content_raises(self):
        with self.assertRaises(Exception):
            services.send_chat_message(
                chat_id=self.chat.pk,
                sender_id=self.user.pk,
                content="",
            )

    def test_creates_inbox_items_for_other_participants(self):
        other_user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=other_user)
        services.send_chat_message(
            chat_id=self.chat.pk,
            sender_id=self.user.pk,
            content="Hey!",
        )
        self.assertEqual(
            UserInbox.objects.filter(
                user=other_user, item_type=InboxItemType.CHAT_MESSAGE
            ).count(),
            1,
        )


# ---------------------------------------------------------------------------
# Service: AdminBroadcast
# ---------------------------------------------------------------------------

class BroadcastServiceTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user1 = UserFactory()
        self.user2 = UserFactory()

    def test_create_broadcast_draft(self):
        broadcast = services.create_broadcast(
            creator_id=self.admin.pk,
            title="Test Broadcast",
            body="Hello everyone!",
        )
        self.assertEqual(broadcast.status, BroadcastStatus.DRAFT)
        self.assertEqual(broadcast.title, "Test Broadcast")

    def test_create_broadcast_non_staff_raises(self):
        regular_user = UserFactory()
        with self.assertRaises(Exception):
            services.create_broadcast(
                creator_id=regular_user.pk,
                title="Broadcast",
                body="Body",
            )

    def test_send_broadcast_creates_inbox_items(self):
        broadcast = AdminBroadcastFactory(
            created_by=self.admin,
            status=BroadcastStatus.DRAFT,
        )
        result = services.send_broadcast(broadcast_id=broadcast.pk)
        self.assertGreaterEqual(result["recipient_count"], 0)
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.status, BroadcastStatus.SENT)

    def test_send_broadcast_invalid_status_raises(self):
        broadcast = AdminBroadcastFactory(
            created_by=self.admin,
            status=BroadcastStatus.SENT,
        )
        with self.assertRaises(BroadcastStateError):
            services.send_broadcast(broadcast_id=broadcast.pk)

    def test_broadcast_state_machine(self):
        broadcast = AdminBroadcastFactory(created_by=self.admin)
        broadcast.transition_to(BroadcastStatus.SENDING)
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.status, BroadcastStatus.SENDING)

    def test_broadcast_invalid_transition_raises(self):
        broadcast = AdminBroadcastFactory(
            created_by=self.admin, status=BroadcastStatus.SENT
        )
        with self.assertRaises(BroadcastStateError):
            broadcast.transition_to(BroadcastStatus.DRAFT)


# ---------------------------------------------------------------------------
# Service: SupportThread
# ---------------------------------------------------------------------------

class SupportThreadServiceTest(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.agent = StaffUserFactory()

    def test_create_support_thread(self):
        thread = services.create_support_thread(
            user_id=self.user.pk,
            subject="Login issue",
            initial_message="I can't log in.",
        )
        self.assertEqual(thread.status, SupportThreadStatus.OPEN)
        self.assertEqual(thread.subject, "Login issue")
        self.assertEqual(thread.messages.count(), 1)

    def test_create_thread_empty_subject_raises(self):
        with self.assertRaises(Exception):
            services.create_support_thread(
                user_id=self.user.pk,
                subject="",
                initial_message="Help!",
            )

    def test_reply_to_thread(self):
        thread = SupportThreadFactory(user=self.user)
        msg = services.reply_to_support_thread(
            thread_id=thread.pk,
            sender_id=self.user.pk,
            content="More details here.",
        )
        self.assertEqual(msg.content, "More details here.")
        self.assertFalse(msg.is_agent_reply)

    def test_agent_reply_changes_status_to_in_progress(self):
        thread = SupportThreadFactory(user=self.user, status=SupportThreadStatus.OPEN)
        services.reply_to_support_thread(
            thread_id=thread.pk,
            sender_id=self.agent.pk,
            content="We are looking into this.",
        )
        thread.refresh_from_db()
        self.assertEqual(thread.status, SupportThreadStatus.IN_PROGRESS)

    def test_reply_to_closed_thread_raises(self):
        thread = SupportThreadFactory(user=self.user, status=SupportThreadStatus.CLOSED)
        with self.assertRaises(SupportThreadClosedError):
            services.reply_to_support_thread(
                thread_id=thread.pk,
                sender_id=self.user.pk,
                content="Hello?",
            )

    def test_assign_thread_to_agent(self):
        thread = SupportThreadFactory(user=self.user)
        thread = services.assign_support_thread(
            thread_id=thread.pk, agent_id=self.agent.pk
        )
        self.assertEqual(thread.assigned_agent_id, self.agent.pk)

    def test_assign_non_staff_raises(self):
        thread = SupportThreadFactory(user=self.user)
        regular = UserFactory()
        with self.assertRaises(Exception):
            services.assign_support_thread(
                thread_id=thread.pk, agent_id=regular.pk
            )


# ---------------------------------------------------------------------------
# UserInbox Tests
# ---------------------------------------------------------------------------

class UserInboxServiceTest(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def test_mark_inbox_items_read(self):
        item1 = UserInboxFactory(user=self.user)
        item2 = UserInboxFactory(user=self.user)
        updated = services.mark_inbox_items_read(
            user_id=self.user.pk, item_ids=[item1.pk, item2.pk]
        )
        self.assertEqual(updated, 2)
        item1.refresh_from_db()
        self.assertTrue(item1.is_read)

    def test_get_unread_count(self):
        UserInboxFactory(user=self.user, is_read=False)
        UserInboxFactory(user=self.user, is_read=False)
        count = services.get_unread_count(self.user.pk)
        self.assertEqual(count, 2)

    def test_mark_read_idempotent(self):
        item = UserInboxFactory(user=self.user, is_read=True, read_at=__import__("django.utils.timezone", fromlist=["timezone"]).timezone.now())
        updated = services.mark_inbox_items_read(
            user_id=self.user.pk, item_ids=[item.pk]
        )
        self.assertEqual(updated, 0)  # already read

    def test_inbox_immutability_once_read(self):
        item = UserInboxFactory(user=self.user, is_read=False)
        item.mark_read()
        item.refresh_from_db()
        item.is_read = False  # attempt to un-read
        with self.assertRaises(ValidationError):
            item.save()
