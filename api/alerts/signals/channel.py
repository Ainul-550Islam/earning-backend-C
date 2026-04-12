"""
Channel Signals
"""
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog, 
    ChannelRateLimit, AlertRecipient
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=AlertChannel)
def alert_channel_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertChannel"""
    try:
        # Set default values if not provided
        if not instance.channel_type:
            instance.channel_type = 'email'
        
        if not instance.priority:
            instance.priority = 5  # Medium priority default
        
        if not instance.rate_limit_per_minute:
            instance.rate_limit_per_minute = 10
        
        if not instance.rate_limit_per_hour:
            instance.rate_limit_per_hour = 100
        
        if not instance.rate_limit_per_day:
            instance.rate_limit_per_day = 1000
        
        if not instance.max_retries:
            instance.max_retries = 3
        
        if not instance.retry_delay_minutes:
            instance.retry_delay_minutes = 5
        
        if not instance.status:
            instance.status = 'active'
        
        # Validate channel type
        valid_types = ['email', 'sms', 'telegram', 'webhook', 'slack', 'discord', 'pagerduty', 'opsgenie']
        if instance.channel_type not in valid_types:
            logger.warning(f"Invalid channel type '{instance.channel_type}' for AlertChannel {instance.id}")
        
        # Validate status
        valid_statuses = ['active', 'inactive', 'error', 'maintenance']
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for AlertChannel {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in alert_channel_pre_save: {e}")


@receiver(post_save, sender=AlertChannel)
def alert_channel_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertChannel"""
    try:
        if created:
            logger.info(f"Created new AlertChannel: {instance.name} ({instance.channel_type})")
            
            # Create rate limit configuration
            ChannelRateLimit.objects.create(
                channel=instance,
                limit_type='per_minute',
                window_seconds=60,
                max_requests=instance.rate_limit_per_minute
            )
            
            ChannelRateLimit.objects.create(
                channel=instance,
                limit_type='per_hour',
                window_seconds=3600,
                max_requests=instance.rate_limit_per_hour
            )
            
            ChannelRateLimit.objects.create(
                channel=instance,
                limit_type='per_day',
                window_seconds=86400,
                max_requests=instance.rate_limit_per_day
            )
            
            # Initial health check
            from ..tasks.notification import test_channel
            test_channel.delay(instance.id)
            
        else:
            logger.debug(f"Updated AlertChannel: {instance.name}")
            
            # Update rate limits if changed
            if instance._state.adding is False:  # This is an update
                ChannelRateLimit.objects.filter(
                    channel=instance,
                    limit_type='per_minute'
                ).update(max_requests=instance.rate_limit_per_minute)
                
                ChannelRateLimit.objects.filter(
                    channel=instance,
                    limit_type='per_hour'
                ).update(max_requests=instance.rate_limit_per_hour)
                
                ChannelRateLimit.objects.filter(
                    channel=instance,
                    limit_type='per_day'
                ).update(max_requests=instance.rate_limit_per_day)
            
    except Exception as e:
        logger.error(f"Error in alert_channel_post_save: {e}")


@receiver(pre_save, sender=ChannelRoute)
def channel_route_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ChannelRoute"""
    try:
        # Set default values if not provided
        if not instance.route_type:
            instance.route_type = 'forward'
        
        if not instance.priority:
            instance.priority = 5  # Medium priority default
        
        if not instance.is_active:
            instance.is_active = True
        
        if not instance.escalation_delay_minutes:
            instance.escalation_delay_minutes = 60
        
        if not instance.escalate_after_failures:
            instance.escalate_after_failures = 3
        
        # Validate route type
        valid_types = ['forward', 'broadcast', 'round_robin', 'failover', 'conditional']
        if instance.route_type not in valid_types:
            logger.warning(f"Invalid route type '{instance.route_type}' for ChannelRoute {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in channel_route_pre_save: {e}")


@receiver(post_save, sender=ChannelRoute)
def channel_route_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ChannelRoute"""
    try:
        if created:
            logger.info(f"Created new ChannelRoute: {instance.name} ({instance.route_type})")
        else:
            logger.debug(f"Updated ChannelRoute: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in channel_route_post_save: {e}")


@receiver(pre_save, sender=ChannelHealthLog)
def channel_health_log_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ChannelHealthLog"""
    try:
        # Set default values if not provided
        if not instance.checked_at:
            instance.checked_at = timezone.now()
        
        if not instance.check_type:
            instance.check_type = 'connectivity'
        
        if not instance.status:
            instance.status = 'unknown'
        
        # Validate check type
        valid_types = ['connectivity', 'authentication', 'rate_limit', 'configuration', 'performance']
        if instance.check_type not in valid_types:
            logger.warning(f"Invalid check type '{instance.check_type}' for ChannelHealthLog {instance.id}")
        
        # Validate status
        valid_statuses = ['healthy', 'warning', 'critical', 'unknown', 'error']
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for ChannelHealthLog {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in channel_health_log_pre_save: {e}")


@receiver(post_save, sender=ChannelHealthLog)
def channel_health_log_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ChannelHealthLog"""
    try:
        if created:
            logger.info(f"Created ChannelHealthLog: {instance.check_name} - {instance.status}")
            
            # Update channel status based on health check
            if instance.status == 'critical':
                instance.channel.status = 'error'
                instance.channel.save(update_fields=['status'])
            elif instance.status == 'healthy' and instance.channel.status == 'error':
                instance.channel.status = 'active'
                instance.channel.save(update_fields=['status'])
                
        else:
            logger.debug(f"Updated ChannelHealthLog: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in channel_health_log_post_save: {e}")


@receiver(pre_save, sender=ChannelRateLimit)
def channel_rate_limit_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ChannelRateLimit"""
    try:
        # Set default values if not provided
        if not instance.limit_type:
            instance.limit_type = 'per_minute'
        
        if not instance.window_seconds:
            if instance.limit_type == 'per_minute':
                instance.window_seconds = 60
            elif instance.limit_type == 'per_hour':
                instance.window_seconds = 3600
            elif instance.limit_type == 'per_day':
                instance.window_seconds = 86400
        
        if not instance.max_requests:
            instance.max_requests = 10
        
        if not instance.current_tokens:
            instance.current_tokens = instance.max_requests
        
        if not instance.last_refill:
            instance.last_refill = timezone.now()
        
        # Validate limit type
        valid_types = ['per_minute', 'per_hour', 'per_day']
        if instance.limit_type not in valid_types:
            logger.warning(f"Invalid limit type '{instance.limit_type}' for ChannelRateLimit {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in channel_rate_limit_pre_save: {e}")


@receiver(post_save, sender=ChannelRateLimit)
def channel_rate_limit_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ChannelRateLimit"""
    try:
        if created:
            logger.info(f"Created ChannelRateLimit: {instance.limit_type} for {instance.channel.name}")
        else:
            logger.debug(f"Updated ChannelRateLimit: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in channel_rate_limit_post_save: {e}")


@receiver(pre_save, sender=AlertRecipient)
def alert_recipient_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertRecipient"""
    try:
        # Set default values if not provided
        if not instance.recipient_type:
            instance.recipient_type = 'user'
        
        if not instance.priority:
            instance.priority = 3  # Medium priority default
        
        if not instance.is_active:
            instance.is_active = True
        
        if not instance.timezone:
            instance.timezone = 'UTC'
        
        if not instance.available_days:
            instance.available_days = [0, 1, 2, 3, 4, 5, 6]  # All days
        
        if not instance.available_hours_start:
            instance.available_hours_start = '09:00'
        
        if not instance.available_hours_end:
            instance.available_hours_end = '17:00'
        
        if not instance.max_notifications_per_hour:
            instance.max_notifications_per_hour = 50
        
        if not instance.max_notifications_per_day:
            instance.max_notifications_per_day = 200
        
        # Validate recipient type
        valid_types = ['user', 'group', 'team', 'service', 'external']
        if instance.recipient_type not in valid_types:
            logger.warning(f"Invalid recipient type '{instance.recipient_type}' for AlertRecipient {instance.id}")
        
        # Validate priority
        valid_priorities = [1, 2, 3, 4, 5]
        if instance.priority not in valid_priorities:
            logger.warning(f"Invalid priority '{instance.priority}' for AlertRecipient {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in alert_recipient_pre_save: {e}")


@receiver(post_save, sender=AlertRecipient)
def alert_recipient_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertRecipient"""
    try:
        if created:
            logger.info(f"Created new AlertRecipient: {instance.name} ({instance.recipient_type})")
        else:
            logger.debug(f"Updated AlertRecipient: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in alert_recipient_post_save: {e}")


# Custom signal handlers for channel business logic
def trigger_channel_health_check(channel):
    """Custom function to trigger channel health check"""
    try:
        logger.info(f"Triggering health check for channel {channel.name}")
        
        # Create health check record
        ChannelHealthLog.objects.create(
            channel=channel,
            check_name=f"Health Check - {channel.name}",
            check_type='connectivity',
            status='checking',
            response_time_ms=0
        )
        
        # Trigger health check task
        from ..tasks.notification import check_channel_health
        check_channel_health.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_channel_health_check: {e}")


def trigger_channel_rate_limit_reset(channel, limit_type):
    """Custom function to trigger channel rate limit reset"""
    try:
        logger.info(f"Resetting rate limit for channel {channel.name}, type {limit_type}")
        
        rate_limit = ChannelRateLimit.objects.get(channel=channel, limit_type=limit_type)
        rate_limit.current_tokens = rate_limit.max_requests
        rate_limit.last_refill = timezone.now()
        rate_limit.save(update_fields=['current_tokens', 'last_refill'])
        
    except ChannelRateLimit.DoesNotExist:
        logger.error(f"Rate limit not found for channel {channel.name}, type {limit_type}")
    except Exception as e:
        logger.error(f"Error in trigger_channel_rate_limit_reset: {e}")


def trigger_channel_routing_update(channel_route):
    """Custom function to trigger channel routing update"""
    try:
        logger.info(f"Updating routing for channel route {channel_route.name}")
        
        # Update routing cache
        from django.core.cache import cache
        cache.delete(f'channel_route_{channel_route.id}')
        
        # Trigger notification queue processing
        from ..tasks.notification import process_notification_queue
        process_notification_queue.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_channel_routing_update: {e}")


def trigger_recipient_availability_check(recipient):
    """Custom function to trigger recipient availability check"""
    try:
        logger.info(f"Checking availability for recipient {recipient.name}")
        
        # Update recipient availability status
        is_available = recipient.is_available_now()
        
        # Update availability in cache
        from django.core.cache import cache
        cache.set(f'recipient_availability_{recipient.id}', is_available, timeout=300)  # 5 minutes
        
        # Trigger recipient availability update task
        from ..tasks.notification import update_recipient_availability
        update_recipient_availability.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_recipient_availability_check: {e}")


def trigger_channel_failure_notification(channel, error_message):
    """Custom function to trigger channel failure notification"""
    try:
        logger.warning(f"Channel {channel.name} failed: {error_message}")
        
        # Create failure notification
        from ..models.core import Notification
        
        notification = Notification.objects.create(
            notification_type='email',
            recipient="admin",  # Would be resolved by routing
            subject=f"Channel Failure: {channel.name}",
            message=f"Channel {channel.name} ({channel.channel_type}) has failed: {error_message}",
            status='pending'
        )
        
        # Trigger notification sending
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        
        return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_channel_failure_notification: {e}")
        return None


def trigger_channel_recovery_notification(channel):
    """Custom function to trigger channel recovery notification"""
    try:
        logger.info(f"Channel {channel.name} recovered")
        
        # Create recovery notification
        from ..models.core import Notification
        
        notification = Notification.objects.create(
            notification_type='email',
            recipient="admin",  # Would be resolved by routing
            subject=f"Channel Recovery: {channel.name}",
            message=f"Channel {channel.name} ({channel.channel_type}) has recovered and is now active",
            status='pending'
        )
        
        # Trigger notification sending
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        
        return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_channel_recovery_notification: {e}")
        return None


def trigger_channel_metrics_update(channel):
    """Custom function to trigger channel metrics update"""
    try:
        logger.info(f"Updating metrics for channel {channel.name}")
        
        # Update channel statistics
        from ..tasks.notification import update_notification_statistics
        update_notification_statistics.delay()
        
        # Generate channel performance report
        from ..tasks.notification import generate_notification_report
        generate_notification_report.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_channel_metrics_update: {e}")


# Signal registration
def register_channel_signals():
    """Register all channel signals"""
    try:
        logger.info("Channel signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering channel signals: {e}")


# Auto-register signals when module is imported
register_channel_signals()
