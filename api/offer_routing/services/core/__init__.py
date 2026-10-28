"""
Core service sub-package — canonical class exports.

Directly imports from each sub-module file to avoid the
`importlib.import_module('offer_routing.services.core')` self-referencing
pattern that was exporting module objects instead of class objects.
"""
import logging

logger = logging.getLogger(__name__)

# ── OfferRoutingEngine ───────────────────────────────────────────────────────
try:
    from .OfferRoutingEngine import OfferRoutingEngine
    routing_engine = OfferRoutingEngine()
except Exception as _e:
    logger.warning("OfferRoutingEngine unavailable: %s", _e)
    class OfferRoutingEngine:
        def route_offers(self, *a, **kw): return {'success': False, 'offers': []}
        def health_check(self): return {'status': 'degraded'}
        def get_evaluation_stats(self): return {}
    routing_engine = OfferRoutingEngine()

# ── OfferRanker ──────────────────────────────────────────────────────────────
try:
    from .OfferRanker import OfferRanker
    ranker_service = OfferRanker()
except Exception as _e:
    logger.warning("OfferRanker unavailable: %s", _e)
    class OfferRanker:
        def rank_offers(self, *a, **kw): return []
        def health_check(self): return {'status': 'degraded'}
        def get_metrics(self): return {}
    ranker_service = OfferRanker()

# ── OfferScorer ──────────────────────────────────────────────────────────────
try:
    from .OfferScorer import OfferScorer
    scorer_service = OfferScorer()
except Exception as _e:
    logger.warning("OfferScorer unavailable: %s", _e)
    class OfferScorer:
        def calculate_comprehensive_score(self, offer=None, user=None, context=None): return {'score': 0.5, 'breakdown': {}, 'offer_id': getattr(offer,'id',None)}
        def calculate_personalization_score(self, offer=None, user=None, context=None): return {'score': 0.5, 'algorithm': 'stub'}
        def calculate_freshness_score(self, offer=None, context=None): return {'score': 0.5, 'age_days': 0}
        def calculate_cr_score(self, offer=None, user=None): return {'score': 0.5, 'cr': 0.0}
        def calculate_epc_score(self, offer=None): return {'score': 0.5, 'epc': 0.0}
        def score_offer(self, *a, **kw): return 0.0
        def health_check(self): return {'status': 'degraded'}
        def get_metrics(self): return {}
    scorer_service = OfferScorer()

# ── RouteEvaluator ───────────────────────────────────────────────────────────
try:
    from .RouteEvaluator import RouteEvaluator
    route_evaluator_core = RouteEvaluator()
except Exception as _e:
    logger.warning("RouteEvaluator (core) unavailable: %s", _e)
    class RouteEvaluator:
        def evaluate_route(self, *a, **kw): return False
        def get_evaluation_stats(self): return {}
        def health_check(self): return {'status': 'degraded'}
    route_evaluator_core = RouteEvaluator()

# ── RoutingCacheService ──────────────────────────────────────────────────────
try:
    from .RoutingCacheService import RoutingCacheService as CoreRoutingCacheService
except Exception as _e:
    logger.warning("RoutingCacheService (core) unavailable: %s", _e)
    CoreRoutingCacheService = None

__all__ = [
    'OfferRoutingEngine', 'routing_engine',
    'OfferRanker',        'ranker_service',
    'OfferScorer',        'scorer_service',
    'RouteEvaluator',     'route_evaluator_core',
    'CoreRoutingCacheService',
]
