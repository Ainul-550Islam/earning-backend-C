"""
Analytics Database Model

This module contains Analytics model and related models
for managing analytics data and reporting.
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

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class AnalyticsReport(AdvertiserPortalBaseModel, AuditModel):
    """
    Main analytics report model for managing custom reports.
    
    This model stores report configurations, schedules,
    and generated report data.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='analytics_reports',
        help_text="Associated advertiser"
    )
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_reports',
        help_text="Associated campaign (optional)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Report name"
    )
    description = models.TextField(
        blank=True,
        help_text="Report description"
    )
    
    # Report Configuration
    report_type = models.CharField(
        max_length=50,
        choices=[
            ('performance', 'Performance Report'),
            ('conversion', 'Conversion Report'),
            ('billing', 'Billing Report'),
            ('audience', 'Audience Report'),
            ('creative', 'Creative Report'),
            ('targeting', 'Targeting Report'),
            ('custom', 'Custom Report')
        ],
        db_index=True,
        help_text="Type of report"
    )
    report_format = models.CharField(
        max_length=20,
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
            ('json', 'JSON'),
            ('html', 'HTML')
        ],
        default='pdf',
        help_text="Report output format"
    )
    
    # Date Range Configuration
    date_range_type = models.CharField(
        max_length=50,
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('last_90_days', 'Last 90 Days'),
            ('month_to_date', 'Month to Date'),
            ('quarter_to_date', 'Quarter to Date'),
            ('year_to_date', 'Year to Date'),
            ('custom', 'Custom Range')
        ],
        default='last_30_days',
        help_text="Date range type"
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Custom start date"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Custom end date"
    )
    
    # Metrics Configuration
    metrics = models.JSONField(
        default=list,
        help_text="List of metrics to include in report"
    )
    dimensions = models.JSONField(
        default=list,
        help_text="List of dimensions to group by"
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Report filters"
    )
    
    # Scheduling Configuration
    is_scheduled = models.BooleanField(
        default=False,
        help_text="Whether report is scheduled"
    )
    schedule_type = models.CharField(
        max_length=50,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly')
        ],
        blank=True,
        help_text="Schedule frequency"
    )
    schedule_day = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day of month for monthly schedule"
    )
    schedule_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time of day for schedule"
    )
    next_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next scheduled run time"
    )
    
    # Distribution Configuration
    recipients = models.JSONField(
        default=list,
        blank=True,
        help_text="List of email recipients"
    )
    delivery_method = models.CharField(
        max_length=50,
        choices=[
            ('email', 'Email'),
            ('download', 'Download'),
            ('api', 'API'),
            ('webhook', 'Webhook')
        ],
        default='email',
        help_text="Report delivery method"
    )
    
    # Status and Processing
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='draft',
        db_index=True,
        help_text="Report status"
    )
    last_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last run timestamp"
    )
    last_file = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to last generated file"
    )
    
    # Configuration Metadata
    template_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Report template identifier"
    )
    custom_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom report settings"
    )
    
    class Meta:
        db_table = 'analytics_reports'
        verbose_name = 'Analytics Report'
        verbose_name_plural = 'Analytics Reports'
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_072'),
            models.Index(fields=['campaign'], name='idx_campaign_073'),
            models.Index(fields=['report_type'], name='idx_report_type_074'),
            models.Index(fields=['is_scheduled'], name='idx_is_scheduled_075'),
            models.Index(fields=['next_run'], name='idx_next_run_076'),
            models.Index(fields=['last_run'], name='idx_last_run_077'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.advertiser.company_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate date range
        if self.date_range_type == 'custom':
            if not self.start_date or not self.end_date:
                raise ValidationError("Start and end dates are required for custom date range")
            
            if self.start_date > self.end_date:
                raise ValidationError("Start date must be before end date")
        
        # Validate schedule configuration
        if self.is_scheduled:
            if not self.schedule_type:
                raise ValidationError("Schedule type is required for scheduled reports")
            
            if self.schedule_type == 'monthly' and not self.schedule_day:
                raise ValidationError("Schedule day is required for monthly schedule")
        
        # Validate recipients for email delivery
        if self.delivery_method == 'email' and not self.recipients:
            raise ValidationError("Recipients are required for email delivery")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set next run time if scheduled
        if self.is_scheduled and not self.next_run:
            self.next_run = self.calculate_next_run()
        
        super().save(*args, **kwargs)
    
    def calculate_next_run(self) -> Optional[datetime]:
        """Calculate next scheduled run time."""
        if not self.is_scheduled or not self.schedule_type:
            return None
        
        now = timezone.now()
        
        if self.schedule_type == 'daily':
            if self.schedule_time:
                next_run = now.replace(
                    hour=self.schedule_time.hour,
                    minute=self.schedule_time.minute,
                    second=self.schedule_time.second
                )
                if next_run <= now:
                    next_run += timezone.timedelta(days=1)
                return next_run
            else:
                return now + timezone.timedelta(days=1)
        
        elif self.schedule_type == 'weekly':
            # Default to next day at same time
            return now + timezone.timedelta(days=7)
        
        elif self.schedule_type == 'monthly':
            if self.schedule_day:
                # Get next month
                if now.month == 12:
                    next_month = now.replace(year=now.year + 1, month=1)
                else:
                    next_month = now.replace(month=now.month + 1)
                
                # Set to schedule day
                try:
                    next_run = next_month.replace(day=self.schedule_day)
                except ValueError:
                    # Handle invalid day (e.g., February 30)
                    next_run = next_month.replace(day=28)
                
                if self.schedule_time:
                    next_run = next_run.replace(
                        hour=self.schedule_time.hour,
                        minute=self.schedule_time.minute,
                        second=self.schedule_time.second
                    )
                
                return next_run
        
        elif self.schedule_type == 'quarterly':
            return now + timezone.timedelta(days=90)
        
        elif self.schedule_type == 'yearly':
            return now + timezone.timedelta(days=365)
        
        return None
    
    def get_date_range(self) -> tuple[Optional[date], Optional[date]]:
        """Get actual date range for report."""
        now = timezone.now().date()
        
        if self.date_range_type == 'today':
            return now, now
        
        elif self.date_range_type == 'yesterday':
            yesterday = now - timezone.timedelta(days=1)
            return yesterday, yesterday
        
        elif self.date_range_type == 'last_7_days':
            end_date = now - timezone.timedelta(days=1)
            start_date = end_date - timezone.timedelta(days=6)
            return start_date, end_date
        
        elif self.date_range_type == 'last_30_days':
            end_date = now - timezone.timedelta(days=1)
            start_date = end_date - timezone.timedelta(days=29)
            return start_date, end_date
        
        elif self.date_range_type == 'last_90_days':
            end_date = now - timezone.timedelta(days=1)
            start_date = end_date - timezone.timedelta(days=89)
            return start_date, end_date
        
        elif self.date_range_type == 'month_to_date':
            start_date = now.replace(day=1)
            return start_date, now
        
        elif self.date_range_type == 'quarter_to_date':
            quarter_start = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(month=quarter_start, day=1)
            return start_date, now
        
        elif self.date_range_type == 'year_to_date':
            start_date = now.replace(month=1, day=1)
            return start_date, now
        
        elif self.date_range_type == 'custom':
            return self.start_date, self.end_date
        
        return None, None
    
    def get_report_config(self) -> Dict[str, Any]:
        """Get complete report configuration."""
        start_date, end_date = self.get_date_range()
        
        return {
            'basic_info': {
                'name': self.name,
                'description': self.description,
                'report_type': self.report_type,
                'report_format': self.report_format
            },
            'date_range': {
                'type': self.date_range_type,
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            },
            'metrics': self.metrics,
            'dimensions': self.dimensions,
            'filters': self.filters,
            'schedule': {
                'is_scheduled': self.is_scheduled,
                'schedule_type': self.schedule_type,
                'schedule_day': self.schedule_day,
                'schedule_time': self.schedule_time.isoformat() if self.schedule_time else None,
                'next_run': self.next_run.isoformat() if self.next_run else None
            } if self.is_scheduled else None,
            'delivery': {
                'delivery_method': self.delivery_method,
                'recipients': self.recipients
            },
            'status': {
                'status': self.status,
                'last_run': self.last_run.isoformat() if self.last_run else None,
                'last_file': self.last_file
            }
        }


class AnalyticsMetric(AdvertiserPortalBaseModel):
    """
    Model for defining analytics metrics.
    """
    
    # Basic Information
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Metric name"
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Display name for UI"
    )
    description = models.TextField(
        blank=True,
        help_text="Metric description"
    )
    
    # Metric Configuration
    metric_type = models.CharField(
        max_length=50,
        choices=[
            ('count', 'Count'),
            ('sum', 'Sum'),
            ('average', 'Average'),
            ('rate', 'Rate'),
            ('ratio', 'Ratio'),
            ('percentage', 'Percentage'),
            ('currency', 'Currency'),
            ('duration', 'Duration'),
            ('custom', 'Custom')
        ],
        help_text="Type of metric"
    )
    category = models.CharField(
        max_length=50,
        choices=[
            ('basic', 'Basic'),
            ('performance', 'Performance'),
            ('conversion', 'Conversion'),
            ('financial', 'Financial'),
            ('quality', 'Quality'),
            ('custom', 'Custom')
        ],
        help_text="Metric category"
    )
    
    # Data Source Configuration
    data_source = models.CharField(
        max_length=50,
        choices=[
            ('impressions', 'Impressions'),
            ('clicks', 'Clicks'),
            ('conversions', 'Conversions'),
            ('billing', 'Billing'),
            ('creative', 'Creative'),
            ('campaign', 'Campaign'),
            ('custom', 'Custom Query')
        ],
        help_text="Data source for metric"
    )
    field_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Field name in data source"
    )
    calculation_formula = models.TextField(
        blank=True,
        help_text="Custom calculation formula"
    )
    
    # Display Configuration
    unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Display unit (e.g., $, %, seconds)"
    )
    decimal_places = models.IntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="Number of decimal places to display"
    )
    format_pattern = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom format pattern"
    )
    
    # Aggregation Configuration
    aggregation_method = models.CharField(
        max_length=50,
        choices=[
            ('sum', 'Sum'),
            ('avg', 'Average'),
            ('min', 'Minimum'),
            ('max', 'Maximum'),
            ('count', 'Count'),
            ('distinct', 'Distinct Count')
        ],
        default='sum',
        help_text="Aggregation method"
    )
    
    # Status and Availability
    is_active = models.BooleanField(
        default=True,
        help_text="Whether metric is active"
    )
    is_system = models.BooleanField(
        default=False,
        help_text="Whether metric is system-defined"
    )
    
    class Meta:
        db_table = 'analytics_metrics'
        verbose_name = 'Analytics Metric'
        verbose_name_plural = 'Analytics Metrics'
        indexes = [
            models.Index(fields=['category'], name='idx_category_078'),
            models.Index(fields=['metric_type'], name='idx_metric_type_079'),
            models.Index(fields=['data_source'], name='idx_data_source_080'),
            models.Index(fields=['is_active'], name='idx_is_active_081'),
        ]
    
    def __str__(self) -> str:
        return self.display_name
    
    def get_formatted_value(self, value: Union[int, float, Decimal]) -> str:
        """Get formatted metric value."""
        if value is None:
            return "N/A"
        
        # Apply decimal places
        if self.decimal_places > 0:
            formatted_value = f"{float(value):.{self.decimals}f}"
        else:
            formatted_value = str(int(float(value)))
        
        # Apply unit
        if self.unit:
            if self.unit == '$':
                formatted_value = f"${formatted_value}"
            elif self.unit == '%':
                formatted_value = f"{formatted_value}%"
            elif self.unit == 'seconds':
                formatted_value = f"{formatted_value}s"
            else:
                formatted_value = f"{formatted_value} {self.unit}"
        
        # Apply custom format pattern
        if self.format_pattern:
            try:
                formatted_value = self.format_pattern.format(value=formatted_value)
            except (KeyError, ValueError):
                pass
        
        return formatted_value


class AnalyticsDashboard(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing analytics dashboards.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='analytics_dashboards',
        help_text="Associated advertiser"
    )
    name = models.CharField(
        max_length=255,
        help_text="Dashboard name"
    )
    description = models.TextField(
        blank=True,
        help_text="Dashboard description"
    )
    
    # Dashboard Configuration
    layout_type = models.CharField(
        max_length=50,
        choices=[
            ('grid', 'Grid'),
            ('flexible', 'Flexible'),
            ('tabbed', 'Tabbed'),
            ('custom', 'Custom')
        ],
        default='grid',
        help_text="Dashboard layout type"
    )
    theme = models.CharField(
        max_length=50,
        choices=[
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('auto', 'Auto')
        ],
        default='light',
        help_text="Dashboard theme"
    )
    
    # Widget Configuration
    widgets = models.JSONField(
        default=list,
        help_text="List of dashboard widgets"
    )
    layout_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Layout configuration"
    )
    
    # Filter Configuration
    default_filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Default filters for dashboard"
    )
    available_filters = models.JSONField(
        default=list,
        blank=True,
        help_text="Available filters for users"
    )
    
    # Sharing and Access
    is_public = models.BooleanField(
        default=False,
        help_text="Whether dashboard is publicly accessible"
    )
    shared_users = models.JSONField(
        default=list,
        blank=True,
        help_text="List of users with access"
    )
    sharing_token = models.CharField(
        max_length=100,
        blank=True,
        help_text="Token for public sharing"
    )
    
    # Status and Configuration
    is_active = models.BooleanField(
        default=True,
        help_text="Whether dashboard is active"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default dashboard"
    )
    
    class Meta:
        db_table = 'analytics_dashboards'
        verbose_name = 'Analytics Dashboard'
        verbose_name_plural = 'Analytics Dashboards'
        indexes = [
            models.Index(fields=['advertiser', 'is_active'], name='idx_advertiser_is_active_082'),
            models.Index(fields=['is_public'], name='idx_is_public_083'),
            models.Index(fields=['is_default'], name='idx_is_default_084'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.advertiser.company_name})"
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Generate sharing token if public and not set
        if self.is_public and not self.sharing_token:
            self.sharing_token = self.generate_sharing_token()
        
        # Ensure only one default dashboard per advertiser
        if self.is_default:
            AnalyticsDashboard.objects.filter(
                advertiser=self.advertiser,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    def generate_sharing_token(self) -> str:
        """Generate unique sharing token."""
        import secrets
        return f"dash_{secrets.token_urlsafe(32)}"
    
    def get_dashboard_config(self) -> Dict[str, Any]:
        """Get complete dashboard configuration."""
        return {
            'basic_info': {
                'name': self.name,
                'description': self.description,
                'layout_type': self.layout_type,
                'theme': self.theme
            },
            'widgets': self.widgets,
            'layout_config': self.layout_config,
            'filters': {
                'default': self.default_filters,
                'available': self.available_filters
            },
            'sharing': {
                'is_public': self.is_public,
                'sharing_token': self.sharing_token,
                'shared_users': self.shared_users
            },
            'status': {
                'is_active': self.is_active,
                'is_default': self.is_default
            }
        }


class AnalyticsAlert(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing analytics alerts and notifications.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='analytics_alerts',
        help_text="Associated advertiser"
    )
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_alerts',
        help_text="Associated campaign (optional)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Alert name"
    )
    description = models.TextField(
        blank=True,
        help_text="Alert description"
    )
    
    # Alert Configuration
    alert_type = models.CharField(
        max_length=50,
        choices=[
            ('threshold', 'Threshold'),
            ('anomaly', 'Anomaly Detection'),
            ('trend', 'Trend Change'),
            ('performance', 'Performance Drop'),
            ('budget', 'Budget Alert'),
            ('custom', 'Custom')
        ],
        help_text="Type of alert"
    )
    metric = models.ForeignKey(
        AnalyticsMetric,
        on_delete=models.CASCADE,
        related_name='alerts',
        help_text="Metric to monitor"
    )
    
    # Threshold Configuration
    threshold_type = models.CharField(
        max_length=50,
        choices=[
            ('greater_than', 'Greater Than'),
            ('less_than', 'Less Than'),
            ('equals', 'Equals'),
            ('percentage_change', 'Percentage Change'),
            ('standard_deviation', 'Standard Deviation')
        ],
        help_text="Type of threshold"
    )
    threshold_value = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        help_text="Threshold value"
    )
    threshold_direction = models.CharField(
        max_length=20,
        choices=[
            ('above', 'Above'),
            ('below', 'Below'),
            ('both', 'Both Directions')
        ],
        default='above',
        help_text="Threshold direction"
    )
    
    # Time Configuration
    time_window = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        help_text="Time window in minutes"
    )
    evaluation_frequency = models.CharField(
        max_length=50,
        choices=[
            ('realtime', 'Real-time'),
            ('5min', 'Every 5 Minutes'),
            ('15min', 'Every 15 Minutes'),
            ('30min', 'Every 30 Minutes'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily')
        ],
        default='hourly',
        help_text="Evaluation frequency"
    )
    
    # Notification Configuration
    notification_channels = models.JSONField(
        default=list,
        help_text="List of notification channels"
    )
    recipients = models.JSONField(
        default=list,
        help_text="List of recipients"
    )
    notification_template = models.TextField(
        blank=True,
        help_text="Custom notification template"
    )
    
    # Status and Behavior
    is_active = models.BooleanField(
        default=True,
        help_text="Whether alert is active"
    )
    is_muted = models.BooleanField(
        default=False,
        help_text="Whether alert is muted"
    )
    mute_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Mute alert until this time"
    )
    cooldown_period = models.IntegerField(
        default=60,
        validators=[MinValueValidator(0)],
        help_text="Cooldown period in minutes"
    )
    last_triggered = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time alert was triggered"
    )
    
    class Meta:
        db_table = 'analytics_alerts'
        verbose_name = 'Analytics Alert'
        verbose_name_plural = 'Analytics Alerts'
        indexes = [
            models.Index(fields=['advertiser', 'is_active'], name='idx_advertiser_is_active_085'),
            models.Index(fields=['campaign'], name='idx_campaign_086'),
            models.Index(fields=['alert_type'], name='idx_alert_type_087'),
            models.Index(fields=['metric'], name='idx_metric_088'),
            models.Index(fields=['last_triggered'], name='idx_last_triggered_089'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.advertiser.company_name})"
    
    def can_trigger(self) -> bool:
        """Check if alert can be triggered."""
        if not self.is_active or self.is_muted:
            return False
        
        if self.mute_until and timezone.now() < self.mute_until:
            return False
        
        if self.last_triggered:
            cooldown_end = self.last_triggered + timezone.timedelta(minutes=self.cooldown_period)
            if timezone.now() < cooldown_end:
                return False
        
        return True
    
    def trigger_alert(self, current_value: Union[int, float, Decimal]) -> bool:
        """Trigger alert if threshold is met."""
        if not self.can_trigger():
            return False
        
        threshold_met = self.evaluate_threshold(current_value)
        
        if threshold_met:
            self.last_triggered = timezone.now()
            self.save(update_fields=['last_triggered'])
            
            # Send notifications
            self.send_notifications(current_value)
            
            return True
        
        return False
    
    def evaluate_threshold(self, current_value: Union[int, float, Decimal]) -> bool:
        """Evaluate if threshold condition is met."""
        try:
            current_val = float(current_value)
            threshold_val = float(self.threshold_value)
            
            if self.threshold_type == 'greater_than':
                return current_val > threshold_val
            elif self.threshold_type == 'less_than':
                return current_val < threshold_val
            elif self.threshold_type == 'equals':
                return abs(current_val - threshold_val) < 0.001
            elif self.threshold_type == 'percentage_change':
                # Would need historical data for this
                return False
            elif self.threshold_type == 'standard_deviation':
                # Would need statistical data for this
                return False
            
            return False
        except (ValueError, TypeError):
            return False
    
    def send_notifications(self, current_value: Union[int, float, Decimal]) -> None:
        """Send alert notifications."""
        # This would integrate with notification system
        message = self.format_notification_message(current_value)
        
        # Send to each channel
        for channel in self.notification_channels:
            if channel == 'email':
                self.send_email_notification(message, current_value)
            elif channel == 'sms':
                self.send_sms_notification(message, current_value)
            elif channel == 'webhook':
                self.send_webhook_notification(message, current_value)
    
    def format_notification_message(self, current_value: Union[int, float, Decimal]) -> str:
        """Format notification message."""
        if self.notification_template:
            try:
                return self.notification_template.format(
                    alert_name=self.name,
                    metric_name=self.metric.display_name,
                    current_value=current_value,
                    threshold_value=self.threshold_value,
                    campaign_name=self.campaign.name if self.campaign else 'All Campaigns'
                )
            except KeyError:
                pass
        
        # Default message
        return (f"Alert: {self.name}\n"
                f"Metric: {self.metric.display_name}\n"
                f"Current Value: {current_value}\n"
                f"Threshold: {self.threshold_value}\n"
                f"Campaign: {self.campaign.name if self.campaign else 'All Campaigns'}")
    
    def send_email_notification(self, message: str, current_value: Union[int, float, Decimal]) -> None:
        """Send email notification."""
        # Implementation would go here
        pass
    
    def send_sms_notification(self, message: str, current_value: Union[int, float, Decimal]) -> None:
        """Send SMS notification."""
        # Implementation would go here
        pass
    
    def send_webhook_notification(self, message: str, current_value: Union[int, float, Decimal]) -> None:
        """Send webhook notification."""
        # Implementation would go here
        pass


class AnalyticsDataPoint(AdvertiserPortalBaseModel):
    """
    Model for storing analytics data points.
    
    This model stores pre-calculated analytics data
    for efficient querying and reporting.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='analytics_data_points',
        help_text="Associated advertiser"
    )
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='analytics_data_points',
        help_text="Associated campaign"
    )
    metric = models.ForeignKey(
        AnalyticsMetric,
        on_delete=models.CASCADE,
        related_name='data_points',
        help_text="Associated metric"
    )
    
    # Time Dimensions
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Data point timestamp"
    )
    date = models.DateField(
        db_index=True,
        help_text="Data point date"
    )
    hour = models.IntegerField(
        db_index=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Hour of day (0-23)"
    )
    
    # Dimension Values
    dimension_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Values for dimensions"
    )
    
    # Metric Values
    value = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Metric value"
    )
    raw_value = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Raw metric value before processing"
    )
    
    # Quality and Processing
    is_processed = models.BooleanField(
        default=True,
        help_text="Whether data point has been processed"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Confidence score (0-100)"
    )
    
    class Meta:
        db_table = 'analytics_data_points'
        verbose_name = 'Analytics Data Point'
        verbose_name_plural = 'Analytics Data Points'
        unique_together = [
            'advertiser', 'campaign', 'metric', 'timestamp', 'dimension_values'
        ]
        indexes = [
            models.Index(fields=['advertiser', 'date'], name='idx_advertiser_date_090'),
            models.Index(fields=['campaign', 'date'], name='idx_campaign_date_091'),
            models.Index(fields=['metric', 'date'], name='idx_metric_date_092'),
            models.Index(fields=['timestamp'], name='idx_timestamp_093'),
            models.Index(fields=['date', 'hour'], name='idx_date_hour_094'),
        ]
    
    def __str__(self) -> str:
        return f"{self.metric.display_name} - {self.date} ({self.campaign.name})"
    
    def get_formatted_value(self) -> str:
        """Get formatted metric value."""
        return self.metric.get_formatted_value(self.value)


class AnalyticsWidget(AdvertiserPortalBaseModel):
    """Dashboard widget for displaying analytics data."""
    dashboard = models.ForeignKey(
        AnalyticsDashboard,
        on_delete=models.CASCADE,
        related_name='widget_items',
        help_text="Parent dashboard"
    )
    widget_type = models.CharField(
        max_length=50,
        choices=[
            ('metric', 'Metric'), ('chart', 'Chart'), ('table', 'Table'),
            ('map', 'Map'), ('funnel', 'Funnel'), ('custom', 'Custom'),
        ],
        default='metric'
    )
    title = models.CharField(max_length=200, blank=True)
    position = models.IntegerField(default=0)
    width = models.IntegerField(default=6, help_text="Grid columns (1-12)")
    height = models.IntegerField(default=4, help_text="Grid rows")
    configuration = models.JSONField(default=dict)
    data_source = models.CharField(max_length=100, blank=True)
    refresh_interval = models.IntegerField(default=300, help_text="Seconds")
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"Widget [{self.widget_type}] {self.title or self.id}"


class AnalyticsEvent(AdvertiserPortalBaseModel):
    """Raw analytics event record."""
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser', on_delete=models.CASCADE,
        related_name='analytics_events'
    )
    event_type = models.CharField(max_length=100, db_index=True)
    event_data = models.JSONField(default=dict)
    session_id = models.CharField(max_length=128, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f"Event [{self.event_type}] {self.occurred_at:%Y-%m-%d %H:%M}"
