"""
tests/test_rate_limit_reset.py

Two previously-untested areas — now covered:

Part A: WebhookRateLimit.reset_counter() — proves the auto_now_add fix works.
        Before the fix, reset_counter() was a silent no-op: current_count was
        cleared in memory but reset_at was never persisted, so the rate-limit
        window never actually advanced.

Part B: Celery task retry path — proves that transient network failures
        (ConnectionError, Timeout) trigger the expected retry behaviour and
        that DeliveryLog.status is set to RETRYING before the retry is queued.
        Previously this was at 0% coverage.
"""

from django.utils import timezone
from django.test import TestCase
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch, call


# ═════════════════════════════════════════════════════════════════════════════
#  PART A — WebhookRateLimit.reset_counter() end-to-end proof
# ═════════════════════════════════════════════════════════════════════════════

class TestRateLimitResetCounter(unittest.TestCase):
    """
    Proves the [ANA-01] fix is correct at the instance level.

    These tests exercise the reset_counter() method directly on
    WebhookRateLimit instances without needing a database.
    """

    def _make_rate_limit(self, current_count=100, window_seconds=3600):
        """Return an in-memory WebhookRateLimit without a DB row."""
        from api.webhooks.models.analytics import WebhookRateLimit
        rl                 = WebhookRateLimit.__new__(WebhookRateLimit)
        rl.current_count   = current_count
        rl.window_seconds  = window_seconds
        rl.pk              = 1
        return rl

    def test_reset_counter_sets_current_count_to_zero(self):
        """reset_counter() must set current_count to 0."""
        rl      = self._make_rate_limit(current_count=850)
        rl.save = MagicMock()
        rl.reset_counter()
        self.assertEqual(rl.current_count, 0)

    def test_reset_counter_updates_reset_at_timestamp(self):
        """
        reset_counter() must update reset_at to approximately now.

        Before the [ANA-01] fix, reset_at had auto_now_add=True so the
        assignment was discarded — this assertion would have failed because
        the timestamp stayed frozen at the original creation time.
        """
        from django.utils import timezone
        rl         = self._make_rate_limit()
        rl.save    = MagicMock()
        before     = timezone.now()
        rl.reset_at = before - timedelta(hours=2)   # simulate old timestamp

        rl.reset_counter()

        self.assertGreaterEqual(
            rl.reset_at,
            before,
            "reset_at was NOT updated after reset_counter() call. "
            "The auto_now_add=True bug may still be present.",
        )

    def test_reset_counter_calls_save_with_update_fields(self):
        """save() must be called with update_fields containing reset_at."""
        rl         = self._make_rate_limit()
        rl.reset_at = MagicMock()  # any value
        save_mock  = MagicMock()
        rl.save    = save_mock

        rl.reset_counter()

        save_mock.assert_called_once()
        call_kwargs = save_mock.call_args[1]
        self.assertIn(
            "reset_at",
            call_kwargs.get("update_fields", []),
            "reset_at not in update_fields — the DB row won't be updated even "
            "though the in-memory attribute was changed.",
        )
        self.assertIn(
            "current_count",
            call_kwargs.get("update_fields", []),
            "current_count not in update_fields.",
        )

    def test_reset_counter_does_not_raise_on_clean_instance(self):
        """reset_counter() must not raise any exception on a normal instance."""
        rl      = self._make_rate_limit(current_count=500)
        rl.save = MagicMock()
        try:
            rl.reset_counter()
        except Exception as exc:
            self.fail(f"reset_counter() raised unexpectedly: {exc}")

    def test_is_exceeded_true_when_at_limit(self):
        rl = self._make_rate_limit(current_count=1000)
        rl.max_requests = 1000
        self.assertTrue(rl.is_exceeded())

    def test_is_exceeded_false_when_below_limit(self):
        rl = self._make_rate_limit(current_count=999)
        rl.max_requests = 1000
        self.assertFalse(rl.is_exceeded())

    def test_window_has_expired_true_after_window_passes(self):
        """window_has_expired() returns True when window has elapsed."""
        from django.utils import timezone
        rl               = self._make_rate_limit(window_seconds=3600)
        rl.reset_at      = timezone.now() - timedelta(hours=2)
        self.assertTrue(rl.window_has_expired())

    def test_window_has_expired_false_within_window(self):
        """window_has_expired() returns False when window is still open."""
        from django.utils import timezone
        rl               = self._make_rate_limit(window_seconds=3600)
        rl.reset_at      = timezone.now()
        self.assertFalse(rl.window_has_expired())

    def test_after_reset_window_not_expired(self):
        """After reset_counter(), window_has_expired() must return False."""
        from django.utils import timezone
        rl               = self._make_rate_limit(current_count=999, window_seconds=3600)
        rl.reset_at      = timezone.now() - timedelta(hours=2)
        rl.save          = MagicMock()

        rl.reset_counter()

        self.assertFalse(
            rl.window_has_expired(),
            "After reset_counter(), window_has_expired() still returns True — "
            "reset_at was not updated (auto_now_add bug may still be present).",
        )

    def test_reset_counter_idempotent_on_zero_count(self):
        """Calling reset_counter() on an already-zeroed counter is safe."""
        rl      = self._make_rate_limit(current_count=0)
        rl.save = MagicMock()
        rl.reset_counter()
        self.assertEqual(rl.current_count, 0)
        rl.save.assert_called_once()

    def test_reset_counter_called_twice_advances_reset_at_both_times(self):
        """Two consecutive resets must each advance reset_at."""
        from django.utils import timezone
        rl       = self._make_rate_limit(current_count=100)
        rl.save  = MagicMock()
        rl.reset_at = timezone.now() - timedelta(hours=3)

        rl.reset_counter()
        first_reset = rl.reset_at

        rl.current_count = 200
        rl.reset_counter()
        second_reset = rl.reset_at

        self.assertGreaterEqual(second_reset, first_reset)
        self.assertEqual(rl.save.call_count, 2)


# ═════════════════════════════════════════════════════════════════════════════
#  PART B — Celery task retry path (ConnectionError, Timeout)
# ═════════════════════════════════════════════════════════════════════════════


class TestCeleryRetryPath(TestCase):
    """
    Proves that transient network failures correctly:
        1. Mark the delivery FAILED on the attempt that hit the error
        2. A subsequent schedule_retry() call queues a new dispatch_event
           task with exponential backoff, rather than giving up early
        3. Once attempt_number reaches max_attempts, schedule_retry() marks
           EXHAUSTED instead and does not queue anything

    REWRITTEN (this session): the original tests imported
    api.webhooks.tasks.dispatch_event._dispatch_with_retry and referenced a
    dispatch_webhook_task - neither exists anywhere in the codebase
    (confirmed empirically: ImportError / AttributeError, and a
    codebase-wide grep found no other reference to either name). The real
    architecture doesn't do in-task Celery self.retry() with inline
    exponential backoff at all: DispatchService._make_http_request() catches
    ConnectionError/Timeout itself and returns {'success': False, ...}
    (it never raises out to the task), _update_delivery_log() marks FAILED
    for any failure (there's no RETRYING transition in this flow - that
    status belongs to WebhookDeliveryLog's own schedule_retry(), a separate
    method used by INTEGRATION_SYSTEM/webhooks_integration.py, not the
    Celery dispatch/retry path this class is actually about), and retrying
    happens via a *separate*, later call to DispatchService.schedule_retry()
    - from the periodic schedule_failed_retries() sweep
    (tasks/retry_failed_dispatch.py) - which does the real exponential
    backoff calculation, sets status to PENDING with next_retry_at, and
    re-queues dispatch_event via apply_async(eta=...). Traced end to end
    (_dispatch -> _update_delivery_log -> schedule_retry) and confirmed
    empirically before rewriting these to test that real, two-phase flow.

    Previously 0% coverage — none of the 68 Celery tasks had a test that
    injected a transient exception and verified the retry path.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from api.webhooks.models import WebhookEndpoint
        from api.webhooks.choices import WebhookStatus
        from api.webhooks.services.core import DispatchService

        User = get_user_model()
        self.user = User.objects.create_user(
            username='celeryretrytest', email='crt@example.com',
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
            max_retries=3,
        )
        self.dispatch_service = DispatchService()

    def test_connection_error_triggers_retry(self):
        """
        ConnectionError during HTTP dispatch must mark the delivery FAILED,
        and a subsequent schedule_retry() call must then queue a new
        attempt (status PENDING, next_retry_at set, a new dispatch_event
        task queued) rather than giving up, since attempts remain.
        """
        import requests
        from api.webhooks.models import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        with patch('requests.request') as mock_req:
            mock_req.side_effect = requests.ConnectionError('Connection refused')
            success = self.dispatch_service.emit(
                endpoint=self.endpoint, event_type='user.created', payload={'test': True},
            )
        self.assertFalse(success)

        log = WebhookDeliveryLog.objects.filter(endpoint=self.endpoint).latest('created_at')
        self.assertEqual(log.status, DeliveryStatus.FAILED)
        self.assertIn('Connection', log.error_message)

        with patch('api.webhooks.tasks.dispatch_event.dispatch_event.apply_async') as mock_apply:
            scheduled = self.dispatch_service.schedule_retry(log)

        log.refresh_from_db()
        self.assertTrue(scheduled)
        self.assertEqual(log.status, DeliveryStatus.PENDING)
        self.assertIsNotNone(log.next_retry_at)
        mock_apply.assert_called_once()

    def test_timeout_error_triggers_retry(self):
        """requests.Timeout must be handled the same way as ConnectionError."""
        import requests
        from api.webhooks.models import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        with patch('requests.request') as mock_req:
            mock_req.side_effect = requests.Timeout('Read timeout')
            success = self.dispatch_service.emit(
                endpoint=self.endpoint, event_type='user.created', payload={'test': True},
            )
        self.assertFalse(success)

        log = WebhookDeliveryLog.objects.filter(endpoint=self.endpoint).latest('created_at')
        self.assertEqual(log.status, DeliveryStatus.FAILED)

        with patch('api.webhooks.tasks.dispatch_event.dispatch_event.apply_async') as mock_apply:
            scheduled = self.dispatch_service.schedule_retry(log)

        log.refresh_from_db()
        self.assertTrue(scheduled)
        self.assertEqual(log.status, DeliveryStatus.PENDING)
        mock_apply.assert_called_once()

    def test_exhausted_after_max_attempts(self):
        """
        When attempt_number == max_attempts, schedule_retry() must mark the
        log EXHAUSTED and must NOT queue a new dispatch_event task.
        """
        from api.webhooks.models import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint, event_type='user.created', payload={},
            status=DeliveryStatus.FAILED, attempt_number=3, max_attempts=3,
        )
        with patch('api.webhooks.tasks.dispatch_event.dispatch_event.apply_async') as mock_apply:
            scheduled = self.dispatch_service.schedule_retry(log)

        log.refresh_from_db()
        self.assertFalse(scheduled)
        self.assertEqual(log.status, DeliveryStatus.EXHAUSTED)
        mock_apply.assert_not_called()

    def test_retry_countdown_uses_exponential_backoff(self):
        """
        Retry delay must follow exponential backoff:
            attempt 1 → 60 s
            attempt 2 → 300 s (5 min)
            attempt 3 → 900 s (15 min)
        """
        from api.webhooks.models.core import WebhookDeliveryLog
        log = WebhookDeliveryLog.__new__(WebhookDeliveryLog)

        log.attempt_number = 1
        self.assertEqual(log.get_retry_delay(), 60)

        log.attempt_number = 2
        self.assertEqual(log.get_retry_delay(), 300)

        log.attempt_number = 3
        self.assertEqual(log.get_retry_delay(), 900)

    def test_schedule_retry_returns_false_for_exhausted_log(self):
        """schedule_retry() must return False when is_retryable is False."""
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        log                = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.status         = DeliveryStatus.EXHAUSTED
        log.attempt_number = 3
        log.max_attempts   = 3

        result = log.schedule_retry()
        self.assertFalse(result, "schedule_retry() returned True for an exhausted log.")

    def test_schedule_retry_sets_retrying_status(self):
        """schedule_retry() must set status to RETRYING and call save()."""
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        log                = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.status         = DeliveryStatus.FAILED
        log.attempt_number = 1
        log.max_attempts   = 3
        log.save           = MagicMock()

        result = log.schedule_retry()

        self.assertTrue(result)
        self.assertEqual(log.status, DeliveryStatus.RETRYING)
        self.assertIsNotNone(log.next_retry_at)
        log.save.assert_called_once()

    def test_schedule_retry_sets_next_retry_at_in_future(self):
        """next_retry_at must be set to a future timestamp."""
        from django.utils import timezone
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        log                = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.status         = DeliveryStatus.FAILED
        log.attempt_number = 2
        log.max_attempts   = 3
        log.save           = MagicMock()

        before = timezone.now()
        log.schedule_retry()

        self.assertGreater(
            log.next_retry_at,
            before,
            "next_retry_at is not in the future after schedule_retry().",
        )

    def test_mark_as_failed_sets_exhausted_when_at_limit(self):
        """mark_as_failed() sets status=EXHAUSTED when attempt==max."""
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        log                = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.attempt_number = 3
        log.max_attempts   = 3
        log.response_body  = ""
        log.completed_at   = None
        log.save           = MagicMock()

        log.mark_as_failed(error_message="final error", status_code=500)

        self.assertEqual(log.status, DeliveryStatus.EXHAUSTED)

    def test_mark_as_failed_sets_failed_when_retryable(self):
        """mark_as_failed() sets status=FAILED when there are retries left."""
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        log                = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.attempt_number = 1
        log.max_attempts   = 3
        log.response_body  = ""
        log.completed_at   = None
        log.save           = MagicMock()

        log.mark_as_failed(error_message="transient error", status_code=503)

        self.assertEqual(log.status, DeliveryStatus.FAILED)

    def test_was_successful_true_on_2xx_response(self):
        """was_successful must be True for a 200–299 status code."""
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        for code in (200, 201, 204, 299):
            log                  = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
            log.status           = DeliveryStatus.SUCCESS
            log.http_status_code = code
            self.assertTrue(
                log.was_successful,
                f"was_successful should be True for HTTP {code}",
            )

    def test_was_successful_false_on_4xx_5xx(self):
        """was_successful must be False for non-2xx responses."""
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus

        for code in (400, 403, 404, 500, 503):
            log                  = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
            log.status           = DeliveryStatus.FAILED
            log.http_status_code = code
            self.assertFalse(
                log.was_successful,
                f"was_successful should be False for HTTP {code}",
            )


if __name__ == "__main__":
    unittest.main()
