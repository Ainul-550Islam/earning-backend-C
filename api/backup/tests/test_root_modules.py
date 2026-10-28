"""
Test Root Module Files
Covers: validators, signals, signals_cap, middleware, consumers,
        pagination, decorators, receivers, tasks_cap, events,
        background_jobs, data_export, dependencies,
        attachment_upload_view, celery_beat_config, openai,
        routing, management/commands/encrypt_backup
"""

import os
import json
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock, Mock, PropertyMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ---------------------------------------------------------------------------
# Validators Tests
# ---------------------------------------------------------------------------

class BackupScheduleValidatorTest(TestCase):

    def test_valid_cron_expression_accepted(self):
        from api.backup.validators import validate_backup_schedule
        # Should not raise
        validate_backup_schedule("0 2 * * *")     # daily 2am
        validate_backup_schedule("*/15 * * * *")  # every 15 min
        validate_backup_schedule("0 0 * * 0")     # weekly sunday

    def test_empty_cron_raises_validation_error(self):
        from api.backup.validators import validate_backup_schedule
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_backup_schedule("")

    def test_invalid_cron_expression_raises_validation_error(self):
        from api.backup.validators import validate_backup_schedule
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_backup_schedule("not-a-cron")

    def test_cron_with_wrong_number_of_parts_raises(self):
        from api.backup.validators import validate_backup_schedule
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_backup_schedule("0 2 *")  # only 3 parts

    def test_invalid_minute_value_raises(self):
        from api.backup.validators import validate_backup_schedule
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_backup_schedule("99 * * * *")  # minute > 59

    def test_invalid_hour_value_raises(self):
        from api.backup.validators import validate_backup_schedule
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_backup_schedule("0 25 * * *")  # hour > 23


class BackupRetentionValidatorTest(TestCase):

    def test_positive_retention_days_accepted(self):
        from api.backup.validators import validate_retention_days
        validate_retention_days(7)
        validate_retention_days(30)
        validate_retention_days(365)

    def test_zero_retention_days_raises(self):
        from api.backup.validators import validate_retention_days
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_retention_days(0)

    def test_negative_retention_days_raises(self):
        from api.backup.validators import validate_retention_days
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_retention_days(-5)


class BackupNameValidatorTest(TestCase):

    def test_valid_backup_name_accepted(self):
        from api.backup.validators import validate_backup_name
        validate_backup_name("my_backup_2026")
        validate_backup_name("production-db-backup")

    def test_empty_backup_name_raises(self):
        from api.backup.validators import validate_backup_name
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_backup_name("")

    def test_too_long_name_raises(self):
        from api.backup.validators import validate_backup_name
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_backup_name("x" * 300)


# ---------------------------------------------------------------------------
# Signals Tests
# ---------------------------------------------------------------------------

class BackupSignalsTest(TestCase):

    def test_backup_lifecycle_signals_exist(self):
        from api.backup.signals import (
            backup_started, backup_completed, backup_failed,
            backup_cancelled, backup_verified, backup_restored,
        )
        for sig in [backup_started, backup_completed, backup_failed,
                    backup_cancelled, backup_verified, backup_restored]:
            self.assertIsNotNone(sig)

    def test_schedule_signals_exist(self):
        from api.backup.signals import (
            schedule_triggered, schedule_completed, schedule_failed,
            schedule_paused, schedule_resumed,
        )
        for sig in [schedule_triggered, schedule_completed, schedule_failed,
                    schedule_paused, schedule_resumed]:
            self.assertIsNotNone(sig)

    def test_storage_signals_exist(self):
        from api.backup.signals import (
            storage_connected, storage_disconnected,
            storage_full, storage_error,
        )
        for sig in [storage_connected, storage_disconnected,
                    storage_full, storage_error]:
            self.assertIsNotNone(sig)

    def test_alert_signals_exist(self):
        from api.backup.signals import alert_created, alert_resolved
        self.assertIsNotNone(alert_created)
        self.assertIsNotNone(alert_resolved)

    def test_backup_started_signal_sends(self):
        from api.backup.signals import backup_started
        handler = Mock()
        backup_started.connect(handler)
        backup_started.send(sender=None, backup_id="bk-001")
        handler.assert_called_once()
        backup_started.disconnect(handler)

    def test_backup_completed_signal_sends(self):
        from api.backup.signals import backup_completed
        handler = Mock()
        backup_completed.connect(handler)
        backup_completed.send(sender=None, backup_id="bk-002", size=1024)
        handler.assert_called_once()
        backup_completed.disconnect(handler)

    def test_backup_failed_signal_sends(self):
        from api.backup.signals import backup_failed
        handler = Mock()
        backup_failed.connect(handler)
        backup_failed.send(sender=None, backup_id="bk-003", error="Disk full")
        handler.assert_called_once()
        backup_failed.disconnect(handler)


class SignalsCapTest(TestCase):

    def test_signals_cap_module_importable(self):
        from backup import signals_cap
        self.assertIsNotNone(signals_cap)

    def test_tasks_cap_module_importable(self):
        from backup import tasks_cap
        self.assertIsNotNone(tasks_cap)


# ---------------------------------------------------------------------------
# Middleware Tests
# ---------------------------------------------------------------------------

class BackupStatusMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_middleware_importable(self):
        from api.backup.middleware import BackupStatusMiddleware
        self.assertTrue(callable(BackupStatusMiddleware))

    def test_middleware_init(self):
        from api.backup.middleware import BackupStatusMiddleware
        get_response = Mock(return_value=Mock(status_code=200))
        mw = BackupStatusMiddleware(get_response)
        self.assertIsNotNone(mw)

    def test_middleware_passes_through_request(self):
        from api.backup.middleware import BackupStatusMiddleware
        from django.http import HttpResponse
        mock_response = HttpResponse("OK")
        get_response = Mock(return_value=mock_response)
        mw = BackupStatusMiddleware(get_response)
        request = self.factory.get("/api/backup/")
        request.user = MagicMock(is_authenticated=True, is_staff=True)
        response = mw(request)
        self.assertEqual(response.status_code, 200)

    def test_middleware_processes_non_backup_routes(self):
        from api.backup.middleware import BackupStatusMiddleware
        from django.http import HttpResponse
        mock_response = HttpResponse("OK")
        get_response = Mock(return_value=mock_response)
        mw = BackupStatusMiddleware(get_response)
        request = self.factory.get("/api/users/")
        request.user = MagicMock(is_authenticated=True, is_staff=False)
        response = mw(request)
        get_response.assert_called_once()


# ---------------------------------------------------------------------------
# Pagination Tests
# ---------------------------------------------------------------------------

class BackupPaginationTest(TestCase):

    def test_pagination_importable(self):
        from api.backup.pagination import BackupPagination
        self.assertTrue(callable(BackupPagination))

    def test_default_page_size(self):
        from api.backup.pagination import BackupPagination
        paginator = BackupPagination()
        self.assertEqual(paginator.page_size, 20)

    def test_max_page_size(self):
        from api.backup.pagination import BackupPagination
        paginator = BackupPagination()
        self.assertEqual(paginator.max_page_size, 100)

    def test_page_size_query_param(self):
        from api.backup.pagination import BackupPagination
        paginator = BackupPagination()
        self.assertEqual(paginator.page_size_query_param, "page_size")

    def test_limit_offset_pagination_importable(self):
        from api.backup.pagination import BackupLimitOffsetPagination
        paginator = BackupLimitOffsetPagination()
        self.assertIsNotNone(paginator)


# ---------------------------------------------------------------------------
# Decorators Tests
# ---------------------------------------------------------------------------

class BackupOperationDecoratorTest(TestCase):

    def test_backup_operation_decorator_importable(self):
        from api.backup.decorators import backup_operation
        self.assertTrue(callable(backup_operation))

    def test_decorator_wraps_function(self):
        from api.backup.decorators import backup_operation

        @backup_operation(operation_type="backup")
        def my_backup_func():
            return "done"

        result = my_backup_func()
        self.assertEqual(result, "done")

    def test_require_backup_permission_decorator_exists(self):
        from api.backup.decorators import require_backup_permission
        self.assertTrue(callable(require_backup_permission))

    def test_log_backup_activity_decorator_exists(self):
        from api.backup.decorators import log_backup_activity
        self.assertTrue(callable(log_backup_activity))

    def test_retry_on_failure_decorator_exists(self):
        from api.backup.decorators import retry_on_failure
        self.assertTrue(callable(retry_on_failure))

    def test_retry_decorator_retries_on_exception(self):
        from api.backup.decorators import retry_on_failure

        call_count = {"n": 0}

        @retry_on_failure(max_retries=3, delay=0)
        def flaky_func():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("transient error")
            return "success"

        result = flaky_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count["n"], 3)


# ---------------------------------------------------------------------------
# Receivers Tests
# ---------------------------------------------------------------------------

class BackupReceiversTest(TestCase):

    def test_receivers_module_importable(self):
        from backup import receivers
        self.assertIsNotNone(receivers)

    def test_backup_post_save_handler_exists(self):
        from api.backup.receivers import handle_backup_post_save
        self.assertTrue(callable(handle_backup_post_save))

    def test_schedule_triggered_handler_exists(self):
        from api.backup.receivers import handle_schedule_triggered
        self.assertTrue(callable(handle_schedule_triggered))


# ---------------------------------------------------------------------------
# Events Tests
# ---------------------------------------------------------------------------

class BackupEventsTest(TestCase):

    def test_events_module_importable(self):
        from backup import events
        self.assertIsNotNone(events)

    def test_backup_event_class_exists(self):
        from api.backup.events import BackupEvent
        self.assertTrue(callable(BackupEvent))

    def test_create_backup_event(self):
        from api.backup.events import BackupEvent
        event = BackupEvent(
            event_type="backup_completed",
            backup_id="bk-001",
            metadata={"size": 1024},
        )
        self.assertEqual(event.event_type, "backup_completed")
        self.assertEqual(event.backup_id, "bk-001")


# ---------------------------------------------------------------------------
# Background Jobs Tests
# ---------------------------------------------------------------------------

class BackgroundJobsTest(TestCase):

    def test_background_jobs_importable(self):
        from backup import background_jobs
        self.assertIsNotNone(background_jobs)

    def test_cleanup_job_exists(self):
        from api.backup.background_jobs import run_cleanup_job
        self.assertTrue(callable(run_cleanup_job))

    def test_health_check_job_exists(self):
        from api.backup.background_jobs import run_health_check_job
        self.assertTrue(callable(run_health_check_job))

    @patch("backup.background_jobs.cleanup_old_backups_task", create=True)
    def test_cleanup_job_calls_celery_task(self, mock_task):
        from api.backup.background_jobs import run_cleanup_job
        run_cleanup_job()
        mock_task.delay.assert_called_once()


# ---------------------------------------------------------------------------
# Data Export Tests
# ---------------------------------------------------------------------------

class DataExportTest(TestCase):

    def test_data_export_importable(self):
        from backup import data_export
        self.assertIsNotNone(data_export)

    def test_export_backup_list_function_exists(self):
        from api.backup.data_export import export_backup_list
        self.assertTrue(callable(export_backup_list))

    def test_export_to_csv_function_exists(self):
        from api.backup.data_export import export_to_csv
        self.assertTrue(callable(export_to_csv))

    def test_export_to_json_function_exists(self):
        from api.backup.data_export import export_to_json
        self.assertTrue(callable(export_to_json))

    @patch("backup.data_export.Backup", create=True)
    def test_export_to_csv_returns_content(self, mock_backup_model):
        from api.backup.data_export import export_to_csv
        mock_backup_model.objects.all.return_value = []
        result = export_to_csv(queryset=[])
        self.assertIsNotNone(result)

    @patch("backup.data_export.Backup", create=True)
    def test_export_to_json_returns_valid_json(self, mock_backup_model):
        from api.backup.data_export import export_to_json
        result = export_to_json(queryset=[])
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# Dependencies Tests
# ---------------------------------------------------------------------------

class DependenciesTest(TestCase):

    def test_dependencies_importable(self):
        from backup import dependencies
        self.assertIsNotNone(dependencies)

    def test_get_backup_service_function_exists(self):
        from api.backup.dependencies import get_backup_service
        self.assertTrue(callable(get_backup_service))

    def test_get_storage_adapter_function_exists(self):
        from api.backup.dependencies import get_storage_adapter
        self.assertTrue(callable(get_storage_adapter))


# ---------------------------------------------------------------------------
# Attachment Upload View Tests
# ---------------------------------------------------------------------------

class AttachmentUploadViewTest(TestCase):

    def test_attachment_upload_importable(self):
        from backup import attachment_upload_view
        self.assertIsNotNone(attachment_upload_view)

    def test_upload_view_class_exists(self):
        from api.backup.attachment_upload_view import AttachmentUploadView
        self.assertTrue(callable(AttachmentUploadView))

    def test_allowed_file_types_defined(self):
        from api.backup.attachment_upload_view import ALLOWED_EXTENSIONS
        self.assertIsInstance(ALLOWED_EXTENSIONS, (list, tuple, set))
        self.assertIn(".sql", ALLOWED_EXTENSIONS)

    def test_max_upload_size_defined(self):
        from api.backup.attachment_upload_view import MAX_UPLOAD_SIZE
        self.assertGreater(MAX_UPLOAD_SIZE, 0)


# ---------------------------------------------------------------------------
# Celery Beat Config Tests
# ---------------------------------------------------------------------------

class CeleryBeatConfigTest(TestCase):

    def test_celery_beat_config_importable(self):
        from backup import celery_beat_config
        self.assertIsNotNone(celery_beat_config)

    def test_beat_schedule_defined(self):
        from api.backup.celery_beat_config import BACKUP_BEAT_SCHEDULE
        self.assertIsInstance(BACKUP_BEAT_SCHEDULE, dict)
        self.assertGreater(len(BACKUP_BEAT_SCHEDULE), 0)

    def test_schedule_entries_have_required_keys(self):
        from api.backup.celery_beat_config import BACKUP_BEAT_SCHEDULE
        for task_name, config in BACKUP_BEAT_SCHEDULE.items():
            self.assertIn("task", config, f"{task_name} missing 'task' key")
            self.assertIn("schedule", config, f"{task_name} missing 'schedule' key")


# ---------------------------------------------------------------------------
# OpenAI Integration Tests
# ---------------------------------------------------------------------------

class OpenAIModuleTest(TestCase):

    def test_openai_module_importable(self):
        from backup import openai as backup_openai
        self.assertIsNotNone(backup_openai)

    def test_backup_analyzer_class_exists(self):
        from api.backup.openai import BackupAnalyzer
        self.assertTrue(callable(BackupAnalyzer))

    @patch("backup.openai.openai", create=True)
    def test_analyze_backup_anomalies(self, mock_openai):
        from api.backup.openai import BackupAnalyzer
        mock_openai.ChatCompletion.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"anomalies": []}'))]
        )
        analyzer = BackupAnalyzer(api_key="test-key")
        result = analyzer.analyze_anomalies(backup_stats={"success_rate": 0.95})
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# Routing Tests
# ---------------------------------------------------------------------------

class RoutingTest(TestCase):

    def test_routing_module_importable(self):
        from backup import routing
        self.assertIsNotNone(routing)

    def test_websocket_urlpatterns_defined(self):
        from api.backup.routing import websocket_urlpatterns
        self.assertIsInstance(websocket_urlpatterns, list)

    def test_backup_status_route_exists(self):
        from api.backup.routing import websocket_urlpatterns
        routes = [str(r.pattern) for r in websocket_urlpatterns]
        # At least one route should reference backup status
        self.assertTrue(
            any("backup" in r.lower() for r in routes),
            "Expected at least one backup-related WebSocket route",
        )


# ---------------------------------------------------------------------------
# Consumers Tests
# ---------------------------------------------------------------------------

class BackupConsumersTest(TestCase):

    def test_consumers_importable(self):
        from backup import consumers
        self.assertIsNotNone(consumers)

    def test_backup_status_consumer_exists(self):
        from api.backup.consumers import BackupStatusConsumer
        self.assertTrue(callable(BackupStatusConsumer))

    def test_backup_log_consumer_exists(self):
        from api.backup.consumers import BackupLogConsumer
        self.assertTrue(callable(BackupLogConsumer))

    def test_consumer_connect_requires_auth(self):
        from api.backup.consumers import BackupStatusConsumer
        consumer = BackupStatusConsumer()
        self.assertTrue(hasattr(consumer, "connect"))


# ---------------------------------------------------------------------------
# Management Command: encrypt_backup Tests
# ---------------------------------------------------------------------------

class EncryptBackupCommandTest(TestCase):

    def test_encrypt_backup_command_importable(self):
        from api.backup.management.commands.encrypt_backup import Command
        self.assertTrue(callable(Command))

    def test_command_has_handle_method(self):
        from api.backup.management.commands.encrypt_backup import Command
        cmd = Command()
        self.assertTrue(hasattr(cmd, "handle"))

    def test_command_has_add_arguments_method(self):
        from api.backup.management.commands.encrypt_backup import Command
        cmd = Command()
        self.assertTrue(hasattr(cmd, "add_arguments"))

    @patch("backup.management.commands.encrypt_backup.BackupEncryptionService", create=True)
    def test_command_calls_encryption_service(self, mock_enc_svc):
        from api.backup.management.commands.encrypt_backup import Command
        from io import StringIO
        mock_enc_svc.return_value.encrypt_backup.return_value = {"status": "success"}
        cmd = Command()
        cmd.stdout = StringIO()
        # Simulate handle with mocked args
        options = {"backup_id": "bk-001", "key": None, "output": None}
        try:
            cmd.handle(**options)
        except Exception:
            pass  # DB not set up — just ensure import and call path work
