"""
Model-level tests — validation, constraints, business methods.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from .factories import (
    UserFactory, InternalChatFactory, GroupChatFactory,
    ChatParticipantFactory, ChatMessageFactory,
)
from ..models import (
    InternalChat, ChatParticipant, ChatMessage,
    UserPresence, CallSession,
)
from ..choices import ChatStatus, MessageStatus, CallStatus


class TestInternalChatModel(TestCase):
    def test_group_chat_requires_name(self):
        chat = InternalChat(is_group=True, name="")
        with self.assertRaises(ValidationError):
            chat.full_clean()

    def test_direct_chat_no_name_ok(self):
        user = UserFactory()
        chat = InternalChat(is_group=False, name="", created_by=user)
        chat.full_clean()  # should not raise

    def test_archive_active_chat(self):
        chat = InternalChatFactory()
        self.assertEqual(chat.status, ChatStatus.ACTIVE)
        chat.archive()
        self.assertEqual(chat.status, ChatStatus.ARCHIVED)

    def test_archive_idempotent(self):
        chat = InternalChatFactory()
        chat.archive()
        chat.archive()  # should not raise
        self.assertEqual(chat.status, ChatStatus.ARCHIVED)

    def test_soft_delete_chat(self):
        chat = InternalChatFactory()
        chat.soft_delete()
        self.assertEqual(chat.status, ChatStatus.DELETED)

    def test_assert_active_raises_on_archived(self):
        from ..exceptions import ChatArchivedError
        chat = InternalChatFactory()
        chat.archive()
        with self.assertRaises(ChatArchivedError):
            chat.assert_active()

    def test_touch_updates_last_message_at(self):
        chat = InternalChatFactory()
        old = chat.last_message_at
        chat.touch()
        chat.refresh_from_db()
        self.assertIsNotNone(chat.last_message_at)
        self.assertNotEqual(chat.last_message_at, old)

    def test_is_active_property(self):
        chat = InternalChatFactory()
        self.assertTrue(chat.is_active)
        chat.archive()
        self.assertFalse(chat.is_active)


class TestChatMessageModel(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_text_message_requires_content(self):
        msg = ChatMessage(chat=self.chat, sender=self.user, content="", message_type="TEXT")
        with self.assertRaises(ValidationError):
            msg.full_clean()

    def test_system_message_no_sender(self):
        msg = ChatMessage(chat=self.chat, sender=self.user, content="test", message_type="SYSTEM")
        with self.assertRaises(ValidationError):
            msg.full_clean()

    def test_soft_delete_replaces_content(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        msg.soft_delete()
        self.assertEqual(msg.status, MessageStatus.DELETED)
        self.assertEqual(msg.content, "[This message was deleted]")
        self.assertEqual(msg.attachments, [])

    def test_soft_delete_idempotent(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        msg.soft_delete()
        msg.soft_delete()  # should not raise
        self.assertEqual(msg.status, MessageStatus.DELETED)

    def test_mark_edited(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="Original")
        msg.mark_edited("Updated content")
        msg.refresh_from_db()
        self.assertEqual(msg.content, "Updated content")
        self.assertTrue(msg.is_edited)
        self.assertIsNotNone(msg.edited_at)

    def test_cannot_edit_deleted_message(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        msg.soft_delete()
        with self.assertRaises(ValidationError):
            msg.mark_edited("New content")

    def test_is_visible_property(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        self.assertTrue(msg.is_visible)
        msg.soft_delete()
        self.assertFalse(msg.is_visible)

    def test_attachment_validation_max_files(self):
        msg = ChatMessage(
            chat=self.chat, sender=self.user, content="test",
            attachments=[
                {"url": f"http://x.com/{i}", "filename": f"f{i}.jpg",
                 "mimetype": "image/jpeg", "size_bytes": 1024}
                for i in range(11)  # exceeds MAX_ATTACHMENTS_PER_MESSAGE=10
            ]
        )
        with self.assertRaises(ValidationError):
            msg.full_clean()

    def test_attachment_requires_all_fields(self):
        msg = ChatMessage(
            chat=self.chat, sender=self.user, content="test",
            attachments=[{"url": "http://x.com/f.jpg"}]  # missing required fields
        )
        with self.assertRaises(ValidationError):
            msg.full_clean()


class TestChatParticipantModel(TestCase):
    def test_left_at_before_joined_at_invalid(self):
        chat = InternalChatFactory()
        user = UserFactory()
        now = timezone.now()
        cp = ChatParticipant(
            chat=chat, user=user,
            joined_at=now,
            left_at=now - timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            cp.full_clean()

    def test_mark_read_updates_timestamp(self):
        chat = InternalChatFactory()
        user = UserFactory()
        cp = ChatParticipantFactory(chat=chat, user=user)
        self.assertIsNone(cp.last_read_at)
        cp.mark_read()
        cp.refresh_from_db()
        self.assertIsNotNone(cp.last_read_at)


class TestUserPresenceModel(TestCase):
    def test_go_online(self):
        user = UserFactory()
        presence = UserPresence.objects.create(user=user, status="OFFLINE")
        presence.go_online()
        presence.refresh_from_db()
        self.assertEqual(presence.status, "ONLINE")

    def test_go_offline(self):
        user = UserFactory()
        presence = UserPresence.objects.create(user=user, status="ONLINE")
        presence.go_offline()
        presence.refresh_from_db()
        self.assertEqual(presence.status, "OFFLINE")

    def test_invisible_shows_offline(self):
        user = UserFactory()
        presence = UserPresence.objects.create(
            user=user, status="ONLINE", is_invisible=True
        )
        self.assertEqual(presence.effective_status, "OFFLINE")

    def test_visible_shows_real_status(self):
        user = UserFactory()
        presence = UserPresence.objects.create(
            user=user, status="ONLINE", is_invisible=False
        )
        self.assertEqual(presence.effective_status, "ONLINE")


class TestCallSessionModel(TestCase):
    def setUp(self):
        self.caller = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.caller)

    def test_end_call_calculates_duration(self):
        from ..utils.call_manager import generate_room_id
        call = CallSession.objects.create(
            call_type="AUDIO",
            status=CallStatus.ONGOING,
            chat=self.chat,
            initiated_by=self.caller,
            room_id=generate_room_id(),
            started_at=timezone.now() - timedelta(seconds=120),
        )
        call.end_call(status=CallStatus.ENDED)
        call.refresh_from_db()
        self.assertEqual(call.status, CallStatus.ENDED)
        self.assertGreaterEqual(call.duration_seconds, 120)

    def test_end_call_with_no_started_at(self):
        from ..utils.call_manager import generate_room_id
        call = CallSession.objects.create(
            call_type="AUDIO",
            status=CallStatus.RINGING,
            chat=self.chat,
            initiated_by=self.caller,
            room_id=generate_room_id(),
        )
        call.end_call(status=CallStatus.MISSED)
        call.refresh_from_db()
        self.assertEqual(call.status, CallStatus.MISSED)
        self.assertEqual(call.duration_seconds, 0)


class TestUserBlockModel(TestCase):
    def test_cannot_block_self(self):
        from ..models import UserBlock
        user = UserFactory()
        block = UserBlock(blocker=user, blocked=user)
        with self.assertRaises(ValidationError):
            block.full_clean()

    def test_unique_block_constraint(self):
        from ..models import UserBlock
        from django.db import IntegrityError
        blocker = UserFactory()
        blocked = UserFactory()
        UserBlock.objects.create(blocker=blocker, blocked=blocked)
        with self.assertRaises(Exception):
            UserBlock.objects.create(blocker=blocker, blocked=blocked)


class TestAdminBroadcastModel(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)

    def test_broadcast_state_machine(self):
        from ..models import AdminBroadcast
        from ..choices import BroadcastStatus
        from ..exceptions import BroadcastStateError
        b = AdminBroadcast.objects.create(
            title="Test", body="Body", created_by=self.admin
        )
        self.assertEqual(b.status, BroadcastStatus.DRAFT)
        b.transition_to(BroadcastStatus.SENDING)
        b.refresh_from_db()
        self.assertEqual(b.status, BroadcastStatus.SENDING)
        b.transition_to(BroadcastStatus.SENT)
        b.refresh_from_db()
        self.assertEqual(b.status, BroadcastStatus.SENT)
        with self.assertRaises(BroadcastStateError):
            b.transition_to(BroadcastStatus.DRAFT)

    def test_delivery_rate(self):
        from ..models import AdminBroadcast
        b = AdminBroadcast(recipient_count=100, delivered_count=85)
        self.assertEqual(b.delivery_rate, 85.0)

    def test_delivery_rate_zero_recipients(self):
        from ..models import AdminBroadcast
        b = AdminBroadcast(recipient_count=0, delivered_count=0)
        self.assertIsNone(b.delivery_rate)


class TestSupportThreadModel(TestCase):
    def test_state_machine(self):
        from ..models import SupportThread
        from ..choices import SupportThreadStatus
        from ..exceptions import SupportThreadClosedError
        user = UserFactory()
        agent = UserFactory(is_staff=True)
        t = SupportThread.objects.create(user=user, subject="Test", status=SupportThreadStatus.OPEN)
        t.transition_to(SupportThreadStatus.IN_PROGRESS, agent=agent)
        t.refresh_from_db()
        self.assertEqual(t.status, SupportThreadStatus.IN_PROGRESS)
        t.transition_to(SupportThreadStatus.RESOLVED, agent=agent)
        t.refresh_from_db()
        self.assertIsNotNone(t.resolved_at)
        t.transition_to(SupportThreadStatus.CLOSED, agent=agent)
        t.refresh_from_db()
        self.assertIsNotNone(t.closed_at)
        with self.assertRaises(SupportThreadClosedError):
            t.transition_to(SupportThreadStatus.OPEN, agent=agent)
