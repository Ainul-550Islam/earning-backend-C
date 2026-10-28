"""
test_tasks_cpa.py
==================
Full coverage for messaging/tasks_cpa.py.
Functions: deliver_cpa_notification_task, _send_notification_email,
           send_cpa_broadcast_task, send_scheduled_cpa_broadcasts,
           send_payout_reminders, cleanup_old_cpa_notifications

Part 6 audit: test_cpa.py's tests all mock deliver_cpa_notification_task
and send_cpa_broadcast_task entirely at the task level (checking only
that .delay()/the task was called from the calling layer), so none of
these tasks' own internal logic was ever actually exercised - which is
exactly how this file sat at 35% coverage with everything green. These
tests call the tasks directly (CELERY_TASK_ALWAYS_EAGER, matching the
established pattern in test_tasks.py) to run the real code.
Place in: messaging/tests/test_tasks_cpa.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core import mail

from .factories import UserFactory, DeviceTokenFactory
from ..models import CPANotification, CPABroadcast
from ..tasks_cpa import (
    deliver_cpa_notification_task,
    _send_notification_email,
    send_cpa_broadcast_task,
    send_scheduled_cpa_broadcasts,
    send_payout_reminders,
    cleanup_old_cpa_notifications,
)


def _make_notification(**overrides):
    user = overrides.pop("recipient", None) or UserFactory()
    defaults = dict(
        recipient=user,
        notification_type="offer.approved",
        title="Your offer was approved",
        body="Great news — your offer application was approved.",
        priority="NORMAL",
    )
    defaults.update(overrides)
    return CPANotification.objects.create(**defaults)


class TestDeliverCpaNotificationTask(TestCase):
    def test_returns_not_found_for_missing_notification(self):
        result = deliver_cpa_notification_task("00000000-0000-0000-0000-000000000000")
        self.assertEqual(result, {"ok": False, "error": "not_found"})

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_push_sent_true_only_when_push_actually_succeeds(self, mock_push):
        """
        Regression test (Part 6 audit): push_sent used to be set True
        unconditionally right after the call, regardless of whether
        _send_push_to_user() returned True or False - as long as it
        didn't raise. Only a genuine success should mark it sent.
        """
        mock_push.return_value = True
        notif = _make_notification()
        deliver_cpa_notification_task(str(notif.id))
        notif.refresh_from_db()
        self.assertTrue(notif.push_sent)
        self.assertIsNotNone(notif.push_sent_at)

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_push_sent_stays_false_when_push_fails(self, mock_push):
        mock_push.return_value = False
        notif = _make_notification()
        result = deliver_cpa_notification_task(str(notif.id))
        notif.refresh_from_db()
        self.assertFalse(notif.push_sent)
        self.assertIsNone(notif.push_sent_at)
        self.assertEqual(result["push"], "failed")

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_push_error_isolated_from_other_channels(self, mock_push):
        mock_push.side_effect = Exception("FCM down")
        notif = _make_notification(priority="URGENT", recipient=UserFactory(email="a@example.com"))
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertIn("push_error", result)
        self.assertEqual(result.get("email"), "sent")  # unaffected by push failure

    def test_normal_priority_skips_email(self):
        user = UserFactory(email="normal@example.com")
        notif = _make_notification(priority="NORMAL", recipient=user)
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(result["email"], "skipped")
        notif.refresh_from_db()
        self.assertFalse(notif.email_sent)

    def test_high_priority_sends_email(self):
        user = UserFactory(email="high@example.com")
        notif = _make_notification(priority="HIGH", recipient=user)
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(result["email"], "sent")
        notif.refresh_from_db()
        self.assertTrue(notif.email_sent)
        self.assertIsNotNone(notif.email_sent_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_urgent_priority_sends_email(self):
        user = UserFactory(email="urgent@example.com")
        notif = _make_notification(priority="URGENT", recipient=user)
        deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(len(mail.outbox), 1)

    @patch("messaging.tasks_cpa._send_notification_email")
    def test_email_error_isolated_from_other_channels(self, mock_email):
        mock_email.side_effect = Exception("SMTP down")
        notif = _make_notification(priority="URGENT")
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertIn("email_error", result)
        self.assertIn("push", result)  # unaffected

    def test_sms_requested_reports_not_configured(self):
        notif = _make_notification(
            priority="URGENT", payload={"send_sms": True},
        )
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(result["sms"], "not_configured")
        notif.refresh_from_db()
        self.assertFalse(notif.sms_sent)

    def test_sms_not_requested_by_default(self):
        notif = _make_notification(priority="URGENT")
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertNotIn("sms", result)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_websocket_event_sent_with_correct_group(self, mock_ws):
        mock_ws.return_value = True
        user = UserFactory()
        notif = _make_notification(recipient=user)
        deliver_cpa_notification_task(str(notif.id))
        mock_ws.assert_called_once()
        self.assertEqual(mock_ws.call_args[1]["group_name"], f"user_devices_{user.pk}")
        self.assertEqual(mock_ws.call_args[1]["event_type"], "cpa.notification")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_websocket_error_isolated_from_other_channels(self, mock_ws):
        mock_ws.side_effect = Exception("channel layer down")
        notif = _make_notification()
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertIn("websocket_error", result)
        # push/email results still present despite the WS failure
        self.assertIn("push", result)

    # --- Broadcast-originated channel preferences (Part 6 audit fix) ---

    def test_broadcast_send_email_false_suppresses_email_even_at_high_priority(self):
        """
        Regression test (Part 6 audit): a broadcast explicitly configured
        with send_email=False previously still got an email if its
        priority was HIGH/URGENT, since the delivery task only ever
        looked at priority and never checked the broadcast's own
        delivery-channel configuration.
        """
        user = UserFactory(email="opted-out@example.com")
        notif = _make_notification(
            priority="HIGH", recipient=user,
            payload={"send_email": False},
        )
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(result["email"], "skipped")
        self.assertEqual(len(mail.outbox), 0)

    def test_broadcast_send_email_true_forces_email_at_normal_priority(self):
        user = UserFactory(email="opted-in@example.com")
        notif = _make_notification(
            priority="NORMAL", recipient=user,
            payload={"send_email": True},
        )
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(result["email"], "sent")
        self.assertEqual(len(mail.outbox), 1)

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_broadcast_send_push_false_skips_push(self, mock_push):
        notif = _make_notification(payload={"send_push": False})
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(result["push"], "skipped")
        mock_push.assert_not_called()

    def test_non_broadcast_notification_unaffected_by_channel_prefs(self):
        """Every notify_*() call in services_cpa.py creates a
        CPANotification with no send_push/send_email/send_sms keys in
        payload at all - these must keep using the original priority-
        based behavior exactly as before."""
        user = UserFactory(email="direct@example.com")
        notif = _make_notification(priority="HIGH", recipient=user, payload={})
        result = deliver_cpa_notification_task(str(notif.id))
        self.assertEqual(result["email"], "sent")  # HIGH priority -> email, unchanged


class TestSendNotificationEmail(TestCase):
    def test_sends_email_when_user_has_email(self):
        user = UserFactory(email="reachable@example.com")
        _send_notification_email(
            user_id=user.pk, title="Hi", body="Body text",
            action_url="/x/", action_label="View",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Body text", mail.outbox[0].body)
        self.assertIn("/x/", mail.outbox[0].body)

    def test_skips_when_user_has_no_email(self):
        user = UserFactory(email="")
        _send_notification_email(user_id=user.pk, title="Hi", body="B", action_url="", action_label="")
        self.assertEqual(len(mail.outbox), 0)

    def test_omits_action_line_when_no_action_url(self):
        user = UserFactory(email="noaction@example.com")
        _send_notification_email(user_id=user.pk, title="Hi", body="Body only", action_url="", action_label="")
        self.assertEqual(mail.outbox[0].body, "Body only")

    def test_swallows_exception_for_nonexistent_user(self):
        # Should not raise
        _send_notification_email(user_id=999999999, title="Hi", body="B", action_url="", action_label="")
        self.assertEqual(len(mail.outbox), 0)


class TestSendCpaBroadcastTask(TestCase):
    def _make_broadcast(self, **overrides):
        defaults = dict(
            title="New offer live!",
            body="Check out our newest offer.",
            notification_type="offer.new",
            priority="NORMAL",
            audience_filter="all",
        )
        defaults.update(overrides)
        return CPABroadcast.objects.create(**defaults)

    def test_returns_not_found_for_missing_broadcast(self):
        result = send_cpa_broadcast_task("00000000-0000-0000-0000-000000000000")
        self.assertEqual(result, {"ok": False, "error": "not_found"})

    def test_delivers_to_all_active_affiliates(self):
        UserFactory.create_batch(3)
        broadcast = self._make_broadcast()
        result = send_cpa_broadcast_task(str(broadcast.id))
        self.assertTrue(result["ok"])
        self.assertEqual(result["total"], result["delivered"])
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.status, "SENT")
        self.assertIsNotNone(broadcast.sent_at)
        self.assertEqual(broadcast.recipient_count, result["total"])
        self.assertEqual(broadcast.delivered_count, result["delivered"])

    def test_creates_one_notification_per_recipient_with_broadcast_id_in_payload(self):
        u1, u2 = UserFactory(), UserFactory()
        broadcast = self._make_broadcast()
        send_cpa_broadcast_task(str(broadcast.id))
        notifs = CPANotification.objects.filter(payload__broadcast_id=str(broadcast.id))
        self.assertEqual(notifs.count(), CPANotification.objects.filter(
            recipient_id__in=[u1.pk, u2.pk]
        ).count())
        for n in notifs:
            self.assertEqual(n.title, broadcast.title)

    def test_channel_prefs_threaded_into_notification_payload(self):
        UserFactory()
        broadcast = self._make_broadcast(send_push=True, send_email=False, send_sms=True)
        send_cpa_broadcast_task(str(broadcast.id))
        notif = CPANotification.objects.filter(payload__broadcast_id=str(broadcast.id)).first()
        self.assertEqual(notif.payload["send_push"], True)
        self.assertEqual(notif.payload["send_email"], False)
        self.assertEqual(notif.payload["send_sms"], True)

    def test_retry_does_not_duplicate_already_notified_recipients(self):
        """
        Regression test (Part 6 audit): a retry after partial failure
        previously re-resolved the same audience and re-created a
        notification for every recipient from scratch, including
        everyone already notified in the failed attempt.
        """
        users = UserFactory.create_batch(3)
        broadcast = self._make_broadcast()

        first_result = send_cpa_broadcast_task(str(broadcast.id))
        self.assertEqual(first_result["delivered"], 3)

        # Simulate a retry of the same task for the same broadcast (e.g.
        # Celery re-running it after a transient failure) - must not
        # create duplicate notifications for the same recipients.
        second_result = send_cpa_broadcast_task(str(broadcast.id))
        self.assertEqual(second_result["delivered"], 3)  # cumulative, not doubled
        self.assertEqual(
            CPANotification.objects.filter(payload__broadcast_id=str(broadcast.id)).count(),
            3,  # NOT 6
        )

    def test_delivered_count_survives_retry_as_cumulative_total(self):
        UserFactory.create_batch(2)
        broadcast = self._make_broadcast()
        send_cpa_broadcast_task(str(broadcast.id))
        send_cpa_broadcast_task(str(broadcast.id))
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.delivered_count, 2)

    def test_individual_recipient_failure_does_not_stop_the_batch(self):
        UserFactory.create_batch(3)
        broadcast = self._make_broadcast()
        with patch("messaging.services_cpa._create_notification") as mock_create:
            mock_create.side_effect = [Exception("boom"), MagicMock(), MagicMock()]
            result = send_cpa_broadcast_task(str(broadcast.id))
        self.assertEqual(result["delivered"], 2)
        self.assertEqual(result["total"], 3)

    def test_empty_audience_still_marks_sent(self):
        broadcast = self._make_broadcast(audience_filter="by_offer", audience_params={})
        result = send_cpa_broadcast_task(str(broadcast.id))
        self.assertTrue(result["ok"])
        self.assertEqual(result["delivered"], 0)
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.status, "SENT")

    def test_retries_on_audience_resolution_failure(self):
        broadcast = self._make_broadcast()
        with patch(
            "messaging.services_cpa._resolve_cpa_broadcast_audience",
            side_effect=Exception("DB down"),
        ):
            with self.assertRaises(Exception):
                send_cpa_broadcast_task.run(str(broadcast.id))
        broadcast.refresh_from_db()
        # First failure with retries remaining -> stays SENDING (task
        # re-queues itself), not marked FAILED yet.
        self.assertIn(broadcast.status, ("SENDING", "FAILED"))

    def test_marks_failed_after_retries_exhausted(self):
        broadcast = self._make_broadcast()
        bound_task = send_cpa_broadcast_task
        with patch(
            "messaging.services_cpa._resolve_cpa_broadcast_audience",
            side_effect=Exception("permanently broken"),
        ), patch.object(bound_task, "max_retries", 0):
            with self.assertRaises(Exception):
                bound_task.run(str(broadcast.id))
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.status, "FAILED")
        self.assertIn("permanently broken", broadcast.error_message)


class TestSendScheduledCpaBroadcasts(TestCase):
    def test_dispatches_due_broadcasts(self):
        from django.utils import timezone
        from datetime import timedelta
        due = CPABroadcast.objects.create(
            title="Due", body="b", status="SCHEDULED",
            scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        not_due = CPABroadcast.objects.create(
            title="Not due", body="b", status="SCHEDULED",
            scheduled_at=timezone.now() + timedelta(hours=1),
        )
        with patch("messaging.tasks_cpa.send_cpa_broadcast_task") as mock_task:
            result = send_scheduled_cpa_broadcasts()
        self.assertEqual(result["dispatched"], 1)
        mock_task.delay.assert_called_once_with(str(due.id))

    def test_ignores_non_scheduled_status(self):
        from django.utils import timezone
        from datetime import timedelta
        CPABroadcast.objects.create(
            title="Draft", body="b", status="DRAFT",
            scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        with patch("messaging.tasks_cpa.send_cpa_broadcast_task") as mock_task:
            result = send_scheduled_cpa_broadcasts()
        self.assertEqual(result["dispatched"], 0)
        mock_task.delay.assert_not_called()

    def test_no_due_broadcasts_returns_zero(self):
        result = send_scheduled_cpa_broadcasts()
        self.assertEqual(result, {"dispatched": 0})


class TestSendPayoutReminders(TestCase):
    def test_returns_stub_result(self):
        result = send_payout_reminders()
        self.assertEqual(result["sent"], 0)
        self.assertIn("date", result)


class TestCleanupOldCpaNotifications(TestCase):
    def test_deletes_old_read_and_dismissed(self):
        from django.utils import timezone
        from datetime import timedelta
        old = _make_notification()
        CPANotification.objects.filter(pk=old.pk).update(
            is_read=True, is_dismissed=True,
            created_at=timezone.now() - timedelta(days=100),
        )
        result = cleanup_old_cpa_notifications(days=90)
        self.assertEqual(result["deleted"], 1)
        self.assertFalse(CPANotification.objects.filter(pk=old.pk).exists())

    def test_keeps_recent_notifications(self):
        recent = _make_notification()
        CPANotification.objects.filter(pk=recent.pk).update(is_read=True, is_dismissed=True)
        result = cleanup_old_cpa_notifications(days=90)
        self.assertEqual(result["deleted"], 0)
        self.assertTrue(CPANotification.objects.filter(pk=recent.pk).exists())

    def test_keeps_unread_notifications_even_if_old(self):
        from django.utils import timezone
        from datetime import timedelta
        old_unread = _make_notification()
        CPANotification.objects.filter(pk=old_unread.pk).update(
            is_read=False, created_at=timezone.now() - timedelta(days=100),
        )
        result = cleanup_old_cpa_notifications(days=90)
        self.assertEqual(result["deleted"], 0)

    def test_respects_custom_days_argument(self):
        from django.utils import timezone
        from datetime import timedelta
        notif = _make_notification()
        CPANotification.objects.filter(pk=notif.pk).update(
            is_read=True, is_dismissed=True,
            created_at=timezone.now() - timedelta(days=40),
        )
        result_30 = cleanup_old_cpa_notifications(days=30)
        self.assertEqual(result_30["deleted"], 1)
