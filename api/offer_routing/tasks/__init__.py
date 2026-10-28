"""
Tasks Module for Offer Routing System

Imports all background tasks from submodules.
Duplicate names resolved: update_global_rankings from scoring takes priority;
generate_insights from analytics takes priority.
"""

from .core import (
    maintenance_tasks,
    cleanup_cache,
    cleanup_database,
    optimize_performance,
    system_health_check,
    warmup_cache,
    update_global_rankings as core_update_global_rankings,
    generate_insights as core_generate_insights,
)
from .scoring import (
    update_all_offer_scores,
    update_global_rankings,
    optimize_score_weights,
    calculate_user_affinity_scores,
    update_user_offer_history,
    refresh_score_cache,
    analyze_score_performance,
    update_epc_data,
    calculate_conversion_rates,
)
from .personalization import (
    update_user_preferences,
    update_affinity_scores,
    update_collaborative_filtering,
    update_content_based_filtering,
    optimize_personalization_configs,
    process_contextual_signals,
    cleanup_expired_signals,
    calculate_personalization_metrics,
    train_ml_models,
    update_real_time_personalization,
)
from .cap import (
    reset_daily_caps,
    enforce_global_caps,
    update_cap_analytics,
    check_cap_health,
    optimize_cap_configuration,
    cleanup_old_cap_data,
    generate_cap_reports,
    update_cap_usage_statistics,
)
from .ab_test import (
    evaluate_active_tests,
    check_test_duration,
    update_test_assignments,
    generate_test_reports,
    cleanup_completed_tests,
    optimize_test_configuration,
    update_test_metrics,
    check_test_health,
)
from .analytics import (
    aggregate_hourly_stats,
    generate_insights,
    update_performance_metrics,
    generate_daily_reports,
    update_exposure_stats,
    calculate_user_analytics,
    cleanup_old_analytics,
    update_trending_metrics,
    calculate_funnel_metrics,
)
from .fallback import (
    check_fallback_health,
    update_offer_pools,
    update_fallback_rules,
    update_empty_handlers,
    generate_fallback_analytics,
    optimize_fallback_configuration,
    cleanup_inactive_fallbacks,
    update_fallback_metrics,
)
from .monitoring import (
    perform_health_check,
    check_service_dependencies,
    collect_performance_metrics,
    check_resource_usage,
    generate_monitoring_report,
    update_monitoring_dashboard,
    check_alert_thresholds,
    cleanup_old_monitoring_data,
    update_monitoring_metrics,
)

__all__ = [
    # Core Tasks
    'maintenance_tasks', 'cleanup_cache', 'cleanup_database',
    'optimize_performance', 'system_health_check', 'warmup_cache',
    'core_update_global_rankings', 'core_generate_insights',
    # Scoring Tasks
    'update_all_offer_scores', 'update_global_rankings', 'optimize_score_weights',
    'calculate_user_affinity_scores', 'update_user_offer_history',
    'refresh_score_cache', 'analyze_score_performance',
    'update_epc_data', 'calculate_conversion_rates',
    # Personalization Tasks
    'update_user_preferences', 'update_affinity_scores',
    'update_collaborative_filtering', 'update_content_based_filtering',
    'optimize_personalization_configs', 'process_contextual_signals',
    'cleanup_expired_signals', 'calculate_personalization_metrics',
    'train_ml_models', 'update_real_time_personalization',
    # Cap Tasks
    'reset_daily_caps', 'enforce_global_caps', 'update_cap_analytics',
    'check_cap_health', 'optimize_cap_configuration', 'cleanup_old_cap_data',
    'generate_cap_reports', 'update_cap_usage_statistics',
    # A/B Test Tasks
    'evaluate_active_tests', 'check_test_duration', 'update_test_assignments',
    'generate_test_reports', 'cleanup_completed_tests',
    'optimize_test_configuration', 'update_test_metrics', 'check_test_health',
    # Analytics Tasks
    'aggregate_hourly_stats', 'generate_insights', 'update_performance_metrics',
    'generate_daily_reports', 'update_exposure_stats', 'calculate_user_analytics',
    'cleanup_old_analytics', 'update_trending_metrics', 'calculate_funnel_metrics',
    # Fallback Tasks
    'check_fallback_health', 'update_offer_pools', 'update_fallback_rules',
    'update_empty_handlers', 'generate_fallback_analytics',
    'optimize_fallback_configuration', 'cleanup_inactive_fallbacks',
    'update_fallback_metrics',
    # Monitoring Tasks
    'perform_health_check', 'check_service_dependencies',
    'collect_performance_metrics', 'check_resource_usage',
    'generate_monitoring_report', 'update_monitoring_dashboard',
    'check_alert_thresholds', 'cleanup_old_monitoring_data',
    'update_monitoring_metrics',
]

# ── Domain-specific periodic tasks ───────────────────────────────────────────
from celery import shared_task


@shared_task(name='offer_routing.tasks.update_offer_scores_task')
def update_offer_scores_task(*args, **kwargs):
    """Stub task: update_offer_scores_task"""
    return True

@shared_task(name='offer_routing.tasks.cleanup_routing_logs_task')
def cleanup_routing_logs_task(*args, **kwargs):
    """Stub task: cleanup_routing_logs_task"""
    return True

@shared_task(name='offer_routing.tasks.send_notification_task')
def send_notification_task(*args, **kwargs):
    """Stub task: send_notification_task"""
    return True

@shared_task(name='offer_routing.tasks.update_routing_cache_task')
def update_routing_cache_task(*args, **kwargs):
    """Stub task: update_routing_cache_task"""
    return True
import logging
_task_logger = logging.getLogger('offer_routing.tasks')


@shared_task(name='offer_routing.tasks.run_fraud_batch_scan')
def run_fraud_batch_scan():
    """Hourly batch fraud scan across all active offers."""
    try:
        from offer_routing.services import fraud_detection_service
        result = fraud_detection_service.batch_scan_active_offers()
        return result
    except Exception as e:
        _task_logger.error(f"run_fraud_batch_scan: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='offer_routing.tasks.recalculate_offer_quality_scores')
def recalculate_offer_quality_scores():
    """Daily quality score recalculation for all tenant offers."""
    try:
        from offer_routing.services.domain import offer_quality_service
        from django.contrib.auth import get_user_model
        User = get_user_model()
        count = 0
        for tenant in User.objects.filter(is_active=True)[:100]:
            result = offer_quality_service.recalculate_all(tenant)
            count += result.get('recalculated', 0)
        return {'success': True, 'recalculated': count}
    except Exception as e:
        _task_logger.error(f"recalculate_offer_quality_scores: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='offer_routing.tasks.refresh_network_performance_cache')
def refresh_network_performance_cache():
    """Every 10 minutes — refresh stale network performance data."""
    try:
        from offer_routing.models import NetworkPerformanceCache
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(hours=1)
        deleted, _ = NetworkPerformanceCache.objects.filter(updated_at__lt=cutoff).delete()
        return {'success': True, 'evicted': deleted}
    except Exception as e:
        _task_logger.error(f"refresh_network_performance_cache: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='offer_routing.tasks.cleanup_old_journey_steps')
def cleanup_old_journey_steps():
    """Weekly — remove journey steps older than 90 days."""
    try:
        from offer_routing.services.domain import user_journey_service
        from django.contrib.auth import get_user_model
        User = get_user_model()
        total = 0
        for tenant in User.objects.filter(is_active=True)[:100]:
            result = user_journey_service.cleanup_old_steps(tenant, days_to_keep=90)
            total += result.get('deleted', 0)
        return {'success': True, 'deleted': total}
    except Exception as e:
        _task_logger.error(f"cleanup_old_journey_steps: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='offer_routing.tasks.generate_tenant_billing')
def generate_tenant_billing():
    """Monthly — auto-generate billing records for all tenants."""
    try:
        from offer_routing.services.domain import tenant_service
        from django.contrib.auth import get_user_model
        from offer_routing.models import RoutingDecisionLog
        from django.utils import timezone
        from django.db.models import Count
        User = get_user_model()
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        count = 0
        for tenant in User.objects.filter(is_active=True)[:100]:
            decisions = RoutingDecisionLog.objects.filter(
                tenant=tenant, created_at__gte=month_start
            ).count()
            cost = round(decisions * 0.001, 4)
            tenant_service.record_billing(tenant, decisions, cost)
            count += 1
        return {'success': True, 'tenants_billed': count}
    except Exception as e:
        _task_logger.error(f"generate_tenant_billing: {e}")
        return {'success': False, 'error': str(e)}
