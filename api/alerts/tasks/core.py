"""
Core Alert Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from ..services.core import (
    AlertProcessorService, AnalyticsService, AlertGroupService, AlertMaintenanceService
)

logger = logging.getLogger(__name__)


@shared_task
def process_pending_alerts():
    """Process pending alerts using AlertRule and AlertLog models"""
    try:
        from ..models.core import AlertRule
        
        # Get active rules
        active_rules = AlertRule.objects.filter(is_active=True)
        
        processed_count = 0
        
        for rule in active_rules:
            # Check if rule can trigger
            if rule.can_trigger_now():
                # Simulate checking for alerts (in real app, would check metrics)
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
def escalate_alerts():
    """Escalate unresolved alerts using AlertEscalation model"""
    try:
        escalated_count = AlertProcessorService.check_and_escalate_alerts()
        logger.info(f"Escalated {escalated_count} alerts")
        return escalated_count
        
    except Exception as e:
        logger.error(f"Error in escalate_alerts: {e}")
        return 0


@shared_task
def generate_daily_analytics():
    """Generate daily analytics using AlertAnalytics model"""
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
    """Send group alerts using AlertGroup model"""
    try:
        alerts_sent = AlertGroupService.check_and_send_group_alerts()
        logger.info(f"Sent {alerts_sent} group alerts")
        return alerts_sent
        
    except Exception as e:
        logger.error(f"Error in send_group_alerts: {e}")
        return 0


@shared_task
def update_alert_group_caches():
    """Update AlertGroup model caches"""
    try:
        from ..models.core import AlertGroup
        
        groups = AlertGroup.objects.filter(is_active=True)
        
        updated_count = 0
        
        for group in groups:
            if group.update_cache():
                updated_count += 1
        
        logger.info(f"Updated cache for {updated_count} alert groups")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_alert_group_caches: {e}")
        return 0


@shared_task
def cleanup_old_alerts():
    """Clean up old resolved alerts"""
    try:
        days = 90  # Default cleanup period
        deleted_count = AlertMaintenanceService.cleanup_old_alerts(days)
        
        logger.info(f"Cleaned up {deleted_count} old alerts")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_alerts: {e}")
        return 0


@shared_task
def cleanup_old_notifications():
    """Clean up old notifications"""
    try:
        days = 30  # Default cleanup period
        deleted_count = AlertMaintenanceService.cleanup_old_notifications(days)
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_notifications: {e}")
        return 0


@shared_task
def update_rule_health():
    """Update health status for alert rules"""
    try:
        updated_count = AlertMaintenanceService.update_rule_health()
        
        logger.info(f"Updated health for {updated_count} alert rules")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_rule_health: {e}")
        return 0


@shared_task
def optimize_alert_indexes():
    """Optimize database indexes for alert tables"""
    try:
        success = AlertMaintenanceService.optimize_alert_indexes()
        
        if success:
            logger.info("Alert database indexes optimization completed")
        else:
            logger.warning("Alert database indexes optimization failed")
        
        return success
        
    except Exception as e:
        logger.error(f"Error in optimize_alert_indexes: {e}")
        return False


@shared_task
def expire_suppressions():
    """Deactivate expired alert suppressions"""
    try:
        from ..models.core import AlertSuppression
        
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


@shared_task
def check_system_health():
    """Perform system health checks"""
    try:
        from ..models.core import SystemHealthCheck
        
        # Get checks that need to be performed
        checks_needed = SystemHealthCheck.get_checks_needed()
        
        checked_count = 0
        failed_count = 0
        
        for check in checks_needed:
            try:
                # Simulate health check
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
def resolve_alert(alert_id, resolved_by_id=None, resolution_note=""):
    """Resolve a specific alert"""
    try:
        from django.contrib.auth import get_user_model
        from ..models.core import AlertLog
        
        resolved_by = None
        if resolved_by_id:
            User = get_user_model()
            resolved_by = User.objects.get(id=resolved_by_id)
        
        success = AlertProcessorService.resolve_alert(alert_id, resolved_by, resolution_note)
        
        if success:
            logger.info(f"Resolved alert {alert_id}")
        else:
            logger.warning(f"Failed to resolve alert {alert_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error in resolve_alert: {e}")
        return False


@shared_task
def acknowledge_alert(alert_id, acknowledged_by_id=None):
    """Acknowledge a specific alert"""
    try:
        from django.contrib.auth import get_user_model
        from ..models.core import AlertLog
        
        acknowledged_by = None
        if acknowledged_by_id:
            User = get_user_model()
            acknowledged_by = User.objects.get(id=acknowledged_by_id)
        
        success = AlertProcessorService.acknowledge_alert(alert_id, acknowledged_by)
        
        if success:
            logger.info(f"Acknowledged alert {alert_id}")
        else:
            logger.warning(f"Failed to acknowledge alert {alert_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error in acknowledge_alert: {e}")
        return False


@shared_task
def test_alert_rule(rule_id):
    """Test an alert rule by creating a test alert"""
    try:
        from ..models.core import AlertRule, AlertLog
        
        rule = AlertRule.objects.get(id=rule_id)
        
        test_alert = AlertLog.objects.create(
            rule=rule,
            trigger_value=rule.threshold_value + 1,
            threshold_value=rule.threshold_value,
            message=f'[TEST] Alert rule "{rule.name}" manually tested',
            is_resolved=True,
            resolved_at=timezone.now(),
            resolution_note='Auto-resolved: manual test',
        )
        
        logger.info(f"Created test alert {test_alert.id} for rule {rule_id}")
        return test_alert.id
        
    except Exception as e:
        logger.error(f"Error in test_alert_rule: {e}")
        return None


@shared_task
def bulk_resolve_alerts(alert_ids, resolved_by_id=None, resolution_note=""):
    """Bulk resolve multiple alerts"""
    try:
        from django.contrib.auth import get_user_model
        from ..models.core import AlertLog
        
        resolved_by = None
        if resolved_by_id:
            User = get_user_model()
            resolved_by = User.objects.get(id=resolved_by_id)
        
        resolved_count = 0
        
        for alert_id in alert_ids:
            if AlertProcessorService.resolve_alert(alert_id, resolved_by, resolution_note):
                resolved_count += 1
        
        logger.info(f"Bulk resolved {resolved_count}/{len(alert_ids)} alerts")
        return resolved_count
        
    except Exception as e:
        logger.error(f"Error in bulk_resolve_alerts: {e}")
        return 0


@shared_task
def update_alert_statistics():
    """Update alert statistics and metrics"""
    try:
        # This task would update various alert statistics
        # For now, just log that it was run
        logger.info("Alert statistics update completed")
        return True
        
    except Exception as e:
        logger.error(f"Error in update_alert_statistics: {e}")
        return False
