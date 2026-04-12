"""
api/ai_engine/cache.py
=======================
AI Engine — Cache management layer।
"""

import logging
from typing import Any, Optional, Callable
from django.core.cache import cache
from .constants import (
    CACHE_TTL_RECOMMENDATION, CACHE_TTL_USER_EMBEDDING,
    CACHE_TTL_SEGMENT, CACHE_TTL_MODEL_META,
    CACHE_TTL_PREDICTION, CACHE_TTL_INSIGHT,
)

logger = logging.getLogger(__name__)

PREFIX = 'ai_engine'


def _key(*parts) -> str:
    return f"{PREFIX}:" + ":".join(str(p) for p in parts)


# ── Model Meta Cache ────────────────────────────────────────────────────

def get_model_meta(model_id: str) -> Optional[dict]:
    return cache.get(_key('model', model_id))


def set_model_meta(model_id: str, data: dict):
    cache.set(_key('model', model_id), data, CACHE_TTL_MODEL_META)


def invalidate_model_meta(model_id: str):
    cache.delete(_key('model', model_id))


# ── User Embedding Cache ────────────────────────────────────────────────

def get_user_embedding(user_id, embedding_type: str = 'behavioral') -> Optional[list]:
    return cache.get(_key('embedding', 'user', user_id, embedding_type))


def set_user_embedding(user_id, embedding_type: str, vector: list):
    cache.set(_key('embedding', 'user', user_id, embedding_type), vector, CACHE_TTL_USER_EMBEDDING)


def invalidate_user_embedding(user_id):
    """User এর সব embedding cache delete করো।"""
    for etype in ['behavioral', 'collaborative', 'content_based', 'hybrid']:
        cache.delete(_key('embedding', 'user', user_id, etype))


# ── Recommendation Cache ────────────────────────────────────────────────

def get_recommendations(user_id, item_type: str = 'offer') -> Optional[list]:
    return cache.get(_key('rec', user_id, item_type))


def set_recommendations(user_id, item_type: str, data: list):
    cache.set(_key('rec', user_id, item_type), data, CACHE_TTL_RECOMMENDATION)


def invalidate_recommendations(user_id):
    for itype in ['offer', 'product', 'content', 'ad', 'task']:
        cache.delete(_key('rec', user_id, itype))


# ── Prediction Cache ────────────────────────────────────────────────────

def get_prediction(user_id, prediction_type: str) -> Optional[dict]:
    return cache.get(_key('pred', user_id, prediction_type))


def set_prediction(user_id, prediction_type: str, data: dict):
    cache.set(_key('pred', user_id, prediction_type), data, CACHE_TTL_PREDICTION)


def invalidate_prediction(user_id, prediction_type: str):
    cache.delete(_key('pred', user_id, prediction_type))


# ── Segment Cache ────────────────────────────────────────────────────────

def get_active_segments(tenant_id) -> Optional[list]:
    return cache.get(_key('segments', tenant_id))


def set_active_segments(tenant_id, data: list):
    cache.set(_key('segments', tenant_id), data, CACHE_TTL_SEGMENT)


def invalidate_segments(tenant_id):
    cache.delete(_key('segments', tenant_id))


# ── Insight Cache ────────────────────────────────────────────────────────

def get_insights(tenant_id) -> Optional[list]:
    return cache.get(_key('insights', tenant_id))


def set_insights(tenant_id, data: list):
    cache.set(_key('insights', tenant_id), data, CACHE_TTL_INSIGHT)


def invalidate_insights(tenant_id):
    cache.delete(_key('insights', tenant_id))


# ── Churn Profile Cache ─────────────────────────────────────────────────

def get_churn_profile(user_id) -> Optional[dict]:
    return cache.get(_key('churn', user_id))


def set_churn_profile(user_id, data: dict):
    cache.set(_key('churn', user_id), data, CACHE_TTL_PREDICTION)


# ── Generic Cache-or-Compute ─────────────────────────────────────────────

def cached_or_compute(cache_key: str, ttl: int, fn: Callable) -> Any:
    """
    Cache hit → return. Cache miss → compute + store।
    """
    result = cache.get(cache_key)
    if result is None:
        try:
            result = fn()
            cache.set(cache_key, result, ttl)
        except Exception as e:
            logger.error(f"Cache compute error [{cache_key}]: {e}")
            raise
    return result


def bulk_invalidate(pattern_prefix: str):
    """Prefix দিয়ে সব cache delete (Django cache backend support করলে)।"""
    # Redis backend ব্যবহার করলে delete_pattern use করা যাবে
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        keys = conn.keys(f"*{pattern_prefix}*")
        if keys:
            conn.delete(*keys)
    except Exception:
        logger.warning("Bulk cache invalidation supported only with Redis backend.")
