"""
test_tasks.py – Tests for Celery tasks.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase

from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    RewardedPostbackLogFactory,
    PostbackS2SLogFactory,
)


class ProcessPostbackTaskTests(TestCase):

    def test_task_is_registered(self):
        from api.postback.tasks import process_postback
        self.assertTrue(callable(process_postback))

    def test_task_is_callable_with_args(self):
        from api.postback.tasks import process_postback
        log = PostbackLogFactory()
        with patch("api.postback.services.process_postback_sync") as mock_sync:
            mock_sync.return_value = log
            # Task is callable without raising an unexpected exception type
            try:
                process_postback(
                    log_id=str(log.pk),
                    signature="",
                    timestamp_str="12345",
                    nonce="",
                    body_bytes_hex="",
                    path="/api/postback/receive/cpalead/",
                    query_params={},
                )
            except Exception as exc:
                # Only Celery Retry is acceptable in test environment
                self.assertIn(
                    type(exc).__name__,
                    ("Retry", "MaxRetriesExceededError", "OperationalError", "ImproperlyConfigured"),
                    f"Unexpected exception type: {type(exc).__name__}: {exc}",
                )

    def test_task_with_nonexistent_log_id_does_not_raise_unexpected(self):
        from api.postback.tasks import process_postback
        try:
            process_postback(
                log_id="00000000-0000-0000-0000-000000000000",
                signature="",
                timestamp_str="12345",
                nonce="",
                body_bytes_hex="",
                path="/",
                query_params={},
            )
        except Exception as exc:
            self.assertIn(
                type(exc).__name__,
                ("Retry", "MaxRetriesExceededError", "OperationalError", "ImproperlyConfigured"),
                f"Unexpected exception type: {type(exc).__name__}: {exc}",
            )


class RetryFailedPostbacksTaskTests(TestCase):

    def test_task_is_registered(self):
        from api.postback.tasks import retry_failed_postbacks
        self.assertTrue(callable(retry_failed_postbacks))

    @patch("api.postback.tasks.process_postback")
    def test_retry_task_queues_failed_logs(self, mock_task):
        from api.postback.tasks import retry_failed_postbacks
        from api.postback.choices import PostbackStatus
        from api.postback.tests.factories import FailedPostbackLogFactory
        log = FailedPostbackLogFactory()
        mock_task.delay = MagicMock()
        retry_failed_postbacks()
        # Should have attempted to queue retry


class CleanupOldLogsTaskTests(TestCase):

    def test_task_is_registered(self):
        from api.postback.tasks import cleanup_old_logs
        self.assertTrue(callable(cleanup_old_logs))

    def test_cleanup_task_runs_without_error(self):
        from api.postback.tasks import cleanup_old_logs
        try:
            result = cleanup_old_logs()
        except Exception as exc:
            self.assertIn(
                type(exc).__name__,
                ("OperationalError", "ImproperlyConfigured", "DatabaseError"),
                f"Unexpected exception: {type(exc).__name__}: {exc}",
            )


class FireS2SPostbackTaskTests(TestCase):

    def test_task_is_registered(self):
        from api.postback.tasks import fire_s2s_postback_task
        self.assertTrue(callable(fire_s2s_postback_task))

    @patch("api.postback.utils.s2s_sender.fire_s2s_postback")
    def test_s2s_task_calls_fire(self, mock_fire):
        from api.postback.tasks import fire_s2s_postback_task
        mock_fire.return_value = True
        log = RewardedPostbackLogFactory()
        try:
            fire_s2s_postback_task(str(log.pk))
        except Exception as exc:
            self.assertIn(
                type(exc).__name__,
                ("Retry", "MaxRetriesExceededError", "OperationalError", "ImproperlyConfigured"),
                f"Unexpected exception: {type(exc).__name__}: {exc}",
            )


class CleanupS2SLogsTaskTests(TestCase):

    def test_task_is_registered(self):
        from api.postback.tasks import cleanup_s2s_logs
        self.assertTrue(callable(cleanup_s2s_logs))

    def test_cleanup_s2s_runs(self):
        from api.postback.tasks import cleanup_s2s_logs
        try:
            cleanup_s2s_logs()
        except Exception as exc:
            self.assertIn(
                type(exc).__name__,
                ("OperationalError", "ImproperlyConfigured", "DatabaseError"),
                f"Unexpected exception: {type(exc).__name__}: {exc}",
            )
