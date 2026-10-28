# =============================================================================
# fraud_detection/notifications_push.py
# =============================================================================
"""
Push Notifications Layer for Fraud Detection System.

Provides real-time push notifications for fraud alerts,
case updates, and system events to administrators and staff.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from api.fraud_detection.exceptions import NotificationError
from api.fraud_detection.constants import NOTIFICATION_CONFIG


logger = logging.getLogger(__name__)

User = get_user_model()


class NotificationType(Enum):
    """Notification types for fraud detection system."""
    FRAUD_ALERT = "fraud_alert"
    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_ESCALATED = "case_escalated"
    RISK_SCORE_CHANGED = "risk_score_changed"
    SYSTEM_ALERT = "system_alert"
    COMPLIANCE_REPORT = "compliance_report"
    THREAT_INTELLIGENCE = "threat_intelligence"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PushNotification:
    """Data class for push notifications."""
    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    recipient_ids: Optional[List[Union[int, str]]] = None
    channels: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class PushNotificationManager:
    """
    Push notification manager for fraud detection system.
    
    Handles real-time notifications via WebSocket, email, SMS,
    and other channels for fraud detection events.
    """
    
    def __init__(self):
        """Initialize push notification manager."""
        self.channel_layer = get_channel_layer()
        self.notification_config = self._load_notification_config()
        self.enabled_channels = self._load_enabled_channels()
        self.notification_queue = []
        self.max_queue_size = self.notification_config.get('max_queue_size', 1000)
        
        # Notification statistics
        self.stats = {
            'sent': 0,
            'failed': 0,
            'queued': 0,
            'expired': 0
        }
    
    def _load_notification_config(self) -> Dict[str, Any]:
        """Load notification configuration."""
        default_config = {
            'max_queue_size': 1000,
            'default_ttl': 3600,  # 1 hour
            'batch_size': 100,
            'retry_attempts': 3,
            'retry_delay': 60,  # seconds
            'channels': {
                'websocket': {'enabled': True, 'room': 'fraud_notifications'},
                'email': {'enabled': True, 'template_prefix': 'fraud'},
                'sms': {'enabled': False, 'provider': 'twilio'},
                'push': {'enabled': False, 'provider': 'fcm'}
            }
        }
        
        return getattr(settings, 'FRAUD_NOTIFICATION_CONFIG', default_config)
    
    def _load_enabled_channels(self) -> List[str]:
        """Load list of enabled notification channels."""
        return [
            channel for channel, config in self.notification_config['channels'].items()
            if config.get('enabled', False)
        ]
    
    def send_notification(self, notification: PushNotification) -> bool:
        """
        Send push notification through enabled channels.
        
        Args:
            notification: Push notification object
            
        Returns:
            True if sent successfully
        """
        try:
            # Set default values
            if not notification.created_at:
                notification.created_at = timezone.now()
            
            if not notification.expires_at:
                notification.expires_at = notification.created_at + timedelta(
                    seconds=self.notification_config['default_ttl']
                )
            
            # Validate notification
            if not self._validate_notification(notification):
                return False
            
            # Send through each enabled channel
            success_count = 0
            total_channels = len(self.enabled_channels)
            
            for channel in self.enabled_channels:
                try:
                    if self._send_via_channel(notification, channel):
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send notification via {channel}: {e}")
                    self.stats['failed'] += 1
            
            # Update statistics
            if success_count > 0:
                self.stats['sent'] += 1
                logger.info(f"Notification sent via {success_count}/{total_channels} channels: {notification.id}")
                return True
            else:
                self.stats['failed'] += 1
                logger.error(f"Failed to send notification via any channel: {notification.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending notification {notification.id}: {e}")
            self.stats['failed'] += 1
            return False
    
    def send_fraud_alert(self, alert_data: Dict[str, Any], 
                         priority: NotificationPriority = NotificationPriority.HIGH) -> bool:
        """
        Send fraud alert notification.
        
        Args:
            alert_data: Alert data dictionary
            priority: Notification priority
            
        Returns:
            True if sent successfully
        """
        notification = PushNotification(
            id=f"fraud_alert_{alert_data.get('alert_id', 'unknown')}",
            type=NotificationType.FRAUD_ALERT,
            priority=priority,
            title=f"Fraud Alert: {alert_data.get('alert_type', 'Unknown')}",
            message=self._format_fraud_alert_message(alert_data),
            data=alert_data,
            recipient_ids=self._get_recipient_ids_for_alert(alert_data),
            channels=['websocket', 'email'],
            metadata={'alert_id': alert_data.get('alert_id')}
        )
        
        return self.send_notification(notification)
    
    def send_case_notification(self, case_data: Dict[str, Any], 
                              action: str = 'created') -> bool:
        """
        Send case-related notification.
        
        Args:
            case_data: Case data dictionary
            action: Action type (created, updated, escalated)
            
        Returns:
            True if sent successfully
        """
        notification_type = {
            'created': NotificationType.CASE_CREATED,
            'updated': NotificationType.CASE_UPDATED,
            'escalated': NotificationType.CASE_ESCALATED
        }.get(action, NotificationType.CASE_UPDATED)
        
        priority = NotificationPriority.CRITICAL if action == 'escalated' else NotificationPriority.HIGH
        
        notification = PushNotification(
            id=f"case_{action}_{case_data.get('case_id', 'unknown')}",
            type=notification_type,
            priority=priority,
            title=f"Fraud Case {action.title()}: {case_data.get('case_id', 'Unknown')}",
            message=self._format_case_message(case_data, action),
            data=case_data,
            recipient_ids=self._get_recipient_ids_for_case(case_data),
            channels=['websocket', 'email'],
            metadata={'case_id': case_data.get('case_id'), 'action': action}
        )
        
        return self.send_notification(notification)
    
    def send_risk_score_notification(self, user_id: Union[int, str], 
                                   old_score: int, new_score: int,
                                   reason: str) -> bool:
        """
        Send risk score change notification.
        
        Args:
            user_id: User ID
            old_score: Previous risk score
            new_score: New risk score
            reason: Change reason
            
        Returns:
            True if sent successfully
        """
        # Determine priority based on score change
        score_change = abs(new_score - old_score)
        if new_score >= 80 or score_change >= 30:
            priority = NotificationPriority.HIGH
        elif new_score >= 60 or score_change >= 15:
            priority = NotificationPriority.MEDIUM
        else:
            priority = NotificationPriority.LOW
        
        notification = PushNotification(
            id=f"risk_score_{user_id}_{timezone.now().strftime('%Y%m%d%H%M%S')}",
            type=NotificationType.RISK_SCORE_CHANGED,
            priority=priority,
            title=f"Risk Score Changed: User {user_id}",
            message=f"User {user_id} risk score changed from {old_score} to {new_score}. Reason: {reason}",
            data={
                'user_id': user_id,
                'old_score': old_score,
                'new_score': new_score,
                'reason': reason,
                'change': new_score - old_score
            },
            recipient_ids=self._get_recipient_ids_for_risk_change(user_id, new_score),
            channels=['websocket'],
            metadata={'user_id': user_id, 'score_change': new_score - old_score}
        )
        
        return self.send_notification(notification)
    
    def send_system_alert(self, alert_data: Dict[str, Any], 
                         priority: NotificationPriority = NotificationPriority.MEDIUM) -> bool:
        """
        Send system alert notification.
        
        Args:
            alert_data: Alert data
            priority: Notification priority
            
        Returns:
            True if sent successfully
        """
        notification = PushNotification(
            id=f"system_alert_{timezone.now().strftime('%Y%m%d%H%M%S')}",
            type=NotificationType.SYSTEM_ALERT,
            priority=priority,
            title=f"System Alert: {alert_data.get('alert_type', 'Unknown')}",
            message=alert_data.get('message', 'System alert occurred'),
            data=alert_data,
            recipient_ids=self._get_system_admin_ids(),
            channels=['websocket', 'email'],
            metadata={'system_alert': True}
        )
        
        return self.send_notification(notification)
    
    def send_compliance_report_notification(self, report_data: Dict[str, Any]) -> bool:
        """
        Send compliance report notification.
        
        Args:
            report_data: Report data
            
        Returns:
            True if sent successfully
        """
        notification = PushNotification(
            id=f"compliance_report_{report_data.get('report_id', 'unknown')}",
            type=NotificationType.COMPLIANCE_REPORT,
            priority=NotificationPriority.MEDIUM,
            title=f"Compliance Report: {report_data.get('report_type', 'Unknown')}",
            message=f"Compliance report {report_data.get('report_id')} is ready for review",
            data=report_data,
            recipient_ids=self._get_compliance_officer_ids(),
            channels=['email'],
            metadata={'report_id': report_data.get('report_id')}
        )
        
        return self.send_notification(notification)
    
    def send_threat_intelligence_notification(self, threat_data: Dict[str, Any]) -> bool:
        """
        Send threat intelligence update notification.
        
        Args:
            threat_data: Threat intelligence data
            
        Returns:
            True if sent successfully
        """
        notification = PushNotification(
            id=f"threat_intel_{timezone.now().strftime('%Y%m%d%H%M%S')}",
            type=NotificationType.THREAT_INTELLIGENCE,
            priority=NotificationPriority.MEDIUM,
            title="Threat Intelligence Update",
            message=f"New threat intelligence data available: {threat_data.get('threat_type', 'Unknown')}",
            data=threat_data,
            recipient_ids=self._get_analyst_ids(),
            channels=['websocket'],
            metadata={'threat_type': threat_data.get('threat_type')}
        )
        
        return self.send_notification(notification)
    
    def _validate_notification(self, notification: PushNotification) -> bool:
        """Validate notification before sending."""
        if not notification.title or not notification.message:
            logger.error(f"Invalid notification: missing title or message: {notification.id}")
            return False
        
        if notification.expires_at and notification.expires_at <= timezone.now():
            logger.warning(f"Notification expired: {notification.id}")
            self.stats['expired'] += 1
            return False
        
        return True
    
    def _send_via_channel(self, notification: PushNotification, channel: str) -> bool:
        """Send notification via specific channel."""
        if channel == 'websocket':
            return self._send_via_websocket(notification)
        elif channel == 'email':
            return self._send_via_email(notification)
        elif channel == 'sms':
            return self._send_via_sms(notification)
        elif channel == 'push':
            return self._send_via_push(notification)
        else:
            logger.error(f"Unknown notification channel: {channel}")
            return False
    
    def _send_via_websocket(self, notification: PushNotification) -> bool:
        """Send notification via WebSocket."""
        try:
            room_name = self.notification_config['channels']['websocket']['room']
            
            message = {
                'type': 'fraud_notification',
                'notification': {
                    'id': notification.id,
                    'type': notification.type.value,
                    'priority': notification.priority.value,
                    'title': notification.title,
                    'message': notification.message,
                    'data': notification.data,
                    'created_at': notification.created_at.isoformat(),
                    'metadata': notification.metadata
                }
            }
            
            # Send to WebSocket room
            async_to_sync(self.channel_layer.group_send)(
                room_name,
                {
                    'type': 'notification_message',
                    'message': message
                }
            )
            
            logger.debug(f"WebSocket notification sent: {notification.id}")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
            return False
    
    def _send_via_email(self, notification: PushNotification) -> bool:
        """Send notification via email."""
        try:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            
            recipient_ids = notification.recipient_ids or []
            if not recipient_ids:
                logger.warning(f"No recipients for email notification: {notification.id}")
                return False
            
            # Get recipient emails
            recipient_emails = []
            for user_id in recipient_ids:
                try:
                    user = User.objects.get(pk=user_id)
                    recipient_emails.append(user.email)
                except User.DoesNotExist:
                    logger.warning(f"User not found for email notification: {user_id}")
            
            if not recipient_emails:
                logger.warning(f"No valid email recipients for notification: {notification.id}")
                return False
            
            # Render email template
            template_name = f"fraud/{notification.type.value}_notification.html"
            context = {
                'notification': notification,
                'data': notification.data or {}
            }
            
            try:
                html_message = render_to_string(template_name, context)
            except Exception as e:
                logger.warning("Template rendering failed, falling back to plain text: %s", e)
                # Fallback to plain text if template not found
                html_message = f"""
                <h2>{notification.title}</h2>
                <p>{notification.message}</p>
                <p>Priority: {notification.priority.value.upper()}</p>
                <p>Time: {notification.created_at}</p>
                """
            
            # Send email
            send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@company.com'),
                recipient_list=recipient_emails,
                html_message=html_message,
                fail_silently=False
            )
            
            logger.debug(f"Email notification sent to {len(recipient_emails)} recipients: {notification.id}")
            return True
            
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False
    
    def _send_via_sms(self, notification: PushNotification) -> bool:
        """Send notification via SMS."""
        # Placeholder for SMS implementation
        # In practice, this would integrate with SMS providers like Twilio
        logger.info(f"SMS notification (not implemented): {notification.id}")
        return True
    
    def _send_via_push(self, notification: PushNotification) -> bool:
        """Send notification via push notification service."""
        # Placeholder for push notification implementation
        # In practice, this would integrate with FCM, APNS, etc.
        logger.info(f"Push notification (not implemented): {notification.id}")
        return True
    
    def _format_fraud_alert_message(self, alert_data: Dict[str, Any]) -> str:
        """Format fraud alert message."""
        user_id = alert_data.get('user_id', 'Unknown')
        alert_type = alert_data.get('alert_type', 'Unknown')
        severity = alert_data.get('severity', 'Unknown')
        
        return f"Fraud alert detected for user {user_id}. Type: {alert_type}, Severity: {severity}"
    
    def _format_case_message(self, case_data: Dict[str, Any], action: str) -> str:
        """Format case notification message."""
        case_id = case_data.get('case_id', 'Unknown')
        user_id = case_data.get('user_id', 'Unknown')
        risk_score = case_data.get('risk_score', 'Unknown')
        
        return f"Fraud case {action} for user {user_id}. Case ID: {case_id}, Risk Score: {risk_score}"
    
    def _get_recipient_ids_for_alert(self, alert_data: Dict[str, Any]) -> List[Union[int, str]]:
        """Get recipient IDs for fraud alert."""
        # Get fraud analysts and security staff
        return self._get_analyst_ids() + self._get_security_staff_ids()
    
    def _get_recipient_ids_for_case(self, case_data: Dict[str, Any]) -> List[Union[int, str]]:
        """Get recipient IDs for case notification."""
        recipients = self._get_analyst_ids()
        
        # Add assigned user if exists
        assigned_to = case_data.get('assigned_to')
        if assigned_to:
            recipients.append(assigned_to)
        
        return recipients
    
    def _get_recipient_ids_for_risk_change(self, user_id: Union[int, str], 
                                          new_score: int) -> List[Union[int, str]]:
        """Get recipient IDs for risk score change."""
        recipients = []
        
        # Include for high risk scores
        if new_score >= 70:
            recipients.extend(self._get_analyst_ids())
            recipients.extend(self._get_security_staff_ids())
        elif new_score >= 50:
            recipients.extend(self._get_analyst_ids())
        
        return recipients
    
    def _get_system_admin_ids(self) -> List[Union[int, str]]:
        """Get system administrator IDs."""
        try:
            return list(
                User.objects.filter(
                    is_staff=True,
                    is_superuser=True,
                    is_active=True
                ).values_list('id', flat=True)
            )
        except Exception as e:
            logger.error(f"Error getting system admin IDs: {e}")
            return []
    
    def _get_analyst_ids(self) -> List[Union[int, str]]:
        """Get fraud analyst IDs."""
        try:
            return list(
                User.objects.filter(
                    groups__name='fraud_analyst',
                    is_active=True
                ).values_list('id', flat=True)
            )
        except Exception as e:
            logger.error(f"Error getting analyst IDs: {e}")
            return []
    
    def _get_security_staff_ids(self) -> List[Union[int, str]]:
        """Get security staff IDs."""
        try:
            return list(
                User.objects.filter(
                    groups__name__in=['security_staff', 'fraud_investigator'],
                    is_active=True
                ).values_list('id', flat=True)
            )
        except Exception as e:
            logger.error(f"Error getting security staff IDs: {e}")
            return []
    
    def _get_compliance_officer_ids(self) -> List[Union[int, str]]:
        """Get compliance officer IDs."""
        try:
            return list(
                User.objects.filter(
                    groups__name='compliance_officer',
                    is_active=True
                ).values_list('id', flat=True)
            )
        except Exception as e:
            logger.error(f"Error getting compliance officer IDs: {e}")
            return []
    
    def get_notification_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        return {
            'statistics': self.stats,
            'enabled_channels': self.enabled_channels,
            'queue_size': len(self.notification_queue),
            'configuration': {
                'max_queue_size': self.max_queue_size,
                'default_ttl': self.notification_config['default_ttl'],
                'batch_size': self.notification_config['batch_size']
            }
        }


class NotificationConsumer:
    """
    WebSocket consumer for fraud detection notifications.
    
    Handles real-time notification delivery to connected clients.
    """
    
    def __init__(self):
        """Initialize notification consumer."""
        self.channel_layer = get_channel_layer()
        self.room_name = 'fraud_notifications'
    
    def connect_user(self, channel_name: str, user_id: Union[int, str]):
        """Connect user to notification room."""
        try:
            async_to_sync(self.channel_layer.group_add)(
                self.room_name,
                channel_name
            )
            logger.info(f"User {user_id} connected to notifications: {channel_name}")
        except Exception as e:
            logger.error(f"Failed to connect user {user_id} to notifications: {e}")
    
    def disconnect_user(self, channel_name: str, user_id: Union[int, str]):
        """Disconnect user from notification room."""
        try:
            async_to_sync(self.channel_layer.group_discard)(
                self.room_name,
                channel_name
            )
            logger.info(f"User {user_id} disconnected from notifications: {channel_name}")
        except Exception as e:
            logger.error(f"Failed to disconnect user {user_id} from notifications: {e}")


# Global instances
_notification_manager = None
_notification_consumer = None


def get_notification_manager() -> PushNotificationManager:
    """Get or create notification manager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = PushNotificationManager()
    return _notification_manager


def get_notification_consumer() -> NotificationConsumer:
    """Get or create notification consumer instance."""
    global _notification_consumer
    if _notification_consumer is None:
        _notification_consumer = NotificationConsumer()
    return _notification_consumer


def send_fraud_alert_notification(alert_data: Dict[str, Any], 
                                  priority: NotificationPriority = NotificationPriority.HIGH) -> bool:
    """
    Convenience function to send fraud alert notification.
    
    Args:
        alert_data: Alert data
        priority: Notification priority
        
    Returns:
        True if sent successfully
    """
    manager = get_notification_manager()
    return manager.send_fraud_alert(alert_data, priority)


def send_case_notification(case_data: Dict[str, Any], action: str = 'created') -> bool:
    """
    Convenience function to send case notification.
    
    Args:
        case_data: Case data
        action: Action type
        
    Returns:
        True if sent successfully
    """
    manager = get_notification_manager()
    return manager.send_case_notification(case_data, action)


def send_system_alert(alert_data: Dict[str, Any], 
                      priority: NotificationPriority = NotificationPriority.MEDIUM) -> bool:
    """
    Convenience function to send system alert.
    
    Args:
        alert_data: Alert data
        priority: Notification priority
        
    Returns:
        True if sent successfully
    """
    manager = get_notification_manager()
    return manager.send_system_alert(alert_data, priority)
