"""
Core Notification System for alerts app - Multi-channel notification management
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
import asyncio
import logging
import json
import uuid
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationStatus(Enum):
    """Notification status enumeration"""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class NotificationChannel(ABC):
    """Abstract base class for notification channels"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
        self.max_retries = config.get('max_retries', 3)
        self.timeout = config.get('timeout', 30)
        self.rate_limit = config.get('rate_limit', 100)  # messages per minute
        
    @abstractmethod
    async def send(self, notification: 'Notification') -> Dict[str, Any]:
        """Send notification through this channel"""
        pass
    
    @abstractmethod
    def validate_config(self) -> Dict[str, Any]:
        """Validate channel configuration"""
        pass
    
    def get_channel_info(self) -> Dict[str, Any]:
        """Get channel information"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'rate_limit': self.rate_limit,
            'config': self.config
        }


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_host = config.get('smtp_host', 'localhost')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.use_tls = config.get('use_tls', True)
        self.from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL)
        
    async def send(self, notification: 'Notification') -> Dict[str, Any]:
        """Send email notification"""
        try:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            
            # Prepare email content
            subject = notification.subject
            message = notification.message
            html_message = notification.html_message
            
            recipient = notification.recipient
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=[recipient],
                html_message=html_message,
                fail_silently=False
            )
            
            return {
                'success': True,
                'channel': self.name,
                'recipient': recipient,
                'sent_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return {
                'success': False,
                'channel': self.name,
                'error': 'Operation failed',
                'recipient': notification.recipient
            }
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate email configuration"""
        errors = []
        
        if not self.smtp_host:
            errors.append("SMTP host is required")
        
        if not self.from_email:
            errors.append("From email is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class SMSNotificationChannel(NotificationChannel):
    """SMS notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.api_url = config.get('api_url')
        self.from_number = config.get('from_number')
        
    async def send(self, notification: 'Notification') -> Dict[str, Any]:
        """Send SMS notification"""
        try:
            import requests
            
            # Prepare SMS payload
            payload = {
                'to': notification.recipient,
                'from': self.from_number,
                'body': notification.message,
                'api_key': self.api_key
            }
            
            # Send SMS
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'channel': self.name,
                    'recipient': notification.recipient,
                    'sent_at': timezone.now().isoformat(),
                    'sms_id': response.json().get('sms_id')
                }
            else:
                return {
                    'success': False,
                    'channel': self.name,
                    'error': f"SMS API error: {response.status_code}",
                    'recipient': notification.recipient
                }
                
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return {
                'success': False,
                'channel': self.name,
                'error': 'Operation failed',
                'recipient': notification.recipient
            }
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate SMS configuration"""
        errors = []
        
        if not self.api_key:
            errors.append("API key is required")
        
        if not self.api_url:
            errors.append("API URL is required")
        
        if not self.from_number:
            errors.append("From number is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url')
        self.channel = config.get('channel', '#alerts')
        self.username = config.get('username', 'AlertBot')
        
    async def send(self, notification: 'Notification') -> Dict[str, Any]:
        """Send Slack notification"""
        try:
            import requests
            
            # Prepare Slack payload
            payload = {
                'channel': self.channel,
                'username': self.username,
                'text': notification.subject,
                'attachments': [
                    {
                        'color': self._get_color_by_priority(notification.priority),
                        'text': notification.message,
                        'fields': [
                            {
                                'title': 'Priority',
                                'value': notification.priority.value,
                                'short': True
                            },
                            {
                                'title': 'Alert ID',
                                'value': str(notification.alert_id) if notification.alert_id else 'N/A',
                                'short': True
                            }
                        ],
                        'ts': int(timezone.now().timestamp())
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'channel': self.name,
                    'recipient': self.channel,
                    'sent_at': timezone.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'channel': self.name,
                    'error': f"Slack API error: {response.status_code}",
                    'recipient': self.channel
                }
                
        except Exception as e:
            logger.error(f"Slack send error: {e}")
            return {
                'success': False,
                'channel': self.name,
                'error': 'Operation failed',
                'recipient': self.channel
            }
    
    def _get_color_by_priority(self, priority: NotificationPriority) -> str:
        """Get Slack color by notification priority"""
        colors = {
            NotificationPriority.LOW: 'good',
            NotificationPriority.NORMAL: 'good',
            NotificationPriority.HIGH: 'warning',
            NotificationPriority.URGENT: 'danger',
            NotificationPriority.CRITICAL: 'danger'
        }
        return colors.get(priority, 'good')
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate Slack configuration"""
        errors = []
        
        if not self.webhook_url:
            errors.append("Webhook URL is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class WebhookNotificationChannel(NotificationChannel):
    """Webhook notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url')
        self.method = config.get('method', 'POST')
        self.headers = config.get('headers', {})
        self.auth_token = config.get('auth_token')
        
    async def send(self, notification: 'Notification') -> Dict[str, Any]:
        """Send webhook notification"""
        try:
            import requests
            
            # Prepare webhook payload
            payload = {
                'id': str(notification.id),
                'subject': notification.subject,
                'message': notification.message,
                'priority': notification.priority.value,
                'recipient': notification.recipient,
                'alert_id': notification.alert_id,
                'created_at': notification.created_at.isoformat(),
                'metadata': notification.metadata
            }
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'AlertSystem-Webhook/1.0',
                **self.headers
            }
            
            if self.auth_token:
                headers['Authorization'] = f"Bearer {self.auth_token}"
            
            # Send webhook
            response = requests.request(
                method=self.method,
                url=self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 201, 202]:
                return {
                    'success': True,
                    'channel': self.name,
                    'recipient': self.webhook_url,
                    'sent_at': timezone.now().isoformat(),
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'channel': self.name,
                    'error': f"Webhook error: {response.status_code}",
                    'recipient': self.webhook_url
                }
                
        except Exception as e:
            logger.error(f"Webhook send error: {e}")
            return {
                'success': False,
                'channel': self.name,
                'error': 'Operation failed',
                'recipient': self.webhook_url
            }
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate webhook configuration"""
        errors = []
        
        if not self.webhook_url:
            errors.append("Webhook URL is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class Notification:
    """Represents a notification"""
    
    def __init__(self, recipient: str, subject: str, message: str, 
                 channel: str = None, priority: NotificationPriority = NotificationPriority.NORMAL,
                 alert_id: int = None, html_message: str = None, metadata: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.recipient = recipient
        self.subject = subject
        self.message = message
        self.html_message = html_message
        self.channel = channel
        self.priority = priority
        self.alert_id = alert_id
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.status = NotificationStatus.PENDING
        self.attempts = 0
        self.last_attempt = None
        self.sent_at = None
        self.error_message = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'recipient': self.recipient,
            'subject': self.subject,
            'message': self.message,
            'html_message': self.html_message,
            'channel': self.channel,
            'priority': self.priority.value,
            'alert_id': self.alert_id,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value,
            'attempts': self.attempts,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message
        }
    
    def mark_sent(self):
        """Mark notification as sent"""
        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
    
    def mark_failed(self, error_message: str):
        """Mark notification as failed"""
        self.status = NotificationStatus.FAILED
        self.error_message = error_message
        self.last_attempt = timezone.now()
        self.attempts += 1
    
    def mark_retrying(self):
        """Mark notification as retrying"""
        self.status = NotificationStatus.RETRYING
        self.last_attempt = timezone.now()
        self.attempts += 1


class NotificationManager:
    """Main notification management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.channels = {}
        self.enabled = config.get('enabled', True)
        self.default_channel = config.get('default_channel', 'email')
        self.batch_size = config.get('batch_size', 100)
        self.retry_delay = config.get('retry_delay', 60)  # seconds
        
        # Initialize channels
        self._initialize_channels()
        
        # Notification queue
        self.queue = []
        self.processing = False
        
    def _initialize_channels(self):
        """Initialize notification channels"""
        channel_configs = self.config.get('channels', {})
        
        for channel_name, channel_config in channel_configs.items():
            channel_type = channel_config.get('type', 'email')
            
            if channel_type == 'email':
                channel = EmailNotificationChannel(channel_config)
            elif channel_type == 'sms':
                channel = SMSNotificationChannel(channel_config)
            elif channel_type == 'slack':
                channel = SlackNotificationChannel(channel_config)
            elif channel_type == 'webhook':
                channel = WebhookNotificationChannel(channel_config)
            else:
                logger.error(f"Unknown channel type: {channel_type}")
                continue
            
            self.channels[channel_name] = channel
            logger.info(f"Initialized notification channel: {channel_name}")
    
    def create_notification(self, recipient: str, subject: str, message: str,
                          channel: str = None, priority: NotificationPriority = NotificationPriority.NORMAL,
                          alert_id: int = None, **kwargs) -> Notification:
        """Create a new notification"""
        notification = Notification(
            recipient=recipient,
            subject=subject,
            message=message,
            channel=channel or self.default_channel,
            priority=priority,
            alert_id=alert_id,
            **kwargs
        )
        
        return notification
    
    async def send_notification(self, notification: Notification) -> Dict[str, Any]:
        """Send a notification"""
        if not self.enabled:
            return {
                'success': False,
                'error': 'Notification manager is disabled'
            }
        
        # Get channel
        channel = self.channels.get(notification.channel)
        if not channel:
            return {
                'success': False,
                'error': f'Channel {notification.channel} not found'
            }
        
        if not channel.enabled:
            return {
                'success': False,
                'error': f'Channel {notification.channel} is disabled'
            }
        
        # Update status
        notification.status = NotificationStatus.SENDING
        notification.last_attempt = timezone.now()
        
        # Send notification
        try:
            result = await channel.send(notification)
            
            if result['success']:
                notification.mark_sent()
                logger.info(f"Notification {notification.id} sent successfully")
            else:
                notification.mark_failed(result.get('error', 'Unknown error'))
                logger.error(f"Notification {notification.id} failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            notification.mark_failed(str(e))
            logger.error(f"Notification {notification.id} error: {e}")
            
            return {
                'success': False,
                'error': 'Operation failed',
                'notification_id': notification.id
            }
    
    async def send_batch(self, notifications: List[Notification]) -> Dict[str, Any]:
        """Send multiple notifications in batch"""
        results = {
            'total': len(notifications),
            'sent': 0,
            'failed': 0,
            'results': []
        }
        
        # Process in batches
        for i in range(0, len(notifications), self.batch_size):
            batch = notifications[i:i + self.batch_size]
            
            # Send batch concurrently
            tasks = []
            for notification in batch:
                task = asyncio.create_task(self.send_notification(notification))
                tasks.append(task)
            
            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    results['failed'] += 1
                    results['results'].append({
                        'success': False,
                        'error': str(result)
                    })
                elif result['success']:
                    results['sent'] += 1
                    results['results'].append(result)
                else:
                    results['failed'] += 1
                    results['results'].append(result)
        
        return results
    
    def queue_notification(self, notification: Notification):
        """Queue notification for later processing"""
        self.queue.append(notification)
        logger.info(f"Queued notification {notification.id}")
    
    async def process_queue(self) -> Dict[str, Any]:
        """Process notification queue"""
        if not self.queue:
            return {
                'processed': 0,
                'sent': 0,
                'failed': 0
            }
        
        # Get notifications from queue
        notifications = self.queue.copy()
        self.queue.clear()
        
        # Process batch
        results = await self.send_batch(notifications)
        
        # Retry failed notifications
        retry_notifications = []
        for i, result in enumerate(results['results']):
            if not result['success']:
                notification = notifications[i]
                channel = self.channels.get(notification.channel)
                
                if channel and notification.attempts < channel.max_retries:
                    notification.mark_retrying()
                    retry_notifications.append(notification)
        
        # Add retry notifications back to queue
        self.queue.extend(retry_notifications)
        
        return {
            'processed': len(notifications),
            'sent': results['sent'],
            'failed': results['failed'],
            'retrying': len(retry_notifications)
        }
    
    def get_channel_status(self) -> Dict[str, Any]:
        """Get status of all channels"""
        return {
            'manager_enabled': self.enabled,
            'total_channels': len(self.channels),
            'enabled_channels': len([c for c in self.channels.values() if c.enabled]),
            'queue_size': len(self.queue),
            'channels': {
                name: channel.get_channel_info()
                for name, channel in self.channels.items()
            },
            'timestamp': timezone.now().isoformat()
        }
    
    def add_channel(self, channel_name: str, channel: NotificationChannel):
        """Add notification channel"""
        self.channels[channel_name] = channel
        logger.info(f"Added notification channel: {channel_name}")
    
    def remove_channel(self, channel_name: str):
        """Remove notification channel"""
        if channel_name in self.channels:
            del self.channels[channel_name]
            logger.info(f"Removed notification channel: {channel_name}")
    
    def enable_channel(self, channel_name: str):
        """Enable notification channel"""
        channel = self.channels.get(channel_name)
        if channel:
            channel.enabled = True
            logger.info(f"Enabled notification channel: {channel_name}")
    
    def disable_channel(self, channel_name: str):
        """Disable notification channel"""
        channel = self.channels.get(channel_name)
        if channel:
            channel.enabled = False
            logger.info(f"Disabled notification channel: {channel_name}")


class NotificationService:
    """High-level notification service"""
    
    def __init__(self, notification_manager: NotificationManager):
        self.notification_manager = notification_manager
        
    async def send_alert_notification(self, alert_id: int, recipient: str, 
                                    subject: str, message: str, 
                                    channels: List[str] = None,
                                    priority: NotificationPriority = NotificationPriority.NORMAL) -> Dict[str, Any]:
        """Send alert notification"""
        channels = channels or [self.notification_manager.default_channel]
        results = []
        
        for channel in channels:
            notification = self.notification_manager.create_notification(
                recipient=recipient,
                subject=subject,
                message=message,
                channel=channel,
                priority=priority,
                alert_id=alert_id
            )
            
            result = await self.notification_manager.send_notification(notification)
            results.append(result)
        
        return {
            'alert_id': alert_id,
            'channels_sent': len([r for r in results if r['success']]),
            'channels_failed': len([r for r in results if not r['success']]),
            'results': results
        }
    
    async def send_system_notification(self, subject: str, message: str,
                                     recipients: List[str] = None,
                                     channels: List[str] = None) -> Dict[str, Any]:
        """Send system notification"""
        recipients = recipients or settings.ADMINS
        channels = channels or [self.notification_manager.default_channel]
        
        notifications = []
        for recipient in recipients:
            for channel in channels:
                notification = self.notification_manager.create_notification(
                    recipient=recipient[1],  # Email from ADMINS tuple
                    subject=subject,
                    message=message,
                    channel=channel,
                    priority=NotificationPriority.NORMAL
                )
                notifications.append(notification)
        
        return await self.notification_manager.send_batch(notifications)


# Global notification manager
notification_manager = None
notification_service = None


def get_notification_manager() -> Optional[NotificationManager]:
    """Get the global notification manager"""
    return notification_manager


def get_notification_service() -> Optional[NotificationService]:
    """Get the global notification service"""
    return notification_service


def initialize_notification_system():
    """Initialize notification system from settings"""
    from django.conf import settings
    
    global notification_manager, notification_service
    
    config = getattr(settings, 'NOTIFICATION_CONFIG', {
        'enabled': True,
        'default_channel': 'email',
        'batch_size': 100,
        'retry_delay': 60,
        'channels': {
            'email': {
                'type': 'email',
                'enabled': True,
                'smtp_host': 'smtp.gmail.com',
                'smtp_port': 587,
                'smtp_username': settings.EMAIL_HOST_USER,
                'smtp_password': settings.EMAIL_HOST_PASSWORD,
                'use_tls': True,
                'from_email': settings.DEFAULT_FROM_EMAIL
            },
            'slack': {
                'type': 'slack',
                'enabled': False,
                'webhook_url': '',
                'channel': '#alerts',
                'username': 'AlertBot'
            }
        }
    })
    
    try:
        notification_manager = NotificationManager(config)
        notification_service = NotificationService(notification_manager)
        logger.info("Notification system initialized")
    except Exception as e:
        logger.error(f"Error initializing notification system: {e}")


# Initialize on module import
try:
    initialize_notification_system()
except Exception as e:
    logger.error(f"Error initializing notification system: {e}")
