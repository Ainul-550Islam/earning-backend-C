"""
Alert Channel Services
"""
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.core import Notification
from ..models.channel import AlertChannel, ChannelRoute, ChannelHealthLog, ChannelRateLimit, AlertRecipient

logger = logging.getLogger(__name__)


class NotificationService:
    """Notification processing and delivery service"""
    
    @staticmethod
    def send_pending_notifications():
        """Send pending notifications using Notification model"""
        try:
            pending_notifications = Notification.objects.filter(
                status='pending'
            ).select_related('alert_log', 'alert_log__rule')[:50]
            
            sent_count = 0
            failed_count = 0
            
            for notification in pending_notifications:
                try:
                    # Check retry delay
                    if notification.retry_count > 0 and notification.last_retry_at:
                        retry_delay = notification.get_retry_delay()
                        time_since_retry = (timezone.now() - notification.last_retry_at).total_seconds()
                        
                        if time_since_retry < retry_delay:
                            continue
                    
                    # Send notification based on type
                    success = NotificationService._send_notification(notification)
                    
                    if success:
                        notification.mark_as_sent(
                            message_id=f"msg_{notification.id}",
                            response_time_ms=100  # Example response time
                        )
                        sent_count += 1
                    else:
                        notification.mark_as_failed("Failed to send")
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error sending notification {notification.id}: {e}")
                    notification.mark_as_failed(str(e))
                    failed_count += 1
            
            return {
                'sent': sent_count,
                'failed': failed_count,
                'total': len(pending_notifications)
            }
            
        except Exception as e:
            logger.error(f"Error in send_pending_notifications: {e}")
            return {'sent': 0, 'failed': 0, 'total': 0}
    
    @staticmethod
    def _send_notification(notification):
        """Send notification based on type"""
        try:
            # Get channel configuration
            channel = AlertChannel.objects.filter(
                channel_type=notification.notification_type,
                is_enabled=True,
                status='active'
            ).first()
            
            if not channel:
                logger.warning(f"No active channel found for {notification.notification_type}")
                return False
            
            # Check rate limits
            if not channel.can_send_notification():
                logger.warning(f"Channel {channel.name} rate limited")
                return False
            
            # Send based on notification type
            if notification.notification_type == 'email':
                return NotificationService._send_email(notification, channel)
            elif notification.notification_type == 'telegram':
                return NotificationService._send_telegram(notification, channel)
            elif notification.notification_type == 'sms':
                return NotificationService._send_sms(notification, channel)
            elif notification.notification_type == 'webhook':
                return NotificationService._send_webhook(notification, channel)
            else:
                logger.warning(f"Unsupported notification type: {notification.notification_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error in _send_notification: {e}")
            return False
    
    @staticmethod
    def _send_email(notification, channel):
        """Send email notification"""
        try:
            # Simulate email sending
            import random
            success_rate = 0.95
            
            if random.random() < success_rate:
                # Record success
                channel.record_success()
                return True
            else:
                # Record failure
                channel.record_failure()
                return False
                
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            channel.record_failure()
            return False
    
    @staticmethod
    def _send_telegram(notification, channel):
        """Send Telegram notification"""
        try:
            # Simulate Telegram sending
            import random
            success_rate = 0.90
            
            if random.random() < success_rate:
                channel.record_success()
                return True
            else:
                channel.record_failure()
                return False
                
        except Exception as e:
            logger.error(f"Error sending Telegram: {e}")
            channel.record_failure()
            return False
    
    @staticmethod
    def _send_sms(notification, channel):
        """Send SMS notification"""
        try:
            # Simulate SMS sending
            import random
            success_rate = 0.85
            
            if random.random() < success_rate:
                channel.record_success()
                return True
            else:
                channel.record_failure()
                return False
                
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            channel.record_failure()
            return False
    
    @staticmethod
    def _send_webhook(notification, channel):
        """Send webhook notification"""
        try:
            # Simulate webhook sending
            import random
            success_rate = 0.92
            
            if random.random() < success_rate:
                channel.record_success()
                return True
            else:
                channel.record_failure()
                return False
                
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            channel.record_failure()
            return False
    
    @staticmethod
    def retry_failed_notifications():
        """Retry failed notifications"""
        try:
            failed_notifications = Notification.objects.filter(
                status='failed'
            )
            
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
        """Get notification statistics"""
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
            
            # Get by type
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
                'success_rate': (stats['successful_sent'] / stats['total_sent'] * 100) if stats['total_sent'] > 0 else 0,
                'by_type': list(by_type)
            }
            
        except Exception as e:
            logger.error(f"Error getting notification statistics: {e}")
            return None


class ChannelRoutingService:
    """Channel routing and management service"""
    
    @staticmethod
    def route_notification(alert_log, notification_type):
        """Route notification through appropriate channels"""
        try:
            # Get active routes
            routes = ChannelRoute.objects.filter(
                is_active=True
            ).order_by('priority')
            
            routed_channels = []
            
            for route in routes:
                if route.should_route(alert_log, notification_type):
                    destination_channels = route.get_destination_channels()
                    routed_channels.extend(destination_channels)
            
            # Remove duplicates while preserving order
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
        """Create notifications for multiple channels"""
        try:
            notifications = []
            
            for channel in channels:
                # Get recipients for channel
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
        """Get recipients for a specific channel"""
        try:
            # Get channel-specific recipients
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
            
            # Fall back to rule recipients if no channel recipients
            if not recipients:
                rule_recipients = alert_log.rule.get_recipients()
                
                if channel.channel_type == 'email':
                    recipients.extend(rule_recipients.get('emails', []))
                elif channel.channel_type == 'sms':
                    recipients.extend(rule_recipients.get('sms', []))
                elif channel.channel_type == 'telegram' and rule_recipients.get('telegram'):
                    recipients.append(rule_recipients['telegram'])
            
            return list(set(recipients))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error getting channel recipients: {e}")
            return []
    
    @staticmethod
    def test_channel(channel_id):
        """Test channel connectivity and configuration"""
        try:
            channel = AlertChannel.objects.get(id=channel_id)
            
            # Perform health check
            health_status = ChannelHealthService.check_channel_health(channel)
            
            # Send test notification
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
        """Send test notification to verify channel"""
        try:
            # Create test notification
            test_notification = Notification.objects.create(
                alert_log=None,  # Test notification
                notification_type=channel.channel_type,
                recipient="test@example.com",  # Default test recipient
                subject=f"Test Alert from {channel.name}",
                message="This is a test notification to verify channel connectivity.",
                status='pending'
            )
            
            # Send the notification
            success = NotificationService._send_notification(test_notification)
            
            # Clean up test notification
            test_notification.delete()
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False


class ChannelHealthService:
    """Channel health monitoring service"""
    
    @staticmethod
    def check_all_channels():
        """Check health of all active channels"""
        try:
            channels = AlertChannel.objects.filter(is_active=True)
            results = []
            
            for channel in channels:
                health_status = ChannelHealthService.check_channel_health(channel)
                results.append(health_status)
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking all channels: {e}")
            return []
    
    @staticmethod
    def check_channel_health(channel):
        """Check health of a specific channel"""
        try:
            # Perform different checks based on channel type
            if channel.channel_type == 'email':
                return ChannelHealthService._check_email_health(channel)
            elif channel.channel_type == 'telegram':
                return ChannelHealthService._check_telegram_health(channel)
            elif channel.channel_type == 'sms':
                return ChannelHealthService._check_sms_health(channel)
            elif channel.channel_type == 'webhook':
                return ChannelHealthService._check_webhook_health(channel)
            else:
                return ChannelHealthService._check_generic_health(channel)
                
        except Exception as e:
            logger.error(f"Error checking channel health: {e}")
            return {
                'channel_id': channel.id,
                'status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def _check_email_health(channel):
        """Check email channel health"""
        try:
            import random
            
            # Simulate email connectivity check
            response_time = random.uniform(100, 500)  # 100-500ms
            success = random.random() > 0.05  # 95% success rate
            
            status = 'healthy' if success else 'critical'
            error_message = "" if success else "SMTP connection failed"
            
            # Log health check
            ChannelHealthLog.log_health_check(
                channel=channel,
                status=status,
                check_type='connectivity',
                response_time_ms=response_time,
                error_message=error_message
            )
            
            return {
                'channel_id': channel.id,
                'channel_type': 'email',
                'status': status,
                'response_time_ms': response_time,
                'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking email health: {e}")
            return {
                'channel_id': channel.id,
                'channel_type': 'email',
                'status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _check_telegram_health(channel):
        """Check Telegram channel health"""
        try:
            import random
            
            response_time = random.uniform(200, 800)
            success = random.random() > 0.10  # 90% success rate
            
            status = 'healthy' if success else 'critical'
            error_message = "" if success else "Bot token invalid"
            
            ChannelHealthLog.log_health_check(
                channel=channel,
                status=status,
                check_type='connectivity',
                response_time_ms=response_time,
                error_message=error_message
            )
            
            return {
                'channel_id': channel.id,
                'channel_type': 'telegram',
                'status': status,
                'response_time_ms': response_time,
                'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking Telegram health: {e}")
            return {
                'channel_id': channel.id,
                'channel_type': 'telegram',
                'status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _check_sms_health(channel):
        """Check SMS channel health"""
        try:
            import random
            
            response_time = random.uniform(300, 1200)
            success = random.random() > 0.15  # 85% success rate
            
            status = 'healthy' if success else 'critical'
            error_message = "" if success else "SMS provider unreachable"
            
            ChannelHealthLog.log_health_check(
                channel=channel,
                status=status,
                check_type='connectivity',
                response_time_ms=response_time,
                error_message=error_message
            )
            
            return {
                'channel_id': channel.id,
                'channel_type': 'sms',
                'status': status,
                'response_time_ms': response_time,
                'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking SMS health: {e}")
            return {
                'channel_id': channel.id,
                'channel_type': 'sms',
                'status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _check_webhook_health(channel):
        """Check webhook channel health"""
        try:
            import random
            import requests
            
            webhook_url = channel.config.get('url')
            if not webhook_url:
                return {
                    'channel_id': channel.id,
                    'channel_type': 'webhook',
                    'status': 'critical',
                    'error_message': 'No webhook URL configured'
                }
            
            # Test webhook endpoint
            start_time = timezone.now()
            try:
                response = requests.get(webhook_url, timeout=10)
                response_time = (timezone.now() - start_time).total_seconds() * 1000
                
                success = response.status_code < 400
                status = 'healthy' if success else 'warning'
                error_message = "" if success else f"HTTP {response.status_code}"
                
            except requests.exceptions.RequestException as e:
                response_time = 10000  # 10 seconds timeout
                success = False
                status = 'critical'
                error_message = str(e)
            
            ChannelHealthLog.log_health_check(
                channel=channel,
                status=status,
                check_type='connectivity',
                response_time_ms=response_time,
                error_message=error_message
            )
            
            return {
                'channel_id': channel.id,
                'channel_type': 'webhook',
                'status': status,
                'response_time_ms': response_time,
                'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking webhook health: {e}")
            return {
                'channel_id': channel.id,
                'channel_type': 'webhook',
                'status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def _check_generic_health(channel):
        """Check generic channel health"""
        try:
            import random
            
            response_time = random.uniform(100, 1000)
            success = random.random() > 0.05
            
            status = 'healthy' if success else 'warning'
            error_message = "" if success else "Generic health check failed"
            
            ChannelHealthLog.log_health_check(
                channel=channel,
                status=status,
                check_type='connectivity',
                response_time_ms=response_time,
                error_message=error_message
            )
            
            return {
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'status': status,
                'response_time_ms': response_time,
                'error_message': error_message,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking generic health: {e}")
            return {
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'status': 'error',
                'error_message': str(e)
            }
    
    @staticmethod
    def get_channel_health_summary(hours=24):
        """Get health summary for all channels"""
        try:
            channels = AlertChannel.objects.filter(is_active=True)
            summary = {
                'total_channels': channels.count(),
                'healthy': 0,
                'warning': 0,
                'critical': 0,
                'error': 0,
                'channels': []
            }
            
            for channel in channels:
                health_summary = ChannelHealthLog.get_health_summary(channel, hours)
                channel_health = channel.get_health_status()
                
                summary[channel_health] += 1
                
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
        """Get available recipients for a notification type"""
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
            
            # Sort by priority
            available_recipients.sort(key=lambda x: {
                'critical': 4,
                'high': 3,
                'medium': 2,
                'low': 1
            }.get(x['priority'], 0), reverse=True)
            
            return available_recipients
            
        except Exception as e:
            logger.error(f"Error getting available recipients: {e}")
            return []
    
    @staticmethod
    def add_recipient(recipient_data):
        """Add a new alert recipient"""
        try:
            recipient = AlertRecipient.objects.create(**recipient_data)
            
            logger.info(f"Added alert recipient: {recipient.name}")
            return recipient
            
        except Exception as e:
            logger.error(f"Error adding recipient: {e}")
            return None
    
    @staticmethod
    def update_recipient_availability(recipient_id, availability_data):
        """Update recipient availability"""
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
        """Get usage statistics for a recipient"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            notifications = Notification.objects.filter(
                recipient__contains=str(recipient_id),  # Simplified check
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
                'success_rate': (stats['successful_sent'] / stats['total_sent'] * 100) if stats['total_sent'] > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting recipient usage statistics: {e}")
            return None
