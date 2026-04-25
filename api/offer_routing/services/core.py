"""
Core Routing Engine Service

This module contains the main routing engine that orchestrates
all routing decisions and coordinates between different services.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from ..models import (
    OfferRoute, RouteCondition, RouteAction,
    RoutingDecisionLog, UserOfferHistory
)
from ..utils import (
    generate_cache_key, hash_context, calculate_score,
    extract_device_info, get_user_segment_info
)
from ..constants import (
    ROUTING_CACHE_TIMEOUT, MAX_ROUTING_TIME_MS,
    DEFAULT_ROUTE_PRIORITY, MAX_OFFERS_PER_ROUTE
)
from ..exceptions import (
    RoutingTimeoutError, RouteNotFoundError,
    OfferNotFoundError, CacheError
)

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferRoutingEngine:
    """
    Main routing engine for offer routing system.
    
    Coordinates between targeting, scoring, personalization,
    cap enforcement, and fallback services to make routing decisions.
    """
    
    def __init__(self):
        self.start_time = None
        self.cache_service = None
        self.targeting_service = None
        self.scoring_service = None
        self.personalization_service = None
        self.cap_service = None
        self.fallback_service = None
        self.ab_test_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all routing services."""
        try:
            from .cache import RoutingCacheService
            from .targeting import TargetingService
            from .scoring import OfferScoringService
            from .personalization import PersonalizationService
            from .cap import CapEnforcementService
            from .fallback import FallbackService
            from .ab_test import ABTestService
            
            self.cache_service = RoutingCacheService()
            self.targeting_service = TargetingService()
            self.scoring_service = OfferScoringService()
            self.personalization_service = PersonalizationService()
            self.cap_service = CapEnforcementService()
            self.fallback_service = FallbackService()
            self.ab_test_service = ABTestService()
            
        except ImportError as e:
            logger.error(f"Failed to initialize routing services: {e}")
            raise
    
    def route_offers(self, user_id: int, context: Dict[str, Any], 
                    limit: int = 10, cache_enabled: bool = True) -> Dict[str, Any]:
        """
        Route offers for a user based on context.
        
        Args:
            user_id: User ID to route offers for
            context: User context (device, location, etc.)
            limit: Maximum number of offers to return
            cache_enabled: Whether to use caching
            
        Returns:
            Dictionary with routed offers and metadata
        """
        self.start_time = time.time()
        
        try:
            # Check cache first
            if cache_enabled:
                cached_result = self._get_cached_routing(user_id, context)
                if cached_result:
                    return cached_result
            
            # Get user and validate
            user = self._get_user(user_id)
            if not user:
                return self._create_empty_result('user_not_found')
            
            # Get user segment info
            user_segment = get_user_segment_info(user_id)
            
            # Find matching routes
            matching_routes = self._find_matching_routes(user, user_segment, context)
            
            if not matching_routes:
                # Try fallback
                fallback_result = self._handle_fallback(user, context)
                if fallback_result:
                    return fallback_result
                else:
                    return self._create_empty_result('no_routes_match')
            
            # Score and rank offers
            scored_offers = self._score_and_rank_offers(user, matching_routes, context)
            
            # Apply personalization
            personalized_offers = self._apply_personalization(user, scored_offers, context)
            
            # Check caps
            capped_offers = self._check_caps(user, personalized_offers)
            
            # Apply A/B testing
            final_offers = self._apply_ab_testing(user, capped_offers, context)
            
            # Limit results
            limited_offers = final_offers[:limit]
            
            # Create result
            result = self._create_routing_result(user, limited_offers, context)
            
            # Cache result
            if cache_enabled:
                self._cache_routing_result(user_id, context, result)
            
            # Log decision
            self._log_routing_decision(user, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Routing error for user {user_id}: {e}")
            return self._create_empty_result('routing_error', str(e))
        
        finally:
            # Check performance
            self._check_performance()
    
    def _get_cached_routing(self, user_id: int, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached routing result."""
        try:
            context_hash = hash_context(context)
            cache_key = generate_cache_key('routing', user_id=user_id, context_hash=context_hash)
            
            result = self.cache_service.get(cache_key)
            if result:
                logger.debug(f"Cache hit for routing: {cache_key}")
                return result
            
            return None
            
        except Exception as e:
            logger.warning(f"Cache error: {e}")
            return None
    
    def _cache_routing_result(self, user_id: int, context: Dict[str, Any], result: Dict[str, Any]):
        """Cache routing result."""
        try:
            context_hash = hash_context(context)
            cache_key = generate_cache_key('routing', user_id=user_id, context_hash=context_hash)
            
            self.cache_service.set(cache_key, result, timeout=ROUTING_CACHE_TIMEOUT)
            logger.debug(f"Cached routing result: {cache_key}")
            
        except Exception as e:
            logger.warning(f"Cache error: {e}")
    
    def _get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
    
    def _find_matching_routes(self, user: User, user_segment: Dict[str, Any], 
                            context: Dict[str, Any]) -> List[OfferRoute]:
        """Find routes that match user and context with memory management."""
        try:
            # Get active routes for user's tenant with prefetch to reduce queries
            routes = OfferRoute.objects.filter(
                tenant=user.tenant,
                is_active=True
            ).prefetch_related(
                'geo_rules', 'device_rules', 'segment_rules', 
                'time_rules', 'behavior_rules'
            ).order_by('priority')
            
            matching_routes = []
            batch_size = 50  # Process in batches to limit memory usage
            
            for i in range(0, len(routes), batch_size):
                route_batch = routes[i:i + batch_size]
                
                for route in route_batch:
                    try:
                        # Check if route matches
                        if self.targeting_service.matches_route(route, user, user_segment, context):
                            matching_routes.append(route)
                    except Exception as e:
                        logger.error(f"Error matching route {route.id}: {e}")
                        continue
                
                # Explicit cleanup of batch reference
                del route_batch
                
                # Force garbage collection after each batch
                if i % (batch_size * 2) == 0:
                    import gc
                    gc.collect()
            
            logger.info(f"Found {len(matching_routes)} matching routes for user {user.id}")
            return matching_routes
            
        except Exception as e:
            logger.error(f"Error finding matching routes: {e}")
            return []
    
    def _score_and_rank_offers(self, user: User, routes: List[OfferRoute], 
                            context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Score and rank offers from matching routes with memory management."""
        try:
            scored_offers = []
            batch_size = 25  # Smaller batch size for memory efficiency
            
            for i in range(0, len(routes), batch_size):
                route_batch = routes[i:i + batch_size]
                
                for route in route_batch:
                    try:
                        # Get offers for this route
                        route_offers = self._get_route_offers(route, user)
                        
                        # Process offers in smaller sub-batches
                        for j in range(0, len(route_offers), 10):
                            offer_sub_batch = route_offers[j:j + 10]
                            
                            for offer in offer_sub_batch:
                                try:
                                    # Calculate score
                                    score_data = self.scoring_service.calculate_offer_score(
                                        offer=offer,
                                        user=user,
                                        context=context
                                    )
                                    
                                    # Only store essential data to reduce memory footprint
                                    scored_offers.append({
                                        'offer_id': offer.id,
                                        'route_id': route.id,
                                        'score': score_data['score'],
                                        'rank': 0
                                    })
                                    
                                    # Explicit cleanup of score_data
                                    del score_data
                                    
                                except Exception as e:
                                    logger.error(f"Error scoring offer {offer.id}: {e}")
                                    continue
                            
                            # Cleanup sub-batch
                            del offer_sub_batch
                        
                        # Cleanup route_offers
                        del route_offers
                        
                    except Exception as e:
                        logger.error(f"Error processing route {route.id}: {e}")
                        continue
                
                # Cleanup batch reference
                del route_batch
                
                # Force garbage collection after each batch
                if i % (batch_size * 2) == 0:
                    import gc
                    gc.collect()
            
            # Sort by score (descending)
            scored_offers.sort(key=lambda x: x['score'], reverse=True)
            
            # Set ranks
            for i, offer_data in enumerate(scored_offers):
                offer_data['rank'] = i + 1
            
            logger.info(f"Scored {len(scored_offers)} offers for user {user.id}")
            return scored_offers
            
        except Exception as e:
            logger.error(f"Error scoring offers: {e}")
            return []
    
    def _get_route_offers(self, route: OfferRoute, user: User) -> List[Any]:
        """Get offers for a route."""
        # This would get offers based on route configuration
        # For now, return placeholder
        return []
    
    def _apply_personalization(self, user: User, scored_offers: List[Dict[str, Any]], 
                             context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply personalization to scored offers with memory management."""
        try:
            if not self.personalization_service.is_enabled(user):
                return scored_offers
            
            personalized_offers = []
            batch_size = 30  # Process in batches for memory efficiency
            
            for i in range(0, len(scored_offers), batch_size):
                offer_batch = scored_offers[i:i + batch_size]
                
                for offer_data in offer_batch:
                    try:
                        # Apply personalization
                        personalization_data = self.personalization_service.apply_personalization(
                            user=user,
                            offer_id=offer_data['offer_id'],
                            context=context
                        )
                        
                        # Update score with personalization
                        if personalization_data.get('personalization_score', 0) > 0:
                            adjusted_score = offer_data['score'] * (1 + personalization_data['personalization_score'])
                            offer_data['score'] = min(adjusted_score, 100.0)
                            offer_data['personalization_applied'] = True
                        else:
                            offer_data['personalization_applied'] = False
                        
                        # Store minimal personalization data
                        if 'personalization_score' in personalization_data:
                            offer_data['personalization_score'] = personalization_data['personalization_score']
                        
                        personalized_offers.append(offer_data)
                        
                        # Explicit cleanup of personalization_data
                        del personalization_data
                        
                    except Exception as e:
                        logger.error(f"Error applying personalization to offer {offer_data.get('offer_id')}: {e}")
                        # Add offer without personalization
                        offer_data['personalization_applied'] = False
                        personalized_offers.append(offer_data)
                        continue
                
                # Cleanup batch reference
                del offer_batch
                
                # Force garbage collection after each batch
                if i % (batch_size * 2) == 0:
                    import gc
                    gc.collect()
            
            # Re-sort after personalization
            personalized_offers.sort(key=lambda x: x['score'], reverse=True)
            
            # Update ranks
            for i, offer_data in enumerate(personalized_offers):
                offer_data['rank'] = i + 1
            
            logger.info(f"Applied personalization to {len(personalized_offers)} offers")
            return personalized_offers
            
        except Exception as e:
            logger.error(f"Error applying personalization: {e}")
            return scored_offers
    
    def _check_caps(self, user: User, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check and enforce caps on offers."""
        try:
            capped_offers = []
            
            for offer_data in offers:
                # Check caps
                cap_result = self.cap_service.check_offer_cap(
                    user=user,
                    offer=offer_data['offer']
                )
                
                if cap_result['allowed']:
                    offer_data['caps_checked'] = True
                    offer_data['cap_data'] = cap_result
                    capped_offers.append(offer_data)
                else:
                    logger.info(f"Offer {offer_data['offer'].id} capped for user {user.id}")
            
            logger.info(f"Applied caps, {len(capped_offers)} offers remaining")
            return capped_offers
            
        except Exception as e:
            logger.error(f"Error checking caps: {e}")
            return offers
    
    def _apply_ab_testing(self, user: User, offers: List[Dict[str, Any]], 
                         context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply A/B testing to offers."""
        try:
            if not self.ab_test_service.is_enabled(user):
                return offers
            
            ab_tested_offers = []
            
            for offer_data in offers:
                # Check A/B test assignment
                ab_test_assignment = self.ab_test_service.get_assignment(
                    user=user,
                    offer=offer_data['offer']
                )
                
                if ab_test_assignment:
                    offer_data['ab_test_applied'] = True
                    offer_data['ab_test_data'] = ab_test_assignment
                else:
                    offer_data['ab_test_applied'] = False
                
                ab_tested_offers.append(offer_data)
            
            logger.info(f"Applied A/B testing to {len(ab_tested_offers)} offers")
            return ab_tested_offers
            
        except Exception as e:
            logger.error(f"Error applying A/B testing: {e}")
            return offers
    
    def _handle_fallback(self, user: User, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle fallback when no routes match."""
        try:
            fallback_result = self.fallback_service.get_fallback_offers(
                user=user,
                context=context
            )
            
            if fallback_result:
                return self._create_routing_result(user, fallback_result, context, is_fallback=True)
            
            return None
            
        except Exception as e:
            logger.error(f"Error handling fallback: {e}")
            return None
    
    def _create_routing_result(self, user: User, offers: List[Dict[str, Any]], 
                             context: Dict[str, Any], is_fallback: bool = False) -> Dict[str, Any]:
        """Create routing result object."""
        response_time_ms = int((time.time() - self.start_time) * 1000)
        
        result = {
            'success': True,
            'user_id': user.id,
            'offers': [],
            'metadata': {
                'total_offers': len(offers),
                'response_time_ms': response_time_ms,
                'cache_hit': False,
                'personalization_applied': any(offer.get('personalization_applied', False) for offer in offers),
                'caps_checked': any(offer.get('caps_checked', False) for offer in offers),
                'ab_test_applied': any(offer.get('ab_test_applied', False) for offer in offers),
                'is_fallback': is_fallback,
                'timestamp': timezone.now().isoformat()
            }
        }
        
        # Add offer data
        for offer_data in offers:
            offer_info = {
                'offer_id': offer_data['offer'].id,
                'offer_name': offer_data['offer'].name,
                'route_id': offer_data['route'].id,
                'route_name': offer_data['route'].name,
                'score': offer_data['score'],
                'rank': offer_data['rank'],
                'personalization_applied': offer_data.get('personalization_applied', False),
                'caps_checked': offer_data.get('caps_checked', False),
                'ab_test_applied': offer_data.get('ab_test_applied', False)
            }
            
            # Add additional data if available
            if 'score_data' in offer_data:
                offer_info['score_data'] = offer_data['score_data']
            
            if 'personalization_data' in offer_data:
                offer_info['personalization_data'] = offer_data['personalization_data']
            
            if 'cap_data' in offer_data:
                offer_info['cap_data'] = offer_data['cap_data']
            
            if 'ab_test_data' in offer_data:
                offer_info['ab_test_data'] = offer_data['ab_test_data']
            
            result['offers'].append(offer_info)
        
        return result
    
    def _create_empty_result(self, reason: str, error_message: str = None) -> Dict[str, Any]:
        """Create empty routing result."""
        response_time_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        
        result = {
            'success': False,
            'offers': [],
            'metadata': {
                'total_offers': 0,
                'response_time_ms': response_time_ms,
                'cache_hit': False,
                'personalization_applied': False,
                'caps_checked': False,
                'ab_test_applied': False,
                'is_fallback': False,
                'reason': reason,
                'error_message': error_message,
                'timestamp': timezone.now().isoformat()
            }
        }
        
        return result
    
    def _log_routing_decision(self, user: User, result: Dict[str, Any]):
        """Log routing decision for analytics."""
        try:
            for offer_info in result['offers']:
                RoutingDecisionLog.objects.create(
                    user=user,
                    offer_id=offer_info['offer_id'],
                    route_id=offer_info['route_id'],
                    reason='route_match' if not result['metadata']['is_fallback'] else 'fallback',
                    score=offer_info['score'],
                    rank=offer_info['rank'],
                    response_time_ms=result['metadata']['response_time_ms'],
                    cache_hit=result['metadata']['cache_hit'],
                    personalization_applied=offer_info['personalization_applied'],
                    caps_checked=offer_info['caps_checked'],
                    fallback_used=result['metadata']['is_fallback']
                )
            
            logger.info(f"Logged {len(result['offers'])} routing decisions for user {user.id}")
            
            # Get performance statistics
            stats = decisions.aggregate(
                total_decisions=models.Count('id'),
                avg_response_time=models.Avg('response_time_ms'),
                cache_hit_rate=models.Avg('cache_hit'),
                personalization_rate=models.Avg('personalization_applied'),
                caps_check_rate=models.Avg('caps_checked'),
                fallback_rate=models.Avg('fallback_used')
            )
            
            stats = decisions.aggregate(
                total_decisions=models.Count('id'),
                avg_response_time=models.Avg('response_time_ms'),
                cache_hit_rate=models.Avg('cache_hit'),
                personalization_rate=models.Avg('personalization_applied'),
                caps_check_rate=models.Avg('caps_checked'),
                fallback_rate=models.Avg('fallback_used')
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting routing stats: {e}")
            return {}
    
    def optimize_routing_configurations(self) -> int:
        """Optimize routing configurations based on performance data."""
        try:
            optimized_count = 0
            
            # This would implement configuration optimization logic
            # For now, return placeholder
            return optimized_count
            
        except Exception as e:
            logger.error(f"Error optimizing routing configurations: {e}")
            return 0
    
    def sync_external_offers(self) -> int:
        """Synchronize offers from external sources."""
        try:
            synced_count = 0
            
            # This would implement external offer synchronization
            # For now, return placeholder
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing external offers: {e}")
            return 0
    
    def _check_performance(self):
        """Check performance metrics and memory usage."""
        if self.start_time:
            elapsed_time = (time.time() - self.start_time) * 1000  # Convert to ms
            
            if elapsed_time > MAX_ROUTING_TIME_MS:
                logger.warning(f"Routing took {elapsed_time:.2f}ms (threshold: {MAX_ROUTING_TIME_MS}ms)")
            
            # Check memory usage
            memory_info = self._get_memory_usage()
            if memory_info['rss_mb'] > 100:  # Alert if using more than 100MB
                logger.warning(f"High memory usage: {memory_info['rss_mb']:.2f}MB RSS")
            
            # Log performance metrics
            logger.debug(f"Routing completed in {elapsed_time:.2f}ms, Memory: {memory_info['rss_mb']:.2f}MB")
    
    def _get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size in MB
                'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size in MB
                'percent': process.memory_percent()  # Memory usage percentage
            }
        except ImportError:
            # Fallback if psutil is not available
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}
    
    def _cleanup_memory(self):
        """Force memory cleanup and garbage collection."""
        try:
            import gc
            
            # Collect garbage
            collected = gc.collect()
            
            # Get memory usage before and after cleanup
            memory_before = self._get_memory_usage()
            
            # Force aggressive collection
            for i in range(3):
                gc.collect()
            
            memory_after = self._get_memory_usage()
            
            memory_freed = memory_before['rss_mb'] - memory_after['rss_mb']
            
            if memory_freed > 1:  # Only log if significant memory was freed
                logger.info(f"Memory cleanup freed {memory_freed:.2f}MB (from {memory_before['rss_mb']:.2f}MB to {memory_after['rss_mb']:.2f}MB)")
            
            return {
                'objects_collected': collected,
                'memory_freed_mb': memory_freed,
                'memory_before_mb': memory_before['rss_mb'],
                'memory_after_mb': memory_after['rss_mb']
            }
            
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
            return {'objects_collected': 0, 'memory_freed_mb': 0}


# Singleton instance
routing_engine = OfferRoutingEngine()
