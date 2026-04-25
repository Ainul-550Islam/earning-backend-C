"""
Rank Update Tasks

Periodic tasks for updating global offer rankings
in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.core import OfferRanker
from ..services.analytics import analytics_service
from ..services.cache import cache_service
from ..models import OfferRoute, OfferScore, GlobalOfferRank
from ..constants import RANK_UPDATE_INTERVAL, RANK_CACHE_TIMEOUT
from ..exceptions import RankingError

logger = logging.getLogger(__name__)

User = get_user_model()


class RankUpdateTask:
    """
    Task for updating global offer rankings.
    
    Runs hourly to update:
    - Global offer rankings
    - Category-based rankings
    - Regional rankings
    - Performance-based rankings
    - Trend analysis
    """
    
    def __init__(self):
        self.ranker = OfferRanker()
        self.analytics_service = analytics_service
        self.cache_service = cache_service
        self.task_stats = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'avg_update_time_ms': 0.0
        }
    
    def run_rank_update(self) -> Dict[str, Any]:
        """
        Run the ranking update task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get offers that need ranking updates
            offers_to_rank = self._get_offers_needing_ranking()
            
            if not offers_to_rank:
                logger.info("No offers need ranking updates")
                return {
                    'success': True,
                    'message': 'No offers need ranking updates',
                    'offers_ranked': 0,
                    'execution_time_ms': 0,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Update rankings for each offer
            ranked_offers = 0
            failed_offers = 0
            
            for offer in offers_to_rank:
                try:
                    # Update offer ranking
                    result = self._update_offer_ranking(offer)
                    
                    if result['success']:
                        ranked_offers += 1
                        logger.info(f"Updated ranking for offer {offer.id}")
                    else:
                        failed_offers += 1
                        logger.error(f"Failed to update ranking for offer {offer.id}: {result['error']}")
                        
                except Exception as e:
                    failed_offers += 1
                    logger.error(f"Error updating ranking for offer {offer.id}: {e}")
            
            # Update global rankings
            global_ranking_result = self._update_global_rankings(offers_to_rank)
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_ranking_cache(offers_to_rank)
            
            return {
                'success': True,
                'message': 'Ranking update task completed',
                'offers_ranked': ranked_offers,
                'offers_failed': failed_offers,
                'total_offers': len(offers_to_rank),
                'global_ranking_result': global_ranking_result,
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in ranking update task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_offers_needing_ranking(self) -> List[OfferRoute]:
        """Get offers that need ranking updates."""
        try:
            # Get offers that haven't been ranked recently
            cutoff_time = timezone.now() - timezone.timedelta(hours=RANK_UPDATE_INTERVAL)
            
            offers = OfferRoute.objects.filter(
                is_active=True,
                ranked_at__lt=cutoff_time
            ).order_by('-updated_at')[:200]  # Limit to 200 offers per batch
            
            # Prioritize offers with recent activity
            recent_activity_cutoff = timezone.now() - timezone.timedelta(hours=6)
            active_offers = OfferRoute.objects.filter(
                id__in=[offer.id for offer in offers],
                userofferhistory__created_at__gte=recent_activity_cutoff
            ).distinct()
            
            # Prioritize active offers
            prioritized_offers = []
            for offer in offers:
                if offer.id in [active_offer.id for active_offer in active_offers]:
                    prioritized_offers.insert(0, offer)
                else:
                    prioritized_offers.append(offer)
            
            return prioritized_offers[:100]  # Limit to 100 total offers
            
        except Exception as e:
            logger.error(f"Error getting offers needing ranking: {e}")
            return []
    
    def _update_offer_ranking(self, offer: OfferRoute) -> Dict[str, Any]:
        """Update ranking for a specific offer."""
        try:
            # Get current ranking
            current_ranking = GlobalOfferRank.objects.filter(offer=offer).first()
            
            # Calculate new ranking
            new_ranking = self.ranker.calculate_global_ranking(offer)
            
            # Update or create ranking record
            with transaction.atomic():
                if current_ranking:
                    current_ranking.rank_value = new_ranking['global_rank']
                    current_ranking.category_rank = new_ranking.get('category_rank', 0)
                    current_ranking.regional_rank = new_ranking.get('regional_rank', 0)
                    current_ranking.performance_score = new_ranking.get('performance_score', 0.0)
                    current_ranking.ranked_at = timezone.now()
                    current_ranking.save()
                else:
                    GlobalOfferRank.objects.create(
                        offer=offer,
                        rank_value=new_ranking['global_rank'],
                        category_rank=new_ranking.get('category_rank', 0),
                        regional_rank=new_ranking.get('regional_rank', 0),
                        performance_score=new_ranking.get('performance_score', 0.0),
                        ranked_at=timezone.now()
                    )
            
            # Update offer's ranked timestamp
            offer.ranked_at = timezone.now()
            offer.save()
            
            # Update analytics
            self._update_ranking_analytics(offer, new_ranking)
            
            return {
                'success': True,
                'offer_id': offer.id,
                'previous_rank': current_ranking.rank_value if current_ranking else None,
                'new_rank': new_ranking,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating ranking for offer {offer.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'offer_id': offer.id,
                'timestamp': timezone.now().isoformat()
            }
    
    def _update_global_rankings(self, offers: List[OfferRoute]) -> Dict[str, Any]:
        """Update global ranking statistics."""
        try:
            # Get top offers by different criteria
            top_by_score = sorted(offers, key=lambda x: getattr(x, 'current_score', 0), reverse=True)[:10]
            top_by_conversion = sorted(offers, key=lambda x: getattr(x, 'conversion_rate', 0), reverse=True)[:10]
            top_by_revenue = sorted(offers, key=lambda x: getattr(x, 'total_revenue', 0), reverse=True)[:10]
            
            # Update global ranking cache
            global_rankings = {
                'top_by_score': [
                    {'offer_id': offer.id, 'score': getattr(offer, 'current_score', 0)}
                    for offer in top_by_score
                ],
                'top_by_conversion': [
                    {'offer_id': offer.id, 'conversion_rate': getattr(offer, 'conversion_rate', 0)}
                    for offer in top_by_conversion
                ],
                'top_by_revenue': [
                    {'offer_id': offer.id, 'revenue': getattr(offer, 'total_revenue', 0)}
                    for offer in top_by_revenue
                ],
                'updated_at': timezone.now().isoformat()
            }
            
            # Cache global rankings
            cache.set('global_offer_rankings', global_rankings, RANK_CACHE_TIMEOUT)
            
            return {
                'success': True,
                'global_rankings': global_rankings,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating global rankings: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _update_ranking_analytics(self, offer: OfferRoute, ranking: Dict[str, Any]):
        """Update analytics for ranking changes."""
        try:
            # Log ranking change
            logger.info(f"Offer {offer.id} ranking updated: {ranking.get('global_rank', 0)}")
            
            # Update cache
            cache_key = f"offer_ranking:{offer.id}"
            self.cache_service.set(cache_key, ranking, RANK_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating ranking analytics for offer {offer.id}: {e}")
    
    def _clear_ranking_cache(self, offers: List[OfferRoute]):
        """Clear ranking cache for updated offers."""
        try:
            for offer in offers:
                cache_key = f"offer_ranking:{offer.id}"
                self.cache_service.delete(cache_key)
                
        except Exception as e:
            logger.error(f"Error clearing ranking cache: {e}")
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_updates'] += 1
            self.task_stats['successful_updates'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_update_time_ms']
            total_updates = self.task_stats['total_updates']
            self.task_stats['avg_update_time_ms'] = (
                (current_avg * (total_updates - 1) + execution_time) / total_updates
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
                'total_updates': 0,
                'successful_updates': 0,
                'failed_updates': 0,
                'avg_update_time_ms': 0.0
            }
            
            logger.info("Reset ranking update task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on ranking update task."""
        try:
            # Test ranker
            test_offer = OfferRoute.objects.filter(is_active=True).first()
            if not test_offer:
                test_offer = OfferRoute.objects.first()
            
            if test_offer:
                test_result = self._update_offer_ranking(test_offer)
                
                return {
                    'status': 'healthy',
                    'ranker_working': test_result['success'],
                    'cache_working': self._test_cache_functionality(),
                    'analytics_working': self._test_analytics_functionality(),
                    'task_stats': self.task_stats,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'status': 'unhealthy',
                'error': 'No offers available for testing',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in ranking update task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "test_ranking_update"
            test_value = 0.85
            self.cache_service.set(test_key, test_value, 60)
            
            # Retrieve from cache
            cached_value = self.cache_service.get(test_key)
            
            return cached_value == test_value
            
        except Exception as e:
            logger.error(f"Error testing cache functionality: {e}")
            return False
    
    def _test_analytics_functionality(self) -> bool:
        """Test analytics functionality."""
        try:
            # Test analytics service health check
            analytics_health = self.analytics_service.health_check()
            
            return analytics_health.get('status') == 'healthy'
            
        except Exception as e:
            logger.error(f"Error testing analytics functionality: {e}")
            return False


# Task instance
rank_update_task = RankUpdateTask()
