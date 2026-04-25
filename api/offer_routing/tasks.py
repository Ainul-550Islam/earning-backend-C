"""
Background Tasks for Offer Routing System

This module provides Celery tasks for offer routing operations.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from .services.core import OfferRoutingEngine, RoutingCacheService
from .services.analytics import RoutingAnalyticsService
from .services.cap import CapEnforcementService
from .services.ab_test import ABTestService
from .models import RoutingDecisionLog, RoutePerformanceStat
from .constants import (
    DECISION_LOG_RETENTION_DAYS, INSIGHT_AGGREGATION_HOURS,
    PERFORMANCE_STATS_RETENTION_DAYS, MAX_DECISION_LOGS_PER_BATCH
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def score_update_task():
    """
    Update offer scores for all active offers.
    Runs every 30 minutes.
    """
    try:
        from .services.scoring import OfferScorerService
        
        scorer = OfferScorerService()
        updated_count = scorer.update_all_scores()
        
        logger.info(f"Score update completed: {updated_count} offers updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Score update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def rank_update_task():
    """
    Update global offer rankings.
    Runs hourly.
    """
    try:
        from .services.scoring import OfferRankerService
        
        ranker = OfferRankerService()
        updated_count = ranker.update_global_rankings()
        
        logger.info(f"Rank update completed: {updated_count} offers ranked")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Rank update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cap_reset_task():
    """
    Reset daily offer caps.
    Runs at midnight.
    """
    try:
        cap_service = CapEnforcementService()
        reset_count = cap_service.reset_daily_caps()
        
        logger.info(f"Cap reset completed: {reset_count} caps reset")
        return {'success': True, 'reset_count': reset_count}
        
    except Exception as e:
        logger.error(f"Cap reset task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cache_warmup_task():
    """
    Warm up routing cache for active users.
    Runs every 5 minutes.
    """
    try:
        cache_service = RoutingCacheService()
        warmed_count = cache_service.warmup_active_users()
        
        logger.info(f"Cache warmup completed: {warmed_count} users warmed")
        return {'success': True, 'warmed_count': warmed_count}
        
    except Exception as e:
        logger.error(f"Cache warmup task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def ab_test_task():
    """
    Evaluate A/B test significance and declare winners.
    Runs every hour.
    """
    try:
        ab_service = ABTestService()
        evaluated_count = ab_service.evaluate_active_tests()
        
        logger.info(f"A/B test evaluation completed: {evaluated_count} tests evaluated")
        return {'success': True, 'evaluated_count': evaluated_count}
        
    except Exception as e:
        logger.error(f"A/B test task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def affinity_update_task():
    """
    Update user-category affinity scores.
    Runs daily.
    """
    try:
        from .services.personalization import CollaborativeFilterService
        
        collab_service = CollaborativeFilterService()
        updated_count = collab_service.update_affinity_scores()
        
        logger.info(f"Affinity update completed: {updated_count} users updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Affinity update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def preference_vector_task():
    """
    Rebuild user preference vectors.
    Runs weekly.
    """
    try:
        from .services.personalization import ContentBasedService
        
        content_service = ContentBasedService()
        rebuilt_count = content_service.rebuild_preference_vectors()
        
        logger.info(f"Preference vector rebuild completed: {rebuilt_count} vectors rebuilt")
        return {'success': True, 'rebuilt_count': rebuilt_count}
        
    except Exception as e:
        logger.error(f"Preference vector task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analytics_task():
    """
    Aggregate routing analytics data.
    Runs hourly.
    """
    try:
        analytics_service = RoutingAnalyticsService()
        aggregated_count = analytics_service.aggregate_hourly_stats()
        
        logger.info(f"Analytics aggregation completed: {aggregated_count} records aggregated")
        return {'success': True, 'aggregated_count': aggregated_count}
        
    except Exception as e:
        logger.error(f"Analytics task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fallback_health_task():
    """
    Check fallback pools are not empty.
    Runs every 30 minutes.
    """
    try:
        from .services.fallback import FallbackService
        
        fallback_service = FallbackService()
        checked_count = fallback_service.check_fallback_health()
        
        logger.info(f"Fallback health check completed: {checked_count} pools checked")
        return {'success': True, 'checked_count': checked_count}
        
    except Exception as e:
        logger.error(f"Fallback health task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def exposure_stat_task():
    """
    Calculate daily exposure statistics.
    Runs daily.
    """
    try:
        from .services.analytics import PerformanceReportService
        
        report_service = PerformanceReportService()
        calculated_count = report_service.calculate_daily_exposure_stats()
        
        logger.info(f"Exposure stats calculation completed: {calculated_count} stats calculated")
        return {'success': True, 'calculated_count': calculated_count}
        
    except Exception as e:
        logger.error(f"Exposure stats task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def decision_log_cleanup_task():
    """
    Archive old routing decision logs.
    Runs daily.
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=DECISION_LOG_RETENTION_DAYS)
        
        with transaction.atomic():
            deleted_count = RoutingDecisionLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
        
        logger.info(f"Decision log cleanup completed: {deleted_count} old logs deleted")
        return {'success': True, 'deleted_count': deleted_count}
        
    except Exception as e:
        logger.error(f"Decision log cleanup task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def performance_report_task():
    """
    Generate weekly performance reports.
    Runs weekly.
    """
    try:
        from .services.analytics import PerformanceReportService
        
        report_service = PerformanceReportService()
        generated_count = report_service.generate_weekly_reports()
        
        logger.info(f"Performance report generation completed: {generated_count} reports generated")
        return {'success': True, 'generated_count': generated_count}
        
    except Exception as e:
        logger.error(f"Performance report task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def routing_optimization_task():
    """
    Optimize routing configurations based on performance data.
    Runs daily.
    """
    try:
        from .services.core import OfferRoutingEngine
        
        routing_engine = OfferRoutingEngine()
        optimized_count = routing_engine.optimize_routing_configurations()
        
        logger.info(f"Routing optimization completed: {optimized_count} configurations optimized")
        return {'success': True, 'optimized_count': optimized_count}
        
    except Exception as e:
        logger.error(f"Routing optimization task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def user_segment_update_task():
    """
    Update user segment assignments.
    Runs every 6 hours.
    """
    try:
        from .services.targeting import SegmentTargetingService
        
        segment_service = SegmentTargetingService()
        updated_count = segment_service.update_user_segments()
        
        logger.info(f"User segment update completed: {updated_count} users updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"User segment update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def geo_targeting_update_task():
    """
    Update geographic targeting rules.
    Runs every 12 hours.
    """
    try:
        from .services.targeting import GeoTargetingService
        
        geo_service = GeoTargetingService()
        updated_count = geo_service.update_geo_rules()
        
        logger.info(f"Geo targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Geo targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def device_targeting_update_task():
    """
    Update device targeting rules.
    Runs every 12 hours.
    """
    try:
        from .services.targeting import DeviceTargetingService
        
        device_service = DeviceTargetingService()
        updated_count = device_service.update_device_rules()
        
        logger.info(f"Device targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Device targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def behavioral_targeting_update_task():
    """
    Update behavioral targeting rules.
    Runs every 6 hours.
    """
    try:
        from .services.targeting import BehaviorTargetingService
        
        behavior_service = BehaviorTargetingService()
        updated_count = behavior_service.update_behavioral_rules()
        
        logger.info(f"Behavioral targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Behavioral targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def time_targeting_update_task():
    """
    Update time-based targeting rules.
    Runs every 12 hours.
    """
    try:
        from .services.targeting import TimeTargetingService
        
        time_service = TimeTargetingService()
        updated_count = time_service.update_time_rules()
        
        logger.info(f"Time targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Time targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def personalization_config_update_task():
    """
    Update personalization configurations.
    Runs every 24 hours.
    """
    try:
        from .services.personalization import PersonalizationConfigService
        
        config_service = PersonalizationConfigService()
        updated_count = config_service.update_configurations()
        
        logger.info(f"Personalization config update completed: {updated_count} configs updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Personalization config update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cache_maintenance_task():
    """
    Perform cache maintenance operations.
    Runs every 2 hours.
    """
    try:
        cache_service = RoutingCacheService()
        maintenance_count = cache_service.perform_maintenance()
        
        logger.info(f"Cache maintenance completed: {maintenance_count} operations performed")
        return {'success': True, 'maintenance_count': maintenance_count}
        
    except Exception as e:
        logger.error(f"Cache maintenance task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def route_validation_task():
    """
    Validate route configurations.
    Runs every 6 hours.
    """
    try:
        from .services.core import RouteEvaluator
        
        evaluator = RouteEvaluator()
        validated_count = evaluator.validate_all_routes()
        
        logger.info(f"Route validation completed: {validated_count} routes validated")
        return {'success': True, 'validated_count': validated_count}
        
    except Exception as e:
        logger.error(f"Route validation task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def offer_sync_task():
    """
    Synchronize offer data from external sources.
    Runs every hour.
    """
    try:
        from .services.core import OfferRoutingEngine
        
        routing_engine = OfferRoutingEngine()
        synced_count = routing_engine.sync_external_offers()
        
        logger.info(f"Offer sync completed: {synced_count} offers synced")
        return {'success': True, 'synced_count': synced_count}
        
    except Exception as e:
        logger.error(f"Offer sync task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def performance_monitoring_task():
    """
    Monitor routing performance and alert on issues.
    Runs every 5 minutes.
    """
    try:
        from .services.analytics import PerformanceReportService
        
        report_service = PerformanceReportService()
        monitored_count = report_service.monitor_performance()
        
        logger.info(f"Performance monitoring completed: {monitored_count} metrics monitored")
        return {'success': True, 'monitored_count': monitored_count}
        
    except Exception as e:
        logger.error(f"Performance monitoring task failed: {e}")
        raise


# Task scheduling configuration
def schedule_tasks():
    """Schedule periodic tasks for offer routing system."""
    from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
    from .celery import app
    
    # Schedule periodic tasks
    tasks_config = [
        {
            'task': score_update_task.name,
            'schedule': CrontabSchedule(minute='*/30'),  # Every 30 minutes
            'name': 'score_update_task'
        },
        {
            'task': rank_update_task.name,
            'schedule': IntervalSchedule(minutes=60),  # Every hour
            'name': 'rank_update_task'
        },
        {
            'task': cap_reset_task.name,
            'schedule': CrontabSchedule(minute='0', hour='0'),  # Daily at midnight
            'name': 'cap_reset_task'
        },
        {
            'task': cache_warmup_task.name,
            'schedule': IntervalSchedule(minutes=5),  # Every 5 minutes
            'name': 'cache_warmup_task'
        },
        {
            'task': ab_test_task.name,
            'schedule': IntervalSchedule(minutes=60),  # Every hour
            'name': 'ab_test_task'
        },
        {
            'task': affinity_update_task.name,
            'schedule': CrontabSchedule(minute='0', hour='2'),  # Daily at 2 AM
            'name': 'affinity_update_task'
        },
        {
            'task': preference_vector_task.name,
            'schedule': CrontabSchedule(minute='0', hour='3', day_of_week='1'),  # Weekly on Monday at 3 AM
            'name': 'preference_vector_task'
        },
        {
            'task': analytics_task.name,
            'schedule': IntervalSchedule(minutes=60),  # Every hour
            'name': 'analytics_task'
        },
        {
            'task': fallback_health_task.name,
            'schedule': IntervalSchedule(minutes=30),  # Every 30 minutes
            'name': 'fallback_health_task'
        },
        {
            'task': exposure_stat_task.name,
            'schedule': CrontabSchedule(minute='0', hour='1'),  # Daily at 1 AM
            'name': 'exposure_stat_task'
        },
        {
            'task': decision_log_cleanup_task.name,
            'schedule': CrontabSchedule(minute='0', hour='2'),  # Daily at 2 AM
            'name': 'decision_log_cleanup_task'
        },
        {
            'task': performance_report_task.name,
            'schedule': CrontabSchedule(minute='0', hour='8', day_of_week='1'),  # Weekly on Monday at 8 AM
            'name': 'performance_report_task'
        },
    ]
    
    for task_config in tasks_config:
        PeriodicTask.objects.update_or_create(
            name=task_config['name'],
            task=task_config['task'],
            schedule=task_config['schedule'],
            enabled=True
        )
    
    logger.info(f"Scheduled {len(tasks_config)} periodic tasks for offer routing")
