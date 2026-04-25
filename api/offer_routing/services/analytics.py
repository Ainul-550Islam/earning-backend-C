"""
Analytics Service for Offer Routing System

This module provides analytics functionality for tracking,
analyzing, and reporting on routing performance.
"""

import logging
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Max, Min, Q, F
from ..models import (
    RoutingDecisionLog, RoutingInsight, RoutePerformanceStat,
    OfferExposureStat, OfferAffinityScore
)
from ..constants import (
    DECISION_LOG_RETENTION_DAYS, INSIGHT_AGGREGATION_HOURS,
    PERFORMANCE_STATS_RETENTION_DAYS
)
from ..exceptions import AnalyticsError

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingAnalyticsService:
    """
    Service for routing analytics and insights.
    
    Provides performance tracking, insight generation,
    and analytics aggregation functionality.
    """
    
    def __init__(self):
        self.cache_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize analytics services."""
        try:
            from .cache import RoutingCacheService
            self.cache_service = RoutingCacheService()
        except ImportError as e:
            logger.error(f"Failed to initialize analytics services: {e}")
    
    def aggregate_hourly_stats(self) -> int:
        """Aggregate routing statistics by hour."""
        try:
            from datetime import timedelta
            from ..models import RoutePerformanceStat, OfferExposureStat
            
            aggregated_count = 0
            
            # Get recent routing decisions
            cutoff_time = timezone.now() - timedelta(hours=1)
            recent_decisions = RoutingDecisionLog.objects.filter(
                created_at__gte=cutoff_time
            )
            
            # Aggregate by route
            route_stats = recent_decisions.values('route_id').annotate(
                impressions=Count('id'),
                unique_users=Count('user_id', distinct=True),
                clicks=Count('id', filter=Q(score__gt=50)),  # Assuming clicks are high scores
                conversions=Count('id', filter=Q(score__gt=80)),  # Assuming conversions are very high scores
                avg_response_time=Avg('response_time_ms'),
                cache_hit_rate=Avg('cache_hit'),
                error_rate=Avg('response_time_ms', filter=Q(response_time_ms__gt=1000))  # Errors as slow responses
            )
            
            for stat in route_stats:
                # Create or update performance stat
                RoutePerformanceStat.objects.update_or_create(
                    route_id=stat['route_id'],
                    date=timezone.now().date(),
                    aggregation_type='hourly',
                    defaults={
                        'impressions': stat['impressions'],
                        'unique_users': stat['unique_users'],
                        'clicks': stat['clicks'],
                        'conversions': stat['conversions'],
                        'revenue': 0.0,  # Would calculate from actual revenue data
                        'avg_response_time_ms': stat['avg_response_time'] or 0,
                        'cache_hit_rate': (stat['cache_hit_rate'] or 0) * 100,
                        'error_rate': (stat['error_rate'] or 0) * 100
                    }
                )
                aggregated_count += 1
            
            # Aggregate exposure stats
            exposure_stats = recent_decisions.values('offer_id').annotate(
                unique_users_exposed=Count('user_id', distinct=True),
                total_exposures=Count('id')
            )
            
            for stat in exposure_stats:
                # Create or update exposure stat
                OfferExposureStat.objects.update_or_create(
                    offer_id=stat['offer_id'],
                    date=timezone.now().date(),
                    aggregation_type='hourly',
                    defaults={
                        'unique_users_exposed': stat['unique_users_exposed'],
                        'total_exposures': stat['total_exposures'],
                        'repeat_exposures': stat['total_exposures'] - stat['unique_users_exposed'],
                        'avg_exposures_per_user': stat['total_exposures'] / stat['unique_users_exposed'] if stat['unique_users_exposed'] > 0 else 0,
                        'max_exposures_per_user': 1  # Would calculate from actual data
                    }
                )
                aggregated_count += 1
            
            logger.info(f"Aggregated {aggregated_count} hourly statistics")
            return aggregated_count
            
        except Exception as e:
            logger.error(f"Error aggregating hourly stats: {e}")
            return 0
    
    def generate_insights(self, tenant_id: int, period_start: timezone.datetime, 
                         period_end: timezone.datetime) -> int:
        """Generate insights for a tenant for a specific period."""
        try:
            generated_count = 0
            
            # Performance insights
            performance_insights = self._generate_performance_insights(tenant_id, period_start, period_end)
            generated_count += len(performance_insights)
            
            # Optimization insights
            optimization_insights = self._generate_optimization_insights(tenant_id, period_start, period_end)
            generated_count += len(optimization_insights)
            
            # Anomaly insights
            anomaly_insights = self._generate_anomaly_insights(tenant_id, period_start, period_end)
            generated_count += len(anomaly_insights)
            
            # Trend insights
            trend_insights = self._generate_trend_insights(tenant_id, period_start, period_end)
            generated_count += len(trend_insights)
            
            logger.info(f"Generated {generated_count} insights for tenant {tenant_id}")
            return generated_count
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return 0
    
    def _generate_performance_insights(self, tenant_id: int, period_start: timezone.datetime, 
                                    period_end: timezone.datetime) -> List[RoutingInsight]:
        """Generate performance insights."""
        insights = []
        
        try:
            # Get performance stats for the period
            stats = RoutePerformanceStat.objects.filter(
                route__tenant_id=tenant_id,
                date__gte=period_start.date(),
                date__lte=period_end.date()
            ).aggregate(
                avg_response_time=Avg('avg_response_time_ms'),
                avg_cache_hit_rate=Avg('cache_hit_rate'),
                avg_error_rate=Avg('error_rate'),
                total_impressions=Sum('impressions'),
                total_conversions=Sum('conversions')
            )
            
            # Check response time
            if stats['avg_response_time'] and stats['avg_response_time'] > 100:
                insights.append(RoutingInsight.objects.create(
                    tenant_id=tenant_id,
                    title='High Response Time Detected',
                    description=f'Average response time is {stats["avg_response_time"]:.2f}ms, which exceeds the 100ms threshold',
                    insight_type='performance',
                    severity='high',
                    confidence=0.9,
                    data={'avg_response_time': stats['avg_response_time']},
                    metrics={'threshold': 100, 'current_value': stats['avg_response_time']},
                    period_start=period_start,
                    period_end=period_end,
                    action_suggestion='Consider optimizing routing logic or increasing cache timeout'
                ))
            
            # Check cache hit rate
            if stats['avg_cache_hit_rate'] and stats['avg_cache_hit_rate'] < 70:
                insights.append(RoutingInsight.objects.create(
                    tenant_id=tenant_id,
                    title='Low Cache Hit Rate',
                    description=f'Cache hit rate is {stats["avg_cache_hit_rate"]:.2f}%, which is below the 70% target',
                    insight_type='performance',
                    severity='medium',
                    confidence=0.8,
                    data={'cache_hit_rate': stats['avg_cache_hit_rate']},
                    metrics={'target': 70, 'current_value': stats['avg_cache_hit_rate']},
                    period_start=period_start,
                    period_end=period_end,
                    action_suggestion='Consider increasing cache timeout or warming up cache more frequently'
                ))
            
            # Check error rate
            if stats['avg_error_rate'] and stats['avg_error_rate'] > 5:
                insights.append(RoutingInsight.objects.create(
                    tenant_id=tenant_id,
                    title='High Error Rate',
                    description=f'Error rate is {stats["avg_error_rate"]:.2f}%, which exceeds the 5% threshold',
                    insight_type='performance',
                    severity='critical',
                    confidence=0.95,
                    data={'error_rate': stats['avg_error_rate']},
                    metrics={'threshold': 5, 'current_value': stats['avg_error_rate']},
                    period_start=period_start,
                    period_end=period_end,
                    action_suggestion='Investigate routing errors and fix underlying issues'
                ))
            
        except Exception as e:
            logger.error(f"Error generating performance insights: {e}")
        
        return insights
    
    def _generate_optimization_insights(self, tenant_id: int, period_start: timezone.datetime, 
                                      period_end: timezone.datetime) -> List[RoutingInsight]:
        """Generate optimization insights."""
        insights = []
        
        try:
            # Get top and bottom performing routes
            top_routes = RoutePerformanceStat.objects.filter(
                route__tenant_id=tenant_id,
                date__gte=period_start.date(),
                date__lte=period_end.date()
            ).order_by('-conversion_rate')[:5]
            
            bottom_routes = RoutePerformanceStat.objects.filter(
                route__tenant_id=tenant_id,
                date__gte=period_start.date(),
                date__lte=period_end.date()
            ).order_by('conversion_rate')[:5]
            
            if top_routes and bottom_routes:
                # Compare performance
                avg_top_cr = sum(route.conversion_rate for route in top_routes) / len(top_routes)
                avg_bottom_cr = sum(route.conversion_rate for route in bottom_routes) / len(bottom_routes)
                
                if avg_top_cr > avg_bottom_cr * 2:
                    insights.append(RoutingInsight.objects.create(
                        tenant_id=tenant_id,
                        title='Significant Performance Gap',
                        description=f'Top performing routes have {avg_top_cr:.2f}% CR vs {avg_bottom_cr:.2f}% for bottom routes',
                        insight_type='optimization',
                        severity='medium',
                        confidence=0.85,
                        data={
                            'top_routes': [{'id': r.route.id, 'cr': r.conversion_rate} for r in top_routes],
                            'bottom_routes': [{'id': r.route.id, 'cr': r.conversion_rate} for r in bottom_routes]
                        },
                        metrics={'top_avg_cr': avg_top_cr, 'bottom_avg_cr': avg_bottom_cr},
                        period_start=period_start,
                        period_end=period_end,
                        action_suggestion='Consider applying successful strategies from top routes to bottom routes'
                    ))
            
        except Exception as e:
            logger.error(f"Error generating optimization insights: {e}")
        
        return insights
    
    def _generate_anomaly_insights(self, tenant_id: int, period_start: timezone.datetime, 
                                 period_end: timezone.datetime) -> List[RoutingInsight]:
        """Generate anomaly insights."""
        insights = []
        
        try:
            # Check for unusual traffic patterns
            daily_stats = RoutePerformanceStat.objects.filter(
                route__tenant_id=tenant_id,
                date__gte=period_start.date(),
                date__lte=period_end.date()
            ).values('date').annotate(
                daily_impressions=Sum('impressions')
            ).order_by('date')
            
            if len(daily_stats) > 1:
                # Calculate average and standard deviation
                impressions = [stat['daily_impressions'] for stat in daily_stats]
                avg_impressions = sum(impressions) / len(impressions)
                
                # Check for outliers (more than 2x average)
                for stat in daily_stats:
                    if stat['daily_impressions'] > avg_impressions * 2:
                        insights.append(RoutingInsight.objects.create(
                            tenant_id=tenant_id,
                            title='Unusual Traffic Spike',
                            description=f'Traffic spike detected on {stat["date"]}: {stat["daily_impressions"]} impressions (avg: {avg_impressions:.0f})',
                            insight_type='anomaly',
                            severity='medium',
                            confidence=0.7,
                            data={'date': stat["date"], 'impressions': stat['daily_impressions']},
                            metrics={'average': avg_impressions, 'spike': stat['daily_impressions']},
                            period_start=period_start,
                            period_end=period_end,
                            action_suggestion='Investigate cause of traffic spike and prepare for future similar events'
                        ))
            
        except Exception as e:
            logger.error(f"Error generating anomaly insights: {e}")
        
        return insights
    
    def _generate_trend_insights(self, tenant_id: int, period_start: timezone.datetime, 
                               period_end: timezone.datetime) -> List[RoutingInsight]:
        """Generate trend insights."""
        insights = []
        
        try:
            # Compare current period with previous period
            previous_period_start = period_start - timezone.timedelta(days=(period_end - period_start).days)
            
            current_stats = RoutePerformanceStat.objects.filter(
                route__tenant_id=tenant_id,
                date__gte=period_start.date(),
                date__lte=period_end.date()
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_conversions=Sum('conversions')
            )
            
            previous_stats = RoutePerformanceStat.objects.filter(
                route__tenant_id=tenant_id,
                date__gte=previous_period_start.date(),
                date__lte=period_start.date()
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_conversions=Sum('conversions')
            )
            
            if current_stats['total_impressions'] and previous_stats['total_impressions']:
                # Calculate growth rates
                impressions_growth = ((current_stats['total_impressions'] - previous_stats['total_impressions']) / 
                                    previous_stats['total_impressions']) * 100
                
                if abs(impressions_growth) > 20:  # More than 20% change
                    trend_direction = 'increase' if impressions_growth > 0 else 'decrease'
                    insights.append(RoutingInsight.objects.create(
                        tenant_id=tenant_id,
                        title=f'Traffic {trend_direction.title()} Trend',
                        description=f'Traffic {trend_direction}d by {abs(impressions_growth):.1f}% compared to previous period',
                        insight_type='trend',
                        severity='low',
                        confidence=0.8,
                        data={
                            'current_impressions': current_stats['total_impressions'],
                            'previous_impressions': previous_stats['total_impressions'],
                            'growth_rate': impressions_growth
                        },
                        metrics={'growth_rate': impressions_growth},
                        period_start=period_start,
                        period_end=period_end,
                        action_suggestion='Monitor trend and adjust routing strategy accordingly'
                    ))
            
        except Exception as e:
            logger.error(f"Error generating trend insights: {e}")
        
        return insights
    
    def get_performance_metrics(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Get performance metrics for a tenant."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get routing decisions stats
            decision_stats = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=cutoff_date
            ).aggregate(
                total_decisions=Count('id'),
                avg_response_time=Avg('response_time_ms'),
                cache_hit_rate=Avg('cache_hit'),
                personalization_rate=Avg('personalization_applied'),
                caps_check_rate=Avg('caps_checked'),
                fallback_rate=Avg('fallback_used')
            )
            
            # Get route performance stats
            route_stats = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date()
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_click_through_rate=Avg('click_through_rate'),
                avg_conversion_rate=Avg('conversion_rate')
            )
            
            # Get exposure stats
            exposure_stats = OfferExposureStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date()
            ).aggregate(
                total_unique_users_exposed=Sum('unique_users_exposed'),
                total_exposures=Sum('total_exposures'),
                avg_exposures_per_user=Avg('avg_exposures_per_user')
            )
            
            return {
                'decision_stats': decision_stats,
                'route_stats': route_stats,
                'exposure_stats': exposure_stats,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific user."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get user routing decisions
            decisions = RoutingDecisionLog.objects.filter(
                user_id=user_id,
                created_at__gte=cutoff_date
            ).aggregate(
                total_decisions=Count('id'),
                avg_score=Avg('score'),
                unique_offers=Count('offer_id', distinct=True),
                cache_hit_rate=Avg('cache_hit'),
                personalization_rate=Avg('personalization_applied')
            )
            
            # Get user offer history
            history = UserOfferHistory.objects.filter(
                user_id=user_id,
                viewed_at__gte=cutoff_date
            ).aggregate(
                total_views=Count('id'),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False)),
                total_revenue=Sum('conversion_value')
            )
            
            # Get user affinity scores
            affinity_scores = OfferAffinityScore.objects.filter(
                user_id=user_id
            ).order_by('-score')[:10]
            
            return {
                'decisions': decisions,
                'history': history,
                'top_affinity_scores': [
                    {
                        'category': score.category,
                        'score': score.score,
                        'confidence': score.confidence
                    }
                    for score in affinity_scores
                ],
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}
    
    def get_route_analytics(self, route_id: int, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific route."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get route performance stats
            stats = RoutePerformanceStat.objects.filter(
                route_id=route_id,
                date__gte=cutoff_date.date()
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_click_through_rate=Avg('click_through_rate'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms'),
                avg_cache_hit_rate=Avg('cache_hit_rate')
            )
            
            # Get routing decisions for this route
            decisions = RoutingDecisionLog.objects.filter(
                route_id=route_id,
                created_at__gte=cutoff_date
            ).aggregate(
                total_decisions=Count('id'),
                avg_score=Avg('score'),
                unique_users=Count('user_id', distinct=True),
                personalization_rate=Avg('personalization_applied')
            )
            
            # Get top users for this route
            top_users = RoutingDecisionLog.objects.filter(
                route_id=route_id,
                created_at__gte=cutoff_date
            ).values('user_id').annotate(
                decision_count=Count('id')
            ).order_by('-decision_count')[:10]
            
            return {
                'performance_stats': stats,
                'decision_stats': decisions,
                'top_users': list(top_users),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting route analytics: {e}")
            return {}
    
    def cleanup_old_data(self) -> int:
        """Clean up old analytics data."""
        try:
            from datetime import timedelta
            
            # Clean up old decision logs
            decision_cutoff = timezone.now() - timedelta(days=DECISION_LOG_RETENTION_DAYS)
            deleted_decisions = RoutingDecisionLog.objects.filter(
                created_at__lt=decision_cutoff
            ).delete()[0]
            
            # Clean up old performance stats
            stats_cutoff = timezone.now() - timedelta(days=PERFORMANCE_STATS_RETENTION_DAYS)
            deleted_stats = RoutePerformanceStat.objects.filter(
                date__lt=stats_cutoff.date()
            ).delete()[0]
            
            total_deleted = deleted_decisions + deleted_stats
            
            logger.info(f"Cleaned up {total_deleted} old analytics records")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0


# Singleton instance
analytics_service = RoutingAnalyticsService()
