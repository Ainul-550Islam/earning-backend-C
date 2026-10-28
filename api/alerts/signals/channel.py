"""
Channel Signals
"""
from django.conf import settings
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
        if not instance.channel_type:
            instance.channel_type = 'email'
        if not instance.priority:
            instance.priority = 5
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
        valid_types = [c[0] for c in AlertChannel._meta.get_field('channel_type').choices]
        if instance.channel_type not in valid_types:
            logger.warning(f"Invalid channel type '{instance.channel_type}' for AlertChannel {instance.id}")
        valid_statuses = [c[0] for c in AlertChannel._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for AlertChannel {instance.id}")
        if instance.pk:
            try:
                instance._prev_is_enabled = AlertChannel.objects.filter(pk=instance.pk).values_list('is_enabled', flat=True).first()
            except Exception:
                instance._prev_is_enabled = None
        else:
            instance._prev_is_enabled = None
    except Exception as e:
        logger.error(f"Error in alert_channel_pre_save: {e}")


@receiver(post_save, sender=AlertChannel)
def alert_channel_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertChannel"""
    try:
        if created:
            logger.info(f"Created new AlertChannel: {instance.name} ({instance.channel_type})")
            rl, rl_created = ChannelRateLimit.objects.get_or_create(
                channel=instance,
                defaults={
                    'limit_type': 'sliding',
                    'window_seconds': 60,
                    'max_requests': instance.rate_limit_per_minute,
                }
            )
            if rl_created:
                logger.info(f"Created ChannelRateLimit: sliding for {instance.name}")
            try:
                from ..tasks.notification import test_channel
                test_channel.delay(instance.id)
            except Exception:
                pass
        else:
            logger.debug(f"Updated AlertChannel: {instance.name}")
            prev_enabled = getattr(instance, '_prev_is_enabled', None)
            if prev_enabled is not None and prev_enabled != instance.is_enabled:
                from api.alerts.signals.channel import channel_enabled, channel_disabled
                (channel_enabled if instance.is_enabled else channel_disabled).send(
                    sender=sender, instance=instance)
            if instance._state.adding is False:
                ChannelRateLimit.objects.filter(
                    channel=instance
                ).update(max_requests=instance.rate_limit_per_minute)
            # Internal bookkeeping saves (health-check-driven status sync,
            # record_success()/record_failure()) set _skip_health_signal
            # before calling .save() specifically to prevent this handler
            # from re-triggering a health check off the back of its own
            # side effects, which would recurse indefinitely (bounded only
            # by chance on each simulated check).
            if not getattr(instance, '_skip_health_signal', False):
                trigger_channel_health_check(instance)
                trigger_channel_metrics_update(instance)
    except Exception as e:
        logger.error(f"Error in alert_channel_post_save: {e}")


@receiver(pre_save, sender=ChannelRoute)
def channel_route_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ChannelRoute"""
    try:
        if not instance.route_type:
            instance.route_type = 'forward'
        if not instance.priority:
            instance.priority = 5
        # Only set is_active default for new instances, never override existing value
        if instance.pk is None and instance.is_active is None:
            instance.is_active = True
        if not instance.escalation_delay_minutes:
            instance.escalation_delay_minutes = 60
        if not instance.escalate_after_failures:
            instance.escalate_after_failures = 3
        valid_types = [c[0] for c in ChannelRoute._meta.get_field('route_type').choices]
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
        # FIXED: always update routing cache and re-queue pending notifications
        trigger_channel_routing_update(instance)
        from api.alerts.signals.channel import routing_updated
        routing_updated.send(sender=sender, instance=instance)
    except Exception as e:
        logger.error(f"Error in channel_route_post_save: {e}")


@receiver(pre_save, sender=ChannelHealthLog)
def channel_health_log_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ChannelHealthLog"""
    try:
        if not instance.checked_at:
            instance.checked_at = timezone.now()
        if not instance.check_type:
            instance.check_type = 'connectivity'
        if not instance.status:
            instance.status = 'unknown'
        valid_types = [c[0] for c in ChannelHealthLog._meta.get_field('check_type').choices]
        if instance.check_type not in valid_types:
            logger.warning(f"Invalid check type '{instance.check_type}' for ChannelHealthLog {instance.id}")
        valid_statuses = [c[0] for c in ChannelHealthLog._meta.get_field('status').choices]
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
            from api.alerts.signals.channel import health_log_created, channel_failure, channel_recovery, channel_health_checked, channel_health_updated
            health_log_created.send(sender=sender, instance=instance)
            channel_health_checked.send(sender=sender, instance=instance, channel=instance.channel, status=instance.status)
            if instance.status == 'critical':
                instance.channel.status = 'error'
                instance.channel._skip_health_signal = True
                instance.channel.save(update_fields=['status'])
                # FIXED: trigger failure notification when channel goes critical
                trigger_channel_failure_notification(
                    instance.channel,
                    getattr(instance, 'error_message', f"Health check failed: {instance.check_name}")
                )
                channel_failure.send(sender=sender, instance=instance, channel=instance.channel)
                channel_health_updated.send(sender=sender, instance=instance, channel=instance.channel, new_status='error')
            elif instance.status == 'healthy' and instance.channel.status == 'error':
                instance.channel.status = 'active'
                instance.channel._skip_health_signal = True
                instance.channel.save(update_fields=['status'])
                # FIXED: trigger recovery notification when channel recovers
                trigger_channel_recovery_notification(instance.channel)
                channel_recovery.send(sender=sender, instance=instance, channel=instance.channel)
                channel_health_updated.send(sender=sender, instance=instance, channel=instance.channel, new_status='active')
        else:
            logger.debug(f"Updated ChannelHealthLog: {instance.id}")
    except Exception as e:
        logger.error(f"Error in channel_health_log_post_save: {e}")


@receiver(pre_save, sender=ChannelRateLimit)
def channel_rate_limit_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ChannelRateLimit"""
    try:
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
        if instance.current_tokens is None:
            instance.current_tokens = instance.max_requests
        if not instance.last_refill:
            instance.last_refill = timezone.now()
        valid_types = [c[0] for c in ChannelRateLimit._meta.get_field('limit_type').choices]
        if instance.limit_type not in valid_types:
            logger.warning(f"Invalid limit type '{instance.limit_type}' for ChannelRateLimit {instance.id}")
    except Exception as e:
        logger.error(f"Error in channel_rate_limit_pre_save: {e}")


@receiver(post_save, sender=ChannelRateLimit)
def channel_rate_limit_post_save(sender, instance, created, update_fields=None, **kwargs):
    """Signal handler after saving ChannelRateLimit"""
    try:
        if created:
            logger.info(f"Created ChannelRateLimit: {instance.limit_type} for {instance.channel.name}")
            from api.alerts.signals.channel import rate_limit_created
            rate_limit_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated ChannelRateLimit: {instance.id}")
            # Only treat this as a "config changed" event on a FULL save
            # (update_fields=None — e.g. admin/API edits via serializer).
            # Partial saves with update_fields (consume_token, refill_tokens,
            # reset, update_statistics) are routine token bookkeeping and
            # must NOT re-trigger a reset, or they'd be immediately
            # overwritten (and with the old broad check, could recurse).
            if update_fields is None:
                trigger_channel_rate_limit_reset(instance.channel, instance.limit_type)
    except Exception as e:
        logger.error(f"Error in channel_rate_limit_post_save: {e}")


@receiver(pre_save, sender=AlertRecipient)
def alert_recipient_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertRecipient"""
    try:
        if not instance.recipient_type:
            instance.recipient_type = 'user'
        if not instance.priority:
            instance.priority = 'medium'
        # Only default is_active for new instances where it was never set
        if instance.pk is None and instance.is_active is None:
            instance.is_active = True
        if not instance.timezone:
            instance.timezone = 'UTC'
        if not instance.available_days:
            instance.available_days = [0, 1, 2, 3, 4, 5, 6]
        if not instance.max_notifications_per_hour:
            instance.max_notifications_per_hour = 50
        if not instance.max_notifications_per_day:
            instance.max_notifications_per_day = 200
        valid_types = [c[0] for c in AlertRecipient._meta.get_field('recipient_type').choices]
        if instance.recipient_type not in valid_types:
            logger.warning(f"Invalid recipient type '{instance.recipient_type}' for AlertRecipient {instance.id}")
        valid_priorities = [c[0] for c in AlertRecipient._meta.get_field('priority').choices]
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
        # FIXED: refresh availability cache whenever recipient is saved
        trigger_recipient_availability_check(instance)
    except Exception as e:
        logger.error(f"Error in alert_recipient_post_save: {e}")


# ── Helper functions (now called from receivers above) ──────────────────────

def trigger_channel_health_check(channel):
    """Trigger a connectivity health check for the given channel"""
    try:
        logger.info(f"Triggering health check for channel {channel.name}")
        ChannelHealthLog.objects.create(
            channel=channel,
            check_name=f"Health Check - {channel.name}",
            check_type='connectivity',
            status='checking',
            response_time_ms=0
        )
        from ..tasks.notification import check_channel_health
        check_channel_health.delay()
    except Exception as e:
        logger.error(f"Error in trigger_channel_health_check: {e}")


def trigger_channel_rate_limit_reset(channel, limit_type):
    """Reset token bucket and update stats for a rate-limit config change"""
    try:
        logger.info(f"Resetting rate limit for channel {channel.name}, type {limit_type}")
        rate_limit = ChannelRateLimit.objects.get(channel=channel, limit_type=limit_type)
        rate_limit.current_tokens = rate_limit.max_requests
        rate_limit.last_refill = timezone.now()
        rate_limit.save(update_fields=['current_tokens', 'last_refill'])
        from ..tasks.notification import update_notification_statistics
        update_notification_statistics.delay()
    except ChannelRateLimit.DoesNotExist:
        logger.error(f"Rate limit not found for channel {channel.name}, type {limit_type}")
    except Exception as e:
        logger.error(f"Error in trigger_channel_rate_limit_reset: {e}")


def trigger_channel_routing_update(channel_route):
    """Invalidate routing cache and re-process pending notification queue"""
    try:
        logger.info(f"Updating routing for channel route {channel_route.name}")
        from django.core.cache import cache
        cache.delete(f'channel_route_{channel_route.id}')
        from ..tasks.notification import process_notification_queue
        process_notification_queue.delay()
    except Exception as e:
        logger.error(f"Error in trigger_channel_routing_update: {e}")


def trigger_recipient_availability_check(recipient):
    """Refresh recipient availability cache and trigger availability update task"""
    try:
        logger.info(f"Checking availability for recipient {recipient.name}")
        is_available = recipient.is_available_now()
        from django.core.cache import cache
        cache_key = f'recipient_availability_{recipient.id}'
        previous_available = cache.get(cache_key)
        cache.set(cache_key, is_available, timeout=300)
        if previous_available is not None and previous_available != is_available:
            from api.alerts.signals.channel import recipient_availability_changed
            recipient_availability_changed.send(
                sender=recipient.__class__, instance=recipient,
                is_available=is_available, previous=previous_available)
        from ..tasks.notification import update_recipient_availability
        update_recipient_availability.delay()
    except Exception as e:
        logger.error(f"Error in trigger_recipient_availability_check: {e}")


def trigger_channel_failure_notification(channel, error_message):
    """Create an admin failure notification and dispatch it"""
    try:
        logger.warning(f"Channel {channel.name} failed: {error_message}")
        from ..models.core import Notification
        notification = Notification.objects.create(
            notification_type='email',
            recipient=getattr(settings, 'ALERTS_ADMIN_EMAIL', 'admin@example.com'),
            subject=f"Channel Failure: {channel.name}",
            message=f"Channel {channel.name} ({channel.channel_type}) has failed: {error_message}",
            status='pending'
        )
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        return notification
    except Exception as e:
        logger.error(f"Error in trigger_channel_failure_notification: {e}")
        return None


def trigger_channel_recovery_notification(channel):
    """Create an admin recovery notification and dispatch it"""
    try:
        logger.info(f"Channel {channel.name} recovered")
        from ..models.core import Notification
        notification = Notification.objects.create(
            notification_type='email',
            recipient=getattr(settings, 'ALERTS_ADMIN_EMAIL', 'admin@example.com'),
            subject=f"Channel Recovery: {channel.name}",
            message=f"Channel {channel.name} ({channel.channel_type}) has recovered and is now active",
            status='pending'
        )
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        return notification
    except Exception as e:
        logger.error(f"Error in trigger_channel_recovery_notification: {e}")
        return None


def trigger_channel_metrics_update(channel):
    """Update notification statistics and regenerate channel report"""
    try:
        logger.info(f"Updating metrics for channel {channel.name}")
        from ..tasks.notification import update_notification_statistics
        update_notification_statistics.delay()
        from ..tasks.notification import generate_notification_report
        generate_notification_report.delay()
    except Exception as e:
        logger.error(f"Error in trigger_channel_metrics_update: {e}")


def register_channel_signals():
    """Register all channel signals"""
    try:
        logger.info("Channel signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering channel signals: {e}")


register_channel_signals()


from django.dispatch import Signal

channel_created          = Signal()
channel_updated          = Signal()
channel_enabled          = Signal()
channel_disabled         = Signal()
channel_health_checked   = Signal()
channel_failure          = Signal()
channel_recovery         = Signal()
channel_test_sent        = Signal()
channel_health_updated   = Signal()
route_created            = Signal()
route_updated            = Signal()
health_log_created       = Signal()
rate_limit_created       = Signal()
recipient_created        = Signal()
recipient_updated        = Signal()
rate_limit_reset         = Signal()
routing_updated          = Signal()
recipient_availability_changed = Signal()

from django.db.models.signals import post_save as _post_save

try:
    from ..models.channel import AlertChannel as _AC, ChannelRoute as _CR, AlertRecipient as _ARec
    _post_save.connect(lambda sender, instance, created, **kw: (channel_created if created else channel_updated).send(sender=sender, instance=instance), sender=_AC, weak=False)
    _post_save.connect(lambda sender, instance, created, **kw: (route_created if created else route_updated).send(sender=sender, instance=instance), sender=_CR, weak=False)
    _post_save.connect(lambda sender, instance, created, **kw: (recipient_created if created else recipient_updated).send(sender=sender, instance=instance), sender=_ARec, weak=False)
except Exception:
    pass
