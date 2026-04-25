"""
Score Update Tasks

Periodic tasks for updating offer scores
in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.core import OfferScorer
from ..services.analytics import analytics_service
from ..services.cache import cache_service
from ..models import OfferRoute, OfferScore, UserOfferHistory
from ..constants import SCORE_UPDATE_INTERVAL, SCORE_CACHE_TIMEOUT
from ..exceptions import ScoringError

logger = logging.getLogger(__name__)

User = get_user_model()


class ScoreUpdateTask:
    """
    Task for updating offer scores periodically.
    
    Runs every 30 minutes to recalculate:
    - Offer performance metrics
    - User affinity scores
    - EPC and CR calculations
    - Personalization adjustments
    - Global offer rankings
    """
    
    def __init__(self):
        self.scorer = OfferScorer()
        self.analytics_service = analytics_service
        self.cache_service = cache_service
        self.task_stats = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'avg_update_time_ms': 0.0
        }
    
    def run_score_update(self) -> Dict[str, Any]:
        """
        Run the score update task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get offers that need score updates
            offers_to_update = self._get_offers_needing_update()
            
            if not offers_to_update:
                logger.info("No offers need score updates")
                return {
                    'success': True,
                    'message': 'No offers need score updates',
                    'offers_updated': 0,
                    'execution_time_ms': 0,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Update scores for each offer
            updated_offers = 0
            failed_offers = 0
            
            for offer in offers_to_update:
                try:
                    # Update offer score
                    result = self._update_offer_score(offer)
                    
                    if result['success']:
                        updated_offers += 1
                        logger.info(f"Updated score for offer {offer.id}")
                    else:
                        failed_offers += 1
                        logger.error(f"Failed to update score for offer {offer.id}: {result['error']}")
                        
                except Exception as e:
                    failed_offers += 1
                    logger.error(f"Error updating score for offer {offer.id}: {e}")
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_score_cache(offers_to_update)
            
            return {
                'success': True,
                'message': 'Score update task completed',
                'offers_updated': updated_offers,
                'offers_failed': failed_offers,
                'total_offers': len(offers_to_update),
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in score update task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_offers_needing_update(self) -> List[OfferRoute]:
        """Get offers that need score updates."""
        try:
            # Get offers that haven't been updated recently
            cutoff_time = timezone.now() - timezone.timedelta(minutes=SCORE_UPDATE_INTERVAL)
            
            offers = OfferRoute.objects.filter(
                is_active=True,
                updated_at__lt=cutoff_time
            ).order_by('-updated_at')[:100]  # Limit to 100 offers per batch
            
            # Get offers with recent activity (higher priority)
            recent_activity_cutoff = timezone.now() - timezone.timedelta(hours=1)
            active_offers = UserOfferHistory.objects.filter(
                created_at__gte=recent_activity_cutoff
            ).values_list('offer_id').distinct()
            
            # Prioritize offers with recent activity
            prioritized_offers = []
            for offer in offers:
                if offer.id in active_offers:
                    prioritized_offers.insert(0, offer)
                else:
                    prioritized_offers.append(offer)
            
            return prioritized_offers[:50]  # Limit to 50 total offers
            
        except Exception as e:
            logger.error(f"Error getting offers needing update: {e}")
            return []
    
    def _update_offer_score(self, offer: OfferRoute) -> Dict[str, Any]:
        """Update score for a specific offer."""
        try:
            # Get current score
            current_score = OfferScore.objects.filter(offer=offer).first()
            
            # Calculate new score
            new_score = self.scorer.calculate_comprehensive_score(offer)
            
            # Update or create score record
            if current_score:
                current_score.score = new_score
                current_score.scored_at = timezone.now()
                current_score.save()
            else:
                OfferScore.objects.create(
                    offer=offer,
                    score=new_score,
                    scored_at=timezone.now()
                )
            
            # Update analytics
            self._update_offer_analytics(offer, new_score)
            
            return {
                'success': True,
                'offer_id': offer.id,
                'previous_score': current_score.score if current_score else None,
                'new_score': new_score,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating score for offer {offer.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'offer_id': offer.id,
                'timestamp': timezone.now().isoformat()
            }
    
    def _update_offer_analytics(self, offer: OfferRoute, score: float):
        """Update analytics for offer score change."""
        try:
            # Get performance metrics for this offer
            performance_data = self.analytics_service.get_route_analytics(
                offer.id,
                days=30
            )
            
            # Log score change
            logger.info(f"Offer {offer.id} score updated: {score}")
            
            # Update cache
            cache_key = f"offer_score:{offer.id}"
            self.cache_service.set(cache_key, score, SCORE_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating analytics for offer {offer.id}: {e}")
    
    def _clear_score_cache(self, offers: List[OfferRoute]):
        """Clear score cache for updated offers."""
        try:
            for offer in offers:
                cache_key = f"offer_score:{offer.id}"
                self.cache_service.delete(cache_key)
                
        except Exception as e:
            logger.error(f"Error clearing score cache: {e}")
    
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
            
            logger.info("Reset score update task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on score update task."""
        try:
            # Test scorer
            test_offer = OfferRoute.objects.filter(is_active=True).first()
            if not test_offer:
                test_offer = OfferRoute.objects.first()
            
            if test_offer:
                test_result = self._update_offer_score(test_offer)
                
                return {
                    'status': 'healthy',
                    'scorer_working': test_result['success'],
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
            logger.error(f"Error in score update task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "test_score_update"
            test_value = 0.75
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
score_update_task = ScoreUpdateTask()
