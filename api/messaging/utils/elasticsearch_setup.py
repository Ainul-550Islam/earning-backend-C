"""
utils/elasticsearch_setup.py — Production Elasticsearch index setup.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RELATIONSHIP TO utils/search_engine.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
utils/search_engine.py   — ACTIVE runtime module.
    Used by: tasks.py (index_message_task, delete_from_index_task,
             bulk_reindex_task) and views.py (MessageSearchView,
             UserSearchView). This is the module that viewsets call
             at runtime for search operations.

utils/elasticsearch_setup.py (THIS FILE) — INDEX ADMINISTRATION only.
    Used by: management commands (setup_messaging_index,
             bulk_index_messages, sync_search_index).
    Provides:
      - MESSAGES_INDEX_MAPPING / USERS_INDEX_MAPPING (detailed production
        mappings with custom analyzers, edge-ngram autocomplete, shards)
      - ensure_index_exists()  — create or update index mapping
      - index_message()        — index a single doc (with DB fallback)
      - delete_from_index()    — soft-delete doc in ES
      - search_messages()      — full-text search (with DB fallback)
      - autocomplete_users()   — user @-mention autocomplete
      - _db_search_fallback()  — ORM fallback when ES unavailable
      - _db_index_fallback()   — write to MessageSearchIndex when ES unavailable
      - _highlight()           — simple substring highlight helper

DO NOT import this file from viewsets, views, or tasks.
Import utils/search_engine.py instead for runtime operations.

This file is imported ONLY from:
  - messaging/management/commands/setup_messaging_index.py
  - messaging/management/commands/bulk_index_messages.py
  - messaging/management/commands/sync_search_index.py
  - messaging/apps.py  (ES index health check on startup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import logging
from typing import Optional

from ..models import ChatMessage, ChatParticipant, MessageSearchIndex  # noqa: F401  (module-level so tests can patch MessageSearchIndex)

logger = logging.getLogger(__name__)

ES_INDEX_MESSAGES = "messaging_messages"
ES_INDEX_USERS    = "messaging_users"

# ── Production index mappings ─────────────────────────────────────────────────
# More detailed than search_engine.py's inline mapping:
#   - 2 shards for messages (horizontal scale)
#   - Custom analyzers: messaging_analyzer (stemmed), autocomplete_analyzer
#     (edge-ngram for prefix search), search_analyzer (lowercase only)
#   - Bangla-friendly: standard tokenizer + lowercase covers Unicode scripts
#   - mentions: keyword array for @-mention filtering
#   - attachments: object disabled (stored but not indexed)

MESSAGES_INDEX_MAPPING: dict = {
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
                "bangla_analyzer": {
                    # Standard tokenizer handles Unicode (Bangla) correctly.
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
                        "type":         "keyword",
                        "ignore_above": 512,
                    },
                    "bangla": {
                        "type":     "text",
                        "analyzer": "bangla_analyzer",
                    },
                },
            },
            "message_type": {"type": "keyword"},
            "created_at":   {"type": "date"},
            "tenant_id":    {"type": "keyword"},
            "is_deleted":   {"type": "boolean"},
            "mentions":     {"type": "keyword"},          # array of user_id strings
            "attachments":  {"type": "object", "enabled": False},  # stored, not indexed
        }
    },
}

USERS_INDEX_MAPPING: dict = {
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
            "user_id":   {"type": "keyword"},
            "username":  {
                "type":            "text",
                "analyzer":        "user_autocomplete",
                "search_analyzer": "standard",
            },
            "full_name": {
                "type":            "text",
                "analyzer":        "user_autocomplete",
                "search_analyzer": "standard",
            },
            "email":     {"type": "keyword"},
            "is_active": {"type": "boolean"},
            "tenant_id": {"type": "keyword"},
        }
    },
}


# ── Client ────────────────────────────────────────────────────────────────────

def get_es_client():
    """
    Return an Elasticsearch client or None if not configured / not installed.

    Reads from Django settings:
        ELASTICSEARCH_URL      (required)
        ELASTICSEARCH_USERNAME (optional, for auth)
        ELASTICSEARCH_PASSWORD (optional, for auth)
    """
    try:
        from django.conf import settings
        es_url  = getattr(settings, "ELASTICSEARCH_URL", None)
        es_user = getattr(settings, "ELASTICSEARCH_USERNAME", None)
        es_pass = getattr(settings, "ELASTICSEARCH_PASSWORD", None)
        if not es_url:
            return None
        from elasticsearch import Elasticsearch
        if es_user and es_pass:
            return Elasticsearch(
                [es_url],
                basic_auth=(es_user, es_pass),
                request_timeout=10,
                max_retries=3,
                retry_on_timeout=True,
            )
        return Elasticsearch([es_url], request_timeout=10, max_retries=3, retry_on_timeout=True)
    except ImportError:
        logger.debug("elasticsearch_setup: elasticsearch-py not installed.")
        return None
    except Exception as exc:
        logger.warning("elasticsearch_setup.get_es_client: %s", exc)
        return None


# ── Index management ──────────────────────────────────────────────────────────

def ensure_index_exists(index: str = ES_INDEX_MESSAGES) -> bool:
    """
    Create the Elasticsearch index with the full production mapping if it
    does not already exist.

    Called by:
      - apps.py MessagingConfig.ready() (startup check)
      - management/commands/setup_messaging_index.py

    Args:
        index: Index name to create. Defaults to ES_INDEX_MESSAGES.

    Returns:
        True if the index already existed or was successfully created.
        False if ES is unavailable or creation failed.
    """
    es = get_es_client()
    if not es:
        return False
    try:
        if es.indices.exists(index=index):
            logger.debug("ensure_index_exists: index '%s' already exists.", index)
            return True
        mapping = MESSAGES_INDEX_MAPPING if index == ES_INDEX_MESSAGES else USERS_INDEX_MAPPING
        es.indices.create(index=index, body=mapping)
        logger.info("ensure_index_exists: created index '%s' with production mapping.", index)
        return True
    except Exception as exc:
        logger.error("ensure_index_exists: %s", exc)
        return False


def ensure_users_index_exists() -> bool:
    """Convenience wrapper to create the users index."""
    return ensure_index_exists(ES_INDEX_USERS)


# ── Document operations ───────────────────────────────────────────────────────

def index_message(
    *,
    message_id: str,
    chat_id: str,
    sender_id: str,
    content: str,
    message_type: str,
    created_at: str,
    tenant_id=None,
    mentions: Optional[list] = None,
) -> bool:
    """
    Index a single message document in Elasticsearch.

    Falls back to _db_index_fallback() (updates MessageSearchIndex table)
    when ES is unavailable.

    Args:
        message_id:   UUID string of the ChatMessage.
        chat_id:      UUID string of the InternalChat.
        sender_id:    UUID string of the sender user.
        content:      Plain-text message content.
        message_type: Value from ChatMessage.message_type choices.
        created_at:   ISO-8601 timestamp string.
        tenant_id:    Optional tenant identifier.
        mentions:     Optional list of mentioned user_id strings.

    Returns:
        True on success (ES or DB fallback), False on complete failure.
    """
    es = get_es_client()
    if not es:
        return _db_index_fallback(message_id, chat_id, content)
    try:
        es.index(
            index=ES_INDEX_MESSAGES,
            id=message_id,
            body={
                "message_id":   message_id,
                "chat_id":      chat_id,
                "sender_id":    sender_id,
                "content":      content or "",
                "message_type": message_type,
                "created_at":   created_at,
                "tenant_id":    str(tenant_id) if tenant_id else None,
                "is_deleted":   False,
                "mentions":     mentions or [],
            },
        )
        return True
    except Exception as exc:
        logger.error("elasticsearch_setup.index_message: msg=%s error=%s", message_id, exc)
        return _db_index_fallback(message_id, chat_id, content)


def delete_from_index(message_id: str) -> bool:
    """
    Soft-delete a message from Elasticsearch by setting is_deleted=True.

    Args:
        message_id: UUID string of the ChatMessage to remove from search.

    Returns:
        True on success, False on failure.
    """
    es = get_es_client()
    if not es:
        return True   # No ES configured — nothing to clean up
    try:
        es.update(
            index=ES_INDEX_MESSAGES,
            id=message_id,
            body={"doc": {"is_deleted": True, "content": ""}},
        )
        return True
    except Exception as exc:
        logger.error("elasticsearch_setup.delete_from_index: msg=%s error=%s", message_id, exc)
        return False


# ── Search ────────────────────────────────────────────────────────────────────

def search_messages(
    *,
    user_id,
    query: str,
    chat_id: Optional[str] = None,
    sender_id: Optional[str] = None,
    message_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    tenant_id=None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Full-text search with Elasticsearch, falling back to DB when unavailable.

    Uses multi_match with autocomplete + standard fields, fuzzy matching,
    and HTML highlight wrapping (<mark>…</mark>).

    Args:
        user_id:      Requesting user — used to restrict to accessible chats.
        query:        Search query string (minimum 2 chars).
        chat_id:      Optional: restrict to a specific chat.
        sender_id:    Optional: restrict to a specific sender.
        message_type: Optional: restrict to a message type.
        from_date:    Optional: ISO-8601 lower bound on created_at.
        to_date:      Optional: ISO-8601 upper bound on created_at.
        tenant_id:    Optional: restrict to a tenant.
        page:         1-based page number.
        page_size:    Results per page (max 100 recommended).

    Returns:
        {"total": int, "results": [...], "page": int, "page_size": int}
    """
    if not query or len(query.strip()) < 2:
        return {"total": 0, "results": [], "page": page, "page_size": page_size}

    es = get_es_client()
    if not es:
        return _db_search_fallback(
            user_id=user_id, query=query, chat_id=chat_id,
            tenant_id=tenant_id, page=page, page_size=page_size,
        )

    must_clauses = [{
        "multi_match": {
            "query":     query,
            "fields":    ["content^2", "content.autocomplete", "content.bangla"],
            "type":      "best_fields",
            "fuzziness": "AUTO",
        }
    }]
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
        date_range: dict = {}
        if from_date:
            date_range["gte"] = from_date
        if to_date:
            date_range["lte"] = to_date
        filter_clauses.append({"range": {"created_at": date_range}})

    # Restrict to chats the user participates in (when no specific chat given)
    if not chat_id:
        accessible = list(
            ChatParticipant.objects.filter(user_id=user_id, left_at__isnull=True)
            .values_list("chat_id", flat=True)[:500]
        )
        filter_clauses.append({"terms": {"chat_id": [str(c) for c in accessible]}})

    try:
        resp = es.search(
            index=ES_INDEX_MESSAGES,
            body={
                "query":     {"bool": {"must": must_clauses, "filter": filter_clauses}},
                "highlight": {
                    "fields": {"content": {"fragment_size": 150, "number_of_fragments": 1}},
                    "pre_tags":  ["<mark>"],
                    "post_tags": ["</mark>"],
                },
                "sort": [{"_score": "desc"}, {"created_at": "desc"}],
                "from": (page - 1) * page_size,
                "size": page_size,
                "_source": [
                    "message_id", "chat_id", "sender_id",
                    "content", "message_type", "created_at",
                ],
            },
        )
        hits = resp["hits"]
        results = []
        for hit in hits["hits"]:
            src = hit["_source"]
            highlight_snip = hit.get("highlight", {}).get("content", [src.get("content", "")[:150]])
            results.append({
                "message_id":   src["message_id"],
                "chat_id":      src["chat_id"],
                "sender_id":    src.get("sender_id"),
                "content":      src.get("content", ""),
                "message_type": src.get("message_type"),
                "created_at":   src.get("created_at"),
                "highlight":    highlight_snip[0] if highlight_snip else "",
                "score":        hit["_score"],
            })
        return {
            "total":     hits["total"]["value"],
            "results":   results,
            "page":      page,
            "page_size": page_size,
            "pages":     (hits["total"]["value"] + page_size - 1) // page_size,
        }
    except Exception as exc:
        logger.error("elasticsearch_setup.search_messages ES: %s — falling back to DB", exc)
        return _db_search_fallback(
            user_id=user_id, query=query, chat_id=chat_id,
            tenant_id=tenant_id, page=page, page_size=page_size,
        )


# Part 6 audit: removed a dead, never-called duplicate of autocomplete_users()
# that lived here. search_engine.py's autocomplete_users() is the real,
# actually-used implementation (per this file's own header docstring, this
# module is index-administration-only and is never imported by runtime
# code) - grep confirmed nothing, including the 3 management commands
# listed above as this file's only valid importers, ever called this
# copy. It shared the same tenant_id-accepted-but-unused gap as the live
# version in search_engine.py (already flagged separately as a business-
# judgment item, not auto-fixed, since resolving it needs the real
# earning_backend tenant/User model this standalone harness doesn't have).
# Keeping two near-identical copies of the same latent bug, one of them
# unreachable, was worth deleting rather than fixing code nothing runs.


# ── Internal fallbacks ────────────────────────────────────────────────────────

def _db_search_fallback(
    user_id,
    query: str,
    chat_id: Optional[str] = None,
    tenant_id=None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    ORM-level search fallback using the MessageSearchIndex table.

    Activated when ES is unavailable or returns an error.
    Uses icontains (case-insensitive substring match) — slower than ES but
    always available.
    """
    if not query or not query.strip():
        return {"total": 0, "results": [], "page": page, "page_size": page_size}

    q = query.strip().lower()

    accessible_chat_ids = ChatParticipant.objects.filter(
        user_id=user_id, left_at__isnull=True,
    ).values_list("chat_id", flat=True)

    qs = MessageSearchIndex.objects.filter(
        chat_id__in=accessible_chat_ids,
        search_text__icontains=q,
    ).select_related("message", "chat")

    if chat_id:
        qs = qs.filter(chat_id=chat_id)
    if tenant_id:
        # Part 6 audit fix: search_messages()'s ES query has always
        # filtered by tenant_id correctly, but this DB fallback (used
        # whenever ES is down or errors) silently dropped it entirely -
        # this function didn't even accept the parameter. The underlying
        # data was already there (_db_index_fallback populates `tenant`
        # on every indexed row), it just was never queried against.
        qs = qs.filter(tenant_id=tenant_id)

    total  = qs.count()
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

    return {
        "total":     total,
        "results":   results,
        "page":      page,
        "page_size": page_size,
        "pages":     (total + page_size - 1) // page_size,
    }


def _db_index_fallback(message_id: str, chat_id: str, content: str) -> bool:
    """
    Write to the MessageSearchIndex DB table when ES is unavailable.

    Called automatically by index_message() on ES failure.
    """
    try:
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
        logger.error("elasticsearch_setup._db_index_fallback: %s", exc)
        return False


def _highlight(content: str, query: str, max_len: int = 150) -> str:
    """
    Wrap the first occurrence of query in content with <mark>…</mark>.

    Returns a trimmed snippet of up to max_len characters with surrounding
    context (30 chars either side of the match).
    """
    if not content:
        return ""
    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:max_len]

    start   = max(0, idx - 30)
    end     = min(len(content), idx + len(query) + 30)
    snippet = content[start:end]
    matched = content[idx: idx + len(query)]
    highlighted = snippet.replace(matched, f"<mark>{matched}</mark>", 1)
    prefix  = "..." if start > 0 else ""
    suffix  = "..." if end < len(content) else ""
    return prefix + highlighted + suffix
