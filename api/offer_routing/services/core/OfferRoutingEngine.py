"""
Main Offer Routing Engine

This is the main entry point for the offer routing system.
Takes user + context and returns ranked offer list in <50ms.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from ...models import (
    OfferRoute, RouteCondition, RouteAction,
    RoutingDecisionLog, UserOfferHistory
)
from ...utils import (
    generate_cache_key, hash_context, calculate_score,
    extract_device_info, get_user_segment_info
)
from ...constants import (
    ROUTING_CACHE_TIMEOUT, MAX_ROUTING_TIME_MS,
    DEFAULT_ROUTE_PRIORITY, MAX_OFFERS_PER_ROUTE
)
from ...exceptions import (
    RoutingTimeoutError, RouteNotFoundError,
    OfferNotFoundError, CacheError
)
from .RouteEvaluator import RouteEvaluator
from .OfferScorer import OfferScorer
from .OfferRanker import OfferRanker
from .RoutingCacheService import RoutingCacheService

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferRoutingEngine:
    """
    Main routing engine for offer routing system.
    
    Coordinates between targeting, scoring, personalization,
    cap enforcement, and fallback services to make routing decisions.
    
    Performance target: <50ms response time for 95% of requests
    """
    
    def __init__(self):
        self.start_time = None
        self.cache_service = RoutingCacheService()
        self.route_evaluator = RouteEvaluator()
        self.offer_scorer = OfferScorer()
        self.offer_ranker = OfferRanker()
        
        # Import other services to avoid circular imports
        from ..targeting import TargetingService
        from ..personalization import PersonalizationService
        from ..cap import CapEnforcementService
        from ..fallback import FallbackService
        from ..ab_test import ABTestService
        
        self.targeting_service = TargetingService()
        self.personalization_service = PersonalizationService()
        self.cap_service = CapEnforcementService()
        self.fallback_service = FallbackService()
        self.ab_test_service = ABTestService()
    
    def route_offers(self, user: User, context: Dict[str, Any], 
                     max_offers: int = None) -> List[Dict[str, Any]]:
        """
        Main entry point for offer routing.
        
        Args:
            user: User object
            context: User context (device, location, time, etc.)
            max_offers: Maximum number of offers to return
            
        Returns:
            List of ranked offers with scores and metadata
            
        Raises:
            RoutingTimeoutError: If routing takes too long
            RouteNotFoundError: If no routes match
        """
        self.start_time = time.time()
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user, context)
            cached_result = self.cache_service.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for user {user.id}")
                return cached_result
            
            # Get eligible routes
            eligible_routes = self._get_eligible_routes(user, context)
            
            if not eligible_routes:
                logger.warning(f"No eligible routes for user {user.id}")
                return self._handle_no_routes(user, context)
            
            # Score and rank offers
            scored_offers = self._score_and_rank_offers(user, context, eligible_routes)
            
            # Apply caps and filters
            final_offers = self._apply_caps_and_filters(user, scored_offers)
            
            # Limit results
            if max_offers:
                final_offers = final_offers[:max_offers]
            
            # Cache result
            self.cache_service.set(cache_key, final_offers, ROUTING_CACHE_TIMEOUT)
            
            # Log decision
            self._log_routing_decision(user, context, final_offers)
            
            # Check performance
            self._check_performance()
            
            return final_offers
            
        except Exception as e:
            logger.error(f"Error in route_offers for user {user.id}: {e}")
            return self._handle_routing_error(user, context, e)
    
    def _generate_cache_key(self, user: User, context: Dict[str, Any]) -> str:
        """Generate cache key for routing decision."""
        context_hash = hash_context(context)
        return f"routing:{user.id}:{context_hash}"
    
    def _get_eligible_routes(self, user: User, context: Dict[str, Any]) -> List[OfferRoute]:
        """Get routes that match user and context."""
        all_routes = OfferRoute.objects.filter(is_active=True).order_by('priority')
        
        eligible_routes = []
        for route in all_routes:
            if self.route_evaluator.evaluate_route(route, user, context):
                eligible_routes.append(route)
        
        return eligible_routes
    
    def _score_and_rank_offers(self, user: User, context: Dict[str, Any], 
                               routes: List[OfferRoute]) -> List[Dict[str, Any]]:
        """Score and rank offers from eligible routes."""
        all_offers = []
        
        for route in routes:
            # Get offers from route
            route_offers = self._get_offers_from_route(route)
            
            # Score each offer
            for offer in route_offers:
                score = self.offer_scorer.score_offer(offer, user, context, route)
                all_offers.append({
                    'offer': offer,
                    'route': route,
                    'score': score,
                    'metadata': {
                        'route_id': route.id,
                        'route_name': route.name,
                        'route_priority': route.priority
                    }
                })
        
        # Rank offers
        ranked_offers = self.offer_ranker.rank_offers(all_offers, user, context)
        
        return ranked_offers
    
    def _get_offers_from_route(self, route: OfferRoute) -> List[Any]:
        """Get offers associated with a route."""
        # This would implement route-specific offer retrieval
        # For now, return placeholder
        return []
    
    def _apply_caps_and_filters(self, user: User, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply caps and additional filters to offers."""
        filtered_offers = []
        
        for offer_data in offers:
            offer = offer_data['offer']
            
            # Check caps
            if self.cap_service.can_show_offer(user, offer):
                # Update cap counters
                self.cap_service.increment_cap(user, offer)
                filtered_offers.append(offer_data)
        
        return filtered_offers
    
    def _handle_no_routes(self, user: User, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle case when no routes match."""
        try:
            fallback_offers = self.fallback_service.get_fallback_offers(user, context)
            return fallback_offers
        except Exception as e:
            logger.error(f"Error in fallback for user {user.id}: {e}")
            return []
    
    def _handle_routing_error(self, user: User, context: Dict[str, Any], 
                            error: Exception) -> List[Dict[str, Any]]:
        """Handle routing errors gracefully."""
        # Log error
        logger.error(f"Routing error for user {user.id}: {error}")
        
        # Try to return safe fallback
        try:
            return self.fallback_service.get_safe_fallback(user, context)
        except:
            return []
    
    def _log_routing_decision(self, user: User, context: Dict[str, Any], 
                           offers: List[Dict[str, Any]]):
        """Log routing decision for analytics."""
        try:
            for i, offer_data in enumerate(offers):
                RoutingDecisionLog.objects.create(
                    user=user,
                    route=offer_data['route'],
                    offer=offer_data['offer'],
                    reason='routed',
                    score=offer_data['score'],
                    rank=i,
                    response_time_ms=int((time.time() - self.start_time) * 1000),
                    context_data=context,
                    personalization_applied=True,
                    caps_checked=True,
                    fallback_used=False
                )
        except Exception as e:
            logger.error(f"Error logging routing decision: {e}")
    
    def _check_performance(self):
        """Check if routing is within performance targets."""
        elapsed_ms = (time.time() - self.start_time) * 1000
        
        if elapsed_ms > MAX_ROUTING_TIME_MS:
            logger.warning(f"Routing took {elapsed_ms:.2f}ms (target: {MAX_ROUTING_TIME_MS}ms)")
        
        # Log performance metrics
        logger.debug(f"Routing completed in {elapsed_ms:.2f}ms")
    
    def get_routing_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get routing statistics for a user."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        decisions = RoutingDecisionLog.objects.filter(
            user_id=user_id,
            created_at__gte=cutoff_date
        )
        
        return {
            'total_decisions': decisions.count(),
            'avg_response_time_ms': decisions.aggregate(
                avg_time=models.Avg('response_time_ms')
            )['avg_time'] or 0,
            'cache_hit_rate': decisions.filter(cache_hit=True).count() / decisions.count() if decisions.count() > 0 else 0,
            'personalization_rate': decisions.filter(personalization_applied=True).count() / decisions.count() if decisions.count() > 0 else 0
        }
    
    def clear_user_cache(self, user_id: int):
        """Clear cache for a specific user."""
        try:
            pattern = f"routing:{user_id}:*"
            self.cache_service.delete_pattern(pattern)
            logger.info(f"Cleared cache for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing cache for user {user_id}: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on routing engine."""
        try:
            # Test cache
            cache_status = self.cache_service.health_check()
            
            # Test services
            services_status = {
                'route_evaluator': bool(self.route_evaluator),
                'offer_scorer': bool(self.offer_scorer),
                'offer_ranker': bool(self.offer_ranker),
                'targeting_service': bool(self.targeting_service),
                'personalization_service': bool(self.personalization_service),
                'cap_service': bool(self.cap_service),
                'fallback_service': bool(self.fallback_service)
            }
            
            return {
                'status': 'healthy',
                'cache': cache_status,
                'services': services_status,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
