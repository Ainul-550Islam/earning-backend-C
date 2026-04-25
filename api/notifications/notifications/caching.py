# earning_backend/api/notifications/caching.py
"""Caching — Centralised caching layer for the notification system."""
import logging
from typing import Any, Optional
from django.core.cache import cache
logger = logging.getLogger(__name__)

TTL_UNREAD_COUNT=60; TTL_USER_STATUS=60; TTL_TEMPLATE=300; TTL_SEGMENT=300
TTL_FATIGUE=120; TTL_OPT_OUT=300; TTL_PREF=300; TTL_HEALTH=30
TTL_ANALYTICS=900; TTL_RATE_LIMIT=60; TTL_DEVICE_LIST=180

def get_unread_count(user_id): return cache.get(f"notif:count:{user_id}")
def set_unread_count(user_id, count): cache.set(f"notif:count:{user_id}", count, TTL_UNREAD_COUNT)
def invalidate_unread_count(user_id): cache.delete(f"notif:count:{user_id}")
def get_user_notification_status(user_id): return cache.get(f"notif:ctx:{user_id}")
def set_user_notification_status(user_id, status): cache.set(f"notif:ctx:{user_id}", status, TTL_USER_STATUS)
def invalidate_user_notification_status(user_id): cache.delete(f"notif:ctx:{user_id}")
def get_template_cache(template_id): return cache.get(f"notif:template:{template_id}")
def set_template_cache(template_id, data): cache.set(f"notif:template:{template_id}", data, TTL_TEMPLATE)
def invalidate_template_cache(template_id): cache.delete(f"notif:template:{template_id}")
def get_segment_users(segment_id): return cache.get(f"notif:segment:{segment_id}")
def set_segment_users(segment_id, user_ids): cache.set(f"notif:segment:{segment_id}", user_ids, TTL_SEGMENT)
def get_opt_outs(user_id): return cache.get(f"notif:optout:{user_id}")
def set_opt_outs(user_id, channels): cache.set(f"notif:optout:{user_id}", channels, TTL_OPT_OUT)
def invalidate_opt_outs(user_id): cache.delete(f"notif:optout:{user_id}")
def get_analytics_cache(key): return cache.get(f"notif:analytics:{key}")
def set_analytics_cache(key, data): cache.set(f"notif:analytics:{key}", data, TTL_ANALYTICS)
def invalidate_all_user_caches(user_id):
    cache.delete_many([f"notif:count:{user_id}",f"notif:ctx:{user_id}",f"notif:fatigue:{user_id}",
                       f"notif:optout:{user_id}",f"notif:pref:{user_id}",f"notif:devices:{user_id}"])
def check_rate_limit(key, limit, window):
    cache_key = f"notif:rl:{key}"
    current = cache.get(cache_key, 0)
    if current >= limit: return False, current
    if current == 0: cache.set(cache_key, 1, window)
    else: cache.incr(cache_key)
    return True, current + 1
