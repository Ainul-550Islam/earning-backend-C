"""
Exposure Statistics Tasks

Periodic tasks for generating daily exposure statistics
in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.analytics import analytics_service
from ..services.cache import cache_service
from ..models import OfferExposureStat, UserOfferHistory, OfferRoute
from ..constants import EXPOSURE_STAT_INTERVAL, EXPOSURE_CACHE_TIMEOUT
from ..exceptions import AnalyticsError

logger = logging.getLogger(__name__)

User = get_user_model()


class ExposureStatTask:
    """
    Task for generating daily exposure statistics.
    
    Runs daily to:
    - Calculate offer exposure metrics
    - Generate exposure reports
    - Update offer popularity scores
    - Track user engagement patterns
    - Monitor exposure effectiveness
    """
    
    def __init__(self):
        self.analytics_service = analytics_service
        self.cache_service = cache_service
        self.task_stats = {
            'total_generations': 0,
            'successful_generations': 0,
            'failed_generations': 0,
            'avg_generation_time_ms': 0.0
        }
    
    def run_exposure_stat_generation(self) -> Dict[str, Any]:
        """
        Run the exposure statistics generation task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get exposure data for the day
            exposure_data = self._get_daily_exposure_data()
            
            if not exposure_data:
                logger.info("No exposure data available for statistics generation")
                return {
                    'success': True,
                    'message': 'No exposure data available',
                    'stats_generated': 0,
                    'execution_time_ms': 0,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Generate exposure statistics
            stats_generated = 0
            failed_generations = 0
            
            for offer_id, data in exposure_data.items():
                try:
                    # Generate exposure statistics for this offer
                    result = self._generate_offer_exposure_stats(offer_id, data)
                    
                    if result['success']:
                        stats_generated += 1
                        logger.info(f"Generated exposure stats for offer {offer_id}")
                    else:
                        failed_generations += 1
                        logger.error(f"Failed to generate exposure stats for offer {offer_id}: {result['error']}")
                        
                except Exception as e:
                    failed_generations += 1
                    logger.error(f"Error generating exposure stats for offer {offer_id}: {e}")
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_exposure_cache()
            
            return {
                'success': True,
                'message': 'Exposure statistics generation task completed',
                'stats_generated': stats_generated,
                'failed_generations': failed_generations,
                'total_offers': len(exposure_data),
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in exposure statistics generation task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_daily_exposure_data(self) -> Dict[int, List[Dict[str, Any]]]:
        """Get daily exposure data for all offers."""
        try:
            # Get all active offers
            active_offers = OfferRoute.objects.filter(is_active=True)
            
            exposure_data = {}
            
            for offer in active_offers:
                # Get exposure data for this offer
                offer_exposure = self._get_offer_exposure_data(offer)
                
                if offer_exposure:
                    exposure_data[offer.id] = offer_exposure
            
            logger.info(f"Retrieved exposure data for {len(exposure_data)} offers")
            
            return exposure_data
            
        except Exception as e:
            logger.error(f"Error getting daily exposure data: {e}")
            return {}
    
    def _get_offer_exposure_data(self, offer: OfferRoute) -> List[Dict[str, Any]]:
        """Get exposure data for a specific offer."""
        try:
            # Get exposure data for today
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timezone.timedelta(days=1)
            
            # Get user offer history for today
            exposure_history = UserOfferHistory.objects.filter(
                offer=offer,
                created_at__gte=today_start,
                created_at__lt=today_end
            )
            
            # Calculate exposure metrics
            exposure_data = []
            
            # Group by hour for detailed analysis
            for hour in range(24):
                hour_start = today_start + timezone.timedelta(hours=hour)
                hour_end = hour_start + timezone.timedelta(hours=1)
                
                hour_exposures = exposure_history.filter(
                    created_at__gte=hour_start,
                    created_at__lt=hour_end
                )
                
                # Calculate hourly metrics
                total_views = hour_exposures.count()
                total_clicks = hour_exposures.filter(clicked_at__isnull=False).count()
                total_conversions = hour_exposures.filter(completed_at__isnull=False).count()
                
                # Calculate rates
                click_rate = total_clicks / max(1, total_views)
                conversion_rate = total_conversions / max(1, total_views)
                
                exposure_data.append({
                    'hour': hour,
                    'total_views': total_views,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'click_rate': click_rate,
                    'conversion_rate': conversion_rate,
                    'revenue': hour_exposures.filter(completed_at__isnull=False).aggregate(
                        total_revenue=models.Sum('conversion_value')
                    )['total_revenue'] or 0.0,
                    'avg_revenue_per_view': 0.0,
                    'avg_revenue_per_click': 0.0,
                    'avg_revenue_per_conversion': 0.0
                })
            
            # Calculate daily totals
            daily_totals = {
                'total_views': sum(item['total_views'] for item in exposure_data),
                'total_clicks': sum(item['total_clicks'] for item in exposure_data),
                'total_conversions': sum(item['total_conversions'] for item in exposure_data),
                'total_revenue': sum(item['revenue'] for item in exposure_data),
                'avg_click_rate': sum(item['total_clicks'] for item in exposure_data) / max(1, sum(item['total_views'] for item in exposure_data)),
                'avg_conversion_rate': sum(item['total_conversions'] for item in exposure_data) / max(1, sum(item['total_views'] for item in exposure_data)),
                'unique_users': exposure_history.values_list('user_id').distinct().count()
            }
            
            # Calculate rates
            if daily_totals['total_views'] > 0:
                daily_totals['avg_click_rate'] = daily_totals['total_clicks'] / daily_totals['total_views']
                daily_totals['avg_conversion_rate'] = daily_totals['total_conversions'] / daily_totals['total_views']
                daily_totals['avg_revenue_per_view'] = daily_totals['total_revenue'] / daily_totals['total_views']
                daily_totals['avg_revenue_per_click'] = daily_totals['total_revenue'] / max(1, daily_totals['total_clicks'])
                daily_totals['avg_revenue_per_conversion'] = daily_totals['total_revenue'] / max(1, daily_totals['total_conversions'])
            else:
                daily_totals['avg_click_rate'] = 0.0
                daily_totals['avg_conversion_rate'] = 0.0
                daily_totals['avg_revenue_per_view'] = 0.0
                daily_totals['avg_revenue_per_click'] = 0.0
                daily_totals['avg_revenue_per_conversion'] = 0.0
            
            # Add daily summary
            exposure_data.append({
                'hour': 'daily_summary',
                'total_views': daily_totals['total_views'],
                'total_clicks': daily_totals['total_clicks'],
                'total_conversions': daily_totals['total_conversions'],
                'total_revenue': daily_totals['total_revenue'],
                'avg_click_rate': daily_totals['avg_click_rate'],
                'avg_conversion_rate': daily_totals['avg_conversion_rate'],
                'unique_users': daily_totals['unique_users'],
                'avg_revenue_per_view': daily_totals['avg_revenue_per_view'],
                'avg_revenue_per_click': daily_totals['avg_revenue_per_click'],
                'avg_revenue_per_conversion': daily_totals['avg_revenue_per_conversion']
            })
            
            return exposure_data
            
        except Exception as e:
            logger.error(f"Error getting offer exposure data: {e}")
            return []
    
    def _generate_offer_exposure_stats(self, offer_id: int, 
                                   exposure_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate exposure statistics for a specific offer."""
        try:
            # Calculate hourly exposure statistics
            hourly_stats = []
            daily_summary = None
            
            for item in exposure_data:
                if item['hour'] != 'daily_summary':
                    hourly_stats.append(item)
                else:
                    daily_summary = item
            
            # Calculate daily totals
            daily_totals = {
                'total_views': sum(item['total_views'] for item in hourly_stats),
                'total_clicks': sum(item['total_clicks'] for item in hourly_stats),
                'total_conversions': sum(item['total_conversions'] for item in hourly_stats),
                'total_revenue': sum(item['revenue'] for item in hourly_stats),
                'peak_hour': max(hourly_stats, key=lambda x: x['total_views'])['hour'] if hourly_stats else None,
                'peak_clicks_hour': max(hourly_stats, key=lambda x: x['total_clicks'])['hour'] if hourly_stats else None,
                'peak_conversions_hour': max(hourly_stats, key=lambda x: x['total_conversions'])['hour'] if hourly_stats else None
            }
            
            # Create exposure statistics record
            exposure_stat = {
                'offer_id': offer_id,
                'date': timezone.now().date(),
                'hourly_exposures': hourly_stats,
                'daily_totals': daily_totals,
                'created_at': timezone.now()
            }
            
            # Save to database
            with transaction.atomic():
                OfferExposureStat.objects.create(**exposure_stat)
            
            # Update cache
            self._update_exposure_cache(offer_id, exposure_stat)
            
            return {
                'success': True,
                'offer_id': offer_id,
                'date': exposure_stat['date'].isoformat(),
                'daily_views': daily_totals['total_views'],
                'daily_clicks': daily_totals['total_clicks'],
                'daily_conversions': daily_totals['total_conversions'],
                'daily_revenue': daily_totals['total_revenue'],
                'peak_hour': daily_totals['peak_hour'],
                'peak_clicks_hour': daily_totals['peak_clicks_hour'],
                'peak_conversions_hour': daily_totals['peak_conversions_hour'],
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating exposure stats for offer {offer_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'offer_id': offer_id,
                'timestamp': timezone.now().isoformat()
            }
    
    def _update_exposure_cache(self, offer_id: int, exposure_stat: Dict[str, Any]):
        """Update exposure cache for an offer."""
        try:
            cache_key = f"exposure_stats:{offer_id}:{exposure_stat['date']}"
            self.cache_service.set(cache_key, exposure_stat, EXPOSURE_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating exposure cache for offer {offer_id}: {e}")
    
    def _clear_exposure_cache(self):
        """Clear exposure-related cache entries."""
        try:
            # Clear all exposure statistics cache
            cache.delete("exposure_stats:*")
            
            logger.info("Cleared exposure statistics cache")
            
        except Exception as e:
            logger.error(f"Error clearing exposure cache: {e}")
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_generations'] += 1
            self.task_stats['successful_generations'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_generation_time_ms']
            total_generations = self.task_stats['total_generations']
            self.task_stats['avg_generation_time_ms'] = (
                (current_avg * (total_generations - 1) + execution_time) / total_generations
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
                'total_generations': 0,
                'successful_generations': 0,
                'failed_generations': 0,
                'avg_generation_time_ms': 0.0
            }
            
            logger.info("Reset exposure statistics generation task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on exposure statistics task."""
        try:
            # Test analytics service
            analytics_health = self.analytics_service.health_check()
            
            # Test cache functionality
            cache_health = self._test_cache_functionality()
            
            # Test exposure data generation
            test_offer = OfferRoute.objects.filter(is_active=True).first()
            if not test_offer:
                test_offer = OfferRoute.objects.first()
            
            if test_offer:
                test_exposure_data = self._get_offer_exposure_data(test_offer)
                test_result = self._generate_offer_exposure_stats(test_offer.id, test_exposure_data)
                
                return {
                    'status': 'healthy' if all([
                        analytics_health.get('status') == 'healthy',
                        cache_health,
                        test_result['success']
                    ]) else 'unhealthy',
                    'analytics_service_health': analytics_health,
                    'cache_health': cache_health,
                    'exposure_generation_test': test_result,
                    'task_stats': self.task_stats,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'status': 'unhealthy',
                'error': 'No offers available for testing',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in exposure statistics task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "test_exposure_stats"
            test_value = {"test": True, "version": "1.0"}
            
            self.cache_service.set(test_key, test_value, 60)
            cached_value = self.cache_service.get(test_key)
            
            # Clean up
            self.cache_service.delete(test_key)
            
            return cached_value and cached_value.get('test') == test_value.get('test')
            
        except Exception as e:
            logger.error(f"Error testing cache functionality: {e}")
            return False


# Task instance
exposure_stat_task = ExposureStatTask()
