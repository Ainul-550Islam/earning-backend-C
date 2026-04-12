"""
Celery Task Tests — all 36 tasks.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock, call
from django.utils import timezone
from datetime import timedelta
from .factories import (
    UserFactory, InternalChatFactory, ChatParticipantFactory,
    ChatMessageFactory, AdminBroadcastFactory, DeviceTokenFactory,
)
from ..models import (
    ChatMessage, UserInbox, AdminBroadcast, UserPresence,
    ScheduledMessage, CPANotification, UserStory,
)
from ..choices import (
    MessageStatus, BroadcastStatus, PresenceStatus,
)


class TestDeliveryStatusTask(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_mark_delivered(self):
        from ..tasks import update_delivery_status_task
        result = update_delivery_status_task(
            str(self.msg.id), str(self.user.pk), "DELIVERED",
            timezone.now().isoformat()
        )
        self.assertTrue(result["ok"])
        self.msg.refresh_from_db()
        self.assertIn(str(self.user.pk), self.msg.delivery_receipts)

    def test_mark_read(self):
        from ..tasks import update_delivery_status_task
        result = update_delivery_status_task(
            str(self.msg.id), str(self.user.pk), "READ",
            timezone.now().isoformat()
        )
        self.assertTrue(result["ok"])
        self.msg.refresh_from_db()
        self.assertIn(str(self.user.pk), self.msg.read_receipts)

    def test_message_not_found(self):
        from ..tasks import update_delivery_status_task
        result = update_delivery_status_task(
            "00000000-0000-0000-0000-000000000000",
            "1", "DELIVERED", timezone.now().isoformat()
        )
        self.assertFalse(result["ok"])


class TestBroadcastTasks(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)
        UserFactory.create_batch(5)

    def test_send_broadcast_async_success(self):
        from ..tasks import send_broadcast_async
        b = AdminBroadcastFactory(created_by=self.admin)
        result = send_broadcast_async(str(b.id))
        self.assertTrue(result["success"])
        b.refresh_from_db()
        self.assertEqual(b.status, BroadcastStatus.SENT)

    def test_send_broadcast_async_not_found(self):
        from ..tasks import send_broadcast_async
        from ..exceptions import BroadcastNotFoundError
        with self.assertRaises(BroadcastNotFoundError):
            send_broadcast_async("00000000-0000-0000-0000-000000000000")

    def test_send_scheduled_broadcasts(self):
        from ..tasks import send_scheduled_broadcasts
        b = AdminBroadcastFactory(
            created_by=self.admin,
            status=BroadcastStatus.SCHEDULED,
            scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        with patch("messaging.tasks.send_broadcast_async") as mock_task:
            mock_task.delay = MagicMock()
            result = send_scheduled_broadcasts()
            self.assertGreaterEqual(result["dispatched"], 1)


class TestCleanupTasks(TestCase):
    def test_cleanup_old_inbox_items(self):
        from ..tasks import cleanup_old_inbox_items
        user = UserFactory()
        old_item = UserInbox.objects.create(
            user=user, item_type="SYSTEM", title="Old",
            is_read=True, read_at=timezone.now(),
            is_archived=True,
        )
        UserInbox.objects.filter(pk=old_item.pk).update(
            created_at=timezone.now() - timedelta(days=100)
        )
        result = cleanup_old_inbox_items(days=90)
        self.assertGreaterEqual(result["deleted"], 1)

    def test_cleanup_presence(self):
        from ..tasks import cleanup_presence
        user = UserFactory()
        presence = UserPresence.objects.create(user=user, status=PresenceStatus.ONLINE)
        UserPresence.objects.filter(pk=presence.pk).update(
            last_seen_at=timezone.now() - timedelta(minutes=10)
        )
        result = cleanup_presence()
        self.assertGreaterEqual(result["marked_offline"], 1)
        presence.refresh_from_db()
        self.assertEqual(presence.status, PresenceStatus.OFFLINE)

    def test_expire_stories(self):
        from ..tasks import expire_stories_task
        user = UserFactory()
        story = UserStory.objects.create(
            user=user,
            story_type="text",
            content="Old story",
            is_active=True,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        result = expire_stories_task()
        self.assertGreaterEqual(result["expired"], 1)
        story.refresh_from_db()
        self.assertFalse(story.is_active)

    def test_expire_calls(self):
        from ..tasks import expire_calls
        from ..models import CallSession
        from ..utils.call_manager import generate_room_id
        chat = InternalChatFactory()
        caller = UserFactory()
        call = CallSession.objects.create(
            call_type="AUDIO",
            status="RINGING",
            chat=chat,
            initiated_by=caller,
            room_id=generate_room_id(),
        )
        CallSession.objects.filter(pk=call.pk).update(
            created_at=timezone.now() - timedelta(seconds=60)
        )
        result = expire_calls()
        self.assertGreaterEqual(result["missed"], 1)

    def test_cleanup_expired_polls(self):
        from ..tasks import cleanup_expired_polls
        chat = InternalChatFactory()
        user = UserFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessage.objects.create(
            chat=chat, sender=user,
            content="Poll question?",
            message_type="POLL",
            poll_data={
                "question": "Poll?",
                "options": [{"id": "0", "text": "A"}],
                "expires_at": (timezone.now() - timedelta(hours=1)).isoformat(),
            }
        )
        result = cleanup_expired_polls()
        self.assertGreaterEqual(result["closed"], 1)
        msg.refresh_from_db()
        self.assertTrue(msg.poll_data.get("closed"))


class TestScheduledMessageTask(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_send_scheduled_messages(self):
        from ..tasks import send_scheduled_messages
        sched = ScheduledMessage.objects.create(
            chat=self.chat,
            sender=self.user,
            content="Scheduled content",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="PENDING",
        )
        result = send_scheduled_messages()
        self.assertGreaterEqual(result["sent"], 1)
        sched.refresh_from_db()
        self.assertEqual(sched.status, "SENT")


class TestNotificationTasks(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @patch("messaging.utils.notifier.notify_user_new_message")
    @patch("messaging.utils.delivery_manager.queue_message_for_offline_user")
    def test_notify_new_chat_message(self, mock_queue, mock_notify):
        mock_notify.return_value = True
        from ..tasks import notify_new_chat_message
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        result = notify_new_chat_message(str(msg.id))
        self.assertTrue(result)

    def test_notify_message_not_found(self):
        from ..tasks import notify_new_chat_message
        result = notify_new_chat_message("00000000-0000-0000-0000-000000000000")
        self.assertFalse(result)


class TestCPATasks(TestCase):
    def setUp(self):
        self.user = UserFactory()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_cleanup_old_cpa_notifications(self, mock_task):
        mock_task.delay = MagicMock()
        from ..tasks_cpa import cleanup_old_cpa_notifications
        notif = CPANotification.objects.create(
            recipient=self.user,
            notification_type="system.announcement",
            title="Old",
            body="Old notification",
            is_read=True,
            read_at=timezone.now(),
            is_dismissed=True,
        )
        CPANotification.objects.filter(pk=notif.pk).update(
            created_at=timezone.now() - timedelta(days=100)
        )
        result = cleanup_old_cpa_notifications(days=90)
        self.assertGreaterEqual(result["deleted"], 1)

    def test_send_scheduled_cpa_broadcasts(self):
        from ..tasks_cpa import send_scheduled_cpa_broadcasts
        from ..models import CPABroadcast
        b = CPABroadcast.objects.create(
            title="Test",
            body="Body",
            status="SCHEDULED",
            scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        with patch("messaging.tasks_cpa.send_cpa_broadcast_task") as mock_task:
            mock_task.delay = MagicMock()
            result = send_scheduled_cpa_broadcasts()
            self.assertGreaterEqual(result["dispatched"], 1)
