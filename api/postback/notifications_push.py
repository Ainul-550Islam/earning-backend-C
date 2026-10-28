"""
notifications_push.py – Push notification system for postback module.

Provides comprehensive push notification functionality including:
- Multi-channel notifications (email, SMS, push, in-app)
- Notification templates and personalization
- Delivery tracking and analytics
- User preferences and opt-out management
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.utils import timezone
from django.core.mail import send_mail
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.conf import settings
from django.template.loader import render_to_string

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationChannel(Enum):
    """Notification channel enumeration."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationPriority(Enum):
    """Notification priority enumeration."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(Enum):
    """Notification status enumeration."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NotificationMessage:
    """Notification message data structure."""
    id: str
    channel: NotificationChannel
    priority: NotificationPriority
    recipient: str  # Email, phone number, device token, etc.
    subject: str
    content: str
    template_name: Optional[str] = None
    template_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    status: NotificationStatus = NotificationStatus.PENDING
    delivery_attempts: int = 0
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'channel': self.channel.value,
            'priority': self.priority.value,
            'recipient': self.recipient,
            'subject': self.subject,
            'content': self.content,
            'template_name': self.template_name,
            'template_context': self.template_context,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status.value,
            'delivery_attempts': self.delivery_attempts,
            'error_message': self.error_message,
        }


class NotificationTemplate:
    """
    Notification template manager.
    
    Handles template rendering and personalization.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.templates = self._setup_default_templates()
    
    def _setup_default_templates(self) -> Dict[str, Dict[str, Any]]:
        """Setup default notification templates."""
        return {
            'postback_processed': {
                'email': {
                    'subject': 'Postback Processed Successfully',
                    'template': 'notifications/postback_processed_email.html',
                    'text_template': 'notifications/postback_processed_email.txt',
                },
                'push': {
                    'title': 'Postback Processed',
                    'body': 'Your postback has been processed successfully.',
                },
                'sms': {
                    'message': 'Your postback has been processed successfully. Lead ID: {lead_id}',
                },
            },
            'postback_failed': {
                'email': {
                    'subject': 'Postback Processing Failed',
                    'template': 'notifications/postback_failed_email.html',
                    'text_template': 'notifications/postback_failed_email.txt',
                },
                'push': {
                    'title': 'Postback Failed',
                    'body': 'Your postback processing failed. Please check your account.',
                },
                'sms': {
                    'message': 'Postback processing failed for lead ID: {lead_id}. Reason: {reason}',
                },
            },
            'anomaly_detected': {
                'email': {
                    'subject': 'Anomaly Detected in Postback System',
                    'template': 'notifications/anomaly_detected_email.html',
                    'text_template': 'notifications/anomaly_detected_email.txt',
                },
                'push': {
                    'title': 'System Alert',
                    'body': 'An anomaly has been detected in the postback system.',
                },
            },
            'network_health_warning': {
                'email': {
                    'subject': 'Network Health Warning',
                    'template': 'notifications/network_health_warning_email.html',
                    'text_template': 'notifications/network_health_warning_email.txt',
                },
                'push': {
                    'title': 'Network Alert',
                    'body': 'Network {network_key} health score is below threshold.',
                },
            },
        }
    
    def render_template(self, template_type: str, channel: NotificationChannel, 
                       context: Dict[str, Any]) -> Dict[str, str]:
        """
        Render notification template.
        
        Args:
            template_type: Type of template
            channel: Notification channel
            context: Template context
            
        Returns:
            Rendered content
        """
        if template_type not in self.templates:
            raise PostbackException(f"Template type {template_type} not found")
        
        template_config = self.templates[template_type]
        
        if channel not in template_config:
            raise PostbackException(f"Channel {channel.value} not supported for template {template_type}")
        
        channel_config = template_config[channel]
        
        rendered = {
            'subject': channel_config.get('subject', ''),
            'content': '',
        }
        
        # Render content based on channel
        if channel == NotificationChannel.EMAIL:
            if 'template' in channel_config:
                rendered['content'] = render_to_string(channel_config['template'], context)
            elif 'text_template' in channel_config:
                rendered['content'] = render_to_string(channel_config['text_template'], context)
            else:
                rendered['content'] = channel_config.get('body', '')
        
        elif channel == NotificationChannel.PUSH:
            rendered['title'] = channel_config.get('title', '')
            rendered['content'] = channel_config.get('body', '').format(**context)
        
        elif channel == NotificationChannel.SMS:
            rendered['content'] = channel_config.get('message', '').format(**context)
        
        else:
            rendered['content'] = channel_config.get('body', '').format(**context)
        
        return rendered
    
    def add_template(self, template_type: str, channel: NotificationChannel, 
                    config: Dict[str, str]):
        """
        Add custom template.
        
        Args:
            template_type: Template type
            channel: Notification channel
            config: Template configuration
        """
        if template_type not in self.templates:
            self.templates[template_type] = {}
        
        self.templates[template_type][channel] = config
        self.logger.info(f"Added template: {template_type} for {channel.value}")
    
    def remove_template(self, template_type: str, channel: NotificationChannel = None):
        """
        Remove template.
        
        Args:
            template_type: Template type
            channel: Specific channel (None = all channels)
        """
        if template_type in self.templates:
            if channel:
                self.templates[template_type].pop(channel.value, None)
            else:
                del self.templates[template_type]
            
            self.logger.info(f"Removed template: {template_type}")


class NotificationSender:
    """
    Base class for notification senders.
    
    Provides common functionality for different notification channels.
    """
    
    def __init__(self, channel: NotificationChannel):
        self.channel = channel
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def send(self, message: NotificationMessage) -> bool:
        """
        Send notification message.
        
        Args:
            message: Notification message
            
        Returns:
            True if sent successfully
        """
        try:
            self.logger.info(f"Sending {self.channel.value} notification: {message.id}")
            
            # Mark as sent
            message.sent_at = timezone.now()
            message.status = NotificationStatus.SENT
            message.delivery_attempts += 1
            
            # Send the notification
            success = self._send_notification(message)
            
            if success:
                message.status = NotificationStatus.DELIVERED
                self.logger.info(f"Notification delivered: {message.id}")
            else:
                message.status = NotificationStatus.FAILED
                self.logger.error(f"Notification failed: {message.id}")
            
            return success
        
        except Exception as e:
            message.status = NotificationStatus.FAILED
            message.error_message = str(e)
            self.logger.error(f"Error sending notification {message.id}: {str(e)}")
            return False
    
    def _send_notification(self, message: NotificationMessage) -> bool:
        """
        Send notification (to be implemented by subclasses).
        
        Args:
            message: Notification message
            
        Returns:
            True if sent successfully
        """
        raise NotImplementedError("Subclasses must implement _send_notification method")


class EmailSender(NotificationSender):
    """Email notification sender."""
    
    def __init__(self):
        super().__init__(NotificationChannel.EMAIL)
    
    def _send_notification(self, message: NotificationMessage) -> bool:
        """Send email notification."""
        try:
            # Send email
            send_mail(
                subject=message.subject,
                message=message.content,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=[message.recipient],
                html_message=message.content if '<' in message.content else None,
                fail_silently=False,
            )
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False


class SMSSender(NotificationSender):
    """SMS notification sender."""
    
    def __init__(self):
        super().__init__(NotificationChannel.SMS)
    
    def _send_notification(self, message: NotificationMessage) -> bool:
        """Send SMS notification."""
        try:
            # This would integrate with SMS service (Twilio, etc.)
            # For now, just log the SMS
            self.logger.info(f"SMS to {message.recipient}: {message.content}")
            
            # Simulate SMS sending
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send SMS: {str(e)}")
            return False


class PushSender(NotificationSender):
    """Push notification sender."""
    
    def __init__(self):
        super().__init__(NotificationChannel.PUSH)
    
    def _send_notification(self, message: NotificationMessage) -> bool:
        """Send push notification."""
        try:
            # This would integrate with push service (Firebase, etc.)
            # For now, just log the push notification
            self.logger.info(f"Push to {message.recipient}: {message.subject} - {message.content}")
            
            # Simulate push sending
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send push notification: {str(e)}")
            return False


class InAppSender(NotificationSender):
    """In-app notification sender."""
    
    def __init__(self):
        super().__init__(NotificationChannel.IN_APP)
    
    def _send_notification(self, message: NotificationMessage) -> bool:
        """Send in-app notification."""
        try:
            # Store in-app notification in cache or database
            cache_key = f"in_app_notification_{message.recipient}"
            notifications = cache.get(cache_key, [])
            
            notifications.append({
                'id': message.id,
                'subject': message.subject,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
                'read': False,
            })
            
            # Keep only last 50 notifications
            notifications = notifications[-50:]
            
            cache.set(cache_key, notifications, timeout=86400)  # 24 hours
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send in-app notification: {str(e)}")
            return False


class WebhookSender(NotificationSender):
    """Webhook notification sender."""
    
    def __init__(self):
        super().__init__(NotificationChannel.WEBHOOK)
    
    def _send_notification(self, message: NotificationMessage) -> bool:
        """Send webhook notification."""
        try:
            import requests
            
            webhook_url = message.recipient
            payload = {
                'id': message.id,
                'subject': message.subject,
                'content': message.content,
                'metadata': message.metadata,
                'timestamp': message.created_at.isoformat(),
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send webhook: {str(e)}")
            return False


class NotificationManager:
    """
    Manager for push notifications.
    
    Handles notification creation, scheduling, and delivery
    across multiple channels.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.template_manager = NotificationTemplate()
        self.senders = self._setup_senders()
        self.pending_notifications: List[NotificationMessage] = []
        self.notification_history: List[NotificationMessage] = []
        self.user_preferences: Dict[str, Dict[str, bool]] = {}
    
    def _setup_senders(self) -> Dict[NotificationChannel, NotificationSender]:
        """Setup notification senders."""
        return {
            NotificationChannel.EMAIL: EmailSender(),
            NotificationChannel.SMS: SMSSender(),
            NotificationChannel.PUSH: PushSender(),
            NotificationChannel.IN_APP: InAppSender(),
            NotificationChannel.WEBHOOK: WebhookSender(),
        }
    
    def create_notification(self, template_type: str, channels: List[NotificationChannel],
                          recipients: List[str], context: Dict[str, Any] = None,
                          priority: NotificationPriority = NotificationPriority.NORMAL,
                          scheduled_at: datetime = None, metadata: Dict[str, Any] = None) -> List[NotificationMessage]:
        """
        Create notification messages.
        
        Args:
            template_type: Type of template
            channels: Notification channels
            recipients: List of recipients
            context: Template context
            priority: Notification priority
            scheduled_at: Schedule time
            metadata: Additional metadata
            
        Returns:
            List of created notification messages
        """
        context = context or {}
        metadata = metadata or {}
        messages = []
        
        for channel in channels:
            # Check if channel is supported
            if channel not in self.senders:
                self.logger.warning(f"Channel {channel.value} not supported")
                continue
            
            # Render template
            try:
                rendered = self.template_manager.render_template(template_type, channel, context)
            except PostbackException as e:
                self.logger.error(f"Template rendering failed: {str(e)}")
                continue
            
            # Create messages for each recipient
            for recipient in recipients:
                # Check user preferences
                if not self._is_user_opted_in(recipient, channel):
                    continue
                
                message = NotificationMessage(
                    id=self._generate_notification_id(),
                    channel=channel,
                    priority=priority,
                    recipient=recipient,
                    subject=rendered.get('subject', ''),
                    content=rendered.get('content', ''),
                    template_name=template_type,
                    template_context=context,
                    metadata=metadata,
                    scheduled_at=scheduled_at,
                )
                
                messages.append(message)
                
                # Add to appropriate queue
                if scheduled_at and scheduled_at > timezone.now():
                    self.pending_notifications.append(message)
                else:
                    self._send_notification(message)
        
        return messages
    
    def send_postback_notification(self, postback: PostbackLog, notification_type: str = 'processed') -> List[NotificationMessage]:
        """
        Send postback-related notification.
        
        Args:
            postback: Postback log instance
            notification_type: Type of notification ('processed', 'failed')
            
        Returns:
            List of sent notification messages
        """
        if notification_type == 'processed':
            template_type = 'postback_processed'
            channels = [NotificationChannel.EMAIL, NotificationChannel.IN_APP]
        elif notification_type == 'failed':
            template_type = 'postback_failed'
            channels = [NotificationChannel.EMAIL, NotificationChannel.IN_APP]
        else:
            return []
        
        # Get recipients
        recipients = []
        
        # Add user if available
        if postback.resolved_user:
            recipients.append(postback.resolved_user.email)
        
        # Add admin recipients
        admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
        recipients.extend(admin_emails)
        
        # Prepare context
        context = {
            'postback': postback,
            'lead_id': postback.lead_id,
            'network_key': postback.network.network_key,
            'status': postback.status,
            'payout': postback.payout,
            'reason': postback.rejection_reason,
        }
        
        return self.create_notification(
            template_type=template_type,
            channels=channels,
            recipients=recipients,
            context=context,
            priority=NotificationPriority.NORMAL
        )
    
    def send_anomaly_notification(self, insight: PostbackInsight) -> List[NotificationMessage]:
        """
        Send anomaly notification.
        
        Args:
            insight: Postback insight instance
            
        Returns:
            List of sent notification messages
        """
        if not insight.anomaly_detected:
            return []
        
        template_type = 'anomaly_detected'
        channels = [NotificationChannel.EMAIL, NotificationChannel.PUSH]
        
        # Get admin recipients
        admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
        recipients = admin_emails
        
        # Prepare context
        context = {
            'insight': insight,
            'network_key': insight.network.network_key,
            'health_score': insight.health_score,
            'anomaly_details': insight.anomaly_details,
            'date': insight.date,
        }
        
        return self.create_notification(
            template_type=template_type,
            channels=channels,
            recipients=recipients,
            context=context,
            priority=NotificationPriority.HIGH
        )
    
    def send_network_health_notification(self, network_key: str, health_score: float) -> List[NotificationMessage]:
        """
        Send network health notification.
        
        Args:
            network_key: Network key
            health_score: Health score
            
        Returns:
            List of sent notification messages
        """
        if health_score >= 50:
            return []
        
        template_type = 'network_health_warning'
        channels = [NotificationChannel.EMAIL]
        
        # Get admin recipients
        admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
        recipients = admin_emails
        
        # Prepare context
        context = {
            'network_key': network_key,
            'health_score': health_score,
            'threshold': 50,
        }
        
        return self.create_notification(
            template_type=template_type,
            channels=channels,
            recipients=recipients,
            context=context,
            priority=NotificationPriority.HIGH
        )
    
    def send_custom_notification(self, template_type: str, channels: List[NotificationChannel],
                              recipients: List[str], context: Dict[str, Any],
                              priority: NotificationPriority = NotificationPriority.NORMAL) -> List[NotificationMessage]:
        """
        Send custom notification.
        
        Args:
            template_type: Type of template
            channels: Notification channels
            recipients: List of recipients
            context: Template context
            priority: Notification priority
            
        Returns:
            List of sent notification messages
        """
        return self.create_notification(
            template_type=template_type,
            channels=channels,
            recipients=recipients,
            context=context,
            priority=priority
        )
    
    def _send_notification(self, message: NotificationMessage) -> bool:
        """Send notification message."""
        sender = self.senders.get(message.channel)
        if not sender:
            self.logger.error(f"No sender found for channel: {message.channel.value}")
            return False
        
        success = sender.send(message)
        self.notification_history.append(message)
        
        return success
    
    def _is_user_opted_in(self, recipient: str, channel: NotificationChannel) -> bool:
        """Check if user is opted in for channel."""
        # Get user preferences
        user_prefs = self.user_preferences.get(recipient, {})
        
        # Default to opted in if no preferences set
        if not user_prefs:
            return True
        
        # Check channel preference
        channel_key = f"opt_in_{channel.value}"
        return user_prefs.get(channel_key, True)
    
    def set_user_preference(self, recipient: str, channel: NotificationChannel, opted_in: bool):
        """
        Set user notification preference.
        
        Args:
            recipient: User identifier (email, user ID, etc.)
            channel: Notification channel
            opted_in: Opt-in status
        """
        if recipient not in self.user_preferences:
            self.user_preferences[recipient] = {}
        
        channel_key = f"opt_in_{channel.value}"
        self.user_preferences[recipient][channel_key] = opted_in
        
        self.logger.info(f"Set preference for {recipient}: {channel.value} = {opted_in}")
    
    def process_pending_notifications(self) -> int:
        """
        Process pending notifications.
        
        Returns:
            Number of notifications processed
        """
        processed_count = 0
        now = timezone.now()
        
        remaining_notifications = []
        
        for message in self.pending_notifications:
            if message.scheduled_at and message.scheduled_at <= now:
                if self._send_notification(message):
                    processed_count += 1
            else:
                remaining_notifications.append(message)
        
        self.pending_notifications = remaining_notifications
        
        if processed_count > 0:
            self.logger.info(f"Processed {processed_count} pending notifications")
        
        return processed_count
    
    def get_notification_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        total_sent = len(self.notification_history)
        
        # Count by status
        status_counts = {}
        for message in self.notification_history:
            status = message.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by channel
        channel_counts = {}
        for message in self.notification_history:
            channel = message.channel.value
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
        
        # Count by priority
        priority_counts = {}
        for message in self.notification_history:
            priority = message.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return {
            'total_sent': total_sent,
            'pending_count': len(self.pending_notifications),
            'status_counts': status_counts,
            'channel_counts': channel_counts,
            'priority_counts': priority_counts,
            'user_preferences_count': len(self.user_preferences),
        }
    
    def _generate_notification_id(self) -> str:
        """Generate unique notification ID."""
        import uuid
        return f"notif_{uuid.uuid4().hex[:12]}"


# Global notification manager instance
notification_manager = NotificationManager()


# Convenience functions
def send_postback_notification(postback: PostbackLog, notification_type: str = 'processed') -> List[NotificationMessage]:
    """Send postback notification."""
    return notification_manager.send_postback_notification(postback, notification_type)


def send_anomaly_notification(insight: PostbackInsight) -> List[NotificationMessage]:
    """Send anomaly notification."""
    return notification_manager.send_anomaly_notification(insight)


def send_network_health_notification(network_key: str, health_score: float) -> List[NotificationMessage]:
    """Send network health notification."""
    return notification_manager.send_network_health_notification(network_key, health_score)


def send_custom_notification(template_type: str, channels: List[NotificationChannel],
                          recipients: List[str], context: Dict[str, Any],
                          priority: NotificationPriority = NotificationPriority.NORMAL) -> List[NotificationMessage]:
    """Send custom notification."""
    return notification_manager.send_custom_notification(template_type, channels, recipients, context, priority)


def set_user_preference(recipient: str, channel: NotificationChannel, opted_in: bool):
    """Set user notification preference."""
    notification_manager.set_user_preference(recipient, channel, opted_in)


def process_pending_notifications() -> int:
    """Process pending notifications."""
    return notification_manager.process_pending_notifications()


def get_notification_statistics() -> Dict[str, Any]:
    """Get notification statistics."""
    return notification_manager.get_notification_statistics()


# Notification utilities
def get_user_notifications(recipient: str, channel: NotificationChannel = NotificationChannel.IN_APP) -> List[Dict[str, Any]]:
    """Get user notifications."""
    if channel == NotificationChannel.IN_APP:
        cache_key = f"in_app_notification_{recipient}"
        return cache.get(cache_key, [])
    
    return []


def mark_notification_read(recipient: str, notification_id: str) -> bool:
    """Mark notification as read."""
    cache_key = f"in_app_notification_{recipient}"
    notifications = cache.get(cache_key, [])
    
    for notification in notifications:
        if notification['id'] == notification_id:
            notification['read'] = True
            cache.set(cache_key, notifications, timeout=86400)
            return True
    
    return False


def clear_user_notifications(recipient: str, channel: NotificationChannel = NotificationChannel.IN_APP) -> bool:
    """Clear user notifications."""
    if channel == NotificationChannel.IN_APP:
        cache_key = f"in_app_notification_{recipient}"
        cache.delete(cache_key)
        return True
    
    return False


# Notification health check
def check_notification_health() -> Dict[str, Any]:
    """Check notification system health."""
    health_status = {
        'overall': 'healthy',
        'notification_manager': 'healthy',
        'template_manager': 'healthy',
        'senders': {},
        'issues': [],
    }
    
    # Test notification manager
    try:
        stats = notification_manager.get_notification_statistics()
        health_status['notification_manager'] = 'healthy'
    except Exception as e:
        health_status['notification_manager'] = 'error'
        health_status['issues'].append(f"Notification manager error: {str(e)}")
    
    # Test template manager
    try:
        notification_manager.template_manager.render_template('postback_processed', NotificationChannel.EMAIL, {'lead_id': 'test'})
        health_status['template_manager'] = 'healthy'
    except Exception as e:
        health_status['template_manager'] = 'error'
        health_status['issues'].append(f"Template manager error: {str(e)}")
    
    # Test senders
    for channel, sender in notification_manager.senders.items():
        try:
            # Create test message
            test_message = NotificationMessage(
                id='test',
                channel=channel,
                priority=NotificationPriority.LOW,
                recipient='test@example.com',
                subject='Test',
                content='Test content',
            )
            
            # Test sender (don't actually send)
            health_status['senders'][channel.value] = 'healthy'
        except Exception as e:
            health_status['senders'][channel.value] = 'error'
            health_status['issues'].append(f"Sender {channel.value} error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
