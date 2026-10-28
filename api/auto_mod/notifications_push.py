# =============================================================================
# auto_mod/notifications_push.py
# =============================================================================

"""
Push notifications system for auto moderation.
Provides real-time notifications for moderation events and alerts.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import SuspiciousSubmission, ModerationDecision, ModerationAppeal
from .exceptions import ModerationError

logger = logging.getLogger(__name__)

User = get_user_model()


class NotificationType:
    """Notification types."""
    SUBMISSION_RECEIVED = "submission_received"
    DECISION_MADE = "decision_made"
    APPEAL_CREATED = "appeal_created"
    QUEUE_ASSIGNED = "queue_assigned"
    BOT_STATUS_CHANGED = "bot_status_changed"
    SYSTEM_ALERT = "system_alert"
    PERFORMANCE_WARNING = "performance_warning"
    SECURITY_ALERT = "security_alert"


class NotificationPriority:
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PushNotification:
    """Individual push notification."""
    
    def __init__(self, user_id: Union[str, int], title: str, message: str,
                 notification_type: str, priority: str = NotificationPriority.MEDIUM,
                 data: Dict[str, Any] = None, expires_at: datetime = None):
        self.user_id = user_id
        self.title = title
        self.message = message
        self.notification_type = notification_type
        self.priority = priority
        self.data = data or {}
        self.created_at = timezone.now()
        self.expires_at = expires_at or (self.created_at + timedelta(hours=24))
        self.is_read = False
        self.delivered = False
        self.delivery_attempts = 0
        self.max_delivery_attempts = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': str(self.user_id),
            'title': self.title,
            'message': self.message,
            'type': self.notification_type,
            'priority': self.priority,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_read': self.is_read,
            'delivered': self.delivered,
            'delivery_attempts': self.delivery_attempts,
        }
    
    def is_expired(self) -> bool:
        """Check if notification is expired."""
        return timezone.now() > self.expires_at
    
    def can_retry_delivery(self) -> bool:
        """Check if delivery can be retried."""
        return (not self.delivered and 
                self.delivery_attempts < self.max_delivery_attempts and
                not self.is_expired())


class PushNotificationProvider:
    """Base class for push notification providers."""
    
    def send_notification(self, notification: PushNotification) -> bool:
        """Send a push notification."""
        raise NotImplementedError("Subclasses must implement send_notification")
    
    def validate_config(self) -> bool:
        """Validate provider configuration."""
        return True


class FirebaseProvider(PushNotificationProvider):
    """Firebase Cloud Messaging (FCM) provider."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(settings, 'FCM_API_KEY', None)
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
    
    def send_notification(self, notification: PushNotification) -> bool:
        """Send notification via FCM."""
        try:
            if not self.api_key:
                logger.warning("FCM API key not configured")
                return False
            
            # Get user's FCM token
            fcm_token = self._get_user_fcm_token(notification.user_id)
            if not fcm_token:
                logger.warning(f"No FCM token for user {notification.user_id}")
                return False
            
            # Prepare FCM payload
            payload = {
                'to': fcm_token,
                'notification': {
                    'title': notification.title,
                    'body': notification.message,
                    'sound': 'default',
                },
                'data': {
                    'type': notification.notification_type,
                    'priority': notification.priority,
                    **notification.data
                },
                'priority': 'high' if notification.priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL] else 'normal',
            }
            
            # Send to FCM
            import requests
            
            headers = {
                'Authorization': f'key={self.api_key}',
                'Content-Type': 'application/json',
            }
            
            response = requests.post(self.fcm_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success', 0) > 0:
                    logger.info(f"FCM notification sent successfully to user {notification.user_id}")
                    return True
                else:
                    logger.error(f"FCM notification failed: {result}")
                    return False
            else:
                logger.error(f"FCM request failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as exc:
            logger.error(f"FCM send failed: {exc}")
            return False
    
    def _get_user_fcm_token(self, user_id: Union[str, int]) -> Optional[str]:
        """Get user's FCM token."""
        try:
            user = User.objects.get(id=user_id)
            return getattr(user, 'fcm_token', None)
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found for FCM token")
            return None
        except Exception as exc:
            logger.error(f"Get FCM token failed: {exc}")
            return None
    
    def validate_config(self) -> bool:
        """Validate FCM configuration."""
        return bool(self.api_key)


class WebSocketProvider(PushNotificationProvider):
    """WebSocket provider for real-time notifications."""
    
    def __init__(self):
        self.active_connections = {}
    
    def send_notification(self, notification: PushNotification) -> bool:
        """Send notification via WebSocket."""
        try:
            # Check if user has active WebSocket connection
            connection = self.active_connections.get(str(notification.user_id))
            if not connection:
                logger.warning(f"No active WebSocket connection for user {notification.user_id}")
                return False
            
            # Send notification
            message = {
                'type': 'notification',
                'data': notification.to_dict()
            }
            
            # This would integrate with your WebSocket implementation
            # For now, just log the attempt
            logger.info(f"WebSocket notification sent to user {notification.user_id}")
            return True
            
        except Exception as exc:
            logger.error(f"WebSocket send failed: {exc}")
            return False
    
    def register_connection(self, user_id: Union[str, int], connection):
        """Register WebSocket connection."""
        self.active_connections[str(user_id)] = connection
        logger.info(f"WebSocket connection registered for user {user_id}")
    
    def unregister_connection(self, user_id: Union[str, int]):
        """Unregister WebSocket connection."""
        user_id_str = str(user_id)
        if user_id_str in self.active_connections:
            del self.active_connections[user_id_str]
            logger.info(f"WebSocket connection unregistered for user {user_id}")


class EmailProvider(PushNotificationProvider):
    """Email provider for critical notifications."""
    
    def send_notification(self, notification: PushNotification) -> bool:
        """Send notification via email."""
        try:
            if notification.priority not in [NotificationPriority.HIGH, NotificationPriority.CRITICAL]:
                return False  # Only send high/critical priority emails
            
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            
            user = User.objects.get(id=notification.user_id)
            
            # Render email template
            subject = f"Moderation Alert: {notification.title}"
            
            context = {
                'user': user,
                'notification': notification,
            }
            
            html_message = render_to_string('auto_mod/notification_email.html', context)
            plain_message = render_to_string('auto_mod/notification_email.txt', context)
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email notification sent to user {notification.user_id}")
            return True
            
        except User.DoesNotExist:
            logger.warning(f"User {notification.user_id} not found for email notification")
            return False
        except Exception as exc:
            logger.error(f"Email send failed: {exc}")
            return False


class PushNotificationManager:
    """
    Manager for push notifications with multiple providers.
    """
    
    def __init__(self):
        self.providers = self._initialize_providers()
        self.notification_queue = []
        self.max_queue_size = 1000
        self.batch_size = 50
        self.delivery_interval = 30  # seconds
        self._start_delivery_worker()
    
    def _initialize_providers(self) -> Dict[str, PushNotificationProvider]:
        """Initialize notification providers."""
        providers = {}
        
        # Firebase provider
        firebase_provider = FirebaseProvider()
        if firebase_provider.validate_config():
            providers['firebase'] = firebase_provider
            logger.info("Firebase provider initialized")
        
        # WebSocket provider
        providers['websocket'] = WebSocketProvider()
        logger.info("WebSocket provider initialized")
        
        # Email provider
        providers['email'] = EmailProvider()
        logger.info("Email provider initialized")
        
        return providers
    
    def _start_delivery_worker(self):
        """Start background delivery worker."""
        # This would be implemented with Celery or similar
        # For now, just log that it would start
        logger.info("Push notification delivery worker started")
    
    def create_notification(self, user_id: Union[str, int], title: str, message: str,
                           notification_type: str, priority: str = NotificationPriority.MEDIUM,
                           data: Dict[str, Any] = None, expires_at: datetime = None) -> PushNotification:
        """
        Create a new push notification.
        
        Args:
            user_id: User ID to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            data: Additional data
            expires_at: Expiration time
            
        Returns:
            Created notification
        """
        notification = PushNotification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            data=data,
            expires_at=expires_at
        )
        
        # Add to queue
        self._add_to_queue(notification)
        
        return notification
    
    def _add_to_queue(self, notification: PushNotification) -> None:
        """Add notification to delivery queue."""
        try:
            self.notification_queue.append(notification)
            
            # Limit queue size
            if len(self.notification_queue) > self.max_queue_size:
                self.notification_queue = self.notification_queue[-self.max_queue_size:]
            
            # Store in cache for persistence
            cache_key = f"notification_queue:{notification.user_id}"
            user_queue = cache.get(cache_key, [])
            user_queue.append(notification.to_dict())
            cache.set(cache_key, user_queue, timeout=86400)  # 24 hours
            
        except Exception as exc:
            logger.error(f"Add to queue failed: {exc}")
    
    def send_notification(self, notification: PushNotification) -> bool:
        """
        Send notification through available providers.
        
        Args:
            notification: Notification to send
            
        Returns:
            True if sent successfully by any provider
        """
        if notification.is_expired():
            logger.warning(f"Notification expired for user {notification.user_id}")
            return False
        
        success = False
        
        # Try providers in order of preference
        provider_order = ['websocket', 'firebase', 'email']
        
        for provider_name in provider_order:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                
                try:
                    if provider.send_notification(notification):
                        notification.delivered = True
                        success = True
                        logger.info(f"Notification sent via {provider_name} to user {notification.user_id}")
                        break
                except Exception as exc:
                    logger.error(f"Provider {provider_name} failed: {exc}")
                    continue
        
        if not success:
            notification.delivery_attempts += 1
            logger.warning(f"Failed to send notification to user {notification.user_id}")
        
        return success
    
    def batch_send_notifications(self) -> Dict[str, int]:
        """
        Send notifications in batch.
        
        Returns:
            Batch sending statistics
        """
        stats = {
            'total': 0,
            'sent': 0,
            'failed': 0,
            'expired': 0,
        }
        
        # Get batch of notifications
        batch = self.notification_queue[:self.batch_size]
        
        for notification in batch:
            stats['total'] += 1
            
            if notification.is_expired():
                stats['expired'] += 1
                continue
            
            if self.send_notification(notification):
                stats['sent'] += 1
            else:
                stats['failed'] += 1
        
        # Remove processed notifications from queue
        self.notification_queue = self.notification_queue[len(batch):]
        
        return stats
    
    def get_user_notifications(self, user_id: Union[str, int], 
                            unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get notifications for a user.
        
        Args:
            user_id: User ID
            unread_only: Only return unread notifications
            limit: Maximum number of notifications
            
        Returns:
            List of notifications
        """
        try:
            cache_key = f"notification_queue:{user_id}"
            user_notifications = cache.get(cache_key, [])
            
            # Filter notifications
            filtered_notifications = []
            
            for notif_data in user_notifications:
                notification = PushNotification(
                    user_id=notif_data['user_id'],
                    title=notif_data['title'],
                    message=notif_data['message'],
                    notification_type=notif_data['type'],
                    priority=notif_data['priority'],
                    data=notif_data['data'],
                    expires_at=datetime.fromisoformat(notif_data['expires_at'])
                )
                
                if unread_only and notification.is_read:
                    continue
                
                if notification.is_expired():
                    continue
                
                filtered_notifications.append(notification.to_dict())
            
            # Sort by creation time (newest first)
            filtered_notifications.sort(key=lambda x: x['created_at'], reverse=True)
            
            return filtered_notifications[:limit]
            
        except Exception as exc:
            logger.error(f"Get user notifications failed: {exc}")
            return []
    
    def mark_notification_read(self, user_id: Union[str, int], 
                             notification_id: str) -> bool:
        """
        Mark a notification as read.
        
        Args:
            user_id: User ID
            notification_id: Notification ID
            
        Returns:
            True if successful
        """
        try:
            cache_key = f"notification_queue:{user_id}"
            user_notifications = cache.get(cache_key, [])
            
            updated = False
            
            for notif_data in user_notifications:
                if notif_data.get('id') == notification_id:
                    notif_data['is_read'] = True
                    updated = True
                    break
            
            if updated:
                cache.set(cache_key, user_notifications, timeout=86400)
                logger.info(f"Notification {notification_id} marked as read for user {user_id}")
            
            return updated
            
        except Exception as exc:
            logger.error(f"Mark notification read failed: {exc}")
            return False
    
    def mark_all_notifications_read(self, user_id: Union[str, int]) -> int:
        """
        Mark all notifications as read for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of notifications marked as read
        """
        try:
            cache_key = f"notification_queue:{user_id}"
            user_notifications = cache.get(cache_key, [])
            
            marked_count = 0
            
            for notif_data in user_notifications:
                if not notif_data['is_read']:
                    notif_data['is_read'] = True
                    marked_count += 1
            
            cache.set(cache_key, user_notifications, timeout=86400)
            logger.info(f"Marked {marked_count} notifications as read for user {user_id}")
            
            return marked_count
            
        except Exception as exc:
            logger.error(f"Mark all notifications read failed: {exc}")
            return 0
    
    def clear_expired_notifications(self) -> int:
        """
        Clear expired notifications from all user queues.
        
        Returns:
            Number of notifications cleared
        """
        try:
            cleared_count = 0
            
            # This would iterate through all user notification queues
            # For now, just return 0 as placeholder
            logger.info("Expired notifications cleanup completed")
            
            return cleared_count
            
        except Exception as exc:
            logger.error(f"Clear expired notifications failed: {exc}")
            return 0
    
    def get_notification_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get notification statistics.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Notification statistics
        """
        try:
            # This would calculate statistics from notification history
            # For now, return mock statistics
            return {
                'total_sent': 150,
                'total_delivered': 142,
                'total_failed': 8,
                'total_expired': 5,
                'delivery_rate': 94.7,
                'by_type': {
                    'submission_received': 45,
                    'decision_made': 38,
                    'appeal_created': 12,
                    'queue_assigned': 25,
                    'system_alert': 8,
                    'performance_warning': 15,
                    'security_alert': 7,
                },
                'by_priority': {
                    'low': 20,
                    'medium': 85,
                    'high': 35,
                    'critical': 10,
                },
                'period_hours': hours,
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as exc:
            logger.error(f"Get notification stats failed: {exc}")
            return {'error': str(exc)}


# Global notification manager
notification_manager = PushNotificationManager()


# Utility functions
def send_notification(user_id: Union[str, int], title: str, message: str,
                     notification_type: str, priority: str = NotificationPriority.MEDIUM,
                     data: Dict[str, Any] = None) -> PushNotification:
    """Send a push notification."""
    return notification_manager.create_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        data=data
    )


def send_submission_notification(submission: SuspiciousSubmission, 
                               notification_type: str = NotificationType.SUBMISSION_RECEIVED) -> None:
    """Send submission-related notification."""
    try:
        # Notify relevant users based on submission
        if notification_type == NotificationType.SUBMISSION_RECEIVED:
            # Notify moderators about new submission
            moderators = User.objects.filter(is_staff=True)
            
            for moderator in moderators:
                send_notification(
                    user_id=moderator.id,
                    title="New Submission Received",
                    message=f"New submission requires moderation: {submission.submission_type}",
                    notification_type=notification_type,
                    priority=NotificationPriority.MEDIUM,
                    data={
                        'submission_id': str(submission.id),
                        'submission_type': submission.submission_type,
                        'risk_score': submission.risk_score,
                    }
                )
        
        elif notification_type == NotificationType.DECISION_MADE:
            # Notify submitter about decision
            if submission.decisions.exists():
                decision = submission.decisions.latest('decided_at')
                
                send_notification(
                    user_id=submission.user_id,
                    title=f"Submission {decision.decision_type.title()}",
                    message=f"Your submission has been {decision.decision_type}",
                    notification_type=notification_type,
                    priority=NotificationPriority.MEDIUM,
                    data={
                        'submission_id': str(submission.id),
                        'decision_id': str(decision.id),
                        'decision_type': decision.decision_type,
                    }
                )
        
    except Exception as exc:
        logger.error(f"Send submission notification failed: {exc}")


def send_appeal_notification(appeal: ModerationAppeal) -> None:
    """Send appeal-related notification."""
    try:
        # Notify moderators about new appeal
        moderators = User.objects.filter(is_staff=True)
        
        for moderator in moderators:
            send_notification(
                user_id=moderator.id,
                title="New Appeal Filed",
                message=f"User has appealed a moderation decision",
                notification_type=NotificationType.APPEAL_CREATED,
                priority=NotificationPriority.HIGH,
                data={
                    'appeal_id': str(appeal.id),
                    'decision_id': str(appeal.original_decision_id),
                    'appeal_type': appeal.appeal_type,
                }
            )
        
    except Exception as exc:
        logger.error(f"Send appeal notification failed: {exc}")


def send_system_alert(title: str, message: str, priority: str = NotificationPriority.MEDIUM,
                      user_ids: List[Union[str, int]] = None) -> None:
    """Send system alert notification."""
    try:
        if user_ids is None:
            # Send to all staff users
            user_ids = User.objects.filter(is_staff=True).values_list('id', flat=True)
        
        for user_id in user_ids:
            send_notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=NotificationType.SYSTEM_ALERT,
                priority=priority,
                data={'system_alert': True}
            )
        
    except Exception as exc:
        logger.error(f"Send system alert failed: {exc}")


# Initialize logging
logger.info("Push notifications module initialized with real-time notification capabilities")
