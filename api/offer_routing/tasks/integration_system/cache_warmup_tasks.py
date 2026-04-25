"""
Cache Warmup Tasks

Periodic tasks for pre-warming routing cache
for active users and popular offers.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.core import RoutingCacheService
from ..services.analytics import analytics_service
from ..models import OfferRoute, UserOfferHistory
from ..constants import CACHE_WARMUP_INTERVAL, CACHE_WARMUP_BATCH_SIZE
from ..exceptions import CacheError

logger = logging.getLogger(__name__)

User = get_user_model()


class CacheWarmupTask:
    """
    Task for pre-warming routing cache.
    
    Runs periodically to:
    - Pre-warm cache for active users
    - Pre-warm cache for popular offers
    - Pre-warm cache for recent routes
    - Optimize cache hit rates
    - Monitor cache performance
    """
    
    def __init__(self):
        self.cache_service = RoutingCacheService()
        self.analytics_service = analytics_service
        self.task_stats = {
            'total_warmups': 0,
            'successful_warmups': 0,
            'failed_warmups': 0,
            'cache_entries_warmed': 0,
            'avg_warmup_time_ms': 0.0
        }
    
    def run_cache_warmup(self) -> Dict[str, Any]:
        """
        Run the cache warmup task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get warmup targets
            warmup_targets = self._get_warmup_targets()
            
            if not warmup_targets:
                logger.info("No cache warmup targets found")
                return {
                    'success': True,
                    'message': 'No cache warmup targets found',
                    'cache_entries_warmed': 0,
                    'execution_time_ms': 0,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Perform warmup for each target
            warmed_entries = 0
            failed_targets = 0
            
            for target in warmup_targets:
                try:
                    result = self._warmup_target(target)
                    
                    if result['success']:
                        warmed_entries += result['entries_warmed']
                        logger.info(f"Warmed up {result['entries_warmed']} cache entries for {target['type']} {target['id']}")
                    else:
                        failed_targets += 1
                        logger.error(f"Failed to warm up cache for {target['type']} {target['id']}: {result['error']}")
                        
                except Exception as e:
                    failed_targets += 1
                    logger.error(f"Error warming up cache for {target['type']} {target['id']}: {e}")
            
            # Update task statistics
            self._update_task_stats(start_time, warmed_entries, failed_targets)
            
            return {
                'success': True,
                'message': 'Cache warmup task completed',
                'targets_processed': len(warmup_targets),
                'targets_failed': failed_targets,
                'cache_entries_warmed': warmed_entries,
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in cache warmup task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_warmup_targets(self) -> List[Dict[str, Any]]:
        """Get targets for cache warmup."""
        try:
            targets = []
            
            # Active users (recent activity)
            active_users = self._get_active_users()
            for user in active_users:
                targets.append({
                    'type': 'user',
                    'id': user.id,
                    'data': {
                        'user_id': user.id,
                        'username': user.username,
                        'last_activity': user.last_login,
                        'cache_keys': self._generate_user_cache_keys(user)
                    }
                })
            
            # Popular offers (high traffic)
            popular_offers = self._get_popular_offers()
            for offer in popular_offers:
                targets.append({
                    'type': 'offer',
                    'id': offer.id,
                    'data': {
                        'offer_id': offer.id,
                        'offer_name': offer.name,
                        'popularity_score': getattr(offer, 'popularity_score', 0),
                        'cache_keys': self._generate_offer_cache_keys(offer)
                    }
                })
            
            # Recent routes (frequently accessed)
            recent_routes = self._get_recent_routes()
            for route in recent_routes:
                targets.append({
                    'type': 'route',
                    'id': route.id,
                    'data': {
                        'route_id': route.id,
                        'route_name': route.name,
                        'access_frequency': getattr(route, 'access_frequency', 0),
                        'cache_keys': self._generate_route_cache_keys(route)
                    }
                })
            
            return targets
            
        except Exception as e:
            logger.error(f"Error getting warmup targets: {e}")
            return []
    
    def _get_active_users(self) -> List[User]:
        """Get recently active users for cache warmup."""
        try:
            # Get users with recent activity
            cutoff_time = timezone.now() - timezone.timedelta(hours=24)
            
            active_users = User.objects.filter(
                last_login__gte=cutoff_time,
                is_active=True
            ).order_by('-last_login')[:50]  # Limit to 50 users
            
            logger.info(f"Found {len(active_users)} active users for cache warmup")
            return active_users
            
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
    
    def _get_popular_offers(self) -> List[OfferRoute]:
        """Get popular offers for cache warmup."""
        try:
            # Get offers with high activity in last 7 days
            cutoff_time = timezone.now() - timezone.timedelta(days=7)
            
            popular_offers = OfferRoute.objects.filter(
                is_active=True,
                userofferhistory__created_at__gte=cutoff_time
            ).annotate(
                activity_count=Count('userofferhistory'),
                total_views=Count('userofferhistory'),
                total_clicks=Count('userofferhistory', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('userofferhistory', filter=Q(completed_at__isnull=False))
            ).filter(
                activity_count__gt=10  # At least 10 activities
            ).order_by('-activity_count')[:100]  # Top 100 offers
            
            logger.info(f"Found {len(popular_offers)} popular offers for cache warmup")
            return popular_offers
            
        except Exception as e:
            logger.error(f"Error getting popular offers: {e}")
            return []
    
    def _get_recent_routes(self) -> List[OfferRoute]:
        """Get recently accessed routes for cache warmup."""
        try:
            # Get routes with recent activity
            cutoff_time = timezone.now() - timezone.timedelta(hours=6)
            
            recent_routes = OfferRoute.objects.filter(
                is_active=True,
                updated_at__gte=cutoff_time
            ).order_by('-updated_at')[:50]  # Top 50 routes
            
            logger.info(f"Found {len(recent_routes)} recent routes for cache warmup")
            return recent_routes
            
        except Exception as e:
            logger.error(f"Error getting recent routes: {e}")
            return []
    
    def _warmup_target(self, target: Dict[str, Any]) -> Dict[str, Any]:
        """Warm up cache for a specific target."""
        try:
            target_type = target['type']
            target_data = target['data']
            
            if target_type == 'user':
                return self._warmup_user_cache(target_data)
            elif target_type == 'offer':
                return self._warmup_offer_cache(target_data)
            elif target_type == 'route':
                return self._warmup_route_cache(target_data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown target type: {target_type}',
                    'entries_warmed': 0
                }
                
        except Exception as e:
            logger.error(f"Error warming up target {target_type}: {e}")
            return {
                'success': False,
                'error': str(e),
                'entries_warmed': 0
            }
    
    def _warmup_user_cache(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Warm up cache for a specific user."""
        try:
            user_id = user_data['user_id']
            cache_keys = user_data['cache_keys']
            
            warmed_entries = 0
            errors = []
            
            for cache_key in cache_keys:
                try:
                    # Generate user-specific cache data
                    cache_data = self._generate_user_cache_data(user_id)
                    
                    # Set cache with appropriate TTL
                    cache.set(cache_key, cache_data, timeout=3600)  # 1 hour
                    
                    warmed_entries += 1
                    
                except Exception as e:
                    errors.append(f"Error warming cache key {cache_key}: {e}")
            
            return {
                'success': len(errors) == 0,
                'entries_warmed': warmed_entries,
                'errors': errors,
                'user_id': user_id
            }
            
        except Exception as e:
            logger.error(f"Error warming user cache: {e}")
            return {
                'success': False,
                'error': str(e),
                'entries_warmed': 0
            }
    
    def _warmup_offer_cache(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Warm up cache for a specific offer."""
        try:
            offer_id = offer_data['offer_id']
            cache_keys = offer_data['cache_keys']
            
            warmed_entries = 0
            errors = []
            
            for cache_key in cache_keys:
                try:
                    # Generate offer-specific cache data
                    cache_data = self._generate_offer_cache_data(offer_id)
                    
                    # Set cache with appropriate TTL
                    cache.set(cache_key, cache_data, timeout=7200)  # 2 hours
                    
                    warmed_entries += 1
                    
                except Exception as e:
                    errors.append(f"Error warming cache key {cache_key}: {e}")
            
            return {
                'success': len(errors) == 0,
                'entries_warmed': warmed_entries,
                'errors': errors,
                'offer_id': offer_id
            }
            
        except Exception as e:
            logger.error(f"Error warming offer cache: {e}")
            return {
                'success': False,
                'error': str(e),
                'entries_warmed': 0
            }
    
    def _warmup_route_cache(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """Warm up cache for a specific route."""
        try:
            route_id = route_data['route_id']
            cache_keys = route_data['cache_keys']
            
            warmed_entries = 0
            errors = []
            
            for cache_key in cache_keys:
                try:
                    # Generate route-specific cache data
                    cache_data = self._generate_route_cache_data(route_id)
                    
                    # Set cache with appropriate TTL
                    cache.set(cache_key, cache_data, timeout=1800)  # 30 minutes
                    
                    warmed_entries += 1
                    
                except Exception as e:
                    errors.append(f"Error warming cache key {cache_key}: {e}")
            
            return {
                'success': len(errors) == 0,
                'entries_warmed': warmed_entries,
                'errors': errors,
                'route_id': route_id
            }
            
        except Exception as e:
            logger.error(f"Error warming route cache: {e}")
            return {
                'success': False,
                'error': str(e),
                'entries_warmed': 0
            }
    
    def _generate_user_cache_keys(self, user: User) -> List[str]:
        """Generate cache keys for a user."""
        try:
            cache_keys = []
            
            # User profile cache
            cache_keys.append(f"user_profile:{user.id}")
            
            # User preferences cache
            cache_keys.append(f"user_preferences:{user.id}")
            
            # User history cache
            cache_keys.append(f"user_history:{user.id}")
            
            # User scores cache
            cache_keys.append(f"user_scores:{user.id}")
            
            # User segments cache
            cache_keys.append(f"user_segments:{user.id}")
            
            return cache_keys
            
        except Exception as e:
            logger.error(f"Error generating user cache keys: {e}")
            return []
    
    def _generate_offer_cache_keys(self, offer: OfferRoute) -> List[str]:
        """Generate cache keys for an offer."""
        try:
            cache_keys = []
            
            # Offer details cache
            cache_keys.append(f"offer_details:{offer.id}")
            
            # Offer score cache
            cache_keys.append(f"offer_score:{offer.id}")
            
            # Offer ranking cache
            cache_keys.append(f"offer_ranking:{offer.id}")
            
            # Offer performance cache
            cache_keys.append(f"offer_performance:{offer.id}")
            
            # Offer targeting cache
            cache_keys.append(f"offer_targeting:{offer.id}")
            
            return cache_keys
            
        except Exception as e:
            logger.error(f"Error generating offer cache keys: {e}")
            return []
    
    def _generate_route_cache_keys(self, route: OfferRoute) -> List[str]:
        """Generate cache keys for a route."""
        try:
            cache_keys = []
            
            # Route configuration cache
            cache_keys.append(f"route_config:{route.id}")
            
            # Route conditions cache
            cache_keys.append(f"route_conditions:{route.id}")
            
            # Route actions cache
            cache_keys.append(f"route_actions:{route.id}")
            
            # Route targeting cache
            cache_keys.append(f"route_targeting:{route.id}")
            
            # Route performance cache
            cache_keys.append(f"route_performance:{route.id}")
            
            return cache_keys
            
        except Exception as e:
            logger.error(f"Error generating route cache keys: {e}")
            return []
    
    def _generate_user_cache_data(self, user_id: int) -> Dict[str, Any]:
        """Generate cache data for a user."""
        try:
            # This would generate actual user cache data
            # For now, return placeholder data
            return {
                'user_id': user_id,
                'cache_type': 'user_profile',
                'data': {
                    'last_warmup': timezone.now().isoformat(),
                    'version': '1.0'
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating user cache data: {e}")
            return {}
    
    def _generate_offer_cache_data(self, offer_id: int) -> Dict[str, Any]:
        """Generate cache data for an offer."""
        try:
            # This would generate actual offer cache data
            # For now, return placeholder data
            return {
                'offer_id': offer_id,
                'cache_type': 'offer_details',
                'data': {
                    'last_warmup': timezone.now().isoformat(),
                    'version': '1.0'
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating offer cache data: {e}")
            return {}
    
    def _generate_route_cache_data(self, route_id: int) -> Dict[str, Any]:
        """Generate cache data for a route."""
        try:
            # This would generate actual route cache data
            # For now, return placeholder data
            return {
                'route_id': route_id,
                'cache_type': 'route_config',
                'data': {
                    'last_warmup': timezone.now().isoformat(),
                    'version': '1.0'
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating route cache data: {e}")
            return {}
    
    def _update_task_stats(self, start_time, warmed_entries, failed_targets):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_warmups'] += 1
            self.task_stats['cache_entries_warmed'] += warmed_entries
            
            # Update average time
            current_avg = self.task_stats['avg_warmup_time_ms']
            total_warmups = self.task_stats['total_warmups']
            self.task_stats['avg_warmup_time_ms'] = (
                (current_avg * (total_warmups - 1) + execution_time) / total_warmups
            )
            
        except Exception as e:
            logger.error(f"Error updating task stats: {e}")
    
    def get_task_stats(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        return self.task_stats
    
    def reset_task_stats(self) -> bool:
        """Reset task statistics."""
        try:
            self.task_stats = {
                'total_warmups': 0,
                'successful_warmups': 0,
                'failed_warmups': 0,
                'cache_entries_warmed': 0,
                'avg_warmup_time_ms': 0.0
            }
            
            logger.info("Reset cache warmup task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache warmup task."""
        try:
            # Test cache service
            cache_health = self.cache_service.health_check()
            
            # Test analytics service
            analytics_health = self.analytics_service.health_check()
            
            # Test warmup functionality
            test_user = User.objects.filter(is_active=True).first()
            if test_user:
                test_result = self._warmup_user_cache({
                    'user_id': test_user.id,
                    'cache_keys': self._generate_user_cache_keys(test_user)
                })
                
                return {
                    'status': 'healthy' if all([
                        cache_health.get('status') == 'healthy',
                        analytics_health.get('status') == 'healthy',
                        test_result['success']
                    ]) else 'unhealthy',
                    'cache_health': cache_health,
                    'analytics_health': analytics_health,
                    'warmup_test': test_result,
                    'task_stats': self.task_stats,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'status': 'unhealthy',
                'error': 'No users available for testing',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in cache warmup task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


# Task instance
cache_warmup_task = CacheWarmupTask()
