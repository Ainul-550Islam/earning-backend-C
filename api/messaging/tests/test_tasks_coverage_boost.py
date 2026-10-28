"""
test_tasks_coverage_boost.py
==============================
Coverage for messaging/tasks.py functions/branches not exercised by
test_tasks.py / test_tasks_missing.py: notify_new_chat_message's
online/offline participant branching, send_scheduled_broadcasts,
dispatch_webhook_task's real delivery loop (incl. the webhook_id single
-target scoping fix), and retry_webhook_delivery_task end to end.

Place in: messaging/tests/test_tasks_coverage_boost.py
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from .factories import (
    UserFactory, InternalChatFactory, ChatParticipantFactory, ChatMessageFactory,
    AdminBroadcastFactory, UserPresenceFactory,
)
from ..models import MessagingWebhook, WebhookDelivery, AdminBroadcast
from ..choices import PresenceStatus, BroadcastStatus


class TestNotifyNewChatMessage(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.sender = UserFactory()
        self.online_user = UserFactory()
        self.offline_user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.sender)
        ChatParticipantFactory(chat=self.chat, user=self.online_user)
        ChatParticipantFactory(chat=self.chat, user=self.offline_user)
        UserPresenceFactory(user=self.online_user, status=PresenceStatus.ONLINE)

    def test_message_not_found_returns_false(self):
        from ..tasks import notify_new_chat_message
        result = notify_new_chat_message("00000000-0000-0000-0000-000000000000")
        self.assertFalse(result)

    def test_notifies_online_and_queues_offline(self):
        from ..tasks import notify_new_chat_message
        msg = ChatMessageFactory(chat=self.chat, sender=self.sender, content="hey team")
        with patch("messaging.utils.notifier.notify_user_new_message") as mock_notify, \
             patch("messaging.utils.delivery_manager.queue_message_for_offline_user") as mock_queue:
            result = notify_new_chat_message(str(msg.id))
        self.assertTrue(result)
        # Push notification goes to both non-sender participants regardless
        # of online status.
        self.assertEqual(mock_notify.call_count, 2)
        notified_ids = {c.kwargs["user_id"] for c in mock_notify.call_args_list}
        self.assertEqual(notified_ids, {self.online_user.pk, self.offline_user.pk})
        # Offline queueing only happens for the offline participant.
        mock_queue.assert_called_once()
        self.assertEqual(mock_queue.call_args[0][0], self.offline_user.pk)

    def test_muted_participant_excluded(self):
        from ..tasks import notify_new_chat_message
        muted = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=muted, is_muted=True)
        msg = ChatMessageFactory(chat=self.chat, sender=self.sender, content="hi")
        with patch("messaging.utils.notifier.notify_user_new_message") as mock_notify, \
             patch("messaging.utils.delivery_manager.queue_message_for_offline_user"):
            notify_new_chat_message(str(msg.id))
        notified_ids = {c.kwargs["user_id"] for c in mock_notify.call_args_list}
        self.assertNotIn(muted.pk, notified_ids)


class TestSendScheduledBroadcasts(TestCase):
    def test_dispatches_due_broadcasts(self):
        from ..tasks import send_scheduled_broadcasts
        from datetime import timedelta
        due = AdminBroadcastFactory(
            status=BroadcastStatus.SCHEDULED, scheduled_at=timezone.now() + timedelta(hours=1),
        )
        AdminBroadcast.objects.filter(pk=due.pk).update(scheduled_at=timezone.now() - timedelta(minutes=1))
        AdminBroadcastFactory(status=BroadcastStatus.DRAFT)  # not due
        with patch("messaging.tasks.send_broadcast_async.delay") as mock_delay:
            result = send_scheduled_broadcasts()
        self.assertEqual(result["dispatched"], 1)
        mock_delay.assert_called_once_with(str(due.id))

    def test_no_due_broadcasts(self):
        from ..tasks import send_scheduled_broadcasts
        result = send_scheduled_broadcasts()
        self.assertEqual(result["dispatched"], 0)


class TestDispatchWebhookTaskDeliveryLoop(TestCase):
    def test_successful_delivery(self):
        from ..tasks import dispatch_webhook_task
        webhook = MessagingWebhook.objects.create(
            name="W", url="https://example.com/hook", secret="s3cr3t",
            events=["message.sent"], is_active=True,
        )
        mock_resp = MagicMock(status_code=200, text="ok")
        with patch("requests.post", return_value=mock_resp):
            result = dispatch_webhook_task(event_type="message.sent", payload={"x": 1})
        self.assertEqual(result["delivered"], 1)
        self.assertEqual(result["failed"], 0)
        webhook.refresh_from_db()
        self.assertEqual(webhook.failure_count, 0)
        self.assertIsNotNone(webhook.last_triggered_at)
        delivery = WebhookDelivery.objects.get(webhook=webhook)
        self.assertTrue(delivery.is_successful)

    def test_failed_delivery_increments_failure_count(self):
        from ..tasks import dispatch_webhook_task
        webhook = MessagingWebhook.objects.create(
            name="W", url="https://example.com/hook", secret="s3cr3t",
            events=["message.sent"], is_active=True, failure_count=0,
        )
        mock_resp = MagicMock(status_code=500, text="server error")
        with patch("requests.post", return_value=mock_resp):
            result = dispatch_webhook_task(event_type="message.sent", payload={})
        self.assertEqual(result["failed"], 1)
        webhook.refresh_from_db()
        self.assertEqual(webhook.failure_count, 1)

    def test_network_exception_counted_as_failure(self):
        from ..tasks import dispatch_webhook_task
        MessagingWebhook.objects.create(
            name="W", url="https://example.com/hook", secret="s3cr3t",
            events=["message.sent"], is_active=True,
        )
        with patch("requests.post", side_effect=ConnectionError("no route")):
            result = dispatch_webhook_task(event_type="message.sent", payload={})
        self.assertEqual(result["failed"], 1)
        delivery = WebhookDelivery.objects.first()
        self.assertIn("no route", delivery.error)

    def test_event_type_not_subscribed_skipped(self):
        from ..tasks import dispatch_webhook_task
        MessagingWebhook.objects.create(
            name="W", url="https://example.com/hook", secret="s3cr3t",
            events=["call.ended"], is_active=True,
        )
        with patch("requests.post") as mock_post:
            result = dispatch_webhook_task(event_type="message.sent", payload={})
        mock_post.assert_not_called()
        self.assertEqual(result["delivered"], 0)

    def test_webhook_id_scopes_to_single_target(self):
        # Regression test for the webhook-scoping bug fix: dispatching with
        # webhook_id must only hit that one webhook, bypassing the
        # is_active/events filters used for the broadcast-to-all path.
        from ..tasks import dispatch_webhook_task
        target = MessagingWebhook.objects.create(
            name="Target", url="https://example.com/target", secret="s1",
            events=["message.sent"], is_active=False,  # inactive on purpose
        )
        other = MessagingWebhook.objects.create(
            name="Other", url="https://example.com/other", secret="s2",
            events=["message.sent"], is_active=True,
        )
        mock_resp = MagicMock(status_code=200, text="ok")
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = dispatch_webhook_task(
                event_type="message.sent", payload={}, webhook_id=str(target.pk),
            )
        self.assertEqual(result["delivered"], 1)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[0][0], "https://example.com/target")


class TestRetryWebhookDeliveryTask(TestCase):
    def setUp(self):
        self.webhook = MessagingWebhook.objects.create(
            name="W", url="https://example.com/hook", secret="s3cr3t", is_active=True,
        )
        self.delivery = WebhookDelivery.objects.create(
            webhook=self.webhook, event_type="message.sent", payload={"a": 1},
        )

    def test_delivery_not_found(self):
        from ..tasks import retry_webhook_delivery_task
        result = retry_webhook_delivery_task.run("00000000-0000-0000-0000-000000000000")
        self.assertFalse(result["success"])

    def test_inactive_webhook_skipped(self):
        from ..tasks import retry_webhook_delivery_task
        self.webhook.is_active = False
        self.webhook.save(update_fields=["is_active"])
        result = retry_webhook_delivery_task.run(str(self.delivery.id))
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "webhook_inactive")

    def test_no_secret_rejected(self):
        from ..tasks import retry_webhook_delivery_task
        self.webhook.secret = ""
        self.webhook.save(update_fields=["secret"])
        result = retry_webhook_delivery_task.run(str(self.delivery.id))
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "webhook_secret_not_configured")

    def test_successful_retry(self):
        from ..tasks import retry_webhook_delivery_task
        mock_resp = MagicMock(status_code=200, text="ok")
        with patch("requests.post", return_value=mock_resp):
            result = retry_webhook_delivery_task.run(str(self.delivery.id))
        self.assertTrue(result["success"])
        self.assertEqual(result["status_code"], 200)
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.failure_count, 0)

    def test_failure_triggers_retry(self):
        from ..tasks import retry_webhook_delivery_task
        from celery.exceptions import Retry
        mock_resp = MagicMock(status_code=503, text="unavailable")
        with patch("requests.post", return_value=mock_resp):
            # .apply() does not implement the broker's retry-looping, so a
            # self.retry() call inside the task surfaces as a real Retry
            # exception rather than an automatically-re-run result.
            with self.assertRaises(Retry):
                retry_webhook_delivery_task.apply(args=[str(self.delivery.id)])
        self.delivery.refresh_from_db()
        self.assertFalse(self.delivery.is_successful)
