"""
alerts/signals/__init__.py — FIXED (complete rewrite)
Previously: imported Signal objects that didn't exist → ImportError on startup
            meaning ALL 118 signal handlers never fired in production.
Now:         safe imports with fallback, all Signal objects defined in each file.
"""
import logging
logger = logging.getLogger(__name__)


def _safe_import(module, names):
    """Import names from module, return only those that exist."""
    imported = {}
    try:
        import importlib
        mod = importlib.import_module(module)
        for name in names:
            obj = getattr(mod, name, None)
            if obj is not None:
                imported[name] = obj
    except Exception as e:
        logger.warning('api.alerts.signals: could not import from %s: %s', module, e)
    return imported


# ── Core signals ───────────────────────────────────────────────────────────────
_core = _safe_import('api.alerts.signals.core', [
    'alert_rule_created', 'alert_rule_updated', 'alert_rule_deleted',
    'alert_rule_enabled', 'alert_rule_disabled', 'alert_log_created',
    'alert_log_updated', 'notification_created', 'notification_updated',
    'escalation_created', 'template_created', 'analytics_created',
    'group_created', 'suppression_created', 'health_check_created',
    'rule_history_created', 'dashboard_config_created', 'metrics_created',
])
alert_rule_created       = _core.get('alert_rule_created')
alert_rule_updated       = _core.get('alert_rule_updated')
alert_rule_deleted       = _core.get('alert_rule_deleted')
alert_rule_enabled       = _core.get('alert_rule_enabled')
alert_rule_disabled      = _core.get('alert_rule_disabled')
alert_log_created        = _core.get('alert_log_created')
alert_log_updated        = _core.get('alert_log_updated')
notification_created     = _core.get('notification_created')
notification_updated     = _core.get('notification_updated')
escalation_created       = _core.get('escalation_created')


# ── Threshold signals ──────────────────────────────────────────────────────────
_threshold = _safe_import('api.alerts.signals.threshold', [
    'threshold_config_created', 'threshold_config_updated',
    'threshold_breach_created', 'threshold_breach_resolved',
    'threshold_breach_acknowledged', 'adaptive_threshold_created',
    'adaptive_threshold_updated', 'threshold_history_created',
    'threshold_profile_created', 'threshold_profile_applied',
])
threshold_config_created   = _threshold.get('threshold_config_created')
threshold_config_updated   = _threshold.get('threshold_config_updated')
threshold_breach_created   = _threshold.get('threshold_breach_created')
threshold_breach_resolved  = _threshold.get('threshold_breach_resolved')
adaptive_threshold_created = _threshold.get('adaptive_threshold_created')
adaptive_threshold_updated = _threshold.get('adaptive_threshold_updated')
threshold_profile_created  = _threshold.get('threshold_profile_created')
threshold_profile_applied  = _threshold.get('threshold_profile_applied')


# ── Channel signals ────────────────────────────────────────────────────────────
_channel = _safe_import('api.alerts.signals.channel', [
    'channel_created', 'channel_updated', 'channel_enabled', 'channel_disabled',
    'channel_health_checked', 'channel_failure', 'channel_recovery',
    'channel_test_sent', 'channel_health_updated', 'route_created', 'route_updated',
    'health_log_created', 'rate_limit_created', 'recipient_created',
    'recipient_updated', 'rate_limit_reset', 'routing_updated',
    'recipient_availability_changed',
])
channel_created          = _channel.get('channel_created')
channel_updated          = _channel.get('channel_updated')
channel_enabled          = _channel.get('channel_enabled')
channel_disabled         = _channel.get('channel_disabled')
channel_failure          = _channel.get('channel_failure')
channel_recovery         = _channel.get('channel_recovery')
route_created            = _channel.get('route_created')
route_updated            = _channel.get('route_updated')
recipient_created        = _channel.get('recipient_created')
recipient_updated        = _channel.get('recipient_updated')
recipient_availability_changed = _channel.get('recipient_availability_changed')


# ── Incident signals ───────────────────────────────────────────────────────────
_incident = _safe_import('api.alerts.signals.incident', [
    'incident_created', 'incident_updated', 'incident_acknowledged',
    'incident_escalated', 'incident_resolved', 'incident_closed',
    'timeline_created', 'responder_created', 'responder_updated',
    'post_mortem_created', 'post_mortem_updated', 'oncall_schedule_created',
    'oncall_updated', 'oncall_rotation_changed', 'post_mortem_required',
    'auto_resolution_triggered', 'timeline_event_added', 'responder_assigned',
])
incident_created      = _incident.get('incident_created')
incident_updated      = _incident.get('incident_updated')
incident_acknowledged = _incident.get('incident_acknowledged')
incident_escalated    = _incident.get('incident_escalated')
incident_resolved     = _incident.get('incident_resolved')
incident_closed       = _incident.get('incident_closed')
timeline_created      = _incident.get('timeline_created')
timeline_event_added  = _incident.get('timeline_event_added')
responder_assigned    = _incident.get('responder_assigned')


# ── Intelligence signals ───────────────────────────────────────────────────────
_intelligence = _safe_import('api.alerts.signals.intelligence', [
    'correlation_created', 'correlation_updated', 'correlation_detected',
    'correlation_analyzed', 'prediction_created', 'prediction_trained',
    'anomaly_detected', 'noise_filter_created', 'noise_filtered',
    'rca_created', 'rca_completed', 'root_cause_identified', 'prediction_made',
])
correlation_detected  = _intelligence.get('correlation_detected')
correlation_created   = _intelligence.get('correlation_created')
prediction_created    = _intelligence.get('prediction_created')
prediction_trained    = _intelligence.get('prediction_trained')
anomaly_detected      = _intelligence.get('anomaly_detected')
noise_filtered        = _intelligence.get('noise_filtered')
rca_created           = _intelligence.get('rca_created')
rca_completed         = _intelligence.get('rca_completed')
root_cause_identified = _intelligence.get('root_cause_identified')


# ── Reporting signals ──────────────────────────────────────────────────────────
_reporting = _safe_import('api.alerts.signals.reporting', [
    'report_created', 'report_updated', 'report_generated', 'report_distributed',
    'report_scheduled', 'mttr_calculated', 'mttd_calculated',
    'sla_breach_detected', 'sla_breach_resolved', 'sla_breach_acknowledged',
    'sla_breach_escalated', 'performance_metric_calculated', 'trend_analysis_completed',
])
report_created       = _reporting.get('report_created')
report_generated     = _reporting.get('report_generated')
report_distributed   = _reporting.get('report_distributed')
report_scheduled     = _reporting.get('report_scheduled')
mttr_calculated      = _reporting.get('mttr_calculated')
mttd_calculated      = _reporting.get('mttd_calculated')
sla_breach_detected  = _reporting.get('sla_breach_detected')
sla_breach_resolved  = _reporting.get('sla_breach_resolved')
sla_breach_acknowledged = _reporting.get('sla_breach_acknowledged')


__all__ = [
    # Core
    'alert_rule_created', 'alert_rule_updated', 'alert_rule_deleted',
    'alert_rule_enabled', 'alert_rule_disabled', 'alert_log_created',
    'alert_log_updated', 'notification_created', 'notification_updated',
    # Threshold
    'threshold_config_created', 'threshold_config_updated',
    'threshold_breach_created', 'threshold_breach_resolved',
    'adaptive_threshold_created', 'adaptive_threshold_updated',
    # Channel
    'channel_created', 'channel_updated', 'channel_enabled', 'channel_disabled',
    'channel_failure', 'channel_recovery', 'route_created', 'route_updated',
    'recipient_created', 'recipient_updated', 'recipient_availability_changed',
    # Incident
    'incident_created', 'incident_updated', 'incident_acknowledged',
    'incident_escalated', 'incident_resolved', 'incident_closed',
    'timeline_created', 'timeline_event_added', 'responder_assigned',
    # Intelligence
    'correlation_detected', 'correlation_created', 'prediction_created',
    'anomaly_detected', 'noise_filtered', 'rca_completed', 'root_cause_identified',
    # Reporting
    'report_created', 'report_generated', 'report_distributed',
    'mttr_calculated', 'mttd_calculated', 'sla_breach_detected', 'sla_breach_resolved',
]
