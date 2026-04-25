"""
Reporting Models for Advertiser Portal

This module contains models for managing advertiser reports,
including campaign reports, publisher breakdowns, and creative performance.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserReport(models.Model):
    """
    Model for managing advertiser reports.
    
    Stores generated reports including performance data,
    financial summaries, and analytics.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this report belongs to')
    )
    
    # Report details
    report_type = models.CharField(
        _('Report Type'),
        max_length=50,
        choices=[
            ('campaign_performance', _('Campaign Performance')),
            ('offer_performance', _('Offer Performance')),
            ('creative_performance', _('Creative Performance')),
            ('publisher_breakdown', _('Publisher Breakdown')),
            ('geo_breakdown', _('Geographic Breakdown')),
            ('device_breakdown', _('Device Breakdown')),
            ('time_breakdown', _('Time Breakdown')),
            ('financial_summary', _('Financial Summary')),
            ('conversion_analysis', _('Conversion Analysis')),
            ('fraud_report', _('Fraud Report')),
            ('custom', _('Custom')),
        ],
        db_index=True,
        help_text=_('Type of report')
    )
    
    name = models.CharField(
        _('Report Name'),
        max_length=200,
        help_text=_('Report name for identification')
    )
    
    description = models.TextField(
        _('Description'),
        null=True,
        blank=True,
        help_text=_('Report description')
    )
    
    # Period and date range
    period = models.CharField(
        _('Period'),
        max_length=20,
        choices=[
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('monthly', _('Monthly')),
            ('quarterly', _('Quarterly')),
            ('yearly', _('Yearly')),
            ('custom', _('Custom')),
        ],
        default='monthly',
        help_text=_('Reporting period')
    )
    
    start_date = models.DateField(
        _('Start Date'),
        db_index=True,
        help_text=_('Start date for report period')
    )
    
    end_date = models.DateField(
        _('End Date'),
        db_index=True,
        help_text=_('End date for report period')
    )
    
    # Status and configuration
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('generating', _('Generating')),
            ('completed', _('Completed')),
            ('failed', _('Failed')),
            ('cancelled', _('Cancelled')),
        ],
        default='generating',
        db_index=True,
        help_text=_('Current report status')
    )
    
    is_scheduled = models.BooleanField(
        _('Is Scheduled'),
        default=False,
        help_text=_('Whether this is a scheduled report')
    )
    
    schedule_frequency = models.CharField(
        _('Schedule Frequency'),
        max_length=20,
        choices=[
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('monthly', _('Monthly')),
            ('quarterly', _('Quarterly')),
        ],
        null=True,
        blank=True,
        help_text=_('Frequency for scheduled reports')
    )
    
    # Report data
    data = models.JSONField(
        _('Data'),
        default=dict,
        help_text=_('Report data in JSON format')
    )
    
    # File information
    file_url = models.URLField(
        _('File URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('URL to generated report file')
    )
    
    file_format = models.CharField(
        _('File Format'),
        max_length=10,
        choices=[
            ('csv', _('CSV')),
            ('excel', _('Excel')),
            ('pdf', _('PDF')),
            ('json', _('JSON')),
        ],
        default='csv',
        help_text=_('File format for report')
    )
    
    file_size = models.IntegerField(
        _('File Size'),
        null=True,
        blank=True,
        help_text=_('File size in bytes')
    )
    
    # Configuration
    filters = models.JSONField(
        _('Filters'),
        default=dict,
        blank=True,
        help_text=_('Filters applied to report')
    )
    
    columns = models.JSONField(
        _('Columns'),
        default=list,
        blank=True,
        help_text=_('Columns included in report')
    )
    
    # Email delivery
    email_recipients = models.JSONField(
        _('Email Recipients'),
        default=list,
        blank=True,
        help_text=_('Email addresses to send report to')
    )
    
    email_sent = models.BooleanField(
        _('Email Sent'),
        default=False,
        help_text=_('Whether report has been emailed')
    )
    
    # Metadata
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional report metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this report was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this report was last updated')
    )
    
    generated_at = models.DateTimeField(
        _('Generated At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this report was generated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_report'
        verbose_name = _('Advertiser Report')
        verbose_name_plural = _('Advertiser Reports')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'report_type'], name='idx_advertiser_report_type_522'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_523'),
            models.Index(fields=['period', 'start_date', 'end_date'], name='idx_period_start_date_end__eac'),
            models.Index(fields=['is_scheduled', 'schedule_frequency'], name='idx_is_scheduled_schedule__0ee'),
            models.Index(fields=['generated_at'], name='idx_generated_at_526'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate date range
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_('Start date must be before end date'))
        
        # Validate schedule frequency
        if self.is_scheduled and not self.schedule_frequency:
            raise ValidationError(_('Schedule frequency is required for scheduled reports'))
        
        # Validate file size
        if self.file_size and self.file_size < 0:
            raise ValidationError(_('File size cannot be negative'))
    
    @property
    def is_completed(self) -> bool:
        """Check if report is completed."""
        return self.status == 'completed'
    
    @property
    def is_failed(self) -> bool:
        """Check if report generation failed."""
        return self.status == 'failed'
    
    @property
    def days_period(self) -> int:
        """Get number of days in report period."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    @property
    def file_size_display(self) -> str:
        """Get human-readable file size."""
        if self.file_size:
            size = self.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "N/A"
    
    @property
    def report_type_display(self) -> str:
        """Get human-readable report type."""
        type_names = {
            'campaign_performance': _('Campaign Performance'),
            'offer_performance': _('Offer Performance'),
            'creative_performance': _('Creative Performance'),
            'publisher_breakdown': _('Publisher Breakdown'),
            'geo_breakdown': _('Geographic Breakdown'),
            'device_breakdown': _('Device Breakdown'),
            'time_breakdown': _('Time Breakdown'),
            'financial_summary': _('Financial Summary'),
            'conversion_analysis': _('Conversion Analysis'),
            'fraud_report': _('Fraud Report'),
            'custom': _('Custom'),
        }
        return type_names.get(self.report_type, self.report_type)
    
    def generate_report(self):
        """Generate the report data."""
        try:
            self.status = 'generating'
            self.save()
            
            # Generate report based on type
            if self.report_type == 'campaign_performance':
                self.data = self._generate_campaign_performance_data()
            elif self.report_type == 'offer_performance':
                self.data = self._generate_offer_performance_data()
            elif self.report_type == 'financial_summary':
                self.data = self._generate_financial_summary_data()
            else:
                self.data = self._generate_custom_data()
            
            self.status = 'completed'
            self.generated_at = timezone.now()
            self.save()
            
            logger.info(f"Report generated: {self.name}")
            
        except Exception as e:
            self.status = 'failed'
            self.save()
            logger.error(f"Error generating report {self.name}: {e}")
    
    def _generate_campaign_performance_data(self) -> dict:
        """Generate campaign performance data."""
        # This would implement campaign performance data generation
        # For now, return placeholder
        return {
            'campaigns': [],
            'summary': {},
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'days': self.days_period
            }
        }
    
    def _generate_offer_performance_data(self) -> dict:
        """Generate offer performance data."""
        # This would implement offer performance data generation
        # For now, return placeholder
        return {
            'offers': [],
            'summary': {},
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'days': self.days_period
            }
        }
    
    def _generate_financial_summary_data(self) -> dict:
        """Generate financial summary data."""
        # This would implement financial summary data generation
        # For now, return placeholder
        return {
            'spending': {},
            'budgets': {},
            'roi': {},
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'days': self.days_period
            }
        }
    
    def _generate_custom_data(self) -> dict:
        """Generate custom report data."""
        # This would implement custom data generation based on configuration
        return {
            'data': [],
            'summary': {},
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'days': self.days_period
            }
        }
    
    def get_report_summary(self) -> dict:
        """Get report summary."""
        return {
            'id': self.id,
            'name': self.name,
            'report_type': self.report_type,
            'report_type_display': self.report_type_display,
            'period': self.period,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'days_period': self.days_period,
            'status': self.status,
            'is_completed': self.is_completed,
            'is_failed': self.is_failed,
            'is_scheduled': self.is_scheduled,
            'schedule_frequency': self.schedule_frequency,
            'file_format': self.file_format,
            'file_url': self.file_url,
            'file_size': self.file_size,
            'file_size_display': self.file_size_display,
            'has_data': bool(self.data),
            'data_keys': list(self.data.keys()) if self.data else [],
            'email_sent': self.email_sent,
            'created_at': self.created_at.isoformat(),
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
        }


class CampaignReport(models.Model):
    """
    Model for storing campaign performance reports.
    
    Stores daily performance metrics for campaigns
    including impressions, clicks, conversions, and spend.
    """
    
    # Core relationships
    campaign = models.ForeignKey(
        'advertiser_portal_v2.AdCampaign',
        on_delete=models.CASCADE,
        related_name='performance_reports',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this report belongs to')
    )
    
    # Date information
    date = models.DateField(
        _('Date'),
        db_index=True,
        help_text=_('Date for this performance data')
    )
    
    hour = models.IntegerField(
        _('Hour'),
        null=True,
        blank=True,
        help_text=_('Hour of day (0-23)')
    )
    
    # Performance metrics
    impressions = models.IntegerField(
        _('Impressions'),
        default=0,
        help_text=_('Number of impressions delivered')
    )
    
    clicks = models.IntegerField(
        _('Clicks'),
        default=0,
        help_text=_('Number of clicks received')
    )
    
    conversions = models.IntegerField(
        _('Conversions'),
        default=0,
        help_text=_('Number of conversions generated')
    )
    
    # Financial metrics
    spend_amount = models.DecimalField(
        _('Spend Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Amount spent')
    )
    
    revenue_amount = models.DecimalField(
        _('Revenue Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Revenue generated')
    )
    
    # Calculated metrics
    ctr = models.DecimalField(
        _('Click Through Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Click through rate percentage')
    )
    
    conversion_rate = models.DecimalField(
        _('Conversion Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Conversion rate percentage')
    )
    
    cpa = models.DecimalField(
        _('Cost Per Action'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per action')
    )
    
    cpc = models.DecimalField(
        _('Cost Per Click'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per click')
    )
    
    cpm = models.DecimalField(
        _('Cost Per Mille'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per thousand impressions')
    )
    
    roi = models.DecimalField(
        _('Return on Investment'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Return on investment percentage')
    )
    
    # Quality metrics
    quality_score = models.DecimalField(
        _('Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score (0-100)')
    )
    
    fraud_rate = models.DecimalField(
        _('Fraud Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Fraud rate percentage')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional performance metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this report was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this report was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_campaign_report'
        verbose_name = _('Campaign Report')
        verbose_name_plural = _('Campaign Reports')
        ordering = ['-date', '-hour']
        indexes = [
            models.Index(fields=['campaign', 'date'], name='idx_campaign_date_527'),
            models.Index(fields=['date', 'hour'], name='idx_date_hour_528'),
            models.Index(fields=['date'], name='idx_date_529'),
            models.Index(fields=['created_at'], name='idx_created_at_530'),
        ]
        unique_together = [
            ['campaign', 'date', 'hour'],
        ]
    
    def __str__(self):
        return f"{self.campaign.name} - {self.date}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate hour
        if self.hour and (self.hour < 0 or self.hour > 23):
            raise ValidationError(_('Hour must be between 0 and 23'))
        
        # Validate metrics
        for field_name in ['impressions', 'clicks', 'conversions']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate amounts
        for field_name in ['spend_amount', 'revenue_amount']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate rates
        for field_name in ['ctr', 'conversion_rate', 'cpa', 'cpc', 'cpm', 'roi', 'quality_score', 'fraud_rate']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate derived metrics
        self._calculate_metrics()
        
        super().save(*args, **kwargs)
    
    def _calculate_metrics(self):
        """Calculate derived performance metrics."""
        # Calculate CTR
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        # Calculate conversion rate
        if self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100
        
        # Calculate CPA
        if self.conversions > 0:
            self.cpa = self.spend_amount / self.conversions
        
        # Calculate CPC
        if self.clicks > 0:
            self.cpc = self.spend_amount / self.clicks
        
        # Calculate CPM
        if self.impressions > 0:
            self.cpm = (self.spend_amount / self.impressions) * 1000
        
        # Calculate ROI
        if self.spend_amount > 0:
            self.roi = ((self.revenue_amount - self.spend_amount) / self.spend_amount) * 100
    
    @property
    def is_hourly(self) -> bool:
        """Check if this is hourly data."""
        return self.hour is not None
    
    @property
    def is_daily(self) -> bool:
        """Check if this is daily data."""
        return self.hour is None
    
    @property
    def has_conversions(self) -> bool:
        """Check if campaign has conversions."""
        return self.conversions > 0
    
    @property
    def is_profitable(self) -> bool:
        """Check if campaign is profitable."""
        return self.revenue_amount > self.spend_amount
    
    def get_performance_summary(self) -> dict:
        """Get performance summary."""
        return {
            'campaign_id': self.campaign.id,
            'campaign_name': self.campaign.name,
            'date': self.date.isoformat(),
            'hour': self.hour,
            'is_hourly': self.is_hourly,
            'is_daily': self.is_daily,
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'spend_amount': float(self.spend_amount),
            'revenue_amount': float(self.revenue_amount),
            'profit': float(self.revenue_amount - self.spend_amount),
            'is_profitable': self.is_profitable,
            'ctr': float(self.ctr),
            'conversion_rate': float(self.conversion_rate),
            'cpa': float(self.cpa),
            'cpc': float(self.cpc),
            'cpm': float(self.cpm),
            'roi': float(self.roi),
            'quality_score': float(self.quality_score),
            'fraud_rate': float(self.fraud_rate),
            'has_conversions': self.has_conversions,
        }


class PublisherBreakdown(models.Model):
    """
    Model for storing publisher performance breakdowns.
    
    Stores performance data broken down by publisher
    including metrics and financial data.
    """
    
    # Core relationships
    campaign = models.ForeignKey(
        'advertiser_portal_v2.AdCampaign',
        on_delete=models.CASCADE,
        related_name='publisher_breakdowns',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this breakdown belongs to')
    )
    
    # Publisher information
    publisher_id = models.CharField(
        _('Publisher ID'),
        max_length=100,
        db_index=True,
        help_text=_('Publisher identifier')
    )
    
    publisher_name = models.CharField(
        _('Publisher Name'),
        max_length=200,
        null=True,
        blank=True,
        help_text=_('Publisher name')
    )
    
    # Date information
    date = models.DateField(
        _('Date'),
        db_index=True,
        help_text=_('Date for this breakdown data')
    )
    
    # Performance metrics
    impressions = models.IntegerField(
        _('Impressions'),
        default=0,
        help_text=_('Number of impressions delivered')
    )
    
    clicks = models.IntegerField(
        _('Clicks'),
        default=0,
        help_text=_('Number of clicks received')
    )
    
    conversions = models.IntegerField(
        _('Conversions'),
        default=0,
        help_text=_('Number of conversions generated')
    )
    
    # Financial metrics
    spend_amount = models.DecimalField(
        _('Spend Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Amount spent on this publisher')
    )
    
    revenue_amount = models.DecimalField(
        _('Revenue Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Revenue generated from this publisher')
    )
    
    # Calculated metrics
    ctr = models.DecimalField(
        _('Click Through Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Click through rate percentage')
    )
    
    conversion_rate = models.DecimalField(
        _('Conversion Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Conversion rate percentage')
    )
    
    cpa = models.DecimalField(
        _('Cost Per Action'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per action')
    )
    
    # Quality metrics
    quality_score = models.DecimalField(
        _('Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Publisher quality score (0-100)')
    )
    
    fraud_rate = models.DecimalField(
        _('Fraud Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Fraud rate percentage')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional publisher metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this breakdown was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this breakdown was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_publisher_breakdown'
        verbose_name = _('Publisher Breakdown')
        verbose_name_plural = _('Publisher Breakdowns')
        ordering = ['-date', '-spend_amount']
        indexes = [
            models.Index(fields=['campaign', 'date'], name='idx_campaign_date_531'),
            models.Index(fields=['publisher_id', 'date'], name='idx_publisher_id_date_532'),
            models.Index(fields=['date'], name='idx_date_533'),
            models.Index(fields=['created_at'], name='idx_created_at_534'),
        ]
        unique_together = [
            ['campaign', 'publisher_id', 'date'],
        ]
    
    def __str__(self):
        return f"{self.publisher_name or self.publisher_id} - {self.date}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate publisher ID
        if not self.publisher_id.strip():
            raise ValidationError(_('Publisher ID cannot be empty'))
        
        # Validate metrics
        for field_name in ['impressions', 'clicks', 'conversions']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate amounts
        for field_name in ['spend_amount', 'revenue_amount']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate rates
        for field_name in ['ctr', 'conversion_rate', 'cpa', 'quality_score', 'fraud_rate']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate derived metrics
        self._calculate_metrics()
        
        super().save(*args, **kwargs)
    
    def _calculate_metrics(self):
        """Calculate derived performance metrics."""
        # Calculate CTR
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        # Calculate conversion rate
        if self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100
        
        # Calculate CPA
        if self.conversions > 0:
            self.cpa = self.spend_amount / self.conversions
    
    @property
    def has_conversions(self) -> bool:
        """Check if publisher has conversions."""
        return self.conversions > 0
    
    @property
    def is_profitable(self) -> bool:
        """Check if publisher is profitable."""
        return self.revenue_amount > self.spend_amount
    
    @property
    def publisher_display_name(self) -> str:
        """Get display name for publisher."""
        return self.publisher_name or self.publisher_id
    
    def get_publisher_summary(self) -> dict:
        """Get publisher performance summary."""
        return {
            'publisher_id': self.publisher_id,
            'publisher_name': self.publisher_display_name,
            'date': self.date.isoformat(),
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'spend_amount': float(self.spend_amount),
            'revenue_amount': float(self.revenue_amount),
            'profit': float(self.revenue_amount - self.spend_amount),
            'is_profitable': self.is_profitable,
            'ctr': float(self.ctr),
            'conversion_rate': float(self.conversion_rate),
            'cpa': float(self.cpa),
            'quality_score': float(self.quality_score),
            'fraud_rate': float(self.fraud_rate),
            'has_conversions': self.has_conversions,
        }


class GeoBreakdown(models.Model):
    """
    Model for storing geographic performance breakdowns.
    
    Stores performance data broken down by geography
    including countries, regions, and cities.
    """
    
    # Core relationships
    campaign = models.ForeignKey(
        'advertiser_portal_v2.AdCampaign',
        on_delete=models.CASCADE,
        related_name='geo_breakdowns',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this breakdown belongs to')
    )
    
    # Geographic information
    country = models.CharField(
        _('Country'),
        max_length=2,
        db_index=True,
        help_text=_('Country code (ISO 3166-1 alpha-2)')
    )
    
    region = models.CharField(
        _('Region'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Region or state name')
    )
    
    city = models.CharField(
        _('City'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('City name')
    )
    
    # Date information
    date = models.DateField(
        _('Date'),
        db_index=True,
        help_text=_('Date for this breakdown data')
    )
    
    # Performance metrics
    impressions = models.IntegerField(
        _('Impressions'),
        default=0,
        help_text=_('Number of impressions delivered')
    )
    
    clicks = models.IntegerField(
        _('Clicks'),
        default=0,
        help_text=_('Number of clicks received')
    )
    
    conversions = models.IntegerField(
        _('Conversions'),
        default=0,
        help_text=_('Number of conversions generated')
    )
    
    # Financial metrics
    spend_amount = models.DecimalField(
        _('Spend Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Amount spent in this geography')
    )
    
    revenue_amount = models.DecimalField(
        _('Revenue Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Revenue generated from this geography')
    )
    
    # Calculated metrics
    ctr = models.DecimalField(
        _('Click Through Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Click through rate percentage')
    )
    
    conversion_rate = models.DecimalField(
        _('Conversion Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Conversion rate percentage')
    )
    
    cpa = models.DecimalField(
        _('Cost Per Action'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per action')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional geographic metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this breakdown was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this breakdown was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_geo_breakdown'
        verbose_name = _('Geographic Breakdown')
        verbose_name_plural = _('Geographic Breakdowns')
        ordering = ['-date', '-spend_amount']
        indexes = [
            models.Index(fields=['campaign', 'date'], name='idx_campaign_date_535'),
            models.Index(fields=['country', 'date'], name='idx_country_date_536'),
            models.Index(fields=['region', 'date'], name='idx_region_date_537'),
            models.Index(fields=['city', 'date'], name='idx_city_date_538'),
            models.Index(fields=['date'], name='idx_date_539'),
            models.Index(fields=['created_at'], name='idx_created_at_540'),
        ]
        unique_together = [
            ['campaign', 'country', 'region', 'city', 'date'],
        ]
    
    def __str__(self):
        location_parts = [self.country, self.region, self.city]
        location = ', '.join(filter(None, location_parts))
        return f"{location} - {self.date}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate country code
        if not self.country or len(self.country) != 2:
            raise ValidationError(_('Country code must be 2 characters'))
        
        # Validate metrics
        for field_name in ['impressions', 'clicks', 'conversions']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate amounts
        for field_name in ['spend_amount', 'revenue_amount']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate rates
        for field_name in ['ctr', 'conversion_rate', 'cpa']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate derived metrics
        self._calculate_metrics()
        
        super().save(*args, **kwargs)
    
    def _calculate_metrics(self):
        """Calculate derived performance metrics."""
        # Calculate CTR
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        # Calculate conversion rate
        if self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100
        
        # Calculate CPA
        if self.conversions > 0:
            self.cpa = self.spend_amount / self.conversions
    
    @property
    def has_conversions(self) -> bool:
        """Check if geography has conversions."""
        return self.conversions > 0
    
    @property
    def is_profitable(self) -> bool:
        """Check if geography is profitable."""
        return self.revenue_amount > self.spend_amount
    
    @property
    def location_display(self) -> str:
        """Get formatted location display."""
        parts = [self.country, self.region, self.city]
        return ', '.join(filter(None, parts))
    
    def get_geo_summary(self) -> dict:
        """Get geographic performance summary."""
        return {
            'country': self.country,
            'region': self.region,
            'city': self.city,
            'location_display': self.location_display,
            'date': self.date.isoformat(),
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'spend_amount': float(self.spend_amount),
            'revenue_amount': float(self.revenue_amount),
            'profit': float(self.revenue_amount - self.spend_amount),
            'is_profitable': self.is_profitable,
            'ctr': float(self.ctr),
            'conversion_rate': float(self.conversion_rate),
            'cpa': float(self.cpa),
            'has_conversions': self.has_conversions,
        }


class CreativePerformance(models.Model):
    """
    Model for storing creative performance data.
    
    Stores performance metrics for creatives
    including impressions, clicks, and conversions.
    """
    
    # Core relationships
    creative = models.ForeignKey(
        'advertiser_portal_v2.CampaignCreative',
        on_delete=models.CASCADE,
        related_name='performance_data',
        verbose_name=_('Creative'),
        help_text=_('Creative this performance belongs to')
    )
    
    # Date information
    date = models.DateField(
        _('Date'),
        db_index=True,
        help_text=_('Date for this performance data')
    )
    
    hour = models.IntegerField(
        _('Hour'),
        null=True,
        blank=True,
        help_text=_('Hour of day (0-23)')
    )
    
    # Performance metrics
    impressions = models.IntegerField(
        _('Impressions'),
        default=0,
        help_text=_('Number of impressions delivered')
    )
    
    clicks = models.IntegerField(
        _('Clicks'),
        default=0,
        help_text=_('Number of clicks received')
    )
    
    conversions = models.IntegerField(
        _('Conversions'),
        default=0,
        help_text=_('Number of conversions generated')
    )
    
    # Calculated metrics
    ctr = models.DecimalField(
        _('Click Through Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Click through rate percentage')
    )
    
    conversion_rate = models.DecimalField(
        _('Conversion Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Conversion rate percentage')
    )
    
    cpa = models.DecimalField(
        _('Cost Per Action'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per action')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional creative performance metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this performance data was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this performance data was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_creative_performance'
        verbose_name = _('Creative Performance')
        verbose_name_plural = _('Creative Performance')
        ordering = ['-date', '-hour']
        indexes = [
            models.Index(fields=['creative', 'date'], name='idx_creative_date_541'),
            models.Index(fields=['date', 'hour'], name='idx_date_hour_542'),
            models.Index(fields=['date'], name='idx_date_543'),
            models.Index(fields=['created_at'], name='idx_created_at_544'),
        ]
        unique_together = [
            ['creative', 'date', 'hour'],
        ]
    
    def __str__(self):
        return f"{self.creative.name} - {self.date}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate hour
        if self.hour and (self.hour < 0 or self.hour > 23):
            raise ValidationError(_('Hour must be between 0 and 23'))
        
        # Validate metrics
        for field_name in ['impressions', 'clicks', 'conversions']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate rates
        for field_name in ['ctr', 'conversion_rate', 'cpa']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate derived metrics
        self._calculate_metrics()
        
        super().save(*args, **kwargs)
    
    def _calculate_metrics(self):
        """Calculate derived performance metrics."""
        # Calculate CTR
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        # Calculate conversion rate
        if self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100
        
        # Calculate CPA
        if self.conversions > 0:
            # This would need spend data from campaign
            # For now, set to 0
            self.cpa = 0.00
    
    @property
    def is_hourly(self) -> bool:
        """Check if this is hourly data."""
        return self.hour is not None
    
    @property
    def is_daily(self) -> bool:
        """Check if this is daily data."""
        return self.hour is None
    
    @property
    def has_conversions(self) -> bool:
        """Check if creative has conversions."""
        return self.conversions > 0
    
    def get_creative_summary(self) -> dict:
        """Get creative performance summary."""
        return {
            'creative_id': self.creative.id,
            'creative_name': self.creative.name,
            'creative_type': self.creative.creative_type,
            'date': self.date.isoformat(),
            'hour': self.hour,
            'is_hourly': self.is_hourly,
            'is_daily': self.is_daily,
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'ctr': float(self.ctr),
            'conversion_rate': float(self.conversion_rate),
            'cpa': float(self.cpa),
            'has_conversions': self.has_conversions,
        }


# Signal handlers for reporting models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=AdvertiserReport)
def advertiser_report_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for advertiser reports."""
    if created:
        logger.info(f"New advertiser report created: {instance.name}")
        
        # Send notification to advertiser
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance.advertiser,
            type='report_created',
            title=_('New Report Created'),
            message=_('Your report "{instance.name}" has been created successfully.'),
        )

@receiver(post_save, sender=CampaignReport)
def campaign_report_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for campaign reports."""
    if created:
        logger.info(f"New campaign report created: {instance.campaign.name} - {instance.date}")

@receiver(post_save, sender=PublisherBreakdown)
def publisher_breakdown_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for publisher breakdowns."""
    if created:
        logger.info(f"New publisher breakdown created: {instance.publisher_id} - {instance.date}")

@receiver(post_save, sender=GeoBreakdown)
def geo_breakdown_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for geographic breakdowns."""
    if created:
        logger.info(f"New geographic breakdown created: {instance.location_display} - {instance.date}")

@receiver(post_save, sender=CreativePerformance)
def creative_performance_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for creative performance."""
    if created:
        logger.info(f"New creative performance created: {instance.creative.name} - {instance.date}")

@receiver(post_delete, sender=AdvertiserReport)
def advertiser_report_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for advertiser reports."""
    logger.info(f"Advertiser report deleted: {instance.name}")

@receiver(post_delete, sender=CampaignReport)
def campaign_report_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for campaign reports."""
    logger.info(f"Campaign report deleted: {instance.campaign.name} - {instance.date}")

@receiver(post_delete, sender=PublisherBreakdown)
def publisher_breakdown_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for publisher breakdowns."""
    logger.info(f"Publisher breakdown deleted: {instance.publisher_id} - {instance.date}")

@receiver(post_delete, sender=GeoBreakdown)
def geo_breakdown_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for geographic breakdowns."""
    logger.info(f"Geographic breakdown deleted: {instance.location_display} - {instance.date}")

@receiver(post_delete, sender=CreativePerformance)
def creative_performance_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for creative performance."""
    logger.info(f"Creative performance deleted: {instance.creative.name} - {instance.date}")
