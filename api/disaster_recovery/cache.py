"""Redis Cache Layer for DR System."""
import json, logging
from datetime import timedelta
from typing import Optional
logger = logging.getLogger(__name__)

class DRCache:
    def __init__(self, redis_url: str):
        try:
            import redis
            self.client = redis.from_url(redis_url, decode_responses=True)
        except ImportError:
            self.client = None
            logger.warning("redis not installed — caching disabled")

    def get(self, key: str) -> Optional[dict]:
        if not self.client:
            return None
        val = self.client.get(key)
        return json.loads(val) if val else None

    def set(self, key: str, value: dict, ttl: int = 300):
        if not self.client:
            return
        self.client.setex(key, ttl, json.dumps(value, default=str))

    def delete(self, key: str):
        if self.client:
            self.client.delete(key)

    def invalidate_pattern(self, pattern: str):
        if not self.client:
            return
        keys = self.client.keys(pattern)
        if keys:
            self.client.delete(*keys)

cache = None

def get_cache() -> DRCache:
    global cache
    if not cache:
        from .config import settings
        cache = DRCache(settings.redis.url)
    return cache
