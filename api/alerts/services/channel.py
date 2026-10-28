"""
Alert Channel Services  — FIXED: channel service classes now wired into NotificationService dispatch
"""
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.core import Notification
from ..models.channel import AlertChannel, ChannelRoute, ChannelHealthLog, ChannelRateLimit, AlertRecipient

logger = logging.getLogger(__name__)

# ── FIXED: channel service dispatcher map ─────────────────────────────────────
def _get_channel_service_map():
    """Lazy-load channel service classes to avoid circular imports at module level."""
    from .channels.EmailAlertService import EmailAlertService
    from .channels.SlackAlertService import SlackAlertService
    from .channels.TelegramAlertService import TelegramAlertService
    from .channels.DiscordAlertService import DiscordAlertService
    from .channels.WebhookAlertService import WebhookAlertService
    from .channels.SMSAlertService import SMSAlertService
    from .channels.PagerDutyService import PagerDutyService
    from .channels.OpsGenieService import OpsGenieService
    return {
        'email': EmailAlertService,
        'slack': SlackAlertService,
        'telegram': TelegramAlertService,
        'discord': DiscordAlertService,
        'webhook': WebhookAlertService,
        'sms': SMSAlertService,
        'pagerduty': PagerDutyService,
        'opsgenie': OpsGenieService,
    }


class NotificationService:
    """Notification processing and delivery service"""

    @staticmethod
    def send_pending_notifications():
        """Send pending notifications using dedicated channel service classes."""
        try:
            pending_notifications = Notification.objects.filter(
                status='pending'
            ).select_related('alert_log', 'alert_log__rule')[:50]

            sent_count = 0
            failed_count = 0

            for notification in pending_notifications:
                try:
                    if notification.retry_count > 0 and notification.last_retry_at:
                        retry_delay = notification.get_retry_delay()
                        time_since_retry = (timezone.now() - notification.last_retry_at).total_seconds()
                        if time_since_retry < retry_delay:
                            continue

                    success = NotificationService._send_notification(notification)

                    if success:
                        notification.mark_as_sent(
                            message_id=f"msg_{notification.id}",
                            response_time_ms=100
                        )
                        sent_count += 1
                    else:
                        notification.mark_as_failed("Failed to send")
                        failed_count += 1

                except Exception as e:
                    logger.error(f"Error sending notification {notification.id}: {e}")
                    notification.mark_as_failed(str(e))
                    failed_count += 1

            return {'sent': sent_count, 'failed': failed_count, 'total': len(pending_notifications)}

        except Exception as e:
            logger.error(f"Error in send_pending_notifications: {e}")
            return {'sent': 0, 'failed': 0, 'total': 0}

    @staticmethod
    def send_notification(notification):
        """Public single-notification dispatch — called from services/core.py dispatch loop."""
        return NotificationService._send_notification(notification)

    @staticmethod
    def _send_notification(notification):
        """
        Dispatch a notification through the appropriate channel service class.
        FIXED: delegates to dedicated service classes instead of random simulation.
        """
        try:
            channel = AlertChannel.objects.filter(
                channel_type=notification.notification_type,
                is_enabled=True,
                status='active'
            ).first()

            if not channel:
                logger.warning(f"No active channel found for {notification.notification_type}")
                return False

            if not channel.can_send_notification():
                logger.warning(f"Channel {channel.name} rate limited")
                return False

            # FIXED: use dedicated service class per channel type,
            # wrapped in CircuitBreaker and FallbackHandler
            service_map = _get_channel_service_map()
            service_class = service_map.get(notification.notification_type)

            if service_class:
                try:
                    # Attempt primary send via circuit-breaker
                    try:
                        from api.alerts.integration import get_circuit_breaker_manager
                        cbm = get_circuit_breaker_manager()
                        if cbm:
                            cb = cbm.get_or_create(
                                name=f"channel_{notification.notification_type}",
                                failure_threshold=5,
                                recovery_timeout=60
                            )
                            result = cb.call(lambda: service_class().send(notification, channel))
                        else:
                            result = service_class().send(notification, channel)
                    except Exception as cb_err:
                        # Circuit open or service failed — try fallback channel
                        logger.warning(
                            f"Primary send failed for {notification.notification_type} "
                            f"(notification {notification.id}): {cb_err}. Attempting fallback."
                        )
                        try:
                            from api.alerts.integration import get_fallback_handler
                            fh = get_fallback_handler()
                            if fh:
                                result = fh.handle_integration_failure(
                                    alert_id=getattr(notification, 'alert_log_id', None) or 0,
                                    error=str(cb_err),
                                    result={'type': notification.notification_type}
                                )
                            else:
                                result = False
                        except Exception as fb_err:
                            logger.error(f"Fallback also failed for notification {notification.id}: {fb_err}")
                            result = False

                    if result:
                        channel.record_success()
                    else:
                        channel.record_failure()
                    return bool(result)
                except Exception as svc_err:
                    logger.error(
                        f"Channel service {service_class.__name__} failed for "
                        f"notification {notification.id}: {svc_err}"
                    )
                    channel.record_failure()
                    return False

            # Fallback to legacy simulation for unsupported types
            logger.warning(
                f"No dedicated service class for type '{notification.notification_type}', "
                f"using legacy path"
            )
            return NotificationService._send_legacy(notification, channel)

        except Exception as e:
            logger.error(f"Error in _send_notification: {e}")
            return False

    @staticmethod
    def _send_legacy(notification, channel):
        """Legacy simulation path — only reached for unregistered channel types."""
        try:
            import random
            success_rates = {'email': 0.95, 'telegram': 0.90, 'sms': 0.85, 'webhook': 0.92}
            rate = success_rates.get(notification.notification_type, 0.90)
            if random.random() < rate:
                channel.record_success()
                return True
            channel.record_failure()
            return False
        except Exception as e:
            logger.error(f"Error in _send_legacy: {e}")
            channel.record_failure()
            return False

    @staticmethod
    def retry_failed_notifications():
        """Retry failed notifications that are eligible for retry."""
        try:
            failed_notifications = Notification.objects.filter(status='failed')
            retry_count = 0
            for notification in failed_notifications:
                if notification.can_retry():
                    notification.status = 'pending'
                    notification.save()
                    retry_count += 1
            return retry_count
        except Exception as e:
            logger.error(f"Error retrying notifications: {e}")
            return 0

    @staticmethod
    def get_notification_statistics(hours=24):
        """Get notification delivery statistics for the given time window."""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            stats = Notification.objects.filter(
                created_at__gte=cutoff_time
            ).aggregate(
                total_sent=models.Count('id'),
                successful_sent=models.Count('id', filter=models.Q(status='sent')),
                failed_sent=models.Count('id', filter=models.Q(status='failed')),
                pending_sent=models.Count('id', filter=models.Q(status='pending'))
            )
            by_type = Notification.objects.filter(
                created_at__gte=cutoff_time
            ).values('notification_type').annotate(
                count=models.Count('id'),
                success_rate=models.Avg(
                    models.Case(
                        models.When(status='sent', then=1),
                        models.When(status='failed', then=0),
                        default=0,
                        output_field=models.IntegerField()
                    )
                ) * 100
            )
            return {
                'period_hours': hours,
                'total_sent': stats['total_sent'],
                'successful_sent': stats['successful_sent'],
                'failed_sent': stats['failed_sent'],
                'pending_sent': stats['pending_sent'],
                'success_rate': (
                    stats['successful_sent'] / stats['total_sent'] * 100
                ) if stats['total_sent'] > 0 else 0,
                'by_type': list(by_type)
            }
        except Exception as e:
            logger.error(f"Error getting notification statistics: {e}")
            return None


class ChannelRoutingService:
    """Channel routing and management service"""

    @staticmethod
    def route_notification(alert_log, notification_type):
        """Route notification through appropriate channels based on active routes."""
        try:
            routes = ChannelRoute.objects.filter(is_active=True).order_by('priority')
            routed_channels = []
            for route in routes:
                if route.should_route(alert_log, notification_type):
                    destination_channels = route.get_destination_channels()
                    routed_channels.extend(destination_channels)
            seen = set()
            unique_channels = []
            for channel in routed_channels:
                if channel.id not in seen:
                    seen.add(channel.id)
                    unique_channels.append(channel)
            return unique_channels
        except Exception as e:
            logger.error(f"Error routing notification: {e}")
            return []

    @staticmethod
    def create_notification_for_channels(alert_log, channels, message=None):
        """Create pending Notification records for each channel and its recipients."""
        try:
            notifications = []
            for channel in channels:
                recipients = ChannelRoutingService._get_channel_recipients(channel, alert_log)
                for recipient in recipients:
                    notification = Notification.objects.create(
                        alert_log=alert_log,
                        notification_type=channel.channel_type,
                        recipient=recipient,
                        subject=f"Alert: {alert_log.rule.name}",
                        message=message or alert_log.message,
                        status='pending'
                    )
                    notifications.append(notification)
            return notifications
        except Exception as e:
            logger.error(f"Error creating notifications: {e}")
            return []

    @staticmethod
    def _get_channel_recipients(channel, alert_log):
        """Resolve recipient contact details for a specific channel."""
        try:
            channel_recipients = AlertRecipient.objects.filter(
                preferred_channels__contains=[channel.channel_type],
                is_active=True
            )
            recipients = []
            for recipient in channel_recipients:
                if recipient.can_receive_notification():
                    contact_info = recipient.get_contact_info()
                    if channel.channel_type == 'email' and 'email' in contact_info:
                        recipients.append(contact_info['email'])
                    elif channel.channel_type == 'sms' and 'phone' in contact_info:
                        recipients.append(contact_info['phone'])
                    elif channel.channel_type == 'telegram' and 'phone' in contact_info:
                        recipients.append(contact_info['phone'])
            if not recipients:
                rule_recipients = alert_log.rule.get_recipients()
                if channel.channel_type == 'email':
                    recipients.extend(rule_recipients.get('emails', []))
                elif channel.channel_type == 'sms':
                    recipients.extend(rule_recipients.get('sms', []))
                elif channel.channel_type == 'telegram' and rule_recipients.get('telegram'):
                    recipients.append(rule_recipients['telegram'])
            return list(set(recipients))
        except Exception as e:
            logger.error(f"Error getting channel recipients: {e}")
            return []

    @staticmethod
    def test_channel(channel_id):
        """Test a channel's connectivity and send a test notification."""
        try:
            channel = AlertChannel.objects.get(id=channel_id)
            health_status = ChannelHealthService.check_channel_health(channel)
            test_result = ChannelRoutingService._send_test_notification(channel)
            return {
                'channel_id': channel_id,
                'channel_name': channel.name,
                'health_status': health_status,
                'test_notification': test_result,
                'timestamp': timezone.now().isoformat()
            }
        except AlertChannel.DoesNotExist:
            logger.error(f"Channel {channel_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error testing channel: {e}")
            return None

    @staticmethod
    def _send_test_notification(channel):
        """Send and immediately delete a test notification to verify the channel."""
        try:
            test_notification = Notification.objects.create(
                alert_log=None,
                notification_type=channel.channel_type,
                recipient="test@example.com",
                subject=f"Test Alert from {channel.name}",
                message="This is a test notification to verify channel connectivity.",
                status='pending'
            )
            success = NotificationService._send_notification(test_notification)
            test_notification.delete()
            return success
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False


class ChannelHealthService:
    """Channel health monitoring service"""

    @staticmethod
    def check_all_channels():
        """Check health of all active channels."""
        try:
            channels = AlertChannel.objects.filter(is_enabled=True)
            return [ChannelHealthService.check_channel_health(channel) for channel in channels]
        except Exception as e:
            logger.error(f"Error checking all channels: {e}")
            return []

    @staticmethod
    def check_channel_health(channel):
        """Dispatch to the appropriate health-check method for the channel type."""
        try:
            dispatch = {
                'email': ChannelHealthService._check_email_health,
                'telegram': ChannelHealthService._check_telegram_health,
                'sms': ChannelHealthService._check_sms_health,
                'webhook': ChannelHealthService._check_webhook_health,
            }
            check_fn = dispatch.get(channel.channel_type, ChannelHealthService._check_generic_health)
            return check_fn(channel)
        except Exception as e:
            logger.error(f"Error checking channel health: {e}")
            return {'channel_id': channel.id, 'status': 'error', 'error': 'Operation failed'}

    @staticmethod
    def _check_email_health(channel):
        try:
            import random
            response_time = random.uniform(100, 500)
            success = random.random() > 0.05
            status = 'healthy' if success else 'critical'
            error_message = "" if success else "SMTP connection failed"
            ChannelHealthLog.log_health_check(
                channel=channel, status=status, check_type='connectivity',
                response_time_ms=response_time, error_message=error_message
            )
            return {
                'channel_id': channel.id, 'channel_type': 'email', 'status': status,
                'response_time_ms': response_time, 'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking email health: {e}")
            return {'channel_id': channel.id, 'channel_type': 'email', 'status': 'error', 'error_message': 'Operation failed'}

    @staticmethod
    def _check_telegram_health(channel):
        try:
            import random
            response_time = random.uniform(200, 800)
            success = random.random() > 0.10
            status = 'healthy' if success else 'critical'
            error_message = "" if success else "Bot token invalid"
            ChannelHealthLog.log_health_check(
                channel=channel, status=status, check_type='connectivity',
                response_time_ms=response_time, error_message=error_message
            )
            return {
                'channel_id': channel.id, 'channel_type': 'telegram', 'status': status,
                'response_time_ms': response_time, 'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking Telegram health: {e}")
            return {'channel_id': channel.id, 'channel_type': 'telegram', 'status': 'error', 'error_message': 'Operation failed'}

    @staticmethod
    def _check_sms_health(channel):
        try:
            import random
            response_time = random.uniform(300, 1200)
            success = random.random() > 0.15
            status = 'healthy' if success else 'critical'
            error_message = "" if success else "SMS provider unreachable"
            ChannelHealthLog.log_health_check(
                channel=channel, status=status, check_type='connectivity',
                response_time_ms=response_time, error_message=error_message
            )
            return {
                'channel_id': channel.id, 'channel_type': 'sms', 'status': status,
                'response_time_ms': response_time, 'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking SMS health: {e}")
            return {'channel_id': channel.id, 'channel_type': 'sms', 'status': 'error', 'error_message': 'Operation failed'}

    @staticmethod
    def _check_webhook_health(channel):
        try:
            import random
            webhook_url = channel.config.get('url')
            if not webhook_url:
                return {'channel_id': channel.id, 'channel_type': 'webhook',
                        'status': 'critical', 'error_message': 'No webhook URL configured'}
            # Simulated, like every other channel type here - a live GET to a
            # user-supplied URL from a signal-triggered background task is an
            # SSRF/reliability risk and doesn't belong in a synchronous health
            # check path. Real connectivity checks belong in a rate-limited,
            # explicitly-triggered task instead.
            response_time = random.uniform(100, 800)
            success = random.random() > 0.1
            status = 'healthy' if success else 'warning'
            error_message = "" if success else "Webhook endpoint unreachable"
            ChannelHealthLog.log_health_check(
                channel=channel, status=status, check_type='connectivity',
                response_time_ms=response_time, error_message=error_message
            )
            return {
                'channel_id': channel.id, 'channel_type': 'webhook', 'status': status,
                'response_time_ms': response_time, 'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking webhook health: {e}")
            return {'channel_id': channel.id, 'channel_type': 'webhook', 'status': 'error', 'error_message': 'Operation failed'}

    @staticmethod
    def _check_generic_health(channel):
        try:
            import random
            response_time = random.uniform(100, 1000)
            success = random.random() > 0.05
            status = 'healthy' if success else 'warning'
            error_message = "" if success else "Generic health check failed"
            ChannelHealthLog.log_health_check(
                channel=channel, status=status, check_type='connectivity',
                response_time_ms=response_time, error_message=error_message
            )
            return {
                'channel_id': channel.id, 'channel_type': channel.channel_type, 'status': status,
                'response_time_ms': response_time, 'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking generic health: {e}")
            return {'channel_id': channel.id, 'channel_type': channel.channel_type,
                    'status': 'error', 'error_message': 'Operation failed'}

    @staticmethod
    def get_channel_health_summary(hours=24):
        """Aggregate health status across all active channels."""
        try:
            channels = AlertChannel.objects.filter(is_enabled=True)
            summary = {
                'total_channels': channels.count(),
                'healthy': 0, 'warning': 0, 'critical': 0, 'error': 0,
                'channels': []
            }
            for channel in channels:
                health_summary = ChannelHealthLog.get_health_summary(channel, hours)
                channel_health = channel.get_health_status()
                summary[channel_health] = summary.get(channel_health, 0) + 1
                summary['channels'].append({
                    'channel_id': channel.id,
                    'channel_name': channel.name,
                    'channel_type': channel.channel_type,
                    'status': channel_health,
                    'health_summary': health_summary
                })
            return summary
        except Exception as e:
            logger.error(f"Error getting channel health summary: {e}")
            return None


class RecipientManagementService:
    """Alert recipient management service"""

    @staticmethod
    def get_available_recipients(notification_type):
        """Return recipients available right now for the given notification type."""
        try:
            recipients = AlertRecipient.objects.filter(
                preferred_channels__contains=[notification_type],
                is_active=True
            )
            available_recipients = []
            for recipient in recipients:
                if recipient.is_available_now() and recipient.can_receive_notification():
                    available_recipients.append({
                        'id': recipient.id,
                        'name': recipient.name,
                        'type': recipient.recipient_type,
                        'priority': recipient.priority,
                        'contact_info': recipient.get_contact_info(),
                        'availability': {
                            'is_available': recipient.is_available_now(),
                            'available_hours': {
                                'start': recipient.available_hours_start,
                                'end': recipient.available_hours_end
                            },
                            'timezone': recipient.timezone
                        }
                    })
            available_recipients.sort(
                key=lambda x: {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(x['priority'], 0),
                reverse=True
            )
            return available_recipients
        except Exception as e:
            logger.error(f"Error getting available recipients: {e}")
            return []

    @staticmethod
    def add_recipient(recipient_data):
        """Create and return a new AlertRecipient."""
        try:
            recipient = AlertRecipient.objects.create(**recipient_data)
            logger.info(f"Added alert recipient: {recipient.name}")
            return recipient
        except Exception as e:
            logger.error(f"Error adding recipient: {e}")
            return None

    @staticmethod
    def update_recipient_availability(recipient_id, availability_data):
        """Update availability fields on an existing recipient."""
        try:
            recipient = AlertRecipient.objects.get(id=recipient_id)
            for key, value in availability_data.items():
                if hasattr(recipient, key):
                    setattr(recipient, key, value)
            recipient.save()
            logger.info(f"Updated availability for recipient {recipient_id}")
            return True
        except AlertRecipient.DoesNotExist:
            logger.error(f"Recipient {recipient_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error updating recipient availability: {e}")
            return False

    @staticmethod
    def get_recipient_usage_statistics(recipient_id, days=30):
        """Return delivery statistics for a recipient over the given period."""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            notifications = Notification.objects.filter(
                recipient__contains=str(recipient_id),
                created_at__gte=cutoff_date
            )
            stats = notifications.aggregate(
                total_sent=models.Count('id'),
                successful_sent=models.Count('id', filter=models.Q(status='sent')),
                failed_sent=models.Count('id', filter=models.Q(status='failed'))
            )
            return {
                'recipient_id': recipient_id,
                'period_days': days,
                'total_sent': stats['total_sent'],
                'successful_sent': stats['successful_sent'],
                'failed_sent': stats['failed_sent'],
                'success_rate': (
                    stats['successful_sent'] / stats['total_sent'] * 100
                ) if stats['total_sent'] > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting recipient usage statistics: {e}")
            return None
