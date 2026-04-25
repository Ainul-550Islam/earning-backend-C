"""
Analytics Models

This module contains tenant analytics models for metrics,
health scores, feature flags, and notifications.
"""

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from .base import TimeStampedModel, SoftDeleteModel

User = get_user_model()


class TenantMetric(TimeStampedModel, SoftDeleteModel):
    """
    Tenant metrics and analytics data.
    
    This model tracks various metrics for tenants including
    user activity, revenue, API usage, and other KPIs.
    """
    
    METRIC_TYPE_CHOICES = [
        ('mau', _('Monthly Active Users')),
        ('dau', _('Daily Active Users')),
        ('revenue', _('Revenue')),
        ('api_calls', _('API Calls')),
        ('storage_used', _('Storage Used')),
        ('bandwidth_used', _('Bandwidth Used')),
        ('tickets_open', _('Tickets Open')),
        ('campaigns_active', _('Active Campaigns')),
        ('publishers_active', _('Active Publishers')),
        ('conversion_rate', _('Conversion Rate')),
        ('custom', _('Custom Metric')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='metrics',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this metric belongs to')
    )
    
    # Metric information
    date = models.DateField(
        verbose_name=_('Date'),
        help_text=_('Date of the metric data')
    )
    metric_type = models.CharField(
        max_length=50,
        choices=METRIC_TYPE_CHOICES,
        verbose_name=_('Metric Type'),
        help_text=_('Type of metric being tracked')
    )
    value = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        verbose_name=_('Value'),
        help_text=_('Metric value')
    )
    
    # Additional data
    unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Unit'),
        help_text=_('Unit of measurement (e.g., users, USD, GB)')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional metric metadata')
    )
    
    # Comparison data
    previous_value = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name=_('Previous Value'),
        help_text=_('Previous period value for comparison')
    )
    change_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Change Percentage'),
        help_text=_('Percentage change from previous period')
    )
    
    class Meta:
        db_table = 'tenant_metrics'
        verbose_name = _('Tenant Metric')
        verbose_name_plural = _('Tenant Metrics')
        ordering = ['-date', 'metric_type']
        unique_together = ['tenant', 'date', 'metric_type']
        indexes = [
            models.Index(fields=['tenant', 'date'], name='idx_tenant_date_1756'),
            models.Index(fields=['metric_type'], name='idx_metric_type_1757'),
            models.Index(fields=['date'], name='idx_date_1758'),
        ]
    
    def __str__(self):
        return f"{self.metric_type} for {self.tenant.name} on {self.date}"
    
    def calculate_change_percentage(self):
        """Calculate percentage change from previous value."""
        if self.previous_value and self.previous_value != 0:
            self.change_percentage = ((self.value - self.previous_value) / self.previous_value) * 100
        else:
            self.change_percentage = None
        return self.change_percentage
    
    @property
    def change_display(self):
        """Get formatted change display."""
        if self.change_percentage is None:
            return "N/A"
        
        sign = "+" if self.change_percentage >= 0 else ""
        return f"{sign}{self.change_percentage:.2f}%"
    
    @property
    def is_positive_change(self):
        """Check if change is positive."""
        return self.change_percentage and self.change_percentage > 0


class TenantHealthScore(TimeStampedModel, SoftDeleteModel):
    """
    Tenant health score and risk assessment.
    
    This model calculates and tracks health scores for tenants
    based on various factors like engagement, usage, and payments.
    """
    
    HEALTH_GRADE_CHOICES = [
        ('A', _('Excellent')),
        ('B', _('Good')),
        ('C', _('Fair')),
        ('D', _('Poor')),
        ('F', _('Critical')),
    ]
    
    RISK_LEVEL_CHOICES = [
        ('low', _('Low Risk')),
        ('medium', _('Medium Risk')),
        ('high', _('High Risk')),
        ('critical', _('Critical Risk')),
    ]
    
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='health_score',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this health score belongs to')
    )
    
    # Health score components
    engagement_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Engagement Score'),
        help_text=_('Score based on user engagement (0-100)')
    )
    usage_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Usage Score'),
        help_text=_('Score based on feature usage (0-100)')
    )
    payment_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Payment Score'),
        help_text=_('Score based on payment history (0-100)')
    )
    support_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Support Score'),
        help_text=_('Score based on support interactions (0-100)')
    )
    
    # Overall health
    overall_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Overall Score'),
        help_text=_('Overall health score (0-100)')
    )
    health_grade = models.CharField(
        max_length=1,
        choices=HEALTH_GRADE_CHOICES,
        default='F',
        verbose_name=_('Health Grade'),
        help_text=_('Overall health grade')
    )
    
    # Risk assessment
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='high',
        verbose_name=_('Risk Level'),
        help_text=_('Churn risk level')
    )
    churn_probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Churn Probability'),
        help_text=_('Probability of churn (0-100)')
    )
    
    # Activity tracking
    last_activity_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Activity At'),
        help_text=_('Last recorded tenant activity')
    )
    days_inactive = models.IntegerField(
        default=0,
        verbose_name=_('Days Inactive'),
        help_text=_('Number of days since last activity')
    )
    
    # Factors and signals
    positive_factors = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Positive Factors'),
        help_text=_('Factors contributing positively to health')
    )
    negative_factors = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Negative Factors'),
        help_text=_('Factors contributing negatively to health')
    )
    risk_signals = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Risk Signals'),
        help_text=_('Signals indicating potential churn')
    )
    
    # Recommendations
    recommendations = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Recommendations'),
        help_text=_('Recommendations for improvement')
    )
    
    class Meta:
        db_table = 'tenant_health_scores'
        verbose_name = _('Tenant Health Score')
        verbose_name_plural = _('Tenant Health Scores')
        ordering = ['-overall_score']
        indexes = [
            models.Index(fields=['tenant'], name='idx_tenant_1759'),
            models.Index(fields=['health_grade'], name='idx_health_grade_1760'),
            models.Index(fields=['risk_level'], name='idx_risk_level_1761'),
            models.Index(fields=['overall_score'], name='idx_overall_score_1762'),
            models.Index(fields=['churn_probability'], name='idx_churn_probability_1763'),
            models.Index(fields=['last_activity_at'], name='idx_last_activity_at_1764'),
        ]
    
    def __str__(self):
        return f"Health Score for {self.tenant.name} ({self.health_grade})"
    
    def calculate_overall_score(self):
        """Calculate overall health score."""
        # Weight different components
        weights = {
            'engagement': 0.3,
            'usage': 0.3,
            'payment': 0.25,
            'support': 0.15,
        }
        
        self.overall_score = (
            self.engagement_score * weights['engagement'] +
            self.usage_score * weights['usage'] +
            self.payment_score * weights['payment'] +
            self.support_score * weights['support']
        )
        
        return self.overall_score
    
    def calculate_health_grade(self):
        """Calculate health grade based on score."""
        score = self.calculate_overall_score()
        
        if score >= 90:
            self.health_grade = 'A'
        elif score >= 80:
            self.health_grade = 'B'
        elif score >= 70:
            self.health_grade = 'C'
        elif score >= 60:
            self.health_grade = 'D'
        else:
            self.health_grade = 'F'
        
        return self.health_grade
    
    def calculate_risk_level(self):
        """Calculate risk level based on various factors."""
        risk_score = 0
        
        # High risk factors
        if self.days_inactive > 30:
            risk_score += 30
        elif self.days_inactive > 14:
            risk_score += 15
        
        if self.payment_score < 50:
            risk_score += 25
        elif self.payment_score < 70:
            risk_score += 10
        
        if self.engagement_score < 30:
            risk_score += 20
        elif self.engagement_score < 50:
            risk_score += 10
        
        if self.usage_score < 40:
            risk_score += 15
        elif self.usage_score < 60:
            risk_score += 5
        
        # Map risk score to risk level
        if risk_score >= 70:
            self.risk_level = 'critical'
        elif risk_score >= 50:
            self.risk_level = 'high'
        elif risk_score >= 25:
            self.risk_level = 'medium'
        else:
            self.risk_level = 'low'
        
        # Calculate churn probability
        self.churn_probability = min(100, risk_score)
        
        return self.risk_level
    
    def update_activity(self, last_activity=None):
        """Update activity tracking."""
        if last_activity:
            self.last_activity_at = last_activity
        else:
            self.last_activity_at = timezone.now()
        
        # Calculate days inactive
        if self.last_activity_at:
            delta = timezone.now() - self.last_activity_at
            self.days_inactive = delta.days
        
        self.save(update_fields=['last_activity_at', 'days_inactive'])
    
    def add_factor(self, factor_type, factor, impact=1):
        """Add a positive or negative factor."""
        if factor_type == 'positive':
            if factor not in self.positive_factors:
                self.positive_factors.append(factor)
        elif factor_type == 'negative':
            if factor not in self.negative_factors:
                self.negative_factors.append(factor)
        
        self.save(update_fields=['positive_factors', 'negative_factors'])
    
    def add_risk_signal(self, signal):
        """Add a risk signal."""
        if signal not in self.risk_signals:
            self.risk_signals.append(signal)
            self.save(update_fields=['risk_signals'])
    
    def generate_recommendations(self):
        """Generate recommendations based on health score."""
        recommendations = []
        
        if self.engagement_score < 50:
            recommendations.append({
                'type': 'engagement',
                'priority': 'high',
                'action': 'Increase user engagement through targeted campaigns',
                'impact': 'medium'
            })
        
        if self.usage_score < 60:
            recommendations.append({
                'type': 'usage',
                'priority': 'medium',
                'action': 'Provide feature training and tutorials',
                'impact': 'high'
            })
        
        if self.payment_score < 70:
            recommendations.append({
                'type': 'payment',
                'priority': 'high',
                'action': 'Review billing process and offer flexible payment options',
                'impact': 'high'
            })
        
        if self.days_inactive > 14:
            recommendations.append({
                'type': 'activity',
                'priority': 'high',
                'action': 'Re-engagement campaign for inactive users',
                'impact': 'medium'
            })
        
        self.recommendations = recommendations
        self.save(update_fields=['recommendations'])
        
        return recommendations


class TenantFeatureFlag(TimeStampedModel, SoftDeleteModel):
    """
    Feature flags for tenant-specific feature toggles.
    
    This model manages feature flags that enable or disable
    features for specific tenants or groups.
    """
    
    FLAG_TYPE_CHOICES = [
        ('boolean', _('Boolean')),
        ('percentage', _('Percentage Rollout')),
        ('whitelist', _('Whitelist')),
        ('blacklist', _('Blacklist')),
        ('conditional', _('Conditional')),
    ]
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('scheduled', _('Scheduled')),
        ('expired', _('Expired')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='feature_flags',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this feature flag belongs to')
    )
    
    # Flag information
    flag_key = models.CharField(
        max_length=100,
        verbose_name=_('Flag Key'),
        help_text=_('Unique identifier for the feature flag')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Name'),
        help_text=_('Human-readable name of the feature')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Description of what the feature does')
    )
    
    # Flag configuration
    flag_type = models.CharField(
        max_length=20,
        choices=FLAG_TYPE_CHOICES,
        default='boolean',
        verbose_name=_('Flag Type'),
        help_text=_('Type of feature flag')
    )
    is_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Is Enabled'),
        help_text=_('Whether the feature is enabled')
    )
    
    # Rollout configuration
    rollout_pct = models.IntegerField(
        default=0,
        verbose_name=_('Rollout Percentage'),
        help_text=_('Percentage of users to rollout to (0-100)')
    )
    variant = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Variant'),
        help_text=_('A/B testing variant')
    )
    
    # Timing
    starts_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Starts At'),
        help_text=_('When the flag becomes active')
    )
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Expires At'),
        help_text=_('When the flag expires')
    )
    
    # Targeting
    target_users = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Target Users'),
        help_text=_('List of user IDs to target')
    )
    target_segments = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Target Segments'),
        help_text=_('List of user segments to target')
    )
    conditions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Conditions'),
        help_text=_('Conditions for flag activation')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional flag metadata')
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Tags'),
        help_text=_('Tags for categorization')
    )
    
    class Meta:
        db_table = 'tenant_feature_flags'
        verbose_name = _('Tenant Feature Flag')
        verbose_name_plural = _('Tenant Feature Flags')
        ordering = ['flag_key']
        unique_together = ['tenant', 'flag_key']
        indexes = [
            models.Index(fields=['tenant', 'flag_key'], name='idx_tenant_flag_key_1765'),
            models.Index(fields=['is_enabled'], name='idx_is_enabled_1766'),
            models.Index(fields=['starts_at'], name='idx_starts_at_1767'),
            models.Index(fields=['expires_at'], name='idx_expires_at_1768'),
        ]
    
    def __str__(self):
        return f"{self.name} for {self.tenant.name}"
    
    def clean(self):
        super().clean()
        if self.rollout_pct < 0 or self.rollout_pct > 100:
            raise ValidationError(_('Rollout percentage must be between 0 and 100.'))
        
        if self.starts_at and self.expires_at and self.starts_at >= self.expires_at:
            raise ValidationError(_('Start time must be before expiry time.'))
    
    def is_active(self):
        """Check if the flag is currently active."""
        if not self.is_enabled:
            return False
        
        now = timezone.now()
        
        # Check timing
        if self.starts_at and now < self.starts_at:
            return False
        
        if self.expires_at and now > self.expires_at:
            return False
        
        return True
    
    def is_enabled_for_user(self, user):
        """Check if flag is enabled for a specific user."""
        if not self.is_active():
            return False
        
        if self.flag_type == 'boolean':
            return self.is_enabled
        
        elif self.flag_type == 'percentage':
            if not user.id:
                return False
            # Use user ID for consistent percentage rollout
            return (user.id % 100) < self.rollout_pct
        
        elif self.flag_type == 'whitelist':
            return str(user.id) in self.target_users
        
        elif self.flag_type == 'blacklist':
            return str(user.id) not in self.target_users
        
        elif self.flag_type == 'conditional':
            # Implement conditional logic based on conditions
            return self.evaluate_conditions(user)
        
        return False
    
    def evaluate_conditions(self, user):
        """Evaluate conditional flag logic."""
        # This would implement complex condition evaluation
        # For now, return False as placeholder
        return False
    
    def get_variant_for_user(self, user):
        """Get A/B testing variant for user."""
        if not self.is_enabled_for_user(user):
            return None
        
        if self.variant:
            return self.variant
        
        # Assign variant based on user ID
        variants = self.metadata.get('variants', ['control', 'test'])
        if variants:
            return variants[user.id % len(variants)]
        
        return None
    
    def enable(self):
        """Enable the feature flag."""
        self.is_enabled = True
        self.save(update_fields=['is_enabled'])
    
    def disable(self):
        """Disable the feature flag."""
        self.is_enabled = False
        self.save(update_fields=['is_enabled'])
    
    def rollout_to_percentage(self, percentage):
        """Rollout to a specific percentage."""
        self.rollout_pct = percentage
        self.is_enabled = True
        self.save(update_fields=['rollout_pct', 'is_enabled'])


class TenantNotification(TimeStampedModel, SoftDeleteModel):
    """
    Tenant notifications and alerts.
    
    This model manages notifications sent to tenants
    including system alerts, announcements, and reminders.
    """
    
    NOTIFICATION_TYPE_CHOICES = [
        ('system', _('System')),
        ('billing', _('Billing')),
        ('security', _('Security')),
        ('feature', _('Feature')),
        ('announcement', _('Announcement')),
        ('reminder', _('Reminder')),
        ('warning', _('Warning')),
        ('info', _('Information')),
    ]
    
    PRIORITY_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('urgent', _('Urgent')),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('sent', _('Sent')),
        ('delivered', _('Delivered')),
        ('read', _('Read')),
        ('failed', _('Failed')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this notification belongs to')
    )
    
    # Notification content
    title = models.CharField(
        max_length=255,
        verbose_name=_('Title'),
        help_text=_('Notification title')
    )
    message = models.TextField(
        verbose_name=_('Message'),
        help_text=_('Notification message content')
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='info',
        verbose_name=_('Notification Type'),
        help_text=_('Type of notification')
    )
    
    # Priority and status
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name=_('Priority'),
        help_text=_('Notification priority')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Status'),
        help_text=_('Current notification status')
    )
    
    # Delivery settings
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('Is Read'),
        help_text=_('Whether the notification has been read')
    )
    read_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Read At'),
        help_text=_('When the notification was read')
    )
    
    # Targeting
    target_users = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Target Users'),
        help_text=_('List of user IDs to notify')
    )
    target_roles = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Target Roles'),
        help_text=_('List of user roles to notify')
    )
    
    # Channels
    send_email = models.BooleanField(
        default=False,
        verbose_name=_('Send Email'),
        help_text=_('Whether to send via email')
    )
    send_push = models.BooleanField(
        default=False,
        verbose_name=_('Send Push'),
        help_text=_('Whether to send via push notification')
    )
    send_sms = models.BooleanField(
        default=False,
        verbose_name=_('Send SMS'),
        help_text=_('Whether to send via SMS')
    )
    send_in_app = models.BooleanField(
        default=True,
        verbose_name=_('Send In-App'),
        help_text=_('Whether to show in-app notification')
    )
    
    # Timing
    scheduled_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Scheduled At'),
        help_text=_('When to send the notification')
    )
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Expires At'),
        help_text=_('When notification expires')
    )
    
    # Actions and links
    action_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Action URL'),
        help_text=_('URL for action button')
    )
    action_text = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Action Text'),
        help_text=_('Text for action button')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional notification metadata')
    )
    
    class Meta:
        db_table = 'tenant_notifications'
        verbose_name = _('Tenant Notification')
        verbose_name_plural = _('Tenant Notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status'], name='idx_tenant_status_1769'),
            models.Index(fields=['notification_type'], name='idx_notification_type_1770'),
            models.Index(fields=['priority'], name='idx_priority_1771'),
            models.Index(fields=['is_read'], name='idx_is_read_1772'),
            models.Index(fields=['scheduled_at'], name='idx_scheduled_at_1773'),
        ]
    
    def __str__(self):
        return f"{self.title} for {self.tenant.name}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_sent(self):
        """Mark notification as sent."""
        self.status = 'sent'
        self.save(update_fields=['status'])
    
    def mark_as_delivered(self):
        """Mark notification as delivered."""
        self.status = 'delivered'
        self.save(update_fields=['status'])
    
    def mark_as_failed(self):
        """Mark notification as failed."""
        self.status = 'failed'
        self.save(update_fields=['status'])
    
    def is_expired(self):
        """Check if notification has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def can_send_to_user(self, user):
        """Check if notification can be sent to a specific user."""
        if self.target_users and str(user.id) not in self.target_users:
            return False
        
        if self.target_roles:
            user_roles = getattr(user, 'roles', [])
            if not any(role in self.target_roles for role in user_roles):
                return False
        
        return True
    
    def get_delivery_channels(self):
        """Get list of enabled delivery channels."""
        channels = []
        if self.send_in_app:
            channels.append('in_app')
        if self.send_email:
            channels.append('email')
        if self.send_push:
            channels.append('push')
        if self.send_sms:
            channels.append('sms')
        return channels
    
    @property
    def is_urgent(self):
        """Check if notification is urgent."""
        return self.priority == 'urgent'
    
    @property
    def is_pending(self):
        """Check if notification is pending."""
        return self.status == 'pending'
