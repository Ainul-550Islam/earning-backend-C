
# Auto-generated re-exports for task imports

try:
    from offer_routing.services.cache import cache_service
except ImportError:
    class cache_service:
        def __getattr__(self, item): return lambda *a, **k: None
