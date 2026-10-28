# Correct imports for task context
try:
    from offer_routing.services.core.RoutingCacheService import RoutingCacheService
except ImportError:
    try:
        from offer_routing.services.cache import RoutingCacheService
    except ImportError:
        class RoutingCacheService:
            def __getattr__(self, item): return lambda *a, **k: None

try:
    from offer_routing.services.core.OfferScorer import OfferScorer
except ImportError:
    OfferScorer = None

try:
    from offer_routing.services.core.OfferRanker import OfferRanker
except ImportError:
    OfferRanker = None

"""Task services stub: core."""
from celery import shared_task


# Auto-generated re-exports for task imports
