"""
Elasticsearch-backed message search engine.
World-class full-text search like Slack, Telegram, Discord.

Features:
- Full-text search across all messages
- Search within a specific chat
- Search with filters (date range, sender, message type)
- Autocomplete / typeahead
- Message indexing on send (async via Celery)
- Fuzzy matching, stemming, language-aware tokenization
- Bangla language support
"""
from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

ES_INDEX_MESSAGES = "messaging_messages"
ES_INDEX_USERS    = "messaging_users"
ES_INDEX_CHANNELS = "messaging_channels"


def get_es_client():
    """
    Get Elasticsearch client from Django settings, or None if
    ELASTICSEARCH_URL isn't configured.

    Deliberately does NOT default es_url to "http://localhost:9200" -
    doing so used to mean that in any environment where ES simply isn't
    configured, this returned a real (if doomed) client instead of None,
    so every caller that does `if es: es.ping()` / `es.search(...)` etc.
    (views.py's /health check, index_message(), search_messages()) paid
    for a real, retrying network connection attempt (multiple seconds of
    exponential backoff) instead of detecting "not configured" and
    falling back immediately. elasticsearch_setup.get_es_client() (the
    other copy of this function) already got this right - matching it.
    """
    from django.conf import settings
    try:
        from elasticsearch import Elasticsearch
        es_url = getattr(settings, "ELASTICSEARCH_URL", None)
        if not es_url:
            return None
        es_user = getattr(settings, "ELASTICSEARCH_USERNAME", None)
        es_pass = getattr(settings, "ELASTICSEARCH_PASSWORD", None)

        if es_user and es_pass:
            return Elasticsearch([es_url], basic_auth=(es_user, es_pass))
        return Elasticsearch([es_url])
    except ImportError:
        logger.warning("Elasticsearch library not installed. Falling back to DB search.")
        return None


# ensure_index_exists is defined further below (see "Fix 2" block) so that it
# delegates to elasticsearch_setup.ensure_index_exists, which carries the full
# production mapping.  Do NOT add a second definition here — Python would
# shadow it and callers would silently get whichever version is defined last.


def index_message(message_id: Any, chat_id: Any, sender_id: Any,
                  content: str, message_type: str, created_at: str,
                  tenant_id: Any = None) -> bool:
    """Index a single message in Elasticsearch. Called after message is sent."""
    es = get_es_client()
    if not es:
        return False
    try:
        es.index(
            index=ES_INDEX_MESSAGES,
            id=str(message_id),
            document={
                "message_id":   str(message_id),
                "chat_id":      str(chat_id),
                "sender_id":    str(sender_id),
                "content":      content or "",
                "message_type": message_type,
                "created_at":   created_at,
                "tenant_id":    str(tenant_id) if tenant_id else None,
                "is_deleted":   False,
            },
        )
        return True
    except Exception as exc:
        logger.error("index_message: msg=%s error=%s", message_id, exc)
        return False


def upsert_search_index_row(msg) -> None:
    """
    Upsert the DB-side MessageSearchIndex mirror row for a ChatMessage.

    Kept as a single shared helper because three call sites need to do
    exactly this and stay identical: index_message_task (single-message
    live indexing right after send), bulk_reindex_task, and the
    sync_search_index management command.

    Part 6 (management/commands/) audit note: before this fix, only
    index_message_task ever wrote this table. bulk_reindex_task and
    sync_search_index both called index_message() above directly, which
    only writes to real Elasticsearch - so anything indexed via either
    bulk path left MessageSearchIndex silently stale. That's more than
    cosmetic: MessageSearchIndexViewSet's admin "browse index" endpoint
    (GET /messaging/search-index/) reads ONLY from this table, and that
    same viewset's own "rebuild" action (POST .../rebuild/) calls
    bulk_reindex_task - so triggering a rebuild did not actually refresh
    what an admin would then see when browsing the index they just
    rebuilt.

    Args:
        msg: an already-loaded ChatMessage instance. Takes the object
             rather than an id so bulk callers that already hold the
             row from a queryset don't pay for a redundant per-message
             re-fetch. Uses msg.chat_id/msg.tenant_id (not msg.chat/
             msg.tenant) deliberately - both are plain FK columns, so
             this never triggers a lazy related-object query even when
             the caller's queryset used .only() without select_related
             (sync_search_index management command does exactly that).
    """
    from ..models import MessageSearchIndex
    MessageSearchIndex.objects.update_or_create(
        message=msg,
        defaults={
            "chat_id": msg.chat_id,
            "search_text": (msg.content or "").lower().strip(),
            "tenant_id": msg.tenant_id,
        },
    )


def search_messages(
    *,
    user_id: Any,
    query: str,
    chat_id: Optional[str] = None,
    sender_id: Optional[str] = None,
    message_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    tenant_id: Optional[Any] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Full-text search across messages.
    Falls back to DB search if Elasticsearch unavailable.
    """
    es = get_es_client()
    if not es:
        return _db_search_fallback(
            user_id=user_id, query=query, chat_id=chat_id,
            tenant_id=tenant_id, page=page, page_size=page_size,
        )

    try:
        must_clauses = [{"match": {"content": {"query": query, "fuzziness": "AUTO"}}}]
        filter_clauses = [{"term": {"is_deleted": False}}]

        if chat_id:
            filter_clauses.append({"term": {"chat_id": str(chat_id)}})
        if sender_id:
            filter_clauses.append({"term": {"sender_id": str(sender_id)}})
        if message_type:
            filter_clauses.append({"term": {"message_type": message_type}})
        if tenant_id:
            filter_clauses.append({"term": {"tenant_id": str(tenant_id)}})
        if from_date or to_date:
            date_range = {}
            if from_date:
                date_range["gte"] = from_date
            if to_date:
                date_range["lte"] = to_date
            filter_clauses.append({"range": {"created_at": date_range}})

        # Restrict to chats user participates in. This must be
        # unconditional - a requested chat_id is validated AGAINST this
        # set, never used as a substitute for it. Previously this only
        # ran when chat_id was absent, so ?chat_id=<any chat's id>
        # bypassed chat-membership entirely and let any authenticated
        # user full-text search any chat's message content platform-wide.
        # Mirrors the already-correct pattern in _db_search_fallback().
        from ..models import ChatParticipant
        user_chat_ids = set(
            str(c) for c in
            ChatParticipant.objects.filter(user_id=user_id, left_at__isnull=True)
            .values_list("chat_id", flat=True)[:500]
        )
        if chat_id:
            if str(chat_id) not in user_chat_ids:
                return {
                    "results": [], "total": 0, "page": page, "page_size": page_size,
                    "pages": 0, "query": query,
                }
        else:
            filter_clauses.append({"terms": {"chat_id": list(user_chat_ids)}})

        body = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "highlight": {
                "fields": {"content": {"fragment_size": 150, "number_of_fragments": 2}},
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
            },
            "sort": [{"_score": "desc"}, {"created_at": "desc"}],
            "from": (page - 1) * page_size,
            "size": page_size,
        }

        result = es.search(index=ES_INDEX_MESSAGES, body=body)
        hits = result["hits"]["hits"]
        total = result["hits"]["total"]["value"]

        # Fetch actual message objects from DB
        message_ids = [h["_source"]["message_id"] for h in hits]
        from ..models import ChatMessage
        messages = {
            str(m.id): m
            for m in ChatMessage.objects.filter(id__in=message_ids).select_related("sender", "chat")
        }

        results = []
        for hit in hits:
            mid = hit["_source"]["message_id"]
            msg = messages.get(mid)
            if msg:
                results.append({
                    "message_id": mid,
                    "chat_id": hit["_source"]["chat_id"],
                    "content": msg.content,
                    "sender_id": str(msg.sender_id),
                    "created_at": msg.created_at.isoformat(),
                    "score": hit["_score"],
                    "highlight": hit.get("highlight", {}).get("content", []),
                })

        return {
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "query": query,
        }
    except Exception as exc:
        logger.error("search_messages: ES query failed: %s — falling back to DB", exc)
        return _db_search_fallback(
            user_id=user_id, query=query, chat_id=chat_id,
            tenant_id=tenant_id, page=page, page_size=page_size,
        )


def _db_search_fallback(user_id: Any, query: str, chat_id: Optional[str],
                        page: int, page_size: int, tenant_id: Optional[Any] = None) -> dict:
    """Fallback to ORM when Elasticsearch is unavailable."""
    from ..models import ChatMessage, ChatParticipant, MessageStatus
    if not query.strip():
        return {"results": [], "total": 0, "page": page, "page_size": page_size, "pages": 0, "query": query}

    chat_ids = list(
        ChatParticipant.objects.filter(user_id=user_id, left_at__isnull=True)
        .values_list("chat_id", flat=True)
    )
    qs = ChatMessage.objects.filter(
        chat_id__in=chat_ids,
        content__icontains=query.strip(),
        status__in=[MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ],
    ).select_related("sender", "chat").order_by("-created_at")

    if chat_id:
        qs = qs.filter(chat_id=chat_id)
    if tenant_id:
        # Part 6 audit fix: search_messages()'s ES query has always
        # filtered by tenant_id correctly, but this DB fallback (used
        # whenever ES is down or errors) silently dropped it - the
        # parameter didn't even exist here, even though ChatMessage
        # already carries a `tenant` field (from TimestampedModel).
        qs = qs.filter(tenant_id=tenant_id)

    total = qs.count()
    msgs = qs[(page-1)*page_size: page*page_size]

    return {
        "results": [{
            "message_id": str(m.id),
            "chat_id": str(m.chat_id),
            "content": m.content,
            "sender_id": str(m.sender_id),
            "created_at": m.created_at.isoformat(),
            "score": 1.0,
            "highlight": [],
        } for m in msgs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "query": query,
    }


def autocomplete_users(query: str, tenant_id: Any = None, limit: int = 10) -> list:
    """
    Autocomplete user search by name or username.
    Used for @mentions and adding participants.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(
        is_active=True
    ).filter(
        __import__("django.db.models", fromlist=["Q"]).Q(username__icontains=query) |
        __import__("django.db.models", fromlist=["Q"]).Q(first_name__icontains=query) |
        __import__("django.db.models", fromlist=["Q"]).Q(last_name__icontains=query)
    )[:limit]
    return [{"user_id": str(u.pk), "username": u.username,
             "full_name": u.get_full_name()} for u in qs]

# ─────────────────────────────────────────────────────────────────────────────
# Fix 2: ensure_index_exists()
# Previously: apps.py startup called this from search_engine but it only
# existed in elasticsearch_setup.py → silent failure on startup.
# This thin wrapper delegates to elasticsearch_setup while keeping search_engine
# as the single runtime import target for tasks/views.
# ─────────────────────────────────────────────────────────────────────────────

def ensure_index_exists(index: str = ES_INDEX_MESSAGES) -> bool:
    """
    Ensure the Elasticsearch index exists with the production mapping.

    Delegates to elasticsearch_setup.ensure_index_exists() which holds the
    full production mapping. Called by apps.py on startup.

    Args:
        index: Index name to create if missing. Defaults to ES_INDEX_MESSAGES.

    Returns:
        True if index exists or was created. False if ES unavailable.
    """
    try:
        from .elasticsearch_setup import ensure_index_exists as _ensure
        return _ensure(index=index)
    except ImportError:
        logger.debug("ensure_index_exists: elasticsearch_setup not importable.")
        return False
    except Exception as exc:
        logger.warning("ensure_index_exists: %s", exc)
        return False


def delete_from_index(message_id: str) -> bool:
    """
    Soft-delete a message from the search index.
    Called by delete_from_index_task in tasks.py.

    Delegates to elasticsearch_setup.delete_from_index(), which holds the
    canonical implementation — mirrors the ensure_index_exists() delegation
    pattern above, for the same reason (avoid two divergent copies of the
    same ES call silently shadowing each other).

    Args:
        message_id: UUID string of the ChatMessage to remove from results.

    Returns:
        True on success or if ES is unavailable. False on error.
    """
    try:
        from .elasticsearch_setup import delete_from_index as _delete
        return _delete(message_id)
    except ImportError:
        logger.debug("delete_from_index: elasticsearch_setup not importable.")
        return False
    except Exception as exc:
        logger.warning("delete_from_index: %s", exc)
        return False
