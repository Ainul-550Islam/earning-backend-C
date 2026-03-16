from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

from .services import (
    AlertProcessorService,
    NotificationService,
    AnalyticsService,
    AlertGroupService
)
from .models import SystemHealthCheck, AlertSuppression


@shared_task
def process_pending_alerts():
    """তোমার AlertLog এবং AlertRule models ব্যবহার করে alerts process"""
    try:
        # তোমার AlertRule active manager ব্যবহার
        active_rules = AlertRule.active.get_cached_active_rules()
        
        processed_count = 0
        
        for rule in active_rules:
            # তোমার AlertRule method ব্যবহার করে check
            if rule.can_trigger_now():
                # Simulate checking for alerts (in real app, would check metrics)
                # তোমার AlertProcessorService ব্যবহার
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
        
    except Exception as e:
        logger.error(f"Error in process_pending_alerts: {e}")
        return 0


@shared_task
def send_notifications():
    """তোমার Notification model এর notifications send"""
    try:
        result = NotificationService.send_pending_notifications()
        logger.info(f"Sent {result['sent']} notifications, failed: {result['failed']}")
        return result
        
    except Exception as e:
        logger.error(f"Error in send_notifications: {e}")
        return {'sent': 0, 'failed': 0, 'total': 0}


@shared_task
def escalate_alerts():
    """তোমার AlertEscalation model ব্যবহার করে alerts escalate"""
    try:
        escalated_count = AlertProcessorService.check_and_escalate_alerts()
        logger.info(f"Escalated {escalated_count} alerts")
        return escalated_count
        
    except Exception as e:
        logger.error(f"Error in escalate_alerts: {e}")
        return 0


@shared_task
def check_system_health():
    """তোমার SystemHealthCheck model health checks"""
    try:
        # তোমার SystemHealthCheck class method ব্যবহার
        checks_needed = SystemHealthCheck.get_checks_needed()
        
        checked_count = 0
        failed_count = 0
        
        for check in checks_needed:
            try:
                # তোমার SystemHealthCheck method ব্যবহার
                success = check.update_status(
                    response_time=50,  # Simulated response time
                    success=True,
                    message="Check completed successfully"
                )
                
                checked_count += 1
                
                if not success:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error checking {check.check_name}: {e}")
                failed_count += 1
        
        logger.info(f"Checked {checked_count} health checks, failed: {failed_count}")
        return {'checked': checked_count, 'failed': failed_count}
        
    except Exception as e:
        logger.error(f"Error in check_system_health: {e}")
        return {'checked': 0, 'failed': 0}


@shared_task
def generate_daily_analytics():
    """তোমার AlertAnalytics model generate"""
    try:
        yesterday = timezone.now().date() - timedelta(days=1)
        analytics = AnalyticsService.generate_daily_analytics(yesterday)
        
        if analytics:
            logger.info(f"Generated analytics for {yesterday}")
            return analytics.id
        else:
            logger.warning(f"Failed to generate analytics for {yesterday}")
            return None
            
    except Exception as e:
        logger.error(f"Error in generate_daily_analytics: {e}")
        return None


@shared_task
def send_group_alerts():
    """তোমার AlertGroup model থেকে group alerts send"""
    try:
        alerts_sent = AlertGroupService.check_and_send_group_alerts()
        logger.info(f"Sent {alerts_sent} group alerts")
        return alerts_sent
        
    except Exception as e:
        logger.error(f"Error in send_group_alerts: {e}")
        return 0


@shared_task
def cleanup_old_data():
    """তোমার models থেকে old data cleanup"""
    try:
        days_to_keep = 90
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # তোমার AlertLog model থেকে old data delete
        deleted_alerts = AlertLog.objects.filter(
            triggered_at__lt=cutoff_date,
            is_resolved=True
        ).delete()
        
        # তোমার Notification model থেকে old data delete
        deleted_notifications = Notification.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['sent', 'delivered', 'read']
        ).delete()
        
        logger.info(f"Cleaned up {deleted_alerts[0]} alerts and {deleted_notifications[0]} notifications")
        return {
            'alerts_deleted': deleted_alerts[0],
            'notifications_deleted': deleted_notifications[0]
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_data: {e}")
        return {'alerts_deleted': 0, 'notifications_deleted': 0}


@shared_task
def update_alert_group_caches():
    """তোমার AlertGroup model caches update"""
    try:
        groups = AlertGroup.objects.filter(is_active=True)
        
        updated_count = 0
        
        for group in groups:
            # তোমার AlertGroup method ব্যবহার
            if group.update_cache():
                updated_count += 1
        
        logger.info(f"Updated cache for {updated_count} alert groups")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_alert_group_caches: {e}")
        return 0


@shared_task
def expire_suppressions():
    """তোমার AlertSuppression model থেকে expired suppressions deactivate"""
    try:
        expired_suppressions = AlertSuppression.objects.filter(
            is_active=True,
            end_time__lt=timezone.now()
        )
        
        count = expired_suppressions.update(is_active=False)
        logger.info(f"Deactivated {count} expired suppressions")
        return count
        
    except Exception as e:
        logger.error(f"Error in expire_suppressions: {e}")
        return 0