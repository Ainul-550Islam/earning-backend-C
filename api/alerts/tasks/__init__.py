"""
Alert Tasks Package
"""
from .collect_system_metrics import (
    collect_system_metrics,
)
from .adaptive_threshold_tasks import (
    recalculate_adaptive_thresholds,
    recalculate_single_adaptive_threshold,
    update_threshold_profiles,
    cleanup_old_threshold_history,
)
from .correlation_tasks import (
    correlate_recent_alerts,
    reanalyze_all_correlations,
    expire_stale_correlations,
    update_correlation_cache,
)
from .oncall_notify_tasks import (
    notify_oncall_new_incident,
    notify_oncall_escalation,
    notify_oncall_rotation_change,
    notify_oncall_unacknowledged_alert,
    check_and_notify_unacknowledged_alerts,
)
from .report_generation_tasks import (
    generate_weekly_report_scheduled,
    generate_monthly_report_scheduled,
    generate_sla_summary_report,
    run_due_recurring_reports,
    generate_report_on_demand,
)
from .channel_health_tasks import (
    check_all_channel_health,
    check_single_channel_health,
    compute_channel_delivery_rates,
    cleanup_old_channel_health_logs,
)
from .core import (
    process_pending_alerts, escalate_alerts, generate_daily_analytics,
    send_group_alerts, update_alert_group_caches, cleanup_old_alerts,
    cleanup_old_notifications, update_rule_health, optimize_alert_indexes,
    expire_suppressions, check_system_health, resolve_alert, acknowledge_alert,
    test_alert_rule, bulk_resolve_alerts, update_alert_statistics
)
from .notification import (
    send_pending_notifications, send_notifications, retry_failed_notifications, check_channel_health,
    test_channel, update_notification_statistics,
    cleanup_old_notifications as cleanup_old_notification_records,
    update_recipient_availability, send_notification_to_recipients,
    process_notification_queue, escalate_notification, track_notification_delivery,
    generate_notification_report, optimize_notification_delivery
)
from .intelligence import (
    analyze_all_correlations, train_prediction_models, detect_anomalies,
    optimize_noise_filters, run_intelligence_pipeline, update_correlation_insights,
    evaluate_model_accuracy, generate_anomaly_report, update_noise_effectiveness,
    create_rca_for_incidents, generate_intelligence_dashboard_data,
    cleanup_old_intelligence_data, train_correlation_model, test_prediction_model,
    update_anomaly_thresholds, generate_correlation_report, optimize_intelligence_models,
    update_prediction_accuracy_metrics
)
from .reporting import (
    generate_daily_reports, generate_weekly_reports, generate_monthly_reports,
    generate_sla_reports, calculate_mttr_metrics, calculate_mttd_metrics,
    check_sla_breaches, generate_performance_reports, generate_trend_analysis_reports,
    distribute_reports, cleanup_old_reports, schedule_recurring_reports,
    update_reporting_metrics, generate_custom_report, export_report,
    create_scheduled_report, analyze_report_usage
)
from .incident import (
    check_incident_escalations, update_on_call_schedules, check_responder_availability,
    generate_incident_summary, create_incident_from_alert, update_incident_metrics,
    check_post_mortem_deadlines, auto_resolve_low_priority_incidents,
    generate_incident_dashboard_data, cleanup_old_incident_data,
    notify_on_call_changes, update_incident_response_metrics,
    escalate_unacknowledged_incidents, generate_incident_trends_report
)

__all__ = [
    # Metrics collection
    'collect_system_metrics',

    # Adaptive threshold tasks
    'recalculate_adaptive_thresholds',
    'recalculate_single_adaptive_threshold',
    'update_threshold_profiles',
    'cleanup_old_threshold_history',

    # Correlation tasks
    'correlate_recent_alerts',
    'reanalyze_all_correlations',
    'expire_stale_correlations',
    'update_correlation_cache',

    # On-call notification tasks
    'notify_oncall_new_incident',
    'notify_oncall_escalation',
    'notify_oncall_rotation_change',
    'notify_oncall_unacknowledged_alert',
    'check_and_notify_unacknowledged_alerts',

    # Scheduled report generation tasks
    'generate_weekly_report_scheduled',
    'generate_monthly_report_scheduled',
    'generate_sla_summary_report',
    'run_due_recurring_reports',
    'generate_report_on_demand',

    # Channel health tasks
    'check_all_channel_health',
    'check_single_channel_health',
    'compute_channel_delivery_rates',
    'cleanup_old_channel_health_logs',

    # Core Tasks
    'process_pending_alerts', 'escalate_alerts', 'generate_daily_analytics',
    'send_group_alerts', 'update_alert_group_caches', 'cleanup_old_alerts',
    'cleanup_old_notifications', 'update_rule_health', 'optimize_alert_indexes',
    'expire_suppressions', 'check_system_health', 'resolve_alert', 'acknowledge_alert',
    'test_alert_rule', 'bulk_resolve_alerts', 'update_alert_statistics',
    
    # Notification Tasks
    'send_pending_notifications', 'send_notifications', 'retry_failed_notifications', 'check_channel_health',
    'test_channel', 'update_notification_statistics', 'cleanup_old_notification_records',
    'update_recipient_availability', 'send_notification_to_recipients',
    'process_notification_queue', 'escalate_notification', 'track_notification_delivery',
    'generate_notification_report', 'optimize_notification_delivery',
    
    # Intelligence Tasks
    'analyze_all_correlations', 'train_prediction_models', 'detect_anomalies',
    'optimize_noise_filters', 'run_intelligence_pipeline', 'update_correlation_insights',
    'evaluate_model_accuracy', 'generate_anomaly_report', 'update_noise_effectiveness',
    'create_rca_for_incidents', 'generate_intelligence_dashboard_data',
    'cleanup_old_intelligence_data', 'train_correlation_model', 'test_prediction_model',
    'update_anomaly_thresholds', 'generate_correlation_report', 'optimize_intelligence_models',
    'update_prediction_accuracy_metrics',
    
    # Reporting Tasks
    'generate_daily_reports', 'generate_weekly_reports', 'generate_monthly_reports',
    'generate_sla_reports', 'calculate_mttr_metrics', 'calculate_mttd_metrics',
    'check_sla_breaches', 'generate_performance_reports', 'generate_trend_analysis_reports',
    'distribute_reports', 'cleanup_old_reports', 'schedule_recurring_reports',
    'update_reporting_metrics', 'generate_custom_report', 'export_report',
    'create_scheduled_report', 'analyze_report_usage',
    
    # Incident Tasks
    'check_incident_escalations', 'update_on_call_schedules', 'check_responder_availability',
    'generate_incident_summary', 'create_incident_from_alert', 'update_incident_metrics',
    'check_post_mortem_deadlines', 'auto_resolve_low_priority_incidents',
    'generate_incident_dashboard_data', 'cleanup_old_incident_data',
    'notify_on_call_changes', 'update_incident_response_metrics',
    'escalate_unacknowledged_incidents', 'generate_incident_trends_report',
]
