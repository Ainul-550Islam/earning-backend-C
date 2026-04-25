"""
Notification Models for Advertiser Portal

This module contains models for managing advertiser notifications,
including alerts, messages, and communication preferences.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserNotification(models.Model):
    """
    Model for managing advertiser notifications.
    
    Stores system notifications, alerts, and
    messages for advertisers.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this notification belongs to')
    )
    
    # Notification details
    type = models.CharField(
        _('Type'),
        max_length=50,
        choices=[
            ('welcome', _('Welcome')),
            ('offer_created', _('Offer Created')),
            ('offer_approved', _('Offer Approved')),
            ('offer_rejected', _('Offer Rejected')),
            ('campaign_created', _('Campaign Created')),
            ('campaign_started', _('Campaign Started')),
            ('campaign_ended', _('Campaign Ended')),
            ('budget_reached', _('Budget Reached')),
            ('pixel_created', _('Pixel Created')),
            ('postback_created', _('Postback Created')),
            ('report_created', _('Report Created')),
            ('invoice_created', _('Invoice Created')),
            ('invoice_due', _('Invoice Due')),
            ('invoice_overdue', _('Invoice Overdue')),
            ('payment_received', _('Payment Received')),
            ('payment_failed', _('Payment Failed')),
            ('fraud_alert', _('Fraud Alert')),
            ('critical_fraud', _('Critical Fraud')),
            ('low_quality', _('Low Quality')),
            ('system_maintenance', _('System Maintenance')),
            ('feature_update', _('Feature Update')),
            ('security_alert', _('Security Alert')),
            ('compliance_required', _('Compliance Required')),
            ('verification_required', _('Verification Required')),
            ('account_suspended', _('Account Suspended')),
            ('account_reactivated', _('Account Reactivated')),
        ],
        db_index=True,
        help_text=_('Type of notification')
    )
    
    title = models.CharField(
        _('Title'),
        max_length=200,
        help_text=_('Notification title')
    )
    
    message = models.TextField(
        _('Message'),
        help_text=_('Notification message')
    )
    
    # Status and priority
    is_read = models.BooleanField(
        _('Is Read'),
        default=False,
        db_index=True,
        help_text=_('Whether notification has been read')
    )
    
    priority = models.CharField(
        _('Priority'),
        max_length=20,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('urgent', _('Urgent')),
            ('critical', _('Critical')),
        ],
        default='medium',
        db_index=True,
        help_text=_('Notification priority')
    )
    
    # Delivery methods
    email_sent = models.BooleanField(
        _('Email Sent'),
        default=False,
        help_text=_('Whether email notification was sent')
    )
    
    sms_sent = models.BooleanField(
        _('SMS Sent'),
        default=False,
        help_text=_('Whether SMS notification was sent')
    )
    
    push_sent = models.BooleanField(
        _('Push Sent'),
        default=False,
        help_text=_('Whether push notification was sent')
    )
    
    # Action information
    action_url = models.URLField(
        _('Action URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('URL for action button')
    )
    
    action_text = models.CharField(
        _('Action Text'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Text for action button')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional notification metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this notification was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this notification was last updated')
    )
    
    read_at = models.DateTimeField(
        _('Read At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this notification was read')
    )
    
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        help_text=_('When this notification expires')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_notification'
        verbose_name = _('Advertiser Notification')
        verbose_name_plural = _('Advertiser Notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'is_read'], name='idx_advertiser_is_read_492'),
            models.Index(fields=['advertiser', 'priority'], name='idx_advertiser_priority_493'),
            models.Index(fields=['type', 'created_at'], name='idx_type_created_at_494'),
            models.Index(fields=['is_read', 'created_at'], name='idx_is_read_created_at_495'),
            models.Index(fields=['priority', 'created_at'], name='idx_priority_created_at_496'),
            models.Index(fields=['expires_at'], name='idx_expires_at_497'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate title
        if not self.title.strip():
            raise ValidationError(_('Title cannot be empty'))
        
        # Validate message
        if not self.message.strip():
            raise ValidationError(_('Message cannot be empty'))
        
        # Validate expiration
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError(_('Expiration time must be in the future'))
    
    @property
    def is_expired(self) -> bool:
        """Check if notification is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_urgent(self) -> bool:
        """Check if notification is urgent."""
        return self.priority in ['urgent', 'critical']
    
    @property
    def is_critical(self) -> bool:
        """Check if notification is critical."""
        return self.priority == 'critical'
    
    @property
    def age_hours(self) -> int:
        """Get age in hours."""
        if self.created_at:
            return int((timezone.now() - self.created_at).total_seconds() / 3600)
        return 0
    
    @property
    def type_display(self) -> str:
        """Get human-readable notification type."""
        type_names = {
            'welcome': _('Welcome'),
            'offer_created': _('Offer Created'),
            'offer_approved': _('Offer Approved'),
            'offer_rejected': _('Offer Rejected'),
            'campaign_created': _('Campaign Created'),
            'campaign_started': _('Campaign Started'),
            'campaign_ended': _('Campaign Ended'),
            'budget_reached': _('Budget Reached'),
            'pixel_created': _('Pixel Created'),
            'postback_created': _('Postback Created'),
            'report_created': _('Report Created'),
            'invoice_created': _('Invoice Created'),
            'invoice_due': _('Invoice Due'),
            'invoice_overdue': _('Invoice Overdue'),
            'payment_received': _('Payment Received'),
            'payment_failed': _('Payment Failed'),
            'fraud_alert': _('Fraud Alert'),
            'critical_fraud': _('Critical Fraud'),
            'low_quality': _('Low Quality'),
            'system_maintenance': _('System Maintenance'),
            'feature_update': _('Feature Update'),
            'security_alert': _('Security Alert'),
            'compliance_required': _('Compliance Required'),
            'verification_required': _('Verification Required'),
            'account_suspended': _('Account Suspended'),
            'account_reactivated': _('Account Reactivated'),
        }
        return type_names.get(self.type, self.type)
    
    @property
    def priority_display(self) -> str:
        """Get human-readable priority."""
        priority_names = {
            'low': _('Low'),
            'medium': _('Medium'),
            'high': _('High'),
            'urgent': _('Urgent'),
            'critical': _('Critical'),
        }
        return priority_names.get(self.priority, self.priority)
    
    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
            
            logger.info(f"Notification marked as read: {self.id}")
    
    def mark_as_unread(self):
        """Mark notification as unread."""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=['is_read', 'read_at'])
            
            logger.info(f"Notification marked as unread: {self.id}")
    
    def get_notification_summary(self) -> dict:
        """Get notification summary."""
        return {
            'id': self.id,
            'type': self.type,
            'type_display': self.type_display,
            'title': self.title,
            'message': self.message,
            'priority': self.priority,
            'priority_display': self.priority_display,
            'is_read': self.is_read,
            'is_expired': self.is_expired,
            'is_urgent': self.is_urgent,
            'is_critical': self.is_critical,
            'delivery': {
                'email_sent': self.email_sent,
                'sms_sent': self.sms_sent,
                'push_sent': self.push_sent,
            },
            'action': {
                'action_url': self.action_url,
                'action_text': self.action_text,
                'has_action': bool(self.action_url),
            },
            'timestamps': {
                'created_at': self.created_at.isoformat(),
                'read_at': self.read_at.isoformat() if self.read_at else None,
                'expires_at': self.expires_at.isoformat() if self.expires_at else None,
                'age_hours': self.age_hours,
            },
            'metadata': self.metadata,
        }


class AdvertiserAlert(models.Model):
    """
    Model for managing advertiser alerts.
    
    Stores alert configurations for monitoring
    campaign performance, budget limits, and other metrics.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='alerts',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this alert belongs to')
    )
    
    # Alert details
    alert_type = models.CharField(
        _('Alert Type'),
        max_length=50,
        choices=[
            ('budget_low', _('Budget Low')),
            ('budget_exhausted', _('Budget Exhausted')),
            ('daily_budget_reached', _('Daily Budget Reached')),
            ('weekly_budget_reached', _('Weekly Budget Reached')),
            ('monthly_budget_reached', _('Monthly Budget Reached')),
            ('campaign_paused', _('Campaign Paused')),
            ('campaign_ended', _('Campaign Ended')),
            ('conversion_rate_low', _('Conversion Rate Low')),
            ('click_through_rate_low', _('Click Through Rate Low')),
            ('cost_per_action_high', _('Cost Per Action High')),
            ('fraud_rate_high', _('Fraud Rate High')),
            ('quality_score_low', _('Quality Score Low')),
            ('offer_performance_poor', _('Offer Performance Poor')),
            ('payment_failed', _('Payment Failed')),
            ('invoice_due', _('Invoice Due')),
            ('account_suspended', _('Account Suspended')),
            ('verification_required', _('Verification Required')),
            ('compliance_issue', _('Compliance Issue')),
            ('system_maintenance', _('System Maintenance')),
            ('api_rate_limit', _('API Rate Limit')),
            ('custom', _('Custom')),
        ],
        help_text=_('Type of alert')
    )
    
    name = models.CharField(
        _('Alert Name'),
        max_length=200,
        help_text=_('Alert name for identification')
    )
    
    description = models.TextField(
        _('Description'),
        null=True,
        blank=True,
        help_text=_('Alert description')
    )
    
    # Threshold configuration
    threshold_value = models.DecimalField(
        _('Threshold Value'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Alert threshold value')
    )
    
    threshold_type = models.CharField(
        _('Threshold Type'),
        max_length=20,
        choices=[
            ('percentage', _('Percentage')),
            ('amount', _('Amount')),
            ('count', _('Count')),
            ('rate', _('Rate')),
            ('boolean', _('Boolean')),
            ('time', _('Time')),
        ],
        default='percentage',
        help_text=_('Type of threshold')
    )
    
    comparison_operator = models.CharField(
        _('Comparison Operator'),
        max_length=10,
        choices=[
            ('less_than', _('Less Than')),
            ('less_equal', _('Less Than or Equal')),
            ('equal', _('Equal')),
            ('greater_equal', _('Greater Than or Equal')),
            ('greater_than', _('Greater Than')),
        ],
        default='greater_than',
        help_text=_('Comparison operator for threshold')
    )
    
    # Status and configuration
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        db_index=True,
        help_text=_('Whether this alert is active')
    )
    
    # Notification settings
    email_enabled = models.BooleanField(
        _('Email Enabled'),
        default=True,
        help_text=_('Whether to send email notifications')
    )
    
    sms_enabled = models.BooleanField(
        _('SMS Enabled'),
        default=False,
        help_text=_('Whether to send SMS notifications')
    )
    
    webhook_enabled = models.BooleanField(
        _('Webhook Enabled'),
        default=False,
        help_text=_('Whether to send webhook notifications')
    )
    
    webhook_url = models.URLField(
        _('Webhook URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('URL for webhook notifications')
    )
    
    # Frequency settings
    cooldown_minutes = models.IntegerField(
        _('Cooldown Minutes'),
        default=60,
        help_text=_('Minutes between same alert notifications')
    )
    
    max_alerts_per_day = models.IntegerField(
        _('Max Alerts Per Day'),
        default=10,
        help_text=_('Maximum alerts per day')
    )
    
    # Additional settings
    custom_conditions = models.JSONField(
        _('Custom Conditions'),
        default=list,
        blank=True,
        help_text=_('Custom alert conditions')
    )
    
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional alert metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this alert was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this alert was last updated')
    )
    
    last_triggered_at = models.DateTimeField(
        _('Last Triggered At'),
        null=True,
        blank=True,
        help_text=_('When this alert was last triggered')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_alert'
        verbose_name = _('Advertiser Alert')
        verbose_name_plural = _('Advertiser Alerts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'is_active'], name='idx_advertiser_is_active_498'),
            models.Index(fields=['alert_type', 'is_active'], name='idx_alert_type_is_active_499'),
            models.Index(fields=['is_active', 'created_at'], name='idx_is_active_created_at_500'),
            models.Index(fields=['last_triggered_at'], name='idx_last_triggered_at_501'),
        ]
        unique_together = [
            ['advertiser', 'alert_type'],
        ]
    
    def __str__(self):
        return f"{self.name} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate name
        if not self.name.strip():
            raise ValidationError(_('Alert name cannot be empty'))
        
        # Validate cooldown
        if self.cooldown_minutes < 0:
            raise ValidationError(_('Cooldown minutes cannot be negative'))
        
        # Validate max alerts per day
        if self.max_alerts_per_day < 1:
            raise ValidationError(_('Max alerts per day must be at least 1'))
        
        # Validate threshold value
        if self.threshold_value is not None and self.threshold_value < 0:
            raise ValidationError(_('Threshold value cannot be negative'))
    
    @property
    def has_threshold(self) -> bool:
        """Check if alert has threshold configured."""
        return self.threshold_value is not None
    
    @property
    def is_budget_alert(self) -> bool:
        """Check if this is a budget alert."""
        return self.alert_type in ['budget_low', 'budget_exhausted', 'daily_budget_reached', 
                                   'weekly_budget_reached', 'monthly_budget_reached']
    
    @property
    def is_performance_alert(self) -> bool:
        """Check if this is a performance alert."""
        return self.alert_type in ['conversion_rate_low', 'click_through_rate_low', 'cost_per_action_high',
                                   'fraud_rate_high', 'quality_score_low', 'offer_performance_poor']
    
    @property
    def is_system_alert(self) -> bool:
        """Check if this is a system alert."""
        return self.alert_type in ['payment_failed', 'account_suspended', 'verification_required',
                               'compliance_issue', 'system_maintenance', 'api_rate_limit']
    
    @property
    def alert_type_display(self) -> str:
        """Get human-readable alert type."""
        type_names = {
            'budget_low': _('Budget Low'),
            'budget_exhausted': _('Budget Exhausted'),
            'daily_budget_reached': _('Daily Budget Reached'),
            'weekly_budget_reached': _('Weekly Budget Reached'),
            'monthly_budget_reached': _('Monthly Budget Reached'),
            'campaign_paused': _('Campaign Paused'),
            'campaign_ended': _('Campaign Ended'),
            'conversion_rate_low': _('Conversion Rate Low'),
            'click_through_rate_low': _('Click Through Rate Low'),
            'cost_per_action_high': _('Cost Per Action High'),
            'fraud_rate_high': _('Fraud Rate High'),
            'quality_score_low': _('Quality Score Low'),
            'offer_performance_poor': _('Offer Performance Poor'),
            'payment_failed': _('Payment Failed'),
            'invoice_due': _('Invoice Due'),
            'account_suspended': _('Account Suspended'),
            'verification_required': _('Verification Required'),
            'compliance_issue': _('Compliance Issue'),
            'system_maintenance': _('System Maintenance'),
            'api_rate_limit': _('API Rate Limit'),
            'custom': _('Custom'),
        }
        return type_names.get(self.alert_type, self.alert_type)
    
    @property
    def threshold_display(self) -> str:
        """Get human-readable threshold."""
        if not self.has_threshold:
            return "N/A"
        
        operator_symbols = {
            'less_than': '<',
            'less_equal': '≤',
            'equal': '=',
            'greater_equal': '≥',
            'greater_than': '>',
        }
        
        operator = operator_symbols.get(self.comparison_operator, self.comparison_operator)
        value = self.threshold_value
        type_name = self.threshold_type
        
        return f"{operator} {value} ({type_name})"
    
    def should_trigger(self, current_value, context=None) -> bool:
        """Check if alert should trigger based on current value."""
        if not self.is_active:
            return False
        
        # Check cooldown period
        if self.last_triggered_at:
            cooldown_end = self.last_triggered_at + timezone.timedelta(minutes=self.cooldown_minutes)
            if timezone.now() < cooldown_end:
                return False
        
        # Check threshold
        if self.has_threshold:
            return self._check_threshold(current_value)
        
        # Check custom conditions
        if self.custom_conditions:
            return self._check_custom_conditions(current_value, context)
        
        return False
    
    def _check_threshold(self, current_value) -> bool:
        """Check threshold condition."""
        if self.comparison_operator == 'less_than':
            return current_value < self.threshold_value
        elif self.comparison_operator == 'less_equal':
            return current_value <= self.threshold_value
        elif self.comparison_operator == 'equal':
            return current_value == self.threshold_value
        elif self.comparison_operator == 'greater_equal':
            return current_value >= self.threshold_value
        elif self.comparison_operator == 'greater_than':
            return current_value > self.threshold_value
        
        return False
    
    def _check_custom_conditions(self, current_value, context) -> bool:
        """Check custom conditions."""
        # This would implement custom condition checking
        # For now, return False
        return False
    
    def trigger_alert(self, current_value=None, context=None):
        """Trigger the alert."""
        self.last_triggered_at = timezone.now()
        self.save(update_fields=['last_triggered_at'])
        
        # Create notification
        notification_data = {
            'advertiser': self.advertiser,
            'type': 'alert_triggered',
            'title': f'Alert: {self.name}',
            'message': self.description or f'Alert {self.name} has been triggered',
            'priority': 'high' if self.is_budget_alert else 'medium',
            'metadata': {
                'alert_id': self.id,
                'alert_type': self.alert_type,
                'current_value': str(current_value) if current_value else None,
                'threshold': self.threshold_display,
                'context': context,
            }
        }
        
        notification = AdvertiserNotification.objects.create(**notification_data)
        
        # Send notifications based on settings
        if self.email_enabled:
            self._send_email_notification(notification, current_value, context)
        
        if self.sms_enabled:
            self._send_sms_notification(notification, current_value, context)
        
        if self.webhook_enabled:
            self._send_webhook_notification(notification, current_value, context)
        
        logger.info(f"Alert triggered: {self.name} for {self.advertiser.company_name}")
        
        return notification
    
    def _send_email_notification(self, notification, current_value, context):
        """Send email notification."""
        # This would implement email sending
        # For now, just mark as sent
        notification.email_sent = True
        notification.save(update_fields=['email_sent'])
    
    def _send_sms_notification(self, notification, current_value, context):
        """Send SMS notification."""
        # This would implement SMS sending
        # For now, just mark as sent
        notification.sms_sent = True
        notification.save(update_fields=['sms_sent'])
    
    def _send_webhook_notification(self, notification, current_value, context):
        """Send webhook notification."""
        # This would implement webhook sending
        # For now, just mark as sent
        notification.push_sent = True
        notification.save(update_fields=['push_sent'])
    
    def get_alert_summary(self) -> dict:
        """Get alert configuration summary."""
        return {
            'id': self.id,
            'name': self.name,
            'alert_type': self.alert_type,
            'alert_type_display': self.alert_type_display,
            'description': self.description,
            'threshold': {
                'has_threshold': self.has_threshold,
                'value': float(self.threshold_value) if self.threshold_value else None,
                'type': self.threshold_type,
                'operator': self.comparison_operator,
                'display': self.threshold_display,
            },
            'status': {
                'is_active': self.is_active,
                'last_triggered_at': self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            },
            'notifications': {
                'email_enabled': self.email_enabled,
                'sms_enabled': self.sms_enabled,
                'webhook_enabled': self.webhook_enabled,
                'webhook_url': self.webhook_url,
            },
            'frequency': {
                'cooldown_minutes': self.cooldown_minutes,
                'max_alerts_per_day': self.max_alerts_per_day,
            },
            'categories': {
                'is_budget_alert': self.is_budget_alert,
                'is_performance_alert': self.is_performance_alert,
                'is_system_alert': self.is_system_alert,
            },
            'custom_conditions': self.custom_conditions,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
        }


# Signal handlers for notification models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=AdvertiserNotification)
def notification_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for notifications."""
    if created:
        logger.info(f"New notification created: {instance.title} - {instance.type}")
        
        # Send email if configured
        if not instance.email_sent and instance.advertiser.email_notifications:
            # This would implement email sending
            pass

@receiver(post_save, sender=AdvertiserAlert)
def alert_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for alerts."""
    if created:
        logger.info(f"New alert created: {instance.name} - {instance.alert_type}")
        
        # Send notification to advertiser
        AdvertiserNotification.objects.create(
            advertiser=instance.advertiser,
            type='alert_created',
            title=_('New Alert Created'),
            message=_('Your alert "{instance.name}" has been created successfully.'),
        )

@receiver(post_delete, sender=AdvertiserNotification)
def notification_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for notifications."""
    logger.info(f"Notification deleted: {instance.title}")

@receiver(post_delete, sender=AdvertiserAlert)
def alert_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for alerts."""
    logger.info(f"Alert deleted: {instance.name}")


class NotificationTemplate(models.Model):
    """
    Model for managing notification templates.
    
    Stores reusable notification templates for different
    notification types and channels.
    """
    
    # Core fields
    name = models.CharField(
        _('Template Name'),
        max_length=100,
        unique=True,
        help_text=_('Unique template name')
    )
    
    template_type = models.CharField(
        _('Template Type'),
        max_length=50,
        choices=[
            ('email', _('Email')),
            ('sms', _('SMS')),
            ('push', _('Push')),
            ('in_app', _('In-App')),
            ('webhook', _('Webhook')),
        ],
        help_text=_('Type of notification template')
    )
    
    notification_category = models.CharField(
        _('Notification Category'),
        max_length=50,
        choices=[
            ('system', _('System')),
            ('billing', _('Billing')),
            ('campaign', _('Campaign')),
            ('offer', _('Offer')),
            ('fraud', _('Fraud')),
            ('verification', _('Verification')),
            ('performance', _('Performance')),
            ('security', _('Security')),
        ],
        help_text=_('Category of notification')
    )
    
    # Template content
    subject_template = models.CharField(
        _('Subject Template'),
        max_length=200,
        blank=True,
        help_text=_('Template for notification subject')
    )
    
    body_template = models.TextField(
        _('Body Template'),
        help_text=_('Template for notification body')
    )
    
    html_template = models.TextField(
        _('HTML Template'),
        blank=True,
        help_text=_('HTML template for email notifications')
    )
    
    # Template variables
    variables = models.JSONField(
        _('Variables'),
        default=list,
        blank=True,
        help_text=_('List of template variables')
    )
    
    default_values = models.JSONField(
        _('Default Values'),
        default=dict,
        blank=True,
        help_text=_('Default values for template variables')
    )
    
    # Template settings
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this template is active')
    )
    
    is_default = models.BooleanField(
        _('Is Default'),
        default=False,
        help_text=_('Whether this is the default template for its type')
    )
    
    language = models.CharField(
        _('Language'),
        max_length=10,
        default='en',
        help_text=_('Language code for this template')
    )
    
    # Styling and formatting
    css_styles = models.TextField(
        _('CSS Styles'),
        blank=True,
        help_text=_('CSS styles for HTML templates')
    )
    
    header_image = models.URLField(
        _('Header Image'),
        max_length=500,
        blank=True,
        help_text=_('URL for header image')
    )
    
    footer_text = models.TextField(
        _('Footer Text'),
        blank=True,
        help_text=_('Footer text for notifications')
    )
    
    # Usage statistics
    usage_count = models.PositiveIntegerField(
        _('Usage Count'),
        default=0,
        help_text=_('Number of times this template has been used')
    )
    
    last_used_at = models.DateTimeField(
        _('Last Used At'),
        null=True,
        blank=True,
        help_text=_('When this template was last used')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this template was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this template was last updated')
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notification_templates',
        verbose_name=_('Created By'),
        help_text=_('User who created this template')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('Notification Template')
        verbose_name_plural = _('Notification Templates')
        ordering = ['template_type', 'name']
        indexes = [
            models.Index(fields=['template_type', 'notification_category'], name='idx_template_type_notifica_8fc'),
            models.Index(fields=['is_active'], name='idx_is_active_503'),
            models.Index(fields=['is_default'], name='idx_is_default_504'),
            models.Index(fields=['language'], name='idx_language_505'),
        ]
    
    def __str__(self):
        return f"{self.template_type} - {self.name}"
    
    def render_subject(self, context=None):
        """Render subject template with context."""
        if not self.subject_template:
            return ""
        
        context = context or {}
        context.update(self.default_values)
        
        try:
            return self.subject_template.format(**context)
        except KeyError as e:
            logger.error(f"Missing variable in subject template: {e}")
            return self.subject_template
    
    def render_body(self, context=None):
        """Render body template with context."""
        context = context or {}
        context.update(self.default_values)
        
        try:
            return self.body_template.format(**context)
        except KeyError as e:
            logger.error(f"Missing variable in body template: {e}")
            return self.body_template
    
    def render_html(self, context=None):
        """Render HTML template with context."""
        if not self.html_template:
            return None
        
        context = context or {}
        context.update(self.default_values)
        
        try:
            return self.html_template.format(**context)
        except KeyError as e:
            logger.error(f"Missing variable in HTML template: {e}")
            return self.html_template
    
    def record_usage(self):
        """Record template usage."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])
    
    def get_template_summary(self):
        """Get template summary as dictionary."""
        return {
            'name': self.name,
            'template_type': self.template_type,
            'notification_category': self.notification_category,
            'language': self.language,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'usage_count': self.usage_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'variables': self.variables,
        }
    
    def validate_template(self):
        """Validate template syntax."""
        errors = []
        
        # Check subject template
        if self.subject_template:
            try:
                self.subject_template.format(**self.default_values)
            except KeyError as e:
                errors.append(f"Subject template missing variable: {e}")
            except Exception as e:
                errors.append(f"Subject template error: {e}")
        
        # Check body template
        try:
            self.body_template.format(**self.default_values)
        except KeyError as e:
            errors.append(f"Body template missing variable: {e}")
        except Exception as e:
            errors.append(f"Body template error: {e}")
        
        # Check HTML template
        if self.html_template:
            try:
                self.html_template.format(**self.default_values)
            except KeyError as e:
                errors.append(f"HTML template missing variable: {e}")
            except Exception as e:
                errors.append(f"HTML template error: {e}")
        
        return errors
        app_label = 'advertiser_portal_v2'
