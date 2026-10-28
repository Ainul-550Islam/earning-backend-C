"""
test_utils_search_engine_coverage_boost.py
=============================================
Real-execution coverage for messaging/utils/search_engine.py.

No dedicated test file existed for this module before. Per the session
handoff: MessageSearchViewSet actually calls services.search_messages (a
different function), while THIS module's search_messages backs
views.py's MessageSearchView directly and is the one with the real
Elasticsearch-or-DB-fallback logic.

The 'elasticsearch' package is installed but no ES server is running in
this sandbox, so real es.search()/es.index() calls naturally raise a
connection error - that's used directly to exercise the "ES call failed,
fall back to DB" branch without any mocking. get_es_client() returning
None (package not installed at all) is a separate branch, covered via a
selective import patch. The ES "happy path" (a successful response) is
covered by mocking only the client's .search()/.index() methods - not
the module's own query-building/response-parsing logic - to a realistic
ES response shape.

OBSERVATION (not fixed): autocomplete_users() accepts a tenant_id
parameter but never applies it to the queryset. In this standalone test
environment AUTH_USER_MODEL is plain auth.User with no tenant concept,
so this can't be confirmed as a live cross-tenant leak from here - but
it's worth checking against the real earning_backend User model/manager,
since as written this function does not scope by tenant on its own.
"""
from __future__ import annotations

import builtins
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from api.messaging.utils import search_engine as se
from api.messaging.tests.factories import (
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@contextmanager
def _no_elasticsearch():
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "elasticsearch" or name.startswith("elasticsearch."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        yield


# ---------------------------------------------------------------------------
# get_es_client
# ---------------------------------------------------------------------------

class TestGetEsClient:
    @override_settings(ELASTICSEARCH_URL="http://es.example.com:9200")
    def test_returns_client_without_auth(self):
        client = se.get_es_client()
        assert client is not None

    @override_settings(
        ELASTICSEARCH_URL="http://es.example.com:9200",
        ELASTICSEARCH_USERNAME="es-user", ELASTICSEARCH_PASSWORD="es-pass",
    )
    def test_returns_client_with_basic_auth(self):
        client = se.get_es_client()
        assert client is not None

    def test_import_error_returns_none(self):
        with _no_elasticsearch():
            assert se.get_es_client() is None

    def test_unconfigured_url_returns_none_without_attempting_a_connection(self):
        """
        Part 6 audit fix: get_es_client() used to default es_url to
        "http://localhost:9200" when ELASTICSEARCH_URL wasn't set at
        all, so this case previously returned a real (but doomed)
        client instead of None - meaning every caller (views.py's
        /health check, index_message(), search_messages()) paid for a
        real, retrying network connection attempt instead of detecting
        "not configured" immediately. This harness never sets
        ELASTICSEARCH_URL, so no override_settings needed here.
        """
        assert se.get_es_client() is None


# ---------------------------------------------------------------------------
# index_message
# ---------------------------------------------------------------------------

class TestIndexMessage:
    def test_returns_false_when_es_unavailable(self):
        with _no_elasticsearch():
            result = se.index_message(
                message_id="m1", chat_id="c1", sender_id="u1",
                content="hi", message_type="TEXT", created_at="2026-01-01T00:00:00Z",
            )
        assert result is False

    def test_returns_true_on_successful_index(self):
        fake_client = MagicMock()
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            result = se.index_message(
                message_id="m1", chat_id="c1", sender_id="u1",
                content="hi", message_type="TEXT", created_at="2026-01-01T00:00:00Z",
                tenant_id="t1",
            )
        assert result is True
        fake_client.index.assert_called_once()
        doc = fake_client.index.call_args.kwargs["document"]
        assert doc["tenant_id"] == "t1"

    def test_tenant_id_none_when_not_provided(self):
        fake_client = MagicMock()
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            se.index_message(
                message_id="m1", chat_id="c1", sender_id="u1",
                content="hi", message_type="TEXT", created_at="2026-01-01T00:00:00Z",
            )
        doc = fake_client.index.call_args.kwargs["document"]
        assert doc["tenant_id"] is None

    def test_returns_false_when_index_call_raises(self):
        fake_client = MagicMock()
        fake_client.index.side_effect = RuntimeError("ES down")
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            result = se.index_message(
                message_id="m1", chat_id="c1", sender_id="u1",
                content="hi", message_type="TEXT", created_at="2026-01-01T00:00:00Z",
            )
        assert result is False


# ---------------------------------------------------------------------------
# search_messages - ES unavailable -> DB fallback
# ---------------------------------------------------------------------------

class TestSearchMessagesFallsBackToDb:
    def test_falls_back_when_es_client_unavailable(self):
        user = UserFactory()
        with _no_elasticsearch():
            result = se.search_messages(user_id=user.pk, query="hello")
        assert result["results"] == []
        assert result["total"] == 0

    def test_falls_back_when_real_es_call_fails(self):
        # No ES server is running in this sandbox, so a real client's
        # .search() call fails with a genuine connection error - this
        # exercises the except-branch fallback without any mocking.
        user = UserFactory()
        result = se.search_messages(user_id=user.pk, query="hello")
        assert "results" in result
        assert result["query"] == "hello"

    def test_tenant_id_threaded_through_when_es_unavailable(self):
        """Regression test (Part 6 audit): tenant_id used to be silently
        dropped on the way into the DB fallback path."""
        user = UserFactory()
        with _no_elasticsearch(), patch.object(se, "_db_search_fallback") as mock_fallback:
            mock_fallback.return_value = {"results": [], "total": 0, "page": 1, "page_size": 20, "pages": 0, "query": "hello"}
            se.search_messages(user_id=user.pk, query="hello", tenant_id="tenant-99")
        assert mock_fallback.call_args.kwargs["tenant_id"] == "tenant-99"


# ---------------------------------------------------------------------------
# search_messages - ES happy path (client itself mocked, not the module's
# own query-building / response-parsing logic)
# ---------------------------------------------------------------------------

class TestSearchMessagesEsHappyPath:
    def _fake_es_response(self, hits):
        return {
            "hits": {
                "hits": hits,
                "total": {"value": len(hits)},
            }
        }

    def test_successful_search_returns_parsed_results(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, content="hello world")

        fake_client = MagicMock()
        fake_client.search.return_value = self._fake_es_response([
            {
                "_source": {"message_id": str(msg.id), "chat_id": str(chat.pk)},
                "_score": 1.23,
                "highlight": {"content": ["<mark>hello</mark> world"]},
            }
        ])

        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            result = se.search_messages(user_id=user.pk, query="hello")

        assert result["total"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["message_id"] == str(msg.id)
        assert result["results"][0]["highlight"] == ["<mark>hello</mark> world"]

    def test_hit_with_no_matching_db_row_is_skipped(self):
        user = UserFactory()
        fake_client = MagicMock()
        fake_client.search.return_value = self._fake_es_response([
            {"_source": {"message_id": "00000000-0000-0000-0000-000000000000", "chat_id": "x"}, "_score": 1.0}
        ])
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            result = se.search_messages(user_id=user.pk, query="hello")
        assert result["results"] == []
        assert result["total"] == 1  # total reflects ES, results reflects DB join

    def test_applies_chat_id_sender_type_and_date_filters(self):
        user = UserFactory()
        sender = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        fake_client = MagicMock()
        fake_client.search.return_value = self._fake_es_response([])

        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            se.search_messages(
                user_id=user.pk,
                query="hello",
                chat_id=str(chat.pk),
                sender_id=str(sender.pk),
                message_type="TEXT",
                from_date="2026-01-01",
                to_date="2026-12-31",
                tenant_id="tenant-1",
            )

        body = fake_client.search.call_args.kwargs["body"]
        filters = body["query"]["bool"]["filter"]
        assert {"term": {"chat_id": str(chat.pk)}} in filters
        assert {"term": {"sender_id": str(sender.pk)}} in filters
        assert {"term": {"message_type": "TEXT"}} in filters
        assert {"term": {"tenant_id": "tenant-1"}} in filters
        assert any("range" in f for f in filters)

    def test_restricts_to_users_chats_when_no_chat_id_given(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        fake_client = MagicMock()
        fake_client.search.return_value = self._fake_es_response([])

        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            se.search_messages(user_id=user.pk, query="hello")

        body = fake_client.search.call_args.kwargs["body"]
        filters = body["query"]["bool"]["filter"]
        terms_filters = [f["terms"]["chat_id"] for f in filters if "terms" in f]
        assert terms_filters
        assert str(chat.pk) in terms_filters[0]

    def test_explicit_chat_id_for_a_chat_user_does_not_belong_to_is_rejected(self):
        """
        SECURITY: this used to be the actual bug - the "restrict to
        user's chats" filter only applied when chat_id was absent, so
        passing an explicit ?chat_id=<any chat> bypassed chat-membership
        entirely and let any authenticated user full-text search any
        chat's message content platform-wide. Now an explicit chat_id
        the user doesn't belong to must short-circuit to empty results
        WITHOUT ever calling es.search() (nothing to leak, no query to
        run against a chat the user has no right to see into).
        """
        user = UserFactory()
        other_users_chat = InternalChatFactory()  # user is NOT a participant
        fake_client = MagicMock()
        fake_client.search.return_value = self._fake_es_response([])

        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            result = se.search_messages(
                user_id=user.pk, query="secret", chat_id=str(other_users_chat.pk)
            )

        assert result["results"] == []
        assert result["total"] == 0
        fake_client.search.assert_not_called()

    def test_explicit_chat_id_for_a_chat_user_belongs_to_still_works(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        fake_client = MagicMock()
        fake_client.search.return_value = self._fake_es_response([])

        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            se.search_messages(user_id=user.pk, query="hello", chat_id=str(chat.pk))

        fake_client.search.assert_called_once()
        body = fake_client.search.call_args.kwargs["body"]
        filters = body["query"]["bool"]["filter"]
        assert {"term": {"chat_id": str(chat.pk)}} in filters

    def test_pagination_math(self):
        user = UserFactory()
        fake_client = MagicMock()
        fake_client.search.return_value = self._fake_es_response([])
        with patch("messaging.utils.search_engine.get_es_client", return_value=fake_client):
            result = se.search_messages(user_id=user.pk, query="hello", page=2, page_size=10)
        body = fake_client.search.call_args.kwargs["body"]
        assert body["from"] == 10
        assert body["size"] == 10
        assert result["page"] == 2


# ---------------------------------------------------------------------------
# _db_search_fallback (direct)
# ---------------------------------------------------------------------------

class TestDbSearchFallback:
    def test_blank_query_returns_empty_immediately(self):
        user = UserFactory()
        result = se._db_search_fallback(user_id=user.pk, query="   ", chat_id=None, page=1, page_size=20)
        assert result == {
            "results": [], "total": 0, "page": 1, "page_size": 20,
            "pages": 0, "query": "   ",
        }

    def test_finds_matching_message_in_users_chat(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, content="find this needle", status="SENT")

        result = se._db_search_fallback(user_id=user.pk, query="needle", chat_id=None, page=1, page_size=20)

        assert result["total"] == 1
        assert result["results"][0]["message_id"] == str(msg.id)

    def test_excludes_chats_user_does_not_participate_in(self):
        user = UserFactory()
        other_chat = InternalChatFactory()
        ChatMessageFactory(chat=other_chat, content="needle here", status="SENT")

        result = se._db_search_fallback(user_id=user.pk, query="needle", chat_id=None, page=1, page_size=20)
        assert result["total"] == 0

    def test_excludes_deleted_status_messages(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        ChatMessageFactory(chat=chat, content="needle deleted", status="DELETED")

        result = se._db_search_fallback(user_id=user.pk, query="needle", chat_id=None, page=1, page_size=20)
        assert result["total"] == 0

    def test_chat_id_filter_narrows_results(self):
        user = UserFactory()
        chat1 = InternalChatFactory()
        chat2 = InternalChatFactory()
        ChatParticipantFactory(chat=chat1, user=user)
        ChatParticipantFactory(chat=chat2, user=user)
        ChatMessageFactory(chat=chat1, content="needle in chat1", status="SENT")
        ChatMessageFactory(chat=chat2, content="needle in chat2", status="SENT")

        result = se._db_search_fallback(
            user_id=user.pk, query="needle", chat_id=str(chat1.pk), page=1, page_size=20
        )
        assert result["total"] == 1
        assert result["results"][0]["chat_id"] == str(chat1.pk)

    def test_pagination_slices_results(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        for i in range(5):
            ChatMessageFactory(chat=chat, content=f"needle {i}", status="SENT")

        page1 = se._db_search_fallback(user_id=user.pk, query="needle", chat_id=None, page=1, page_size=2)
        page2 = se._db_search_fallback(user_id=user.pk, query="needle", chat_id=None, page=2, page_size=2)

        assert page1["total"] == 5
        assert len(page1["results"]) == 2
        assert len(page2["results"]) == 2
        assert page1["pages"] == 3

    def test_tenant_id_filter_excludes_other_tenants(self):
        """
        Regression test (Part 6 audit): search_messages()'s ES query has
        always filtered by tenant_id correctly, but this DB fallback (used
        whenever ES is down or errors) silently dropped it - the
        parameter didn't even exist here, even though ChatMessage already
        carries a `tenant` field (from TimestampedModel).
        """
        from django.apps import apps
        Tenant = apps.get_model("tenants", "Tenant")
        tenant_a = Tenant.objects.create(name="Tenant A")
        tenant_b = Tenant.objects.create(name="Tenant B")
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg_a = ChatMessageFactory(chat=chat, content="needle in tenant A", status="SENT", tenant=tenant_a)
        ChatMessageFactory(chat=chat, content="needle in tenant B", status="SENT", tenant=tenant_b)

        result = se._db_search_fallback(
            user_id=user.pk, query="needle", chat_id=None,
            page=1, page_size=20, tenant_id=tenant_a.pk,
        )
        assert result["total"] == 1
        assert result["results"][0]["message_id"] == str(msg_a.id)


# ---------------------------------------------------------------------------
# autocomplete_users
# ---------------------------------------------------------------------------

class TestAutocompleteUsers:
    def test_matches_by_username(self):
        user = UserFactory(username="searchable_zebra")
        results = se.autocomplete_users("zebra")
        assert any(r["user_id"] == str(user.pk) for r in results)

    def test_matches_by_first_or_last_name(self):
        user = UserFactory(first_name="Ziggy", last_name="Stardust")
        results = se.autocomplete_users("Stardust")
        assert any(r["user_id"] == str(user.pk) for r in results)

    def test_excludes_inactive_users(self):
        user = UserFactory(username="inactive_walrus", is_active=False)
        results = se.autocomplete_users("walrus")
        assert not any(r["user_id"] == str(user.pk) for r in results)

    def test_respects_limit(self):
        for i in range(5):
            UserFactory(username=f"limituser{i}")
        results = se.autocomplete_users("limituser", limit=2)
        assert len(results) == 2

    def test_returns_expected_shape(self):
        user = UserFactory(username="shapecheck_otter")
        results = se.autocomplete_users("shapecheck")
        assert results
        assert set(results[0].keys()) == {"user_id", "username", "full_name"}


# ---------------------------------------------------------------------------
# ensure_index_exists / delete_from_index (delegation wrappers)
# ---------------------------------------------------------------------------

class TestEnsureIndexExists:
    def test_delegates_to_elasticsearch_setup(self):
        with patch(
            "messaging.utils.elasticsearch_setup.ensure_index_exists",
            return_value=True,
        ) as mock_ensure:
            result = se.ensure_index_exists(index="custom-index")
        assert result is True
        mock_ensure.assert_called_once_with(index="custom-index")

    def test_returns_false_when_elasticsearch_setup_not_importable(self):
        with patch.dict(
            "sys.modules", {"messaging.utils.elasticsearch_setup": None}
        ):
            result = se.ensure_index_exists()
        assert result is False

    def test_returns_false_on_generic_exception(self):
        with patch(
            "messaging.utils.elasticsearch_setup.ensure_index_exists",
            side_effect=RuntimeError("boom"),
        ):
            result = se.ensure_index_exists()
        assert result is False


class TestDeleteFromIndex:
    def test_delegates_to_elasticsearch_setup(self):
        with patch(
            "messaging.utils.elasticsearch_setup.delete_from_index",
            return_value=True,
        ) as mock_delete:
            result = se.delete_from_index("msg-123")
        assert result is True
        mock_delete.assert_called_once_with("msg-123")

    def test_returns_false_when_elasticsearch_setup_not_importable(self):
        with patch.dict(
            "sys.modules", {"messaging.utils.elasticsearch_setup": None}
        ):
            result = se.delete_from_index("msg-123")
        assert result is False

    def test_returns_false_on_generic_exception(self):
        with patch(
            "messaging.utils.elasticsearch_setup.delete_from_index",
            side_effect=RuntimeError("boom"),
        ):
            result = se.delete_from_index("msg-123")
        assert result is False
