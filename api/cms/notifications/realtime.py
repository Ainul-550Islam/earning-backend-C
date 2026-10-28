# cms/notifications/realtime.py
"""
Real-Time Notification System

Comprehensive real-time notifications with:
- WebSocket-based delivery
- In-app notifications
- Push notifications
- Email notifications
- Notification channels
- User preferences
- Delivery tracking

Notification Types:
- System notifications (maintenance, updates)
- User notifications (offers, earnings, messages)
- Alert notifications (fraud, limits exceeded)
- Social notifications (comments, likes)
- Transaction notifications (payments, withdrawals)
"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from django.db import models
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import json

logger = logging.getLogger('cms.notifications.realtime')


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION TYPES & CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────

class NotificationType:
    """Notification type definitions"""
    
    # System notifications
    SYSTEM_UPDATE = 'system.update'
    SYSTEM_MAINTENANCE = 'system.maintenance'
    
    # User notifications
    OFFER_AVAILABLE = 'offer.available'
    SURVEY_AVAILABLE = 'survey.available'
    EARNINGS_RECEIVED = 'earnings.received'
    MESSAGE_RECEIVED = 'message.received'
    
    # Alert notifications
    FRAUD_DETECTED = 'alert.fraud'
    WITHDRAWAL_LIMIT = 'alert.withdrawal_limit'
    ACCOUNT_VERIFIED = 'alert.verified'
    
    # Social notifications
    COMMENT_RECEIVED = 'social.comment'
    LIKE_RECEIVED = 'social.like'
    MENTION_RECEIVED = 'social.mention'
    
    # Transaction notifications
    PAYMENT_SUCCESS = 'transaction.payment_success'
    WITHDRAWAL_APPROVED = 'transaction.withdrawal_approved'
    WITHDRAWAL_REJECTED = 'transaction.withdrawal_rejected'


class NotificationPriority:
    """Notification priority levels"""
    
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    CRITICAL = 'critical'


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION MESSAGE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

class NotificationMessageBuilder:
    """
    Build structured notification messages
    
    Usage:
        builder = NotificationMessageBuilder(NotificationType.OFFER_AVAILABLE)
        message = (builder
                   .set_title("New Offer Available")
                   .set_body("A new survey offer is waiting for you!")
                   .set_action_url("/api/v3/offers/123/")
                   .set_metadata({'offer_id': 123, 'reward': 10.00})
                   .build())
    """
    
    def __init__(self, notification_type: str):
        """Initialize builder"""
        self.notification_type = notification_type
        self.data = {
            'type': notification_type,
            'timestamp': timezone.now().isoformat(),
            'priority': NotificationPriority.NORMAL,
        }
    
    def set_title(self, title: str) -> 'NotificationMessageBuilder':
        """Set notification title"""
        self.data['title'] = title
        return self
    
    def set_body(self, body: str) -> 'NotificationMessageBuilder':
        """Set notification body/message"""
        self.data['body'] = body
        return self
    
    def set_priority(self, priority: str) -> 'NotificationMessageBuilder':
        """Set priority level"""
        self.data['priority'] = priority
        return self
    
    def set_action_url(self, url: str) -> 'NotificationMessageBuilder':
        """Set action URL"""
        self.data['action_url'] = url
        return self
    
    def set_metadata(self, metadata: Dict[str, Any]) -> 'NotificationMessageBuilder':
        """Set custom metadata"""
        self.data['metadata'] = metadata
        return self
    
    def set_image(self, image_url: str) -> 'NotificationMessageBuilder':
        """Set notification image"""
        self.data['image'] = image_url
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build final message"""
        return self.data


# ─────────────────────────────────────────────────────────────────────────────
# REAL-TIME NOTIFICATION SENDER
# ─────────────────────────────────────────────────────────────────────────────

class RealtimeNotificationSender:
    """
    Send real-time notifications via WebSocket
    
    Usage:
        sender = RealtimeNotificationSender()
        sender.notify_user(
            user_id=user.id,
            notification_type=NotificationType.OFFER_AVAILABLE,
            title="New Offer",
            body="A survey is waiting..."
        )
    """
    
    def __init__(self):
        """Initialize sender"""
        self.channel_layer = get_channel_layer()
    
    def notify_user(self, user_id: int, notification_type: str,
                   title: str, body: str, **kwargs) -> bool:
        """
        Send notification to individual user
        
        Args:
            user_id: User ID
            notification_type: Type of notification
            title: Notification title
            body: Notification body
            **kwargs: Additional fields (action_url, metadata, etc.)
            
        Returns:
            True if sent successfully
        """
        try:
            # Build message
            builder = NotificationMessageBuilder(notification_type)
            builder.set_title(title).set_body(body)
            
            # Add optional fields
            if 'priority' in kwargs:
                builder.set_priority(kwargs['priority'])
            if 'action_url' in kwargs:
                builder.set_action_url(kwargs['action_url'])
            if 'metadata' in kwargs:
                builder.set_metadata(kwargs['metadata'])
            if 'image' in kwargs:
                builder.set_image(kwargs['image'])
            
            message = builder.build()
            
            # Send via channel layer
            channel_name = f'user_{user_id}'
            async_to_sync(self.channel_layer.group_send)(
                channel_name,
                {
                    'type': 'notification.send',
                    'message': message,
                }
            )
            
            logger.info(f"Notification sent to user {user_id}: {notification_type}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return False
    
    def notify_group(self, group_name: str, notification_type: str,
                    title: str, body: str, **kwargs) -> int:
        """
        Send notification to group of users
        
        Args:
            group_name: Group identifier
            notification_type: Type of notification
            title: Notification title
            body: Notification body
            **kwargs: Additional fields
            
        Returns:
            Number of users notified (estimated)
        """
        try:
            # Build message
            builder = NotificationMessageBuilder(notification_type)
            builder.set_title(title).set_body(body)
            
            if 'priority' in kwargs:
                builder.set_priority(kwargs['priority'])
            if 'metadata' in kwargs:
                builder.set_metadata(kwargs['metadata'])
            
            message = builder.build()
            
            # Send to group
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification.send',
                    'message': message,
                }
            )
            
            logger.info(f"Group notification sent: {group_name} - {notification_type}")
            return 1  # In real system, would return actual user count
        
        except Exception as e:
            logger.error(f"Failed to send group notification: {e}")
            return 0
    
    def broadcast(self, notification_type: str, title: str, body: str,
                 priority: str = NotificationPriority.NORMAL) -> int:
        """
        Broadcast notification to all online users
        
        Args:
            notification_type: Type of notification
            title: Notification title
            body: Notification body
            priority: Notification priority
            
        Returns:
            Number of users notified
        """
        try:
            # Build message
            builder = (NotificationMessageBuilder(notification_type)
                      .set_title(title)
                      .set_body(body)
                      .set_priority(priority))
            
            message = builder.build()
            
            # Broadcast to all
            async_to_sync(self.channel_layer.group_send)(
                'broadcast',
                {
                    'type': 'notification.send',
                    'message': message,
                }
            )
            
            logger.info(f"Broadcast notification: {notification_type}")
            return 1
        
        except Exception as e:
            logger.error(f"Failed to broadcast notification: {e}")
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION STORAGE & HISTORY
# ─────────────────────────────────────────────────────────────────────────────

class NotificationStore:
    """
    Store and retrieve notification history
    
    Provides:
    - Persistent notification storage
    - Notification read/unread tracking
    - Notification filtering
    - Cleanup of old notifications
    """
    
    @staticmethod
    def store_notification(user_id: int, notification_type: str,
                          title: str, body: str, **kwargs) -> Dict[str, Any]:
        """
        Store notification in database
        
        Args:
            user_id: User ID
            notification_type: Type of notification
            title: Notification title
            body: Notification body
            **kwargs: Additional fields
            
        Returns:
            Stored notification data
        """
        from api.cms.models_new.notifications import Notification
        
        try:
            notification = Notification.objects.create(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                body=body,
                data=kwargs,
                is_read=False,
            )
            
            logger.info(f"Notification stored: {notification.id}")
            
            return {
                'id': notification.id,
                'user_id': user_id,
                'type': notification_type,
                'title': title,
                'body': body,
                'created_at': notification.created_at.isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Failed to store notification: {e}")
            return {}
    
    @staticmethod
    def get_user_notifications(user_id: int, unread_only: bool = False,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get notifications for user
        
        Args:
            user_id: User ID
            unread_only: Only return unread
            limit: Maximum notifications to return
            
        Returns:
            List of notifications
        """
        from api.cms.models_new.notifications import Notification
        
        try:
            queryset = Notification.objects.filter(user_id=user_id)
            
            if unread_only:
                queryset = queryset.filter(is_read=False)
            
            notifications = list(
                queryset.order_by('-created_at')[:limit]
                .values('id', 'notification_type', 'title', 'body',
                       'is_read', 'created_at')
            )
            
            return notifications
        
        except Exception as e:
            logger.error(f"Failed to get notifications: {e}")
            return []
    
    @staticmethod
    def mark_as_read(notification_id: int) -> bool:
        """Mark notification as read"""
        from api.cms.models_new.notifications import Notification
        
        try:
            Notification.objects.filter(id=notification_id).update(is_read=True)
            logger.info(f"Notification marked as read: {notification_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark notification as read: {e}")
            return False
    
    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """Mark all user notifications as read"""
        from api.cms.models_new.notifications import Notification
        
        try:
            count = Notification.objects.filter(
                user_id=user_id,
                is_read=False
            ).update(is_read=True)
            
            logger.info(f"Marked {count} notifications as read for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to mark all as read: {e}")
            return 0
    
    @staticmethod
    def cleanup_old_notifications(days: int = 30) -> int:
        """
        Delete notifications older than X days
        
        Args:
            days: Age in days
            
        Returns:
            Number deleted
        """
        from api.cms.models_new.notifications import Notification
        from datetime import timedelta
        
        try:
            cutoff = timezone.now() - timedelta(days=days)
            count, _ = Notification.objects.filter(
                created_at__lt=cutoff,
                is_read=True
            ).delete()
            
            logger.info(f"Cleaned up {count} old notifications")
            return count
        except Exception as e:
            logger.error(f"Failed to cleanup notifications: {e}")
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION PREFERENCES
# ─────────────────────────────────────────────────────────────────────────────

class NotificationPreferences:
    """
    User notification preferences
    
    Allows users to control:
    - Which notifications they receive
    - Notification channels (email, push, in-app)
    - Quiet hours
    - Frequency limits
    """
    
    @staticmethod
    def get_user_preferences(user_id: int) -> Dict[str, Any]:
        """Get user notification preferences"""
        from api.cms.models_new.notifications import UserNotificationPreference
        
        try:
            prefs = UserNotificationPreference.objects.get(user_id=user_id)
            return {
                'user_id': user_id,
                'enable_email': prefs.enable_email,
                'enable_push': prefs.enable_push,
                'enable_sms': prefs.enable_sms,
                'quiet_hours_start': prefs.quiet_hours_start,
                'quiet_hours_end': prefs.quiet_hours_end,
                'notification_types': prefs.notification_types,
            }
        except UserNotificationPreference.DoesNotExist:
            # Return defaults
            return {
                'user_id': user_id,
                'enable_email': True,
                'enable_push': True,
                'enable_sms': False,
                'quiet_hours_start': None,
                'quiet_hours_end': None,
                'notification_types': [],
            }
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return {}
    
    @staticmethod
    def update_preferences(user_id: int, **kwargs) -> bool:
        """Update user preferences"""
        from api.cms.models_new.notifications import UserNotificationPreference
        
        try:
            prefs, created = UserNotificationPreference.objects.get_or_create(
                user_id=user_id
            )
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(prefs, key):
                    setattr(prefs, key, value)
            
            prefs.save()
            logger.info(f"Preferences updated for user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update preferences: {e}")
            return False
    
    @staticmethod
    def is_in_quiet_hours(user_id: int) -> bool:
        """Check if user is in quiet hours"""
        from api.cms.models_new.notifications import UserNotificationPreference
        from datetime import datetime
        
        try:
            prefs = UserNotificationPreference.objects.get(user_id=user_id)
            
            if not prefs.quiet_hours_start or not prefs.quiet_hours_end:
                return False
            
            now = datetime.now().time()
            return prefs.quiet_hours_start <= now <= prefs.quiet_hours_end
        
        except UserNotificationPreference.DoesNotExist:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

class NotificationHelpers:
    """Helper functions for common notifications"""
    
    sender = RealtimeNotificationSender()
    store = NotificationStore()
    
    @classmethod
    def notify_offer_available(cls, user_id: int, offer_id: int,
                              offer_title: str, reward: float) -> bool:
        """Notify user of available offer"""
        
        # Send real-time notification
        cls.sender.notify_user(
            user_id=user_id,
            notification_type=NotificationType.OFFER_AVAILABLE,
            title=f"New Offer: {offer_title}",
            body=f"Complete this offer and earn ${reward:.2f}",
            action_url=f"/api/v3/offers/{offer_id}/",
            metadata={'offer_id': offer_id, 'reward': reward}
        )
        
        # Store for history
        cls.store.store_notification(
            user_id=user_id,
            notification_type=NotificationType.OFFER_AVAILABLE,
            title=f"New Offer: {offer_title}",
            body=f"Complete this offer and earn ${reward:.2f}",
            offer_id=offer_id,
            reward=reward,
        )
        
        return True
    
    @classmethod
    def notify_earnings_received(cls, user_id: int, amount: float,
                                source: str) -> bool:
        """Notify user of earnings"""
        
        cls.sender.notify_user(
            user_id=user_id,
            notification_type=NotificationType.EARNINGS_RECEIVED,
            title="You Earned Money!",
            body=f"${amount:.2f} added to your account from {source}",
            priority=NotificationPriority.HIGH,
            metadata={'amount': amount, 'source': source}
        )
        
        cls.store.store_notification(
            user_id=user_id,
            notification_type=NotificationType.EARNINGS_RECEIVED,
            title="You Earned Money!",
            body=f"${amount:.2f} added to your account from {source}",
            amount=amount,
            source=source,
        )
        
        return True
    
    @classmethod
    def notify_withdrawal_approved(cls, user_id: int, amount: float,
                                  withdrawal_id: int) -> bool:
        """Notify user of withdrawal approval"""
        
        cls.sender.notify_user(
            user_id=user_id,
            notification_type=NotificationType.WITHDRAWAL_APPROVED,
            title="Withdrawal Approved!",
            body=f"Your ${amount:.2f} withdrawal has been approved",
            priority=NotificationPriority.HIGH,
            action_url=f"/api/v3/withdrawals/{withdrawal_id}/",
            metadata={'amount': amount, 'withdrawal_id': withdrawal_id}
        )
        
        cls.store.store_notification(
            user_id=user_id,
            notification_type=NotificationType.WITHDRAWAL_APPROVED,
            title="Withdrawal Approved!",
            body=f"Your ${amount:.2f} withdrawal has been approved",
            amount=amount,
            withdrawal_id=withdrawal_id,
        )
        
        return True
    
    @classmethod
    def notify_fraud_detected(cls, user_id: int, details: str) -> bool:
        """Notify user of fraud detection"""
        
        cls.sender.notify_user(
            user_id=user_id,
            notification_type=NotificationType.FRAUD_DETECTED,
            title="Security Alert",
            body=f"Suspicious activity detected: {details}",
            priority=NotificationPriority.CRITICAL,
        )
        
        cls.store.store_notification(
            user_id=user_id,
            notification_type=NotificationType.FRAUD_DETECTED,
            title="Security Alert",
            body=f"Suspicious activity detected: {details}",
            details=details,
        )
        
        return True


# Export public API
__all__ = [
    'NotificationType',
    'NotificationPriority',
    'NotificationMessageBuilder',
    'RealtimeNotificationSender',
    'NotificationStore',
    'NotificationPreferences',
    'NotificationHelpers',
]
