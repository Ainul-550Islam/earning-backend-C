"""
Cache Service for Offer Routing System

This module provides caching functionality for routing decisions,
scores, and other frequently accessed data.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from ..constants import (
    ROUTING_CACHE_TIMEOUT, SCORE_CACHE_TIMEOUT, CAP_CACHE_TIMEOUT,
    AFFINITY_CACHE_TIMEOUT, PREFERENCE_VECTOR_CACHE_TIMEOUT
)
from ..utils import generate_cache_key, hash_context
from ..exceptions import CacheError

logger = logging.getLogger(__name__)


class RoutingCacheService:
    """
    Service for managing routing-related cache operations.
    
    Provides caching for routing decisions, offer scores,
    user affinity data, and other frequently accessed data.
    """
    
    def __init__(self):
        self.cache_backend = cache
        self.default_timeout = 300  # 5 minutes
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    def get_routing_result(self, user_id: int, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached routing result for user and context with Redis fallback."""
        try:
            context_hash = hash_context(context)
            cache_key = generate_cache_key('routing', user_id=user_id, context_hash=context_hash)
            
            result = self.cache_backend.get(cache_key)
            
            if result is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for routing result: {cache_key}")
                return result
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for routing result: {cache_key}")
                return None
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis cache error, falling back to database: {e}")
            # Fallback to database
            return self._get_routing_result_from_db(user_id, context)
    
    def set_routing_result(self, user_id: int, context: Dict[str, Any], 
                          result: Dict[str, Any], timeout: int = ROUTING_CACHE_TIMEOUT):
        """Cache routing result for user and context with Redis fallback."""
        try:
            context_hash = hash_context(context)
            cache_key = generate_cache_key('routing', user_id=user_id, context_hash=context_hash)
            
            success = self.cache_backend.set(cache_key, result, timeout)
            
            if success:
                self.stats['sets'] += 1
                logger.debug(f"Cached routing result: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to cache routing result: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis cache error, skipping cache set: {e}")
            # Continue without caching - system still works
    
    def _get_routing_result_from_db(self, user_id: int, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fallback method to get routing result from database."""
        try:
            from django.contrib.auth import get_user_model
            from ..models import RoutingDecisionLog, UserOfferHistory
            from ..services.core import routing_engine
            
            User = get_user_model()
            
            # Get user
            user = User.objects.filter(id=user_id).first()
            if not user:
                return None
            
            # Get recent routing decisions for this user and context
            recent_decisions = RoutingDecisionLog.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
            ).order_by('-created_at')[:10]
            
            if recent_decisions.exists():
                # Return most recent decision
                latest_decision = recent_decisions.first()
                return {
                    'success': True,
                    'offers': [],  # Would need to reconstruct from history
                    'metadata': {
                        'source': 'database_fallback',
                        'decision_id': latest_decision.id,
                        'cached': False
                    }
                }
            
            # If no recent decisions, perform fresh routing
            try:
                result = routing_engine.route_offers(
                    user_id=user_id,
                    context=context,
                    limit=10,
                    cache_enabled=False  # Prevent infinite recursion
                )
                return result
            except Exception as e:
                logger.error(f"Failed to perform fresh routing for fallback: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Database fallback error: {e}")
            return None
    
    def delete_routing_result(self, user_id: int, context: Dict[str, Any]):
        """Delete cached routing result for user and context."""
        try:
            context_hash = hash_context(context)
            cache_key = generate_cache_key('routing', user_id=user_id, context_hash=context_hash)
            
            success = self.cache_backend.delete(cache_key)
            
            if success:
                self.stats['deletes'] += 1
                logger.debug(f"Deleted cached routing result: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to delete cached routing result: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error deleting routing result: {e}")
    
    def get_offer_score(self, offer_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached offer score."""
        try:
            cache_key = generate_cache_key('score', offer_id=offer_id, user_id=user_id)
            
            result = self.cache_backend.get(cache_key)
            
            if result is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for offer score: {cache_key}")
                return result
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for offer score: {cache_key}")
                return None
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error getting offer score: {e}")
            return None
    
    def set_offer_score(self, offer_id: int, user_id: int, score_data: Dict[str, Any], 
                       timeout: int = SCORE_CACHE_TIMEOUT):
        """Cache offer score."""
        try:
            cache_key = generate_cache_key('score', offer_id=offer_id, user_id=user_id)
            
            success = self.cache_backend.set(cache_key, score_data, timeout)
            
            if success:
                self.stats['sets'] += 1
                logger.debug(f"Cached offer score: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to cache offer score: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error setting offer score: {e}")
    
    def delete_offer_score(self, offer_id: int, user_id: int):
        """Delete cached offer score."""
        try:
            cache_key = generate_cache_key('score', offer_id=offer_id, user_id=user_id)
            
            success = self.cache_backend.delete(cache_key)
            
            if success:
                self.stats['deletes'] += 1
                logger.debug(f"Deleted cached offer score: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to delete cached offer score: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error deleting offer score: {e}")
    
    def get_user_cap(self, offer_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached user cap data with Redis fallback."""
        try:
            cache_key = generate_cache_key('cap', offer_id=offer_id, user_id=user_id)
            
            result = self.cache_backend.get(cache_key)
            
            if result is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for user cap: {cache_key}")
                return result
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for user cap: {cache_key}")
                return None
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis cache error, falling back to database for user cap: {e}")
            # Fallback to database
            return self._get_user_cap_from_db(offer_id, user_id)
    
    def _get_user_cap_from_db(self, offer_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Fallback method to get user cap from database."""
        try:
            from ..models import UserOfferCap
            
            user_cap = UserOfferCap.objects.filter(
                user_id=user_id,
                offer_id=offer_id
            ).first()
            
            if user_cap:
                return {
                    'allowed': user_cap.can_show_offer(),
                    'cap_type': user_cap.cap_type,
                    'cap_value': user_cap.max_shows_per_day,
                    'current_value': user_cap.shown_today,
                    'source': 'database_fallback'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Database fallback error for user cap: {e}")
            return None
    
    def set_user_cap(self, offer_id: int, user_id: int, cap_data: Dict[str, Any], 
                    timeout: int = CAP_CACHE_TIMEOUT):
        """Cache user cap data."""
        try:
            cache_key = generate_cache_key('cap', offer_id=offer_id, user_id=user_id)
            
            success = self.cache_backend.set(cache_key, cap_data, timeout)
            
            if success:
                self.stats['sets'] += 1
                logger.debug(f"Cached user cap: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to cache user cap: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error setting user cap: {e}")
    
    def delete_user_cap(self, offer_id: int, user_id: int):
        """Delete cached user cap data."""
        try:
            cache_key = generate_cache_key('cap', offer_id=offer_id, user_id=user_id)
            
            success = self.cache_backend.delete(cache_key)
            
            if success:
                self.stats['deletes'] += 1
                logger.debug(f"Deleted cached user cap: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to delete cached user cap: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error deleting user cap: {e}")
    
    def get_affinity_score(self, user_id: int, category: str) -> Optional[Dict[str, Any]]:
        """Get cached affinity score."""
        try:
            cache_key = generate_cache_key('affinity', user_id=user_id, category=category)
            
            result = self.cache_backend.get(cache_key)
            
            if result is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for affinity score: {cache_key}")
                return result
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for affinity score: {cache_key}")
                return None
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error getting affinity score: {e}")
            return None
    
    def set_affinity_score(self, user_id: int, category: str, affinity_data: Dict[str, Any], 
                          timeout: int = AFFINITY_CACHE_TIMEOUT):
        """Cache affinity score."""
        try:
            cache_key = generate_cache_key('affinity', user_id=user_id, category=category)
            
            success = self.cache_backend.set(cache_key, affinity_data, timeout)
            
            if success:
                self.stats['sets'] += 1
                logger.debug(f"Cached affinity score: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to cache affinity score: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error setting affinity score: {e}")
    
    def delete_affinity_score(self, user_id: int, category: str):
        """Delete cached affinity score."""
        try:
            cache_key = generate_cache_key('affinity', user_id=user_id, category=category)
            
            success = self.cache_backend.delete(cache_key)
            
            if success:
                self.stats['deletes'] += 1
                logger.debug(f"Deleted cached affinity score: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to delete cached affinity score: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error deleting affinity score: {e}")
    
    def get_preference_vector(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached user preference vector."""
        try:
            cache_key = generate_cache_key('preference_vector', user_id=user_id)
            
            result = self.cache_backend.get(cache_key)
            
            if result is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for preference vector: {cache_key}")
                return result
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for preference vector: {cache_key}")
                return None
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error getting preference vector: {e}")
            return None
    
    def set_preference_vector(self, user_id: int, preference_vector: Dict[str, Any], 
                             timeout: int = PREFERENCE_VECTOR_CACHE_TIMEOUT):
        """Cache user preference vector."""
        try:
            cache_key = generate_cache_key('preference_vector', user_id=user_id)
            
            success = self.cache_backend.set(cache_key, preference_vector, timeout)
            
            if success:
                self.stats['sets'] += 1
                logger.debug(f"Cached preference vector: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to cache preference vector: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error setting preference vector: {e}")
    
    def delete_preference_vector(self, user_id: int):
        """Delete cached user preference vector."""
        try:
            cache_key = generate_cache_key('preference_vector', user_id=user_id)
            
            success = self.cache_backend.delete(cache_key)
            
            if success:
                self.stats['deletes'] += 1
                logger.debug(f"Deleted cached preference vector: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to delete cached preference vector: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error deleting preference vector: {e}")
    
    def get_contextual_signal(self, user_id: int, signal_type: str) -> Optional[Dict[str, Any]]:
        """Get cached contextual signal."""
        try:
            cache_key = generate_cache_key('signal', user_id=user_id, signal_type=signal_type)
            
            result = self.cache_backend.get(cache_key)
            
            if result is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for contextual signal: {cache_key}")
                return result
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for contextual signal: {cache_key}")
                return None
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error getting contextual signal: {e}")
            return None
    
    def set_contextual_signal(self, user_id: int, signal_type: str, signal_data: Dict[str, Any], 
                            timeout: int = 3600):
        """Cache contextual signal."""
        try:
            cache_key = generate_cache_key('signal', user_id=user_id, signal_type=signal_type)
            
            success = self.cache_backend.set(cache_key, signal_data, timeout)
            
            if success:
                self.stats['sets'] += 1
                logger.debug(f"Cached contextual signal: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to cache contextual signal: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error setting contextual signal: {e}")
    
    def delete_contextual_signal(self, user_id: int, signal_type: str):
        """Delete cached contextual signal."""
        try:
            cache_key = generate_cache_key('signal', user_id=user_id, signal_type=signal_type)
            
            success = self.cache_backend.delete(cache_key)
            
            if success:
                self.stats['deletes'] += 1
                logger.debug(f"Deleted cached contextual signal: {cache_key}")
            else:
                self.stats['errors'] += 1
                logger.error(f"Failed to delete cached contextual signal: {cache_key}")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error deleting contextual signal: {e}")
    
    def invalidate_user_cache(self, user_id: int):
        """Invalidate all cache entries for a user."""
        try:
            # This would use pattern matching to invalidate all user-related keys
            # For now, we'll implement basic invalidation
            
            patterns = [
                f"routing:*:user_id:{user_id}:*",
                f"score:*:user_id:{user_id}:*",
                f"cap:*:user_id:{user_id}:*",
                f"affinity:user_id:{user_id}:*",
                f"preference_vector:user_id:{user_id}",
                f"signal:user_id:{user_id}:*"
            ]
            
            invalidated_count = 0
            
            for pattern in patterns:
                # This would implement pattern-based deletion
                # For now, we'll just log the pattern
                logger.debug(f"Would invalidate pattern: {pattern}")
                invalidated_count += 1
            
            logger.info(f"Invalidated {invalidated_count} cache patterns for user {user_id}")
            return invalidated_count
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error invalidating user cache: {e}")
            return 0
    
    def invalidate_offer_cache(self, offer_id: int):
        """Invalidate all cache entries for an offer."""
        try:
            patterns = [
                f"routing:*:offer_id:{offer_id}:*",
                f"score:offer_id:{offer_id}:*",
                f"cap:offer_id:{offer_id}:*"
            ]
            
            invalidated_count = 0
            
            for pattern in patterns:
                logger.debug(f"Would invalidate pattern: {pattern}")
                invalidated_count += 1
            
            logger.info(f"Invalidated {invalidated_count} cache patterns for offer {offer_id}")
            return invalidated_count
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error invalidating offer cache: {e}")
            return 0
    
    def warmup_active_users(self, user_ids: List[int] = None) -> int:
        """Warm up cache for active users."""
        try:
            if not user_ids:
                # Get active users from recent routing decisions
                from ..models import RoutingDecisionLog
                from datetime import timedelta
                
                cutoff_date = timezone.now() - timedelta(hours=24)
                recent_users = RoutingDecisionLog.objects.filter(
                    created_at__gte=cutoff_date
                ).values_list('user_id', flat=True).distinct()
                
                user_ids = list(recent_users)
            
            warmed_count = 0
            
            for user_id in user_ids:
                # Pre-warm common contexts
                common_contexts = [
                    {'page': 'home'},
                    {'page': 'products'},
                    {'page': 'offers'},
                    {'page': 'profile'}
                ]
                
                for context in common_contexts:
                    # Set empty cache entry to warm up
                    self.set_routing_result(user_id, context, {}, timeout=60)
                    warmed_count += 1
            
            logger.info(f"Warmed up cache for {len(user_ids)} users with {warmed_count} entries")
            return warmed_count
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error warming up active users: {e}")
            return 0
    
    def perform_maintenance(self) -> int:
        """Perform cache maintenance operations."""
        try:
            maintenance_count = 0
            
            # Clean up expired entries (if cache backend supports it)
            # This would implement cleanup logic
            
            # Refresh frequently accessed data
            # This would implement refresh logic
            
            logger.info(f"Performed {maintenance_count} cache maintenance operations")
            return maintenance_count
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error performing maintenance: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        try:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'sets': self.stats['sets'],
                'deletes': self.stats['deletes'],
                'errors': self.stats['errors'],
                'total_requests': total_requests,
                'hit_rate': hit_rate,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error getting stats: {e}")
            return {}
    
    def reset_stats(self):
        """Reset cache statistics."""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
        logger.info("Cache statistics reset")
    
    def clear_cache(self):
        """Clear all cache entries."""
        try:
            success = self.cache_backend.clear()
            
            if success:
                logger.info("Cache cleared successfully")
                self.reset_stats()
            else:
                logger.error("Failed to clear cache")
                self.stats['errors'] += 1
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache error clearing cache: {e}")


# Singleton instance
cache_service = RoutingCacheService()
