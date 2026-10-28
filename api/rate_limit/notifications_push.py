# api/rate_limit/notifications_push.py
"""
Push notification system for rate limit module.

Provides real-time notifications for rate limiting events.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from api.rate_limit.models import RateLimitLog, AbuseReport, IPBlockList
from api.rate_limit.repositories import RepositoryFactory

logger = logging.getLogger(__name__)


class NotificationType:
    """Enumeration of notification types."""
    
    RATE_LIMIT_EXCEEDED = 'rate_limit_exceeded'
    ABUSE_DETECTED = 'abuse_detected'
    IP_BLOCKED = 'ip_blocked'
    SYSTEM_ALERT = 'system_alert'
    USER_SUSPICIOUS = 'user_suspicious'
    CONFIGURATION_CHANGED = 'configuration_changed'
    HEALTH_DEGRADED = 'health_degraded'
    
    CHOICES = [
        (RATE_LIMIT_EXCEEDED, 'Rate Limit Exceeded'),
        (ABUSE_DETECTED, 'Abuse Detected'),
        (IP_BLOCKED, 'IP Blocked'),
        (SYSTEM_ALERT, 'System Alert'),
        (USER_SUSPICIOUS, 'User Suspicious'),
        (CONFIGURATION_CHANGED, 'Configuration Changed'),
        (HEALTH_DEGRADED, 'Health Degraded'),
    ]


class NotificationPriority:
    """Enumeration of notification priorities."""
    
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]


class NotificationChannel:
    """Base class for notification channels."""
    
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
    
    def send(self, notification: 'Notification') -> bool:
        """
        Send notification through this channel.
        
        Args:
            notification: Notification to send
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            return self._send_notification(notification)
        except Exception as e:
            logger.error(f"Failed to send notification via {self.name}: {str(e)}")
            return False
    
    def _send_notification(self, notification: 'Notification') -> bool:
        """Implement actual sending logic."""
        raise NotImplementedError("Subclasses must implement _send_notification")


class WebSocketNotificationChannel(NotificationChannel):
    """WebSocket notification channel."""
    
    def __init__(self, enabled: bool = True):
        super().__init__('websocket', enabled)
        self.channel_layer = get_channel_layer()
    
    def _send_notification(self, notification: 'Notification') -> bool:
        """Send notification via WebSocket."""
        try:
            # Send to rate limit monitoring group
            async_to_sync(self.channel_layer.group_send)(
                'rate_limit_monitoring',
                {
                    'type': 'rate_limit_notification',
                    'notification': notification.to_dict()
                }
            )
            
            # Send to admin group if critical
            if notification.priority == NotificationPriority.CRITICAL:
                async_to_sync(self.channel_layer.group_send)(
                    'admin_alerts',
                    {
                        'type': 'critical_notification',
                        'notification': notification.to_dict()
                    }
                )
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket notification failed: {str(e)}")
            return False


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""
    
    def __init__(self, enabled: bool = True):
        super().__init__('email', enabled)
    
    def _send_notification(self, notification: 'Notification') -> bool:
        """Send notification via email."""
        try:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            
            # Only send high priority notifications via email
            if notification.priority not in [NotificationPriority.HIGH, NotificationPriority.CRITICAL]:
                return True
            
            # Get recipient emails
            recipients = self._get_recipients(notification)
            
            if not recipients:
                return True
            
            # Render email template
            subject = f"Rate Limit Alert: {notification.title}"
            
            context = {
                'notification': notification,
                'timestamp': timezone.now(),
            }
            
            html_message = render_to_string('rate_limit/email_notification.html', context)
            text_message = render_to_string('rate_limit/email_notification.txt', context)
            
            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=recipients,
                html_message=html_message,
                fail_silently=False
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Email notification failed: {str(e)}")
            return False
    
    def _get_recipients(self, notification: 'Notification') -> List[str]:
        """Get email recipients for notification."""
        recipients = []
        
        # Get admin emails
        admin_emails = getattr(settings, 'RATE_LIMIT_ADMIN_EMAILS', [])
        recipients.extend(admin_emails)
        
        # Get rate limit manager emails
        from django.contrib.auth.models import User
        rate_limit_managers = User.objects.filter(groups__name='rate_limit_managers')
        recipients.extend([user.email for user in rate_limit_managers if user.email])
        
        return list(set(recipients))


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel."""
    
    def __init__(self, enabled: bool = True):
        super().__init__('slack', enabled)
        self.webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
    
    def _send_notification(self, notification: 'Notification') -> bool:
        """Send notification via Slack."""
        if not self.webhook_url:
            return True
        
        try:
            import requests
            
            # Only send high and critical priority notifications
            if notification.priority not in [NotificationPriority.HIGH, NotificationPriority.CRITICAL]:
                return True
            
            # Format Slack message
            color = self._get_slack_color(notification.priority)
            
            payload = {
                'attachments': [
                    {
                        'color': color,
                        'title': f"Rate Limit Alert: {notification.title}",
                        'text': notification.message,
                        'fields': [
                            {
                                'title': 'Priority',
                                'value': notification.priority.upper(),
                                'short': True
                            },
                            {
                                'title': 'Type',
                                'value': notification.notification_type,
                                'short': True
                            },
                            {
                                'title': 'Timestamp',
                                'value': notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                'short': True
                            }
                        ],
                        'footer': 'Rate Limit Monitoring',
                        'ts': notification.created_at.timestamp()
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"Slack notification failed: {str(e)}")
            return False
    
    def _get_slack_color(self, priority: str) -> str:
        """Get Slack color for priority."""
        colors = {
            NotificationPriority.LOW: '#36a64f',      # green
            NotificationPriority.MEDIUM: '#ff9500',   # orange
            NotificationPriority.HIGH: '#ff0000',     # red
            NotificationPriority.CRITICAL: '#8b0000', # dark red
        }
        return colors.get(priority, '#36a64f')


class SMSNotificationChannel(NotificationChannel):
    """SMS notification channel."""
    
    def __init__(self, enabled: bool = True):
        super().__init__('sms', enabled)
        self.api_key = getattr(settings, 'SMS_API_KEY', None)
        self.api_url = getattr(settings, 'SMS_API_URL', None)
    
    def _send_notification(self, notification: 'Notification') -> bool:
        """Send notification via SMS."""
        if not self.api_key or not self.api_url:
            return True
        
        # Only send critical notifications via SMS
        if notification.priority != NotificationPriority.CRITICAL:
            return True
        
        try:
            import requests
            
            # Get phone numbers
            phone_numbers = self._get_phone_numbers()
            
            if not phone_numbers:
                return True
            
            # Format message
            message = f"CRITICAL: {notification.title} - {notification.message[:100]}"
            
            # Send SMS
            for phone_number in phone_numbers:
                payload = {
                    'api_key': self.api_key,
                    'to': phone_number,
                    'message': message
                }
                
                response = requests.post(self.api_url, json=payload, timeout=10)
                response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"SMS notification failed: {str(e)}")
            return False
    
    def _get_phone_numbers(self) -> List[str]:
        """Get phone numbers for SMS notifications."""
        phone_numbers = getattr(settings, 'RATE_LIMIT_SMS_NUMBERS', [])
        return phone_numbers


class Notification:
    """Represents a notification."""
    
    def __init__(self, title: str, message: str, notification_type: str, 
                 priority: str = NotificationPriority.MEDIUM, data: Dict[str, Any] = None,
                 target_user_id: int = None, target_channels: List[str] = None):
        self.title = title
        self.message = message
        self.notification_type = notification_type
        self.priority = priority
        self.data = data or {}
        self.target_user_id = target_user_id
        self.target_channels = target_channels or []
        self.created_at = timezone.now()
        self.read = False
        self.read_at = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary."""
        return {
            'id': id(self),
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'priority': self.priority,
            'data': self.data,
            'target_user_id': self.target_user_id,
            'created_at': self.created_at.isoformat(),
            'read': self.read,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }
    
    def mark_as_read(self):
        """Mark notification as read."""
        self.read = True
        self.read_at = timezone.now()


class NotificationManager:
    """Manages notifications and notification channels."""
    
    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        self.repositories = RepositoryFactory.get_all_repositories()
        self._initialize_channels()
        self._notification_queue = []
        self._max_queue_size = 1000
    
    def _initialize_channels(self):
        """Initialize notification channels."""
        
        # WebSocket channel (always enabled)
        self.register_channel(WebSocketNotificationChannel(enabled=True))
        
        # Email channel
        email_enabled = getattr(settings, 'RATE_LIMIT_EMAIL_NOTIFICATIONS', True)
        self.register_channel(EmailNotificationChannel(enabled=email_enabled))
        
        # Slack channel
        slack_enabled = getattr(settings, 'RATE_LIMIT_SLACK_NOTIFICATIONS', False)
        self.register_channel(SlackNotificationChannel(enabled=slack_enabled))
        
        # SMS channel
        sms_enabled = getattr(settings, 'RATE_LIMIT_SMS_NOTIFICATIONS', False)
        self.register_channel(SMSNotificationChannel(enabled=sms_enabled))
    
    def register_channel(self, channel: NotificationChannel):
        """Register a notification channel."""
        self.channels[channel.name] = channel
        logger.info(f"Registered notification channel: {channel.name}")
    
    def unregister_channel(self, name: str):
        """Unregister a notification channel."""
        if name in self.channels:
            del self.channels[name]
            logger.info(f"Unregistered notification channel: {name}")
    
    def send_notification(self, notification: Notification) -> Dict[str, Any]:
        """
        Send notification through appropriate channels.
        
        Args:
            notification: Notification to send
            
        Returns:
            Send result
        """
        try:
            # Add to queue
            self._add_to_queue(notification)
            
            # Determine target channels
            target_channels = notification.target_channels if notification.target_channels else self._get_default_channels(notification.priority)
            
            results = {}
            sent_count = 0
            
            for channel_name in target_channels:
                if channel_name in self.channels:
                    channel = self.channels[channel_name]
                    success = channel.send(notification)
                    results[channel_name] = success
                    
                    if success:
                        sent_count += 1
            
            # Log notification
            logger.info(f"Notification sent: {notification.title} - {sent_count}/{len(target_channels)} channels")
            
            # Store notification for history
            self._store_notification(notification, results)
            
            return {
                'success': sent_count > 0,
                'notification_id': id(notification),
                'sent_channels': sent_count,
                'total_channels': len(target_channels),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _add_to_queue(self, notification: Notification):
        """Add notification to queue."""
        self._notification_queue.append(notification)
        
        # Maintain queue size
        if len(self._notification_queue) > self._max_queue_size:
            self._notification_queue.pop(0)
    
    def _get_default_channels(self, priority: str) -> List[str]:
        """Get default channels based on priority."""
        if priority == NotificationPriority.CRITICAL:
            return ['websocket', 'email', 'slack', 'sms']
        elif priority == NotificationPriority.HIGH:
            return ['websocket', 'email', 'slack']
        elif priority == NotificationPriority.MEDIUM:
            return ['websocket']
        else:
            return ['websocket']
    
    def _store_notification(self, notification: Notification, results: Dict[str, bool]):
        """Store notification in cache for history."""
        try:
            notification_data = {
                'notification': notification.to_dict(),
                'results': results,
                'timestamp': timezone.now().isoformat()
            }
            
            # Store in cache with TTL
            cache_key = f"rate_limit_notification:{id(notification)}"
            cache.set(cache_key, notification_data, timeout=86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Failed to store notification: {str(e)}")
    
    def create_rate_limit_notification(self, log_entry: RateLimitLog) -> Notification:
        """Create rate limit exceeded notification."""
        title = "Rate Limit Exceeded"
        message = f"Rate limit exceeded for {log_entry.ip_address} on {log_entry.endpoint}"
        
        priority = NotificationPriority.HIGH if log_entry.suspicion_score > 70 else NotificationPriority.MEDIUM
        
        data = {
            'log_id': log_entry.id,
            'ip_address': log_entry.ip_address,
            'endpoint': log_entry.endpoint,
            'suspicion_score': log_entry.suspicion_score,
            'user_id': log_entry.user.id if log_entry.user else None
        }
        
        return Notification(
            title=title,
            message=message,
            notification_type=NotificationType.RATE_LIMIT_EXCEEDED,
            priority=priority,
            data=data
        )
    
    def create_abuse_notification(self, abuse_report: AbuseReport) -> Notification:
        """Create abuse detected notification."""
        title = "Abuse Detected"
        message = f"Abuse detected: {abuse_report.abuse_type} from {abuse_report.ip_address}"
        
        priority = NotificationPriority.CRITICAL if abuse_report.severity >= 4 else NotificationPriority.HIGH
        
        data = {
            'report_id': abuse_report.id,
            'abuse_type': abuse_report.abuse_type,
            'severity': abuse_report.severity,
            'ip_address': abuse_report.ip_address,
            'user_id': abuse_report.user.id if abuse_report.user else None
        }
        
        return Notification(
            title=title,
            message=message,
            notification_type=NotificationType.ABUSE_DETECTED,
            priority=priority,
            data=data
        )
    
    def create_ip_block_notification(self, ip_block: IPBlockList) -> Notification:
        """Create IP blocked notification."""
        title = "IP Address Blocked"
        message = f"IP {ip_block.ip_address} blocked due to {ip_block.block_reason}"
        
        priority = NotificationPriority.HIGH if ip_block.block_reason in ['abuse', 'security'] else NotificationPriority.MEDIUM
        
        data = {
            'block_id': ip_block.id,
            'ip_address': ip_block.ip_address,
            'block_reason': ip_block.block_reason,
            'block_type': ip_block.block_type,
            'permanent': ip_block.permanent,
            'expires_at': ip_block.expires_at.isoformat() if ip_block.expires_at else None
        }
        
        return Notification(
            title=title,
            message=message,
            notification_type=NotificationType.IP_BLOCKED,
            priority=priority,
            data=data
        )
    
    def create_system_alert_notification(self, title: str, message: str, 
                                        priority: str = NotificationPriority.MEDIUM, 
                                        data: Dict[str, Any] = None) -> Notification:
        """Create system alert notification."""
        return Notification(
            title=title,
            message=message,
            notification_type=NotificationType.SYSTEM_ALERT,
            priority=priority,
            data=data or {}
        )
    
    def get_notification_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get notification history from cache."""
        try:
            # Get all notification keys from cache
            cache_keys = cache.keys("rate_limit_notification:*")
            
            notifications = []
            for cache_key in cache_keys[:limit]:
                notification_data = cache.get(cache_key)
                if notification_data:
                    notifications.append(notification_data)
            
            # Sort by timestamp (most recent first)
            notifications.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return notifications
            
        except Exception as e:
            logger.error(f"Failed to get notification history: {str(e)}")
            return []
    
    def get_channel_status(self) -> Dict[str, Any]:
        """Get status of all notification channels."""
        status = {}
        
        for name, channel in self.channels.items():
            status[name] = {
                'enabled': channel.enabled,
                'type': channel.__class__.__name__
            }
        
        return status
    
    def enable_channel(self, name: str):
        """Enable notification channel."""
        if name in self.channels:
            self.channels[name].enabled = True
            logger.info(f"Enabled notification channel: {name}")
    
    def disable_channel(self, name: str):
        """Disable notification channel."""
        if name in self.channels:
            self.channels[name].enabled = False
            logger.info(f"Disabled notification channel: {name}")


# Global notification manager instance
notification_manager = NotificationManager()


# Convenience functions
def send_rate_limit_notification(log_entry: RateLimitLog) -> Dict[str, Any]:
    """Send rate limit exceeded notification."""
    notification = notification_manager.create_rate_limit_notification(log_entry)
    return notification_manager.send_notification(notification)


def send_abuse_notification(abuse_report: AbuseReport) -> Dict[str, Any]:
    """Send abuse detected notification."""
    notification = notification_manager.create_abuse_notification(abuse_report)
    return notification_manager.send_notification(notification)


def send_ip_block_notification(ip_block: IPBlockList) -> Dict[str, Any]:
    """Send IP blocked notification."""
    notification = notification_manager.create_ip_block_notification(ip_block)
    return notification_manager.send_notification(notification)


def send_system_alert(title: str, message: str, priority: str = NotificationPriority.MEDIUM, 
                      data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Send system alert notification."""
    notification = notification_manager.create_system_alert_notification(title, message, priority, data)
    return notification_manager.send_notification(notification)


# Export classes and functions
__all__ = [
    'NotificationType',
    'NotificationPriority',
    'NotificationChannel',
    'WebSocketNotificationChannel',
    'EmailNotificationChannel',
    'SlackNotificationChannel',
    'SMSNotificationChannel',
    'Notification',
    'NotificationManager',
    'notification_manager',
    'send_rate_limit_notification',
    'send_abuse_notification',
    'send_ip_block_notification',
    'send_system_alert'
]
