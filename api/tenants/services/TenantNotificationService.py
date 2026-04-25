"""
Tenant Notification Service

This module provides business logic for managing tenant notifications
including notification creation, delivery, and management.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from ..models.analytics import TenantNotification
from ..models.core import Tenant
from .base import BaseService


class TenantNotificationService(BaseService):
    """
    Service class for managing tenant notifications.
    
    Provides business logic for notification operations including:
    - Notification creation and delivery
    - Notification management and tracking
    - Notification preferences and settings
    - Notification templates and formatting
    """
    
    @staticmethod
    def create_notification(tenant, title, message, notification_type='system', **kwargs):
        """
        Create a new notification for a tenant.
        
        Args:
            tenant (Tenant): Tenant to create notification for
            title (str): Notification title
            message (str): Notification message
            notification_type (str): Type of notification
            **kwargs: Additional notification fields
            
        Returns:
            TenantNotification: Created notification
            
        Raises:
            ValidationError: If notification data is invalid
        """
        try:
            with transaction.atomic():
                # Validate notification data
                TenantNotificationService._validate_notification_data(
                    title, message, notification_type, **kwargs
                )
                
                # Create notification
                notification = TenantNotification.objects.create(
                    tenant=tenant,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=kwargs.get('priority', 'medium'),
                    status=kwargs.get('status', 'pending'),
                    send_email=kwargs.get('send_email', False),
                    send_push=kwargs.get('send_push', False),
                    send_sms=kwargs.get('send_sms', False),
                    scheduled_at=kwargs.get('scheduled_at'),
                    expires_at=kwargs.get('expires_at'),
                    metadata=kwargs.get('metadata', {}),
                    action_url=kwargs.get('action_url'),
                    action_text=kwargs.get('action_text'),
                    icon=kwargs.get('icon'),
                    category=kwargs.get('category', 'general')
                )
                
                # Send notification immediately if not scheduled
                if not notification.scheduled_at:
                    TenantNotificationService._send_notification(notification)
                
                return notification
                
        except Exception as e:
            raise ValidationError(f"Failed to create notification: {str(e)}")
    
    @staticmethod
    def send_notification(notification):
        """
        Send a notification.
        
        Args:
            notification (TenantNotification): Notification to send
            
        Returns:
            TenantNotification: Sent notification
        """
        try:
            with transaction.atomic():
                # Update status to sending
                notification.status = 'sending'
                notification.sent_at = timezone.now()
                notification.save()
                
                # Send via different channels
                success = True
                
                if notification.send_email:
                    email_success = TenantNotificationService._send_email_notification(notification)
                    success = success and email_success
                
                if notification.send_push:
                    push_success = TenantNotificationService._send_push_notification(notification)
                    success = success and push_success
                
                if notification.send_sms:
                    sms_success = TenantNotificationService._send_sms_notification(notification)
                    success = success and sms_success
                
                # Update status based on success
                notification.status = 'sent' if success else 'failed'
                notification.save()
                
                return notification
                
        except Exception as e:
            notification.status = 'failed'
            notification.save()
            raise ValidationError(f"Failed to send notification: {str(e)}")
    
    @staticmethod
    def mark_as_read(notification, read_at=None):
        """
        Mark a notification as read.
        
        Args:
            notification (TenantNotification): Notification to mark as read
            read_at (datetime): When it was read (optional)
            
        Returns:
            TenantNotification: Updated notification
        """
        notification.status = 'read'
        notification.read_at = read_at or timezone.now()
        notification.save()
        return notification
    
    @staticmethod
    def mark_as_unread(notification):
        """
        Mark a notification as unread.
        
        Args:
            notification (TenantNotification): Notification to mark as unread
            
        Returns:
            TenantNotification: Updated notification
        """
        notification.status = 'sent'
        notification.read_at = None
        notification.save()
        return notification
    
    @staticmethod
    def archive_notification(notification):
        """
        Archive a notification.
        
        Args:
            notification (TenantNotification): Notification to archive
            
        Returns:
            TenantNotification: Archived notification
        """
        notification.status = 'archived'
        notification.save()
        return notification
    
    @staticmethod
    def delete_notification(notification):
        """
        Delete a notification.
        
        Args:
            notification (TenantNotification): Notification to delete
        """
        notification.delete()
    
    @staticmethod
    def get_tenant_notifications(tenant, status=None, category=None, unread_only=False):
        """
        Get notifications for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get notifications for
            status (str): Filter by status (optional)
            category (str): Filter by category (optional)
            unread_only (bool): Get only unread notifications
            
        Returns:
            QuerySet: Tenant notifications
        """
        queryset = TenantNotification.objects.filter(tenant=tenant)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if category:
            queryset = queryset.filter(category=category)
        
        if unread_only:
            queryset = queryset.filter(status='sent')
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def get_unread_count(tenant):
        """
        Get count of unread notifications for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get count for
            
        Returns:
            int: Unread notification count
        """
        return TenantNotification.objects.filter(
            tenant=tenant,
            status='sent'
        ).count()
    
    @staticmethod
    def mark_all_as_read(tenant):
        """
        Mark all notifications as read for a tenant.
        
        Args:
            tenant (Tenant): Tenant to mark notifications as read for
            
        Returns:
            int: Number of notifications marked as read
        """
        count = TenantNotification.objects.filter(
            tenant=tenant,
            status='sent'
        ).update(
            status='read',
            read_at=timezone.now()
        )
        return count
    
    @staticmethod
    def bulk_send_notifications(notifications):
        """
        Send multiple notifications in bulk.
        
        Args:
            notifications (list): List of TenantNotification objects
            
        Returns:
            dict: Bulk send results
        """
        results = {
            'total': len(notifications),
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        for notification in notifications:
            try:
                TenantNotificationService.send_notification(notification)
                results['sent'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(str(e))
        
        return results
    
    @staticmethod
    def schedule_notification(tenant, title, message, scheduled_at, **kwargs):
        """
        Schedule a notification for future delivery.
        
        Args:
            tenant (Tenant): Tenant to schedule notification for
            title (str): Notification title
            message (str): Notification message
            scheduled_at (datetime): When to send the notification
            **kwargs: Additional notification fields
            
        Returns:
            TenantNotification: Scheduled notification
        """
        return TenantNotificationService.create_notification(
            tenant=tenant,
            title=title,
            message=message,
            scheduled_at=scheduled_at,
            **kwargs
        )
    
    @staticmethod
    def process_scheduled_notifications():
        """
        Process all scheduled notifications that are due.
        
        Returns:
            dict: Processing results
        """
        now = timezone.now()
        scheduled_notifications = TenantNotification.objects.filter(
            status='pending',
            scheduled_at__lte=now
        )
        
        results = {
            'total': scheduled_notifications.count(),
            'processed': 0,
            'failed': 0,
            'errors': []
        }
        
        for notification in scheduled_notifications:
            try:
                TenantNotificationService.send_notification(notification)
                results['processed'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(str(e))
        
        return results
    
    @staticmethod
    def cleanup_old_notifications(days=90):
        """
        Clean up old notifications.
        
        Args:
            days (int): Number of days to keep notifications
            
        Returns:
            int: Number of notifications deleted
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        count = TenantNotification.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['read', 'archived', 'failed']
        ).delete()[0]
        
        return count
    
    @staticmethod
    def get_notification_statistics(tenant=None, days=30):
        """
        Get notification statistics.
        
        Args:
            tenant (Tenant): Specific tenant (optional)
            days (int): Number of days to analyze
            
        Returns:
            dict: Notification statistics
        """
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        queryset = TenantNotification.objects.filter(created_at__gte=start_date)
        
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        stats = {
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days,
            },
            'total_notifications': queryset.count(),
            'sent_notifications': queryset.filter(status='sent').count(),
            'read_notifications': queryset.filter(status='read').count(),
            'failed_notifications': queryset.filter(status='failed').count(),
            'notifications_by_type': {},
            'notifications_by_status': {},
            'notifications_by_priority': {},
            'delivery_rates': {}
        }
        
        # Count by type
        for notification_type in ['system', 'billing', 'security', 'onboarding', 'marketing']:
            stats['notifications_by_type'][notification_type] = queryset.filter(
                notification_type=notification_type
            ).count()
        
        # Count by status
        for status in ['pending', 'sending', 'sent', 'read', 'failed', 'archived']:
            stats['notifications_by_status'][status] = queryset.filter(
                status=status
            ).count()
        
        # Count by priority
        for priority in ['low', 'medium', 'high', 'critical']:
            stats['notifications_by_priority'][priority] = queryset.filter(
                priority=priority
            ).count()
        
        # Calculate delivery rates
        total_sent = stats['sent_notifications']
        total_read = stats['read_notifications']
        
        if total_sent > 0:
            stats['delivery_rates']['read_rate'] = (total_read / total_sent) * 100
        else:
            stats['delivery_rates']['read_rate'] = 0
        
        return stats
    
    @staticmethod
    def _validate_notification_data(title, message, notification_type, **kwargs):
        """
        Validate notification data.
        
        Args:
            title (str): Notification title
            message (str): Notification message
            notification_type (str): Type of notification
            **kwargs: Additional data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        if not title or not title.strip():
            raise ValidationError("Title is required")
        
        if not message or not message.strip():
            raise ValidationError("Message is required")
        
        valid_types = ['system', 'billing', 'security', 'onboarding', 'marketing', 'custom']
        if notification_type not in valid_types:
            raise ValidationError(f"Notification type must be one of: {', '.join(valid_types)}")
        
        valid_priorities = ['low', 'medium', 'high', 'critical']
        priority = kwargs.get('priority', 'medium')
        if priority not in valid_priorities:
            raise ValidationError(f"Priority must be one of: {', '.join(valid_priorities)}")
        
        # Validate scheduled_at if provided
        scheduled_at = kwargs.get('scheduled_at')
        if scheduled_at and scheduled_at <= timezone.now():
            raise ValidationError("Scheduled time must be in the future")
        
        # Validate expires_at if provided
        expires_at = kwargs.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError("Expiration time must be in the future")
    
    @staticmethod
    def _send_notification(notification):
        """
        Send notification through appropriate channels.
        
        Args:
            notification (TenantNotification): Notification to send
        """
        # This would integrate with actual notification services
        # For now, just update the status
        if notification.status == 'pending':
            TenantNotificationService.send_notification(notification)
    
    @staticmethod
    def _send_email_notification(notification):
        """
        Send notification via email.
        
        Args:
            notification (TenantNotification): Notification to send
            
        Returns:
            bool: True if successful
        """
        try:
            # This would integrate with email service
            # For now, just return True
            return True
        except Exception:
            return False
    
    @staticmethod
    def _send_push_notification(notification):
        """
        Send notification via push notification.
        
        Args:
            notification (TenantNotification): Notification to send
            
        Returns:
            bool: True if successful
        """
        try:
            # This would integrate with push notification service
            # For now, just return True
            return True
        except Exception:
            return False
    
    @staticmethod
    def _send_sms_notification(notification):
        """
        Send notification via SMS.
        
        Args:
            notification (TenantNotification): Notification to send
            
        Returns:
            bool: True if successful
        """
        try:
            # This would integrate with SMS service
            # For now, just return True
            return True
        except Exception:
            return False
