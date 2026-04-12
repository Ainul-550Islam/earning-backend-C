"""
Reporting Database Model

This module contains Reporting model and related models
for managing reports, dashboards, and data visualization.
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


class Report(AdvertiserPortalBaseModel, AuditModel):
    """
    Main report model for managing custom reports.
    
    This model stores report configurations, schedules,
    and generated report data.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='reports',
        help_text="Associated advertiser"
    )
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
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
            ('financial', 'Financial Report'),
            ('conversion', 'Conversion Report'),
            ('audience', 'Audience Report'),
            ('creative', 'Creative Report'),
            ('targeting', 'Targeting Report'),
            ('attribution', 'Attribution Report'),
            ('custom', 'Custom Report')
        ],
        db_index=True,
        help_text="Type of report"
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
    
    # Metrics and Dimensions
    metrics = models.JSONField(
        default=list,
        help_text="List of metrics to include"
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
    
    # Output Configuration
    output_format = models.CharField(
        max_length=20,
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
            ('json', 'JSON'),
            ('html', 'HTML'),
            ('powerpoint', 'PowerPoint')
        ],
        default='pdf',
        help_text="Output format"
    )
    template_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Report template identifier"
    )
    
    # Scheduling Configuration
    is_scheduled = models.BooleanField(
        default=False,
        help_text="Whether report is scheduled"
    )
    schedule_frequency = models.CharField(
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
            ('webhook', 'Webhook'),
            ('ftp', 'FTP')
        ],
        default='email',
        help_text="Delivery method"
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
    
    # Performance Metrics
    run_count = models.IntegerField(
        default=0,
        help_text="Number of times report has been run"
    )
    success_count = models.IntegerField(
        default=0,
        help_text="Number of successful runs"
    )
    failure_count = models.IntegerField(
        default=0,
        help_text="Number of failed runs"
    )
    average_run_time = models.IntegerField(
        default=0,
        help_text="Average run time in seconds"
    )
    
    # Access Control
    is_public = models.BooleanField(
        default=False,
        help_text="Whether report is publicly accessible"
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
    
    # Custom Settings
    custom_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom report settings"
    )
    
    class Meta:
        db_table = 'reports'
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        indexes = [
            models.Index(fields=['advertiser', 'status']),
            models.Index(fields=['campaign']),
            models.Index(fields=['report_type']),
            models.Index(fields=['is_scheduled']),
            models.Index(fields=['next_run']),
            models.Index(fields=['last_run']),
            models.Index(fields=['is_public']),
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
            if not self.schedule_frequency:
                raise ValidationError("Schedule frequency is required for scheduled reports")
            
            if self.schedule_frequency == 'monthly' and not self.schedule_day:
                raise ValidationError("Schedule day is required for monthly schedule")
        
        # Validate recipients for email delivery
        if self.delivery_method == 'email' and not self.recipients:
            raise ValidationError("Recipients are required for email delivery")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set next run time if scheduled
        if self.is_scheduled and not self.next_run:
            self.next_run = self.calculate_next_run()
        
        # Generate sharing token if public and not set
        if self.is_public and not self.sharing_token:
            self.sharing_token = self.generate_sharing_token()
        
        super().save(*args, **kwargs)
    
    def calculate_next_run(self) -> Optional[datetime]:
        """Calculate next scheduled run time."""
        if not self.is_scheduled or not self.schedule_frequency:
            return None
        
        now = timezone.now()
        
        if self.schedule_frequency == 'daily':
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
        
        elif self.schedule_frequency == 'weekly':
            return now + timezone.timedelta(days=7)
        
        elif self.schedule_frequency == 'monthly':
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
        
        elif self.schedule_frequency == 'quarterly':
            return now + timezone.timedelta(days=90)
        
        elif self.schedule_frequency == 'yearly':
            return now + timezone.timedelta(days=365)
        
        return None
    
    def generate_sharing_token(self) -> str:
        """Generate unique sharing token."""
        import secrets
        return f"report_{secrets.token_urlsafe(32)}"
    
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
    
    def run_report(self) -> Dict[str, Any]:
        """Generate the report."""
        try:
            self.status = 'processing'
            self.run_count += 1
            self.save(update_fields=['status', 'run_count'])
            
            start_time = timezone.now()
            
            # Generate report data
            report_data = self.generate_report_data()
            
            # Generate report file
            file_path = self.generate_report_file(report_data)
            
            # Update metrics
            end_time = timezone.now()
            run_time = int((end_time - start_time).total_seconds())
            
            # Update average run time
            if self.average_run_time == 0:
                self.average_run_time = run_time
            else:
                self.average_run_time = (self.average_run_time + run_time) // 2
            
            self.status = 'completed'
            self.last_run = timezone.now()
            self.last_file = file_path
            self.success_count += 1
            
            self.save(update_fields=['status', 'last_run', 'last_file', 'success_count', 'average_run_time'])
            
            # Schedule next run
            if self.is_scheduled:
                self.next_run = self.calculate_next_run()
                self.save(update_fields=['next_run'])
            
            # Send report if scheduled
            if self.is_scheduled:
                self.send_report(file_path)
            
            return {
                'success': True,
                'file_path': file_path,
                'run_time': run_time
            }
            
        except Exception as e:
            self.status = 'failed'
            self.failure_count += 1
            self.save(update_fields=['status', 'failure_count'])
            
            logger.error(f"Error running report {self.id}: {str(e)}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_report_data(self) -> Dict[str, Any]:
        """Generate report data based on configuration."""
        start_date, end_date = self.get_date_range()
        
        # This would implement actual data generation logic
        # For now, return mock data
        return {
            'report_info': {
                'name': self.name,
                'type': self.report_type,
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                },
                'metrics': self.metrics,
                'dimensions': self.dimensions,
                'filters': self.filters
            },
            'data': {
                'summary': {
                    'total_impressions': 1000000,
                    'total_clicks': 10000,
                    'total_conversions': 100,
                    'total_spend': 1000.00,
                    'total_revenue': 2000.00
                },
                'details': [
                    {
                        'date': '2024-01-01',
                        'impressions': 100000,
                        'clicks': 1000,
                        'conversions': 10,
                        'spend': 100.00,
                        'revenue': 200.00
                    }
                ]
            }
        }
    
    def generate_report_file(self, report_data: Dict[str, Any]) -> str:
        """Generate report file in specified format."""
        # This would implement actual file generation
        # For now, return a mock file path
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.name}_{timestamp}.{self.output_format}"
        file_path = f"reports/{self.advertiser.id}/{filename}"
        
        return file_path
    
    def send_report(self, file_path: str) -> bool:
        """Send report via configured delivery method."""
        try:
            if self.delivery_method == 'email':
                return self.send_email_report(file_path)
            elif self.delivery_method == 'webhook':
                return self.send_webhook_report(file_path)
            elif self.delivery_method == 'ftp':
                return self.send_ftp_report(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Error sending report {self.id}: {str(e)}")
            return False
    
    def send_email_report(self, file_path: str) -> bool:
        """Send report via email."""
        # Implementation would go here
        return True
    
    def send_webhook_report(self, file_path: str) -> bool:
        """Send report via webhook."""
        # Implementation would go here
        return True
    
    def send_ftp_report(self, file_path: str) -> bool:
        """Send report via FTP."""
        # Implementation would go here
        return True
    
    def get_report_summary(self) -> Dict[str, Any]:
        """Get report summary."""
        return {
            'basic_info': {
                'name': self.name,
                'description': self.description,
                'report_type': self.report_type,
                'campaign': self.campaign.name if self.campaign else None
            },
            'configuration': {
                'date_range_type': self.date_range_type,
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None,
                'metrics': self.metrics,
                'dimensions': self.dimensions,
                'output_format': self.output_format
            },
            'schedule': {
                'is_scheduled': self.is_scheduled,
                'schedule_frequency': self.schedule_frequency,
                'schedule_day': self.schedule_day,
                'schedule_time': self.schedule_time.isoformat() if self.schedule_time else None,
                'next_run': self.next_run.isoformat() if self.next_run else None
            },
            'distribution': {
                'delivery_method': self.delivery_method,
                'recipients': self.recipients
            },
            'status': {
                'status': self.status,
                'last_run': self.last_run.isoformat() if self.last_run else None,
                'last_file': self.last_file
            },
            'performance': {
                'run_count': self.run_count,
                'success_count': self.success_count,
                'failure_count': self.failure_count,
                'success_rate': (self.success_count / self.run_count * 100) if self.run_count > 0 else 0,
                'average_run_time': self.average_run_time
            },
            'access': {
                'is_public': self.is_public,
                'sharing_token': self.sharing_token,
                'shared_users': self.shared_users
            }
        }


class Dashboard(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing analytics dashboards.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='dashboards',
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
    refresh_interval = models.IntegerField(
        default=300,
        validators=[MinValueValidator(30)],
        help_text="Auto-refresh interval in seconds"
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
    
    # Access Control
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
        db_table = 'dashboards'
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
        indexes = [
            models.Index(fields=['advertiser', 'is_active']),
            models.Index(fields=['is_public']),
            models.Index(fields=['is_default']),
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
            Dashboard.objects.filter(
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
                'theme': self.theme,
                'refresh_interval': self.refresh_interval
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


class Widget(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing dashboard widgets.
    """
    
    # Basic Information
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='widget_definitions',
        help_text="Associated dashboard"
    )
    widget_id = models.CharField(
        max_length=100,
        help_text="Widget identifier"
    )
    name = models.CharField(
        max_length=255,
        help_text="Widget name"
    )
    
    # Widget Configuration
    widget_type = models.CharField(
        max_length=50,
        choices=[
            ('metric', 'Metric Card'),
            ('chart', 'Chart'),
            ('table', 'Table'),
            ('gauge', 'Gauge'),
            ('map', 'Map'),
            ('funnel', 'Funnel'),
            ('heatmap', 'Heatmap'),
            ('custom', 'Custom Widget')
        ],
        help_text="Type of widget"
    )
    
    # Data Configuration
    data_source = models.CharField(
        max_length=100,
        help_text="Data source for widget"
    )
    metrics = models.JSONField(
        default=list,
        help_text="List of metrics to display"
    )
    dimensions = models.JSONField(
        default=list,
        help_text="List of dimensions for grouping"
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Widget-specific filters"
    )
    
    # Display Configuration
    chart_type = models.CharField(
        max_length=50,
        choices=[
            ('line', 'Line Chart'),
            ('bar', 'Bar Chart'),
            ('pie', 'Pie Chart'),
            ('area', 'Area Chart'),
            ('scatter', 'Scatter Plot'),
            ('donut', 'Donut Chart')
        ],
        blank=True,
        help_text="Chart type for chart widgets"
    )
    display_options = models.JSONField(
        default=dict,
        blank=True,
        help_text="Display options and styling"
    )
    
    # Layout Configuration
    position = models.JSONField(
        default=dict,
        help_text="Widget position and size"
    )
    is_visible = models.BooleanField(
        default=True,
        help_text="Whether widget is visible"
    )
    
    class Meta:
        db_table = 'widgets'
        verbose_name = 'Widget'
        verbose_name_plural = 'Widgets'
        unique_together = ['dashboard', 'widget_id']
        indexes = [
            models.Index(fields=['dashboard', 'widget_type']),
            models.Index(fields=['is_visible']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.dashboard.name})"
    
    def get_widget_data(self) -> Dict[str, Any]:
        """Get widget data."""
        # This would implement actual data retrieval
        # For now, return mock data
        return {
            'widget_id': self.widget_id,
            'widget_type': self.widget_type,
            'data': {
                'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
                'datasets': [
                    {
                        'label': 'Impressions',
                        'data': [1000, 1200, 1100, 1300, 1400]
                    }
                ]
            }
        }


class ReportTemplate(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing report templates.
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
            ('performance', 'Performance Template'),
            ('financial', 'Financial Template'),
            ('conversion', 'Conversion Template'),
            ('custom', 'Custom Template')
        ],
        help_text="Type of template"
    )
    
    # Template Content
    template_content = models.TextField(
        help_text="Template content (HTML, etc.)"
    )
    css_styles = models.TextField(
        blank=True,
        help_text="CSS styles for template"
    )
    javascript_code = models.TextField(
        blank=True,
        help_text="JavaScript code for template"
    )
    
    # Template Configuration
    variables = models.JSONField(
        default=dict,
        help_text="Template variables and placeholders"
    )
    default_settings = models.JSONField(
        default=dict,
        help_text="Default template settings"
    )
    
    # Status and Access
    is_active = models.BooleanField(
        default=True,
        help_text="Whether template is active"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Whether template is publicly available"
    )
    
    class Meta:
        db_table = 'report_templates'
        verbose_name = 'Report Template'
        verbose_name_plural = 'Report Templates'
        indexes = [
            models.Index(fields=['template_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_public']),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def render_template(self, data: Dict[str, Any]) -> str:
        """Render template with provided data."""
        # This would implement actual template rendering
        # For now, return the template content
        return self.template_content


class ReportSchedule(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing report schedules.
    """
    
    # Basic Information
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='schedules',
        help_text="Associated report"
    )
    schedule_name = models.CharField(
        max_length=255,
        help_text="Schedule name"
    )
    
    # Schedule Configuration
    frequency = models.CharField(
        max_length=50,
        choices=[
            ('once', 'Once'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly')
        ],
        help_text="Schedule frequency"
    )
    
    # Timing Configuration
    run_date = models.DateField(
        null=True,
        blank=True,
        help_text="Specific run date for one-time schedules"
    )
    run_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Run time for recurring schedules"
    )
    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="Day of week (0=Sunday, 6=Saturday)"
    )
    day_of_month = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day of month"
    )
    
    # Recurrence Configuration
    recurrence_pattern = models.JSONField(
        default=dict,
        blank=True,
        help_text="Recurrence pattern configuration"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date for recurring schedules"
    )
    max_occurrences = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of occurrences"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether schedule is active"
    )
    next_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next scheduled run time"
    )
    last_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last run timestamp"
    )
    
    class Meta:
        db_table = 'report_schedules'
        verbose_name = 'Report Schedule'
        verbose_name_plural = 'Report Schedules'
        indexes = [
            models.Index(fields=['report', 'is_active']),
            models.Index(fields=['next_run']),
            models.Index(fields=['frequency']),
        ]
    
    def __str__(self) -> str:
        return f"{self.schedule_name} ({self.report.name})"
    
    def calculate_next_run(self) -> Optional[datetime]:
        """Calculate next run time."""
        if not self.is_active:
            return None
        
        now = timezone.now()
        
        if self.frequency == 'once':
            if self.run_date and not self.last_run:
                return timezone.datetime.combine(self.run_date, self.run_time or timezone.time(9, 0))
            return None
        
        elif self.frequency == 'daily':
            next_run = now.replace(
                hour=self.run_time.hour if self.run_time else 9,
                minute=self.run_time.minute if self.run_time else 0,
                second=0
            )
            if next_run <= now:
                next_run += timezone.timedelta(days=1)
            return next_run
        
        elif self.frequency == 'weekly':
            if self.day_of_week is not None:
                days_ahead = self.day_of_week - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                
                next_run = now + timezone.timedelta(days=days_ahead)
                if self.run_time:
                    next_run = next_run.replace(
                        hour=self.run_time.hour,
                        minute=self.run_time.minute,
                        second=0
                    )
                
                return next_run
        
        elif self.frequency == 'monthly':
            if self.day_of_month is not None:
                if now.day > self.day_of_month:
                    # Move to next month
                    if now.month == 12:
                        next_month = now.replace(year=now.year + 1, month=1)
                    else:
                        next_month = now.replace(month=now.month + 1)
                    
                    try:
                        next_run = next_month.replace(day=self.day_of_month)
                    except ValueError:
                        next_run = next_month.replace(day=28)
                else:
                    next_run = now.replace(day=self.day_of_month)
                
                if self.run_time:
                    next_run = next_run.replace(
                        hour=self.run_time.hour,
                        minute=self.run_time.minute,
                        second=0
                    )
                
                return next_run
        
        return None


class Visualization(AdvertiserPortalBaseModel, AuditModel):
    """Chart or graph visualization attached to a report or dashboard."""
    report = models.ForeignKey(
        Report, on_delete=models.CASCADE,
        related_name='visualizations', null=True, blank=True
    )
    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE,
        related_name='visualizations', null=True, blank=True
    )
    title = models.CharField(max_length=200)
    chart_type = models.CharField(
        max_length=50,
        choices=[
            ('line', 'Line'), ('bar', 'Bar'), ('pie', 'Pie'),
            ('area', 'Area'), ('scatter', 'Scatter'), ('table', 'Table'),
            ('funnel', 'Funnel'), ('heatmap', 'Heatmap'),
        ],
        default='line'
    )
    data_source = models.CharField(max_length=100, blank=True)
    configuration = models.JSONField(default=dict)
    position = models.IntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"Visualization [{self.chart_type}] {self.title}"
