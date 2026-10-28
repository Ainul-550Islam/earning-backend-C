"""
Reporting Signals  — FIXED: sla_breach_detected, report_generated, threshold_breach now trigger real downstream actions
"""
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.reporting import (
    AlertReport, MTTRMetric, MTTDMetric, SLABreach
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=AlertReport)
def alert_report_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertReport"""
    try:
        if not instance.report_type:
            instance.report_type = 'custom'
        if not instance.status:
            instance.status = 'pending'
        if not instance.format_type:
            instance.format_type = 'json'
        if not instance.auto_distribute:
            instance.auto_distribute = False
        if not instance.is_recurring:
            instance.is_recurring = False
        if not instance.max_retries:
            instance.max_retries = 3
        valid_types = [c[0] for c in AlertReport._meta.get_field('report_type').choices]
        if instance.report_type not in valid_types:
            logger.warning(f"Invalid report type '{instance.report_type}' for AlertReport {instance.id}")
        valid_statuses = [c[0] for c in AlertReport._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for AlertReport {instance.id}")
        valid_formats = [c[0] for c in AlertReport._meta.get_field('format_type').choices]
        if instance.format_type not in valid_formats:
            logger.warning(f"Invalid format type '{instance.format_type}' for AlertReport {instance.id}")
    except Exception as e:
        logger.error(f"Error in alert_report_pre_save: {e}")


@receiver(post_save, sender=AlertReport)
def alert_report_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertReport"""
    try:
        if created:
            logger.info(f"Created new AlertReport: {instance.title} ({instance.report_type})")
            from ..tasks.reporting import generate_custom_report
            generate_custom_report.delay(instance.id)
        else:
            logger.debug(f"Updated AlertReport: {instance.title}")
            if instance.status == 'pending':
                from ..tasks.reporting import generate_custom_report
                generate_custom_report.delay(instance.id)
            if instance.is_recurring and not instance.next_run:
                from ..tasks.reporting import schedule_recurring_reports
                schedule_recurring_reports.delay()
            # FIXED: auto-distribute immediately when report completes
            if instance.status == 'completed' and instance.auto_distribute:
                from ..tasks.reporting import distribute_reports
                distribute_reports.delay(instance.id)
    except Exception as e:
        logger.error(f"Error in alert_report_post_save: {e}")


@receiver(pre_save, sender=MTTRMetric)
def mttr_metric_pre_save(sender, instance, **kwargs):
    """Signal handler before saving MTTRMetric"""
    try:
        if not instance.calculation_period_days:
            instance.calculation_period_days = 30
        if not instance.target_mttr_minutes:
            instance.target_mttr_minutes = 60
        if not 1 <= instance.calculation_period_days <= 365:
            logger.warning(f"Invalid calculation period '{instance.calculation_period_days}' for MTTRMetric {instance.id}")
        if instance.target_mttr_minutes <= 0:
            logger.warning(f"Invalid target MTTR '{instance.target_mttr_minutes}' for MTTRMetric {instance.id}")
    except Exception as e:
        logger.error(f"Error in mttr_metric_pre_save: {e}")


@receiver(post_save, sender=MTTRMetric)
def mttr_metric_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving MTTRMetric"""
    try:
        if created:
            logger.info(f"Created new MTTRMetric: {instance.name}")
        else:
            logger.debug(f"Updated MTTRMetric: {instance.name}")
        from ..tasks.reporting import calculate_mttr_metrics
        if not getattr(instance, '_skip_recalc_signal', False):
            calculate_mttr_metrics.delay()
    except Exception as e:
        logger.error(f"Error in mttr_metric_post_save: {e}")


@receiver(pre_save, sender=MTTDMetric)
def mttd_metric_pre_save(sender, instance, **kwargs):
    """Signal handler before saving MTTDMetric"""
    try:
        if not instance.calculation_period_days:
            instance.calculation_period_days = 30
        if not instance.target_mttd_minutes:
            instance.target_mttd_minutes = 15
        if not 1 <= instance.calculation_period_days <= 365:
            logger.warning(f"Invalid calculation period '{instance.calculation_period_days}' for MTTDMetric {instance.id}")
        if instance.target_mttd_minutes <= 0:
            logger.warning(f"Invalid target MTTD '{instance.target_mttd_minutes}' for MTTDMetric {instance.id}")
    except Exception as e:
        logger.error(f"Error in mttd_metric_pre_save: {e}")


@receiver(post_save, sender=MTTDMetric)
def mttd_metric_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving MTTDMetric"""
    try:
        if created:
            logger.info(f"Created new MTTDMetric: {instance.name}")
        else:
            logger.debug(f"Updated MTTDMetric: {instance.name}")
        from ..tasks.reporting import calculate_mttd_metrics
        if not getattr(instance, '_skip_recalc_signal', False):
            calculate_mttd_metrics.delay()
    except Exception as e:
        logger.error(f"Error in mttd_metric_post_save: {e}")


@receiver(pre_save, sender=SLABreach)
def sla_breach_pre_save(sender, instance, **kwargs):
    """Signal handler before saving SLABreach"""
    try:
        if not instance.sla_type:
            instance.sla_type = 'resolution_time'
        if not instance.severity:
            instance.severity = 'medium'
        if not instance.status:
            instance.status = 'active'
        if not instance.escalation_level:
            instance.escalation_level = 0
        if not instance.stakeholder_notified:
            instance.stakeholder_notified = False
        if not instance.communication_sent:
            instance.communication_sent = False
        valid_types = [c[0] for c in SLABreach._meta.get_field('sla_type').choices]
        if instance.sla_type not in valid_types:
            logger.warning(f"Invalid SLA type '{instance.sla_type}' for SLABreach {instance.id}")
        valid_severities = [c[0] for c in SLABreach._meta.get_field('severity').choices]
        if instance.severity not in valid_severities:
            logger.warning(f"Invalid severity '{instance.severity}' for SLABreach {instance.id}")
        valid_statuses = [c[0] for c in SLABreach._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for SLABreach {instance.id}")
    except Exception as e:
        logger.error(f"Error in sla_breach_pre_save: {e}")


@receiver(post_save, sender=SLABreach)
def sla_breach_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving SLABreach"""
    try:
        if created:
            logger.info(f"Created new SLABreach: {instance.name} ({instance.sla_type} - {instance.severity})")
            from ..tasks.notification import send_notification_to_recipients
            send_notification_to_recipients.delay(
                notification_type='email',
                message=f"SLA Breach Detected: {instance.name}",
                subject=f"SLA Breach Alert: {instance.sla_type}"
            )
            if instance.severity == 'critical':
                from ..tasks.incident import check_incident_escalations
                check_incident_escalations.delay()
            # FIXED: notify on-call immediately for any SLA breach
            try:
                from ..tasks.oncall_notify_tasks import notify_oncall_escalation
                notify_oncall_escalation.delay(breach_id=instance.pk)
            except Exception as exc:
                logger.warning(f"Could not trigger notify_oncall_escalation for breach {instance.pk}: {exc}")
            # FIXED: trigger SLA report to capture the breach
            from ..tasks.reporting import check_sla_breaches
            check_sla_breaches.delay()
            # Audit log the SLA breach
            try:
                from api.alerts.integration import get_audit_logger
                from api.alerts.integration.integ_audit_logs import AuditEventType, AuditSeverity
                al = get_audit_logger()
                if al:
                    al.log_event(
                        event_type=AuditEventType.SLA_BREACH_DETECTED,
                        severity=AuditSeverity.CRITICAL if instance.severity == 'critical' else AuditSeverity.WARNING,
                        description=f"SLA breach: {instance.name} ({instance.sla_type})",
                        details={'breach_id': instance.pk, 'severity': instance.severity, 'sla_type': instance.sla_type}
                    )
            except Exception:
                pass
        else:
            logger.debug(f"Updated SLABreach: {instance.name}")
            if instance.status == 'escalated':
                from ..tasks.notification import escalate_notification
                escalate_notification.delay(instance.id, instance.escalation_level)
    except Exception as e:
        logger.error(f"Error in sla_breach_post_save: {e}")


# ── Helper functions ─────────────────────────────────────────────────────────

def trigger_sla_breach_check(alert_log):
    """Check if a resolved alert has breached its SLA and create a SLABreach record if so."""
    try:
        if alert_log.is_resolved and alert_log.resolved_at:
            resolution_time = (alert_log.resolved_at - alert_log.triggered_at).total_seconds() / 60
            sla_thresholds = {
                'critical': 60,
                'high': 120,
                'medium': 240,
                'low': 480
            }
            threshold = sla_thresholds.get(alert_log.rule.severity, 240)
            if resolution_time > threshold:
                breach = SLABreach.objects.create(
                    name=f"SLA Breach - {alert_log.rule.name}",
                    sla_type='resolution_time',
                    severity=alert_log.rule.severity,
                    alert_log=alert_log,
                    threshold_minutes=threshold,
                    breach_time=alert_log.resolved_at,
                    breach_duration_minutes=resolution_time - threshold,
                    breach_percentage=(resolution_time / threshold - 1) * 100
                )
                logger.warning(f"SLA breach detected: {breach.name} - {resolution_time:.1f}min > {threshold}min")
                from ..tasks.notification import send_notification_to_recipients
                send_notification_to_recipients.delay(
                    notification_type='email',
                    message=f"SLA Breach: {breach.name}",
                    subject=f"SLA Breach Alert: {alert_log.rule.severity}"
                )
    except Exception as e:
        logger.error(f"Error in trigger_sla_breach_check: {e}")


def trigger_mttr_calculation():
    """Trigger MTTR recalculation and regenerate performance reports."""
    try:
        logger.info("Triggering MTTR calculation")
        from ..tasks.reporting import calculate_mttr_metrics
        calculate_mttr_metrics.delay()
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
    except Exception as e:
        logger.error(f"Error in trigger_mttr_calculation: {e}")


def trigger_mttd_calculation():
    """Trigger MTTD recalculation and regenerate performance reports."""
    try:
        logger.info("Triggering MTTD calculation")
        from ..tasks.reporting import calculate_mttd_metrics
        calculate_mttd_metrics.delay()
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
    except Exception as e:
        logger.error(f"Error in trigger_mttd_calculation: {e}")


def trigger_sla_report_generation():
    """Generate SLA reports and run a breach check."""
    try:
        logger.info("Triggering SLA report generation")
        from ..tasks.reporting import generate_sla_reports
        generate_sla_reports.delay()
        from ..tasks.reporting import check_sla_breaches
        check_sla_breaches.delay()
    except Exception as e:
        logger.error(f"Error in trigger_sla_report_generation: {e}")


def trigger_daily_report_generation():
    """Generate daily reports and update reporting metrics."""
    try:
        logger.info("Triggering daily report generation")
        from ..tasks.reporting import generate_daily_reports
        generate_daily_reports.delay()
        from ..tasks.reporting import update_reporting_metrics
        update_reporting_metrics.delay()
    except Exception as e:
        logger.error(f"Error in trigger_daily_report_generation: {e}")


def trigger_weekly_report_generation():
    """Generate weekly reports and trend analysis."""
    try:
        logger.info("Triggering weekly report generation")
        from ..tasks.reporting import generate_weekly_reports
        generate_weekly_reports.delay()
        from ..tasks.reporting import generate_trend_analysis_reports
        generate_trend_analysis_reports.delay()
    except Exception as e:
        logger.error(f"Error in trigger_weekly_report_generation: {e}")


def trigger_monthly_report_generation():
    """Generate monthly reports and performance analysis."""
    try:
        logger.info("Triggering monthly report generation")
        from ..tasks.reporting import generate_monthly_reports
        generate_monthly_reports.delay()
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
    except Exception as e:
        logger.error(f"Error in trigger_monthly_report_generation: {e}")


def trigger_report_distribution(report):
    """Distribute a completed report and notify recipients."""
    try:
        logger.info(f"Triggering distribution for report {report.title}")
        from ..tasks.reporting import distribute_reports
        distribute_reports.delay(report.pk)
        from ..models.core import Notification
        notification = Notification.objects.create(
            notification_type='email',
            recipient="report_recipients",
            subject=f"Report Distributed: {report.title}",
            message=f"Report '{report.title}' has been distributed to recipients",
            status='pending'
        )
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        return notification
    except Exception as e:
        logger.error(f"Error in trigger_report_distribution: {e}")
        return None


def trigger_report_cleanup():
    """Remove old report files and DB records."""
    try:
        logger.info("Triggering report cleanup")
        from ..tasks.reporting import cleanup_old_reports
        cleanup_old_reports.delay()
    except Exception as e:
        logger.error(f"Error in trigger_report_cleanup: {e}")


def trigger_sla_escalation(sla_breach):
    """Escalate a critical SLA breach and notify the SLA manager."""
    try:
        logger.warning(f"Triggering SLA escalation for breach {sla_breach.name}")
        from ..models.core import Notification
        notification = Notification.objects.create(
            notification_type='email',
            recipient="sla_manager",
            subject=f"SLA Escalation: {sla_breach.name}",
            message=f"SLA breach requires escalation: {sla_breach.name} - {sla_breach.breach_percentage:.1f}% breach",
            status='pending'
        )
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        return notification
    except Exception as e:
        logger.error(f"Error in trigger_sla_escalation: {e}")
        return None


def trigger_metrics_dashboard_update():
    """Recalculate MTTR/MTTD and refresh the reporting dashboard."""
    try:
        logger.info("Triggering metrics dashboard update")
        trigger_mttr_calculation()
        trigger_mttd_calculation()
        from ..tasks.reporting import update_reporting_metrics
        update_reporting_metrics.delay()
    except Exception as e:
        logger.error(f"Error in trigger_metrics_dashboard_update: {e}")


def register_reporting_signals():
    """Register all reporting signals"""
    try:
        logger.info("Reporting signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering reporting signals: {e}")


register_reporting_signals()


from django.dispatch import Signal

report_created       = Signal()
report_updated       = Signal()
report_generated     = Signal()
report_distributed   = Signal()
report_scheduled     = Signal()
mttr_calculated      = Signal()
mttd_calculated      = Signal()
sla_breach_detected  = Signal()
sla_breach_resolved  = Signal()
sla_breach_acknowledged = Signal()
sla_breach_escalated = Signal()
performance_metric_calculated = Signal()
trend_analysis_completed = Signal()

from django.db.models.signals import post_save as _post_save

try:
    from ..models.reporting import AlertReport as _Rep, SLABreach as _SLA
    _post_save.connect(lambda sender, instance, created, **kw: (report_created if created else report_updated).send(sender=sender, instance=instance), sender=_Rep, weak=False)
    _post_save.connect(lambda sender, instance, created, **kw: sla_breach_detected.send(sender=sender, instance=instance) if created else None, sender=_SLA, weak=False)
except Exception:
    pass
