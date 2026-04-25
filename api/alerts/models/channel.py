"""
Alert Channel Models
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, validate_email
from django.core.exceptions import ValidationError
from datetime import timedelta
import json

from decimal import Decimal
import uuid
import re

from .core import AlertRule, AlertLog, Notification


class AlertChannel(models.Model):
    """Configuration for different alert notification channels"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    CHANNEL_TYPES = [
        ('email', 'Email'),
        ('telegram', 'Telegram'),
        ('sms', 'SMS'),
        ('webhook', 'Webhook'),
        ('slack', 'Slack'),
        ('discord', 'Discord'),
        ('msteams', 'Microsoft Teams'),
        ('push', 'Push Notification'),
        ('voice_call', 'Voice Call'),
        ('pager', 'Pager'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
        ('maintenance', 'Maintenance'),
        ('testing', 'Testing'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    description = models.TextField(blank=True)
    
    # Channel configuration
    is_enabled = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Higher number = higher priority"
    )
    
    # Rate limiting
    rate_limit_per_minute = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Maximum notifications per minute"
    )
    rate_limit_per_hour = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Maximum notifications per hour"
    )
    rate_limit_per_day = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1), MaxValueValidator(100000)],
        help_text="Maximum notifications per day"
    )
    
    # Retry configuration
    max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    retry_delay_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    
    # Channel-specific configuration
    config = models.JSONField(
        default=dict,
        help_text="Channel-specific configuration"
    )
    
    # Status and health
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_success = models.DateTimeField(null=True, blank=True)
    last_failure = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.IntegerField(default=0)
    
    # Metrics
    total_sent = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    success_rate = models.FloatField(default=100.0)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertchannel_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"
    
    def clean(self):
        """Validate channel configuration"""
        super().clean()
        
        # Validate channel-specific configuration
        if self.channel_type == 'email':
            self._validate_email_config()
        elif self.channel_type == 'telegram':
            self._validate_telegram_config()
        elif self.channel_type == 'sms':
            self._validate_sms_config()
        elif self.channel_type == 'webhook':
            self._validate_webhook_config()
        elif self.channel_type == 'slack':
            self._validate_slack_config()
        elif self.channel_type == 'discord':
            self._validate_discord_config()
        elif self.channel_type == 'msteams':
            self._validate_msteams_config()
        elif self.channel_type == 'push':
            self._validate_push_config()
        elif self.channel_type == 'voice_call':
            self._validate_voice_call_config()
        elif self.channel_type == 'pager':
            self._validate_pager_config()
    
    def _validate_email_config(self):
        """Validate email configuration"""
        required_fields = ['smtp_server', 'smtp_port', 'username', 'password']
        for field in required_fields:
            if field not in self.config:
                raise ValidationError(f"Email channel requires '{field}' in configuration")
    
    def _validate_telegram_config(self):
        """Validate Telegram configuration"""
        if 'bot_token' not in self.config:
            raise ValidationError("Telegram channel requires 'bot_token' in configuration")
    
    def _validate_sms_config(self):
        """Validate SMS configuration"""
        if 'provider' not in self.config:
            raise ValidationError("SMS channel requires 'provider' in configuration")
        
        provider = self.config['provider']
        if provider == 'twilio':
            required_fields = ['account_sid', 'auth_token', 'from_number']
        elif provider == 'aws_sns':
            required_fields = ['access_key', 'secret_key', 'region']
        else:
            required_fields = []
        
        for field in required_fields:
            if field not in self.config:
                raise ValidationError(f"SMS provider {provider} requires '{field}' in configuration")
    
    def _validate_webhook_config(self):
        """Validate webhook configuration"""
        if 'url' not in self.config:
            raise ValidationError("Webhook channel requires 'url' in configuration")
        
        url = self.config['url']
        if not url.startswith(('http://', 'https://')):
            raise ValidationError("Webhook URL must start with http:// or https://")
    
    def _validate_slack_config(self):
        """Validate Slack configuration"""
        if 'webhook_url' not in self.config:
            raise ValidationError("Slack channel requires 'webhook_url' in configuration")
    
    def _validate_discord_config(self):
        """Validate Discord configuration"""
        if 'webhook_url' not in self.config:
            raise ValidationError("Discord channel requires 'webhook_url' in configuration")
    
    def _validate_msteams_config(self):
        """Validate Microsoft Teams configuration"""
        if 'webhook_url' not in self.config:
            raise ValidationError("Microsoft Teams channel requires 'webhook_url' in configuration")
    
    def _validate_push_config(self):
        """Validate push notification configuration"""
        if 'service' not in self.config:
            raise ValidationError("Push channel requires 'service' in configuration")
    
    def _validate_voice_call_config(self):
        """Validate voice call configuration"""
        if 'provider' not in self.config:
            raise ValidationError("Voice call channel requires 'provider' in configuration")
    
    def _validate_pager_config(self):
        """Validate pager configuration"""
        if 'provider' not in self.config:
            raise ValidationError("Pager channel requires 'provider' in configuration")
    
    def can_send_notification(self):
        """Check if channel can send notification"""
        if not self.is_enabled or self.status != 'active':
            return False
        
        # Check rate limits
        if not self._check_rate_limits():
            return False
        
        return True
    
    def _check_rate_limits(self):
        """Check if channel is within rate limits"""
        now = timezone.now()
        
        # Check per-minute limit
        minute_ago = now - timedelta(minutes=1)
        minute_count = Notification.objects.filter(
            notification_type=self.channel_type,
            created_at__gte=minute_ago
        ).count()
        
        if minute_count >= self.rate_limit_per_minute:
            return False
        
        # Check per-hour limit
        hour_ago = now - timedelta(hours=1)
        hour_count = Notification.objects.filter(
            notification_type=self.channel_type,
            created_at__gte=hour_ago
        ).count()
        
        if hour_count >= self.rate_limit_per_hour:
            return False
        
        # Check per-day limit
        day_ago = now - timedelta(days=1)
        day_count = Notification.objects.filter(
            notification_type=self.channel_type,
            created_at__gte=day_ago
        ).count()
        
        if day_count >= self.rate_limit_per_day:
            return False
        
        return True
    
    def record_success(self):
        """Record successful notification"""
        self.last_success = timezone.now()
        self.consecutive_failures = 0
        self.total_sent += 1
        self._update_success_rate()
        self.save(update_fields=['last_success', 'consecutive_failures', 'total_sent', 'success_rate'])
    
    def record_failure(self):
        """Record failed notification"""
        self.last_failure = timezone.now()
        self.consecutive_failures += 1
        self.total_failed += 1
        self._update_success_rate()
        
        # Auto-disable after too many consecutive failures
        if self.consecutive_failures >= 5:
            self.status = 'error'
        
        self.save(update_fields=['last_failure', 'consecutive_failures', 'total_failed', 'success_rate', 'status'])
    
    def _update_success_rate(self):
        """Update success rate"""
        total = self.total_sent + self.total_failed
        if total > 0:
            self.success_rate = (self.total_sent / total) * 100
        else:
            self.success_rate = 100.0
    
    def get_health_status(self):
        """Get channel health status"""
        if self.status == 'error':
            return 'critical'
        elif self.status == 'maintenance':
            return 'warning'
        elif self.consecutive_failures >= 3:
            return 'warning'
        elif self.success_rate < 90:
            return 'warning'
        else:
            return 'healthy'
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['channel_type', 'is_enabled'], name='idx_channel_type_is_enable_146'),
            models.Index(fields=['status'], name='idx_status_693'),
            models.Index(fields=['priority'], name='idx_priority_694'),
        ]
        db_table_comment = "Configuration for different alert notification channels"
        verbose_name = "Alert Channel"
        verbose_name_plural = "Alert Channels"


class ChannelRoute(models.Model):
    """Routing rules for alert channels"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ROUTE_TYPES = [
        ('rule_based', 'Rule-Based'),
        ('severity_based', 'Severity-Based'),
        ('time_based', 'Time-Based'),
        ('recipient_based', 'Recipient-Based'),
        ('condition_based', 'Condition-Based'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Route configuration
    route_type = models.CharField(max_length=20, choices=ROUTE_TYPES)
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    # Source and destination
    source_rules = models.ManyToManyField(
        AlertRule,
        related_name='%(app_label)s_%(class)s_source',
        blank=True
    )
    source_channels = models.ManyToManyField(
        AlertChannel,
        related_name='%(app_label)s_%(class)s_source',
        blank=True
    )
    destination_channels = models.ManyToManyField(
        AlertChannel,
        related_name='%(app_label)s_%(class)s_destination'
    )
    
    # Routing conditions
    conditions = models.JSONField(
        default=dict,
        help_text="Conditions for routing"
    )
    
    # Time-based routing
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    days_of_week = models.JSONField(
        default=list,
        help_text="Days of week (0=Monday)"
    )
    
    # Escalation settings
    escalation_delay_minutes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    escalate_after_failures = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_channelroute_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Route: {self.name}"
    
    def should_route(self, alert_log, notification_type):
        """Check if this route should be applied"""
        if not self.is_active:
            return False
        
        # Check time-based conditions
        if not self._check_time_conditions():
            return False
        
        # Check route type specific conditions
        if self.route_type == 'rule_based':
            return self._check_rule_based_condition(alert_log)
        elif self.route_type == 'severity_based':
            return self._check_severity_based_condition(alert_log)
        elif self.route_type == 'time_based':
            return self._check_time_based_condition(alert_log)
        elif self.route_type == 'recipient_based':
            return self._check_recipient_based_condition(alert_log)
        elif self.route_type == 'condition_based':
            return self._check_condition_based_condition(alert_log)
        
        return False
    
    def _check_time_conditions(self):
        """Check if current time is within routing time window"""
        if not self.start_time or not self.end_time:
            return True
        
        now = timezone.now().time()
        return self.start_time <= now <= self.end_time
    
    def _check_rule_based_condition(self, alert_log):
        """Check rule-based routing condition"""
        return self.source_rules.filter(id=alert_log.rule.id).exists()
    
    def _check_severity_based_condition(self, alert_log):
        """Check severity-based routing condition"""
        severity_conditions = self.conditions.get('severity', [])
        return alert_log.rule.severity in severity_conditions
    
    def _check_time_based_condition(self, alert_log):
        """Check time-based routing condition"""
        # Additional time-based checks beyond basic time window
        hour_conditions = self.conditions.get('hours', [])
        if hour_conditions:
            current_hour = timezone.now().hour
            return current_hour in hour_conditions
        
        return True
    
    def _check_recipient_based_condition(self, alert_log):
        """Check recipient-based routing condition"""
        recipient_conditions = self.conditions.get('recipients', [])
        if not recipient_conditions:
            return True
        
        # Check if any notification recipient matches conditions
        notifications = alert_log.notifications.all()
        for notification in notifications:
            for condition in recipient_conditions:
                if condition in notification.recipient:
                    return True
        
        return False
    
    def _check_condition_based_condition(self, alert_log):
        """Check custom condition-based routing"""
        conditions = self.conditions.get('custom', [])
        
        for condition in conditions:
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            
            if field == 'trigger_value':
                current_value = alert_log.trigger_value
            elif field == 'threshold_value':
                current_value = alert_log.threshold_value
            elif field == 'age_minutes':
                current_value = alert_log.age_in_minutes
            else:
                continue
            
            if operator == 'gt' and current_value > value:
                return True
            elif operator == 'lt' and current_value < value:
                return True
            elif operator == 'eq' and current_value == value:
                return True
            elif operator == 'gte' and current_value >= value:
                return True
            elif operator == 'lte' and current_value <= value:
                return True
        
        return False
    
    def get_destination_channels(self):
        """Get destination channels for this route"""
        return self.destination_channels.filter(is_enabled=True, status='active')
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['route_type', 'is_active'], name='idx_route_type_is_active_695'),
            models.Index(fields=['priority'], name='idx_priority_696'),
        ]
        db_table_comment = "Routing rules for alert channels"
        verbose_name = "Channel Route"
        verbose_name_plural = "Channel Routes"


class ChannelHealthLog(models.Model):
    """Health monitoring logs for channels"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    channel = models.ForeignKey(
        AlertChannel,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Health check details
    status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
            ('unknown', 'Unknown'),
        ]
    )
    response_time_ms = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Check details
    check_type = models.CharField(
        max_length=20,
        choices=[
            ('connectivity', 'Connectivity Check'),
            ('authentication', 'Authentication Check'),
            ('rate_limit', 'Rate Limit Check'),
            ('configuration', 'Configuration Check'),
            ('performance', 'Performance Check'),
        ]
    )
    details = models.JSONField(default=dict)
    
    # Timestamps
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    def __str__(self):
        return f"Health: {self.channel.name} - {self.status}"
    
    @classmethod
    def log_health_check(cls, channel, status, check_type, response_time_ms=None, error_message="", details=None):
        """Log a health check result"""
        return cls.objects.create(
            channel=channel,
            status=status,
            check_type=check_type,
            response_time_ms=response_time_ms,
            error_message=error_message,
            details=details or {}
        )
    
    @classmethod
    def get_recent_health(cls, channel, hours=24):
        """Get recent health status for a channel"""
        cutoff = timezone.now() - timedelta(hours=hours)
        return cls.objects.filter(
            channel=channel,
            checked_at__gte=cutoff
        ).order_by('-checked_at')
    
    @classmethod
    def get_health_summary(cls, channel, hours=24):
        """Get health summary for a channel"""
        cutoff = timezone.now() - timedelta(hours=hours)
        checks = cls.objects.filter(
            channel=channel,
            checked_at__gte=cutoff
        )
        
        total_checks = checks.count()
        if total_checks == 0:
            return {'status': 'unknown', 'checks': 0}
        
        healthy_checks = checks.filter(status='healthy').count()
        warning_checks = checks.filter(status='warning').count()
        critical_checks = checks.filter(status='critical').count()
        
        health_percentage = (healthy_checks / total_checks) * 100
        
        if critical_checks > 0:
            overall_status = 'critical'
        elif warning_checks > 0:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'
        
        return {
            'status': overall_status,
            'checks': total_checks,
            'healthy': healthy_checks,
            'warning': warning_checks,
            'critical': critical_checks,
            'health_percentage': health_percentage
        }
    
    class Meta:
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['channel', 'checked_at'], name='idx_channel_checked_at_697'),
            models.Index(fields=['status', 'checked_at'], name='idx_status_checked_at_698'),
            models.Index(fields=['check_type', 'checked_at'], name='idx_check_type_checked_at_699'),
        ]
        db_table_comment = "Health monitoring logs for channels"
        verbose_name = "Channel Health Log"
        verbose_name_plural = "Channel Health Logs"


class ChannelRateLimit(models.Model):
    """Rate limiting configuration for channels"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    channel = models.OneToOneField(
        AlertChannel,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Rate limit configuration
    limit_type = models.CharField(
        max_length=20,
        choices=[
            ('fixed', 'Fixed Window'),
            ('sliding', 'Sliding Window'),
            ('token_bucket', 'Token Bucket'),
            ('leaky_bucket', 'Leaky Bucket'),
        ],
        default='sliding'
    )
    
    # Time windows
    window_seconds = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(86400)]
    )
    
    # Limits
    max_requests = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100000)]
    )
    burst_size = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    
    # Token bucket specific
    refill_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.1), MaxValueValidator(1000)]
    )
    bucket_size = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )
    
    # Current state
    current_tokens = models.FloatField(default=0)
    last_refill = models.DateTimeField(auto_now=True)
    
    # Statistics
    total_requests = models.IntegerField(default=0)
    rejected_requests = models.IntegerField(default=0)
    rejection_rate = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Rate Limit: {self.channel.name}"
    
    def can_send(self):
        """Check if channel can send notification based on rate limit"""
        if self.limit_type == 'fixed':
            return self._check_fixed_window()
        elif self.limit_type == 'sliding':
            return self._check_sliding_window()
        elif self.limit_type == 'token_bucket':
            return self._check_token_bucket()
        elif self.limit_type == 'leaky_bucket':
            return self._check_leaky_bucket()
        
        return True
    
    def _check_fixed_window(self):
        """Check fixed window rate limit"""
        now = timezone.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        requests = Notification.objects.filter(
            notification_type=self.channel.channel_type,
            created_at__gte=window_start
        ).count()
        
        return requests < self.max_requests
    
    def _check_sliding_window(self):
        """Check sliding window rate limit"""
        now = timezone.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        requests = Notification.objects.filter(
            notification_type=self.channel.channel_type,
            created_at__gte=window_start
        ).count()
        
        return requests < self.max_requests
    
    def _check_token_bucket(self):
        """Check token bucket rate limit"""
        self._refill_tokens()
        return self.current_tokens >= 1
    
    def _check_leaky_bucket(self):
        """Check leaky bucket rate limit"""
        # Simplified leaky bucket implementation
        return self._check_sliding_window()
    
    def _refill_tokens(self):
        """Refill tokens for token bucket algorithm"""
        if self.limit_type != 'token_bucket' or not self.refill_rate:
            return
        
        now = timezone.now()
        time_passed = (now - self.last_refill).total_seconds()
        tokens_to_add = time_passed * self.refill_rate
        
        self.current_tokens = min(self.bucket_size, self.current_tokens + tokens_to_add)
        self.last_refill = now
        self.save(update_fields=['current_tokens', 'last_refill'])
    
    def consume_token(self):
        """Consume a token from the bucket"""
        if self.limit_type == 'token_bucket':
            if self.current_tokens >= 1:
                self.current_tokens -= 1
                self.total_requests += 1
                self.save(update_fields=['current_tokens', 'total_requests'])
                return True
            else:
                self.rejected_requests += 1
                self.save(update_fields=['rejected_requests'])
                return False
        
        return True
    
    def update_statistics(self):
        """Update rejection rate statistics"""
        total = self.total_requests + self.rejected_requests
        if total > 0:
            self.rejection_rate = (self.rejected_requests / total) * 100
        self.save(update_fields=['rejection_rate'])
    
    class Meta:
        ordering = ['channel__name']
        indexes = [
            models.Index(fields=['channel', 'limit_type'], name='idx_channel_limit_type_700'),
        ]
        db_table_comment = "Rate limiting configuration for channels"
        verbose_name = "Channel Rate Limit"
        verbose_name_plural = "Channel Rate Limits"


class AlertRecipient(models.Model):
    """Management of alert recipients"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    RECIPIENT_TYPES = [
        ('user', 'User'),
        ('group', 'Group'),
        ('email', 'Email Address'),
        ('phone', 'Phone Number'),
        ('webhook', 'Webhook URL'),
        ('slack', 'Slack Channel'),
        ('discord', 'Discord Channel'),
        ('msteams', 'Teams Channel'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    name = models.CharField(max_length=100)
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPES)
    
    # Recipient details
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts_alertrecipient_user'
    )
    email_address = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    webhook_url = models.URLField(blank=True)
    
    # Channel preferences
    preferred_channels = models.JSONField(
        default=list,
        help_text="List of preferred channel types"
    )
    channel_config = models.JSONField(
        default=dict,
        help_text="Channel-specific configuration"
    )
    
    # Notification preferences
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Availability
    available_hours_start = models.TimeField(null=True, blank=True)
    available_hours_end = models.TimeField(null=True, blank=True)
    available_days = models.JSONField(
        default=list,
        help_text="Days of week (0=Monday)"
    )
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Rate limiting per recipient
    max_notifications_per_hour = models.IntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    max_notifications_per_day = models.IntegerField(
        default=500,
        validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertrecipient_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_recipient_type_display()})"
    
    def clean(self):
        """Validate recipient configuration"""
        super().clean()
        
        # Validate recipient type specific fields
        if self.recipient_type == 'user' and not self.user:
            raise ValidationError("User recipient type requires a user")
        
        if self.recipient_type == 'email' and not self.email_address:
            raise ValidationError("Email recipient type requires an email address")
        
        if self.recipient_type == 'phone' and not self.phone_number:
            raise ValidationError("Phone recipient type requires a phone number")
        
        if self.recipient_type == 'webhook' and not self.webhook_url:
            raise ValidationError("Webhook recipient type requires a webhook URL")
    
    def is_available_now(self):
        """Check if recipient is available now"""
        if not self.is_active:
            return False
        
        if not self.available_hours_start or not self.available_hours_end:
            return True
        
        # Check time availability
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(self.timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo('UTC')
        
        now = timezone.now().astimezone(tz)
        current_time = now.time()
        
        if not (self.available_hours_start <= current_time <= self.available_hours_end):
            return False
        
        # Check day availability
        if self.available_days and now.weekday() not in self.available_days:
            return False
        
        return True
    
    def get_contact_info(self):
        """Get contact information for the recipient"""
        if self.recipient_type == 'user':
            return {
                'type': 'user',
                'user_id': self.user.id,
                'email': self.user.email,
                'phone': getattr(self.user, 'phone', ''),
                'name': self.user.get_full_name() or self.user.username
            }
        elif self.recipient_type == 'email':
            return {
                'type': 'email',
                'email': self.email_address,
                'name': self.name
            }
        elif self.recipient_type == 'phone':
            return {
                'type': 'phone',
                'phone': self.phone_number,
                'name': self.name
            }
        elif self.recipient_type == 'webhook':
            return {
                'type': 'webhook',
                'url': self.webhook_url,
                'name': self.name
            }
        else:
            return {
                'type': self.recipient_type,
                'name': self.name,
                'config': self.channel_config
            }
    
    def can_receive_notification(self):
        """Check if recipient can receive notification"""
        if not self.is_available_now():
            return False
        
        # Check rate limits
        now = timezone.now()
        
        # Check per-hour limit
        hour_ago = now - timedelta(hours=1)
        hour_notifications = Notification.objects.filter(
            recipient=self.get_contact_identifier(),
            created_at__gte=hour_ago
        ).count()
        
        if hour_notifications >= self.max_notifications_per_hour:
            return False
        
        # Check per-day limit
        day_ago = now - timedelta(days=1)
        day_notifications = Notification.objects.filter(
            recipient=self.get_contact_identifier(),
            created_at__gte=day_ago
        ).count()
        
        if day_notifications >= self.max_notifications_per_day:
            return False
        
        return True
    
    def get_contact_identifier(self):
        """Get unique identifier for the recipient"""
        if self.recipient_type == 'user':
            return f"user:{self.user.id}"
        elif self.recipient_type == 'email':
            return f"email:{self.email_address}"
        elif self.recipient_type == 'phone':
            return f"phone:{self.phone_number}"
        elif self.recipient_type == 'webhook':
            return f"webhook:{self.webhook_url}"
        else:
            return f"{self.recipient_type}:{self.name}"
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['recipient_type', 'is_active'], name='idx_recipient_type_is_acti_266'),
            models.Index(fields=['priority'], name='idx_priority_702'),
        ]
        db_table_comment = "Management of alert recipients"
        verbose_name = "Alert Recipient"
        verbose_name_plural = "Alert Recipients"
