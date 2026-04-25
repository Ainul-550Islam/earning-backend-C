"""
Core Tasks for Offer Routing System

This module contains core background tasks for the offer routing system,
including periodic maintenance, cleanup, and system health checks.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from ..services.core import routing_engine
from ..services.cache import cache_service
from ..services.monitoring import monitoring_service
from ..services.analytics import analytics_service
from ..constants import (
    DECISION_LOG_RETENTION_DAYS, PERFORMANCE_STATS_RETENTION_DAYS,
    INSIGHT_AGGREGATION_HOURS, CACHE_CLEANUP_INTERVAL_HOURS
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='offer_routing.tasks.core.maintenance_tasks')
def maintenance_tasks(self):
    """
    Execute routine maintenance tasks for the offer routing system.
    
    This task runs periodically to perform system maintenance including:
    - Cache cleanup
    - Database cleanup
    - Performance optimization
    - Health checks
    """
    try:
        logger.info("Starting routine maintenance tasks")
        
        # Execute individual maintenance tasks
        results = {}
        
        # Cache cleanup
        try:
            cache_result = cleanup_cache()
            results['cache_cleanup'] = cache_result
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            results['cache_cleanup'] = {'success': False, 'error': str(e)}
        
        # Database cleanup
        try:
            db_result = cleanup_database()
            results['database_cleanup'] = db_result
        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")
            results['database_cleanup'] = {'success': False, 'error': str(e)}
        
        # Performance optimization
        try:
            perf_result = optimize_performance()
            results['performance_optimization'] = perf_result
        except Exception as e:
            logger.error(f"Performance optimization failed: {e}")
            results['performance_optimization'] = {'success': False, 'error': str(e)}
        
        # Health check
        try:
            health_result = system_health_check()
            results['health_check'] = health_result
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            results['health_check'] = {'success': False, 'error': str(e)}
        
        logger.info(f"Routine maintenance completed: {results}")
        return {
            'success': True,
            'completed_at': timezone.now().isoformat(),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Maintenance tasks failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.core.cleanup_cache')
def cleanup_cache(self):
    """
    Clean up expired cache entries and optimize cache performance.
    
    This task removes expired entries and performs cache maintenance
    to ensure optimal performance.
    """
    try:
        logger.info("Starting cache cleanup")
        
        if not cache_service:
            logger.warning("Cache service not available")
            return {'success': False, 'error': 'Cache service not available'}
        
        # Clean up expired entries
        expired_count = 0
        
        # Clean up routing result cache
        try:
            expired_count += cache_service.cleanup_expired_routing_results()
        except Exception as e:
            logger.error(f"Failed to cleanup routing results cache: {e}")
        
        # Clean up score cache
        try:
            expired_count += cache_service.cleanup_expired_scores()
        except Exception as e:
            logger.error(f"Failed to cleanup scores cache: {e}")
        
        # Clean up user cap cache
        try:
            expired_count += cache_service.cleanup_expired_user_caps()
        except Exception as e:
            logger.error(f"Failed to cleanup user caps cache: {e}")
        
        # Clean up affinity score cache
        try:
            expired_count += cache_service.cleanup_expired_affinity_scores()
        except Exception as e:
            logger.error(f"Failed to cleanup affinity scores cache: {e}")
        
        # Clean up preference vector cache
        try:
            expired_count += cache_service.cleanup_expired_preference_vectors()
        except Exception as e:
            logger.error(f"Failed to cleanup preference vectors cache: {e}")
        
        # Clean up contextual signal cache
        try:
            expired_count += cache_service.cleanup_expired_contextual_signals()
        except Exception as e:
            logger.error(f"Failed to cleanup contextual signals cache: {e}")
        
        # Optimize cache
        try:
            cache_service.optimize_cache()
        except Exception as e:
            logger.error(f"Failed to optimize cache: {e}")
        
        logger.info(f"Cache cleanup completed: {expired_count} expired entries removed")
        return {
            'success': True,
            'expired_entries_removed': expired_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.core.cleanup_database')
def cleanup_database(self):
    """
    Clean up old database records and optimize database performance.
    
    This task removes old records based on retention policies
    and performs database maintenance.
    """
    try:
        logger.info("Starting database cleanup")
        
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
        
        # Optimize database tables
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                # Analyze tables for query optimization
                tables = [
                    'offer_routing_routingdecisionlog',
                    'offer_routing_routeperformancestat',
                    'offer_routing_routinginsight'
                ]
                
                for table in tables:
                    try:
                        cursor.execute(f"ANALYZE {table}")
                    except Exception as e:
                        logger.warning(f"Failed to analyze table {table}: {e}")
        except Exception as e:
            logger.warning(f"Database optimization failed: {e}")
        
        total_deleted = deleted_decisions + deleted_stats + deleted_insights
        
        logger.info(f"Database cleanup completed: {total_deleted} records deleted")
        return {
            'success': True,
            'deleted_decision_logs': deleted_decisions,
            'deleted_performance_stats': deleted_stats,
            'deleted_insights': deleted_insights,
            'total_deleted': total_deleted,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.core.optimize_performance')
def optimize_performance(self):
    """
    Optimize system performance by analyzing metrics and making adjustments.
    
    This task analyzes performance data and makes automatic optimizations
    to improve routing performance.
    """
    try:
        logger.info("Starting performance optimization")
        
        if not analytics_service:
            logger.warning("Analytics service not available")
            return {'success': False, 'error': 'Analytics service not available'}
        
        # Get performance metrics
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(hours=24)
        
        # Analyze response times
        avg_response_time = analytics_service.get_average_response_time(cutoff_date)
        
        optimizations = []
        
        # Optimize cache settings if response time is high
        if avg_response_time > 100:  # 100ms threshold
            logger.info(f"High response time detected: {avg_response_time}ms, optimizing cache")
            
            # Increase cache timeout
            try:
                cache_service.increase_cache_timeout()
                optimizations.append({
                    'type': 'cache_timeout_increased',
                    'reason': f'High response time: {avg_response_time}ms'
                })
            except Exception as e:
                logger.error(f"Failed to increase cache timeout: {e}")
        
        # Analyze cache hit rate
        cache_hit_rate = analytics_service.get_cache_hit_rate(cutoff_date)
        
        if cache_hit_rate < 70:  # 70% threshold
            logger.info(f"Low cache hit rate: {cache_hit_rate}%, warming up cache")
            
            # Warm up cache
            try:
                cache_service.warm_up_cache()
                optimizations.append({
                    'type': 'cache_warmup',
                    'reason': f'Low cache hit rate: {cache_hit_rate}%'
                })
            except Exception as e:
                logger.error(f"Failed to warm up cache: {e}")
        
        # Analyze error rates
        error_rate = analytics_service.get_error_rate(cutoff_date)
        
        if error_rate > 5:  # 5% threshold
            logger.warning(f"High error rate: {error_rate}%, investigating issues")
            
            # Log high error rate for investigation
            optimizations.append({
                'type': 'high_error_rate_detected',
                'reason': f'High error rate: {error_rate}%'
            })
        
        # Optimize routing engine configuration
        try:
            routing_engine.optimize_configuration()
            optimizations.append({
                'type': 'routing_engine_optimized',
                'reason': 'Routine optimization'
            })
        except Exception as e:
            logger.error(f"Failed to optimize routing engine: {e}")
        
        logger.info(f"Performance optimization completed: {len(optimizations)} optimizations applied")
        return {
            'success': True,
            'optimizations': optimizations,
            'avg_response_time': avg_response_time,
            'cache_hit_rate': cache_hit_rate,
            'error_rate': error_rate,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance optimization failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.core.system_health_check')
def system_health_check(self):
    """
    Perform comprehensive system health check.
    
    This task checks the health of all system components
    and generates alerts for any issues.
    """
    try:
        logger.info("Starting system health check")
        
        if not monitoring_service:
            logger.warning("Monitoring service not available")
            return {'success': False, 'error': 'Monitoring service not available'}
        
        # Check system health
        health_status = monitoring_service.check_system_health()
        
        # Check service dependencies
        dependencies = monitoring_service.check_service_dependencies()
        
        # Generate alerts for issues
        alerts = []
        
        if health_status['overall_status'] != 'healthy':
            alerts.append({
                'type': 'system_health',
                'severity': 'critical',
                'message': f"System health status: {health_status['overall_status']}",
                'details': health_status['alerts']
            })
        
        if dependencies['overall_status'] != 'healthy':
            alerts.append({
                'type': 'dependency_health',
                'severity': 'warning',
                'message': f"Dependency health status: {dependencies['overall_status']}",
                'details': dependencies
            })
        
        # Check performance metrics
        try:
            performance_metrics = monitoring_service.get_performance_summary(60)  # Last hour
            
            # Check for performance issues
            if 'avg_response_time' in performance_metrics and performance_metrics['avg_response_time'] > 200:
                alerts.append({
                    'type': 'performance',
                    'severity': 'warning',
                    'message': f"High average response time: {performance_metrics['avg_response_time']}ms"
                })
            
            if 'cache_hit_rate' in performance_metrics and performance_metrics['cache_hit_rate'] < 60:
                alerts.append({
                    'type': 'cache_performance',
                    'severity': 'warning',
                    'message': f"Low cache hit rate: {performance_metrics['cache_hit_rate']}%"
                })
                
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
        
        # Log health check results
        if alerts:
            logger.warning(f"System health check found {len(alerts)} issues")
            for alert in alerts:
                logger.warning(f"Alert: {alert['message']}")
        else:
            logger.info("System health check passed - all systems healthy")
        
        return {
            'success': True,
            'health_status': health_status,
            'dependencies': dependencies,
            'alerts': alerts,
            'alert_count': len(alerts),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.core.warmup_cache')
def warmup_cache(self):
    """
    Warm up cache with frequently accessed data.
    
    This task preloads cache with commonly used data
    to improve system performance.
    """
    try:
        logger.info("Starting cache warmup")
        
        if not cache_service:
            logger.warning("Cache service not available")
            return {'success': False, 'error': 'Cache service not available'}
        
        warmup_stats = cache_service.warm_up_cache()
        
        logger.info(f"Cache warmup completed: {warmup_stats}")
        return {
            'success': True,
            'warmup_stats': warmup_stats,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache warmup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.core.update_global_rankings')
def update_global_rankings(self):
    """
    Update global offer rankings based on recent performance data.
    
    This task recalculates global rankings for all offers
    to ensure accurate ranking information.
    """
    try:
        logger.info("Starting global rankings update")
        
        from ..services.scoring import ranker_service
        
        updated_count = ranker_service.update_global_rankings()
        
        logger.info(f"Global rankings update completed: {updated_count} offers updated")
        return {
            'success': True,
            'updated_offers': updated_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Global rankings update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.core.generate_insights')
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
        
        from datetime import timedelta
        period_start = timezone.now() - timedelta(hours=INSIGHT_AGGREGATION_HOURS)
        period_end = timezone.now()
        
        # Generate insights for all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        total_insights = 0
        for tenant in tenants:
            try:
                insights_count = analytics_service.generate_insights(
                    tenant_id=tenant.id,
                    period_start=period_start,
                    period_end=period_end
                )
                total_insights += insights_count
            except Exception as e:
                logger.error(f"Failed to generate insights for tenant {tenant.id}: {e}")
        
        logger.info(f"Insights generation completed: {total_insights} insights generated")
        return {
            'success': True,
            'generated_insights': total_insights,
            'period_hours': INSIGHT_AGGREGATION_HOURS,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Insights generation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
