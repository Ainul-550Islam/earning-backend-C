"""
Elasticsearch Production Setup — Index mappings and configuration.
Optimized for messaging search with CPAlead platform requirements.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ES_INDEX_MESSAGES = "messaging_messages"
ES_INDEX_USERS    = "messaging_users"

# Full production mapping for messages index
MESSAGES_INDEX_MAPPING = {
    "settings": {
        "number_of_shards":   2,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "messaging_analyzer": {
                    "type":      "custom",
                    "tokenizer": "standard",
                    "filter":    ["lowercase", "stop", "snowball"],
                },
                "autocomplete_analyzer": {
                    "type":      "custom",
                    "tokenizer": "standard",
                    "filter":    ["lowercase", "edge_ngram_filter"],
                },
                "search_analyzer": {
                    "type":      "custom",
                    "tokenizer": "standard",
                    "filter":    ["lowercase"],
                },
            },
            "filter": {
                "edge_ngram_filter": {
                    "type":     "edge_ngram",
                    "min_gram": 1,
                    "max_gram": 20,
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "message_id":   {"type": "keyword"},
            "chat_id":      {"type": "keyword"},
            "sender_id":    {"type": "keyword"},
            "content": {
                "type":            "text",
                "analyzer":        "messaging_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {
                    "autocomplete": {
                        "type":     "text",
                        "analyzer": "autocomplete_analyzer",
                    },
                    "keyword": {
                        "type": "keyword",
                    },
                },
            },
            "message_type": {"type": "keyword"},
            "created_at":   {"type": "date"},
            "tenant_id":    {"type": "keyword"},
            "is_deleted":   {"type": "boolean"},
            "mentions":     {"type": "keyword"},
            "attachments":  {"type": "object", "enabled": False},
        }
    },
}

USERS_INDEX_MAPPING = {
    "settings": {
        "number_of_shards":   1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "user_autocomplete": {
                    "type":      "custom",
                    "tokenizer": "standard",
                    "filter":    ["lowercase", "edge_ngram_filter"],
                },
            },
            "filter": {
                "edge_ngram_filter": {
                    "type":     "edge_ngram",
                    "min_gram": 1,
                    "max_gram": 15,
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "user_id":    {"type": "keyword"},
            "username":   {"type": "text", "analyzer": "user_autocomplete", "search_analyzer": "standard"},
            "full_name":  {"type": "text", "analyzer": "user_autocomplete", "search_analyzer": "standard"},
            "email":      {"type": "keyword"},
            "is_active":  {"type": "boolean"},
            "tenant_id":  {"type": "keyword"},
        }
    },
}


def get_es_client():
    """Get Elasticsearch client. Returns None if not configured."""
    try:
        from django.conf import settings
        es_url = getattr(settings, "ELASTICSEARCH_URL", None)
        if not es_url:
            return None
        from elasticsearch import Elasticsearch
        return Elasticsearch([es_url], timeout=10, max_retries=3, retry_on_timeout=True)
    except ImportError:
        logger.debug("elasticsearch-py not installed")
        return None
    except Exception as exc:
        logger.warning("get_es_client: %s", exc)
        return None


def ensure_index_exists(index: str = ES_INDEX_MESSAGES) -> bool:
    """Create index with full mapping if it doesn't exist."""
    es = get_es_client()
    if not es:
        return False
    try:
        if not es.indices.exists(index=index):
            mapping = MESSAGES_INDEX_MAPPING if index == ES_INDEX_MESSAGES else USERS_INDEX_MAPPING
            es.indices.create(index=index, body=mapping)
            logger.info("ensure_index_exists: created index '%s'", index)
        return True
    except Exception as exc:
        logger.error("ensure_index_exists: %s", exc)
        return False


def index_message(
    *,
    message_id: str,
    chat_id: str,
    sender_id: str,
    content: str,
    message_type: str,
    created_at: str,
    tenant_id=None,
    mentions: list = None,
) -> bool:
    es = get_es_client()
    if not es:
        return _db_index_fallback(message_id, chat_id, content)
    try:
        es.index(index=ES_INDEX_MESSAGES, id=message_id, body={
            "message_id":   message_id,
            "chat_id":      chat_id,
            "sender_id":    sender_id,
            "content":      content,
            "message_type": message_type,
            "created_at":   created_at,
            "tenant_id":    str(tenant_id) if tenant_id else None,
            "is_deleted":   False,
            "mentions":     mentions or [],
        })
        return True
    except Exception as exc:
        logger.error("index_message: %s", exc)
        return _db_index_fallback(message_id, chat_id, content)


def delete_from_index(message_id: str) -> bool:
    es = get_es_client()
    if not es:
        return True
    try:
        es.update(index=ES_INDEX_MESSAGES, id=message_id,
                  body={"doc": {"is_deleted": True}})
        return True
    except Exception as exc:
        logger.error("delete_from_index: %s", exc)
        return False


def search_messages(
    *,
    user_id,
    query: str,
    chat_id: str = None,
    sender_id: str = None,
    message_type: str = None,
    from_date: str = None,
    to_date: str = None,
    tenant_id=None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Full-text search with Elasticsearch + DB fallback."""
    if not query or len(query.strip()) < 2:
        return {"total": 0, "results": [], "page": page}

    es = get_es_client()
    if not es:
        return _db_search_fallback(user_id=user_id, query=query, chat_id=chat_id,
                                    page=page, page_size=page_size)

    must_clauses = [{"multi_match": {
        "query": query,
        "fields": ["content^2", "content.autocomplete"],
        "type": "best_fields",
        "fuzziness": "AUTO",
    }}]
    filter_clauses = [{"term": {"is_deleted": False}}]

    if chat_id:
        filter_clauses.append({"term": {"chat_id": chat_id}})
    if sender_id:
        filter_clauses.append({"term": {"sender_id": str(sender_id)}})
    if message_type:
        filter_clauses.append({"term": {"message_type": message_type}})
    if tenant_id:
        filter_clauses.append({"term": {"tenant_id": str(tenant_id)}})
    if from_date or to_date:
        date_range = {}
        if from_date: date_range["gte"] = from_date
        if to_date:   date_range["lte"] = to_date
        filter_clauses.append({"range": {"created_at": date_range}})

    try:
        resp = es.search(
            index=ES_INDEX_MESSAGES,
            body={
                "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
                "highlight": {
                    "fields": {"content": {"fragment_size": 150, "number_of_fragments": 1}},
                    "pre_tags": ["<mark>"], "post_tags": ["</mark>"],
                },
                "from": (page - 1) * page_size,
                "size": page_size,
                "_source": ["message_id", "chat_id", "sender_id",
                            "content", "message_type", "created_at"],
            },
        )
        hits = resp["hits"]
        results = []
        for hit in hits["hits"]:
            src = hit["_source"]
            highlight = hit.get("highlight", {}).get("content", [src.get("content", "")[:150]])
            results.append({
                "message_id":   src["message_id"],
                "chat_id":      src["chat_id"],
                "sender_id":    src.get("sender_id"),
                "content":      src.get("content", ""),
                "message_type": src.get("message_type"),
                "created_at":   src.get("created_at"),
                "highlight":    highlight[0] if highlight else "",
                "score":        hit["_score"],
            })
        return {
            "total":   hits["total"]["value"],
            "results": results,
            "page":    page,
            "page_size": page_size,
        }
    except Exception as exc:
        logger.error("search_messages ES: %s — falling back to DB", exc)
        return _db_search_fallback(user_id=user_id, query=query, chat_id=chat_id,
                                    page=page, page_size=page_size)


def autocomplete_users(query: str, tenant_id=None, limit: int = 10) -> list:
    """User autocomplete for @mentions."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    from django.db.models import Q
    qs = User.objects.filter(is_active=True).filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    )[:limit]
    return [{
        "user_id":  str(u.pk),
        "username": u.username,
        "full_name": u.get_full_name(),
        "email":    u.email,
    } for u in qs]


def _db_search_fallback(
    user_id, query: str, chat_id: str = None,
    page: int = 1, page_size: int = 20
) -> dict:
    """DB-level fallback search using MessageSearchIndex."""
    if not query or not query.strip():
        return {"total": 0, "results": [], "page": page}

    from ..models import ChatMessage, ChatParticipant, MessageSearchIndex
    from django.db.models import Q

    q = query.strip().lower()

    # Get chats user can access
    accessible_chat_ids = ChatParticipant.objects.filter(
        user_id=user_id, left_at__isnull=True
    ).values_list("chat_id", flat=True)

    qs = MessageSearchIndex.objects.filter(
        chat_id__in=accessible_chat_ids,
        search_text__icontains=q,
    ).select_related("message", "chat")

    if chat_id:
        qs = qs.filter(chat_id=chat_id)

    total = qs.count()
    offset = (page - 1) * page_size
    items  = qs.order_by("-message__created_at")[offset: offset + page_size]

    results = []
    for idx in items:
        msg = idx.message
        results.append({
            "message_id":   str(msg.id),
            "chat_id":      str(msg.chat_id),
            "sender_id":    str(msg.sender_id) if msg.sender_id else None,
            "content":      msg.content,
            "message_type": msg.message_type,
            "created_at":   msg.created_at.isoformat(),
            "highlight":    _highlight(msg.content, q),
            "score":        1.0,
        })

    return {"total": total, "results": results, "page": page, "page_size": page_size}


def _db_index_fallback(message_id: str, chat_id: str, content: str) -> bool:
    """Update the DB search index when ES is not available."""
    try:
        from ..models import MessageSearchIndex, ChatMessage
        msg = ChatMessage.objects.filter(pk=message_id).first()
        if msg:
            MessageSearchIndex.objects.update_or_create(
                message_id=message_id,
                defaults={
                    "chat_id":     chat_id,
                    "search_text": (content or "").lower().strip(),
                    "tenant":      msg.tenant,
                },
            )
        return True
    except Exception as exc:
        logger.error("_db_index_fallback: %s", exc)
        return False


def _highlight(content: str, query: str, max_len: int = 150) -> str:
    """Simple highlight — wrap matched term in <mark>."""
    if not content:
        return ""
    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:max_len]
    start = max(0, idx - 30)
    end   = min(len(content), idx + len(query) + 30)
    snippet = content[start:end]
    highlighted = snippet.replace(
        content[idx:idx + len(query)],
        f"<mark>{content[idx:idx + len(query)]}</mark>",
        1,
    )
    return ("..." if start > 0 else "") + highlighted + ("..." if end < len(content) else "")
