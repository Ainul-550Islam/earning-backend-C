# api/cache/decorators/__init__.py
"""Cache decorators - cache_data, cache_view, cache_page."""
from api.cache.decorators.cache_data import cache_data, cache_property, cache_method_result
from api.cache.decorators.cache_view import cache_view
from api.cache.decorators.cache_page import cache_page, PageCacheMiddleware

__all__ = [
    'cache_data',
    'cache_property',
    'cache_method_result',
    'cache_view',
    'cache_page',
    'PageCacheMiddleware',
]

try:
    from api.cache.decorators.cache_view import cache_api_view, cache_api_method
    __all__ += ['cache_api_view', 'cache_api_method']
except ImportError:
    cache_api_view = None
    cache_api_method = None
