# api/cache/keys/__init__.py
"""Cache key generation and patterns."""
from api.cache.keys.CacheKeyGenerator import (
    CacheKeyGenerator,
    cache_key_generator,
    generate_key,
    increment_version,
    make_simple_key,
)
from api.cache.keys.KeyPatterns import KeyPatterns, key_patterns

__all__ = [
    'CacheKeyGenerator',
    'cache_key_generator',
    'generate_key',
    'increment_version',
    'make_simple_key',
    'KeyPatterns',
    'key_patterns',
]
