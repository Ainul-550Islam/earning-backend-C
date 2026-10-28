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
        return f"AlertChannel: {self.name} - {self.channel_type}"
    
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
    
    def check_rate_limit(self, notification_type=None):
        """Check if channel is within rate limits. Alias for can_send_notification."""
        return self.can_send_notification()

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
        self._skip_health_signal = True
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
        
        self._skip_health_signal = True
        self.save(update_fields=['last_failure', 'consecutive_failures', 'total_failed', 'success_rate', 'status'])
    
    def _update_success_rate(self):
        """Update success rate"""
        total = self.total_sent + self.total_failed
        if total > 0:
            self.success_rate = (self.total_sent / total) * 100
        else:
            self.success_rate = 100.0
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['channel_type', 'is_enabled']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
        ]
        db_table_comment = "Configuration for different alert notification channels"
        verbose_name = "Alert Channel"
        verbose_name_plural = "Alert Channels"


    def get_success_rate(self, days=30):
        """Return send success rate as a percentage"""
        success = getattr(self, 'success_count', 0) or 0
        fail = getattr(self, 'failure_count', 0) or 0
        total = success + fail
        if total == 0:
            return 0.0
        return round((success / total * 100), 2)

    def get_rate_limit_status(self):
        """Return current rate limit status"""
        return {
            'can_send': self.can_send_notification(),
            'limit_per_minute': getattr(self, 'rate_limit_per_minute', 10),
            'limit_per_hour': getattr(self, 'rate_limit_per_hour', 100),
        }

    def mark_error(self, error_message=""):
        """Mark channel as error state"""
        self.status = 'error'
        self.last_error_message = error_message
        self.save()

    def mark_active(self):
        """Mark channel as active"""
        self.status = 'active'
        self.save()

    def mark_maintenance(self):
        """Mark channel as in maintenance"""
        self.status = 'maintenance'
        self.save()


    def mark_healthy(self, response_time_ms=0):
        """Mark channel as healthy after a check"""
        self.status = 'active'
        self.save()

    def send_notification(self, notification=None, recipient=None, message=None, subject=None, **kwargs):
        """Send a notification through this channel"""
        try:
            from api.alerts.services.channel import NotificationService
            if notification:
                return NotificationService._send_notification(notification)
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"send_notification error: {e}")
            return False

    def get_status_display(self):
        choices = {
            'active': 'Active', 'inactive': 'Inactive',
            'error': 'Error', 'maintenance': 'Maintenance'
        }
        return choices.get(getattr(self,'status','active'), 'Unknown')

    def get_health_status(self):
        """Return health status: healthy/warning/critical"""
        status = getattr(self, 'status', 'active')
        if status == 'active':
            return 'healthy'
        elif status == 'error':
            return 'critical'
        return 'warning'

    def get_channel_type_display(self):
        choices = {
            'email': 'Email', 'sms': 'SMS', 'slack': 'Slack',
            'telegram': 'Telegram', 'webhook': 'Webhook',
            'discord': 'Discord', 'pagerduty': 'PagerDuty', 'opsgenie': 'OpsGenie'
        }
        return choices.get(getattr(self,'channel_type','email'), 'Email')


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
        return f"ChannelRoute: {self.name} - {self.route_type}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.priority is not None and self.priority < 0:
            errors['priority'] = 'Priority cannot be negative.'
        if self.route_type == 'time_based':
            if hasattr(self, 'time_start') and hasattr(self, 'time_end') and (not self.time_start or not self.time_end):
                errors['time_start'] = 'time_based routes require both time_start and time_end.'
            elif hasattr(self, 'time_start') and hasattr(self, 'time_end') and (self.time_start >= self.time_end):
                errors['time_start'] = 'time_start must be before time_end.'
        if errors:
            raise ValidationError(errors)


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
            models.Index(fields=['route_type', 'is_active']),
            models.Index(fields=['priority']),
        ]
        db_table_comment = "Routing rules for alert channels"
        verbose_name = "Channel Route"
        verbose_name_plural = "Channel Routes"


    def get_route_type_display(self):
        choices = {'forward':'Forward','broadcast':'Broadcast','round_robin':'Round Robin','failover':'Failover','conditional':'Conditional'}
        return choices.get(getattr(self,'route_type','forward'), 'Forward')

    def get_status_display(self):
        return 'Active' if getattr(self,'is_active',True) else 'Inactive'


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
    check_name = models.CharField(max_length=200, blank=True, default='')
    status_message = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
            ('unknown', 'Unknown'),
            ('checking', 'Checking'),
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
        return f"ChannelHealthLog: {self.id} - {self.check_type}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.response_time_ms is not None and self.response_time_ms < 0:
            errors['response_time_ms'] = 'Response time cannot be negative.'
        if self.status == 'failed' and not self.error_message:
            errors['error_message'] = 'Failed health checks must include an error message.'
        if errors:
            raise ValidationError(errors)


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
    def log_successful_send(cls, channel_type=None, recipient=None, **kwargs):
        """Log a successful notification send (no DB record needed, just metrics)"""
        import logging
        logging.getLogger(__name__).debug(
            f"Successful send: type={channel_type}, recipient={recipient}"
        )

    @classmethod
    def log_failed_send(cls, channel_type=None, recipient=None, error_message="", **kwargs):
        """Log a failed notification send (no DB record needed, just metrics)"""
        import logging
        logging.getLogger(__name__).warning(
            f"Failed send: type={channel_type}, recipient={recipient}, error={error_message}"
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
            models.Index(fields=['channel', 'checked_at']),
            models.Index(fields=['status', 'checked_at']),
            models.Index(fields=['check_type', 'checked_at']),
        ]
        db_table_comment = "Health monitoring logs for channels"
        verbose_name = "Channel Health Log"
        verbose_name_plural = "Channel Health Logs"

    def is_healthy(self):
        """Return True if status is healthy"""
        return self.status == 'healthy'

    def get_response_time_display(self):
        """Return formatted response time"""
        if self.response_time_ms is None:
            return 'N/A'
        return f'{self.response_time_ms} ms'

    def get_check_type_display(self):
        choices = {
            'connectivity': 'Connectivity', 'authentication': 'Authentication',
            'rate_limit': 'Rate Limit', 'configuration': 'Configuration',
            'performance': 'Performance', 'availability': 'Availability',
        }
        return choices.get(getattr(self, 'check_type', 'connectivity'), 'Connectivity')

    def get_status_display(self):
        choices = {
            'healthy': 'Healthy', 'warning': 'Warning',
            'critical': 'Critical', 'unknown': 'Unknown', 'error': 'Error',
        }
        return choices.get(getattr(self, 'status', 'healthy'), 'Unknown')


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
        return f"ChannelRateLimit: {self.id} - {self.limit_type}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if hasattr(self, 'max_per_window') and (self.max_per_window is not None and self.max_per_window < 1):
            errors['max_per_window'] = 'max_per_window must be at least 1.'
        if self.window_seconds is not None and self.window_seconds < 1:
            errors['window_seconds'] = 'window_seconds must be at least 1 second.'
        if hasattr(self, 'burst_limit') and hasattr(self, 'max_per_window') and (self.burst_limit is not None and self.max_per_window is not None):
            if hasattr(self, 'burst_limit') and hasattr(self, 'max_per_window') and (self.burst_limit < self.max_per_window):
                errors['burst_limit'] = 'burst_limit must be >= max_per_window.'
        if self.limit_type == 'token_bucket':
            if not getattr(self, 'refill_rate', None):
                errors['refill_rate'] = 'token_bucket limits require a refill_rate.'
        if errors:
            raise ValidationError(errors)


    def can_send_notification(self):
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
            models.Index(fields=['channel', 'limit_type']),
        ]
        db_table_comment = "Rate limiting configuration for channels"
        verbose_name = "Channel Rate Limit"
        verbose_name_plural = "Channel Rate Limits"

    def refill_tokens(self):
        """Refill tokens to max_requests"""
        self.current_tokens = self.max_requests
        self.last_refill = timezone.now()
        self.save(update_fields=['current_tokens', 'last_refill'])

    def get_utilization(self):
        """Get utilization percentage (how many tokens used)"""
        if self.max_requests == 0:
            return 100.0
        used = self.max_requests - self.current_tokens
        return round((used / self.max_requests) * 100, 2)

    def reset(self):
        """Reset the rate limit state"""
        self.current_tokens = self.max_requests
        self.total_requests = 0
        self.rejected_requests = 0
        self.save(update_fields=['current_tokens', 'total_requests', 'rejected_requests'])
        from api.alerts.signals.channel import rate_limit_reset
        rate_limit_reset.send(sender=self.__class__, instance=self)

    def get_limit_type_display(self):
        choices = {
            'fixed': 'Fixed Window', 'sliding': 'Sliding Window',
            'token_bucket': 'Token Bucket', 'leaky_bucket': 'Leaky Bucket',
            'per_minute': 'Per Minute', 'per_hour': 'Per Hour', 'per_day': 'Per Day',
        }
        return choices.get(getattr(self, 'limit_type', 'sliding'), 'Sliding Window')


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

    # Notification counters (reset daily/hourly)
    notifications_sent_today = models.IntegerField(default=0)
    notifications_sent_this_hour = models.IntegerField(default=0)
    last_notification_at = models.DateTimeField(null=True, blank=True)
    
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
        return f"AlertRecipient: {self.name} - {self.recipient_type}"
    
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
            models.Index(fields=['recipient_type', 'is_active']),
            models.Index(fields=['priority']),
        ]
        db_table_comment = "Management of alert recipients"
        verbose_name = "Alert Recipient"
        verbose_name_plural = "Alert Recipients"

    def increment_notification_count(self):
        """Increment total notification count"""
        self.notification_count = (getattr(self, 'notification_count', 0) or 0) + 1
        self.save()

    def reset_counters(self):
        """Reset notification counters"""
        self.notification_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.save()

    def get_recipient_type_display(self):
        choices = {'user':'User','group':'Group','team':'Team','service':'Service','external':'External'}
        return choices.get(getattr(self,'recipient_type','user'), 'User')

