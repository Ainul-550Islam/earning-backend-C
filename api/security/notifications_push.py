"""
Security Push Notifications Module
Push notification system for security alerts
"""

import logging
import json
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from django.core.cache import cache
from django.conf import settings

from .models import SecurityLog, SecurityIncident
from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.notifications_push')


class NotificationType:
    """Notification types"""
    SECURITY_ALERT = 'security_alert'
    INCIDENT_CREATED = 'incident_created'
    INCIDENT_UPDATED = 'incident_updated'
    THREAT_DETECTED = 'threat_detected'
    USER_BANNED = 'user_banned'
    SYSTEM_HEALTH = 'system_health'
    COMPLIANCE_VIOLATION = 'compliance_violation'
    ANOMALY_DETECTED = 'anomaly_detected'


class NotificationPriority:
    """Notification priority levels"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class NotificationStatus:
    """Notification status"""
    PENDING = 'pending'
    SENT = 'sent'
    FAILED = 'failed'
    DELIVERED = 'delivered'
    READ = 'read'


class PushNotification(models.Model):
    """Push notification model"""
    
    id = models.UUIDField(primary_key=True, default=SecurityUtils.generate_uuid)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_notifications')
    notification_type = models.CharField(max_length=50, choices=[
        (NotificationType.SECURITY_ALERT, 'Security Alert'),
        (NotificationType.INCIDENT_CREATED, 'Incident Created'),
        (NotificationType.INCIDENT_UPDATED, 'Incident Updated'),
        (NotificationType.THREAT_DETECTED, 'Threat Detected'),
        (NotificationType.USER_BANNED, 'User Banned'),
        (NotificationType.SYSTEM_HEALTH, 'System Health'),
        (NotificationType.COMPLIANCE_VIOLATION, 'Compliance Violation'),
        (NotificationType.ANOMALY_DETECTED, 'Anomaly Detected'),
    ])
    
    priority = models.CharField(max_length=20, choices=[
        (NotificationPriority.LOW, 'Low'),
        (NotificationPriority.MEDIUM, 'Medium'),
        (NotificationPriority.HIGH, 'High'),
        (NotificationPriority.CRITICAL, 'Critical'),
    ])
    
    status = models.CharField(max_length=20, choices=[
        (NotificationStatus.PENDING, 'Pending'),
        (NotificationStatus.SENT, 'Sent'),
        (NotificationStatus.FAILED, 'Failed'),
        (NotificationStatus.DELIVERED, 'Delivered'),
        (NotificationStatus.READ, 'Read'),
    ], default=NotificationStatus.PENDING)
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    
    # Delivery
    device_token = models.CharField(max_length=255, blank=True)
    platform = models.CharField(max_length=20, choices=[
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
        ('email', 'Email'),
        ('sms', 'SMS'),
    ])
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'security_push_notifications'
        verbose_name = "Push Notification"
        verbose_name_plural = "Push Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def is_expired(self) -> bool:
        """Check if notification has expired"""
        if self.expires_at and self.expires_at <= timezone.now():
            return True
        return False
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
        self.save()
    
    def mark_as_delivered(self):
        """Mark notification as delivered"""
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save()
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.status = NotificationStatus.READ
        self.read_at = timezone.now()
        self.save()


class DeviceToken(models.Model):
    """Device token model for push notifications"""
    
    id = models.UUIDField(primary_key=True, default=SecurityUtils.generate_uuid)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, choices=[
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    ])
    
    # Device information
    device_id = models.CharField(max_length=255, blank=True)
    device_name = models.CharField(max_length=255, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'security_device_tokens'
        verbose_name = "Device Token"
        verbose_name_plural = "Device Tokens"
        ordering = ['-last_used_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['token']),
            models.Index(fields=['platform']),
        ]
    
    def __str__(self):
        return f"{self.platform} - {self.user.username}"


class PushNotificationService:
    """Service for managing push notifications"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize notification providers"""
        # iOS Provider (APNS)
        if hasattr(settings, 'APNS_KEY_ID'):
            self.providers['ios'] = APNSProvider()
        
        # Android Provider (FCM)
        if hasattr(settings, 'FCM_SERVER_KEY'):
            self.providers['android'] = FCMProvider()
        
        # Web Provider (Web Push)
        self.providers['web'] = WebPushProvider()
        
        # Email Provider
        if hasattr(settings, 'EMAIL_HOST'):
            self.providers['email'] = EmailProvider()
        
        # SMS Provider
        if hasattr(settings, 'SMS_PROVIDER'):
            self.providers['sms'] = SMSProvider()
    
    def send_notification(self, user: User, title: str, message: str,
                        notification_type: str = NotificationType.SECURITY_ALERT,
                        priority: str = NotificationPriority.MEDIUM,
                        data: Dict[str, Any] = None,
                        platform: str = None,
                        device_token: str = None) -> PushNotification:
        """Send push notification to user"""
        notification = PushNotification.objects.create(
            user=user,
            notification_type=notification_type,
            priority=priority,
            title=title,
            message=message,
            data=data or {},
            platform=platform,
            device_token=device_token
        )
        
        # Send notification
        self._send_notification(notification)
        
        return notification
    
    def send_bulk_notification(self, users: List[User], title: str, message: str,
                              notification_type: str = NotificationType.SECURITY_ALERT,
                              priority: str = NotificationPriority.MEDIUM,
                              data: Dict[str, Any] = None) -> List[PushNotification]:
        """Send bulk notification to multiple users"""
        notifications = []
        
        for user in users:
            notification = PushNotification.objects.create(
                user=user,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=message,
                data=data or {}
            )
            notifications.append(notification)
        
        # Send notifications in bulk
        self._send_bulk_notifications(notifications)
        
        return notifications
    
    def send_security_alert(self, user: User, alert_data: Dict[str, Any]) -> PushNotification:
        """Send security alert notification"""
        title = f"Security Alert: {alert_data.get('type', 'Unknown')}"
        message = alert_data.get('description', 'Security event detected')
        
        return self.send_notification(
            user=user,
            title=title,
            message=message,
            notification_type=NotificationType.SECURITY_ALERT,
            priority=alert_data.get('severity', NotificationPriority.MEDIUM),
            data=alert_data
        )
    
    def send_incident_notification(self, users: List[User], incident: SecurityIncident,
                                 action: str = 'created') -> List[PushNotification]:
        """Send incident notification"""
        title = f"Incident {action.title()}: {incident.title}"
        message = f"Security incident {action}: {incident.description[:100]}..."
        
        data = {
            'incident_id': str(incident.id),
            'incident_type': incident.incident_type,
            'severity': incident.severity,
            'priority': incident.priority,
            'action': action
        }
        
        notification_type = f"incident_{action}"
        return self.send_bulk_notification(
            users=users,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=incident.priority,
            data=data
        )
    
    def send_threat_notification(self, users: List[User], threat_data: Dict[str, Any]) -> List[PushNotification]:
        """Send threat notification"""
        title = f"Threat Detected: {threat_data.get('type', 'Unknown')}"
        message = threat_data.get('description', 'Security threat detected')
        
        return self.send_bulk_notification(
            users=users,
            title=title,
            message=message,
            notification_type=NotificationType.THREAT_DETECTED,
            priority=NotificationPriority.HIGH,
            data=threat_data
        )
    
    def register_device_token(self, user: User, token: str, platform: str,
                              device_info: Dict[str, Any] = None) -> DeviceToken:
        """Register device token"""
        # Deactivate existing tokens for same device
        device_id = device_info.get('device_id') if device_info else None
        if device_id:
            DeviceToken.objects.filter(
                user=user,
                device_id=device_id
            ).update(is_active=False)
        
        # Create or update token
        device_token, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': user,
                'platform': platform,
                'device_id': device_id or '',
                'device_name': device_info.get('device_name', '') if device_info else '',
                'app_version': device_info.get('app_version', '') if device_info else '',
                'os_version': device_info.get('os_version', '') if device_info else '',
                'is_active': True,
                'metadata': device_info or {}
            }
        )
        
        if not created:
            device_token.last_used_at = timezone.now()
            device_token.save()
        
        return device_token
    
    def unregister_device_token(self, token: str) -> bool:
        """Unregister device token"""
        try:
            deleted_count = DeviceToken.objects.filter(token=token).delete()
            return deleted_count[0] > 0
        except Exception as e:
            logger.error(f"Error unregistering device token: {e}")
            return False
    
    def get_user_tokens(self, user: User, platform: str = None) -> List[DeviceToken]:
        """Get user's device tokens"""
        tokens = DeviceToken.objects.filter(user=user, is_active=True)
        
        if platform:
            tokens = tokens.filter(platform=platform)
        
        return list(tokens)
    
    def _send_notification(self, notification: PushNotification):
        """Send single notification"""
        try:
            # Get user's device tokens
            if notification.device_token:
                # Send to specific device
                tokens = [DeviceToken(token=notification.device_token, platform=notification.platform)]
            else:
                # Send to all user's devices
                tokens = self.get_user_tokens(notification.user, notification.platform)
            
            if not tokens:
                notification.status = NotificationStatus.FAILED
                notification.save()
                return
            
            # Send via appropriate provider
            sent_count = 0
            for token in tokens:
                provider = self.providers.get(token.platform)
                if provider:
                    try:
                        success = provider.send_notification(notification, token)
                        if success:
                            sent_count += 1
                    except Exception as e:
                        logger.error(f"Provider {token.platform} error: {e}")
            
            if sent_count > 0:
                notification.mark_as_sent()
                notification.mark_as_delivered()
            else:
                notification.status = NotificationStatus.FAILED
                notification.save()
        
        except Exception as e:
            logger.error(f"Error sending notification {notification.id}: {e}")
            notification.status = NotificationStatus.FAILED
            notification.save()
    
    def _send_bulk_notifications(self, notifications: List[PushNotification]):
        """Send bulk notifications"""
        for notification in notifications:
            self._send_notification(notification)
    
    def get_notification_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get notification statistics"""
        from django.db.models import Count
        
        start_date = timezone.now() - timedelta(days=days)
        
        stats = {
            'total_notifications': PushNotification.objects.filter(created_at__gte=start_date).count(),
            'by_status': dict(
                PushNotification.objects.filter(created_at__gte=start_date)
                .values('status')
                .annotate(count=Count('id'))
                .values_list('status', 'count')
            ),
            'by_type': dict(
                PushNotification.objects.filter(created_at__gte=start_date)
                .values('notification_type')
                .annotate(count=Count('id'))
                .values_list('notification_type', 'count')
            ),
            'by_priority': dict(
                PushNotification.objects.filter(created_at__gte=start_date)
                .values('priority')
                .annotate(count=Count('id'))
                .values_list('priority', 'count')
            ),
            'by_platform': dict(
                PushNotification.objects.filter(created_at__gte=start_date)
                .values('platform')
                .annotate(count=Count('id'))
                .values_list('platform', 'count')
            )
        }
        
        return stats
    
    def cleanup_expired_notifications(self) -> int:
        """Clean up expired notifications"""
        deleted_count = PushNotification.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        
        return deleted_count[0]
    
    def cleanup_old_notifications(self, days: int = 90) -> int:
        """Clean up old notifications"""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = PushNotification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        return deleted_count[0]


class BaseNotificationProvider:
    """Base notification provider"""
    
    def send_notification(self, notification: PushNotification, device_token: DeviceToken) -> bool:
        """Send notification - override in subclasses"""
        raise NotImplementedError("Subclasses must implement send_notification")


class APNSProvider(BaseNotificationProvider):
    """Apple Push Notification Service provider"""
    
    def __init__(self):
        self.key_id = getattr(settings, 'APNS_KEY_ID')
        self.team_id = getattr(settings, 'APNS_TEAM_ID')
        self.bundle_id = getattr(settings, 'APNS_BUNDLE_ID')
        self.private_key = getattr(settings, 'APNS_PRIVATE_KEY')
    
    def send_notification(self, notification: PushNotification, device_token: DeviceToken) -> bool:
        """Send APNS notification"""
        try:
            import pyapns
            
            client = pyapns.APNSClient(
                team_id=self.team_id,
                key_id=self.key_id,
                use_sandbox=getattr(settings, 'APNS_USE_SANDBOX', False),
                private_key=self.private_key
            )
            
            # Create notification payload
            payload = {
                'aps': {
                    'alert': {
                        'title': notification.title,
                        'body': notification.message
                    },
                    'sound': 'default',
                    'badge': 1,
                    'data': notification.data or {}
                }
            }
            
            # Send notification
            result = client.send_notification(
                device_token=device_token.token,
                payload=payload,
                topic=self.bundle_id
            )
            
            return result.status_code == 200
            
        except Exception as e:
            logger.error(f"APNS error: {e}")
            return False


class FCMProvider(BaseNotificationProvider):
    """Firebase Cloud Messaging provider"""
    
    def __init__(self):
        self.server_key = getattr(settings, 'FCM_SERVER_KEY')
    
    def send_notification(self, notification: PushNotification, device_token: DeviceToken) -> bool:
        """Send FCM notification"""
        try:
            import requests
            
            url = 'https://fcm.googleapis.com/fcm/send'
            
            headers = {
                'Authorization': f'key={self.server_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': device_token.token,
                'notification': {
                    'title': notification.title,
                    'body': notification.message,
                    'sound': 'default'
                },
                'data': notification.data or {},
                'priority': 'high' if notification.priority == NotificationPriority.CRITICAL else 'normal'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"FCM error: {e}")
            return False


class WebPushProvider(BaseNotificationProvider):
    """Web Push notification provider"""
    
    def send_notification(self, notification: PushNotification, device_token: DeviceToken) -> bool:
        """Send Web Push notification"""
        try:
            import requests
            
            # This would integrate with a Web Push service like Pushpad or custom implementation
            # For now, return True as placeholder
            return True
            
        except Exception as e:
            logger.error(f"Web Push error: {e}")
            return False


class EmailProvider(BaseNotificationProvider):
    """Email notification provider"""
    
    def send_notification(self, notification: PushNotification, device_token: DeviceToken) -> bool:
        """Send email notification"""
        try:
            from django.core.mail import send_mail
            
            subject = notification.title
            message = notification.message
            
            # Add notification data to email body
            if notification.data:
                message += f"\n\nAdditional Information:\n{json.dumps(notification.data, indent=2)}"
            
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL'),
                [notification.user.email],
                fail_silently=False
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Email error: {e}")
            return False


class SMSProvider(BaseNotificationProvider):
    """SMS notification provider"""
    
    def send_notification(self, notification: PushNotification, device_token: DeviceToken) -> bool:
        """Send SMS notification"""
        try:
            # This would integrate with an SMS service like Twilio
            # For now, return True as placeholder
            return True
            
        except Exception as e:
            logger.error(f"SMS error: {e}")
            return False


class NotificationScheduler:
    """Scheduler for timed notifications"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def schedule_notification(self, notification: PushNotification, delay_minutes: int = None,
                             delay_hours: int = None, delay_days: int = None):
        """Schedule notification for later delivery"""
        delay = timedelta()
        
        if delay_minutes:
            delay += timedelta(minutes=delay_minutes)
        if delay_hours:
            delay += timedelta(hours=delay_hours)
        if delay_days:
            delay += timedelta(days=delay_days)
        
        if delay.total_seconds() > 0:
            send_at = timezone.now() + delay
            notification.expires_at = send_at
            
            # Store in cache for scheduled delivery
            cache_key = f"scheduled_notification_{notification.id}"
            cache.set(cache_key, True, int(delay.total_seconds()))
            
            logger.info(f"Scheduled notification {notification.id} for {send_at}")
    
    def process_scheduled_notifications(self):
        """Process scheduled notifications"""
        # This would be called by a background task
        # For now, it's a placeholder
        pass


# Global notification service
notification_service = PushNotificationService()


# Notification handlers for security events
class SecurityNotificationHandler:
    """Handler for security event notifications"""
    
    def __init__(self, notification_service: PushNotificationService):
        self.notification_service = notification_service
    
    def on_security_log_created(self, log_entry):
        """Handle security log creation"""
        if log_entry.severity in ['high', 'critical']:
            # Get security admins
            security_admins = User.objects.filter(is_staff=True, is_active=True)
            
            if security_admins.exists():
                self.notification_service.send_security_alert(
                    user=security_admins.first(),
                    alert_data={
                        'type': log_entry.security_type,
                        'severity': log_entry.severity,
                        'description': log_entry.description,
                        'ip_address': log_entry.ip_address,
                        'timestamp': log_entry.created_at.isoformat()
                    }
                )
    
    def on_incident_created(self, incident):
        """Handle incident creation"""
        # Get security admins
        security_admins = User.objects.filter(is_staff=True, is_active=True)
        
        if security_admins.exists():
            self.notification_service.send_incident_notification(
                users=list(security_admins),
                incident=incident,
                action='created'
            )
    
    def on_threat_detected(self, threat_data):
        """Handle threat detection"""
        # Get security admins
        security_admins = User.objects.filter(is_staff=True, is_active=True)
        
        if security_admins.exists():
            self.notification_service.send_threat_notification(
                users=list(security_admins),
                threat_data=threat_data
            )


# Global notification handler
notification_handler = SecurityNotificationHandler(notification_service)


# Export classes and utilities
__all__ = [
    'NotificationType',
    'NotificationPriority',
    'NotificationStatus',
    'PushNotification',
    'DeviceToken',
    'PushNotificationService',
    'notification_service',
    'BaseNotificationProvider',
    'APNSProvider',
    'FCMProvider',
    'WebPushProvider',
    'EmailProvider',
    'SMSProvider',
    'NotificationScheduler',
    'SecurityNotificationHandler',
    'notification_handler'
]