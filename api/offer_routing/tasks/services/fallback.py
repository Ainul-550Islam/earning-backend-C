"""Task services stub: fallback."""
from celery import shared_task


# Auto-generated re-exports for task imports

try:
    from offer_routing.services.fallback import FallbackService
except ImportError:
    class FallbackService:
        def __getattr__(self, item): return lambda *a, **k: None
