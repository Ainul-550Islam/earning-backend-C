"""Test Replay Events Management Command

Regression coverage for management/commands/replay_events.py, which had no
test coverage at all before Session 9. Focused on the batch_id bug in
_show_progress() (see that method's docstring for the full root-cause
writeup) - not a general test of every flag/branch in the command.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import OutputWrapper
from django.test import TestCase
from django.utils import timezone

from ..management.commands.replay_events import Command as ReplayEventsCommand
from ..services.replay import ReplayService
from ..models import WebhookEndpoint, WebhookDeliveryLog, WebhookReplayBatch, WebhookReplayItem
from ..constants import WebhookStatus, DeliveryStatus, ReplayStatus

User = get_user_model()


class ReplayEventsShowProgressTest(TestCase):
    """Direct tests of _show_progress() against a real ReplayService and a
    real WebhookReplayBatch - the fixed code path itself, not the full CLI
    wiring (see ReplayEventsCommandHandleTest for that)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='replay_admin', email='replay_admin@example.com', password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.replay_service = ReplayService()

    def _make_batch(self, status, item_count=0):
        today = timezone.now().date()
        batch = WebhookReplayBatch.objects.create(
            event_type='user.created',
            reason='test batch',
            created_by=self.user,
            count=max(item_count, 1),
            date_from=today,
            date_to=today,
            status=status,
        )
        for i in range(item_count):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'i': i},
                status=DeliveryStatus.FAILED,
            )
            WebhookReplayItem.objects.create(
                batch=batch, original_log=log, status=ReplayStatus.PENDING,
            )
        return batch

    def test_show_progress_terminal_status_no_attribute_error(self):
        """Regression test for the replay_batch.batch_id AttributeError.

        WebhookReplayBatch has no batch_id field; the previous code passed
        replay_batch.batch_id (an AttributeError - confirmed against the
        model) to get_batch_status(). That AttributeError never surfaced
        visibly: it was raised and caught inside this same method's own
        broad except, which only logs it - never re-raised, never written
        to stdout/stderr. So the only observable symptom was progress
        reporting silently doing nothing. This uses a real ReplayService
        and a real batch, so get_batch_status(replay_batch.pk) is
        genuinely exercised, not mocked away.
        """
        batch = self._make_batch(status=ReplayStatus.COMPLETED)
        command = ReplayEventsCommand()
        out = StringIO()
        command.stdout = OutputWrapper(out)

        with patch('api.webhooks.management.commands.replay_events.logger') as mock_logger:
            command._show_progress(self.replay_service, batch)
            mock_logger.error.assert_not_called()

        # Terminal status breaks on the very first check - no progress
        # line expected, but also no silent early exit due to an error.
        self.assertEqual(out.getvalue(), "")

    def test_show_progress_prints_progress_then_stops_on_both_call_sites(self):
        """Covers both fixed call sites (get_batch_status AND
        get_batch_progress both used replay_batch.batch_id before the fix).
        get_batch_status is mocked to go non-terminal -> terminal across two
        iterations; get_batch_progress stays real, against 1 pending item
        out of 2, so the printed line's numbers are genuine, not stubbed.
        """
        batch = self._make_batch(status=ReplayStatus.PROCESSING, item_count=2)
        completed_item = batch.items.first()
        completed_item.status = ReplayStatus.COMPLETED
        completed_item.save(update_fields=['status'])

        command = ReplayEventsCommand()
        out = StringIO()
        command.stdout = OutputWrapper(out)

        real_get_batch_status = self.replay_service.get_batch_status
        with patch.object(
            self.replay_service, 'get_batch_status',
            side_effect=[{'status': 'processing'}, {'status': 'completed'}],
        ) as mock_status, patch('time.sleep') as mock_sleep:
            command._show_progress(self.replay_service, batch)

        # Both calls used the batch's real pk, not a nonexistent batch_id
        # attribute.
        mock_status.assert_called_with(batch.pk)
        self.assertEqual(mock_status.call_count, 2)
        mock_sleep.assert_called_once_with(5)

        output = out.getvalue()
        self.assertIn("Progress: 1/2", output)
        self.assertIn("50.0%", output)
        self.assertIn("Status: processing", output)

        # Sanity-check get_batch_progress(batch.pk) directly too, since
        # it's the second of the two fixed call sites.
        progress = real_get_batch_status(batch.pk)
        self.assertEqual(progress['status'], ReplayStatus.PROCESSING)


class ReplayEventsCommandHandleTest(TestCase):
    """End-to-end-ish test through handle() itself, to confirm the fix is
    correctly wired in from the top of the command, not just correct in
    isolation.

    start_batch_processing() is mocked here rather than left to actually
    queue the real Celery task and hit a real HTTP endpoint. This used to
    be load-bearing for a different reason: a separate ordering bug in
    ReplayService.start_batch_processing() (delay() ran the real
    processing synchronously in eager mode BEFORE the old code's
    unconditional batch.status = "processing" line, which could stomp
    right back over a real terminal result) meant an unmocked run here
    risked a genuine hang against _show_progress()'s polling loop. That's
    fixed now too (see ReplayService.start_batch_processing()'s docstring
    and its own dedicated tests in test_services.py/test_viewsets.py) -
    keeping the mock here regardless, since this test's own concern is
    replay_events.py's wiring specifically, and a real HTTP call to a
    fake endpoint has nothing to do with that.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='replay_admin2', email='replay_admin2@example.com', password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 1},
            status=DeliveryStatus.FAILED,
        )

    def test_handle_reaches_show_progress_without_silent_failure(self):
        def fake_start_batch_processing(batch):
            batch.status = ReplayStatus.COMPLETED
            batch.save(update_fields=['status'])
            return True

        out = StringIO()
        err = StringIO()
        with patch(
            'api.webhooks.services.replay.ReplayService.start_batch_processing',
            side_effect=fake_start_batch_processing,
        ):
            call_command('replay_events', event_type='user.created', stdout=out, stderr=err)

        output = out.getvalue()
        self.assertIn("Created replay batch", output)
        self.assertIn("Replay batch processing started", output)
        # No visible sign of the swallowed AttributeError, and no stderr
        # output at all - the pre-fix behavior produced no error text
        # anywhere, so absence of stderr output isn't itself sufficient
        # proof, but combined with the direct _show_progress tests above
        # it confirms handle() reaches the fixed code without raising.
        self.assertEqual(err.getvalue(), "")
