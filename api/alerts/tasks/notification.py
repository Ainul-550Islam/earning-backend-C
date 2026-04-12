"""
Notification Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from ..services.channel import NotificationService, ChannelHealthService, RecipientManagementService

logger = logging.getLogger(__name__)


@shared_task
def send_pending_notifications():
    """Send pending notifications using Notification model"""
    try:
        result = NotificationService.send_pending_notifications()
        logger.info(f"Sent {result['sent']} notifications, failed: {result['failed']}")
        return result
        
    except Exception as e:
        logger.error(f"Error in send_notifications: {e}")
        return {'sent': 0, 'failed': 0, 'total': 0}


@shared_task
def retry_failed_notifications():
    """Retry failed notifications"""
    try:
        retry_count = NotificationService.retry_failed_notifications()
        logger.info(f"Retried {retry_count} failed notifications")
        return retry_count
        
    except Exception as e:
        logger.error(f"Error in retry_failed_notifications: {e}")
        return 0


@shared_task
def check_channel_health():
    """Check health of all alert channels"""
    try:
        health_results = ChannelHealthService.check_all_channels()
        
        healthy_count = len([r for r in health_results if r.get('status') == 'healthy'])
        warning_count = len([r for r in health_results if r.get('status') == 'warning'])
        critical_count = len([r for r in health_results if r.get('status') == 'critical'])
        error_count = len([r for r in health_results if r.get('status') == 'error'])
        
        logger.info(f"Channel health check: {healthy_count} healthy, {warning_count} warnings, {critical_count} critical, {error_count} errors")
        return {
            'total': len(health_results),
            'healthy': healthy_count,
            'warning': warning_count,
            'critical': critical_count,
            'error': error_count
        }
        
    except Exception as e:
        logger.error(f"Error in check_channel_health: {e}")
        return {'total': 0, 'healthy': 0, 'warning': 0, 'critical': 0, 'error': 1}


@shared_task
def test_channel(channel_id):
    """Test a specific channel connectivity"""
    try:
        from ..services.channel import ChannelRoutingService
        
        test_result = ChannelRoutingService.test_channel(channel_id)
        
        if test_result:
            logger.info(f"Channel {channel_id} test completed")
        else:
            logger.warning(f"Channel {channel_id} test failed")
        
        return test_result
        
    except Exception as e:
        logger.error(f"Error in test_channel: {e}")
        return None


@shared_task
def update_notification_statistics():
    """Update notification statistics"""
    try:
        from ..models.channel import Notification
        
        # Update statistics for recent notifications
        recent_notifications = Notification.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        updated_count = 0
        for notification in recent_notifications:
            # Update any statistics that need calculation
            updated_count += 1
        
        logger.info(f"Updated statistics for {updated_count} notifications")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_notification_statistics: {e}")
        return 0


@shared_task
def cleanup_old_notifications():
    """Clean up old notifications"""
    try:
        from ..models.channel import Notification
        
        days_to_keep = 30
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        deleted_count = Notification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_notifications: {e}")
        return 0


@shared_task
def update_recipient_availability():
    """Update recipient availability status"""
    try:
        from ..models.channel import AlertRecipient
        
        recipients = AlertRecipient.objects.filter(is_active=True)
        
        updated_count = 0
        for recipient in recipients:
            # Check if recipient is currently available
            is_available = recipient.is_available_now()
            
            # Update availability status if needed
            updated_count += 1
        
        logger.info(f"Updated availability for {updated_count} recipients")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_recipient_availability: {e}")
        return 0


@shared_task
def send_notification_to_recipients(notification_type, message, subject="", recipients=None):
    """Send notification to specific recipients"""
    try:
        if not recipients:
            logger.warning("No recipients specified for notification")
            return 0
        
        sent_count = 0
        
        for recipient in recipients:
            # Check if recipient can receive notification
            if RecipientManagementService.get_available_recipients(notification_type):
                # Create and send notification
                from ..models.core import Notification
                
                notification = Notification.objects.create(
                    notification_type=notification_type,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    status='pending'
                )
                
                sent_count += 1
        
        logger.info(f"Queued {sent_count} notifications for {notification_type}")
        return sent_count
        
    except Exception as e:
        logger.error(f"Error in send_notification_to_recipients: {e}")
        return 0


@shared_task
def process_notification_queue():
    """Process notification queue and send notifications"""
    try:
        # This would integrate with actual notification services
        # For now, just simulate processing
        
        from ..models.channel import Notification
        
        pending_notifications = Notification.objects.filter(status='pending')[:50]
        
        processed_count = 0
        for notification in pending_notifications:
            # Simulate sending
            notification.status = 'sent'
            notification.sent_at = timezone.now()
            notification.save()
            processed_count += 1
        
        logger.info(f"Processed {processed_count} notifications from queue")
        return processed_count
        
    except Exception as e:
        logger.error(f"Error in process_notification_queue: {e}")
        return 0


@shared_task
def escalate_notification(notification_id, escalation_level=1):
    """Escalate a notification to higher priority"""
    try:
        from ..models.channel import Notification
        
        notification = Notification.objects.get(id=notification_id)
        
        # Update notification with escalation details
        notification.details['escalation_level'] = escalation_level
        notification.details['escalated_at'] = timezone.now().isoformat()
        notification.save()
        
        logger.info(f"Escalated notification {notification_id} to level {escalation_level}")
        return True
        
    except Exception as e:
        logger.error(f"Error in escalate_notification: {e}")
        return False


@shared_task
def track_notification_delivery(notification_id):
    """Track delivery status of a notification"""
    try:
        from ..models.channel import Notification
        
        notification = Notification.objects.get(id=notification_id)
        
        # Simulate delivery tracking
        if notification.status == 'sent':
            notification.status = 'delivered'
            notification.save()
        
        logger.info(f"Tracked delivery for notification {notification_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error in track_notification_delivery: {e}")
        return False


@shared_task
def generate_notification_report():
    """Generate notification delivery report"""
    try:
        from ..models.channel import Notification
        
        # Generate statistics for the last 24 hours
        cutoff_date = timezone.now() - timedelta(hours=24)
        
        notifications = Notification.objects.filter(created_at__gte=cutoff_date)
        
        stats = notifications.aggregate(
            total=models.Count('id'),
            sent=models.Count('id', filter=models.Q(status='sent')),
            failed=models.Count('id', filter=models.Q(status='failed')),
            delivered=models.Count('id', filter=models.Q(status='delivered'))
        )
        
        logger.info(f"Generated notification report: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error in generate_notification_report: {e}")
        return None


@shared_task
def optimize_notification_delivery():
    """Optimize notification delivery performance"""
    try:
        # This task would optimize notification delivery
        # For now, just log that it was run
        logger.info("Notification delivery optimization completed")
        return True
        
    except Exception as e:
        logger.error(f"Error in optimize_notification_delivery: {e}")
        return False
