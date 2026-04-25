"""
Reporter Service for Offer Routing System

This module provides reporting functionality for generating
reports on routing performance, analytics, and business metrics.
"""

import logging
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Max, Min, Q, F
from ..models import (
    RoutePerformanceStat, OfferExposureStat, RoutingDecisionLog,
    RoutingInsight, RoutingABTest, ABTestResult
)
from ..constants import PERFORMANCE_STATS_RETENTION_DAYS

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingReporter:
    """
    Service for generating routing reports.
    
    Provides comprehensive reporting on performance,
    analytics, and business metrics.
    """
    
    def __init__(self):
        self.cache_service = None
        self.analytics_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize reporter services."""
        try:
            from .cache import RoutingCacheService
            from .analytics import RoutingAnalyticsService
            
            self.cache_service = RoutingCacheService()
            self.analytics_service = RoutingAnalyticsService()
        except ImportError as e:
            logger.error(f"Failed to initialize reporter services: {e}")
    
    def generate_performance_report(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        try:
            report = {
                'report_type': 'performance',
                'tenant_id': tenant_id,
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
                'summary': {},
                'route_performance': {},
                'user_analytics': {},
                'trending_metrics': {},
                'recommendations': []
            }
            
            # Get performance summary
            report['summary'] = self._get_performance_summary(tenant_id, days)
            
            # Get route performance details
            report['route_performance'] = self._get_route_performance_details(tenant_id, days)
            
            # Get user analytics
            report['user_analytics'] = self._get_user_analytics_summary(tenant_id, days)
            
            # Get trending metrics
            report['trending_metrics'] = self._get_trending_metrics(tenant_id, days)
            
            # Generate recommendations
            report['recommendations'] = self._generate_performance_recommendations(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {
                'report_type': 'performance',
                'tenant_id': tenant_id,
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
                'error': str(e)
            }
    
    def _get_performance_summary(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get performance summary."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get overall performance metrics
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
            
            # Get route performance metrics
            route_stats = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date()
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_click_through_rate=Avg('click_through_rate'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms')
            )
            
            # Calculate derived metrics
            total_decisions = decision_stats['total_decisions'] or 0
            total_impressions = route_stats['total_impressions'] or 0
            total_clicks = route_stats['total_clicks'] or 0
            total_conversions = route_stats['total_conversions'] or 0
            total_revenue = route_stats['total_revenue'] or 0
            
            overall_cr = (total_conversions / total_impressions * 100) if total_impressions > 0 else 0
            overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            avg_revenue_per_conversion = (total_revenue / total_conversions) if total_conversions > 0 else 0
            
            return {
                'total_decisions': total_decisions,
                'avg_response_time_ms': decision_stats['avg_response_time'] or 0,
                'cache_hit_rate': (decision_stats['cache_hit_rate'] or 0) * 100,
                'personalization_rate': (decision_stats['personalization_rate'] or 0) * 100,
                'caps_check_rate': (decision_stats['caps_check_rate'] or 0) * 100,
                'fallback_rate': (decision_stats['fallback_used'] or 0) * 100,
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'total_revenue': float(total_revenue),
                'overall_conversion_rate': overall_cr,
                'overall_click_through_rate': overall_ctr,
                'avg_revenue_per_conversion': float(avg_revenue_per_conversion),
                'avg_route_response_time': route_stats['avg_response_time_ms'] or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
    
    def _get_route_performance_details(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get detailed route performance."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get top performing routes
            top_routes = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date()
            ).values('route_id', 'route__name').annotate(
                total_impressions=Sum('impressions'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms')
            ).order_by('-total_revenue')[:10]
            
            # Get bottom performing routes
            bottom_routes = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date(),
                total_impressions__gt=0  # Only routes with impressions
            ).values('route_id', 'route__name').annotate(
                total_impressions=Sum('impressions'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms')
            ).order_by('avg_conversion_rate')[:10]
            
            return {
                'top_performing_routes': list(top_routes),
                'bottom_performing_routes': list(bottom_routes),
                'total_routes_analyzed': RoutePerformanceStat.objects.filter(
                    tenant_id=tenant_id,
                    date__gte=cutoff_date.date()
                ).values('route_id').distinct().count()
            }
            
        except Exception as e:
            logger.error(f"Error getting route performance details: {e}")
            return {}
    
    def _get_user_analytics_summary(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get user analytics summary."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get user engagement metrics
            user_stats = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=cutoff_date
            ).aggregate(
                total_users=Count('user_id', distinct=True),
                avg_decisions_per_user=Avg('decisions_per_user'),
                avg_score=Avg('score'),
                unique_offers_per_user=Avg('unique_offers_per_user')
            )
            
            # Get user segmentation
            user_segments = self._calculate_user_segments(tenant_id, cutoff_date)
            
            return {
                'total_active_users': user_stats['total_users'] or 0,
                'avg_decisions_per_user': user_stats['avg_decisions_per_user'] or 0,
                'avg_score': user_stats['avg_score'] or 0,
                'avg_unique_offers_per_user': user_stats['avg_unique_offers_per_user'] or 0,
                'user_segments': user_segments
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics summary: {e}")
            return {}
    
    def _calculate_user_segments(self, tenant_id: int, cutoff_date: timezone.datetime) -> Dict[str, Any]:
        """Calculate user segments based on activity."""
        try:
            # Get user activity levels
            user_activity = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=cutoff_date
            ).values('user_id').annotate(
                decision_count=Count('id'),
                avg_score=Avg('score')
            )
            
            segments = {
                'highly_active': 0,    # > 100 decisions
                'moderately_active': 0,  # 10-100 decisions
                'low_activity': 0,     # 1-10 decisions
                'inactive': 0           # 0 decisions
            }
            
            for user_data in user_activity:
                decision_count = user_data['decision_count']
                if decision_count > 100:
                    segments['highly_active'] += 1
                elif decision_count > 10:
                    segments['moderately_active'] += 1
                elif decision_count > 0:
                    segments['low_activity'] += 1
                else:
                    segments['inactive'] += 1
            
            return segments
            
        except Exception as e:
            logger.error(f"Error calculating user segments: {e}")
            return {}
    
    def _get_trending_metrics(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get trending metrics."""
        try:
            from datetime import timedelta
            
            # Compare current period with previous period
            current_start = timezone.now() - timedelta(days=days)
            previous_start = current_start - timedelta(days=days)
            
            # Get current period stats
            current_stats = self._get_period_stats(tenant_id, current_start, timezone.now())
            
            # Get previous period stats
            previous_stats = self._get_period_stats(tenant_id, previous_start, current_start)
            
            # Calculate trends
            trends = {}
            
            for metric in ['total_decisions', 'avg_response_time', 'cache_hit_rate', 
                          'total_conversions', 'total_revenue']:
                current_value = current_stats.get(metric, 0)
                previous_value = previous_stats.get(metric, 0)
                
                if previous_value > 0:
                    change_percent = ((current_value - previous_value) / previous_value) * 100
                    trends[metric] = {
                        'current': current_value,
                        'previous': previous_value,
                        'change_percent': change_percent,
                        'trend': 'up' if change_percent > 0 else 'down'
                    }
                else:
                    trends[metric] = {
                        'current': current_value,
                        'previous': previous_value,
                        'change_percent': 0,
                        'trend': 'stable'
                    }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting trending metrics: {e}")
            return {}
    
    def _get_period_stats(self, tenant_id: int, start_date: timezone.datetime, 
                         end_date: timezone.datetime) -> Dict[str, Any]:
        """Get statistics for a specific period."""
        try:
            decision_stats = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=start_date,
                created_at__lt=end_date
            ).aggregate(
                total_decisions=Count('id'),
                avg_response_time=Avg('response_time_ms'),
                cache_hit_rate=Avg('cache_hit')
            )
            
            route_stats = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=start_date.date(),
                date__lt=end_date.date()
            ).aggregate(
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue')
            )
            
            return {
                'total_decisions': decision_stats['total_decisions'] or 0,
                'avg_response_time': decision_stats['avg_response_time'] or 0,
                'cache_hit_rate': decision_stats['cache_hit_rate'] or 0,
                'total_conversions': route_stats['total_conversions'] or 0,
                'total_revenue': route_stats['total_revenue'] or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting period stats: {e}")
            return {}
    
    def _generate_performance_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        try:
            summary = report.get('summary', {})
            
            # Response time recommendations
            avg_response_time = summary.get('avg_response_time_ms', 0)
            if avg_response_time > 100:
                recommendations.append(f"High average response time ({avg_response_time:.1f}ms) - consider optimizing routing logic")
            elif avg_response_time > 50:
                recommendations.append(f"Response time could be improved ({avg_response_time:.1f}ms) - consider cache optimization")
            
            # Cache hit rate recommendations
            cache_hit_rate = summary.get('cache_hit_rate', 0)
            if cache_hit_rate < 70:
                recommendations.append(f"Low cache hit rate ({cache_hit_rate:.1f}%) - consider increasing cache timeout")
            elif cache_hit_rate < 85:
                recommendations.append(f"Cache hit rate could be improved ({cache_hit_rate:.1f}%) - consider cache warming")
            
            # Conversion rate recommendations
            overall_cr = summary.get('overall_conversion_rate', 0)
            if overall_cr < 1:
                recommendations.append(f"Low conversion rate ({overall_cr:.2f}%) - review offer relevance and targeting")
            elif overall_cr < 3:
                recommendations.append(f"Conversion rate could be improved ({overall_cr:.2f}%) - consider A/B testing")
            
            # Personalization recommendations
            personalization_rate = summary.get('personalization_rate', 0)
            if personalization_rate < 50:
                recommendations.append(f"Low personalization rate ({personalization_rate:.1f}%) - enable more personalization features")
            
            # Fallback rate recommendations
            fallback_rate = summary.get('fallback_rate', 0)
            if fallback_rate > 20:
                recommendations.append(f"High fallback rate ({fallback_rate:.1f}%) - review targeting rules")
            
            if not recommendations:
                recommendations.append("Performance metrics look good - continue monitoring")
            
        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")
        
        return recommendations
    
    def generate_ab_test_report(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Generate A/B testing report."""
        try:
            report = {
                'report_type': 'ab_test',
                'tenant_id': tenant_id,
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
                'summary': {},
                'test_results': {},
                'winner_analysis': {},
                'recommendations': []
            }
            
            # Get A/B test summary
            report['summary'] = self._get_ab_test_summary(tenant_id, days)
            
            # Get detailed test results
            report['test_results'] = self._get_ab_test_results(tenant_id, days)
            
            # Get winner analysis
            report['winner_analysis'] = self._get_winner_analysis(tenant_id, days)
            
            # Generate recommendations
            report['recommendations'] = self._generate_ab_test_recommendations(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating A/B test report: {e}")
            return {
                'report_type': 'ab_test',
                'tenant_id': tenant_id,
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
                'error': str(e)
            }
    
    def _get_ab_test_summary(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get A/B test summary."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get test statistics
            test_stats = RoutingABTest.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=cutoff_date
            ).aggregate(
                total_tests=Count('id'),
                active_tests=Count('id', filter=Q(is_active=True)),
                completed_tests=Count('id', filter=Q(ended_at__isnull=False)),
                tests_with_winners=Count('id', filter=Q(winner__isnull=False))
            )
            
            # Get result statistics
            result_stats = ABTestResult.objects.filter(
                test__tenant_id=tenant_id,
                analyzed_at__gte=cutoff_date
            ).aggregate(
                total_results=Count('id'),
                significant_results=Count('id', filter=Q(is_significant=True)),
                avg_confidence=Avg('winner_confidence'),
                avg_effect_size=Avg('effect_size')
            )
            
            return {
                'total_tests': test_stats['total_tests'] or 0,
                'active_tests': test_stats['active_tests'] or 0,
                'completed_tests': test_stats['completed_tests'] or 0,
                'tests_with_winners': test_stats['tests_with_winners'] or 0,
                'total_results': result_stats['total_results'] or 0,
                'significant_results': result_stats['significant_results'] or 0,
                'avg_confidence': result_stats['avg_confidence'] or 0,
                'avg_effect_size': result_stats['avg_effect_size'] or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting A/B test summary: {e}")
            return {}
    
    def _get_ab_test_results(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get detailed A/B test results."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get recent test results
            results = ABTestResult.objects.filter(
                test__tenant_id=tenant_id,
                analyzed_at__gte=cutoff_date
            ).order_by('-analyzed_at')[:20]
            
            test_results = []
            for result in results:
                test_results.append({
                    'test_id': result.test.id,
                    'test_name': result.test.name,
                    'winner': result.winner,
                    'confidence': result.winner_confidence,
                    'p_value': result.p_value,
                    'effect_size': result.effect_size,
                    'control_cr': result.control_cr,
                    'variant_cr': result.variant_cr,
                    'cr_improvement': result.cr_difference,
                    'analyzed_at': result.analyzed_at.isoformat()
                })
            
            return {
                'recent_results': test_results,
                'total_results_analyzed': len(test_results)
            }
            
        except Exception as e:
            logger.error(f"Error getting A/B test results: {e}")
            return {}
    
    def _get_winner_analysis(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get winner analysis."""
        try:
            # Get winner distribution
            winner_distribution = RoutingABTest.objects.filter(
                tenant_id=tenant_id,
                winner__isnull=False
            ).values('winner').annotate(
                count=Count('id')
            )
            
            # Get performance by winner type
            performance_by_winner = {}
            for winner_data in winner_distribution:
                winner_type = winner_data['winner']
                
                # Get average performance for this winner type
                test_results = ABTestResult.objects.filter(
                    test__tenant_id=tenant_id,
                    winner=winner_type
                ).aggregate(
                    avg_confidence=Avg('winner_confidence'),
                    avg_effect_size=Avg('effect_size'),
                    avg_cr_improvement=Avg('cr_difference')
                )
                
                performance_by_winner[winner_type] = {
                    'count': winner_data['count'],
                    'avg_confidence': performance_by_winner['avg_confidence'] or 0,
                    'avg_effect_size': performance_by_winner['avg_effect_size'] or 0,
                    'avg_cr_improvement': performance_by_winner['avg_cr_improvement'] or 0
                }
            
            return {
                'winner_distribution': list(winner_distribution),
                'performance_by_winner': performance_by_winner
            }
            
        except Exception as e:
            logger.error(f"Error getting winner analysis: {e}")
            return {}
    
    def _generate_ab_test_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate A/B testing recommendations."""
        recommendations = []
        
        try:
            summary = report.get('summary', {})
            
            # Test volume recommendations
            total_tests = summary.get('total_tests', 0)
            if total_tests < 5:
                recommendations.append("Consider running more A/B tests to optimize routing")
            
            # Statistical significance recommendations
            significant_results = summary.get('significant_results', 0)
            total_results = summary.get('total_results', 0)
            
            if total_results > 0:
                significance_rate = (significant_results / total_results) * 100
                if significance_rate < 50:
                    recommendations.append(f"Low statistical significance rate ({significance_rate:.1f}%) - increase sample sizes or test duration")
            
            # Winner analysis recommendations
            winner_analysis = report.get('winner_analysis', {})
            performance_by_winner = winner_analysis.get('performance_by_winner', {})
            
            if 'variant' in performance_by_winner:
                variant_performance = performance_by_winner['variant']
                if variant_performance['avg_cr_improvement'] > 5:
                    recommendations.append("Variants consistently outperform controls - consider implementing variant features as defaults")
            
            if not recommendations:
                recommendations.append("A/B testing performance looks good - continue testing and monitoring")
            
        except Exception as e:
            logger.error(f"Error generating A/B test recommendations: {e}")
        
        return recommendations
    
    def generate_business_report(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Generate business-focused report."""
        try:
            report = {
                'report_type': 'business',
                'tenant_id': tenant_id,
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
                'revenue_metrics': {},
                'conversion_metrics': {},
                'user_metrics': {},
                'roi_analysis': {},
                'recommendations': []
            }
            
            # Get revenue metrics
            report['revenue_metrics'] = self._get_revenue_metrics(tenant_id, days)
            
            # Get conversion metrics
            report['conversion_metrics'] = self._get_conversion_metrics(tenant_id, days)
            
            # Get user metrics
            report['user_metrics'] = self._get_user_business_metrics(tenant_id, days)
            
            # Get ROI analysis
            report['roi_analysis'] = self._get_roi_analysis(tenant_id, days)
            
            # Generate business recommendations
            report['recommendations'] = self._generate_business_recommendations(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating business report: {e}")
            return {
                'report_type': 'business',
                'tenant_id': tenant_id,
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
                'error': str(e)
            }
    
    def _get_revenue_metrics(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get revenue metrics."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            revenue_stats = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date()
            ).aggregate(
                total_revenue=Sum('revenue'),
                avg_revenue_per_impression=Avg('revenue_per_impression'),
                avg_revenue_per_user=Avg('revenue_per_user')
            )
            
            # Get revenue trends
            revenue_trends = self._get_revenue_trends(tenant_id, days)
            
            return {
                'total_revenue': float(revenue_stats['total_revenue'] or 0),
                'avg_revenue_per_impression': float(revenue_stats['avg_revenue_per_impression'] or 0),
                'avg_revenue_per_user': float(revenue_stats['avg_revenue_per_user'] or 0),
                'revenue_trends': revenue_trends
            }
            
        except Exception as e:
            logger.error(f"Error getting revenue metrics: {e}")
            return {}
    
    def _get_revenue_trends(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get revenue trends."""
        try:
            from datetime import timedelta
            
            # Get daily revenue
            cutoff_date = timezone.now() - timedelta(days=days)
            daily_revenue = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date()
            ).values('date').annotate(
                daily_revenue=Sum('revenue')
            ).order_by('date')
            
            revenue_trends = []
            for day_data in daily_revenue:
                revenue_trends.append({
                    'date': day_data['date'].isoformat(),
                    'revenue': float(day_data['daily_revenue'] or 0)
                })
            
            return {
                'daily_revenue': revenue_trends,
                'trend_direction': 'up'  # Would calculate actual trend
            }
            
        except Exception as e:
            logger.error(f"Error getting revenue trends: {e}")
            return {}
    
    def _get_conversion_metrics(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get conversion metrics."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            conversion_stats = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date.date()
            ).aggregate(
                total_conversions=Sum('conversions'),
                total_impressions=Sum('impressions'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_click_through_rate=Avg('click_through_rate')
            )
            
            total_impressions = conversion_stats['total_impressions'] or 0
            total_conversions = conversion_stats['total_conversions'] or 0
            
            return {
                'total_conversions': total_conversions,
                'total_impressions': total_impressions,
                'avg_conversion_rate': conversion_stats['avg_conversion_rate'] or 0,
                'avg_click_through_rate': conversion_stats['avg_click_through_rate'] or 0,
                'conversion_rate': (total_conversions / total_impressions * 100) if total_impressions > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting conversion metrics: {e}")
            return {}
    
    def _get_user_business_metrics(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get user business metrics."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            user_stats = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=cutoff_date
            ).aggregate(
                total_users=Count('user_id', distinct=True),
                avg_decisions_per_user=Avg('decisions_per_user'),
                avg_revenue_per_user=Avg('revenue_per_user')
            )
            
            return {
                'total_active_users': user_stats['total_users'] or 0,
                'avg_decisions_per_user': user_stats['avg_decisions_per_user'] or 0,
                'avg_revenue_per_user': float(user_stats['avg_revenue_per_user'] or 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting user business metrics: {e}")
            return {}
    
    def _get_roi_analysis(self, tenant_id: int, days: int) -> Dict[str, Any]:
        """Get ROI analysis."""
        try:
            # This would calculate ROI based on costs and revenue
            # For now, return placeholder
            
            return {
                'total_revenue': 0.0,
                'estimated_costs': 0.0,
                'roi_percentage': 0.0,
                'payback_period_days': 0
            }
            
        except Exception as e:
            logger.error(f"Error getting ROI analysis: {e}")
            return {}
    
    def _generate_business_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate business recommendations."""
        recommendations = []
        
        try:
            revenue_metrics = report.get('revenue_metrics', {})
            conversion_metrics = report.get('conversion_metrics', {})
            
            # Revenue recommendations
            total_revenue = revenue_metrics.get('total_revenue', 0)
            if total_revenue < 1000:
                recommendations.append("Low revenue generation - consider optimizing offer selection and targeting")
            
            # Conversion recommendations
            avg_conv_rate = conversion_metrics.get('conversion_rate', 0)
            if avg_conv_rate < 2:
                recommendations.append(f"Low conversion rate ({avg_conv_rate:.2f}%) - review offer relevance and user experience")
            elif avg_conv_rate > 10:
                recommendations.append(f"High conversion rate ({avg_conv_rate:.2f}%) - consider increasing traffic volume")
            
            if not recommendations:
                recommendations.append("Business metrics look healthy - continue monitoring and optimization")
            
        except Exception as e:
            logger.error(f"Error generating business recommendations: {e}")
        
        return recommendations


# Singleton instance
routing_reporter = RoutingReporter()
