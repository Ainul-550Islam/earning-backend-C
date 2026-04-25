"""
Analytics Tasks for Offer Routing System

This module contains background tasks for analytics,
including data aggregation, insight generation, and reporting.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from ..services.analytics import analytics_service
from ..services.reporter import routing_reporter
from ..constants import INSIGHT_AGGREGATION_HOURS, PERFORMANCE_STATS_RETENTION_DAYS

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='offer_routing.tasks.analytics.aggregate_hourly_stats')
def aggregate_hourly_stats(self):
    """
    Aggregate hourly performance statistics.
    
    This task aggregates routing performance data
    into hourly statistics for analysis.
    """
    try:
        logger.info("Starting hourly stats aggregation")
        
        if not analytics_service:
            logger.warning("Analytics service not available")
            return {'success': False, 'error': 'Analytics service not available'}
        
        # Aggregate hourly statistics
        aggregated_count = analytics_service.aggregate_hourly_stats()
        
        logger.info(f"Hourly stats aggregation completed: {aggregated_count} records aggregated")
        return {
            'success': True,
            'aggregated_records': aggregated_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Hourly stats aggregation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.generate_insights')
def generate_insights(self):
    """
    Generate routing insights based on recent data.
    
    This task analyzes recent routing data and generates
    actionable insights for optimization.
    """
    try:
        logger.info("Starting insights generation")
        
        if not analytics_service:
            logger.warning("Analytics service not available")
            return {'success': False, 'error': 'Analytics service not available'}
        
        # Generate insights for all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        total_insights = 0
        failed_tenants = []
        
        for tenant in tenants:
            try:
                from datetime import timedelta
                period_start = timezone.now() - timedelta(hours=INSIGHT_AGGREGATION_HOURS)
                period_end = timezone.now()
                
                insights_count = analytics_service.generate_insights(
                    tenant_id=tenant.id,
                    period_start=period_start,
                    period_end=period_end
                )
                total_insights += insights_count
                
            except Exception as e:
                logger.error(f"Failed to generate insights for tenant {tenant.id}: {e}")
                failed_tenants.append(tenant.id)
        
        logger.info(f"Insights generation completed: {total_insights} insights generated, {len(failed_tenants)} failed")
        return {
            'success': True,
            'generated_insights': total_insights,
            'failed_tenants': failed_tenants,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Insights generation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.update_performance_metrics')
def update_performance_metrics(self):
    """
    Update performance metrics for monitoring.
    
    This task updates performance metrics tables
    for real-time monitoring and alerting.
    """
    try:
        logger.info("Starting performance metrics update")
        
        # Get recent performance data
        from ..models import RoutingDecisionLog
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_decisions = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date
        )
        
        # Calculate performance metrics
        metrics = recent_decisions.aggregate(
            total_decisions=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            cache_hit_rate=Avg('cache_hit'),
            personalization_rate=Avg('personalization_applied'),
            caps_check_rate=Avg('caps_checked'),
            fallback_rate=Avg('fallback_used'),
            error_rate=Avg('response_time_ms', filter=Q(response_time_ms__gt=1000))
        )
        
        # Store metrics (placeholder)
        # This would save the metrics to database or cache
        
        logger.info(f"Performance metrics update completed: {metrics['total_decisions']} decisions analyzed")
        return {
            'success': True,
            'metrics': metrics,
            'decisions_analyzed': metrics['total_decisions'],
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance metrics update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.generate_daily_reports')
def generate_daily_reports(self):
    """
    Generate daily analytics reports.
    
    This task generates comprehensive daily reports
    for all tenants.
    """
    try:
        logger.info("Starting daily report generation")
        
        # Get all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        generated_reports = 0
        failed_tenants = []
        
        for tenant in tenants:
            try:
                # Generate performance report
                performance_report = routing_reporter.generate_performance_report(
                    tenant_id=tenant.id,
                    days=1
                )
                
                # Generate A/B test report
                ab_test_report = routing_reporter.generate_ab_test_report(
                    tenant_id=tenant.id,
                    days=1
                )
                
                # Generate business report
                business_report = routing_reporter.generate_business_report(
                    tenant_id=tenant.id,
                    days=1
                )
                
                # Store reports (placeholder)
                # This would save the reports to database or send via email
                
                generated_reports += 1
                
            except Exception as e:
                logger.error(f"Failed to generate daily report for tenant {tenant.id}: {e}")
                failed_tenants.append(tenant.id)
        
        logger.info(f"Daily report generation completed: {generated_reports} reports generated, {len(failed_tenants)} failed")
        return {
            'success': True,
            'generated_reports': generated_reports,
            'failed_tenants': failed_tenants,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.update_exposure_stats')
def update_exposure_stats(self):
    """
    Update offer exposure statistics.
    
    This task calculates and updates offer exposure
    statistics for analytics.
    """
    try:
        logger.info("Starting exposure statistics update")
        
        # Get recent routing decisions
        from ..models import RoutingDecisionLog, OfferExposureStat
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_decisions = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date
        )
        
        # Group by offer and calculate exposure stats
        exposure_stats = recent_decisions.values('offer_id').annotate(
            unique_users_exposed=Count('user_id', distinct=True),
            total_exposures=Count('id')
        )
        
        updated_stats = 0
        failed_updates = 0
        
        for stat in exposure_stats:
            try:
                # Update or create exposure stat
                exposure_stat, created = OfferExposureStat.objects.update_or_create(
                    offer_id=stat['offer_id'],
                    date=timezone.now().date(),
                    aggregation_type='hourly',
                    defaults={
                        'unique_users_exposed': stat['unique_users_exposed'],
                        'total_exposures': stat['total_exposures'],
                        'repeat_exposures': stat['total_exposures'] - stat['unique_users_exposed'],
                        'avg_exposures_per_user': stat['total_exposures'] / stat['unique_users_exposed'] if stat['unique_users_exposed'] > 0 else 0
                    }
                )
                
                if not created:
                    # Update existing record
                    exposure_stat.unique_users_exposed = stat['unique_users_exposed']
                    exposure_stat.total_exposures = stat['total_exposures']
                    exposure_stat.repeat_exposures = stat['total_exposures'] - stat['unique_users_exposed']
                    exposure_stat.avg_exposures_per_user = stat['total_exposures'] / stat['unique_users_exposed'] if stat['unique_users_exposed'] > 0 else 0
                    exposure_stat.save()
                
                updated_stats += 1
                
            except Exception as e:
                logger.error(f"Failed to update exposure stat for offer {stat['offer_id']}: {e}")
                failed_updates += 1
        
        logger.info(f"Exposure statistics update completed: {updated_stats} updated, {failed_updates} failed")
        return {
            'success': True,
            'updated_stats': updated_stats,
            'failed_updates': failed_updates,
            'total_offers': exposure_stats.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Exposure statistics update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.calculate_user_analytics')
def calculate_user_analytics(self):
    """
    Calculate user-specific analytics.
    
    This task calculates analytics for individual users
    to support personalization and targeting.
    """
    try:
        logger.info("Starting user analytics calculation")
        
        # Get recent user activity
        from ..models import RoutingDecisionLog
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_decisions = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date
        ).values('user_id').annotate(
            decision_count=Count('id'),
            avg_score=Avg('score'),
            unique_offers=Count('offer_id', distinct=True),
            cache_hit_rate=Avg('cache_hit'),
            personalization_rate=Avg('personalization_applied')
        )
        
        updated_users = 0
        failed_updates = 0
        
        for user_stat in recent_decisions:
            try:
                # Update user analytics (placeholder)
                # This would save the user analytics to database or cache
                
                updated_users += 1
                
            except Exception as e:
                logger.error(f"Failed to calculate analytics for user {user_stat['user_id']}: {e}")
                failed_updates += 1
        
        logger.info(f"User analytics calculation completed: {updated_users} updated, {failed_updates} failed")
        return {
            'success': True,
            'updated_users': updated_users,
            'failed_updates': failed_updates,
            'active_users': recent_decisions.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"User analytics calculation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.cleanup_old_analytics')
def cleanup_old_analytics(self):
    """
    Clean up old analytics data.
    
    This task removes old analytics data to maintain
    system performance and storage efficiency.
    """
    try:
        logger.info("Starting analytics cleanup")
        
        # Clean up old decision logs
        from ..models import RoutingDecisionLog
        from datetime import timedelta
        
        decision_cutoff = timezone.now() - timedelta(days=DECISION_LOG_RETENTION_DAYS)
        deleted_decisions = RoutingDecisionLog.objects.filter(
            created_at__lt=decision_cutoff
        ).delete()[0]
        
        # Clean up old performance stats
        from ..models import RoutePerformanceStat
        stats_cutoff = timezone.now() - timedelta(days=PERFORMANCE_STATS_RETENTION_DAYS)
        deleted_stats = RoutePerformanceStat.objects.filter(
            date__lt=stats_cutoff.date()
        ).delete()[0]
        
        # Clean up old insights
        from ..models import RoutingInsight
        insight_cutoff = timezone.now() - timedelta(days=90)
        deleted_insights = RoutingInsight.objects.filter(
            created_at__lt=insight_cutoff,
            is_actionable=False  # Only delete non-actionable old insights
        ).delete()[0]
        
        total_deleted = deleted_decisions + deleted_stats + deleted_insights
        
        logger.info(f"Analytics cleanup completed: {total_deleted} records deleted")
        return {
            'success': True,
            'deleted_decision_logs': deleted_decisions,
            'deleted_performance_stats': deleted_stats,
            'deleted_insights': deleted_insights,
            'total_deleted': total_deleted,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Analytics cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.update_trending_metrics')
def update_trending_metrics(self):
    """
    Update trending metrics and indicators.
    
    This task calculates trending metrics and
    identifies performance trends.
    """
    try:
        logger.info("Starting trending metrics update")
        
        # Get recent performance data
        from datetime import timedelta
        
        current_period_start = timezone.now() - timedelta(days=7)
        previous_period_start = current_period_start - timedelta(days=7)
        
        # Calculate current period stats
        from ..models import RoutingDecisionLog
        current_stats = RoutingDecisionLog.objects.filter(
            created_at__gte=current_period_start
        ).aggregate(
            total_decisions=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            cache_hit_rate=Avg('cache_hit'),
            total_conversions=Sum('score', filter=Q(score__gt=80))  # High score as conversion proxy
        )
        
        # Calculate previous period stats
        previous_stats = RoutingDecisionLog.objects.filter(
            created_at__gte=previous_period_start,
            created_at__lt=current_period_start
        ).aggregate(
            total_decisions=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            cache_hit_rate=Avg('cache_hit'),
            total_conversions=Sum('score', filter=Q(score__gt=80))
        )
        
        # Calculate trends
        trends = {}
        
        for metric in ['total_decisions', 'avg_response_time', 'cache_hit_rate', 'total_conversions']:
            current_value = current_stats[metric] or 0
            previous_value = previous_stats[metric] or 0
            
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
        
        # Store trends (placeholder)
        # This would save the trends to database or cache
        
        logger.info(f"Trending metrics update completed: {len(trends)} metrics updated")
        return {
            'success': True,
            'trends': trends,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Trending metrics update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.analytics.calculate_funnel_metrics')
def calculate_funnel_metrics(self):
    """
    Calculate funnel metrics for user journey analysis.
    
    This task calculates funnel metrics to analyze
    user journey and conversion patterns.
    """
    try:
        logger.info("Starting funnel metrics calculation")
        
        # Get recent user interactions
        from ..models import UserOfferHistory
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=7)
        user_interactions = UserOfferHistory.objects.filter(
            created_at__gte=cutoff_date
        )
        
        # Calculate funnel stages
        funnel_stages = {
            'impressions': user_interactions.count(),
            'views': user_interactions.filter(viewed_at__isnull=False).count(),
            'clicks': user_interactions.filter(clicked_at__isnull=False).count(),
            'conversions': user_interactions.filter(completed_at__isnull=False).count()
        }
        
        # Calculate conversion rates
        conversion_rates = {}
        
        if funnel_stages['impressions'] > 0:
            conversion_rates['view_rate'] = (funnel_stages['views'] / funnel_stages['impressions']) * 100
        else:
            conversion_rates['view_rate'] = 0
        
        if funnel_stages['views'] > 0:
            conversion_rates['click_rate'] = (funnel_stages['clicks'] / funnel_stages['views']) * 100
        else:
            conversion_rates['click_rate'] = 0
        
        if funnel_stages['clicks'] > 0:
            conversion_rates['conversion_rate'] = (funnel_stages['conversions'] / funnel_stages['clicks']) * 100
        else:
            conversion_rates['conversion_rate'] = 0
        
        if funnel_stages['impressions'] > 0:
            conversion_rates['overall_rate'] = (funnel_stages['conversions'] / funnel_stages['impressions']) * 100
        else:
            conversion_rates['overall_rate'] = 0
        
        # Store funnel metrics (placeholder)
        # This would save the funnel metrics to database or cache
        
        logger.info(f"Funnel metrics calculation completed: {funnel_stages}")
        return {
            'success': True,
            'funnel_stages': funnel_stages,
            'conversion_rates': conversion_rates,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Funnel metrics calculation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
