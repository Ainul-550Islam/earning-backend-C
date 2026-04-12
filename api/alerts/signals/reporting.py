"""
Reporting Signals
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
        # Set default values if not provided
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
        
        # Validate report type
        valid_types = ['daily', 'weekly', 'monthly', 'quarterly', 'custom', 'sla', 'performance', 'trend']
        if instance.report_type not in valid_types:
            logger.warning(f"Invalid report type '{instance.report_type}' for AlertReport {instance.id}")
        
        # Validate status
        valid_statuses = ['pending', 'generating', 'completed', 'failed', 'scheduled']
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for AlertReport {instance.id}")
        
        # Validate format type
        valid_formats = ['json', 'pdf', 'csv', 'html']
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
            
            # Trigger report generation
            from ..tasks.reporting import generate_custom_report
            generate_custom_report.delay(instance.id)
            
        else:
            logger.debug(f"Updated AlertReport: {instance.title}")
            
            # Regenerate if configuration changed
            if instance.status == 'pending':
                from ..tasks.reporting import generate_custom_report
                generate_custom_report.delay(instance.id)
            
            # Schedule next run if recurring
            if instance.is_recurring and not instance.next_run:
                from ..tasks.reporting import schedule_recurring_reports
                schedule_recurring_reports.delay()
            
            # Distribute if completed and auto-distribute is enabled
            if instance.status == 'completed' and instance.auto_distribute:
                from ..tasks.reporting import distribute_reports
                distribute_reports.delay()
            
    except Exception as e:
        logger.error(f"Error in alert_report_post_save: {e}")


@receiver(pre_save, sender=MTTRMetric)
def mttr_metric_pre_save(sender, instance, **kwargs):
    """Signal handler before saving MTTRMetric"""
    try:
        # Set default values if not provided
        if not instance.calculation_period_days:
            instance.calculation_period_days = 30
        
        if not instance.target_mttr_minutes:
            instance.target_mttr_minutes = 60  # 1 hour default
        
        # Validate calculation period
        if not 1 <= instance.calculation_period_days <= 365:
            logger.warning(f"Invalid calculation period '{instance.calculation_period_days}' for MTTRMetric {instance.id}")
        
        # Validate target MTTR
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
            
            # Trigger MTTR calculation
            from ..tasks.reporting import calculate_mttr_metrics
            calculate_mttr_metrics.delay()
            
        else:
            logger.debug(f"Updated MTTRMetric: {instance.name}")
            
            # Recalculate if configuration changed
            from ..tasks.reporting import calculate_mttr_metrics
            calculate_mttr_metrics.delay()
            
    except Exception as e:
        logger.error(f"Error in mttr_metric_post_save: {e}")


@receiver(pre_save, sender=MTTDMetric)
def mttd_metric_pre_save(sender, instance, **kwargs):
    """Signal handler before saving MTTDMetric"""
    try:
        # Set default values if not provided
        if not instance.calculation_period_days:
            instance.calculation_period_days = 30
        
        if not instance.target_mttd_minutes:
            instance.target_mttd_minutes = 15  # 15 minutes default
        
        # Validate calculation period
        if not 1 <= instance.calculation_period_days <= 365:
            logger.warning(f"Invalid calculation period '{instance.calculation_period_days}' for MTTDMetric {instance.id}")
        
        # Validate target MTTD
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
            
            # Trigger MTTD calculation
            from ..tasks.reporting import calculate_mttd_metrics
            calculate_mttd_metrics.delay()
            
        else:
            logger.debug(f"Updated MTTDMetric: {instance.name}")
            
            # Recalculate if configuration changed
            from ..tasks.reporting import calculate_mttd_metrics
            calculate_mttd_metrics.delay()
            
    except Exception as e:
        logger.error(f"Error in mttd_metric_post_save: {e}")


@receiver(pre_save, sender=SLABreach)
def sla_breach_pre_save(sender, instance, **kwargs):
    """Signal handler before saving SLABreach"""
    try:
        # Set default values if not provided
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
        
        # Validate SLA type
        valid_types = ['resolution_time', 'response_time', 'detection_time', 'availability', 'custom']
        if instance.sla_type not in valid_types:
            logger.warning(f"Invalid SLA type '{instance.sla_type}' for SLABreach {instance.id}")
        
        # Validate severity
        valid_severities = ['low', 'medium', 'high', 'critical']
        if instance.severity not in valid_severities:
            logger.warning(f"Invalid severity '{instance.severity}' for SLABreach {instance.id}")
        
        # Validate status
        valid_statuses = ['active', 'resolved', 'escalated', 'acknowledged']
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
            
            # Trigger SLA breach notification
            from ..tasks.notification import send_notification_to_recipients
            send_notification_to_recipients.delay(
                notification_type='email',
                message=f"SLA Breach Detected: {instance.name}",
                subject=f"SLA Breach Alert: {instance.sla_type}"
            )
            
            # Trigger escalation if critical
            if instance.severity == 'critical':
                from ..tasks.incident import check_incident_escalations
                check_incident_escalations.delay()
                
        else:
            logger.debug(f"Updated SLABreach: {instance.name}")
            
            # Trigger escalation if status changed to escalated
            if instance.status == 'escalated':
                from ..tasks.notification import escalate_notification
                escalate_notification.delay(instance.id, instance.escalation_level)
            
    except Exception as e:
        logger.error(f"Error in sla_breach_post_save: {e}")


# Custom signal handlers for reporting business logic
def trigger_sla_breach_check(alert_log):
    """Custom function to check for SLA breaches on alert resolution"""
    try:
        if alert_log.is_resolved and alert_log.resolved_at:
            # Check if resolution time exceeds SLA
            resolution_time = (alert_log.resolved_at - alert_log.triggered_at).total_seconds() / 60
            
            # Default SLA thresholds by severity
            sla_thresholds = {
                'critical': 60,   # 1 hour
                'high': 120,      # 2 hours
                'medium': 240,    # 4 hours
                'low': 480        # 8 hours
            }
            
            threshold = sla_thresholds.get(alert_log.rule.severity, 240)
            
            if resolution_time > threshold:
                # Create SLA breach record
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
                
                # Trigger SLA breach notification
                from ..tasks.notification import send_notification_to_recipients
                send_notification_to_recipients.delay(
                    notification_type='email',
                    message=f"SLA Breach: {breach.name}",
                    subject=f"SLA Breach Alert: {alert_log.rule.severity}"
                )
                
    except Exception as e:
        logger.error(f"Error in trigger_sla_breach_check: {e}")


def trigger_mttr_calculation():
    """Custom function to trigger MTTR calculation"""
    try:
        logger.info("Triggering MTTR calculation")
        
        # Calculate MTTR for all configured metrics
        from ..tasks.reporting import calculate_mttr_metrics
        calculate_mttr_metrics.delay()
        
        # Generate performance report
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_mttr_calculation: {e}")


def trigger_mttd_calculation():
    """Custom function to trigger MTTD calculation"""
    try:
        logger.info("Triggering MTTD calculation")
        
        # Calculate MTTD for all configured metrics
        from ..tasks.reporting import calculate_mttd_metrics
        calculate_mttd_metrics.delay()
        
        # Generate performance report
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_mttd_calculation: {e}")


def trigger_sla_report_generation():
    """Custom function to trigger SLA report generation"""
    try:
        logger.info("Triggering SLA report generation")
        
        # Generate SLA reports
        from ..tasks.reporting import generate_sla_reports
        generate_sla_reports.delay()
        
        # Check for SLA breaches
        from ..tasks.reporting import check_sla_breaches
        check_sla_breaches.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_sla_report_generation: {e}")


def trigger_daily_report_generation():
    """Custom function to trigger daily report generation"""
    try:
        logger.info("Triggering daily report generation")
        
        # Generate daily reports
        from ..tasks.reporting import generate_daily_reports
        generate_daily_reports.delay()
        
        # Update reporting metrics
        from ..tasks.reporting import update_reporting_metrics
        update_reporting_metrics.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_daily_report_generation: {e}")


def trigger_weekly_report_generation():
    """Custom function to trigger weekly report generation"""
    try:
        logger.info("Triggering weekly report generation")
        
        # Generate weekly reports
        from ..tasks.reporting import generate_weekly_reports
        generate_weekly_reports.delay()
        
        # Generate trend analysis
        from ..tasks.reporting import generate_trend_analysis_reports
        generate_trend_analysis_reports.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_weekly_report_generation: {e}")


def trigger_monthly_report_generation():
    """Custom function to trigger monthly report generation"""
    try:
        logger.info("Triggering monthly report generation")
        
        # Generate monthly reports
        from ..tasks.reporting import generate_monthly_reports
        generate_monthly_reports.delay()
        
        # Generate performance analysis
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_monthly_report_generation: {e}")


def trigger_report_distribution(report):
    """Custom function to trigger report distribution"""
    try:
        logger.info(f"Triggering distribution for report {report.title}")
        
        # Distribute report to recipients
        from ..tasks.reporting import distribute_reports
        distribute_reports.delay()
        
        # Create notification for distribution
        from ..models.core import Notification
        
        notification = Notification.objects.create(
            notification_type='email',
            recipient="report_recipients",  # Would be resolved by routing
            subject=f"Report Distributed: {report.title}",
            message=f"Report '{report.title}' has been distributed to recipients",
            status='pending'
        )
        
        # Trigger notification sending
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        
        return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_report_distribution: {e}")
        return None


def trigger_report_cleanup():
    """Custom function to trigger report cleanup"""
    try:
        logger.info("Triggering report cleanup")
        
        # Clean up old reports
        from ..tasks.reporting import cleanup_old_reports
        cleanup_old_reports.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_report_cleanup: {e}")


def trigger_sla_escalation(sla_breach):
    """Custom function to trigger SLA breach escalation"""
    try:
        logger.warning(f"Triggering SLA escalation for breach {sla_breach.name}")
        
        # Create escalation notification
        from ..models.core import Notification
        
        notification = Notification.objects.create(
            notification_type='email',
            recipient="sla_manager",  # Would be resolved by routing
            subject=f"SLA Escalation: {sla_breach.name}",
            message=f"SLA breach requires escalation: {sla_breach.name} - {sla_breach.breach_percentage:.1f}% breach",
            status='pending'
        )
        
        # Trigger notification sending
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        
        return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_sla_escalation: {e}")
        return None


def trigger_metrics_dashboard_update():
    """Custom function to trigger metrics dashboard update"""
    try:
        logger.info("Triggering metrics dashboard update")
        
        # Update all metrics
        mttr_count = trigger_mttr_calculation()
        mttd_count = trigger_mttd_calculation()
        
        # Generate dashboard data
        from ..tasks.reporting import update_reporting_metrics
        update_reporting_metrics.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_metrics_dashboard_update: {e}")


# Signal registration
def register_reporting_signals():
    """Register all reporting signals"""
    try:
        logger.info("Reporting signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering reporting signals: {e}")


# Auto-register signals when module is imported
register_reporting_signals()
