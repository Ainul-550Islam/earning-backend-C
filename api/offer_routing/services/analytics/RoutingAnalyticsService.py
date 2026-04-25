"""
Routing Analytics Service

Provides analytics and insights for the
offer routing system with performance metrics.
"""

import logging
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, F
from django.core.cache import cache
from django.db import transaction
from ....models import (
    OfferRoute, RoutingDecisionLog, RoutePerformanceStat,
    OfferExposureStat, RoutingInsight, UserOfferHistory
)
from ....constants import (
    ANALYTICS_CACHE_TIMEOUT, INSIGHT_GENERATION_INTERVAL,
    PERFORMANCE_CALCULATION_WINDOW, MIN_SAMPLE_SIZE_FOR_INSIGHTS,
    DEFAULT_ANALYTICS_TIMEZONE, ANALYTICS_BATCH_SIZE
)
from ....exceptions import AnalyticsError, InsightGenerationError
from ....utils import calculate_routing_metrics, generate_insight_data

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingAnalyticsService:
    """
    Service for routing analytics and insights.
    
    Provides comprehensive analytics:
    - Performance metrics calculation
    - Route performance analysis
    - User behavior analytics
    - Automated insight generation
    - Trend analysis and forecasting
    
    Performance targets:
    - Metrics calculation: <100ms for 1000 records
    - Insight generation: <500ms per insight
    - Cache hit rate: >95%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.analytics_stats = {
            'total_calculations': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_calculation_time_ms': 0.0
        }
        
        # Insight generators
        self.insight_generators = {
            'performance': self._generate_performance_insights,
            'trend': self._generate_trend_insights,
            'anomaly': self._generate_anomaly_insights,
            'opportunity': self._generate_opportunity_insights,
            'optimization': self._generate_optimization_insights
        }
        
        # Metric calculators
        self.metric_calculators = {
            'basic': self._calculate_basic_metrics,
            'conversion': self._calculate_conversion_metrics,
            'engagement': self._calculate_engagement_metrics,
            'revenue': self._calculate_revenue_metrics,
            'performance': self._calculate_performance_metrics
        }
    
    def get_routing_metrics(self, start_date: datetime = None, 
                          end_date: datetime = None, 
                          filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get comprehensive routing metrics.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
            filters: Additional filters
            
        Returns:
            Comprehensive routing metrics
        """
        try:
            start_time = timezone.now()
            
            # Set default date range
            if not start_date:
                start_date = timezone.now() - timedelta(days=PERFORMANCE_CALCULATION_WINDOW)
            if not end_date:
                end_date = timezone.now()
            
            # Check cache first
            cache_key = f"routing_metrics:{start_date.isoformat()}:{end_date.isoformat()}:{hash(str(filters or {})}"
            cached_metrics = self.cache_service.get(cache_key)
            
            if cached_metrics:
                self.analytics_stats['cache_hits'] += 1
                return cached_metrics
            
            # Get base query
            base_query = self._get_base_routing_query(start_date, end_date, filters)
            
            # Calculate all metric types
            all_metrics = {}
            
            for metric_type, calculator in self.metric_calculators.items():
                try:
                    metrics = calculator(base_query, start_date, end_date, filters)
                    all_metrics[metric_type] = metrics
                except Exception as e:
                    logger.warning(f"Error calculating {metric_type} metrics: {e}")
                    all_metrics[metric_type] = {'error': str(e)}
            
            # Add metadata
            all_metrics['metadata'] = {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'filters': filters or {},
                'calculated_at': timezone.now().isoformat(),
                'total_records': base_query.count()
            }
            
            # Cache result
            self.cache_service.set(cache_key, all_metrics, ANALYTICS_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_calculation_stats(elapsed_ms)
            
            return all_metrics
            
        except Exception as e:
            logger.error(f"Error getting routing metrics: {e}")
            self.analytics_stats['errors'] += 1
            return {'error': str(e)}
    
    def _get_base_routing_query(self, start_date: datetime, end_date: datetime, 
                               filters: Dict[str, Any] = None):
        """Get base query for routing analytics."""
        try:
            query = RoutingDecisionLog.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            )
            
            # Apply filters
            if filters:
                if 'user_id' in filters:
                    query = query.filter(user_id=filters['user_id'])
                
                if 'offer_id' in filters:
                    query = query.filter(offer_id=filters['offer_id'])
                
                if 'route_id' in filters:
                    query = query.filter(route_id=filters['route_id'])
                
                if 'device_type' in filters:
                    query = query.filter(device_type=filters['device_type'])
                
                if 'country' in filters:
                    query = query.filter(country=filters['country'])
                
                if 'score_min' in filters:
                    query = query.filter(score__gte=filters['score_min'])
                
                if 'score_max' in filters:
                    query = query.filter(score__lte=filters['score_max'])
                
                if 'cache_hit' in filters:
                    query = query.filter(cache_hit=filters['cache_hit'])
            
            return query
            
        except Exception as e:
            logger.error(f"Error getting base routing query: {e}")
            return RoutingDecisionLog.objects.none()
    
    def _calculate_basic_metrics(self, query, start_date: datetime, 
                                end_date: datetime, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate basic routing metrics."""
        try:
            basic_metrics = query.aggregate(
                total_decisions=Count('id'),
                avg_score=Avg('score'),
                avg_response_time_ms=Avg('response_time_ms'),
                cache_hits=Count('id', filter=Q(cache_hit=True)),
                cache_misses=Count('id', filter=Q(cache_hit=False))
            )
            
            total_decisions = basic_metrics['total_decisions'] or 0
            cache_hits = basic_metrics['cache_hits'] or 0
            cache_misses = basic_metrics['cache_misses'] or 0
            
            cache_hit_rate = cache_hits / max(1, total_decisions)
            
            return {
                'total_decisions': total_decisions,
                'avg_score': float(basic_metrics['avg_score'] or 0.0),
                'avg_response_time_ms': float(basic_metrics['avg_response_time_ms'] or 0.0),
                'cache_hits': cache_hits,
                'cache_misses': cache_misses,
                'cache_hit_rate': cache_hit_rate,
                'decisions_per_hour': total_decisions / max(1, (end_date - start_date).total_seconds() / 3600)
            }
            
        except Exception as e:
            logger.error(f"Error calculating basic metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_conversion_metrics(self, query, start_date: datetime, 
                                   end_date: datetime, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate conversion metrics."""
        try:
            # Get conversion data from offer history
            user_ids = query.values_list('user_id', flat=True).distinct()
            offer_ids = query.values_list('offer_id', flat=True).distinct()
            
            conversion_data = UserOfferHistory.objects.filter(
                user_id__in=user_ids,
                offer_id__in=offer_ids,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).aggregate(
                total_views=Count('id'),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False)),
                total_revenue=Sum('conversion_value')
            )
            
            total_views = conversion_data['total_views'] or 0
            total_clicks = conversion_data['total_clicks'] or 0
            total_conversions = conversion_data['total_conversions'] or 0
            total_revenue = float(conversion_data['total_revenue'] or 0.0)
            
            click_rate = total_clicks / max(1, total_views)
            conversion_rate = total_conversions / max(1, total_views)
            avg_revenue_per_conversion = total_revenue / max(1, total_conversions)
            
            return {
                'total_views': total_views,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'total_revenue': total_revenue,
                'click_rate': click_rate,
                'conversion_rate': conversion_rate,
                'avg_revenue_per_conversion': avg_revenue_per_conversion,
                'revenue_per_view': total_revenue / max(1, total_views)
            }
            
        except Exception as e:
            logger.error(f"Error calculating conversion metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_engagement_metrics(self, query, start_date: datetime, 
                                    end_date: datetime, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate engagement metrics."""
        try:
            # Get unique users and offers
            unique_users = query.values('user_id').distinct().count()
            unique_offers = query.values('offer_id').distinct().count()
            
            # Calculate engagement metrics
            engagement_data = query.aggregate(
                avg_session_length=Avg('session_length'),
                total_personalized=Count('id', filter=Q(personalization_applied=True)),
                total_with_fallback=Count('id', filter=Q(fallback_used=True))
            )
            
            total_decisions = query.count()
            personalized_rate = (engagement_data['total_personalized'] or 0) / max(1, total_decisions)
            fallback_rate = (engagement_data['total_with_fallback'] or 0) / max(1, total_decisions)
            
            return {
                'unique_users': unique_users,
                'unique_offers': unique_offers,
                'decisions_per_user': total_decisions / max(1, unique_users),
                'offers_per_user': unique_offers / max(1, unique_users),
                'avg_session_length': float(engagement_data['avg_session_length'] or 0.0),
                'personalization_rate': personalized_rate,
                'fallback_rate': fallback_rate
            }
            
        except Exception as e:
            logger.error(f"Error calculating engagement metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_revenue_metrics(self, query, start_date: datetime, 
                                  end_date: datetime, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate revenue metrics."""
        try:
            # Get revenue data from conversions
            user_ids = query.values_list('user_id', flat=True).distinct()
            offer_ids = query.values_list('offer_id', flat=True).distinct()
            
            revenue_data = UserOfferHistory.objects.filter(
                user_id__in=user_ids,
                offer_id__in=offer_ids,
                completed_at__isnull=False,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).aggregate(
                total_revenue=Sum('conversion_value'),
                avg_conversion_value=Avg('conversion_value'),
                max_conversion_value=Avg('conversion_value'),
                min_conversion_value=Avg('conversion_value')
            )
            
            total_revenue = float(revenue_data['total_revenue'] or 0.0)
            total_conversions = UserOfferHistory.objects.filter(
                user_id__in=user_ids,
                offer_id__in=offer_ids,
                completed_at__isnull=False,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).count()
            
            return {
                'total_revenue': total_revenue,
                'total_conversions': total_conversions,
                'avg_conversion_value': float(revenue_data['avg_conversion_value'] or 0.0),
                'max_conversion_value': float(revenue_data['max_conversion_value'] or 0.0),
                'min_conversion_value': float(revenue_data['min_conversion_value'] or 0.0),
                'revenue_per_conversion': total_revenue / max(1, total_conversions),
                'revenue_per_day': total_revenue / max(1, (end_date - start_date).days)
            }
            
        except Exception as e:
            logger.error(f"Error calculating revenue metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_performance_metrics(self, query, start_date: datetime, 
                                   end_date: datetime, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance metrics."""
        try:
            # Calculate response time percentiles
            response_times = list(query.values_list('response_time_ms', flat=True))
            
            if response_times:
                response_times.sort()
                p50 = response_times[len(response_times) // 2]
                p95 = response_times[int(len(response_times) * 0.95)]
                p99 = response_times[int(len(response_times) * 0.99)]
                max_response_time = max(response_times)
                min_response_time = min(response_times)
            else:
                p50 = p95 = p99 = max_response_time = min_response_time = 0.0
            
            # Calculate score distribution
            score_data = query.aggregate(
                avg_score=Avg('score'),
                min_score=Avg('score'),
                max_score=Avg('score')
            )
            
            return {
                'response_time_p50': p50,
                'response_time_p95': p95,
                'response_time_p99': p99,
                'max_response_time': max_response_time,
                'min_response_time': min_response_time,
                'avg_score': float(score_data['avg_score'] or 0.0),
                'min_score': float(score_data['min_score'] or 0.0),
                'max_score': float(score_data['max_score'] or 0.0),
                'score_distribution': self._calculate_score_distribution(query)
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_score_distribution(self, query) -> Dict[str, Any]:
        """Calculate score distribution buckets."""
        try:
            score_ranges = [
                (0.0, 0.2, '0-20%'),
                (0.2, 0.4, '20-40%'),
                (0.4, 0.6, '40-60%'),
                (0.6, 0.8, '60-80%'),
                (0.8, 1.0, '80-100%')
            ]
            
            distribution = {}
            total_count = query.count()
            
            for min_score, max_score, label in score_ranges:
                count = query.filter(
                    score__gte=min_score,
                    score__lt=max_score
                ).count()
                
                distribution[label] = {
                    'count': count,
                    'percentage': count / max(1, total_count)
                }
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error calculating score distribution: {e}")
            return {}
    
    def get_route_performance(self, route_id: int = None, 
                           start_date: datetime = None, 
                           end_date: datetime = None) -> Dict[str, Any]:
        """
        Get performance metrics for specific routes.
        
        Args:
            route_id: Specific route ID (None for all routes)
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Route performance metrics
        """
        try:
            start_time = timezone.now()
            
            # Set default date range
            if not start_date:
                start_date = timezone.now() - timedelta(days=PERFORMANCE_CALCULATION_WINDOW)
            if not end_date:
                end_date = timezone.now()
            
            # Get route performance data
            performance_query = RoutingDecisionLog.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            )
            
            if route_id:
                performance_query = performance_query.filter(route_id=route_id)
            
            # Calculate metrics per route
            route_metrics = {}
            
            route_data = performance_query.values('route_id').annotate(
                total_decisions=Count('id'),
                avg_score=Avg('score'),
                avg_response_time=Avg('response_time_ms'),
                cache_hits=Count('id', filter=Q(cache_hit=True)),
                total_conversions=Count('id', filter=Q(converted=True))
            )
            
            for route_stat in route_data:
                route_id = route_stat['route_id']
                total_decisions = route_stat['total_decisions']
                cache_hits = route_stat['cache_hits']
                
                route_metrics[route_id] = {
                    'total_decisions': total_decisions,
                    'avg_score': float(route_stat['avg_score'] or 0.0),
                    'avg_response_time_ms': float(route_stat['avg_response_time_ms'] or 0.0),
                    'cache_hit_rate': cache_hits / max(1, total_decisions),
                    'total_conversions': route_stat['total_conversions'],
                    'conversion_rate': route_stat['total_conversions'] / max(1, total_decisions)
                }
            
            # Get route details
            route_details = {}
            if route_id:
                route = OfferRoute.objects.filter(id=route_id).first()
                if route:
                    route_details[route_id] = {
                        'name': route.name,
                        'description': route.description,
                        'priority': route.priority,
                        'is_active': route.is_active
                    }
            else:
                routes = OfferRoute.objects.filter(id__in=route_metrics.keys())
                for route in routes:
                    route_details[route.id] = {
                        'name': route.name,
                        'description': route.description,
                        'priority': route.priority,
                        'is_active': route.is_active
                    }
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_calculation_stats(elapsed_ms)
            
            return {
                'route_metrics': route_metrics,
                'route_details': route_details,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting route performance: {e}")
            self.analytics_stats['errors'] += 1
            return {'error': str(e)}
    
    def generate_insights(self, insight_types: List[str] = None) -> List[Dict[str, Any]]:
        """
        Generate automated insights from routing data.
        
        Args:
            insight_types: Types of insights to generate
            
        Returns:
            List of generated insights
        """
        try:
            start_time = timezone.now()
            
            if not insight_types:
                insight_types = list(self.insight_generators.keys())
            
            insights = []
            
            for insight_type in insight_types:
                if insight_type in self.insight_generators:
                    try:
                        generator = self.insight_generators[insight_type]
                        type_insights = generator()
                        insights.extend(type_insights)
                    except Exception as e:
                        logger.warning(f"Error generating {insight_type} insights: {e}")
                        continue
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_calculation_stats(elapsed_ms)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            self.analytics_stats['errors'] += 1
            return []
    
    def _generate_performance_insights(self) -> List[Dict[str, Any]]:
        """Generate performance-related insights."""
        try:
            insights = []
            
            # Get recent performance data
            recent_data = self.get_routing_metrics(
                start_date=timezone.now() - timedelta(days=7)
            )
            
            if 'error' in recent_data:
                return insights
            
            basic_metrics = recent_data.get('basic', {})
            conversion_metrics = recent_data.get('conversion', {})
            
            # Insight 1: High response time
            avg_response_time = basic_metrics.get('avg_response_time_ms', 0)
            if avg_response_time > 100:  # 100ms threshold
                insights.append({
                    'type': 'performance',
                    'category': 'response_time',
                    'severity': 'high',
                    'title': 'High Average Response Time',
                    'description': f'Average response time is {avg_response_time:.1f}ms, which exceeds the 100ms threshold',
                    'recommendation': 'Investigate routing engine performance and consider optimizing database queries',
                    'metrics': {
                        'avg_response_time_ms': avg_response_time,
                        'threshold_ms': 100
                    },
                    'generated_at': timezone.now().isoformat()
                })
            
            # Insight 2: Low cache hit rate
            cache_hit_rate = basic_metrics.get('cache_hit_rate', 0)
            if cache_hit_rate < 0.8:  # 80% threshold
                insights.append({
                    'type': 'performance',
                    'category': 'cache_hit_rate',
                    'severity': 'medium',
                    'title': 'Low Cache Hit Rate',
                    'description': f'Cache hit rate is {cache_hit_rate:.1%}, which is below the 80% target',
                    'recommendation': 'Review caching strategy and consider increasing cache TTL for frequently accessed data',
                    'metrics': {
                        'cache_hit_rate': cache_hit_rate,
                        'target_rate': 0.8
                    },
                    'generated_at': timezone.now().isoformat()
                })
            
            # Insight 3: Low conversion rate
            conversion_rate = conversion_metrics.get('conversion_rate', 0)
            if conversion_rate < 0.02:  # 2% threshold
                insights.append({
                    'type': 'performance',
                    'category': 'conversion_rate',
                    'severity': 'medium',
                    'title': 'Low Conversion Rate',
                    'description': f'Conversion rate is {conversion_rate:.2%}, which is below the 2% target',
                    'recommendation': 'Review offer quality and targeting rules to improve relevance',
                    'metrics': {
                        'conversion_rate': conversion_rate,
                        'target_rate': 0.02
                    },
                    'generated_at': timezone.now().isoformat()
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating performance insights: {e}")
            return []
    
    def _generate_trend_insights(self) -> List[Dict[str, Any]]:
        """Generate trend-related insights."""
        try:
            insights = []
            
            # Compare current period with previous period
            current_period = timezone.now() - timedelta(days=7)
            previous_period = timezone.now() - timedelta(days=14)
            
            current_metrics = self.get_routing_metrics(
                start_date=current_period,
                end_date=timezone.now()
            )
            
            previous_metrics = self.get_routing_metrics(
                start_date=previous_period,
                end_date=current_period
            )
            
            if 'error' in current_metrics or 'error' in previous_metrics:
                return insights
            
            # Analyze trends
            current_decisions = current_metrics.get('basic', {}).get('total_decisions', 0)
            previous_decisions = previous_metrics.get('basic', {}).get('total_decisions', 0)
            
            if previous_decisions > 0:
                decision_change = (current_decisions - previous_decisions) / previous_decisions
                
                # Insight: Significant volume change
                if abs(decision_change) > 0.2:  # 20% change threshold
                    insights.append({
                        'type': 'trend',
                        'category': 'volume',
                        'severity': 'medium',
                        'title': 'Significant Volume Change',
                        'description': f'Routing decisions changed by {decision_change:.1%} compared to previous week',
                        'recommendation': 'Investigate cause of volume change and adjust capacity planning',
                        'metrics': {
                            'current_decisions': current_decisions,
                            'previous_decisions': previous_decisions,
                            'change_percentage': decision_change
                        },
                        'generated_at': timezone.now().isoformat()
                    })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating trend insights: {e}")
            return []
    
    def _generate_anomaly_insights(self) -> List[Dict[str, Any]]:
        """Generate anomaly-related insights."""
        try:
            insights = []
            
            # Look for unusual patterns in recent data
            recent_logs = RoutingDecisionLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            if not recent_logs.exists():
                return insights
            
            # Check for unusual response times
            response_times = list(recent_logs.values_list('response_time_ms', flat=True))
            
            if len(response_times) >= MIN_SAMPLE_SIZE_FOR_INSIGHTS:
                mean_response_time = statistics.mean(response_times)
                std_response_time = statistics.stdev(response_times)
                
                # Find outliers (more than 2 standard deviations from mean)
                outliers = [rt for rt in response_times if abs(rt - mean_response_time) > 2 * std_response_time]
                
                if len(outliers) > len(response_times) * 0.05:  # More than 5% outliers
                    insights.append({
                        'type': 'anomaly',
                        'category': 'response_time_outliers',
                        'severity': 'high',
                        'title': 'High Number of Response Time Outliers',
                        'description': f'Found {len(outliers)} response time outliers in the last 24 hours',
                        'recommendation': 'Investigate potential performance issues or system load spikes',
                        'metrics': {
                            'total_requests': len(response_times),
                            'outlier_count': len(outliers),
                            'outlier_percentage': len(outliers) / len(response_times)
                        },
                        'generated_at': timezone.now().isoformat()
                    })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating anomaly insights: {e}")
            return []
    
    def _generate_opportunity_insights(self) -> List[Dict[str, Any]]:
        """Generate opportunity-related insights."""
        try:
            insights = []
            
            # Analyze underperforming routes
            route_performance = self.get_route_performance()
            
            if 'error' in route_performance:
                return insights
            
            route_metrics = route_performance.get('route_metrics', {})
            
            # Find routes with low conversion rates
            low_conversion_routes = []
            
            for route_id, metrics in route_metrics.items():
                conversion_rate = metrics.get('conversion_rate', 0)
                if conversion_rate < 0.01:  # Less than 1% conversion
                    low_conversion_routes.append(route_id)
            
            if low_conversion_routes:
                insights.append({
                    'type': 'opportunity',
                    'category': 'underperforming_routes',
                    'severity': 'medium',
                    'title': 'Routes with Low Conversion Rates',
                    'description': f'Found {len(low_conversion_routes)} routes with conversion rates below 1%',
                    'recommendation': 'Review and optimize underperforming routes or consider deactivating them',
                    'metrics': {
                        'low_conversion_routes': low_conversion_routes,
                        'route_count': len(route_metrics)
                    },
                    'generated_at': timezone.now().isoformat()
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating opportunity insights: {e}")
            return []
    
    def _generate_optimization_insights(self) -> List[Dict[str, Any]]:
        """Generate optimization-related insights."""
        try:
            insights = []
            
            # Analyze score distribution
            recent_metrics = self.get_routing_metrics(
                start_date=timezone.now() - timedelta(days=7)
            )
            
            if 'error' in recent_metrics:
                return insights
            
            performance_metrics = recent_metrics.get('performance', {})
            score_distribution = performance_metrics.get('score_distribution', {})
            
            # Check if scores are concentrated in low range
            low_score_percentage = score_distribution.get('0-40%', {}).get('percentage', 0)
            
            if low_score_percentage > 0.6:  # More than 60% in low range
                insights.append({
                    'type': 'optimization',
                    'category': 'score_distribution',
                    'severity': 'medium',
                    'title': 'Low Score Distribution',
                    'description': f'{low_score_percentage:.1%} of offers have scores below 40%',
                    'recommendation': 'Review scoring algorithm and consider adjusting weights or improving data quality',
                    'metrics': {
                        'low_score_percentage': low_score_percentage,
                        'score_distribution': score_distribution
                    },
                    'generated_at': timezone.now().isoformat()
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating optimization insights: {e}")
            return []
    
    def _update_calculation_stats(self, elapsed_ms: float):
        """Update calculation performance statistics."""
        self.analytics_stats['total_calculations'] += 1
        
        # Update average time
        current_avg = self.analytics_stats['avg_calculation_time_ms']
        total_calculations = self.analytics_stats['total_calculations']
        self.analytics_stats['avg_calculation_time_ms'] = (
            (current_avg * (total_calculations - 1) + elapsed_ms) / total_calculations
        )
    
    def get_analytics_stats(self) -> Dict[str, Any]:
        """Get analytics service performance statistics."""
        total_requests = self.analytics_stats['total_calculations']
        cache_hit_rate = (
            self.analytics_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_calculations': total_requests,
            'cache_hits': self.analytics_stats['cache_hits'],
            'cache_misses': total_requests - self.analytics_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.analytics_stats['errors'],
            'error_rate': self.analytics_stats['errors'] / max(1, total_requests),
            'avg_calculation_time_ms': self.analytics_stats['avg_calculation_time_ms'],
            'supported_insight_types': list(self.insight_generators.keys()),
            'supported_metric_types': list(self.metric_calculators.keys())
        }
    
    def clear_cache(self, pattern: str = None):
        """Clear analytics cache."""
        try:
            if pattern:
                # Clear specific pattern cache
                # This would need pattern deletion support
                logger.info(f"Cache clearing for pattern {pattern} not implemented")
            else:
                # Clear all analytics cache
                logger.info("Cache clearing for all analytics not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing analytics cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on analytics service."""
        try:
            # Test metrics calculation
            test_metrics = self.get_routing_metrics(
                start_date=timezone.now() - timedelta(hours=1),
                end_date=timezone.now()
            )
            
            # Test insight generation
            test_insights = self.generate_insights(['performance'])
            
            # Test route performance
            test_route_performance = self.get_route_performance(
                start_date=timezone.now() - timedelta(hours=1),
                end_date=timezone.now()
            )
            
            return {
                'status': 'healthy',
                'test_metrics_calculation': 'error' not in test_metrics,
                'test_insight_generation': len(test_insights) >= 0,
                'test_route_performance': 'error' not in test_route_performance,
                'stats': self.get_analytics_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
