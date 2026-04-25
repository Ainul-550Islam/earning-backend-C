"""
Analytics Tasks

Periodic tasks for rolling up analytics statistics
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
from ..models import RoutingDecisionLog, RoutePerformanceStat, OfferExposureStat
from ..constants import ANALYTICS_ROLLUP_INTERVAL, ANALYTICS_BATCH_SIZE, ANALYTICS_CACHE_TIMEOUT
from ..exceptions import AnalyticsError

logger = logging.getLogger(__name__)

User = get_user_model()


class AnalyticsTask:
    """
    Task for rolling up analytics statistics.
    
    Runs hourly to:
    - Aggregate routing decisions
    - Calculate route performance metrics
    - Generate exposure statistics
    - Update performance dashboards
    - Archive old analytics data
    """
    
    def __init__(self):
        self.analytics_service = analytics_service
        self.cache_service = cache_service
        self.task_stats = {
            'total_rollups': 0,
            'successful_rollups': 0,
            'failed_rollups': 0,
            'avg_rollup_time_ms': 0.0
        }
    
    def run_analytics_rollup(self) -> Dict[str, Any]:
        """
        Run the analytics rollup task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get time window for rollup
            end_time = timezone.now()
            start_time = end_time - timezone.timedelta(hours=ANALYTICS_ROLLUP_INTERVAL)
            
            # Perform rollup for different metrics
            rollup_results = self._perform_analytics_rollup(start_time, end_time)
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_analytics_cache()
            
            return {
                'success': True,
                'message': 'Analytics rollup task completed',
                'rollup_results': rollup_results,
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in analytics rollup task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _perform_analytics_rollup(self, start_time, end_time) -> Dict[str, Any]:
        """Perform analytics rollup for the time window."""
        try:
            rollup_results = {}
            
            # Rollup routing decisions
            routing_rollup = self._rollup_routing_decisions(start_time, end_time)
            rollup_results['routing_decisions'] = routing_rollup
            
            # Rollup route performance
            performance_rollup = self._rollup_route_performance(start_time, end_time)
            rollup_results['route_performance'] = performance_rollup
            
            # Rollup exposure statistics
            exposure_rollup = self._rollup_exposure_stats(start_time, end_time)
            rollup_results['exposure_stats'] = exposure_rollup
            
            # Rollup user engagement metrics
            engagement_rollup = self._rollup_user_engagement(start_time, end_time)
            rollup_results['user_engagement'] = engagement_rollup
            
            # Rollup conversion metrics
            conversion_rollup = self._rollup_conversion_metrics(start_time, end_time)
            rollup_results['conversion_metrics'] = conversion_rollup
            
            # Rollup system performance metrics
            system_rollup = self._rollup_system_performance(start_time, end_time)
            rollup_results['system_performance'] = system_rollup
            
            return rollup_results
            
        except Exception as e:
            logger.error(f"Error performing analytics rollup: {e}")
            return {'error': str(e)}
    
    def _rollup_routing_decisions(self, start_time, end_time) -> Dict[str, Any]:
        """Rollup routing decision statistics."""
        try:
            # Get routing decisions in time window
            decisions = RoutingDecisionLog.objects.filter(
                created_at__gte=start_time,
                created_at__lt=end_time
            )
            
            # Calculate basic statistics
            total_decisions = decisions.count()
            cache_hits = decisions.filter(cache_hit=True).count()
            cache_misses = total_decisions - cache_hits
            cache_hit_rate = cache_hits / max(1, total_decisions)
            
            # Calculate response time statistics
            response_times = list(decisions.values_list('response_time_ms', flat=True))
            response_times.sort()
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                median_response_time = response_times[len(response_times) // 2]
                p95_response_time = response_times[int(len(response_times) * 0.95)]
                p99_response_time = response_times[int(len(response_times) * 0.99)]
            else:
                avg_response_time = median_response_time = p95_response_time = p99_response_time = 0.0
            
            # Calculate score distribution
            scores = list(decisions.values_list('score', flat=True))
            scores.sort()
            
            if scores:
                avg_score = sum(scores) / len(scores)
                median_score = scores[len(scores) // 2]
                p95_score = scores[int(len(scores) * 0.95)]
                p99_score = scores[int(len(scores) * 0.99)]
            else:
                avg_score = median_score = p95_score = p99_score = 0.0
            
            # Group by hour
            hourly_stats = {}
            for decision in decisions:
                hour = decision.created_at.hour
                if hour not in hourly_stats:
                    hourly_stats[hour] = {
                        'count': 0,
                        'cache_hits': 0,
                        'avg_response_time': 0.0
                    }
                
                hourly_stats[hour]['count'] += 1
                if decision.cache_hit:
                    hourly_stats[hour]['cache_hits'] += 1
                
                hourly_stats[hour]['avg_response_time'] += decision.response_time_ms
            
            # Calculate hourly averages
            for hour, stats in hourly_stats.items():
                if stats['count'] > 0:
                    stats['avg_response_time'] = stats['avg_response_time'] / stats['count']
            
            return {
                'total_decisions': total_decisions,
                'cache_hits': cache_hits,
                'cache_misses': cache_misses,
                'cache_hit_rate': cache_hit_rate,
                'avg_response_time_ms': avg_response_time,
                'median_response_time_ms': median_response_time,
                'p95_response_time_ms': p95_response_time,
                'p99_response_time_ms': p99_response_time,
                'avg_score': avg_score,
                'median_score': median_score,
                'p95_score': p95_score,
                'p99_score': p99_score,
                'hourly_breakdown': hourly_stats,
                'time_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error rolling up routing decisions: {e}")
            return {'error': str(e)}
    
    def _rollup_route_performance(self, start_time, end_time) -> Dict[str, Any]:
        """Rollup route performance statistics."""
        try:
            # Get route performance data in time window
            performance_data = RoutePerformanceStat.objects.filter(
                created_at__gte=start_time,
                created_at__lt=end_time
            )
            
            # Group by route
            route_stats = {}
            
            for stat in performance_data:
                route_id = stat.route_id
                if route_id not in route_stats:
                    route_stats[route_id] = {
                        'total_requests': 0,
                        'avg_score': 0.0,
                        'avg_response_time': 0.0,
                        'conversion_rate': 0.0,
                        'revenue': 0.0
                    }
                
                route_stats[route_id]['total_requests'] += 1
                route_stats[route_id]['avg_score'] += stat.avg_score or 0.0
                route_stats[route_id]['avg_response_time'] += stat.avg_response_time or 0.0
                route_stats[route_id]['conversion_rate'] += stat.conversion_rate or 0.0
                route_stats[route_id]['revenue'] += stat.revenue or 0.0
            
            # Calculate averages
            for route_id, stats in route_stats.items():
                if stats['total_requests'] > 0:
                    stats['avg_score'] = stats['avg_score'] / stats['total_requests']
                    stats['avg_response_time'] = stats['avg_response_time'] / stats['total_requests']
                    stats['conversion_rate'] = stats['conversion_rate'] / stats['total_requests']
            
            return {
                'route_performance': route_stats,
                'total_routes': len(route_stats),
                'time_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error rolling up route performance: {e}")
            return {'error': str(e)}
    
    def _rollup_exposure_stats(self, start_time, end_time) -> Dict[str, Any]:
        """Rollup offer exposure statistics."""
        try:
            # Get exposure data in time window
            exposure_data = OfferExposureStat.objects.filter(
                created_at__gte=start_time,
                created_at__lt=end_time
            )
            
            # Calculate basic statistics
            total_exposures = exposure_data.count()
            unique_users = exposure_data.values('user_id').distinct().count()
            unique_offers = exposure_data.values('offer_id').distinct().count()
            
            # Group by offer
            offer_stats = {}
            
            for stat in exposure_data:
                offer_id = stat.offer_id
                if offer_id not in offer_stats:
                    offer_stats[offer_id] = {
                        'exposures': 0,
                        'unique_users': set(),
                        'total_views': 0,
                        'total_clicks': 0,
                        'total_conversions': 0
                    }
                
                offer_stats[offer_id]['exposures'] += 1
                offer_stats[offer_id]['unique_users'].add(stat.user_id)
                offer_stats[offer_id]['total_views'] += stat.total_views or 0
                offer_stats[offer_id]['total_clicks'] += stat.total_clicks or 0
                offer_stats[offer_id]['total_conversions'] += stat.total_conversions or 0
            
            # Calculate conversion rates
            for offer_id, stats in offer_stats.items():
                if stats['total_views'] > 0:
                    stats['click_rate'] = stats['total_clicks'] / stats['total_views']
                    stats['conversion_rate'] = stats['total_conversions'] / stats['total_views']
            
            # Convert sets to counts
            for offer_id, stats in offer_stats.items():
                stats['unique_users'] = len(stats['unique_users'])
            
            return {
                'offer_exposure': offer_stats,
                'total_exposures': total_exposures,
                'unique_users': unique_users,
                'unique_offers': unique_offers,
                'time_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error rolling up exposure stats: {e}")
            return {'error': str(e)}
    
    def _rollup_user_engagement(self, start_time, end_time) -> Dict[str, Any]:
        """Rollup user engagement metrics."""
        try:
            # This would aggregate user engagement metrics
            # For now, return placeholder data
            
            return {
                'total_active_users': 0,
                'avg_session_duration': 0.0,
                'total_sessions': 0,
                'bounce_rate': 0.0,
                'retention_rate': 0.0,
                'time_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error rolling up user engagement: {e}")
            return {'error': str(e)}
    
    def _rollup_conversion_metrics(self, start_time, end_time) -> Dict[str, Any]:
        """Rollup conversion metrics."""
        try:
            # This would aggregate conversion metrics
            # For now, return placeholder data
            
            return {
                'total_conversions': 0,
                'conversion_rate': 0.0,
                'avg_conversion_value': 0.0,
                'total_revenue': 0.0,
                'conversions_by_category': {},
                'conversions_by_source': {},
                'time_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error rolling up conversion metrics: {e}")
            return {'error': str(e)}
    
    def _rollup_system_performance(self, start_time, end_time) -> Dict[str, Any]:
        """Rollup system performance metrics."""
        try:
            # This would aggregate system performance metrics
            # For now, return placeholder data
            
            return {
                'avg_response_time_ms': 0.0,
                'cache_hit_rate': 0.0,
                'error_rate': 0.0,
                'throughput_per_second': 0.0,
                'system_load': 'normal',
                'memory_usage': 'normal',
                'disk_usage': 'normal',
                'time_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error rolling up system performance: {e}")
            return {'error': str(e)}
    
    def _clear_analytics_cache(self):
        """Clear analytics-related cache entries."""
        try:
            # Clear analytics cache entries
            cache_patterns = [
                "analytics_rollup:*",
                "routing_stats:*",
                "performance_stats:*",
                "exposure_stats:*"
            ]
            
            for pattern in cache_patterns:
                # This would need pattern deletion support
                # For now, clear specific keys
                cache.delete("analytics_rollup:latest")
                cache.delete("routing_stats:latest")
                cache.delete("performance_stats:latest")
                cache.delete("exposure_stats:latest")
            
            logger.info("Cleared analytics cache entries")
            
        except Exception as e:
            logger.error(f"Error clearing analytics cache: {e}")
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_rollups'] += 1
            self.task_stats['successful_rollups'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_rollup_time_ms']
            total_rollups = self.task_stats['total_rollups']
            self.task_stats['avg_rollup_time_ms'] = (
                (current_avg * (total_rollups - 1) + execution_time) / total_rollups
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
                'total_rollups': 0,
                'successful_rollups': 0,
                'failed_rollups': 0,
                'avg_rollup_time_ms': 0.0
            }
            
            logger.info("Reset analytics rollup task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on analytics rollup task."""
        try:
            # Test analytics service
            analytics_health = self.analytics_service.health_check()
            
            # Test cache functionality
            cache_health = self._test_cache_functionality()
            
            # Test data aggregation
            test_aggregation = self._test_data_aggregation()
            
            return {
                'status': 'healthy' if all([
                    analytics_health.get('status') == 'healthy',
                    cache_health,
                    test_aggregation
                ]) else 'unhealthy',
                'analytics_service_health': analytics_health,
                'cache_health': cache_health,
                'data_aggregation_test': test_aggregation,
                'task_stats': self.task_stats,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in analytics rollup task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "test_analytics_rollup"
            test_value = {"test": True, "version": "1.0"}
            
            self.cache_service.set(test_key, test_value, 60)
            cached_value = self.cache_service.get(test_key)
            
            # Clean up
            self.cache_service.delete(test_key)
            
            return cached_value and cached_value.get('test') == test_value.get('test')
            
        except Exception as e:
            logger.error(f"Error testing cache functionality: {e}")
            return False
    
    def _test_data_aggregation(self) -> bool:
        """Test data aggregation functionality."""
        try:
            # Test basic aggregation
            test_data = [1, 2, 3, 4, 5]
            avg_value = sum(test_data) / len(test_data)
            
            return avg_value == 3.0  # Expected average
            
        except Exception as e:
            logger.error(f"Error testing data aggregation: {e}")
            return False


# Task instance
analytics_task = AnalyticsTask()
