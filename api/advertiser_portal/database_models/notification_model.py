from django.conf import settings
"""
Notification Database Model

This module contains Notification model and related models
for managing user notifications and alerts.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator

from ..models import *
from ..enums import *
from ..utils import *
from ..validators import *


class Notification(AdvertiserPortalBaseModel):
    """
    Main notification model for managing user notifications.
    
    This model stores notification content, delivery status,
    and user preferences.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="Associated advertiser"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="Notification recipient"
    )
    
    # Notification Content
    title = models.CharField(
        max_length=255,
        help_text="Notification title"
    )
    message = models.TextField(
        help_text="Notification message"
    )
    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('system', 'System Notification'),
            ('campaign', 'Campaign Alert'),
            ('billing', 'Billing Alert'),
            ('performance', 'Performance Alert'),
            ('security', 'Security Alert'),
            ('integration', 'Integration Alert'),
            ('report', 'Report Notification'),
            ('custom', 'Custom Notification')
        ],
        db_index=True,
        help_text="Type of notification"
    )
    
    # Priority and Urgency
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
            ('critical', 'Critical')
        ],
        default='medium',
        db_index=True,
        help_text="Notification priority"
    )
    
    # Delivery Channels
    channels = models.JSONField(
        default=list,
        help_text="Delivery channels (email, sms, push, in-app)"
    )
    
    # Status Information
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('read', 'Read'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending',
        db_index=True,
        help_text="Notification status"
    )
    
    # Timestamps
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Scheduled delivery time"
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Time when notification was sent"
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Time when notification was delivered"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Time when notification was read"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Notification expiration time"
    )
    
    # Content References
    related_object_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of related object"
    )
    related_object_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID of related object"
    )
    action_url = models.URLField(
        blank=True,
        help_text="Action URL for notification"
    )
    action_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Text for action button"
    )
    
    # Delivery Configuration
    email_template = models.CharField(
        max_length=100,
        blank=True,
        help_text="Email template to use"
    )
    sms_template = models.CharField(
        max_length=100,
        blank=True,
        help_text="SMS template to use"
    )
    push_template = models.CharField(
        max_length=100,
        blank=True,
        help_text="Push notification template to use"
    )
    
    # Delivery Results
    delivery_results = models.JSONField(
        default=dict,
        blank=True,
        help_text="Delivery results by channel"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if delivery failed"
    )
    retry_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of retry attempts"
    )
    max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0)],
        help_text="Maximum retry attempts"
    )
    
    # User Interaction
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether notification has been read"
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether notification is archived"
    )
    is_starred = models.BooleanField(
        default=False,
        help_text="Whether notification is starred"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional notification metadata"
    )
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['advertiser', 'user', 'status']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['priority']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.title} ({self.user.username})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate scheduled time
        if self.scheduled_at and self.scheduled_at < timezone.now():
            raise ValidationError("Scheduled time cannot be in the past")
        
        # Validate expiration time
        if self.expires_at and self.expires_at < timezone.now():
            raise ValidationError("Expiration time cannot be in the past")
        
        # Validate channels
        if not self.channels:
            raise ValidationError("At least one delivery channel is required")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set default channels if not specified
        if not self.channels:
            self.channels = ['in_app']
        
        # Update read status based on read_at
        if self.read_at and not self.is_read:
            self.is_read = True
        
        super().save(*args, **kwargs)
    
    def is_expired(self) -> bool:
        """Check if notification is expired."""
        if not self.expires_at:
            return False
        
        return timezone.now() > self.expires_at
    
    def is_ready_to_send(self) -> bool:
        """Check if notification is ready to be sent."""
        return (
            self.status == 'pending' and
            not self.is_expired() and
            (not self.scheduled_at or self.scheduled_at <= timezone.now())
        )
    
    def mark_as_read(self) -> None:
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.status = 'read'
            self.save(update_fields=['is_read', 'read_at', 'status'])
    
    def mark_as_unread(self) -> None:
        """Mark notification as unread."""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.status = 'delivered'
            self.save(update_fields=['is_read', 'read_at', 'status'])
    
    def archive(self) -> None:
        """Archive notification."""
        self.is_archived = True
        self.save(update_fields=['is_archived'])
    
    def unarchive(self) -> None:
        """Unarchive notification."""
        self.is_archived = False
        self.save(update_fields=['is_archived'])
    
    def star(self) -> None:
        """Star notification."""
        self.is_starred = True
        self.save(update_fields=['is_starred'])
    
    def unstar(self) -> None:
        """Unstar notification."""
        self.is_starred = False
        self.save(update_fields=['is_starred'])
    
    def send_notification(self) -> Dict[str, Any]:
        """Send notification through configured channels."""
        if not self.is_ready_to_send():
            return {'success': False, 'message': 'Notification not ready to send'}
        
        results = {}
        success_count = 0
        
        for channel in self.channels:
            try:
                if channel == 'email':
                    result = self.send_email_notification()
                elif channel == 'sms':
                    result = self.send_sms_notification()
                elif channel == 'push':
                    result = self.send_push_notification()
                elif channel == 'in_app':
                    result = self.send_in_app_notification()
                else:
                    result = {'success': False, 'message': f'Unknown channel: {channel}'}
                
                results[channel] = result
                if result.get('success'):
                    success_count += 1
                
            except Exception as e:
                results[channel] = {'success': False, 'message': str(e)}
        
        # Update status based on results
        if success_count == len(self.channels):
            self.status = 'sent'
            self.sent_at = timezone.now()
        elif success_count > 0:
            self.status = 'delivered'
        else:
            self.status = 'failed'
            self.error_message = str(results)
        
        self.delivery_results = results
        self.save(update_fields=['status', 'sent_at', 'delivery_results', 'error_message'])
        
        return {
            'success': success_count > 0,
            'results': results
        }
    
    def send_email_notification(self) -> Dict[str, Any]:
        """Send email notification."""
        try:
            # This would implement actual email sending
            # For now, return success
            return {
                'success': True,
                'message': 'Email sent successfully',
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def send_sms_notification(self) -> Dict[str, Any]:
        """Send SMS notification."""
        try:
            # This would implement actual SMS sending
            # For now, return success
            return {
                'success': True,
                'message': 'SMS sent successfully',
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def send_push_notification(self) -> Dict[str, Any]:
        """Send push notification."""
        try:
            # This would implement actual push notification sending
            # For now, return success
            return {
                'success': True,
                'message': 'Push notification sent successfully',
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def send_in_app_notification(self) -> Dict[str, Any]:
        """Send in-app notification."""
        try:
            # In-app notifications are just stored in the database
            # Mark as delivered
            if self.status == 'pending':
                self.status = 'delivered'
                self.delivered_at = timezone.now()
                self.save(update_fields=['status', 'delivered_at'])
            
            return {
                'success': True,
                'message': 'In-app notification delivered',
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def retry_delivery(self) -> bool:
        """Retry notification delivery."""
        if self.retry_count >= self.max_retries:
            return False
        
        self.retry_count += 1
        self.status = 'pending'
        self.save(update_fields=['retry_count', 'status'])
        
        result = self.send_notification()
        return result.get('success', False)
    
    def get_notification_summary(self) -> Dict[str, Any]:
        """Get notification summary."""
        return {
            'basic_info': {
                'title': self.title,
                'message': self.message,
                'notification_type': self.notification_type,
                'priority': self.priority
            },
            'delivery': {
                'channels': self.channels,
                'status': self.status,
                'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
                'sent_at': self.sent_at.isoformat() if self.sent_at else None,
                'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
                'read_at': self.read_at.isoformat() if self.read_at else None
            },
            'interaction': {
                'is_read': self.is_read,
                'is_archived': self.is_archived,
                'is_starred': self.is_starred
            },
            'content': {
                'action_url': self.action_url,
                'action_text': self.action_text,
                'related_object_type': self.related_object_type,
                'related_object_id': self.related_object_id
            },
            'results': self.delivery_results,
            'metadata': self.metadata
        }


class NotificationTemplate(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing notification templates.
    """
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Template name"
    )
    description = models.TextField(
        blank=True,
        help_text="Template description"
    )
    
    # Template Configuration
    template_type = models.CharField(
        max_length=50,
        choices=[
            ('email', 'Email Template'),
            ('sms', 'SMS Template'),
            ('push', 'Push Notification Template'),
            ('in_app', 'In-App Template')
        ],
        help_text="Type of template"
    )
    
    # Template Content
    subject_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subject template (for email)"
    )
    body_template = models.TextField(
        help_text="Body template"
    )
    html_template = models.TextField(
        blank=True,
        help_text="HTML template (for email)"
    )
    
    # Template Variables
    variables = models.JSONField(
        default=dict,
        help_text="Template variables and descriptions"
    )
    default_variables = models.JSONField(
        default=dict,
        help_text="Default variable values"
    )
    
    # Styling Configuration
    css_styles = models.TextField(
        blank=True,
        help_text="CSS styles for template"
    )
    
    # Status and Access
    is_active = models.BooleanField(
        default=True,
        help_text="Whether template is active"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default template"
    )
    
    class Meta:
        db_table = 'ap_notification_templates'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        unique_together = ['template_type', 'name']
        indexes = [
            models.Index(fields=['template_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_default']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.template_type})"
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Ensure only one default template per type
        if self.is_default:
            NotificationTemplate.objects.filter(
                template_type=self.template_type,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    def render_template(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render template with provided variables."""
        # Merge with default variables
        template_vars = {**self.default_variables, **variables}
        
        # Simple template rendering (in practice, use a proper template engine)
        rendered = {}
        
        if self.subject_template:
            rendered['subject'] = self._render_text(self.subject_template, template_vars)
        
        rendered['body'] = self._render_text(self.body_template, template_vars)
        
        if self.html_template:
            rendered['html'] = self._render_text(self.html_template, template_vars)
        
        return rendered
    
    def _render_text(self, template: str, variables: Dict[str, Any]) -> str:
        """Render text template with variables."""
        try:
            # Simple string replacement (in practice, use Jinja2 or similar)
            rendered = template
            for key, value in variables.items():
                rendered = rendered.replace(f'{{{key}}}', str(value))
            return rendered
        except Exception:
            return template


class NotificationPreference(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing user notification preferences.
    """
    
    # Basic Information
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='advertiser_notification_preferences',
        help_text="Associated user"
    )
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='user_notification_preferences',
        help_text="Associated advertiser"
    )
    
    # Channel Preferences
    email_enabled = models.BooleanField(
        default=True,
        help_text="Enable email notifications"
    )
    sms_enabled = models.BooleanField(
        default=False,
        help_text="Enable SMS notifications"
    )
    push_enabled = models.BooleanField(
        default=True,
        help_text="Enable push notifications"
    )
    in_app_enabled = models.BooleanField(
        default=True,
        help_text="Enable in-app notifications"
    )
    
    # Type Preferences
    notification_preferences = models.JSONField(
        default=dict,
        help_text="Preferences by notification type"
    )
    
    # Frequency Preferences
    frequency_settings = models.JSONField(
        default=dict,
        help_text="Frequency settings by type"
    )
    
    # Quiet Hours
    quiet_hours_enabled = models.BooleanField(
        default=False,
        help_text="Enable quiet hours"
    )
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Quiet hours start time"
    )
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text="Quiet hours end time"
    )
    quiet_hours_timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="Timezone for quiet hours"
    )
    
    # Priority Preferences
    minimum_priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
            ('critical', 'Critical')
        ],
        default='low',
        help_text="Minimum priority to receive"
    )
    
    # Email Preferences
    email_address = models.EmailField(
        blank=True,
        help_text="Alternative email address"
    )
    email_format = models.CharField(
        max_length=20,
        choices=[
            ('html', 'HTML'),
            ('text', 'Plain Text')
        ],
        default='html',
        help_text="Email format preference"
    )
    
    # SMS Preferences
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number for SMS"
    )
    sms_country_code = models.CharField(
        max_length=3,
        blank=True,
        help_text="Country code for SMS"
    )
    
    # Push Preferences
    device_tokens = models.JSONField(
        default=list,
        blank=True,
        help_text="Device tokens for push notifications"
    )
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
        unique_together = ['user', 'advertiser']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['advertiser']),
        ]
    
    def __str__(self) -> str:
        return f"Preferences for {self.user.username}"
    
    def is_in_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        if not self.quiet_hours_enabled:
            return False
        
        try:
            from django.utils import timezone
            import pytz
            
            # Get user's timezone
            tz = pytz.timezone(self.quiet_hours_timezone)
            now = timezone.now().astimezone(tz)
            current_time = now.time()
            
            if self.quiet_hours_start and self.quiet_hours_end:
                if self.quiet_hours_start <= self.quiet_hours_end:
                    return self.quiet_hours_start <= current_time <= self.quiet_hours_end
                else:
                    # Quiet hours span midnight
                    return current_time >= self.quiet_hours_start or current_time <= self.quiet_hours_end
            
        except Exception:
            pass
        
        return False
    
    def should_receive_notification(self, notification: Notification) -> bool:
        """Check if user should receive notification."""
        # Check quiet hours
        if self.is_in_quiet_hours():
            # Only allow urgent/critical during quiet hours
            if notification.priority not in ['urgent', 'critical']:
                return False
        
        # Check minimum priority
        priority_levels = ['low', 'medium', 'high', 'urgent', 'critical']
        notification_level = priority_levels.index(notification.priority)
        minimum_level = priority_levels.index(self.minimum_priority)
        
        if notification_level < minimum_level:
            return False
        
        # Check type-specific preferences
        type_prefs = self.notification_preferences.get(notification.notification_type, {})
        if not type_prefs.get('enabled', True):
            return False
        
        # Check channel preferences
        if 'email' in notification.channels and not self.email_enabled:
            return False
        
        if 'sms' in notification.channels and not self.sms_enabled:
            return False
        
        if 'push' in notification.channels and not self.push_enabled:
            return False
        
        if 'in_app' in notification.channels and not self.in_app_enabled:
            return False
        
        return True
    
    def get_effective_channels(self, notification: Notification) -> List[str]:
        """Get effective delivery channels for notification."""
        if not self.should_receive_notification(notification):
            return []
        
        channels = []
        
        if 'email' in notification.channels and self.email_enabled:
            channels.append('email')
        
        if 'sms' in notification.channels and self.sms_enabled:
            channels.append('sms')
        
        if 'push' in notification.channels and self.push_enabled:
            channels.append('push')
        
        if 'in_app' in notification.channels and self.in_app_enabled:
            channels.append('in_app')
        
        return channels
    
    def get_preferences_summary(self) -> Dict[str, Any]:
        """Get preferences summary."""
        return {
            'channels': {
                'email_enabled': self.email_enabled,
                'sms_enabled': self.sms_enabled,
                'push_enabled': self.push_enabled,
                'in_app_enabled': self.in_app_enabled
            },
            'quiet_hours': {
                'enabled': self.quiet_hours_enabled,
                'start': self.quiet_hours_start.isoformat() if self.quiet_hours_start else None,
                'end': self.quiet_hours_end.isoformat() if self.quiet_hours_end else None,
                'timezone': self.quiet_hours_timezone
            },
            'priority': {
                'minimum_priority': self.minimum_priority
            },
            'contact': {
                'email_address': self.email_address,
                'phone_number': self.phone_number,
                'sms_country_code': self.sms_country_code
            },
            'type_preferences': self.notification_preferences,
            'frequency_settings': self.frequency_settings
        }


class NotificationLog(AdvertiserPortalBaseModel):
    """
    Model for logging notification events.
    """
    
    # Basic Information
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='logs',
        help_text="Associated notification"
    )
    
    # Log Details
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Created'),
            ('scheduled', 'Scheduled'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('read', 'Read'),
            ('failed', 'Failed'),
            ('retried', 'Retried'),
            ('cancelled', 'Cancelled')
        ],
        db_index=True,
        help_text="Type of event"
    )
    
    # Channel Information
    channel = models.CharField(
        max_length=50,
        choices=[
            ('email', 'Email'),
            ('sms', 'SMS'),
            ('push', 'Push'),
            ('in_app', 'In-App')
        ],
        help_text="Delivery channel"
    )
    
    # Event Data
    message = models.TextField(
        help_text="Log message"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event details"
    )
    
    # Performance Metrics
    response_time = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Response time in milliseconds"
    )
    
    # Error Information
    error_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Error code if any"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if any"
    )
    
    class Meta:
        db_table = 'notification_logs'
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        indexes = [
            models.Index(fields=['notification', 'event_type']),
            models.Index(fields=['channel']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.event_type} - {self.notification.title}"
