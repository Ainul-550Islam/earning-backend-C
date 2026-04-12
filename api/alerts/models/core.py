"""
Alert Core Models
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
import zoneinfo  # Python 3.9+ standard library, better than pytz
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.db.models import Q
from django.db.models import Prefetch, Count, Avg, Max, Min, Sum, F
from django.db.models.functions import TruncDate, TruncHour
from django.contrib.postgres.indexes import GinIndex, BrinIndex  # If using PostgreSQL


# ==================== CUSTOM QUERYSETS & MANAGERS ====================

class AlertRuleQuerySet(models.QuerySet):
    """Custom QuerySet for AlertRule with optimized queries"""
    
    def active(self):
        """Get active rules only"""
        return self.filter(is_active=True)
    
    def high_severity(self):
        """Get high and critical severity rules"""
        return self.filter(severity__in=['high', 'critical'])
    
    def needs_attention(self):
        """Get rules that haven't triggered recently but should be monitored"""
        return self.filter(
            is_active=True,
            last_triggered__lt=timezone.now() - timedelta(hours=24)
        )
    
    def by_type(self, alert_type):
        """Get rules by alert type"""
        return self.filter(alert_type=alert_type)
    
    def with_recent_alerts(self, hours=24):
        """Prefetch recent alerts to avoid N+1 queries"""
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.prefetch_related(
            Prefetch(
                'logs',
                queryset=AlertLog.objects.filter(
                    triggered_at__gte=cutoff
                ).order_by('-triggered_at')[:10],
                to_attr='recent_alerts'
            )
        )
    
    def bulk_update_status(self, is_active=True):
        """Bulk update rule status"""
        return self.update(is_active=is_active)


class ActiveAlertRuleManager(models.Manager):
    """Manager for active alert rules with caching"""
    
    def get_queryset(self):
        return AlertRuleQuerySet(self.model, using=self._db).filter(is_active=True)
    
    def get_cached_active_rules(self):
        """Get active rules with caching"""
        cache_key = f'active_alert_rules_{self.model.__name__}'
        rules = cache.get(cache_key)
        
        if not rules:
            rules = list(self.get_queryset().select_related(
                'created_by'
            ).prefetch_related(
                'schedules',
                'escalations',
                'suppressions'
            ))
            cache.set(cache_key, rules, timeout=300)  # 5 minutes cache
        return rules
    
    def clear_cache(self):
        """Clear active rules cache"""
        cache_key = f'active_alert_rules_{self.model.__name__}'
        cache.delete(cache_key)


class AlertLogQuerySet(models.QuerySet):
    """Custom QuerySet for AlertLog"""
    
    def unresolved(self):
        """Get unresolved alerts"""
        return self.filter(is_resolved=False)
    
    def resolved(self):
        """Get resolved alerts"""
        return self.filter(is_resolved=True)
    
    def by_severity(self, severity):
        """Get alerts by rule severity"""
        return self.filter(rule__severity=severity)
    
    def recent(self, hours=24):
        """Get recent alerts"""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(triggered_at__gte=cutoff)
    
    def needs_escalation(self):
        """Get alerts that need escalation"""
        return self.filter(
            is_resolved=False,
            triggered_at__lt=timezone.now() - timedelta(minutes=30)
        )
    
    def with_performance_data(self):
        """Include performance metrics"""
        return self.select_related('rule').annotate(
            time_since_trigger=models.ExpressionWrapper(
                timezone.now() - F('triggered_at'),
                output_field=models.DurationField()
            )
        )
    
    def bulk_resolve(self, resolved_by=None, note=""):
        """Bulk resolve alerts"""
        return self.update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=resolved_by,
            resolution_note=note
        )


class ResolvedAlertManager(models.Manager):
    """Manager for resolved alerts"""
    
    def get_queryset(self):
        return AlertLogQuerySet(self.model, using=self._db).filter(is_resolved=True)


class UnresolvedAlertManager(models.Manager):
    """Manager for unresolved alerts"""
    
    def get_queryset(self):
        return AlertLogQuerySet(self.model, using=self._db).filter(is_resolved=False)


# ==================== HELPER FUNCTIONS ====================

def _safe_serialize(value):
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'pk'):
        return value.pk
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(i) for i in value]
    if isinstance(value, dict):
        return {k: _safe_serialize(v) for k, v in value.items()}
    try:
        import json
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def validate_phone_number(value):
    """Validate phone number format"""
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', value)
    
    # Check for valid length (adjust based on your country)
    if len(digits) < 10 or len(digits) > 15:
        raise ValidationError(_('Invalid phone number length'))
    
    # Add more specific validation as needed
    return True


def sanitize_email_list(email_string):
    """Sanitize and validate email list"""
    if not email_string:
        return []
    
    emails = []
    for email in email_string.split(','):
        email = email.strip()
        if email:
            validate_email(email)
            emails.append(email.lower())  # Normalize to lowercase
    return emails


def sanitize_phone_list(phone_string):
    """Sanitize and validate phone number list"""
    if not phone_string:
        return []
    
    phones = []
    for phone in phone_string.split(','):
        phone = phone.strip()
        if phone:
            validate_phone_number(phone)
            # Normalize phone format
            normalized = re.sub(r'\D', '', phone)
            phones.append(normalized)
    return phones


# ==================== MAIN ALERT MODELS ====================

class AlertRule(models.Model):
    """Admin-configurable alert rules"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ALERT_TYPES = [
        ('high_earning', 'High Earning Activity'),
        ('mass_signup', 'Mass User Signup'),
        ('payment_spike', 'Payment Request Spike'),
        ('fraud_spike', 'Fraud Indicator Spike'),
        ('server_error', 'Server Error Rate'),
        ('low_balance', 'Low Advertiser Balance'),
    ]
    
    SEVERITY = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY, default='medium')
    description = models.TextField(blank=True)
    
    # Threshold configuration
    threshold_value = models.FloatField(
        help_text="Trigger value",
        validators=[MinValueValidator(0)]
    )
    time_window_minutes = models.IntegerField(
        default=60,
        help_text="Time window in minutes (1-1440)",
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    
    # Alert channels
    send_email = models.BooleanField(default=True)
    send_telegram = models.BooleanField(default=False)
    send_sms = models.BooleanField(default=False)
    send_webhook = models.BooleanField(default=False)
    webhook_url = models.URLField(blank=True, max_length=500)
    
    # Recipients with validation
    email_recipients = models.TextField(
        help_text="Comma-separated emails",
        blank=True
    )
    telegram_chat_id = models.CharField(max_length=100, blank=True)
    sms_recipients = models.TextField(
        blank=True, 
        help_text="Comma-separated phone numbers with country code"
    )
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    cooldown_minutes = models.IntegerField(
        default=30, 
        help_text="Minimum time between alerts (minutes)",
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    
    # Performance tracking
    trigger_count = models.IntegerField(default=0, help_text="Total times triggered")
    avg_processing_time = models.FloatField(default=0, help_text="Average processing time in ms")
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertrule_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom managers
    objects = AlertRuleQuerySet.as_manager()
    active = ActiveAlertRuleManager()
    
    def __str__(self):
        return f"{self.name} ({self.get_severity_display()})"
    
    def clean(self):
        """Validate model data"""
        super().clean()
        
        # Validate email recipients
        if self.email_recipients:
            sanitize_email_list(self.email_recipients)
        
        # Validate SMS recipients
        if self.sms_recipients:
            sanitize_phone_list(self.sms_recipients)
        
        # Validate webhook URL if enabled
        if self.send_webhook and not self.webhook_url:
            raise ValidationError("Webhook URL is required when webhook notifications are enabled")
        
        # Business logic validation
        if self.cooldown_minutes >= self.time_window_minutes:
            raise ValidationError("Cooldown minutes must be less than time window minutes")
        
        # Alert type specific validations
        if self.alert_type == 'server_error' and self.threshold_value > 100:
            raise ValidationError("Error rate cannot exceed 100%")
    
    def save(self, *args, **kwargs):
        """Clear cache on save"""
        self.full_clean()
        super().save(*args, **kwargs)
        # self.active.clear_cache()  # disabled - causes manager error
    
    def can_trigger_now(self):
        """Check if alert can be triggered (respect cooldown)"""
        if not self.last_triggered:
            return True
        
        if not self.cooldown_minutes:
            return True
        
        cooldown_time = timezone.now() - timedelta(minutes=self.cooldown_minutes)
        return self.last_triggered < cooldown_time
    
    def get_recipients(self):
        """Get sanitized recipients lists"""
        return {
            'emails': sanitize_email_list(self.email_recipients),
            'telegram': self.telegram_chat_id,
            'sms': sanitize_phone_list(self.sms_recipients)
        }
    
    def trigger_count_today(self):
        """Get number of times triggered today - optimized with cache"""
        today = timezone.now().date()
        cache_key = f'rule_{self.id}_trigger_count_{today}'
        
        count = cache.get(cache_key)
        if count is None:
            count = self.logs.filter(triggered_at__date=today).count()
            cache.set(cache_key, count, timeout=300)  # 5 minutes cache
        return count
    
    def update_processing_time(self, processing_time_ms):
        """Update average processing time"""
        total_time = (self.avg_processing_time * self.trigger_count) + processing_time_ms
        self.trigger_count += 1
        self.avg_processing_time = total_time / self.trigger_count
        self.save(update_fields=['trigger_count', 'avg_processing_time'])
    
    class Meta:
        ordering = ['-severity', 'name']
        indexes = [
            models.Index(fields=['is_active', 'alert_type']),
            models.Index(fields=['severity', 'last_triggered']),
            models.Index(fields=['created_at']),
            GinIndex(fields=['name'], name='rule_name_gin_idx'),  # For PostgreSQL
        ]
        db_table_comment = "Stores alert rules configuration and thresholds"
        verbose_name = "Alert Rule"
        verbose_name_plural = "Alert Rules"


class AlertLog(models.Model):
    """Log of triggered alerts"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    rule = models.ForeignKey(
        AlertRule, 
        on_delete=models.CASCADE, 
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True
    )
    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Alert details
    trigger_value = models.FloatField()
    threshold_value = models.FloatField()
    message = models.TextField()
    details = models.JSONField(default=dict)
    
    # Performance tracking
    processing_started = models.DateTimeField(null=True, blank=True)
    processing_time_ms = models.FloatField(default=0, help_text="Time to process alert in ms")
    
    # Actions taken
    email_sent = models.BooleanField(default=False)
    telegram_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    webhook_sent = models.BooleanField(default=False)
    
    email_sent_at = models.DateTimeField(null=True, blank=True)
    telegram_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    webhook_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_alertlog_resolved_by'
    )
    resolution_note = models.TextField(blank=True)
    
    # Escalation tracking
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_level = models.IntegerField(default=0)
    
    # Custom managers
    objects = AlertLogQuerySet.as_manager()
    resolved = ResolvedAlertManager()
    unresolved = UnresolvedAlertManager()
    
    def __str__(self):
        return f"Alert: {self.rule.name} at {self.triggered_at.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Update rule's last_triggered when alert is logged"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Update rule's last_triggered timestamp
            AlertRule.objects.filter(id=self.rule_id).update(
                last_triggered=self.triggered_at
            )
    
    @property
    def time_to_resolve(self):
        """Calculate time taken to resolve"""
        if self.is_resolved and self.resolved_at:
            return (self.resolved_at - self.triggered_at).total_seconds() / 60
        return None
    
    @property
    def age_in_minutes(self):
        """Get age of alert in minutes"""
        return (timezone.now() - self.triggered_at).total_seconds() / 60
    
    def mark_as_processing(self):
        """Mark start of processing for performance tracking"""
        self.processing_started = timezone.now()
        self.save(update_fields=['processing_started'])
    
    def mark_as_complete(self):
        """Mark end of processing and update performance metrics"""
        if self.processing_started:
            self.processing_time_ms = (
                timezone.now() - self.processing_started
            ).total_seconds() * 1000
            self.save(update_fields=['processing_time_ms'])
            
            # Update rule's average processing time
            self.rule.update_processing_time(self.processing_time_ms)
    
    def mark_as_sent(self, channel, message_id=None):
        """Mark notification as sent for specific channel"""
        if channel == 'email':
            self.email_sent = True
            self.email_sent_at = timezone.now()
        elif channel == 'telegram':
            self.telegram_sent = True
            self.telegram_sent_at = timezone.now()
        elif channel == 'sms':
            self.sms_sent = True
            self.sms_sent_at = timezone.now()
        elif channel == 'webhook':
            self.webhook_sent = True
            self.webhook_sent_at = timezone.now()
        
        update_fields = [
            f'{channel}_sent',
            f'{channel}_sent_at'
        ]
        self.save(update_fields=update_fields)
    
    def needs_escalation(self, escalation_level=1):
        """Check if alert needs escalation"""
        escalation_time = self.triggered_at + timedelta(minutes=30 * escalation_level)
        return timezone.now() >= escalation_time and not self.is_resolved
    
    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['triggered_at']),
            models.Index(fields=['is_resolved', 'triggered_at']),
            models.Index(fields=['rule', 'triggered_at']),
            BrinIndex(fields=['triggered_at'], name='triggered_at_brin_idx'),  # For PostgreSQL time series
            GinIndex(fields=['details'], name='details_gin_idx'),  # For JSON queries
        ]
        db_table_comment = "Logs all triggered alerts with resolution tracking"
        verbose_name = "Alert Log"
        verbose_name_plural = "Alert Logs"


# ==================== SYSTEM 1: NOTIFICATION TRACKING ====================

class Notification(models.Model):
    """Track all notifications sent"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('telegram', 'Telegram'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('webhook', 'Webhook'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    ]
    
    alert_log = models.ForeignKey(
        AlertLog, 
        on_delete=models.CASCADE, 
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    recipient = models.CharField(max_length=255, db_index=True)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    message_id = models.CharField(max_length=255, blank=True, help_text="Provider message ID")
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    max_retries = models.IntegerField(default=3)
    
    # Cost tracking (for paid notifications)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Performance metrics
    response_time_ms = models.FloatField(default=0, help_text="Response time from provider")
    
    def __str__(self):
        return f"{self.get_notification_type_display()} to {self.recipient[:20]} ({self.status})"
    
    @property
    def delivery_time_seconds(self):
        """Calculate delivery time"""
        if self.sent_at and self.delivered_at:
            return (self.delivered_at - self.sent_at).total_seconds()
        return None
    
    def mark_as_sent(self, message_id='', response_time_ms=0):
        """Mark notification as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.response_time_ms = response_time_ms
        if message_id:
            self.message_id = message_id
        self.save(update_fields=['status', 'sent_at', 'message_id', 'response_time_ms'])
    
    def mark_as_failed(self, error_msg):
        """Mark notification as failed"""
        self.status = 'failed'
        self.error_message = str(error_msg)[:500]  # Limit error message length
        self.retry_count += 1
        self.last_retry_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'retry_count', 'last_retry_at'])
    
    def can_retry(self):
        """Check if notification can be retried"""
        return self.status == 'failed' and self.retry_count < self.max_retries
    
    def get_retry_delay(self):
        """Calculate retry delay in seconds (exponential backoff)"""
        if self.retry_count == 0:
            return 60  # 1 minute
        elif self.retry_count == 1:
            return 300  # 5 minutes
        else:
            return 900  # 15 minutes
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['alert_log', 'created_at']),
            models.Index(fields=['recipient', 'created_at']),
        ]
        db_table_comment = "Tracks all notification attempts and their status"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"


# ==================== SYSTEM 2: ALERT SCHEDULE ====================

def get_default_days_of_week():
    return [0, 1, 2, 3, 4]

class AlertSchedule(models.Model):
    """Schedule for when alerts should be active"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    rule = models.ForeignKey(
        AlertRule, 
        on_delete=models.CASCADE, 
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Schedule timing
    start_time = models.TimeField()
    end_time = models.TimeField()
    days_of_week = models.JSONField(
        default=get_default_days_of_week,
        help_text="List of days (0=Monday)"
    )
    
    # Timezone handling with zoneinfo
    TIMEZONE_CHOICES = [
        ('UTC', 'UTC'),
        ('America/New_York', 'New York'),
        ('Europe/London', 'London'),
        ('Asia/Dhaka', 'Dhaka'),
        ('Asia/Kolkata', 'Kolkata'),
        ('Asia/Singapore', 'Singapore'),
        ('Australia/Sydney', 'Sydney'),
    ]
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(default=1, help_text="Higher number = higher priority")
    
    # Override settings
    override_recipients = models.BooleanField(default=False)
    override_email_recipients = models.TextField(blank=True)
    override_telegram_chat_id = models.CharField(max_length=100, blank=True)
    override_sms_recipients = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Schedule: {self.name} for {self.rule.name}"
    
    def clean(self):
        """Validate schedule data"""
        super().clean()
        
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")
        
        if self.override_recipients and self.override_email_recipients:
            sanitize_email_list(self.override_email_recipients)
        
        if self.override_recipients and self.override_sms_recipients:
            sanitize_phone_list(self.override_sms_recipients)
    
    def is_active_now(self):
        """Check if schedule is active at current moment"""
        if not self.is_active:
            return False
        
        # Get current time in schedule's timezone
        try:
            tz = zoneinfo.ZoneInfo(self.timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo('UTC')
        
        now = timezone.now().astimezone(tz)
        
        # Check day of week
        if now.weekday() not in self.days_of_week:
            return False
        
        # Check time
        current_time = now.time()
        return self.start_time <= current_time <= self.end_time
    
    def get_active_period_today(self):
        """Get active period for today"""
        try:
            tz = zoneinfo.ZoneInfo(self.timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo('UTC')
        
        now = timezone.now().astimezone(tz)
        
        if now.weekday() in self.days_of_week:
            return {
                'start': self.start_time,
                'end': self.end_time,
                'is_now': self.is_active_now(),
                'timezone': self.timezone
            }
        return None
    
    def get_recipients_for_schedule(self):
        """Get recipients based on schedule settings"""
        if self.override_recipients:
            return {
                'emails': sanitize_email_list(self.override_email_recipients),
                'telegram': self.override_telegram_chat_id,
                'sms': sanitize_phone_list(self.override_sms_recipients)
            }
        
        return self.rule.get_recipients()
    
    @classmethod
    def get_active_schedules(cls):
        """Get all currently active schedules"""
        now = timezone.now()
        schedules = []
        
        for schedule in cls.objects.filter(is_active=True).select_related('rule'):
            if schedule.is_active_now():
                schedules.append(schedule)
        
        return schedules
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['rule', 'is_active']),
            models.Index(fields=['is_active', 'timezone']),
            models.Index(fields=['is_active', 'days_of_week']),
        ]
        db_table_comment = "Defines when alert rules should be active based on schedule"
        verbose_name = "Alert Schedule"
        verbose_name_plural = "Alert Schedules"


# ==================== SYSTEM 3: ALERT ESCALATION ====================

class AlertEscalation(models.Model):
    """Escalation rules for unresolved alerts"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    rule = models.ForeignKey(
        AlertRule, 
        on_delete=models.CASCADE, 
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Escalation timing
    level = models.IntegerField(default=1)
    delay_minutes = models.IntegerField(
        default=60,
        help_text="Minutes after trigger before escalating",
        validators=[MinValueValidator(5)]
    )
    
    # Escalation recipients
    escalate_to_email = models.TextField(
        blank=True,
        help_text="Comma-separated emails for escalation"
    )
    escalate_to_telegram = models.CharField(max_length=100, blank=True)
    escalate_to_sms = models.TextField(blank=True)
    escalate_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_alertescalation_escalate_to_user'
    )
    
    # Message customization
    message_template = models.TextField(
        default="Alert #{alert_id} for rule '{rule_name}' has not been resolved after {delay} minutes.\n"
                "Trigger Value: {trigger_value}\n"
                "Threshold: {threshold_value}\n"
                "Severity: {severity}\n"
                "Triggered At: {triggered_at}",
        help_text="Available variables: {alert_id}, {rule_name}, {triggered_at}, {delay}, "
                  "{trigger_value}, {threshold_value}, {severity}, {age_minutes}"
    )
    
    # Settings
    is_active = models.BooleanField(default=True, db_index=True)
    require_acknowledgment = models.BooleanField(default=False)
    auto_escalate = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Escalation L{self.level}: {self.name}"
    
    def clean(self):
        """Validate escalation data"""
        super().clean()
        
        if self.escalate_to_email:
            sanitize_email_list(self.escalate_to_email)
        
        if self.escalate_to_sms:
            sanitize_phone_list(self.escalate_to_sms)
    
    def should_escalate(self, alert_log):
        """Check if alert should be escalated"""
        if not self.is_active or not self.auto_escalate:
            return False
        
        if alert_log.is_resolved:
            return False
        
        # Check if already escalated to this level
        if alert_log.escalation_level >= self.level:
            return False
        
        time_since_trigger = (timezone.now() - alert_log.triggered_at).total_seconds() / 60
        return time_since_trigger >= self.delay_minutes
    
    def get_escalation_recipients(self):
        """Get all escalation recipients"""
        recipients = {
            'emails': [],
            'telegram': '',
            'sms': [],
            'users': []
        }
        
        if self.escalate_to_email:
            recipients['emails'] = sanitize_email_list(self.escalate_to_email)
        
        if self.escalate_to_telegram:
            recipients['telegram'] = self.escalate_to_telegram
        
        if self.escalate_to_sms:
            recipients['sms'] = sanitize_phone_list(self.escalate_to_sms)
        
        if self.escalate_to_user:
            recipients['users'].append(self.escalate_to_user)
        
        return recipients
    
    def render_escalation_message(self, alert_log):
        """Render escalation message with context"""
        context = {
            'alert_id': alert_log.id,
            'rule_name': alert_log.rule.name,
            'triggered_at': alert_log.triggered_at.strftime('%Y-%m-%d %H:%M'),
            'delay': self.delay_minutes,
            'trigger_value': alert_log.trigger_value,
            'threshold_value': alert_log.threshold_value,
            'severity': alert_log.rule.get_severity_display(),
            'age_minutes': round(alert_log.age_in_minutes, 1),
        }
        
        message = self.message_template
        for key, value in context.items():
            placeholder = f'{{{key}}}'
            message = message.replace(placeholder, str(value))
        
        return message
    
    def escalate_alert(self, alert_log):
        """Execute escalation for alert"""
        if not self.should_escalate(alert_log):
            return False
        
        # Update alert escalation level
        alert_log.escalation_level = self.level
        alert_log.escalated_at = timezone.now()
        alert_log.save(update_fields=['escalation_level', 'escalated_at'])
        
        return True
    
    class Meta:
        ordering = ['rule', 'level']
        unique_together = ['rule', 'level']
        indexes = [
            models.Index(fields=['is_active', 'level']),
        ]
        db_table_comment = "Defines escalation rules for unresolved alerts"
        verbose_name = "Alert Escalation"
        verbose_name_plural = "Alert Escalations"


# ==================== SYSTEM 4: ALERT TEMPLATE ====================

def get_default_available_variables():
    return [
        'rule_name', 'alert_type', 'severity',
        'trigger_value', 'threshold_value', 'triggered_at',
        'message', 'details', 'system_metrics',
        'current_time', 'alert_id'
    ]

class AlertTemplate(models.Model):
    """Templates for alert messages"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    name = models.CharField(max_length=100, unique=True, db_index=True)
    alert_type = models.CharField(max_length=50, choices=AlertRule.ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=AlertRule.SEVERITY)
    description = models.TextField(blank=True)
    
    # Templates for different channels
    email_subject = models.CharField(max_length=200)
    email_body = models.TextField()
    telegram_message = models.TextField()
    sms_message = models.CharField(max_length=160, help_text="Max 160 characters for SMS")
    push_title = models.CharField(max_length=100, blank=True)
    push_body = models.TextField(blank=True)
    webhook_payload = models.JSONField(default=dict, blank=True)
    
    # Template variables
    available_variables = models.JSONField(
        default=get_default_available_variables
    )
    
    # Settings
    is_default = models.BooleanField(default=False)
    language = models.CharField(max_length=10, default='en', choices=[
        ('en', 'English'),
        ('bn', 'Bengali'),
        ('es', 'Spanish'),
        ('fr', 'French'),
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alerttemplate_created_by'
    )
    
    def __str__(self):
        return f"{self.name} ({self.get_severity_display()})"
    
    def clean(self):
        """Validate template data"""
        super().clean()
        
        # Validate SMS length
        if len(self.sms_message) > 160:
            raise ValidationError("SMS message cannot exceed 160 characters")
    
    def render_message(self, channel, context):
        """Render template with context for specific channel"""
        templates = {
            'email': {'subject': self.email_subject, 'body': self.email_body},
            'telegram': self.telegram_message,
            'sms': self.sms_message,
            'push': {'title': self.push_title, 'body': self.push_body},
            'webhook': self.webhook_payload,
        }
        
        if channel not in templates:
            raise ValueError(f"Unsupported channel: {channel}")
        
        template = templates[channel]
        context['current_time'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if isinstance(template, dict):
            rendered = {}
            for key, value in template.items():
                if value:
                    rendered[key] = self._render_text(value, context)
            return rendered
        else:
            return self._render_text(template, context)
    
    def _render_text(self, text, context):
        """Render text with context variables"""
        for key, value in context.items():
            placeholder = f'{{{key}}}'
            if placeholder in text:
                text = text.replace(placeholder, str(value))
        return text
    
    def save(self, *args, **kwargs):
        """Ensure only one default template per alert_type and severity"""
        if self.is_default:
            # Remove default flag from other templates with same alert_type and severity
            AlertTemplate.objects.filter(
                alert_type=self.alert_type,
                severity=self.severity,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_template_for_alert(cls, alert_log):
        """Get appropriate template for alert"""
        template = cls.objects.filter(
            alert_type=alert_log.rule.alert_type,
            severity=alert_log.rule.severity,
            is_default=True
        ).first()
        
        if not template:
            template = cls.objects.filter(
                alert_type=alert_log.rule.alert_type,
                is_default=True
            ).first()
        
        return template
    
    class Meta:
        ordering = ['alert_type', 'severity', 'name']
        indexes = [
            models.Index(fields=['alert_type', 'severity']),
            models.Index(fields=['is_default', 'language']),
            models.Index(fields=['alert_type', 'is_default']),
        ]
        db_table_comment = "Templates for alert messages across different channels"
        verbose_name = "Alert Template"
        verbose_name_plural = "Alert Templates"


# ==================== SYSTEM 5: ALERT ANALYTICS ====================

class AlertAnalytics(models.Model):
    """Daily analytics for alerts"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    date = models.DateField(unique=True, db_index=True)
    
    # Count metrics
    total_alerts = models.IntegerField(default=0)
    resolved_alerts = models.IntegerField(default=0)
    unresolved_alerts = models.IntegerField(default=0)
    escalated_alerts = models.IntegerField(default=0)
    false_positives = models.IntegerField(default=0)
    acknowledged_alerts = models.IntegerField(default=0)
    
    # Time metrics (in minutes)
    avg_response_time_min = models.FloatField(default=0)
    avg_resolution_time_min = models.FloatField(default=0)
    max_response_time_min = models.FloatField(default=0)
    min_response_time_min = models.FloatField(default=0)
    p95_response_time_min = models.FloatField(default=0)  # 95th percentile
    
    # Notification metrics
    notifications_sent = models.IntegerField(default=0)
    emails_sent = models.IntegerField(default=0)
    telegrams_sent = models.IntegerField(default=0)
    sms_sent = models.IntegerField(default=0)
    webhooks_sent = models.IntegerField(default=0)
    notifications_failed = models.IntegerField(default=0)
    notification_success_rate = models.FloatField(default=0)
    avg_notification_delay_ms = models.FloatField(default=0)
    
    # Cost metrics
    estimated_sms_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_email_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_notification_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Performance metrics
    system_uptime_percent = models.FloatField(default=100)
    alert_accuracy_percent = models.FloatField(default=0)
    avg_processing_time_ms = models.FloatField(default=0)
    
    # Severity distribution
    critical_alerts = models.IntegerField(default=0)
    high_alerts = models.IntegerField(default=0)
    medium_alerts = models.IntegerField(default=0)
    low_alerts = models.IntegerField(default=0)
    
    # Alert type distribution
    alerts_by_type = models.JSONField(default=dict)
    
    # Calculated metrics
    resolution_rate = models.FloatField(default=0)
    false_positive_rate = models.FloatField(default=0)
    escalation_rate = models.FloatField(default=0)
    avg_alerts_per_hour = models.FloatField(default=0)
    
    generated_at = models.DateTimeField(auto_now_add=True)
    generation_duration_ms = models.FloatField(default=0)
    is_complete = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Analytics for {self.date}"
    
    def calculate_metrics(self):
        """Calculate derived metrics"""
        # Calculate rates
        if self.total_alerts > 0:
            self.resolution_rate = (self.resolved_alerts / self.total_alerts) * 100
            self.false_positive_rate = (self.false_positives / self.total_alerts) * 100
            self.escalation_rate = (self.escalated_alerts / self.total_alerts) * 100
        
        # Calculate notification success rate
        if self.notifications_sent > 0:
            self.notification_success_rate = (
                (self.notifications_sent - self.notifications_failed) / 
                self.notifications_sent * 100
            )
        
        # Calculate total cost
        self.total_notification_cost = (
            self.estimated_sms_cost + 
            self.estimated_email_cost
        )
        
        # Calculate average alerts per hour
        self.avg_alerts_per_hour = self.total_alerts / 24 if self.total_alerts > 0 else 0
    
    def save(self, *args, **kwargs):
        self.calculate_metrics()
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_for_date(cls, date, force_regenerate=False):
        """Generate analytics for a specific date"""
        from django.db.models import Count, Avg, Max, Min, Sum  # Fixed: Removed StdDev, Percentile (not in Django ORM)
        
        # Check if already generated
        if not force_regenerate:
            existing = cls.objects.filter(date=date).first()
            if existing and existing.is_complete:
                return existing
        
        import time
        start_time = time.time()
        
        # Get data for the date
        alerts = AlertLog.objects.filter(
            triggered_at__date=date
        ).select_related('rule')
        
        notifications = Notification.objects.filter(
            created_at__date=date
        )
        
        # Calculate basic metrics
        total_alerts = alerts.count()
        resolved_alerts = alerts.filter(is_resolved=True).count()
        unresolved_alerts = total_alerts - resolved_alerts
        
        # Calculate severity distribution
        severity_counts = alerts.values('rule__severity').annotate(count=Count('id'))
        severity_dist = {s['rule__severity']: s['count'] for s in severity_counts}
        
        # Calculate alert type distribution
        type_counts = alerts.values('rule__alert_type').annotate(count=Count('id'))
        type_dist = {t['rule__alert_type']: t['count'] for t in type_counts}
        
        # Calculate time metrics
        time_metrics = alerts.aggregate(
            avg_resolution=Avg(F('resolved_at') - F('triggered_at')),
            max_resolution=Max(F('resolved_at') - F('triggered_at')),
            min_resolution=Min(F('resolved_at') - F('triggered_at')),
        )
        
        # Calculate notification metrics
        notification_metrics = notifications.aggregate(
            total_sent=Count('id'),
            failed=Count('id', filter=Q(status='failed')),
            emails=Count('id', filter=Q(notification_type='email')),
            telegrams=Count('id', filter=Q(notification_type='telegram')),
            sms=Count('id', filter=Q(notification_type='sms')),
            webhooks=Count('id', filter=Q(notification_type='webhook')),
        )
        
        # Create analytics object
        analytics = cls.objects.create(
            date=date,
            total_alerts=total_alerts,
            resolved_alerts=resolved_alerts,
            unresolved_alerts=unresolved_alerts,
            false_positives=alerts.filter(details__contains={'false_positive': True}).count(),
            escalated_alerts=alerts.filter(escalation_level__gt=0).count(),
            acknowledged_alerts=alerts.filter(details__contains={'acknowledged': True}).count(),
            critical_alerts=severity_dist.get('critical', 0),
            high_alerts=severity_dist.get('high', 0),
            medium_alerts=severity_dist.get('medium', 0),
            low_alerts=severity_dist.get('low', 0),
            alerts_by_type=type_dist,
            notifications_sent=notification_metrics['total_sent'] or 0,
            notifications_failed=notification_metrics['failed'] or 0,
            emails_sent=notification_metrics['emails'] or 0,
            telegrams_sent=notification_metrics['telegrams'] or 0,
            sms_sent=notification_metrics['sms'] or 0,
            webhooks_sent=notification_metrics['webhooks'] or 0,
            avg_resolution_time_min=time_metrics['avg_resolution'].total_seconds() / 60 
                if time_metrics['avg_resolution'] else 0,
            max_response_time_min=time_metrics['max_resolution'].total_seconds() / 60 
                if time_metrics['max_resolution'] else 0,
            min_response_time_min=time_metrics['min_resolution'].total_seconds() / 60 
                if time_metrics['min_resolution'] else 0,
            is_complete=True,
            generation_duration_ms=(time.time() - start_time) * 1000
        )
        
        return analytics
    
    @classmethod
    def get_latest_analytics(cls, days=7):
        """Get latest analytics"""
        return cls.objects.filter(
            is_complete=True
        ).order_by('-date')[:days]
    
    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['resolution_rate']),
            models.Index(fields=['total_notification_cost']),
            models.Index(fields=['total_alerts', 'date']),
        ]
        db_table_comment = "Daily aggregated analytics for alert system performance"
        verbose_name = "Alert Analytics"
        verbose_name_plural = "Alert Analytics"


# ==================== SYSTEM 6: ALERT GROUP ====================

class AlertGroup(models.Model):
    """Group related alert rules together"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    rules = models.ManyToManyField(
        AlertRule, 
        related_name='%(app_label)s_%(class)s_tenant', 
        blank=True,
        db_index=True
    )
    
    # Group settings
    group_notification_enabled = models.BooleanField(default=False)
    group_threshold = models.IntegerField(
        default=3,
        help_text="Minimum number of alerts to trigger group notification",
        validators=[MinValueValidator(1)]
    )
    cooldown_minutes = models.IntegerField(default=60, validators=[MinValueValidator(1)])
    
    # Group recipients (overrides individual rule recipients)
    group_email_recipients = models.TextField(blank=True)
    group_telegram_chat_id = models.CharField(max_length=100, blank=True)
    group_sms_recipients = models.TextField(blank=True)
    
    # Group message template
    group_message_template = models.TextField(
        default="Multiple alerts triggered in group '{group_name}'\n"
                "[STATS] Total alerts: {alert_count}\n"
                "Critical: {critical_count}\n"
                "High: {high_count}\n"
                "Medium: {medium_count}\n"
                "Low: {low_count}\n"
                "Rules: {rules_list}",
        help_text="Available variables: {group_name}, {alert_count}, {rules_list}, "
                  "{critical_count}, {high_count}, {medium_count}, {low_count}, "
                  "{unresolved_count}, {total_rules}"
    )
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    last_group_alert_at = models.DateTimeField(null=True, blank=True)
    
    # Cache for performance
    cached_alert_count = models.IntegerField(default=0)
    cache_updated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertgroup_created_by'
    )
    
    def __str__(self):
        return f"Group: {self.name}"
    
    def clean(self):
        """Validate group data"""
        super().clean()
        
        if self.group_email_recipients:
            sanitize_email_list(self.group_email_recipients)
        
        if self.group_sms_recipients:
            sanitize_phone_list(self.group_sms_recipients)
    
    def get_active_alerts(self, use_cache=True, cache_timeout=300):
        """Get all active/unresolved alerts in this group - optimized with cache"""
        if use_cache and self.cache_updated_at:
            cache_age = (timezone.now() - self.cache_updated_at).total_seconds()
            if cache_age < cache_timeout:
                # Return cached count if recent
                return AlertLog.objects.filter(
                    id__in=[]  # Empty queryset, we only need count from cache
                )
        
        # Get rule IDs efficiently
        rule_ids = list(self.rules.values_list('id', flat=True))
        
        if not rule_ids:
            self.cached_alert_count = 0
            self.cache_updated_at = timezone.now()
            self.save(update_fields=['cached_alert_count', 'cache_updated_at'])
            return AlertLog.objects.none()
        
        # Get active alerts
        active_alerts = AlertLog.objects.filter(
            rule_id__in=rule_ids,
            is_resolved=False,
            triggered_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        # Update cache
        self.cached_alert_count = active_alerts.count()
        self.cache_updated_at = timezone.now()
        self.save(update_fields=['cached_alert_count', 'cache_updated_at'])
        
        return active_alerts
    
    def should_send_group_alert(self):
        """Check if group alert should be sent"""
        if not self.group_notification_enabled or not self.is_active:
            return False
        
        # Check cooldown
        if self.last_group_alert_at:
            cooldown_end = self.last_group_alert_at + timedelta(minutes=self.cooldown_minutes)
            if timezone.now() < cooldown_end:
                return False
        
        active_alerts = self.get_active_alerts()
        return active_alerts.count() >= self.group_threshold
    
    def get_group_alert_context(self):
        """Get context for group alert message"""
        active_alerts = self.get_active_alerts().select_related('rule')
        
        # Count by severity
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        rule_names = set()
        
        for alert in active_alerts:
            severity_counts[alert.rule.severity] += 1
            rule_names.add(alert.rule.name)
        
        return {
            'group_name': self.name,
            'alert_count': active_alerts.count(),
            'rules_list': ', '.join(sorted(rule_names)[:10]),  # Limit to 10 rules
            'total_rules': self.rules.count(),
            'unresolved_count': active_alerts.count(),
            'critical_count': severity_counts['critical'],
            'high_count': severity_counts['high'],
            'medium_count': severity_counts['medium'],
            'low_count': severity_counts['low'],
        }
    
    def render_group_message(self):
        """Render group message with context"""
        context = self.get_group_alert_context()
        message = self.group_message_template
        
        for key, value in context.items():
            message = message.replace(f'{{{key}}}', str(value))
        
        return message
    
    def get_group_recipients(self):
        """Get recipients for group alerts - optimized"""
        if self.group_email_recipients or self.group_telegram_chat_id or self.group_sms_recipients:
            return {
                'emails': sanitize_email_list(self.group_email_recipients),
                'telegram': self.group_telegram_chat_id,
                'sms': sanitize_phone_list(self.group_sms_recipients)
            }
        
        # Fall back to individual rule recipients
        cache_key = f'group_{self.id}_recipients'
        recipients = cache.get(cache_key)
        
        if recipients is None:
            emails = set()
            telegram_ids = set()
            sms_numbers = set()
            
            # Batch fetch rules with recipients
            rules = self.rules.all().only(
                'email_recipients', 'telegram_chat_id', 'sms_recipients'
            )
            
            for rule in rules:
                if rule.email_recipients:
                    emails.update(sanitize_email_list(rule.email_recipients))
                if rule.telegram_chat_id:
                    telegram_ids.add(rule.telegram_chat_id)
                if rule.sms_recipients:
                    sms_numbers.update(sanitize_phone_list(rule.sms_recipients))
            
            recipients = {
                'emails': list(emails),
                'telegram': ', '.join(telegram_ids),
                'sms': list(sms_numbers)
            }
            
            cache.set(cache_key, recipients, timeout=300)  # 5 minutes cache
        
        return recipients
    
    def send_group_alert(self):
        """Send group alert notification"""
        if self.should_send_group_alert():
            # Update last group alert time
            self.last_group_alert_at = timezone.now()
            self.save(update_fields=['last_group_alert_at'])
            
            # Clear recipients cache
            cache_key = f'group_{self.id}_recipients'
            cache.delete(cache_key)
            
            # Return context for sending notification
            return {
                'message': self.render_group_message(),
                'recipients': self.get_group_recipients(),
                'alert_count': self.get_active_alerts().count(),
                'group_id': self.id,
                'group_name': self.name
            }
        return None
    
    def update_cache(self):
        """Force update of cached data"""
        self.get_active_alerts(use_cache=False)
        cache_key = f'group_{self.id}_recipients'
        cache.delete(cache_key)
        return True
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['group_notification_enabled']),
            models.Index(fields=['cached_alert_count']),
        ]
        db_table_comment = "Groups related alert rules for coordinated notifications"
        verbose_name = "Alert Group"
        verbose_name_plural = "Alert Groups"


# ==================== SYSTEM 7: ALERT SUPPRESSION ====================

class AlertSuppression(models.Model):
    """Temporarily suppress specific alerts"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    SUPPRESSION_TYPES = [
        ('rule', 'Specific Rule'),
        ('type', 'Alert Type'),
        ('severity', 'Severity Level'),
        ('all', 'All Alerts'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Suppression scope
    suppression_type = models.CharField(max_length=20, choices=SUPPRESSION_TYPES)
    rule = models.ForeignKey(
        AlertRule, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    alert_type = models.CharField(max_length=50, choices=AlertRule.ALERT_TYPES, blank=True)
    severity = models.CharField(max_length=20, choices=AlertRule.SEVERITY, blank=True)
    
    # Suppression window
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    
    # Channel suppression
    suppress_all_channels = models.BooleanField(default=True)
    suppress_email = models.BooleanField(default=False)
    suppress_telegram = models.BooleanField(default=False)
    suppress_sms = models.BooleanField(default=False)
    suppress_webhook = models.BooleanField(default=False)
    
    # Settings
    is_active = models.BooleanField(default=True, db_index=True)
    silent_mode = models.BooleanField(
        default=False,
        help_text="If True, alerts will be silently dropped without logging"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertsuppression_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Suppression: {self.name}"
    
    def clean(self):
        """Validate suppression data"""
        super().clean()
        
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
        
        # Validate suppression type consistency
        if self.suppression_type == 'rule' and not self.rule:
            raise ValidationError("Rule must be specified for rule-based suppression")
        
        if self.suppression_type == 'type' and not self.alert_type:
            raise ValidationError("Alert type must be specified for type-based suppression")
        
        if self.suppression_type == 'severity' and not self.severity:
            raise ValidationError("Severity must be specified for severity-based suppression")
    
    def is_active_now(self):
        """Check if suppression is currently active"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        return self.start_time <= now <= self.end_time
    
    def should_suppress_alert(self, alert_log):
        """Check if specific alert should be suppressed"""
        if not self.is_active_now():
            return False
        
        # Check based on suppression type
        if self.suppression_type == 'all':
            return True
        
        elif self.suppression_type == 'rule':
            return self.rule and alert_log.rule == self.rule
        
        elif self.suppression_type == 'type':
            return self.alert_type and alert_log.rule.alert_type == self.alert_type
        
        elif self.suppression_type == 'severity':
            return self.severity and alert_log.rule.severity == self.severity
        
        return False
    
    def should_suppress_channel(self, channel):
        """Check if specific channel should be suppressed"""
        if self.suppress_all_channels:
            return True
        
        channel_map = {
            'email': self.suppress_email,
            'telegram': self.suppress_telegram,
            'sms': self.suppress_sms,
            'webhook': self.suppress_webhook,
        }
        
        return channel_map.get(channel, False)
    
    def get_time_remaining(self):
        """Get time remaining for suppression in minutes"""
        if not self.is_active_now():
            return 0
        
        remaining = self.end_time - timezone.now()
        return max(0, remaining.total_seconds() / 60)
    
    def get_suppression_summary(self):
        """Get human-readable summary"""
        if self.suppression_type == 'all':
            return "Suppressing all alerts"
        
        elif self.suppression_type == 'rule':
            return f"Suppressing rule: {self.rule.name if self.rule else 'N/A'}"
        
        elif self.suppression_type == 'type':
            return f"Suppressing alert type: {self.get_alert_type_display()}"
        
        elif self.suppression_type == 'severity':
            return f"Suppressing severity: {self.get_severity_display()}"
        
        return "Suppression active"
    
    @classmethod
    def get_active_suppressions(cls):
        """Get all currently active suppressions"""
        now = timezone.now()
        return cls.objects.filter(
            is_active=True,
            start_time__lte=now,
            end_time__gte=now
        ).select_related('rule')
    
    @classmethod
    def should_suppress(cls, alert_log, channel=None):
        """Check if alert should be suppressed by any active suppression"""
        active_suppressions = cls.get_active_suppressions()
        
        for suppression in active_suppressions:
            if suppression.should_suppress_alert(alert_log):
                if channel is None or suppression.should_suppress_channel(channel):
                    return True
        return False
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['is_active', 'start_time', 'end_time']),
            models.Index(fields=['suppression_type']),
            models.Index(fields=['rule', 'is_active']),
        ]
        db_table_comment = "Temporarily suppresses alerts based on various criteria"
        verbose_name = "Alert Suppression"
        verbose_name_plural = "Alert Suppressions"


# ==================== SYSTEM 8: SYSTEM HEALTH CHECK ====================

class SystemHealthCheck(models.Model):
    """Periodic system health checks"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    CHECK_TYPES = [
        ('database', 'Database'),
        ('redis', 'Redis'),
        ('api', 'API'),
        ('external_service', 'External Service'),
        ('disk_space', 'Disk Space'),
        ('memory', 'Memory'),
        ('cpu', 'CPU'),
        ('network', 'Network'),
        ('queue', 'Queue'),
        ('cache', 'Cache'),
        ('celery', 'Celery Worker'),
    ]
    
    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown'),
    ]
    
    check_name = models.CharField(max_length=100, unique=True, db_index=True)
    check_type = models.CharField(max_length=50, choices=CHECK_TYPES)
    description = models.TextField(blank=True)
    
    # Check configuration
    endpoint_url = models.URLField(blank=True, null=True)
    check_interval_minutes = models.IntegerField(default=5)
    timeout_seconds = models.IntegerField(default=10)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    status_message = models.TextField(blank=True)
    response_time_ms = models.FloatField(default=0)
    error_message = models.TextField(blank=True)
    
    # Timing
    last_checked = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    next_check = models.DateTimeField(null=True, blank=True)
    
    # Alert settings
    alert_on_failure = models.BooleanField(default=True)
    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Thresholds
    warning_threshold_ms = models.FloatField(default=1000)
    critical_threshold_ms = models.FloatField(default=5000)
    
    # Metadata
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(default=1)
    
    # Performance history
    response_history = models.JSONField(
        default=list,
        help_text="Last 100 response times for trend analysis"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.check_name} ({self.get_status_display()})"
    
    @property
    def needs_checking(self):
        """Check if health check is due"""
        if not self.is_active or not self.last_checked:
            return True
        
        next_check_time = self.last_checked + timedelta(minutes=self.check_interval_minutes)
        return timezone.now() >= next_check_time
    
    @property
    def uptime_percentage(self):
        """Calculate uptime percentage based on recent history"""
        if not self.response_history:
            return 100.0
        
        # Count healthy statuses in history
        healthy_count = sum(1 for status, _ in self.response_history if status == 'healthy')
        total_count = len(self.response_history)
        
        return (healthy_count / total_count * 100) if total_count > 0 else 100.0
    
    @property
    def avg_response_time(self):
        """Calculate average response time from history"""
        if not self.response_history:
            return 0
        
        times = [rt for _, rt in self.response_history if rt > 0]
        return sum(times) / len(times) if times else 0
    
    def get_status_color(self):
        """Get color for status"""
        colors = {
            'healthy': 'success',
            'warning': 'warning',
            'critical': 'danger',
            'offline': 'dark',
            'unknown': 'secondary',
        }
        return colors.get(self.status, 'secondary')
    
    def update_response_history(self, status, response_time):
        """Update response history (keep last 100 entries)"""
        self.response_history.append([status, response_time])
        
        # Keep only last 100 entries
        if len(self.response_history) > 100:
            self.response_history = self.response_history[-100:]
    
    def update_status(self, response_time, success=True, message=''):
        """Update health check status"""
        self.last_checked = timezone.now()
        self.response_time_ms = response_time
        
        if success:
            self.last_success = timezone.now()
            
            if response_time <= self.warning_threshold_ms:
                new_status = 'healthy'
                status_msg = f"Healthy - {response_time:.0f}ms response"
            elif response_time <= self.critical_threshold_ms:
                new_status = 'warning'
                status_msg = f"Slow response - {response_time:.0f}ms"
            else:
                new_status = 'critical'
                status_msg = f"Very slow response - {response_time:.0f}ms"
            
            self.error_message = ''
        else:
            new_status = 'offline'
            status_msg = message
            self.error_message = message
        
        # Update status if changed
        if self.status != new_status:
            self.status = new_status
            self.status_message = status_msg
        
        # Update response history
        self.update_response_history(new_status, response_time)
        
        self.next_check = self.last_checked + timedelta(minutes=self.check_interval_minutes)
        self.save()
        
        # Check if alert should be triggered
        if self.should_trigger_alert():
            return True
        return False
    
    def should_trigger_alert(self):
        """Check if should trigger alert"""
        if not self.alert_on_failure or not self.alert_rule:
            return False
        
        return self.status in ['critical', 'offline']
    
    @classmethod
    def get_checks_needed(cls):
        """Get all health checks that need to be performed"""
        now = timezone.now()
        return cls.objects.filter(
            is_active=True
        ).filter(
            Q(next_check__isnull=True) | Q(next_check__lte=now)
        ).order_by('priority')
    
    @classmethod
    def get_overall_status(cls):
        """Get overall system health status"""
        checks = cls.objects.filter(is_active=True)
        
        if not checks:
            return 'unknown'
        
        # Check for any critical/offline
        if checks.filter(status__in=['critical', 'offline']).exists():
            return 'critical'
        
        # Check for any warnings
        if checks.filter(status='warning').exists():
            return 'warning'
        
        # All healthy
        if checks.filter(status='healthy').count() == checks.count():
            return 'healthy'
        
        return 'unknown'
    
    class Meta:
        ordering = ['priority', 'check_name']
        indexes = [
            models.Index(fields=['check_type', 'status']),
            models.Index(fields=['is_active', 'next_check']),
            models.Index(fields=['status', 'last_checked']),
            models.Index(fields=['priority', 'is_active']),
        ]
        db_table_comment = "Monitors system health through periodic checks"
        verbose_name = "System Health Check"
        verbose_name_plural = "System Health Checks"


# ==================== SYSTEM 9: ALERT RULE HISTORY ====================

class AlertRuleHistory(models.Model):
    """Track changes to alert rules"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('test', 'Test Trigger'),
        ('clone', 'Clone'),
    ]
    
    rule = models.ForeignKey(
        AlertRule, 
        on_delete=models.CASCADE, 
        related_name='%(app_label)s_%(class)s_tenant',
        null=True,  # Allow null for deleted rules
        blank=True
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    # Changed data
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    
    # Changed fields tracking
    changed_fields = models.JSONField(default=list)
    
    # User info
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertrulehistory_changed_by'
    )
    
    # Metadata
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # For deleted rules
    rule_name_backup = models.CharField(max_length=100, blank=True)
    rule_id_backup = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        if self.rule:
            return f"{self.get_action_display()} - {self.rule.name}"
        return f"{self.get_action_display()} - Rule #{self.rule_id_backup}"
    
    def get_changes_summary(self):
        """Get human-readable summary of changes"""
        if self.action == 'create':
            return f"Created rule '{self.rule.name if self.rule else self.rule_name_backup}'"
        
        elif self.action == 'update':
            if self.changed_fields:
                field_names = ', '.join([
                    f.replace('_', ' ').title() 
                    for f in self.changed_fields 
                    if f != '__deleted__'
                ])
                return f"Updated {field_names} in '{self.rule.name if self.rule else self.rule_name_backup}'"
            return f"Updated rule '{self.rule.name if self.rule else self.rule_name_backup}'"
        
        elif self.action == 'delete':
            return f"Deleted rule '{self.rule_name_backup}'"
        
        elif self.action == 'activate':
            return f"Activated rule '{self.rule.name}'"
        
        elif self.action == 'deactivate':
            return f"Deactivated rule '{self.rule.name}'"
        
        elif self.action == 'test':
            return f"Tested trigger for '{self.rule.name}'"
        
        elif self.action == 'clone':
            return f"Cloned rule '{self.rule.name}'"
        
        return f"{self.action} on rule"
    
    def get_field_changes(self):
        """Get detailed field changes"""
        if not self.old_data or not self.new_data:
            return []
        
        changes = []
        all_fields = set(self.old_data.keys()) | set(self.new_data.keys())
        
        for field in all_fields:
            old_value = self.old_data.get(field)
            new_value = self.new_data.get(field)
            
            if old_value != new_value:
                changes.append({
                    'field': field,
                    'old': old_value,
                    'new': new_value,
                    'type': 'changed' if old_value and new_value else 'added' if new_value else 'removed'
                })
        
        return changes
    
    def get_audit_data(self):
        """Get complete audit data"""
        return {
            'action': self.action,
            'action_display': self.get_action_display(),
            'changed_by': self.changed_by.username if self.changed_by else 'System',
            'changed_at': self.changed_at.isoformat(),
            'rule_name': self.rule.name if self.rule else self.rule_name_backup,
            'rule_id': self.rule.id if self.rule else self.rule_id_backup,
            'summary': self.get_changes_summary(),
            'field_changes': self.get_field_changes(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent[:100] if self.user_agent else '',
        }
    
    @classmethod
    def log_change(cls, rule, action, changed_by, old_data=None, new_data=None, 
                   changed_fields=None, request=None):
        """Log a change to an alert rule"""
        history = cls.objects.create(
            rule=rule,
            action=action,
            old_data=old_data,
            new_data=new_data,
            changed_fields=changed_fields or [],
            changed_by=changed_by,
            rule_name_backup=rule.name if rule else '',
            rule_id_backup=rule.id if rule else None,
        )
        
        # Capture request info if available
        if request:
            history.ip_address = request.META.get('REMOTE_ADDR')
            history.user_agent = request.META.get('HTTP_USER_AGENT', '')
            history.session_id = request.session.session_key if hasattr(request, 'session') else ''
            history.save()
        
        return history
    
    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['rule', 'changed_at']),
            models.Index(fields=['changed_by', 'changed_at']),
            models.Index(fields=['action', 'changed_at']),
            GinIndex(fields=['changed_fields'], name='changed_fields_gin_idx'),
        ]
        db_table_comment = "Audit trail for all changes to alert rules"
        verbose_name = "Alert Rule History"
        verbose_name_plural = "Alert Rule Histories"


# ==================== SYSTEM 10: ALERT DASHBOARD CONFIG ====================

def get_severity_filters():
    return ['critical', 'high', 'medium', 'low']

def get_default_dashboard_layout():
    return {
        'alert_stats': {'x': 0, 'y': 0, 'w': 4, 'h': 2},
        'recent_alerts': {'x': 4, 'y': 0, 'w': 8, 'h': 4},
        'system_health': {'x': 0, 'y': 2, 'w': 4, 'h': 2},
        'severity_distribution': {'x': 0, 'y': 4, 'w': 6, 'h': 3},
        'notification_stats': {'x': 6, 'y': 4, 'w': 6, 'h': 3},
        'alert_trends': {'x': 0, 'y': 7, 'w': 12, 'h': 3},
        'performance_metrics': {'x': 0, 'y': 10, 'w': 6, 'h': 3},
        'quick_actions': {'x': 6, 'y': 10, 'w': 6, 'h': 3},
    }

class AlertDashboardConfig(models.Model):
    """User-specific dashboard configurations"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='alerts_alertdashboardconfig_user'
    )
    
    # Display preferences
    theme = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('auto', 'Auto (System)'),
        ],
        default='auto'
    )
    
    default_time_range = models.CharField(
        max_length=20,
        choices=[
            ('1h', 'Last 1 hour'),
            ('3h', 'Last 3 hours'),
            ('6h', 'Last 6 hours'),
            ('12h', 'Last 12 hours'),
            ('24h', 'Last 24 hours'),
            ('7d', 'Last 7 days'),
            ('30d', 'Last 30 days'),
            ('custom', 'Custom'),
        ],
        default='24h'
    )
    
    # Widget visibility
    show_alert_stats = models.BooleanField(default=True)
    show_system_health = models.BooleanField(default=True)
    show_recent_alerts = models.BooleanField(default=True)
    show_notification_stats = models.BooleanField(default=True)
    show_alert_trends = models.BooleanField(default=True)
    show_severity_distribution = models.BooleanField(default=True)
    show_performance_metrics = models.BooleanField(default=True)
    show_quick_actions = models.BooleanField(default=True)
    show_alert_groups = models.BooleanField(default=True)
    show_escalation_status = models.BooleanField(default=True)
    
    severity_filter = models.JSONField(
        default=get_severity_filters
    )
    alert_type_filter = models.JSONField(default=list)
    show_resolved_alerts = models.BooleanField(default=False)
    show_acknowledged_alerts = models.BooleanField(default=True)
    show_false_positives = models.BooleanField(default=False)
    
    # Notification preferences
    auto_refresh_interval = models.IntegerField(
        default=30,
        help_text="Auto-refresh interval in seconds (0 = disabled)",
        validators=[MinValueValidator(0), MaxValueValidator(3600)]
    )
    show_desktop_notifications = models.BooleanField(default=False)
    play_alert_sound = models.BooleanField(default=True)
    
    # Chart preferences
    chart_type = models.CharField(
        max_length=20,
        choices=[
            ('line', 'Line Chart'),
            ('bar', 'Bar Chart'),
            ('area', 'Area Chart'),
            ('pie', 'Pie Chart'),
            ('scatter', 'Scatter Plot'),
        ],
        default='line'
    )
    
    chart_color_scheme = models.CharField(
        max_length=20,
        choices=[
            ('default', 'Default'),
            ('monochrome', 'Monochrome'),
            ('pastel', 'Pastel'),
            ('vibrant', 'Vibrant'),
            ('dark', 'Dark'),
        ],
        default='default'
    )
    
    # Data density
    data_points_limit = models.IntegerField(
        default=50,
        help_text="Maximum data points to show in charts",
        validators=[MinValueValidator(10), MaxValueValidator(1000)]
    )
    
    # Export preferences
    default_export_format = models.CharField(
        max_length=10,
        choices=[
            ('csv', 'CSV'),
            ('json', 'JSON'),
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
        ],
        default='csv'
    )
    
    # Notification sound
    alert_sound = models.CharField(
        max_length=50,
        choices=[
            ('default', 'Default Beep'),
            ('chime', 'Soft Chime'),
            ('bell', 'Bell'),
            ('siren', 'Siren'),
            ('none', 'None'),
        ],
        default='default'
    )
    
    custom_sound_url = models.URLField(blank=True, max_length=500)
    
    # Fixed: Added missing dashboard_layout field (referenced in get_dashboard_settings and serializer)
    dashboard_layout = models.JSONField(
        default=get_default_dashboard_layout,
        help_text="Widget layout configuration"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Dashboard Config for {self.user.username}"
    
    def get_visible_severities(self):
        """Get list of severities to show"""
        return [s for s in self.severity_filter if s in ['critical', 'high', 'medium', 'low']]
    
    def get_visible_alert_types(self):
        """Get list of alert types to show"""
        return self.alert_type_filter
    
    def get_widget_visibility(self):
        """Get widget visibility settings"""
        return {
            'alert_stats': self.show_alert_stats,
            'system_health': self.show_system_health,
            'recent_alerts': self.show_recent_alerts,
            'notification_stats': self.show_notification_stats,
            'alert_trends': self.show_alert_trends,
            'severity_distribution': self.show_severity_distribution,
            'performance_metrics': self.show_performance_metrics,
            'quick_actions': self.show_quick_actions,
            'alert_groups': self.show_alert_groups,
            'escalation_status': self.show_escalation_status,
        }
    
    def get_dashboard_settings(self):
        """Get all dashboard settings as dict"""
        return {
            'theme': self.theme,
            'default_time_range': self.default_time_range,
            'auto_refresh_interval': self.auto_refresh_interval,
            'show_desktop_notifications': self.show_desktop_notifications,
            'play_alert_sound': self.play_alert_sound,
            'chart_type': self.chart_type,
            'chart_color_scheme': self.chart_color_scheme,
            'data_points_limit': self.data_points_limit,
            'default_export_format': self.default_export_format,
            'alert_sound': self.alert_sound,
            'widget_visibility': self.get_widget_visibility(),
            'severity_filter': self.get_visible_severities(),
            'alert_type_filter': self.get_visible_alert_types(),
            'show_resolved_alerts': self.show_resolved_alerts,
            'show_acknowledged_alerts': self.show_acknowledged_alerts,
            'show_false_positives': self.show_false_positives,
            'dashboard_layout': self.dashboard_layout,
        }
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.theme = 'auto'
        self.default_time_range = '24h'
        self.show_alert_stats = True
        self.show_system_health = True
        self.show_recent_alerts = True
        self.show_notification_stats = True
        self.show_alert_trends = True
        self.show_severity_distribution = True
        self.show_performance_metrics = True
        self.show_quick_actions = True
        self.show_alert_groups = True
        self.show_escalation_status = True
        self.severity_filter = ['critical', 'high', 'medium', 'low']
        self.alert_type_filter = []
        self.show_resolved_alerts = False
        self.show_acknowledged_alerts = True
        self.show_false_positives = False
        self.auto_refresh_interval = 30
        self.show_desktop_notifications = False
        self.play_alert_sound = True
        self.chart_type = 'line'
        self.chart_color_scheme = 'default'
        self.data_points_limit = 50
        self.default_export_format = 'csv'
        self.alert_sound = 'default'
        self.custom_sound_url = ''
        self.save()
    
    class Meta:
        db_table_comment = "User-specific dashboard configuration and preferences"
        verbose_name = "Dashboard Configuration"
        verbose_name_plural = "Dashboard Configurations"


# ==================== SYSTEM METRICS MODEL ====================

class SystemMetrics(models.Model):
    """Track system-wide metrics for monitoring"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    timestamp = models.DateTimeField(auto_now_add=True)
    
    # User metrics
    total_users = models.IntegerField(default=0)
    active_users_1h = models.IntegerField(default=0)
    active_users_24h = models.IntegerField(default=0)
    new_signups_1h = models.IntegerField(default=0)
    new_signups_24h = models.IntegerField(default=0)
    
    # Earning metrics
    total_earnings_1h = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earnings_24h = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tasks_1h = models.IntegerField(default=0)
    avg_earning_per_user = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Payment metrics
    pending_payments = models.IntegerField(default=0)
    payment_requests_1h = models.IntegerField(default=0)
    total_payout_pending = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Security metrics
    fraud_indicators_1h = models.IntegerField(default=0)
    banned_users_24h = models.IntegerField(default=0)
    vpn_blocks_1h = models.IntegerField(default=0)
    
    # System health
    avg_response_time_ms = models.FloatField(default=0)
    error_count_1h = models.IntegerField(default=0)
    db_connections = models.IntegerField(default=0)
    redis_memory_mb = models.FloatField(default=0)
    
    # New metrics
    cpu_usage_percent = models.FloatField(default=0, help_text="CPU usage percentage")
    memory_usage_percent = models.FloatField(default=0, help_text="Memory usage percentage")
    disk_usage_percent = models.FloatField(default=0, help_text="Disk usage percentage")
    
    # Metadata
    data_source = models.CharField(
        max_length=50,
        default='auto',
        choices=[('auto', 'Auto-generated'), ('manual', 'Manual entry')]
    )
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Metrics at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def is_healthy(self):
        return (
            self.avg_response_time_ms < 500 and
            self.error_count_1h < 10 and
            self.cpu_usage_percent < 80 and
            self.memory_usage_percent < 85
        )
    
    @classmethod
    def get_latest(cls):
        return cls.objects.order_by('-timestamp').first()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['data_source', 'timestamp']),
        ]
        verbose_name = "System Metrics"
        verbose_name_plural = "System Metrics"


# ==================== SIGNALS ====================

from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

# Fixed: Use _old_data dict to capture pre-save state
# Pre-save: capture current DB state before overwrite
@receiver(pre_save, sender=AlertRule)
def capture_old_data_and_validate(sender, instance, **kwargs):
    """Capture old data before save + validate"""
    # Validate
    try:
        instance.full_clean()
    except ValidationError as e:
        logger.error(f"Validation error for AlertRule {instance.name}: {e}")
        raise e
    
    # Fixed: Capture old data HERE (pre_save), before DB write
    if instance.pk:
        try:
            old = AlertRule.objects.get(pk=instance.pk)
            instance._pre_save_old_data = {
                field.name: _safe_serialize(getattr(old, field.name))
                for field in old._meta.fields
                if field.name not in ['id', 'created_at', 'updated_at']
            }
        except AlertRule.DoesNotExist:
            instance._pre_save_old_data = None
    else:
        instance._pre_save_old_data = None


@receiver(post_save, sender=AlertRule)
def create_rule_history_on_save(sender, instance, created, **kwargs):
    """Create history entry when AlertRule is saved"""
    import json as _json
    action = 'create' if created else 'update'
    
    if not created and instance.pk:
        old_data = getattr(instance, '_pre_save_old_data', None)
        if old_data:
            new_data = {
                field.name: _safe_serialize(getattr(instance, field.name))
                for field in instance._meta.fields
                if field.name not in ['id', 'created_at', 'updated_at']
            }
            new_data = _json.loads(_json.dumps(new_data, default=str))
            old_data = _json.loads(_json.dumps(old_data, default=str))
            
            changed_fields = [k for k in new_data if new_data.get(k) != old_data.get(k)]
            
            AlertRuleHistory.log_change(
                rule=instance,
                action=action,
                changed_by=None,
                old_data=old_data,
                new_data=new_data,
                changed_fields=changed_fields
            )


@receiver(pre_delete, sender=AlertRule)
def create_history_on_delete(sender, instance, **kwargs):
    """Create history entry when AlertRule is deleted"""
    # Store rule data before deletion
    rule_data = {
        field.name: _safe_serialize(getattr(instance, field.name))
        for field in instance._meta.fields
        if field.name not in ['id', 'created_at', 'updated_at']
    }
    
    import json as _json
    rule_data = _json.loads(_json.dumps(rule_data, default=str))
    # Create history entry
    AlertRuleHistory.objects.create(
        rule=None,
        action='delete',
        old_data=rule_data,
        new_data=None,
        changed_fields=['__deleted__'],
        rule_name_backup=instance.name,
        rule_id_backup=str(instance.id),
        changed_by=None  # Would be request.user in views
    )
    
    # Clear cache
    pass  # cache clear disabled


@receiver(post_save, sender=AlertRule)
@receiver(post_delete, sender=AlertRule)
def clear_rule_cache(sender, instance, **kwargs):
    """Clear alert rule cache on save or delete"""
    pass  # cache clear disabled
    logger.debug(f"Cleared cache for AlertRule {instance.id}")


@receiver(post_save, sender=AlertLog)
def update_alert_group_cache(sender, instance, created, **kwargs):
    """Update alert group cache when alert is created or resolved"""
    if created or instance.is_resolved:
        # Find all groups containing this rule
        groups = AlertGroup.objects.filter(rules=instance.rule)
        for group in groups:
            group.update_cache()


@receiver(post_save, sender=SystemHealthCheck)
def trigger_health_alert(sender, instance, **kwargs):
    """Trigger alert if health check fails"""
    if instance.should_trigger_alert() and instance.alert_rule:
        try:
            # Create alert log for health check failure
            AlertLog.objects.create(
                rule=instance.alert_rule,
                trigger_value=instance.response_time_ms,
                threshold_value=instance.critical_threshold_ms,
                message=f"Health check '{instance.check_name}' failed with status: {instance.status}",
                details={
                    'check_type': instance.check_type,
                    'status_message': instance.status_message,
                    'response_time_ms': instance.response_time_ms,
                    'health_check_id': instance.id
                }
            )
            logger.info(f"Health alert triggered for {instance.check_name}")
        except Exception as e:
            logger.error(f"Failed to trigger health alert: {e}")
