"""
test_management_commands_audit_fixes.py
=========================================
management/commands/ audit round - regression tests for the confirmed
bugs found and fixed:

  1. cleanup_chats.py hard-deleted InternalChat rows (cascading to
     ChatMessage/MessageSearchIndex at the DB level) but never removed
     the corresponding documents from real Elasticsearch.
     delete_from_index_task existed but was never called from anywhere
     in the codebase (confirmed via full-codebase grep before this fix)
     - deleted messages stayed permanently searchable in ES.

  2. export_data_gdpr.py declared "reactions" / "blocked_users" /
     "device_tokens" keys in its output dict but never queried any of
     the three models to populate them - every GDPR Article 20 export
     silently omitted all three categories, every time.

  3. bulk_reindex_task (used by bulk_index_messages.py and by
     setup_messaging_index.py --bulk-index) and sync_search_index.py
     both called utils.search_engine.index_message() directly, which
     only writes to real Elasticsearch. Neither ever updated the
     MessageSearchIndex DB mirror table, which MessageSearchIndexViewSet
     depends on for its admin "browse index" endpoint - including that
     same viewset's own "rebuild" action, which calls bulk_reindex_task.

  4. cleanup_messaging.py's --days had no validation (unlike its sibling
     cleanup_chats.py) and no feedback when no cleanup flag was passed.
"""
from __future__ import annotations
import json
import os
import tempfile
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .factories import (
    UserFactory, InternalChatFactory, ChatMessageFactory,
    MessageReactionFactory, DeviceTokenFactory, SupportThreadFactory,
    SupportMessageFactory, UserInboxFactory, CallSessionFactory,
    UserStoryFactory,
)
from ..models import InternalChat, ChatMessage, MessageSearchIndex, UserBlock, CPANotification
from ..choices import ChatStatus


# ─────────────────────────────────────────────────────────────────────────
# Bug 1: cleanup_chats.py never deindexed hard-deleted messages from ES
# ─────────────────────────────────────────────────────────────────────────

class TestCleanupChatsDeindexesFromSearch(TestCase):

    def _make_doomed_chat(self, n_messages=2):
        chat = InternalChatFactory(status=ChatStatus.DELETED)
        InternalChat.objects.filter(pk=chat.pk).update(
            updated_at=timezone.now() - timedelta(days=60)
        )
        messages = [ChatMessageFactory(chat=chat) for _ in range(n_messages)]
        return chat, messages

    def test_delete_from_index_called_per_message_with_real_es_client(self):
        """
        Confirms the actual bug end-to-end: before this fix, nothing in
        the codebase ever called delete_from_index/delete_from_index_task,
        so cascading a hard chat-delete left every message permanently
        orphaned and searchable in real ES. Only get_es_client (the
        network boundary) is patched, so delete_from_index's real logic
        runs for real against a fake client - same convention already
        used in test_utils_search_engine_coverage_boost.py.
        """
        chat, messages = self._make_doomed_chat(n_messages=3)
        expected_ids = {str(m.id) for m in messages}

        fake_es = MagicMock()
        with patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=fake_es):
            out = StringIO()
            call_command("cleanup_chats", days=30, inbox_days=90, stdout=out)

        # DB side: chat and its messages are actually gone.
        self.assertFalse(InternalChat.objects.filter(pk=chat.pk).exists())
        self.assertEqual(ChatMessage.objects.filter(chat_id=chat.pk).count(), 0)

        # ES side: elasticsearch_setup.delete_from_index's real
        # implementation calls es.update(index=..., id=<message_id>,
        # body={"doc": {"is_deleted": True, ...}}) - assert it fired for
        # every message that was about to be destroyed.
        self.assertEqual(fake_es.update.call_count, 3)
        called_ids = {c.kwargs["id"] for c in fake_es.update.call_args_list}
        self.assertEqual(called_ids, expected_ids)
        for c in fake_es.update.call_args_list:
            self.assertTrue(c.kwargs["body"]["doc"]["is_deleted"])

        self.assertIn("Deindexed 3 messages", out.getvalue())

    def test_succeeds_and_reports_deindex_count_when_es_not_configured(self):
        """
        In this harness ELASTICSEARCH_URL isn't set, so get_es_client()
        returns None and delete_from_index() no-ops (returns True)
        rather than raising - the command must still report clean
        success, not crash, in the common no-ES-configured environment.
        """
        chat, messages = self._make_doomed_chat(n_messages=2)
        out = StringIO()
        call_command("cleanup_chats", days=30, inbox_days=90, stdout=out)
        self.assertFalse(InternalChat.objects.filter(pk=chat.pk).exists())
        self.assertIn("Deindexed 2 messages", out.getvalue())
        self.assertNotIn("errors", out.getvalue())

    def test_no_deindex_attempted_for_chats_outside_the_window(self):
        """A chat not old enough to be deleted must not have its
        (still-alive) messages touched at all."""
        fresh_chat = InternalChatFactory(status=ChatStatus.DELETED)  # updated_at = now
        ChatMessageFactory(chat=fresh_chat)

        fake_es = MagicMock()
        with patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=fake_es):
            call_command("cleanup_chats", days=30, inbox_days=90, stdout=StringIO())

        self.assertTrue(InternalChat.objects.filter(pk=fresh_chat.pk).exists())
        fake_es.update.assert_not_called()

    def test_dry_run_does_not_touch_es_or_delete_anything(self):
        chat, messages = self._make_doomed_chat(n_messages=2)
        fake_es = MagicMock()
        with patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=fake_es):
            call_command("cleanup_chats", days=30, inbox_days=90, dry_run=True, stdout=StringIO())
        fake_es.update.assert_not_called()
        self.assertTrue(InternalChat.objects.filter(pk=chat.pk).exists())

    def test_one_bad_message_id_does_not_abort_the_whole_batch(self):
        """A single ES error for one message must not stop the others
        from being deindexed, and must not fail the command."""
        chat, messages = self._make_doomed_chat(n_messages=3)
        bad_id = str(messages[0].id)

        fake_es = MagicMock()

        def flaky_update(index, id, body):
            if id == bad_id:
                raise ConnectionError("ES temporarily unreachable")
            return {"result": "updated"}

        fake_es.update.side_effect = flaky_update

        with patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=fake_es):
            out = StringIO()
            call_command("cleanup_chats", days=30, inbox_days=90, stdout=out)

        self.assertEqual(fake_es.update.call_count, 3)
        self.assertIn("Deindexed 2 messages", out.getvalue())
        self.assertIn("1 deindex errors", out.getvalue())
        # DB cleanup itself must still have fully succeeded regardless.
        self.assertFalse(InternalChat.objects.filter(pk=chat.pk).exists())

    def test_deindex_survives_delete_from_index_itself_raising(self):
        """
        delete_from_index() normally catches its own exceptions and
        returns False (covered above). This covers the defensive except
        around the call in cleanup_chats.py itself, for the case where
        delete_from_index raises directly rather than returning False.
        """
        chat, messages = self._make_doomed_chat(n_messages=2)
        with patch(
            "messaging.utils.search_engine.delete_from_index",
            side_effect=RuntimeError("unexpected"),
        ):
            out = StringIO()
            call_command("cleanup_chats", days=30, inbox_days=90, stdout=out)

        self.assertFalse(InternalChat.objects.filter(pk=chat.pk).exists())
        self.assertIn("Deindexed 0 messages", out.getvalue())
        self.assertIn("2 deindex errors", out.getvalue())


# ─────────────────────────────────────────────────────────────────────────
# Bug 2: export_data_gdpr.py declared but never populated 3 categories
# ─────────────────────────────────────────────────────────────────────────

class TestGdprExportPopulatesAllDeclaredCategories(TestCase):

    def test_reactions_blocked_users_and_device_tokens_are_populated(self):
        user = UserFactory()
        other_user = UserFactory()
        message = ChatMessageFactory()
        MessageReactionFactory(user=user, message=message, emoji="🔥")
        UserBlock.objects.create(blocker=user, blocked=other_user, reason="spam")
        DeviceTokenFactory(user=user, platform="ios", token="tok-abc-123")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "export.json")
            call_command(
                "export_data_gdpr", user_id=user.pk, output=out_path,
                stdout=StringIO(), stderr=StringIO(),
            )
            with open(out_path) as f:
                data = json.load(f)

        self.assertEqual(len(data["reactions"]), 1)
        self.assertEqual(data["reactions"][0]["message_id"], str(message.id))
        self.assertEqual(data["reactions"][0]["chat_id"], str(message.chat_id))
        self.assertEqual(data["reactions"][0]["emoji"], "🔥")

        self.assertEqual(len(data["blocked_users"]), 1)
        self.assertEqual(data["blocked_users"][0]["blocked_user_id"], str(other_user.pk))
        self.assertEqual(data["blocked_users"][0]["blocked_username"], other_user.username)
        self.assertEqual(data["blocked_users"][0]["reason"], "spam")

        self.assertEqual(len(data["device_tokens"]), 1)
        self.assertEqual(data["device_tokens"][0]["token"], "tok-abc-123")
        self.assertEqual(data["device_tokens"][0]["platform"], "ios")
        self.assertTrue(data["device_tokens"][0]["is_active"])

    def test_does_not_leak_other_users_reactions_blocks_or_tokens(self):
        """Scoping check - the entire point of a GDPR export is per-user
        isolation, so a bug here would be worse than the data just being
        empty."""
        user = UserFactory()
        stranger = UserFactory()
        another = UserFactory()

        MessageReactionFactory(user=stranger)
        UserBlock.objects.create(blocker=stranger, blocked=another, reason="x")
        DeviceTokenFactory(user=stranger)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "export.json")
            call_command(
                "export_data_gdpr", user_id=user.pk, output=out_path,
                stdout=StringIO(), stderr=StringIO(),
            )
            with open(out_path) as f:
                data = json.load(f)

        self.assertEqual(data["reactions"], [])
        self.assertEqual(data["blocked_users"], [])
        self.assertEqual(data["device_tokens"], [])

    def test_blocked_by_others_is_not_conflated_with_blocked_users(self):
        """UserBlock.blocker's related_name is literally "blocked_users" -
        confirm the export reports users THIS account blocked, not users
        who blocked this account."""
        user = UserFactory()
        someone_else = UserFactory()
        UserBlock.objects.create(blocker=someone_else, blocked=user, reason="unrelated")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "export.json")
            call_command(
                "export_data_gdpr", user_id=user.pk, output=out_path,
                stdout=StringIO(), stderr=StringIO(),
            )
            with open(out_path) as f:
                data = json.load(f)

        self.assertEqual(data["blocked_users"], [])

    def test_support_threads_inbox_cpa_stories_and_calls_are_populated(self):
        """
        These five categories were structurally declared and (unlike
        reactions/blocked_users/device_tokens) DID have working query
        loops already - but no existing test ever created real data for
        any of them, so a regression here (e.g. a wrong field name)
        could have silently slipped through the same way the other
        three did. Exercising all five with real data at once.
        """
        user = UserFactory()

        thread = SupportThreadFactory(user=user, subject="Payout question")
        SupportMessageFactory(thread=thread, content="When will I get paid?", is_agent_reply=False)
        SupportMessageFactory(thread=thread, content="Next Friday.", is_agent_reply=True)

        UserInboxFactory(user=user, item_type="SYSTEM", title="Welcome!")

        notif = CPANotification.objects.create(
            recipient=user, notification_type="OFFER_APPROVED",
            title="Offer approved", body="Your offer was approved.",
        )

        UserStoryFactory(user=user, story_type="text", content="My story content")

        call = CallSessionFactory(call_type="VIDEO", status="ENDED", duration_seconds=42)
        call.participants.add(user)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "export.json")
            call_command(
                "export_data_gdpr", user_id=user.pk, output=out_path,
                stdout=StringIO(), stderr=StringIO(),
            )
            with open(out_path) as f:
                data = json.load(f)

        self.assertEqual(len(data["support_threads"]), 1)
        self.assertEqual(data["support_threads"][0]["subject"], "Payout question")
        self.assertEqual(len(data["support_threads"][0]["messages"]), 2)
        self.assertEqual(data["support_threads"][0]["messages"][0]["content"], "When will I get paid?")
        self.assertFalse(data["support_threads"][0]["messages"][0]["is_agent"])
        self.assertTrue(data["support_threads"][0]["messages"][1]["is_agent"])

        self.assertEqual(len(data["inbox_items"]), 1)
        self.assertEqual(data["inbox_items"][0]["title"], "Welcome!")

        self.assertEqual(len(data["cpa_notifications"]), 1)
        self.assertEqual(data["cpa_notifications"][0]["id"], str(notif.id))
        self.assertEqual(data["cpa_notifications"][0]["type"], "OFFER_APPROVED")

        self.assertEqual(len(data["stories"]), 1)
        self.assertEqual(data["stories"][0]["content"], "My story content")

        self.assertEqual(len(data["call_history"]), 1)
        self.assertEqual(data["call_history"][0]["call_id"], str(call.id))
        self.assertEqual(data["call_history"][0]["duration_seconds"], 42)


# ─────────────────────────────────────────────────────────────────────────
# Bug 3: bulk_reindex_task / sync_search_index never updated the
# MessageSearchIndex DB mirror table.
# ─────────────────────────────────────────────────────────────────────────

class TestBulkIndexMessagesSyncsDbMirror(TestCase):
    """bulk_index_messages.py (sync mode) -> tasks.bulk_reindex_task."""

    def test_bulk_reindex_creates_message_search_index_rows(self):
        msg1 = ChatMessageFactory(content="Hello World")
        msg2 = ChatMessageFactory(content="  Second Message  ")

        fake_es = MagicMock()
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_es):
            call_command("bulk_index_messages", stdout=StringIO())

        row1 = MessageSearchIndex.objects.get(message=msg1)
        self.assertEqual(row1.chat_id, msg1.chat_id)
        self.assertEqual(row1.search_text, "hello world")
        self.assertEqual(row1.tenant_id, msg1.tenant_id)

        row2 = MessageSearchIndex.objects.get(message=msg2)
        self.assertEqual(row2.search_text, "second message")

    def test_rerunning_bulk_reindex_upserts_not_duplicates(self):
        """MessageSearchIndex.message is a OneToOneField - re-running
        must update the existing row, never raise IntegrityError."""
        ChatMessageFactory(content="original")
        fake_es = MagicMock()
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_es):
            call_command("bulk_index_messages", stdout=StringIO())
            self.assertEqual(MessageSearchIndex.objects.count(), 1)
            call_command("bulk_index_messages", stdout=StringIO())
        self.assertEqual(MessageSearchIndex.objects.count(), 1)


class TestSetupMessagingIndexBulkFlagSyncsDbMirror(TestCase):
    """setup_messaging_index.py --bulk-index also goes through
    bulk_reindex_task and must get the same fix."""

    def test_bulk_index_flag_creates_message_search_index_rows(self):
        msg = ChatMessageFactory(content="via setup command")
        fake_es = MagicMock()
        fake_es.ping.return_value = True
        fake_es.indices.exists.return_value = True
        # Both copies of get_es_client need patching: the command's own
        # top-level call (search_engine) and ensure_index_exists()'s
        # internal delegation to elasticsearch_setup's separate copy.
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_es), \
             patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=fake_es):
            call_command("setup_messaging_index", bulk_index=True, stdout=StringIO())
        self.assertTrue(MessageSearchIndex.objects.filter(message=msg).exists())


class TestSyncSearchIndexSyncsDbMirror(TestCase):
    """The sync_search_index management command directly."""

    def test_sync_creates_message_search_index_rows(self):
        msg = ChatMessageFactory(content="Find Me Please")
        fake_es = MagicMock()
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_es):
            call_command("sync_search_index", days=7, stdout=StringIO())

        row = MessageSearchIndex.objects.get(message=msg)
        self.assertEqual(row.search_text, "find me please")
        self.assertEqual(row.chat_id, msg.chat_id)

    def test_aborts_cleanly_when_es_not_configured(self):
        """This harness has no ELASTICSEARCH_URL set, so get_es_client()
        returns None by default - the command must abort with a clear
        message and touch no data, not crash."""
        ChatMessageFactory(content="should not be indexed")
        out, err = StringIO(), StringIO()
        call_command("sync_search_index", days=7, stdout=out, stderr=err)
        self.assertIn("not configured", err.getvalue())
        self.assertEqual(MessageSearchIndex.objects.count(), 0)


# ─────────────────────────────────────────────────────────────────────────
# Bonus fix found while testing the above: search_engine.get_es_client()
# defaulted es_url to "http://localhost:9200" when ELASTICSEARCH_URL
# wasn't set, unlike its elasticsearch_setup.py sibling (which correctly
# returns None). Concretely: views.py's /health endpoint calls this
# directly and does es.ping() on the result, so in any environment where
# ES simply isn't configured, every health check attempted a real,
# retrying network connection (observed ~14s of exponential backoff in
# this sandbox) instead of reporting "not configured" immediately.
# ─────────────────────────────────────────────────────────────────────────

class TestHealthCheckReportsUnconfiguredEsQuickly(TestCase):

    def test_get_es_client_returns_immediately_without_a_connection_attempt(self):
        """The unit-level guarantee: no network I/O at all when
        ELASTICSEARCH_URL isn't set."""
        import time
        from api.messaging.utils.search_engine import get_es_client

        started = time.monotonic()
        client = get_es_client()
        elapsed = time.monotonic() - started

        self.assertIsNone(client)
        self.assertLess(elapsed, 0.5)  # no retrying connection attempt

    def test_health_check_reports_es_not_configured(self):
        """
        End-to-end confirmation that the /health endpoint surfaces the
        fixed behavior. Deliberately doesn't assert on total response
        time - this endpoint's Celery check (current_app.control.
        inspect().active()) does its own real broker round-trip and is
        independently slow when no broker is reachable; that's a
        separate, unrelated finding outside this audit's scope, not
        something to conflate with the ES fix here.
        """
        from rest_framework.test import APIClient

        response = APIClient().get("/messaging/health/")
        self.assertIn(response.status_code, (200, 207))
        self.assertEqual(response.data["checks"]["elasticsearch"], "not configured")


class TestUpsertSearchIndexRowUnit(TestCase):
    """Direct unit tests of the new shared helper."""

    def test_upsert_creates_row_with_expected_fields(self):
        from ..utils.search_engine import upsert_search_index_row
        msg = ChatMessageFactory(content="  MiXeD Case Text  ")
        upsert_search_index_row(msg)
        row = MessageSearchIndex.objects.get(message=msg)
        self.assertEqual(row.search_text, "mixed case text")
        self.assertEqual(row.chat_id, msg.chat_id)
        self.assertEqual(row.tenant_id, msg.tenant_id)

    def test_upsert_is_an_idempotent_update(self):
        from ..utils.search_engine import upsert_search_index_row
        msg = ChatMessageFactory(content="first version")
        upsert_search_index_row(msg)
        msg.content = "second version"
        msg.save(update_fields=["content"])
        upsert_search_index_row(msg)
        self.assertEqual(MessageSearchIndex.objects.filter(message=msg).count(), 1)
        self.assertEqual(
            MessageSearchIndex.objects.get(message=msg).search_text, "second version"
        )

    def test_query_count_unaffected_by_only_restricted_fetch(self):
        """
        The point of using msg.chat_id/msg.tenant_id instead of msg.chat/
        msg.tenant is that the query cost must be identical whether or
        not the caller preloaded those relations. sync_search_index.py's
        queryset uses .only(...) without select_related("chat") - if
        upsert_search_index_row ever regresses back to msg.chat/
        msg.tenant, the .only()-fetched variant costs 2 extra queries
        (one lazy SELECT per relation) and this test catches it.
        """
        from ..utils.search_engine import upsert_search_index_row

        full = ChatMessageFactory(content="full fetch")
        with CaptureQueriesContext(connection) as ctx_full:
            upsert_search_index_row(full)
        full_count = len(ctx_full.captured_queries)

        lean_source = ChatMessageFactory(content="lean fetch")
        lean = ChatMessage.objects.only(
            "id", "chat_id", "sender_id", "content", "message_type", "created_at", "tenant_id"
        ).get(pk=lean_source.pk)
        with CaptureQueriesContext(connection) as ctx_lean:
            upsert_search_index_row(lean)
        lean_count = len(ctx_lean.captured_queries)

        self.assertEqual(
            full_count, lean_count,
            f"upsert_search_index_row cost {lean_count} queries on a .only()-restricted "
            f"instance vs {full_count} on a fully-loaded one - it is touching msg.chat/"
            f"msg.tenant (lazy relations) instead of msg.chat_id/msg.tenant_id.",
        )


# ─────────────────────────────────────────────────────────────────────────
# Bug 4: cleanup_messaging.py --days validation + no-op feedback
# ─────────────────────────────────────────────────────────────────────────

class TestCleanupMessagingDaysValidationAndNoop(TestCase):

    def test_zero_days_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("cleanup_messaging", inbox=True, days=0, stdout=StringIO())

    def test_negative_days_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("cleanup_messaging", inbox=True, days=-5, stdout=StringIO())

    def test_no_flags_warns_instead_of_silently_doing_nothing(self):
        out = StringIO()
        call_command("cleanup_messaging", stdout=out)
        self.assertIn("No cleanup type selected", out.getvalue())

    @patch("messaging.tasks.cleanup_old_inbox_items")
    def test_valid_days_still_reaches_the_task(self, mock_task):
        mock_task.return_value = {"deleted": 1}
        out = StringIO()
        call_command("cleanup_messaging", inbox=True, days=15, stdout=out)
        mock_task.assert_called_once_with(days=15)
        self.assertNotIn("No cleanup type selected", out.getvalue())
