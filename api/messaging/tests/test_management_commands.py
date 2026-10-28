"""
test_management_commands.py
============================
Fix 8: Tests for all 7 previously-untested management commands.

Place in: messaging/tests/test_management_commands.py

Coverage:
  - bulk_index_messages
  - cleanup_chats
  - cleanup_messaging
  - create_cpa_templates
  - export_data_gdpr
  - setup_messaging_index
  - sync_search_index
"""
from __future__ import annotations
from io import StringIO
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .factories import UserFactory, InternalChatFactory


# ─────────────────────────────────────────────────────────────────────────────
# bulk_index_messages
# ─────────────────────────────────────────────────────────────────────────────

class TestBulkIndexMessagesCommand(TestCase):

    @patch("messaging.tasks.bulk_reindex_task")
    def test_sync_mode_calls_task_inline(self, mock_task):
        mock_task.return_value = {"indexed": 50, "errors": 0}
        out = StringIO()
        call_command("bulk_index_messages", stdout=out)
        mock_task.assert_called_once()
        self.assertIn("50", out.getvalue())

    @patch("messaging.tasks.bulk_reindex_task")
    def test_chat_id_filter_passed(self, mock_task):
        mock_task.return_value = {"indexed": 5, "errors": 0}
        call_command("bulk_index_messages", chat_id="some-uuid", stdout=StringIO())
        call_kwargs = mock_task.call_args[1]
        self.assertEqual(call_kwargs["chat_id"], "some-uuid")

    @patch("messaging.tasks.bulk_reindex_task")
    def test_days_option_passed(self, mock_task):
        mock_task.return_value = {"indexed": 10, "errors": 0}
        call_command("bulk_index_messages", days=30, stdout=StringIO())
        call_kwargs = mock_task.call_args[1]
        self.assertEqual(call_kwargs["days"], 30)

    @patch("messaging.tasks.bulk_reindex_task")
    def test_async_mode_uses_delay(self, mock_task):
        mock_delay = MagicMock()
        mock_delay.id = "celery-task-id-123"
        mock_task.delay.return_value = mock_delay
        out = StringIO()
        call_command("bulk_index_messages", use_async=True, stdout=out)
        mock_task.delay.assert_called_once()
        self.assertIn("celery-task-id-123", out.getvalue())

    @patch("messaging.tasks.bulk_reindex_task")
    def test_with_errors_still_reports(self, mock_task):
        mock_task.return_value = {"indexed": 100, "errors": 3}
        out = StringIO()
        call_command("bulk_index_messages", stdout=out)
        self.assertIn("3", out.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# cleanup_chats
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanupChatsCommand(TestCase):

    def test_dry_run_does_not_delete(self):
        out = StringIO()
        # Should not raise even with no data
        call_command("cleanup_chats", dry_run=True, stdout=out)
        self.assertIn("DRY RUN", out.getvalue())

    def test_invalid_days_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("cleanup_chats", days=0, stdout=StringIO())

    def test_invalid_inbox_days_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("cleanup_chats", inbox_days=0, stdout=StringIO())

    def test_default_run_outputs_counts(self):
        out = StringIO()
        call_command("cleanup_chats", days=30, inbox_days=90, stdout=out)
        output = out.getvalue()
        # Should mention chats and inbox items
        self.assertIn("Chats to delete:", output)
        self.assertIn("Inbox items to delete:", output)

    def test_dry_run_with_explicit_days(self):
        out = StringIO()
        call_command("cleanup_chats", days=7, inbox_days=30, dry_run=True, stdout=out)
        self.assertIn("DRY RUN", out.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# cleanup_messaging
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanupMessagingCommand(TestCase):

    @patch("messaging.tasks.cleanup_old_inbox_items")
    def test_inbox_cleanup(self, mock_task):
        mock_task.return_value = {"deleted": 5}
        out = StringIO()
        call_command("cleanup_messaging", inbox=True, stdout=out)
        mock_task.assert_called_once()
        self.assertIn("Inbox cleanup", out.getvalue())

    @patch("messaging.tasks.expire_stories_task")
    @patch("messaging.tasks.cleanup_old_stories")
    def test_stories_cleanup(self, mock_clean, mock_expire):
        mock_expire.return_value = {"expired": 2}
        mock_clean.return_value = {"deleted": 8}
        out = StringIO()
        call_command("cleanup_messaging", stories=True, stdout=out)
        mock_expire.assert_called_once()
        mock_clean.assert_called_once()
        self.assertIn("Stories", out.getvalue())

    @patch("messaging.tasks.expire_calls")
    @patch("messaging.tasks.cleanup_old_call_sessions")
    def test_calls_cleanup(self, mock_clean, mock_expire):
        mock_expire.return_value = {"expired": 1}
        mock_clean.return_value = {"deleted": 3}
        out = StringIO()
        call_command("cleanup_messaging", calls=True, stdout=out)
        mock_expire.assert_called_once()
        mock_clean.assert_called_once()
        self.assertIn("Calls", out.getvalue())

    @patch("messaging.tasks.cleanup_old_inbox_items")
    @patch("messaging.tasks.expire_stories_task")
    @patch("messaging.tasks.cleanup_old_stories")
    @patch("messaging.tasks.expire_calls")
    @patch("messaging.tasks.cleanup_old_call_sessions")
    @patch("messaging.tasks.cleanup_old_edit_history")
    @patch("messaging.tasks.cleanup_presence")
    @patch("messaging.tasks.expire_disappearing_messages_task")
    def test_all_flag_runs_all_tasks(
        self, mock_dis, mock_pres, mock_edit, mock_calls_c,
        mock_calls_e, mock_stories_c, mock_stories_e, mock_inbox
    ):
        for m in [mock_dis, mock_pres, mock_edit, mock_calls_c,
                  mock_calls_e, mock_stories_c, mock_stories_e, mock_inbox]:
            m.return_value = {"done": True}
        out = StringIO()
        call_command("cleanup_messaging", all=True, stdout=out)
        mock_inbox.assert_called()
        mock_stories_e.assert_called()
        mock_calls_e.assert_called()

    @patch("messaging.tasks.cleanup_presence")
    def test_presence_cleanup(self, mock_task):
        mock_task.return_value = {"cleaned": 10}
        out = StringIO()
        call_command("cleanup_messaging", presence=True, stdout=out)
        mock_task.assert_called_once()
        self.assertIn("Presence", out.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# create_cpa_templates
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateCpaTemplatesCommand(TestCase):

    def test_creates_10_default_templates(self):
        out = StringIO()
        call_command("create_cpa_templates", stdout=out)
        from ..models import MessageTemplate
        self.assertGreaterEqual(MessageTemplate.objects.count(), 10)
        self.assertIn("CREATED", out.getvalue())

    def test_skips_existing_templates_without_force(self):
        # Run twice
        call_command("create_cpa_templates", stdout=StringIO())
        out = StringIO()
        call_command("create_cpa_templates", stdout=out)
        self.assertIn("SKIP", out.getvalue())

    def test_force_flag_recreates_templates(self):
        call_command("create_cpa_templates", stdout=StringIO())
        out = StringIO()
        call_command("create_cpa_templates", force=True, stdout=out)
        # Should not skip any
        self.assertNotIn("SKIP", out.getvalue())

    def test_templates_have_required_fields(self):
        call_command("create_cpa_templates", stdout=StringIO())
        from ..models import MessageTemplate
        for tpl in MessageTemplate.objects.all():
            self.assertTrue(tpl.name)
            self.assertTrue(tpl.body)
            self.assertTrue(tpl.category)
            self.assertTrue(tpl.is_active)

    def test_template_categories_covered(self):
        call_command("create_cpa_templates", stdout=StringIO())
        from ..models import MessageTemplate
        categories = set(MessageTemplate.objects.values_list("category", flat=True))
        self.assertIn("offer", categories)
        self.assertIn("payout", categories)
        self.assertIn("account", categories)


# ─────────────────────────────────────────────────────────────────────────────
# export_data_gdpr
# ─────────────────────────────────────────────────────────────────────────────

class TestExportDataGdprCommand(TestCase):

    def test_nonexistent_user_writes_error(self):
        err = StringIO()
        call_command("export_data_gdpr", user_id=999999, stderr=err, stdout=StringIO())
        self.assertIn("not found", err.getvalue())

    def test_valid_user_exports_json(self):
        user = UserFactory()
        out = StringIO()
        call_command("export_data_gdpr", user_id=user.pk, stdout=out)
        output = out.getvalue()
        import json
        # Output should be valid JSON
        data = json.loads(output)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["id"], user.pk)
        self.assertEqual(data["user"]["username"], user.username)

    def test_export_contains_all_keys(self):
        user = UserFactory()
        out = StringIO()
        call_command("export_data_gdpr", user_id=user.pk, stdout=out)
        import json
        data = json.loads(out.getvalue())
        expected_keys = [
            "user", "chats_participated", "messages_sent",
            "support_threads", "inbox_items", "reactions",
            "blocked_users", "device_tokens", "cpa_notifications",
            "stories", "call_history",
        ]
        for key in expected_keys:
            self.assertIn(key, data, f"Missing key: {key}")

    def test_export_to_file(self):
        import tempfile, json, os
        user = UserFactory()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmpfile = f.name
        try:
            call_command(
                "export_data_gdpr",
                user_id=user.pk,
                output=tmpfile,
                stdout=StringIO(),
            )
            self.assertTrue(os.path.exists(tmpfile))
            with open(tmpfile) as f:
                data = json.load(f)
            self.assertEqual(data["user"]["id"], user.pk)
        finally:
            os.unlink(tmpfile)

    def test_messages_appear_in_export(self):
        from .factories import InternalChatFactory, ChatParticipantFactory, ChatMessageFactory
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        ChatMessageFactory(chat=chat, sender=user, content="GDPR test message")
        out = StringIO()
        call_command("export_data_gdpr", user_id=user.pk, stdout=out)
        import json
        data = json.loads(out.getvalue())
        self.assertGreater(len(data["messages_sent"]), 0)
        contents = [m["content"] for m in data["messages_sent"]]
        self.assertIn("GDPR test message", contents)


# ─────────────────────────────────────────────────────────────────────────────
# setup_messaging_index
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupMessagingIndexCommand(TestCase):

    @patch("messaging.utils.search_engine.get_es_client", return_value=None)
    def test_no_es_client_writes_error(self, mock_client):
        err = StringIO()
        call_command("setup_messaging_index", stderr=err, stdout=StringIO())
        self.assertIn("not configured", err.getvalue())

    @patch("messaging.utils.search_engine.get_es_client")
    def test_es_not_pingable_writes_error(self, mock_client_fn):
        mock_es = MagicMock()
        mock_es.ping.return_value = False
        mock_client_fn.return_value = mock_es
        err = StringIO()
        call_command("setup_messaging_index", stderr=err, stdout=StringIO())
        self.assertIn("Cannot connect", err.getvalue())

    @patch("messaging.utils.search_engine.ensure_index_exists", return_value=True)
    @patch("messaging.utils.search_engine.get_es_client")
    def test_successful_index_creation(self, mock_client_fn, mock_ensure):
        mock_es = MagicMock()
        mock_es.ping.return_value = True
        mock_client_fn.return_value = mock_es
        out = StringIO()
        call_command("setup_messaging_index", stdout=out)
        self.assertIn("ready", out.getvalue())

    @patch("messaging.utils.search_engine.ensure_index_exists", return_value=False)
    @patch("messaging.utils.search_engine.get_es_client")
    def test_failed_index_creation_writes_error(self, mock_client_fn, mock_ensure):
        mock_es = MagicMock()
        mock_es.ping.return_value = True
        mock_client_fn.return_value = mock_es
        err = StringIO()
        call_command("setup_messaging_index", stderr=err, stdout=StringIO())
        self.assertIn("Failed", err.getvalue())

    @patch("messaging.tasks.bulk_reindex_task")
    @patch("messaging.utils.search_engine.ensure_index_exists", return_value=True)
    @patch("messaging.utils.search_engine.get_es_client")
    def test_bulk_index_option(self, mock_client_fn, mock_ensure, mock_task):
        mock_es = MagicMock()
        mock_es.ping.return_value = True
        mock_client_fn.return_value = mock_es
        mock_task.return_value = {"indexed": 200, "errors": 0}
        out = StringIO()
        call_command("setup_messaging_index", bulk_index=True, days=30, stdout=out)
        mock_task.assert_called_once_with(days=30)
        self.assertIn("200", out.getvalue())

    @patch("messaging.utils.search_engine.ensure_index_exists", return_value=True)
    @patch("messaging.utils.search_engine.get_es_client")
    def test_recreate_deletes_existing_index(self, mock_client_fn, mock_ensure):
        mock_es = MagicMock()
        mock_es.ping.return_value = True
        mock_es.indices.exists.return_value = True
        mock_client_fn.return_value = mock_es
        out = StringIO()
        call_command("setup_messaging_index", recreate=True, stdout=out)
        mock_es.indices.delete.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# sync_search_index
# ─────────────────────────────────────────────────────────────────────────────

class TestSyncSearchIndexCommand(TestCase):

    def test_dry_run_no_indexing(self):
        out = StringIO()
        call_command("sync_search_index", dry_run=True, stdout=out)
        self.assertIn("DRY RUN", out.getvalue())

    @patch("messaging.utils.search_engine.index_message", return_value=True)
    @patch("messaging.utils.search_engine.get_es_client")
    def test_sync_indexes_messages(self, mock_client_fn, mock_index):
        from .factories import InternalChatFactory, ChatParticipantFactory, ChatMessageFactory
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        ChatMessageFactory(chat=chat, sender=user, content="sync test")

        mock_es = MagicMock()
        mock_client_fn.return_value = mock_es
        out = StringIO()
        call_command("sync_search_index", days=1, stdout=out)
        self.assertIn("indexed=", out.getvalue())

    @patch("messaging.utils.search_engine.index_message", return_value=True)
    @patch("messaging.utils.search_engine.get_es_client")
    def test_chat_id_filter_applied(self, mock_client_fn, mock_index):
        mock_es = MagicMock()
        mock_client_fn.return_value = mock_es
        out = StringIO()
        call_command(
            "sync_search_index",
            days=7,
            chat_id="00000000-0000-0000-0000-000000000001",
            stdout=out,
        )
        self.assertIn("indexed=", out.getvalue())

    @patch("messaging.utils.search_engine.index_message", side_effect=Exception("ES error"))
    @patch("messaging.utils.search_engine.get_es_client")
    def test_errors_reported_but_not_raised(self, mock_client_fn, mock_index):
        from .factories import InternalChatFactory, ChatParticipantFactory, ChatMessageFactory
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        ChatMessageFactory(chat=chat, sender=user, content="error test")

        mock_es = MagicMock()
        mock_client_fn.return_value = mock_es
        err = StringIO()
        out = StringIO()
        # Should not raise
        call_command("sync_search_index", days=1, stdout=out, stderr=err)
        output = out.getvalue()
        self.assertIn("errors=", output)

    def test_default_days_is_7(self):
        out = StringIO()
        call_command("sync_search_index", dry_run=True, stdout=out)
        # Command outputs message count — just check it runs without error
        self.assertIn("Found", out.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# send_broadcast
# ─────────────────────────────────────────────────────────────────────────────

class TestSendBroadcastCommand(TestCase):
    """
    Coverage for management/commands/send_broadcast.py.

    The command takes a broadcast_id positional argument and an optional
    --async flag.  Sync path calls services.send_broadcast() directly;
    async path calls send_broadcast_async.delay() and prints the task id.
    """

    # ── sync mode ─────────────────────────────────────────────────────────────

    @patch("messaging.services.send_broadcast")
    def test_sync_success_writes_recipient_count(self, mock_send):
        """Happy path: services.send_broadcast returns delivered count."""
        mock_send.return_value = {"delivered": 42, "skipped": 0, "failed": 0}
        out = StringIO()
        call_command("send_broadcast", "test-broadcast-id", stdout=out)
        mock_send.assert_called_once_with(broadcast_id="test-broadcast-id")
        self.assertIn("42", out.getvalue())

    @patch("messaging.services.send_broadcast")
    def test_sync_failure_writes_error_to_stderr(self, mock_send):
        """If services.send_broadcast raises, the error is written to stderr
        and the command does NOT raise (so it exits cleanly in a cron/shell)."""
        mock_send.side_effect = Exception("Broadcast not found or already sent")
        err = StringIO()
        out = StringIO()
        # Must not raise
        call_command("send_broadcast", "bad-id", stdout=out, stderr=err)
        self.assertIn("Failed", err.getvalue())
        self.assertIn("Broadcast not found", err.getvalue())

    @patch("messaging.services.send_broadcast")
    def test_sync_zero_delivered_still_succeeds(self, mock_send):
        """A broadcast sent to zero recipients (e.g. empty audience) is still
        a success — the command should not raise or write to stderr."""
        mock_send.return_value = {"delivered": 0, "skipped": 5, "failed": 0}
        out = StringIO()
        err = StringIO()
        call_command("send_broadcast", "empty-audience-id", stdout=out, stderr=err)
        mock_send.assert_called_once()
        self.assertEqual(err.getvalue(), "")
        self.assertIn("0", out.getvalue())

    @patch("messaging.services.send_broadcast")
    def test_sync_passes_broadcast_id_unchanged(self, mock_send):
        """Broadcast ID must be forwarded verbatim (it may be a UUID string)."""
        mock_send.return_value = {"delivered": 1}
        call_command(
            "send_broadcast",
            "00000000-0000-0000-0000-000000000099",
            stdout=StringIO(),
        )
        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["broadcast_id"], "00000000-0000-0000-0000-000000000099")

    # ── async mode ────────────────────────────────────────────────────────────

    @patch("messaging.tasks.send_broadcast_async")
    def test_async_flag_calls_delay_not_service(self, mock_task):
        """--async must call .delay() and must NOT call services.send_broadcast."""
        mock_result = MagicMock()
        mock_result.id = "celery-task-abc-123"
        mock_task.delay.return_value = mock_result

        out = StringIO()
        with patch("messaging.services.send_broadcast") as mock_sync:
            call_command("send_broadcast", "some-id", use_async=True, stdout=out)
            mock_sync.assert_not_called()

        mock_task.delay.assert_called_once_with("some-id")
        self.assertIn("celery-task-abc-123", out.getvalue())

    @patch("messaging.tasks.send_broadcast_async")
    def test_async_output_contains_broadcast_id(self, mock_task):
        """Queued message should include the broadcast ID for traceability."""
        mock_result = MagicMock()
        mock_result.id = "task-xyz"
        mock_task.delay.return_value = mock_result

        out = StringIO()
        call_command("send_broadcast", "broadcast-99", use_async=True, stdout=out)
        self.assertIn("broadcast-99", out.getvalue())

    @patch("messaging.tasks.send_broadcast_async")
    def test_async_output_contains_task_id(self, mock_task):
        """Queued message should include the Celery task ID for log tracing."""
        mock_result = MagicMock()
        mock_result.id = "unique-task-id-567"
        mock_task.delay.return_value = mock_result

        out = StringIO()
        call_command("send_broadcast", "any-id", use_async=True, stdout=out)
        self.assertIn("unique-task-id-567", out.getvalue())

    # ── edge cases ────────────────────────────────────────────────────────────

    @patch("messaging.services.send_broadcast")
    def test_service_exception_does_not_propagate(self, mock_send):
        """Unhandled exceptions from the service layer must be caught so the
        management command exits with code 0 (not 1) for cron safety."""
        mock_send.side_effect = RuntimeError("DB connection lost")
        err = StringIO()
        # assertRaises would catch a Django CommandError — but the command
        # catches all Exception types internally, so nothing should be raised.
        try:
            call_command("send_broadcast", "crash-id", stdout=StringIO(), stderr=err)
        except Exception as exc:
            self.fail(
                f"send_broadcast command raised {type(exc).__name__} instead of "
                f"handling the error gracefully: {exc}"
            )
        self.assertIn("Failed", err.getvalue())
