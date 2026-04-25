"""
Tasks Module for Offer Routing System

This module imports all background tasks for the offer routing system.
"""

from .core import (
    maintenance_tasks, cleanup_cache, cleanup_database, optimize_performance,
    system_health_check, warmup_cache, update_global_rankings, generate_insights
)
from .scoring import (
    update_all_offer_scores, update_global_rankings, optimize_score_weights,
    calculate_user_affinity_scores, update_user_offer_history, refresh_score_cache,
    analyze_score_performance, update_epc_data, calculate_conversion_rates
)
from .personalization import (
    update_user_preferences, update_affinity_scores, update_collaborative_filtering,
    update_content_based_filtering, optimize_personalization_configs,
    process_contextual_signals, cleanup_expired_signals, calculate_personalization_metrics,
    train_ml_models, update_real_time_personalization
)
from .cap import (
    reset_daily_caps, enforce_global_caps, update_cap_analytics, check_cap_health,
    optimize_cap_configuration, cleanup_old_cap_data, generate_cap_reports,
    update_cap_usage_statistics
)
from .ab_test import (
    evaluate_active_tests, check_test_duration, update_test_assignments,
    generate_test_reports, cleanup_completed_tests, optimize_test_configuration,
    update_test_metrics, check_test_health
)
from .analytics import (
    aggregate_hourly_stats, generate_insights, update_performance_metrics,
    generate_daily_reports, update_exposure_stats, calculate_user_analytics,
    cleanup_old_analytics, update_trending_metrics, calculate_funnel_metrics
)
from .fallback import (
    check_fallback_health, update_offer_pools, update_fallback_rules,
    update_empty_handlers, generate_fallback_analytics, optimize_fallback_configuration,
    cleanup_inactive_fallbacks, update_fallback_metrics
)
from .monitoring import (
    perform_health_check, check_service_dependencies, collect_performance_metrics,
    check_resource_usage, generate_monitoring_report, update_monitoring_dashboard,
    check_alert_thresholds, cleanup_old_monitoring_data, update_monitoring_metrics
)

__all__ = [
    # Core Tasks
    'maintenance_tasks',
    'cleanup_cache',
    'cleanup_database',
    'optimize_performance',
    'system_health_check',
    'warmup_cache',
    'update_global_rankings',
    'generate_insights',
    
    # Scoring Tasks
    'update_all_offer_scores',
    'update_global_rankings',
    'optimize_score_weights',
    'calculate_user_affinity_scores',
    'update_user_offer_history',
    'refresh_score_cache',
    'analyze_score_performance',
    'update_epc_data',
    'calculate_conversion_rates',
    
    # Personalization Tasks
    'update_user_preferences',
    'update_affinity_scores',
    'update_collaborative_filtering',
    'update_content_based_filtering',
    'optimize_personalization_configs',
    'process_contextual_signals',
    'cleanup_expired_signals',
    'calculate_personalization_metrics',
    'train_ml_models',
    'update_real_time_personalization',
    
    # Cap Tasks
    'reset_daily_caps',
    'enforce_global_caps',
    'update_cap_analytics',
    'check_cap_health',
    'optimize_cap_configuration',
    'cleanup_old_cap_data',
    'generate_cap_reports',
    'update_cap_usage_statistics',
    
    # A/B Test Tasks
    'evaluate_active_tests',
    'check_test_duration',
    'update_test_assignments',
    'generate_test_reports',
    'cleanup_completed_tests',
    'optimize_test_configuration',
    'update_test_metrics',
    'check_test_health',
    
    # Analytics Tasks
    'aggregate_hourly_stats',
    'generate_insights',
    'update_performance_metrics',
    'generate_daily_reports',
    'update_exposure_stats',
    'calculate_user_analytics',
    'cleanup_old_analytics',
    'update_trending_metrics',
    'calculate_funnel_metrics',
    
    # Fallback Tasks
    'check_fallback_health',
    'update_offer_pools',
    'update_fallback_rules',
    'update_empty_handlers',
    'generate_fallback_analytics',
    'optimize_fallback_configuration',
    'cleanup_inactive_fallbacks',
    'update_fallback_metrics',
    
    # Monitoring Tasks
    'perform_health_check',
    'check_service_dependencies',
    'collect_performance_metrics',
    'check_resource_usage',
    'generate_monitoring_report',
    'update_monitoring_dashboard',
    'check_alert_thresholds',
    'cleanup_old_monitoring_data',
    'update_monitoring_metrics',
]
