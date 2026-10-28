# Reconstructed from services/FIX_ALL_PART1_Services1-4.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

from django.db import transaction
from django.utils import timezone
from celery import shared_task
import logging

from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.services.notification import NotificationService

logger = logging.getLogger(__name__)


class AlertProcessingService:
    """
    Consolidates all alert processing logic.
    Eliminates duplicates from: celery_tasks.py + tasks/core.py

    NOTE (corrected after cross-checking the real callers): the version of
    process_pending_alerts() previously here operated on AlertLog rows with
    status='pending' and sent notifications for them. That does not match
    what either celery_tasks.py or tasks/core.py actually does. The REAL
    duplicated logic in both files evaluates active AlertRules and creates
    new AlertLog entries via AlertProcessorService.process_alert() -- it has
    nothing to do with an AlertLog.status='pending' queue. Rewritten below to
    match that real, verified behavior.
    """

    @staticmethod
    def process_pending_alerts():
        """
        Evaluate all active alert rules and process any that can trigger now.

        Previously duplicated in:
        - alerts/celery_tasks.py (used AlertRule.active.get_cached_active_rules())
        - alerts/tasks/core.py (used the plain AlertRule.objects.filter(is_active=True),
          bypassing the cached manager -- the cached version is kept here since it's
          strictly better and behaviorally equivalent)

        Returns:
            int: number of alerts processed (matches both callers' original return type)
        """
        from api.alerts.services.core import LegacyAlertProcessorService as AlertProcessorService

        active_rules = AlertRule.active.get_cached_active_rules()
        processed_count = 0

        for rule in active_rules:
            if rule.can_trigger_now():
                alert = AlertProcessorService.process_alert(
                    rule_id=rule.id,
                    trigger_value=rule.threshold_value * 1.1,  # 10% above threshold
                    message=f"Auto-generated alert for {rule.name}",
                    details={'auto_generated': True}
                )
                if alert:
                    processed_count += 1

        logger.info(f"Processed {processed_count} alerts")
        return processed_count

    @staticmethod
    @transaction.atomic
    def escalate_alerts(alert=None, rule_id=None):
        """
        Escalate alert to next level.
        
        Previously duplicated in:
        - alerts/celery_tasks.py
        - alerts/tasks/core.py
        
        Args:
            alert: AlertLog instance
            rule_id: AlertRule ID
            
        Returns:
            dict: Escalation result
        """
        if alert:
            rule = alert.rule
        else:
            rule = AlertRule.objects.get(id=rule_id)
            alert = None

        logger.info(f"Evaluating escalation for rule {rule.id}")

        if alert is None:
            return {'escalated': False, 'reason': 'no_alert'}

        from api.alerts.models import AlertEscalation

        # Escalate to the next level above the alert's current one
        next_step = AlertEscalation.objects.filter(
            rule=rule, level__gt=alert.escalation_level, is_active=True
        ).order_by('level').first()

        if not next_step:
            return {'escalated': False, 'reason': 'no_escalation_configured'}

        escalated = next_step.escalate_alert(alert)

        if not escalated:
            return {'escalated': False, 'reason': 'not_due_yet'}

        recipients = next_step.get_escalation_recipients()
        message = next_step.render_escalation_message(alert)
        for email in recipients.get('emails', []):
            notification = Notification.objects.create(
                alert_log=alert,
                recipient=email,
                notification_type='escalation',
                message=message,
            )
            NotificationService.send_notification(notification)

        logger.info(f"Alert {alert.id} escalated to level {next_step.level}")
        return {'escalated': True, 'level': next_step.level, 'recipients': len(recipients.get('emails', []))}

    @staticmethod
    @transaction.atomic
    def bulk_resolve_alerts(alert_ids, resolution_notes=''):
        """
        Resolve multiple alerts at once.
        
        Previously duplicated in:
        - alerts/views.py
        - alerts/tasks/core.py
        
        Args:
            alert_ids: list of AlertLog IDs
            resolution_notes: Resolution notes
            
        Returns:
            dict: Resolution result
        """
        logger.info(f"Bulk resolving {len(alert_ids)} alerts")
        
        alerts = AlertLog.objects.filter(id__in=alert_ids)
        resolved_count = 0
        
        for alert in alerts:
            if alert.status != 'resolved':
                alert.status = 'resolved'
                alert.resolved_at = timezone.now()
                alert.resolution_note = resolution_notes
                alert.save(update_fields=['status', 'resolved_at', 'resolution_note'])
                resolved_count += 1
        
        logger.info(f"Bulk resolved {resolved_count} alerts")
        return {
            'resolved': resolved_count,
            'skipped': len(alert_ids) - resolved_count
        }

    @staticmethod
    @transaction.atomic
    def send_group_alerts(group_id, recipients=None):
        """
        Send alerts to a group of recipients.
        
        Previously duplicated in:
        - alerts/celery_tasks.py
        - alerts/tasks/core.py
        
        Args:
            group_id: AlertGroup ID
            recipients: Optional list of recipients (if None, use group's recipients)
            
        Returns:
            dict: Send result
        """
        from api.alerts.models import AlertGroup
        
        logger.info(f"Sending group alerts for group {group_id}")
        
        group = AlertGroup.objects.get(id=group_id)
        
        if recipients is None:
            recipients = group.get_group_recipients()
        
        sent_count = 0
        failed_count = 0
        
        for alert in AlertLog.objects.filter(rule__in=group.rules.all()):
            for recipient in recipients:
                try:
                    notification = Notification.objects.create(
                        alert_log=alert,
                        recipient=recipient,
                        notification_type='group'
                    )
                    NotificationService.send_notification(notification)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send group alert: {str(e)}")
                    failed_count += 1
        
        logger.info(f"Group alerts sent: {sent_count} sent, {failed_count} failed")
        return {
            'sent': sent_count,
            'failed': failed_count
        }

    @staticmethod
    def generate_daily_analytics():
        """
        Generate daily analytics for alerts.
        
        Previously duplicated in:
        - alerts/celery_tasks.py
        - alerts/tasks/core.py
        
        Returns:
            dict: Analytics data
        """
        from django.db.models import Count, Q
        from api.alerts.models import AlertAnalytics
        
        logger.info("Generating daily analytics")
        
        today = timezone.now().date()
        
        # Calculate metrics
        total_alerts = AlertLog.objects.filter(triggered_at__date=today).count()
        resolved_alerts = AlertLog.objects.filter(
            triggered_at__date=today,
            status='resolved'
        ).count()
        failed_alerts = AlertLog.objects.filter(
            triggered_at__date=today,
            status='failed'
        ).count()
        escalated_alerts = AlertLog.objects.filter(
            triggered_at__date=today,
            escalation_level__gt=0
        ).count()
        
        # Group by severity
        by_severity = AlertLog.objects.filter(
            triggered_at__date=today
        ).values('severity').annotate(count=Count('id'))
        
        # Create analytics record
        analytics = AlertAnalytics.objects.create(
            date=today,
            total_alerts=total_alerts,
            resolved_alerts=resolved_alerts,
            escalated_alerts=escalated_alerts,
            avg_response_time_min=AlertProcessingService._calculate_avg_response_time(today)
        )
        
        logger.info(f"Daily analytics generated: {total_alerts} total, {resolved_alerts} resolved")
        
        return {
            'total_alerts': total_alerts,
            'resolved_alerts': resolved_alerts,
            'failed_alerts': failed_alerts,
            'escalated_alerts': escalated_alerts
        }

    @staticmethod
    def _calculate_avg_response_time(date):
        """Calculate average response time for a date"""
        from django.db.models import Avg, F
        from django.utils.timezone import make_aware
        from datetime import timedelta
        
        resolved = AlertLog.objects.filter(
            triggered_at__date=date,
            status='resolved',
            resolved_at__isnull=False
        ).annotate(
            response_time=F('resolved_at') - F('triggered_at')
        ).aggregate(avg=Avg('response_time'))
        
        avg = resolved.get('avg')
        if avg:
            return int(avg.total_seconds() / 60)  # Convert to minutes
        return 0

    @staticmethod
    def should_escalate(alert):
        """Check if alert should be escalated"""
        from api.alerts.models import AlertEscalation

        next_step = AlertEscalation.objects.filter(
            rule=alert.rule, level__gt=alert.escalation_level, is_active=True
        ).order_by('level').first()

        if not next_step:
            return False

        return next_step.should_escalate(alert)

    @staticmethod
    def get_processing_stats():
        """Get alert processing statistics"""
        from django.db.models import Count
        
        stats = {
            'pending': AlertLog.objects.filter(status='pending').count(),
            'processed': AlertLog.objects.filter(status='processed').count(),
            'failed': AlertLog.objects.filter(status='failed').count(),
            'resolved': AlertLog.objects.filter(status='resolved').count(),
        }
        return stats

    @staticmethod
    def retry_failed_alerts():
        """Retry all failed alerts"""
        logger.info("Retrying failed alerts")
        
        failed_alerts = AlertLog.objects.filter(status='failed')
        retried_count = 0
        
        for alert in failed_alerts:
            alert.status = 'pending'
            alert.save(update_fields=['status'])
            retried_count += 1
        
        logger.info(f"Retried {retried_count} alerts")
        return {'retried': retried_count}

    @staticmethod
    def get_processing_history(days=7):
        """Get alert processing history"""
        from django.db.models import Count
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        history = AlertLog.objects.filter(
            triggered_at__gte=start_date
        ).values('triggered_at__date', 'status').annotate(count=Count('id'))
        
        return list(history)


# Export for use in other modules
__all__ = ['AlertProcessingService']
