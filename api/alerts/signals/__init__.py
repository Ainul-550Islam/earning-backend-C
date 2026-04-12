"""
Alert Signals Package
"""
from .core import (
    alert_rule_created, alert_rule_updated, alert_rule_deleted,
    alert_rule_enabled, alert_rule_disabled, alert_log_created,
    alert_log_updated, notification_created, notification_updated,
    escalation_created, template_created, analytics_created,
    group_created, suppression_created, health_check_created,
    rule_history_created, dashboard_config_created, metrics_created
)
from .threshold import (
    threshold_config_created, threshold_config_updated, threshold_breach_created,
    threshold_breach_resolved, adaptive_threshold_created, adaptive_threshold_updated,
    threshold_history_created, threshold_profile_created, threshold_profile_applied
)
from .channel import (
    channel_created, channel_updated, channel_health_checked,
    channel_failure, channel_recovery, route_created, route_updated,
    health_log_created, rate_limit_created, recipient_created,
    recipient_updated, rate_limit_reset, routing_updated
)
from .incident import (
    incident_created, incident_updated, incident_escalated,
    incident_resolved, incident_closed, timeline_created, responder_created,
    responder_updated, post_mortem_created, post_mortem_updated,
    oncall_schedule_created, oncall_updated, oncall_rotation_changed,
    post_mortem_required, auto_resolution_triggered
)
from .intelligence import (
    correlation_created, correlation_analyzed, prediction_created,
    prediction_trained, anomaly_detected, noise_filter_created,
    noise_filter_applied, rca_created, rca_completed, pipeline_completed,
    model_optimized, intelligence_updated
)
from .reporting import (
    report_created, report_generated, report_distributed,
    mttr_calculated, mttd_calculated, sla_breach_detected,
    sla_breach_escalated, daily_report_generated, weekly_report_generated,
    monthly_report_generated, performance_report_generated,
    trend_report_generated, metrics_updated
)

__all__ = [
    # Core signals
    'alert_rule_created', 'alert_rule_updated', 'alert_rule_deleted',
    'alert_rule_enabled', 'alert_rule_disabled', 'alert_log_created',
    'alert_log_updated', 'notification_created', 'notification_updated',
    'escalation_created', 'template_created', 'analytics_created',
    'group_created', 'suppression_created', 'health_check_created',
    'rule_history_created', 'dashboard_config_created', 'metrics_created',
    
    # Threshold signals
    'threshold_config_created', 'threshold_config_updated', 'threshold_breach_created',
    'threshold_breach_resolved', 'adaptive_threshold_created', 'adaptive_threshold_updated',
    'threshold_history_created', 'threshold_profile_created', 'threshold_profile_applied',
    
    # Channel signals
    'channel_created', 'channel_updated', 'channel_health_checked',
    'channel_failure', 'channel_recovery', 'route_created', 'route_updated',
    'health_log_created', 'rate_limit_created', 'recipient_created',
    'recipient_updated', 'rate_limit_reset', 'routing_updated',
    
    # Incident signals
    'incident_created', 'incident_updated', 'incident_escalated',
    'incident_resolved', 'incident_closed', 'timeline_created', 'responder_created',
    'responder_updated', 'post_mortem_created', 'post_mortem_updated',
    'oncall_schedule_created', 'oncall_updated', 'oncall_rotation_changed',
    'post_mortem_required', 'auto_resolution_triggered',
    
    # Intelligence signals
    'correlation_created', 'correlation_analyzed', 'prediction_created',
    'prediction_trained', 'anomaly_detected', 'noise_filter_created',
    'noise_filter_applied', 'rca_created', 'rca_completed', 'pipeline_completed',
    'model_optimized', 'intelligence_updated',
    
    # Reporting signals
    'report_created', 'report_generated', 'report_distributed',
    'mttr_calculated', 'mttd_calculated', 'sla_breach_detected',
    'sla_breach_escalated', 'daily_report_generated', 'weekly_report_generated',
    'monthly_report_generated', 'performance_report_generated',
    'trend_report_generated', 'metrics_updated',
]
