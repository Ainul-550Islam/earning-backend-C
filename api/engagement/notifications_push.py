# engagement/notifications_push.py
"""
Push notification system for engagement gamification.
Provides real-time notifications via various channels.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from api.engagement.models.checkin import DailyCheckIn

logger = logging.getLogger(__name__)

User = get_user_model()


class NotificationChannel(Enum):
    """Notification channels."""
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    WEBSOCKET = "websocket"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class PushNotification:
    """Push notification data structure."""
    title: str
    body: str
    icon: Optional[str] = None
    image: Optional[str] = None
    badge: Optional[str] = None
    sound: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    actions: List[Dict[str, str]] = field(default_factory=list)
    priority: NotificationPriority = NotificationPriority.NORMAL
    ttl: Optional[int] = None  # Time to live in seconds
    collapse_key: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None


class BaseNotificationProvider(ABC):
    """Base notification provider class."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def send(self, notification: PushNotification, user: User) -> Dict[str, Any]:
        """Send notification to user."""
        pass
    
    @abstractmethod
    def send_batch(self, notifications: List[PushNotification], users: List[User]) -> Dict[str, Any]:
        """Send notifications to multiple users."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class FCMProvider(BaseNotificationProvider):
    """Firebase Cloud Messaging provider."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("fcm", config)
        self.api_key = self.config.get('api_key')
        self.server_key = self.config.get('server_key')
    
    def send(self, notification: PushNotification, user: User) -> Dict[str, Any]:
        """Send push notification via FCM."""
        try:
            # Get user's FCM token
            fcm_token = self._get_user_fcm_token(user)
            if not fcm_token:
                return {
                    'success': False,
                    'error': 'No FCM token found for user',
                    'provider': self.name
                }
            
            # Prepare FCM payload
            payload = self._prepare_fcm_payload(notification, fcm_token)
            
            # Send to FCM
            response = self._send_to_fcm(payload)
            
            return {
                'success': response.get('success', False),
                'message_id': response.get('message_id'),
                'error': response.get('error'),
                'provider': self.name
            }
            
        except Exception as exc:
            self.logger.error(f"Failed to send FCM notification: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'provider': self.name
            }
    
    def send_batch(self, notifications: List[PushNotification], users: List[User]) -> Dict[str, Any]:
        """Send push notifications to multiple users via FCM."""
        results = []
        
        for notification, user in zip(notifications, users):
            result = self.send(notification, user)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count == len(results),
            'total_sent': len(results),
            'successful': success_count,
            'failed': len(results) - success_count,
            'provider': self.name,
            'results': results
        }
    
    def is_available(self) -> bool:
        """Check if FCM provider is available."""
        return bool(self.api_key or self.server_key)
    
    def _get_user_fcm_token(self, user: User) -> Optional[str]:
        """Get user's FCM token."""
        try:
            # This would get the user's FCM token from your user profile or device tokens table
            # For now, it's a placeholder
            return getattr(user, 'fcm_token', None)
        except Exception:
            return None
    
    def _prepare_fcm_payload(self, notification: PushNotification, fcm_token: str) -> Dict[str, Any]:
        """Prepare FCM payload."""
        payload = {
            'to': fcm_token,
            'notification': {
                'title': notification.title,
                'body': notification.body,
                'icon': notification.icon,
                'image': notification.image,
                'badge': notification.badge,
                'sound': notification.sound or 'default',
            },
            'data': notification.data,
            'priority': notification.priority.value.upper(),
        }
        
        if notification.actions:
            payload['notification']['actions'] = notification.actions
        
        if notification.ttl:
            payload['time_to_live'] = notification.ttl
        
        if notification.collapse_key:
            payload['collapse_key'] = notification.collapse_key
        
        if notification.tags:
            payload['notification']['tag'] = ','.join(notification.tags)
        
        return payload
    
    def _send_to_fcm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send payload to FCM."""
        try:
            import requests
            
            url = "https://fcm.googleapis.com/fcm/send"
            headers = {
                'Authorization': f'key={self.server_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response_data = response.json()
            
            if response.status_code == 200:
                if response_data.get('success') == 1:
                    return {
                        'success': True,
                        'message_id': response_data.get('results', [{}])[0].get('message_id')
                    }
                else:
                    return {
                        'success': False,
                        'error': response_data.get('results', [{}])[0].get('error')
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class APNSProvider(BaseNotificationProvider):
    """Apple Push Notification Service provider."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("apns", config)
        self.cert_file = self.config.get('cert_file')
        self.key_file = self.config.get('key_file')
        self.use_sandbox = self.config.get('use_sandbox', True)
    
    def send(self, notification: PushNotification, user: User) -> Dict[str, Any]:
        """Send push notification via APNS."""
        try:
            # Get user's APNS token
            apns_token = self._get_user_apns_token(user)
            if not apns_token:
                return {
                    'success': False,
                    'error': 'No APNS token found for user',
                    'provider': self.name
                }
            
            # Prepare APNS payload
            payload = self._prepare_apns_payload(notification)
            
            # Send to APNS
            response = self._send_to_apns(payload, apns_token)
            
            return {
                'success': response.get('success', False),
                'message_id': response.get('message_id'),
                'error': response.get('error'),
                'provider': self.name
            }
            
        except Exception as exc:
            self.logger.error(f"Failed to send APNS notification: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'provider': self.name
            }
    
    def send_batch(self, notifications: List[PushNotification], users: List[User]) -> Dict[str, Any]:
        """Send push notifications to multiple users via APNS."""
        results = []
        
        for notification, user in zip(notifications, users):
            result = self.send(notification, user)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count == len(results),
            'total_sent': len(results),
            'successful': success_count,
            'failed': len(results) - success_count,
            'provider': self.name,
            'results': results
        }
    
    def is_available(self) -> bool:
        """Check if APNS provider is available."""
        return bool(self.cert_file and self.key_file)
    
    def _get_user_apns_token(self, user: User) -> Optional[str]:
        """Get user's APNS token."""
        try:
            # This would get the user's APNS token from your user profile or device tokens table
            # For now, it's a placeholder
            return getattr(user, 'apns_token', None)
        except Exception:
            return None
    
    def _prepare_apns_payload(self, notification: PushNotification) -> Dict[str, Any]:
        """Prepare APNS payload."""
        payload = {
            'aps': {
                'alert': {
                    'title': notification.title,
                    'body': notification.body,
                },
                'sound': notification.sound or 'default',
                'badge': notification.badge,
                'priority': notification.priority.value,
            },
            'data': notification.data
        }
        
        if notification.icon:
            payload['aps']['alert']['title-loc-key'] = notification.icon
        
        if notification.actions:
            payload['aps']['category'] = notification.actions[0].get('id', 'DEFAULT')
        
        return payload
    
    def _send_to_apns(self, payload: Dict[str, Any], apns_token: str) -> Dict[str, Any]:
        """Send payload to APNS."""
        try:
            # This would use the APNS library to send the notification
            # For now, it's a placeholder
            
            if self.use_sandbox:
                url = "https://api.development.push.apple.com/3/device/{}".format(apns_token)
            else:
                url = "https://api.push.apple.com/3/device/{}".format(apns_token)
            
            # Mock response
            return {
                'success': True,
                'message_id': 'mock_apns_id'
            }
            
        except Exception as exc:
            return {
                'success': False,
                'error': str(exc)
            }


class WebSocketProvider(BaseNotificationProvider):
    """WebSocket notification provider."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("websocket", config)
        self.channel_layer = self.config.get('channel_layer')
    
    def send(self, notification: PushNotification, user: User) -> Dict[str, Any]:
        """Send notification via WebSocket."""
        try:
            from channels.layers import get_channel_layer
            
            channel_layer = get_channel_layer()
            
            # Send to user's WebSocket channel
            channel_name = f"user_{user.id}"
            
            message = {
                'type': 'notification',
                'notification': {
                    'title': notification.title,
                    'body': notification.body,
                    'icon': notification.icon,
                    'data': notification.data,
                    'timestamp': timezone.now().isoformat(),
                }
            }
            
            # Send message
            channel_layer.group_send(
                channel_name,
                {
                    'type': 'notification.message',
                    'message': message
                }
            )
            
            return {
                'success': True,
                'channel': channel_name,
                'provider': self.name
            }
            
        except Exception as exc:
            self.logger.error(f"Failed to send WebSocket notification: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'provider': self.name
            }
    
    def send_batch(self, notifications: List[PushNotification], users: List[User]) -> Dict[str, Any]:
        """Send notifications to multiple users via WebSocket."""
        results = []
        
        for notification, user in zip(notifications, users):
            result = self.send(notification, user)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count == len(results),
            'total_sent': len(results),
            'successful': success_count,
            'failed': len(results) - success_count,
            'provider': self.name,
            'results': results
        }
    
    def is_available(self) -> bool:
        """Check if WebSocket provider is available."""
        try:
            from channels.layers import get_channel_layer
            return get_channel_layer() is not None
        except ImportError:
            return False


class EmailProvider(BaseNotificationProvider):
    """Email notification provider."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("email", config)
        self.from_email = self.config.get('from_email', settings.DEFAULT_FROM_EMAIL)
    
    def send(self, notification: PushNotification, user: User) -> Dict[str, Any]:
        """Send notification via email."""
        try:
            from django.core.mail import send_mail
            
            subject = notification.title
            message = notification.body
            html_message = self._prepare_html_message(notification)
            
            send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
            
            return {
                'success': True,
                'email': user.email,
                'provider': self.name
            }
            
        except Exception as exc:
            self.logger.error(f"Failed to send email notification: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'provider': self.name
            }
    
    def send_batch(self, notifications: List[PushNotification], users: List[User]) -> Dict[str, Any]:
        """Send notifications to multiple users via email."""
        results = []
        
        for notification, user in zip(notifications, users):
            result = self.send(notification, user)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count == len(results),
            'total_sent': len(results),
            'successful': success_count,
            'failed': len(results) - success_count,
            'provider': self.name,
            'results': results
        }
    
    def is_available(self) -> bool:
        """Check if email provider is available."""
        return bool(settings.EMAIL_HOST and settings.EMAIL_PORT)
    
    def _prepare_html_message(self, notification: PushNotification) -> str:
        """Prepare HTML email message."""
        html_template = f"""
        <html>
        <head>
            <title>{notification.title}</title>
        </head>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                    <h2 style="color: #333; margin: 0 0 10px 0;">{notification.title}</h2>
                    <p style="color: #666; margin: 0 0 20px 0;">{notification.body}</p>
                    {self._render_notification_data(notification.data)}
                </div>
                <div style="text-align: center; margin-top: 20px; color: #999; font-size: 12px;">
                    <p>This notification was sent by the Engagement System</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html_template
    
    def _render_notification_data(self, data: Dict[str, Any]) -> str:
        """Render notification data as HTML."""
        if not data:
            return ""
        
        html = "<div style='margin-top: 20px;'>"
        html += "<h3 style='color: #333; margin: 0 0 10px 0;'>Details:</h3>"
        html += "<table style='width: 100%; border-collapse: collapse;'>"
        
        for key, value in data.items():
            html += f"""
            <tr style='border-bottom: 1px solid #eee;'>
                <td style='padding: 8px; font-weight: bold; color: #555;'>{key}:</td>
                <td style='padding: 8px; color: #666;'>{value}</td>
            </tr>
            """
        
        html += "</table></div>"
        return html


class WebhookProvider(BaseNotificationProvider):
    """Webhook notification provider."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("webhook", config)
        self.webhook_url = self.config.get('url')
        self.headers = self.config.get('headers', {})
        self.timeout = self.config.get('timeout', 10)
    
    def send(self, notification: PushNotification, user: User) -> Dict[str, Any]:
        """Send notification via webhook."""
        try:
            import requests
            
            payload = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'notification': {
                    'title': notification.title,
                    'body': notification.body,
                    'icon': notification.icon,
                    'data': notification.data,
                    'priority': notification.priority.value,
                    'timestamp': timezone.now().isoformat(),
                }
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'provider': self.name
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'provider': self.name
                }
                
        except Exception as exc:
            self.logger.error(f"Failed to send webhook notification: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'provider': self.name
            }
    
    def send_batch(self, notifications: List[PushNotification], users: List[User]) -> Dict[str, Any]:
        """Send notifications to multiple users via webhook."""
        results = []
        
        for notification, user in zip(notifications, users):
            result = self.send(notification, user)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count == len(results),
            'total_sent': len(results),
            'successful': success_count,
            'failed': len(results) - success_count,
            'provider': self.name,
            'results': results
        }
    
    def is_available(self) -> bool:
        """Check if webhook provider is available."""
        return bool(self.webhook_url)


class PushNotificationManager:
    """Manager for push notifications."""
    
    def __init__(self):
        self.providers = {}
        self.default_providers = []
        self._setup_providers()
    
    def _setup_providers(self):
        """Setup notification providers."""
        # Setup FCM provider
        fcm_config = getattr(settings, 'FCM_CONFIG', {})
        if fcm_config:
            fcm_provider = FCMProvider(fcm_config)
            self.providers['fcm'] = fcm_provider
            if fcm_provider.is_available():
                self.default_providers.append('fcm')
        
        # Setup APNS provider
        apns_config = getattr(settings, 'APNS_CONFIG', {})
        if apns_config:
            apns_provider = APNSProvider(apns_config)
            self.providers['apns'] = apns_provider
            if apns_provider.is_available():
                self.default_providers.append('apns')
        
        # Setup WebSocket provider
        websocket_config = getattr(settings, 'WEBSOCKET_CONFIG', {})
        websocket_provider = WebSocketProvider(websocket_config)
        self.providers['websocket'] = websocket_provider
        if websocket_provider.is_available():
            self.default_providers.append('websocket')
        
        # Setup email provider
        email_config = getattr(settings, 'EMAIL_CONFIG', {})
        email_provider = EmailProvider(email_config)
        self.providers['email'] = email_provider
        if email_provider.is_available():
            self.default_providers.append('email')
        
        # Setup webhook provider
        webhook_config = getattr(settings, 'WEBHOOK_CONFIG', {})
        if webhook_config:
            webhook_provider = WebhookProvider(webhook_config)
            self.providers['webhook'] = webhook_provider
            if webhook_provider.is_available():
                self.default_providers.append('webhook')
    
    def send_notification(self, notification: PushNotification, user: User, 
                         channels: List[NotificationChannel] = None) -> Dict[str, Any]:
        """Send notification to user via specified channels."""
        if channels is None:
            # Use default providers
            channels = [NotificationChannel(p) for p in self.default_providers]
        
        results = {}
        
        for channel in channels:
            provider_name = channel.value
            provider = self.providers.get(provider_name)
            
            if provider and provider.is_available():
                try:
                    result = provider.send(notification, user)
                    results[provider_name] = result
                except Exception as exc:
                    self.logger.error(f"Failed to send notification via {provider_name}: {exc}")
                    results[provider_name] = {
                        'success': False,
                        'error': str(exc),
                        'provider': provider_name
                    }
            else:
                results[provider_name] = {
                    'success': False,
                    'error': f'Provider {provider_name} not available',
                    'provider': provider_name
                }
        
        # Determine overall success
        success_count = sum(1 for r in results.values() if r['success'])
        
        return {
            'success': success_count > 0,
            'total_channels': len(channels),
            'successful_channels': success_count,
            'failed_channels': len(channels) - success_count,
            'results': results
        }
    
    def send_batch_notifications(self, notifications: List[PushNotification], 
                                users: List[User], channels: List[NotificationChannel] = None) -> Dict[str, Any]:
        """Send notifications to multiple users."""
        if channels is None:
            channels = [NotificationChannel(p) for p in self.default_providers]
        
        results = {}
        
        for channel in channels:
            provider_name = channel.value
            provider = self.providers.get(provider_name)
            
            if provider and provider.is_available():
                try:
                    result = provider.send_batch(notifications, users)
                    results[provider_name] = result
                except Exception as exc:
                    self.logger.error(f"Failed to send batch notifications via {provider_name}: {exc}")
                    results[provider_name] = {
                        'success': False,
                        'error': str(exc),
                        'provider': provider_name
                    }
            else:
                results[provider_name] = {
                    'success': False,
                    'error': f'Provider {provider_name} not available',
                    'provider': provider_name
                }
        
        # Determine overall success
        success_count = sum(1 for r in results.values() if r['success'])
        
        return {
            'success': success_count > 0,
            'total_channels': len(channels),
            'successful_channels': success_count,
            'failed_channels': len(channels) - success_count,
            'results': results
        }
    
    def send_to_multiple_users(self, notification: PushNotification, users: List[User], 
                              channels: List[NotificationChannel] = None) -> Dict[str, Any]:
        """Send same notification to multiple users."""
        notifications = [notification] * len(users)
        return self.send_batch_notifications(notifications, users, channels)
    
    def add_provider(self, name: str, provider: BaseNotificationProvider):
        """Add a custom notification provider."""
        self.providers[name] = provider
        if provider.is_available():
            self.default_providers.append(name)
    
    def remove_provider(self, name: str):
        """Remove a notification provider."""
        if name in self.providers:
            del self.providers[name]
        if name in self.default_providers:
            self.default_providers.remove(name)
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers."""
        status = {}
        
        for name, provider in self.providers.items():
            status[name] = {
                'available': provider.is_available(),
                'is_default': name in self.default_providers
            }
        
        return status


# Global push notification manager instance
push_notification_manager = PushNotificationManager()


# ── Notification Templates ─────────────────────────────────────────────────────

class NotificationTemplates:
    """Predefined notification templates."""
    
    @staticmethod
    def checkin_completed(user, checkin_data: Dict[str, Any]) -> PushNotification:
        """Template for check-in completion notification."""
        return PushNotification(
            title="✅ Check-in Completed!",
            body=f"Great job! You've earned {checkin_data.get('coins_earned', 0)} coins and {checkin_data.get('xp_earned', 0)} XP.",
            icon="📅",
            data={
                'type': 'checkin_completed',
                'coins_earned': checkin_data.get('coins_earned', 0),
                'xp_earned': checkin_data.get('xp_earned', 0),
                'streak': checkin_data.get('streak', 0)
            },
            priority=NotificationPriority.NORMAL,
            tags=['engagement', 'checkin']
        )
    
    @staticmethod
    def spin_completed(user, spin_data: Dict[str, Any]) -> PushNotification:
        """Template for spin completion notification."""
        return PushNotification(
            title="🎰 Spin Completed!",
            body=f"You won {spin_data.get('coins_won', 0)} coins!",
            icon="🎲",
            data={
                'type': 'spin_completed',
                'coins_won': spin_data.get('coins_won', 0),
                'xp_earned': spin_data.get('xp_earned', 0),
                'is_boosted': spin_data.get('is_boosted', False)
            },
            priority=NotificationPriority.NORMAL,
            tags=['engagement', 'spin']
        )
    
    @staticmethod
    def achievement_unlocked(user, achievement_data: Dict[str, Any]) -> PushNotification:
        """Template for achievement unlock notification."""
        return PushNotification(
            title="🏆 Achievement Unlocked!",
            body=f"Congratulations! You've unlocked: {achievement_data.get('achievement_name', 'New Achievement')}",
            icon="🎯",
            data={
                'type': 'achievement_unlocked',
                'achievement_id': achievement_data.get('achievement_id'),
                'achievement_name': achievement_data.get('achievement_name'),
                'coins_reward': achievement_data.get('coins_reward', 0),
                'xp_reward': achievement_data.get('xp_reward', 0)
            },
            priority=NotificationPriority.HIGH,
            tags=['achievement', 'milestone']
        )
    
    @staticmethod
    def quest_completed(user, quest_data: Dict[str, Any]) -> PushNotification:
        """Template for quest completion notification."""
        return PushNotification(
            title="✅ Quest Completed!",
            body=f"Well done! You've completed: {quest_data.get('quest_name', 'Quest')}",
            icon="📋",
            data={
                'type': 'quest_completed',
                'quest_id': quest_data.get('quest_id'),
                'quest_name': quest_data.get('quest_name'),
                'coins_reward': quest_data.get('coins_reward', 0),
                'xp_reward': quest_data.get('xp_reward', 0)
            },
            priority=NotificationPriority.NORMAL,
            tags=['quest', 'gamification']
        )
    
    @staticmethod
    def streak_milestone(user, streak_data: Dict[str, Any]) -> PushNotification:
        """Template for streak milestone notification."""
        return PushNotification(
            title=f"🔥 {streak_data.get('streak', 0)}-Day Streak!",
            body=f"Incredible! You've maintained a {streak_data.get('streak', 0)}-day streak!",
            icon="🌟",
            data={
                'type': 'streak_milestone',
                'streak': streak_data.get('streak', 0),
                'bonus_coins': streak_data.get('bonus_coins', 0)
            },
            priority=NotificationPriority.HIGH,
            tags=['streak', 'milestone']
        )
    
    @staticmethod
    def level_up(user, level_data: Dict[str, Any]) -> PushNotification:
        """Template for level up notification."""
        return PushNotification(
            title="⭐ Level Up!",
            body=f"Congratulations! You've reached level {level_data.get('new_level', 1)}!",
            icon="🎊",
            data={
                'type': 'level_up',
                'new_level': level_data.get('new_level', 1),
                'total_xp': level_data.get('total_xp', 0)
            },
            priority=NotificationPriority.HIGH,
            tags=['level', 'progression']
        )
    
    @staticmethod
    def purchase_completed(user, purchase_data: Dict[str, Any]) -> PushNotification:
        """Template for purchase completion notification."""
        return PushNotification(
            title="🛍️ Purchase Completed!",
            body=f"Thank you for purchasing: {purchase_data.get('item_name', 'Item')}",
            icon="🎁",
            data={
                'type': 'purchase_completed',
                'item_id': purchase_data.get('item_id'),
                'item_name': purchase_data.get('item_name'),
                'quantity': purchase_data.get('quantity', 1),
                'coins_spent': purchase_data.get('coins_spent', 0)
            },
            priority=NotificationPriority.NORMAL,
            tags=['shop', 'purchase']
        )
    
    @staticmethod
    def leaderboard_rank(user, rank_data: Dict[str, Any]) -> PushNotification:
        """Template for leaderboard rank notification."""
        return PushNotification(
            title="📊 Leaderboard Update!",
            body=f"Your current rank: {rank_data.get('rank', 'N/A')} in {rank_data.get('period', 'daily')} leaderboard",
            icon="🏅",
            data={
                'type': 'leaderboard_rank',
                'rank': rank_data.get('rank', 0),
                'period': rank_data.get('period', 'daily'),
                'total_players': rank_data.get('total_players', 0)
            },
            priority=NotificationPriority.NORMAL,
            tags=['leaderboard', 'ranking']
        )
    
    @staticmethod
    def welcome(user, welcome_data: Dict[str, Any] = None) -> PushNotification:
        """Template for welcome notification."""
        return PushNotification(
            title="🎉 Welcome to Engagement!",
            body="Get started with your first check-in and spin to begin your journey!",
            icon="👋",
            data={
                'type': 'welcome',
                'user_id': user.id,
                'username': user.username
            },
            priority=NotificationPriority.NORMAL,
            tags=['welcome', 'onboarding']
        )
    
    @staticmethod
    def reminder(user, reminder_data: Dict[str, Any]) -> PushNotification:
        """Template for reminder notification."""
        return PushNotification(
            title="⏰ Daily Reminder!",
            body=f"Don't forget to check in today! You have a {reminder_data.get('current_streak', 0)}-day streak going!",
            icon="⏰",
            data={
                'type': 'reminder',
                'current_streak': reminder_data.get('current_streak', 0),
                'last_checkin': reminder_data.get('last_checkin')
            },
            priority=NotificationPriority.LOW,
            tags=['reminder', 'engagement']
        )


# ── Notification Decorators ─────────────────────────────────────────────────────

def send_notification(template_func, channels: List[NotificationChannel] = None):
    """Decorator to send notification after function execution."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            # Try to get user from kwargs or function arguments
            user = None
            if 'user' in kwargs:
                user = kwargs['user']
            elif 'request' in kwargs and hasattr(kwargs['request'], 'user'):
                user = kwargs['request'].user
            
            # Send notification if user is available
            if user and user.is_authenticated:
                try:
                    # Create notification from template
                    notification = template_func(user, result)
                    
                    # Send notification
                    push_notification_manager.send_notification(notification, user, channels)
                    
                except Exception as exc:
                    logger.error(f"Failed to send notification: {exc}")
            
            return result
        return wrapper
    return decorator


# ── Notification Tasks ─────────────────────────────────────────────────────

class NotificationTasks:
    """Scheduled notification tasks."""
    
    @staticmethod
    def send_daily_reminders():
        """Send daily reminder notifications."""
        try:
            from .models.checkin import DailyCheckIn
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            
            # Get users who checked in yesterday but not today
            users_to_remind = DailyCheckIn.objects.filter(
                date=yesterday
            ).exclude(
                date=today
            ).values_list('user_id', flat=True)
            
            for user_id in users_to_remind:
                try:
                    user = User.objects.get(id=user_id)
                    
                    # Get current streak
                    from .services.checkin_service import CheckInService
                    current_streak = CheckInService.get_current_streak(user)
                    
                    # Create reminder notification
                    notification = NotificationTemplates.reminder(user, {
                        'current_streak': current_streak,
                        'last_checkin': yesterday.isoformat()
                    })
                    
                    # Send notification
                    push_notification_manager.send_notification(
                        notification, 
                        user, 
                        [NotificationChannel.PUSH, NotificationChannel.EMAIL]
                    )
                    
                except Exception as exc:
                    logger.error(f"Failed to send reminder to user {user_id}: {exc}")
            
            logger.info(f"Sent daily reminders to {len(users_to_remind)} users")
            
        except Exception as exc:
            logger.error(f"Failed to send daily reminders: {exc}")
    
    @staticmethod
    def send_weekly_digest():
        """Send weekly digest notifications."""
        try:
            from django.contrib.auth import get_user_model
            from .use_cases import EngagementOrchestrator
            
            User = get_user_model()
            
            # Get active users from last week
            week_ago = timezone.now() - timedelta(days=7)
            active_users = DailyCheckIn.objects.filter(
                date__gte=week_ago.date()
            ).values_list('user_id', flat=True).distinct()
            
            orchestrator = EngagementOrchestrator()
            
            for user_id in active_users:
                try:
                    user = User.objects.get(id=user_id)
                    
                    # Generate weekly digest
                    digest_result = orchestrator.generate_user_digest(
                        user, 
                        period='weekly'
                    )
                    
                    if digest_result.success:
                        # Create digest notification
                        notification = PushNotification(
                            title="📊 Your Weekly Digest!",
                            body="Here's your engagement summary for this week.",
                            icon="📈",
                            data={
                                'type': 'weekly_digest',
                                'digest_data': digest_result.data
                            },
                            priority=NotificationPriority.NORMAL,
                            tags=['digest', 'weekly']
                        )
                        
                        # Send notification
                        push_notification_manager.send_notification(
                            notification, 
                            user, 
                            [NotificationChannel.EMAIL]
                        )
                    
                except Exception as exc:
                    logger.error(f"Failed to send digest to user {user_id}: {exc}")
            
            logger.info(f"Sent weekly digests to {len(active_users)} users")
            
        except Exception as exc:
            logger.error(f"Failed to send weekly digests: {exc}")
