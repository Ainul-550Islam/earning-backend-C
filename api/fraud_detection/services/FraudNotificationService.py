# =============================================================================
# fraud_detection/services/FraudNotificationService.py
# =============================================================================
"""
Fraud Notification Service.

Comprehensive service for managing fraud notifications including
multi-channel delivery, templates, and escalation.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.cache import cache

from api.fraud_detection.models import FraudNotification, FraudAlert, FraudCase
from api.fraud_detection.choices import NotificationType, AlertPriority
from api.fraud_detection.constants import CACHE_KEYS

# PushNotificationManager — was floating, now delegated to from here
try:
    from api.fraud_detection.notifications_push import (
        get_notification_manager as _get_push_manager,
        send_fraud_alert_notification as _push_send_alert,
        send_case_notification as _push_send_case,
    )
    _PUSH_AVAILABLE = True
except ImportError:
    _PUSH_AVAILABLE = False
    _get_push_manager = None
    _push_send_alert  = None
    _push_send_case   = None

logger = logging.getLogger(__name__)


class FraudNotificationService:
    """Service for managing fraud notifications and multi-channel delivery."""
    
    def __init__(self):
        self.cache_ttl = 1800  # 30 minutes
        self.max_retries = 3
        self.retry_delay = 60  # seconds
    
    def create_notification(self, user_id: int, notification_type: str,
                          message: str, fraud_case_id: Optional[int] = None,
                          fraud_alert_id: Optional[int] = None,
                          metadata: Optional[Dict] = None) -> FraudNotification:
        """
        Create a new fraud notification.
        
        Args:
            user_id: User ID to notify
            notification_type: Type of notification
            message: Notification message
            fraud_case_id: Related fraud case ID
            fraud_alert_id: Related fraud alert ID
            metadata: Additional metadata
            
        Returns:
            Created FraudNotification instance
        """
        try:
            with transaction.atomic():
                notification = FraudNotification.objects.create(
                    user_id=user_id,
                    notification_type=notification_type,
                    message=message,
                    fraud_case_id=fraud_case_id,
                    fraud_alert_id=fraud_alert_id,
                    metadata=metadata or {},
                )
                
                # Queue for delivery
                self._queue_notification(notification)
                
                logger.info(f"Created notification {notification.id} for user {user_id}")
                return notification
                
        except Exception as e:
            logger.error(f"Error creating notification for user {user_id}: {e}")
            raise
    
    def send_notification(self, notification_id: int) -> bool:
        """
        Send a notification through appropriate channels.
        
        Args:
            notification_id: Notification ID to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            notification = FraudNotification.objects.select_related('user').get(id=notification_id)
            
            if notification.is_sent:
                logger.warning(f"Notification {notification_id} already sent")
                return True
            
            success = False
            
            # Send based on notification type
            if notification.notification_type == NotificationType.EMAIL:
                success = self._send_email_notification(notification)
            elif notification.notification_type == NotificationType.SMS:
                success = self._send_sms_notification(notification)
            elif notification.notification_type == NotificationType.PUSH:
                success = self._send_push_notification(notification)
            elif notification.notification_type == NotificationType.WEBHOOK:
                success = self._send_webhook_notification(notification)
            elif notification.notification_type == NotificationType.DASHBOARD:
                success = self._send_dashboard_notification(notification)
            
            # Update notification status
            if success:
                notification.is_sent = True
                notification.sent_at = timezone.now()
                notification.save()
                
                # Log successful delivery
                logger.info(f"Successfully sent notification {notification_id} via {notification.notification_type}")
            else:
                # Increment retry count
                notification.retry_count += 1
                notification.last_retry_at = timezone.now()
                
                # Mark as failed if max retries reached
                if notification.retry_count >= self.max_retries:
                    notification.is_sent = False
                    notification.failed_at = timezone.now()
                    logger.error(f"Notification {notification_id} failed after {self.max_retries} retries")
                
                notification.save()
            
            return success
            
        except FraudNotification.DoesNotExist:
            logger.error(f"Notification {notification_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error sending notification {notification_id}: {e}")
            return False
    
    def send_bulk_notifications(self, notification_type: str, message: str,
                              user_ids: List[int], metadata: Optional[Dict] = None) -> Dict[str, int]:
        """
        Send bulk notifications to multiple users.
        
        Args:
            notification_type: Type of notification
            message: Notification message
            user_ids: List of user IDs to notify
            metadata: Additional metadata
            
        Returns:
            Dictionary with success and error counts
        """
        success_count = 0
        error_count = 0
        
        try:
            with transaction.atomic():
                notifications = []
                
                for user_id in user_ids:
                    try:
                        notification = FraudNotification.objects.create(
                            user_id=user_id,
                            notification_type=notification_type,
                            message=message,
                            metadata=metadata or {},
                        )
                        notifications.append(notification)
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Error creating bulk notification for user {user_id}: {e}")
                        error_count += 1
                
                # Queue all notifications for delivery
                for notification in notifications:
                    self._queue_notification(notification)
                
                logger.info(f"Created {success_count} bulk notifications, {error_count} errors")
                return {'success': success_count, 'errors': error_count}
                
        except Exception as e:
            logger.error(f"Error in bulk notification creation: {e}")
            return {'success': 0, 'errors': len(user_ids)}
    
    def create_alert_notification(self, alert_id: int) -> bool:
        """
        Create notification for a fraud alert.
        
        Args:
            alert_id: Fraud alert ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            alert = FraudAlert.objects.select_related('user').get(id=alert_id)
            
            # Determine notification recipients
            recipients = self._get_alert_recipients(alert)
            
            # Create notifications for all recipients
            success_count = 0
            for user_id in recipients:
                try:
                    message = self._generate_alert_message(alert)
                    
                    FraudNotification.objects.create(
                        user_id=user_id,
                        notification_type=NotificationType.DASHBOARD,
                        message=message,
                        fraud_alert_id=alert_id,
                        metadata={
                            'alert_id': alert.id,
                            'alert_type': alert.alert_type,
                            'priority': alert.priority,
                        }
                    )
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"Error creating alert notification for user {user_id}: {e}")
            
            logger.info(f"Created {success_count} notifications for alert {alert_id}")
            return success_count > 0
            
        except FraudAlert.DoesNotExist:
            logger.error(f"Alert {alert_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error creating alert notification for alert {alert_id}: {e}")
            return False
    
    def create_case_notification(self, case_id: int, notification_type: str,
                              message: Optional[str] = None) -> bool:
        """
        Create notification for a fraud case.
        
        Args:
            case_id: Fraud case ID
            notification_type: Type of notification
            message: Optional custom message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            case = FraudCase.objects.select_related('user', 'assigned_to').get(id=case_id)
            
            # Determine recipients based on notification type
            recipients = self._get_case_recipients(case, notification_type)
            
            # Generate message if not provided
            if not message:
                message = self._generate_case_message(case, notification_type)
            
            # Create notifications
            success_count = 0
            for user_id in recipients:
                try:
                    FraudNotification.objects.create(
                        user_id=user_id,
                        notification_type=notification_type,
                        message=message,
                        fraud_case_id=case_id,
                        metadata={
                            'case_id': case.id,
                            'case_number': case.case_number,
                            'priority': case.priority,
                        }
                    )
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"Error creating case notification for user {user_id}: {e}")
            
            logger.info(f"Created {success_count} notifications for case {case_id}")
            return success_count > 0
            
        except FraudCase.DoesNotExist:
            logger.error(f"Case {case_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error creating case notification for case {case_id}: {e}")
            return False
    
    def get_notification_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get notification delivery statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            stats = {}
            
            # Total notifications
            stats['total_notifications'] = FraudNotification.objects.filter(
                created_at__gte=cutoff
            ).count()
            
            # Sent notifications
            stats['sent_notifications'] = FraudNotification.objects.filter(
                created_at__gte=cutoff,
                is_sent=True
            ).count()
            
            # Failed notifications
            stats['failed_notifications'] = FraudNotification.objects.filter(
                created_at__gte=cutoff,
                failed_at__isnull=False
            ).count()
            
            # By type
            for notification_type, _ in NotificationType.choices:
                stats[f'{notification_type}_total'] = FraudNotification.objects.filter(
                    notification_type=notification_type,
                    created_at__gte=cutoff
                ).count()
                
                stats[f'{notification_type}_sent'] = FraudNotification.objects.filter(
                    notification_type=notification_type,
                    created_at__gte=cutoff,
                    is_sent=True
                ).count()
            
            # Delivery rate
            if stats['total_notifications'] > 0:
                stats['delivery_rate'] = (stats['sent_notifications'] / stats['total_notifications']) * 100
            else:
                stats['delivery_rate'] = 0
            
            # Average delivery time
            delivered = FraudNotification.objects.filter(
                created_at__gte=cutoff,
                is_sent=True,
                sent_at__isnull=False
            )
            
            if delivered.exists():
                delivery_times = [(n.sent_at - n.created_at).total_seconds() for n in delivered]
                stats['avg_delivery_time_seconds'] = sum(delivery_times) / len(delivery_times)
            else:
                stats['avg_delivery_time_seconds'] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting notification statistics: {e}")
            return {}
    
    def retry_failed_notifications(self, max_age_hours: int = 24) -> Dict[str, int]:
        """
        Retry failed notifications that are not too old.
        
        Args:
            max_age_hours: Maximum age in hours to retry
            
        Returns:
            Dictionary with retry counts
        """
        try:
            cutoff = timezone.now() - timedelta(hours=max_age_hours)
            
            failed_notifications = FraudNotification.objects.filter(
                is_sent=False,
                failed_at__isnull=True,
                created_at__gte=cutoff,
                retry_count__lt=self.max_retries
            )
            
            retry_count = 0
            success_count = 0
            
            for notification in failed_notifications:
                try:
                    # Check if enough time has passed for retry
                    if notification.last_retry_at:
                        time_since_retry = timezone.now() - notification.last_retry_at
                        if time_since_retry.total_seconds() < self.retry_delay:
                            continue
                    
                    if self.send_notification(notification.id):
                        success_count += 1
                    
                    retry_count += 1
                    
                except Exception as e:
                    logger.error(f"Error retrying notification {notification.id}: {e}")
            
            logger.info(f"Retried {retry_count} failed notifications, {success_count} successful")
            return {'retried': retry_count, 'successful': success_count}
            
        except Exception as e:
            logger.error(f"Error retrying failed notifications: {e}")
            return {'retried': 0, 'successful': 0}
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _queue_notification(self, notification: FraudNotification):
        """Queue notification for background delivery."""
        try:
            from api.fraud_detection.tasks import send_pending_notifications
            
            # Queue for immediate delivery
            send_pending_notifications.apply_async(
                args=[],
                kwargs={'notification_ids': [notification.id]},
                countdown=1  # Small delay to ensure transaction is complete
            )
            
        except Exception as e:
            logger.error(f"Error queuing notification {notification.id}: {e}")
    
    def _send_email_notification(self, notification: FraudNotification) -> bool:
        """
        Send email notification.
        Delegates to PushNotificationManager email channel if available,
        otherwise falls back to direct Django send_mail().
        """
        try:
            if not notification.user or not notification.user.email:
                logger.warning("User %s has no email address", getattr(notification.user, 'id', '?'))
                return False

            # Try PushNotificationManager first (has templates + tracking)
            if _PUSH_AVAILABLE and _get_push_manager is not None:
                try:
                    push_mgr = _get_push_manager()
                    email_data = {
                        'to_email':         notification.user.email,
                        'subject':          f"Fraud Detection Alert: {notification.notification_type.title()}",
                        'body':             notification.message,
                        'notification_id':  notification.id,
                        'user_id':          notification.user_id,
                        'metadata':         notification.metadata or {},
                    }
                    if hasattr(push_mgr, 'send_email'):
                        result = push_mgr.send_email(email_data)
                        if result:
                            return True
                except Exception as push_exc:
                    logger.debug("PushNotificationManager email failed, falling back: %s", push_exc)

            # Fallback: direct Django send_mail
            subject = f"Fraud Detection Alert: {notification.notification_type.title()}"
            try:
                html_message = render_to_string('fraud_detection/email_notification.html', {
                    'notification': notification,
                    'user':         notification.user,
                })
            except Exception:
                html_message = None

            send_mail(
                subject=subject,
                message=notification.message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@frauddetection.com'),
                recipient_list=[notification.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            return True

        except Exception as e:
            logger.error("Error sending email notification %d: %s", notification.id, e)
            return False
    
    def _send_sms_notification(self, notification: FraudNotification) -> bool:
        """Send SMS notification."""
        try:
            # In production, integrate with SMS service (Twilio, etc.)
            # For now, just log the SMS
            logger.info(f"SMS notification {notification.id}: {notification.message} to {notification.user.phone}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS notification {notification.id}: {e}")
            return False
    
    def _send_push_notification(self, notification: FraudNotification) -> bool:
        """
        Send push notification via PushNotificationManager (notifications_push.py).
        Supports WebSocket, Firebase FCM, and in-app channels.
        """
        try:
            if _PUSH_AVAILABLE and _get_push_manager is not None:
                push_mgr = _get_push_manager()
                push_data = {
                    'notification_id': notification.id,
                    'user_id':         notification.user_id,
                    'title':           f"Fraud Alert: {notification.notification_type}",
                    'body':            notification.message,
                    'notification_type': notification.notification_type,
                    'metadata':        notification.metadata or {},
                    'priority':        notification.metadata.get('priority', 'normal') if notification.metadata else 'normal',
                }
                # Try WebSocket first (real-time), fall back to FCM
                success = push_mgr.send_push(push_data)
                if success:
                    logger.info(
                        "PushNotificationManager delivered notification %d to user %d",
                        notification.id, notification.user_id,
                    )
                    return True
                # Fall through to basic logging if push fails
            # Fallback: basic log (original behavior)
            logger.info(
                "Push notification %d: %s → user %d",
                notification.id, notification.message, notification.user_id,
            )
            return True
        except Exception as e:
            logger.error("Error sending push notification %d: %s", notification.id, e)
            return False
    
    def _send_webhook_notification(self, notification: FraudNotification) -> bool:
        """Send webhook notification."""
        try:
            import requests
            
            webhook_url = getattr(settings, 'FRAUD_WEBHOOK_URL', None)
            if not webhook_url:
                logger.warning("No webhook URL configured")
                return False
            
            payload = {
                'notification_id': notification.id,
                'user_id': notification.user.id,
                'type': notification.notification_type,
                'message': notification.message,
                'timestamp': notification.created_at.isoformat(),
                'metadata': notification.metadata,
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error sending webhook notification {notification.id}: {e}")
            return False
    
    def _send_dashboard_notification(self, notification: FraudNotification) -> bool:
        """
        Send dashboard / in-app notification.
        Attempts real-time WebSocket push via PushNotificationManager,
        then falls back to DB-only (polled by frontend).
        """
        try:
            if _PUSH_AVAILABLE and _get_push_manager is not None:
                try:
                    push_mgr = _get_push_manager()
                    ws_data = {
                        'channel':           f'user_{notification.user_id}_notifications',
                        'event':             'fraud_notification',
                        'notification_id':   notification.id,
                        'message':           notification.message,
                        'notification_type': notification.notification_type,
                        'metadata':          notification.metadata or {},
                        'created_at':        notification.created_at.isoformat()
                                             if notification.created_at else None,
                    }
                    if hasattr(push_mgr, 'send_websocket'):
                        push_mgr.send_websocket(ws_data)
                        logger.info(
                            "WebSocket push sent for notification %d → user %d",
                            notification.id, notification.user_id,
                        )
                except Exception as ws_exc:
                    logger.debug("WebSocket push skipped: %s", ws_exc)
            # DB-only path is always the source of truth — frontend polls /notifications/
            return True
        except Exception as e:
            logger.error("Error sending dashboard notification %d: %s", notification.id, e)
            return False
    
    def _get_alert_recipients(self, alert: FraudAlert) -> List[int]:
        """Get recipients for fraud alert notification."""
        recipients = []
        
        # Add the user involved in the alert
        if alert.user:
            recipients.append(alert.user.id)
        
        # Add staff users for high priority alerts
        if alert.priority in [AlertPriority.HIGH, AlertPriority.CRITICAL]:
            from django.contrib.auth.models import User
            staff_users = User.objects.filter(is_staff=True, is_active=True).values_list('id', flat=True)
            recipients.extend(staff_users)
        
        return list(set(recipients))  # Remove duplicates
    
    def _get_case_recipients(self, case: FraudCase, notification_type: str) -> List[int]:
        """Get recipients for fraud case notification."""
        recipients = []
        
        # Add the user involved in the case
        if case.user:
            recipients.append(case.user.id)
        
        # Add assigned staff
        if case.assigned_to:
            recipients.append(case.assigned_to.id)
        
        # Add all staff for critical cases
        if case.priority == 'critical' and notification_type in ['escalate', 'resolve']:
            from django.contrib.auth.models import User
            staff_users = User.objects.filter(is_staff=True, is_active=True).values_list('id', flat=True)
            recipients.extend(staff_users)
        
        return list(set(recipients))  # Remove duplicates
    
    def _generate_alert_message(self, alert: FraudAlert) -> str:
        """Generate message for fraud alert notification."""
        return f"Fraud Alert: {alert.title} - {alert.description}"
    
    def _generate_case_message(self, case: FraudCase, notification_type: str) -> str:
        """Generate message for fraud case notification."""
        if notification_type == 'create':
            return f"New Fraud Case: {case.case_number} - {case.title}"
        elif notification_type == 'escalate':
            return f"Case Escalated: {case.case_number} - {case.title}"
        elif notification_type == 'resolve':
            return f"Case Resolved: {case.case_number} - {case.title}"
        else:
            return f"Case Update: {case.case_number} - {case.title}"
