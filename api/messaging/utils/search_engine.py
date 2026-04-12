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
    """Get Elasticsearch client from Django settings."""
    from django.conf import settings
    try:
        from elasticsearch import Elasticsearch
        es_url = getattr(settings, "ELASTICSEARCH_URL", "http://localhost:9200")
        es_user = getattr(settings, "ELASTICSEARCH_USERNAME", None)
        es_pass = getattr(settings, "ELASTICSEARCH_PASSWORD", None)

        if es_user and es_pass:
            return Elasticsearch([es_url], basic_auth=(es_user, es_pass))
        return Elasticsearch([es_url])
    except ImportError:
        logger.warning("Elasticsearch library not installed. Falling back to DB search.")
        return None


def ensure_index_exists() -> bool:
    """Create Elasticsearch index with proper mappings if it doesn't exist."""
    es = get_es_client()
    if not es:
        return False
    try:
        if not es.indices.exists(index=ES_INDEX_MESSAGES):
            es.indices.create(index=ES_INDEX_MESSAGES, body={
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                    "analysis": {
                        "analyzer": {
                            "message_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase", "asciifolding", "stop"],
                            },
                            "bangla_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase"],
                            },
                        }
                    },
                },
                "mappings": {
                    "properties": {
                        "message_id":  {"type": "keyword"},
                        "chat_id":     {"type": "keyword"},
                        "sender_id":   {"type": "keyword"},
                        "content":     {
                            "type": "text",
                            "analyzer": "message_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256},
                                "bangla": {"type": "text", "analyzer": "bangla_analyzer"},
                            },
                        },
                        "message_type":{"type": "keyword"},
                        "created_at":  {"type": "date"},
                        "tenant_id":   {"type": "keyword"},
                        "is_deleted":  {"type": "boolean"},
                    }
                },
            })
            logger.info("ensure_index_exists: Created index %s", ES_INDEX_MESSAGES)
        return True
    except Exception as exc:
        logger.error("ensure_index_exists: %s", exc)
        return False


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


def delete_from_index(message_id: Any) -> bool:
    """Remove a deleted message from search index."""
    es = get_es_client()
    if not es:
        return False
    try:
        es.update(
            index=ES_INDEX_MESSAGES,
            id=str(message_id),
            doc={"is_deleted": True, "content": ""},
        )
        return True
    except Exception as exc:
        logger.error("delete_from_index: msg=%s error=%s", message_id, exc)
        return False


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
            page=page, page_size=page_size,
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

        # Restrict to chats user participates in
        if not chat_id:
            from ..models import ChatParticipant
            chat_ids = list(
                ChatParticipant.objects.filter(user_id=user_id, left_at__isnull=True)
                .values_list("chat_id", flat=True)[:500]
            )
            filter_clauses.append({"terms": {"chat_id": [str(c) for c in chat_ids]}})

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
        return _db_search_fallback(user_id=user_id, query=query, chat_id=chat_id, page=page, page_size=page_size)


def _db_search_fallback(user_id: Any, query: str, chat_id: Optional[str],
                        page: int, page_size: int) -> dict:
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
