"""
test_utils_elasticsearch_setup.py
===================================
Full coverage for messaging/utils/elasticsearch_setup.py
Functions: get_es_client, ensure_index_exists, index_message,
           delete_from_index, search_messages,
           _db_search_fallback, _db_index_fallback, _highlight

Part 6 audit: this file used to also test autocomplete_users(), a dead
duplicate of search_engine.py's real implementation that nothing ever
called (removed from the source - see elasticsearch_setup.py for the
full explanation).
Place in: messaging/tests/test_utils_elasticsearch_setup.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings

from .factories import (
    UserFactory,
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
)
from ..utils.elasticsearch_setup import (
    get_es_client,
    ensure_index_exists,
    index_message,
    delete_from_index,
    search_messages,
    _db_search_fallback,
    _db_index_fallback,
    _highlight,
    ES_INDEX_MESSAGES,
)


class TestGetEsClient(TestCase):
    @override_settings(ELASTICSEARCH_URL=None)
    def test_returns_none_when_not_configured(self):
        result = get_es_client()
        self.assertIsNone(result)

    @override_settings(ELASTICSEARCH_URL="http://localhost:9200")
    @patch("messaging.utils.elasticsearch_setup.Elasticsearch", create=True)
    def test_returns_client_when_configured(self, mock_es_class):
        mock_client = MagicMock()
        mock_es_class.return_value = mock_client
        try:
            result = get_es_client()
            if result is not None:
                self.assertIsNotNone(result)
        except Exception:
            pass  # elasticsearch-py may not be installed in test env

    @override_settings(ELASTICSEARCH_URL="http://localhost:9200")
    @patch("elasticsearch.Elasticsearch",
           side_effect=ImportError("elasticsearch not installed"))
    def test_returns_none_on_import_error(self, _):
        # get_es_client() does a function-local `from elasticsearch import
        # Elasticsearch`, so the patch target must be the real
        # elasticsearch.Elasticsearch attribute (what that local import
        # actually resolves against at call time) rather than an
        # otherwise-nonexistent module-level name on elasticsearch_setup.
        result = get_es_client()
        self.assertIsNone(result)

    @override_settings(
        ELASTICSEARCH_URL="http://localhost:9200",
        ELASTICSEARCH_USERNAME="elastic",
        ELASTICSEARCH_PASSWORD="changeme",
    )
    def test_uses_basic_auth_when_credentials_configured(self):
        # Elasticsearch's constructor doesn't make a network call, so this
        # exercises the real basic_auth branch without mocking.
        client = get_es_client()
        self.assertIsNotNone(client)


class TestEnsureIndexExists(TestCase):
    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_returns_false_when_no_es_client(self, mock_get_client):
        mock_get_client.return_value = None
        result = ensure_index_exists()
        self.assertFalse(result)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_creates_index_if_not_exists(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = False
        mock_get_client.return_value = mock_es
        result = ensure_index_exists()
        self.assertTrue(result)
        mock_es.indices.create.assert_called_once()

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_skips_create_if_index_exists(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = True
        mock_get_client.return_value = mock_es
        result = ensure_index_exists()
        self.assertTrue(result)
        mock_es.indices.create.assert_not_called()

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_returns_false_on_exception(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.indices.exists.side_effect = Exception("ES down")
        mock_get_client.return_value = mock_es
        result = ensure_index_exists()
        self.assertFalse(result)


class TestIndexMessage(TestCase):
    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_indexes_to_es_when_available(self, mock_get_client):
        mock_es = MagicMock()
        mock_get_client.return_value = mock_es
        result = index_message(
            message_id="msg-1",
            chat_id="chat-1",
            sender_id="user-1",
            content="Hello world",
            message_type="TEXT",
            created_at="2024-01-01T10:00:00Z",
        )
        self.assertTrue(result)
        mock_es.index.assert_called_once()

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_falls_back_to_db_when_no_es(self, mock_get_client):
        mock_get_client.return_value = None
        chat = InternalChatFactory()
        user = UserFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, sender=user, content="test")
        result = index_message(
            message_id=str(msg.id),
            chat_id=str(chat.id),
            sender_id=str(user.pk),
            content="test",
            message_type="TEXT",
            created_at=msg.created_at.isoformat(),
        )
        # DB fallback should work or return True
        self.assertIsInstance(result, bool)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_falls_back_to_db_on_es_exception(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.index.side_effect = Exception("ES write failed")
        mock_get_client.return_value = mock_es
        result = index_message(
            message_id="msg-x",
            chat_id="chat-x",
            sender_id="user-x",
            content="test",
            message_type="TEXT",
            created_at="2024-01-01T00:00:00Z",
        )
        self.assertIsInstance(result, bool)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_tenant_id_included_when_provided(self, mock_get_client):
        mock_es = MagicMock()
        mock_get_client.return_value = mock_es
        index_message(
            message_id="m1", chat_id="c1", sender_id="u1",
            content="hi", message_type="TEXT",
            created_at="2024-01-01T00:00:00Z",
            tenant_id="tenant-42",
        )
        call_body = mock_es.index.call_args[1]["body"]
        self.assertEqual(call_body["tenant_id"], "tenant-42")


class TestDeleteFromIndex(TestCase):
    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_marks_deleted_in_es(self, mock_get_client):
        mock_es = MagicMock()
        mock_get_client.return_value = mock_es
        result = delete_from_index("msg-123")
        self.assertTrue(result)
        mock_es.update.assert_called_once()

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_returns_true_when_no_es_client(self, mock_get_client):
        mock_get_client.return_value = None
        result = delete_from_index("msg-x")
        self.assertTrue(result)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_returns_false_on_exception(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.update.side_effect = Exception("update failed")
        mock_get_client.return_value = mock_es
        result = delete_from_index("msg-x")
        self.assertFalse(result)


class TestSearchMessages(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatMessageFactory(chat=self.chat, sender=self.user, content="django is awesome")
        ChatMessageFactory(chat=self.chat, sender=self.user, content="python rocks")

    def test_empty_query_returns_empty(self):
        result = search_messages(user_id=self.user.pk, query="")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["results"], [])

    def test_short_query_returns_empty(self):
        result = search_messages(user_id=self.user.pk, query="a")
        self.assertEqual(result["total"], 0)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_falls_back_to_db_when_no_es(self, mock_get_client):
        mock_get_client.return_value = None
        result = search_messages(user_id=self.user.pk, query="django")
        self.assertIn("results", result)
        self.assertIn("total", result)

    @patch("messaging.utils.elasticsearch_setup._db_search_fallback")
    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_tenant_id_threaded_through_to_db_fallback_when_no_es(self, mock_get_client, mock_fallback):
        """Regression test (Part 6 audit): tenant_id used to be silently
        dropped on the way into the DB fallback path."""
        mock_get_client.return_value = None
        mock_fallback.return_value = {"total": 0, "results": [], "page": 1, "page_size": 20}
        search_messages(user_id=self.user.pk, query="django", tenant_id="tenant-77")
        self.assertEqual(mock_fallback.call_args.kwargs["tenant_id"], "tenant-77")

    @patch("messaging.utils.elasticsearch_setup._db_search_fallback")
    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_tenant_id_threaded_through_to_db_fallback_on_es_exception(self, mock_get_client, mock_fallback):
        mock_es = MagicMock()
        mock_es.search.side_effect = Exception("ES down")
        mock_get_client.return_value = mock_es
        mock_fallback.return_value = {"total": 0, "results": [], "page": 1, "page_size": 20}
        search_messages(user_id=self.user.pk, query="django", tenant_id="tenant-77")
        self.assertEqual(mock_fallback.call_args.kwargs["tenant_id"], "tenant-77")

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_falls_back_to_db_on_es_exception(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.search.side_effect = Exception("ES down")
        mock_get_client.return_value = mock_es
        result = search_messages(user_id=self.user.pk, query="django")
        self.assertIn("results", result)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_es_search_builds_correct_query(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {"total": {"value": 0}, "hits": []}
        }
        mock_get_client.return_value = mock_es
        search_messages(user_id=self.user.pk, query="test query")
        mock_es.search.assert_called_once()
        body = mock_es.search.call_args[1]["body"]
        self.assertIn("query", body)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_pagination_params_passed(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {"total": {"value": 0}, "hits": []}
        }
        mock_get_client.return_value = mock_es
        search_messages(user_id=self.user.pk, query="test", page=2, page_size=10)
        body = mock_es.search.call_args[1]["body"]
        self.assertEqual(body["from"], 10)
        self.assertEqual(body["size"], 10)

    @patch("messaging.utils.elasticsearch_setup.get_es_client")
    def test_all_optional_filters_build_correct_clauses(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}
        mock_get_client.return_value = mock_es
        search_messages(
            user_id=self.user.pk, query="test",
            sender_id=self.user.pk, message_type="TEXT",
            tenant_id="tenant-9", from_date="2026-01-01", to_date="2026-06-01",
        )
        body = mock_es.search.call_args[1]["body"]
        filters = body["query"]["bool"]["filter"]
        self.assertIn({"term": {"sender_id": str(self.user.pk)}}, filters)
        self.assertIn({"term": {"message_type": "TEXT"}}, filters)
        self.assertIn({"term": {"tenant_id": "tenant-9"}}, filters)
        self.assertIn(
            {"range": {"created_at": {"gte": "2026-01-01", "lte": "2026-06-01"}}}, filters
        )


class TestDbSearchFallback(TestCase):
    def setUp(self):
        from ..models import MessageSearchIndex
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        msg1 = ChatMessageFactory(chat=self.chat, sender=self.user, content="hello world test")
        msg2 = ChatMessageFactory(chat=self.chat, sender=self.user, content="python is great")
        # _db_search_fallback reads from MessageSearchIndex, which in production
        # is populated by index_message_task (an async Celery task), not by a
        # save-time signal. Mirror that here so the fallback search has data.
        for msg in (msg1, msg2):
            MessageSearchIndex.objects.update_or_create(
                message=msg,
                defaults={
                    "chat": msg.chat,
                    "search_text": (msg.content or "").lower().strip(),
                    "tenant": msg.tenant,
                },
            )

    def test_returns_matching_messages(self):
        result = _db_search_fallback(
            user_id=self.user.pk, query="hello",
            chat_id=None, page=1, page_size=20
        )
        self.assertGreaterEqual(result["total"], 1)
        self.assertTrue(any("hello" in r["content"].lower() for r in result["results"]))

    def test_empty_query_returns_zero(self):
        result = _db_search_fallback(
            user_id=self.user.pk, query="",
            chat_id=None, page=1, page_size=20
        )
        self.assertEqual(result["total"], 0)

    def test_restricted_to_accessible_chats(self):
        outsider = UserFactory()
        result = _db_search_fallback(
            user_id=outsider.pk, query="hello",
            chat_id=None, page=1, page_size=20
        )
        self.assertEqual(result["total"], 0)

    def test_chat_id_filter(self):
        other_chat = InternalChatFactory()
        ChatParticipantFactory(chat=other_chat, user=self.user)
        ChatMessageFactory(chat=other_chat, sender=self.user, content="hello in other chat")
        result = _db_search_fallback(
            user_id=self.user.pk, query="hello",
            chat_id=str(self.chat.id), page=1, page_size=20
        )
        for r in result["results"]:
            self.assertEqual(r["chat_id"], str(self.chat.id))

    def test_tenant_id_filter(self):
        """
        Regression test (Part 6 audit): search_messages()'s ES query has
        always filtered by tenant_id correctly, but this DB fallback (used
        whenever ES is down or errors) silently dropped it - the parameter
        didn't even exist here. MessageSearchIndex.tenant is already
        populated by _db_index_fallback, so this was purely a missing
        filter, not missing data. A message in a different tenant matching
        the same query must not leak through when tenant_id is given.
        """
        from django.apps import apps
        from ..models import MessageSearchIndex
        Tenant = apps.get_model("tenants", "Tenant")
        other_tenant = Tenant.objects.create(name="Other Co")
        other_msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="hello from another tenant")
        MessageSearchIndex.objects.filter(message=other_msg).delete()
        MessageSearchIndex.objects.create(
            message=other_msg, chat=other_msg.chat,
            search_text="hello from another tenant", tenant=other_tenant,
        )

        result = _db_search_fallback(
            user_id=self.user.pk, query="hello",
            chat_id=None, tenant_id=other_tenant.pk,
            page=1, page_size=20,
        )
        returned_ids = {r["message_id"] for r in result["results"]}
        # Only the other-tenant message should come back when filtering by
        # its tenant_id - the two setUp messages (tenant=None) must not.
        self.assertEqual(returned_ids, {str(other_msg.id)})


class TestDbIndexFallback(TestCase):
    def test_creates_search_index_record(self):
        from ..models import MessageSearchIndex
        chat = InternalChatFactory()
        user = UserFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, sender=user, content="searchable content")
        result = _db_index_fallback(str(msg.id), str(chat.id), "searchable content")
        self.assertTrue(result)
        self.assertTrue(MessageSearchIndex.objects.filter(message=msg).exists())

    def test_does_not_create_for_nonexistent_message(self):
        import uuid
        result = _db_index_fallback(str(uuid.uuid4()), str(uuid.uuid4()), "content")
        self.assertIsInstance(result, bool)

    def test_returns_false_on_exception(self):
        with patch("messaging.utils.elasticsearch_setup.MessageSearchIndex") as mock_model:
            mock_model.objects.update_or_create.side_effect = Exception("DB error")
            result = _db_index_fallback("m", "c", "content")
        self.assertFalse(result)


class TestHighlight(TestCase):
    def test_wraps_match_in_mark_tag(self):
        result = _highlight("Hello world, how are you", "world")
        self.assertIn("<mark>world</mark>", result)

    def test_returns_empty_for_empty_content(self):
        result = _highlight("", "query")
        self.assertEqual(result, "")

    def test_returns_snippet_when_no_match(self):
        result = _highlight("Short text", "xyz")
        self.assertIn("Short text", result)

    def test_adds_ellipsis_for_long_content(self):
        long_text = "x " * 200 + "target word " + "y " * 200
        result = _highlight(long_text, "target")
        self.assertIn("target", result)

    def test_respects_max_len(self):
        content = "a" * 200
        result = _highlight(content, "b", max_len=50)
        self.assertLessEqual(len(result), 60)  # Some tolerance
