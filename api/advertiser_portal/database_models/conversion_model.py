from django.conf import settings
"""
Conversion Database Model

This module contains the Conversion model and related models
for tracking ad conversions and attribution.
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
from django.contrib.gis.geos import Point


from ..models import *
from ..enums import *
from ..utils import *
from ..validators import *


class Conversion(AdvertiserPortalBaseModel, AuditModel):
    """
    Main conversion model for tracking ad conversions.
    
    This model stores detailed information about conversions
    including attribution, value, and post-conversion metrics.
    """
    
    # Basic Information
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='conversion_records',
        help_text="Associated campaign"
    )
    creative = models.ForeignKey(
        'advertiser_portal.Creative',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversion_set_creative',
        help_text="Associated creative"
    )
    click = models.ForeignKey(
        'advertiser_portal.Click',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversion_set_creative',
        help_text="Associated click"
    )
    conversion_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique conversion identifier"
    )
    
    # Timestamp Information
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Conversion timestamp"
    )
    date = models.DateField(
        db_index=True,
        help_text="Conversion date (for partitioning)"
    )
    hour = models.IntegerField(
        db_index=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Hour of day (0-23)"
    )
    
    # Conversion Details
    conversion_type = models.CharField(
        max_length=50,
        choices=[
            ('purchase', 'Purchase'),
            ('lead', 'Lead'),
            ('signup', 'Sign Up'),
            ('download', 'Download'),
            ('form_submit', 'Form Submit'),
            ('phone_call', 'Phone Call'),
            ('app_install', 'App Install'),
            ('video_view', 'Video View'),
            ('page_view', 'Page View'),
            ('custom', 'Custom')
        ],
        db_index=True,
        help_text="Type of conversion"
    )
    conversion_name = models.CharField(
        max_length=255,
        help_text="Conversion name or goal"
    )
    description = models.TextField(
        blank=True,
        help_text="Conversion description"
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Conversion category"
    )
    
    # Value and Revenue
    conversion_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Conversion value"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code"
    )
    revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Attributed revenue"
    )
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Attributed cost"
    )
    profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Calculated profit"
    )
    
    # Attribution Information
    attribution_model = models.CharField(
        max_length=50,
        choices=[
            ('last_click', 'Last Click'),
            ('first_click', 'First Click'),
            ('linear', 'Linear'),
            ('time_decay', 'Time Decay'),
            ('position_based', 'Position Based'),
            ('data_driven', 'Data Driven'),
            ('custom', 'Custom')
        ],
        default='last_click',
        help_text="Attribution model used"
    )
    attribution_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Attribution score percentage"
    )
    touchpoints = models.JSONField(
        default=list,
        blank=True,
        help_text="List of conversion touchpoints"
    )
    
    # User Information
    user_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Anonymous user identifier"
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="User session identifier"
    )
    device_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Device identifier"
    )
    
    # Geographic Information
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="User IP address"
    )
    country = models.CharField(
        max_length=2,
        blank=True,
        db_index=True,
        help_text="Country code (ISO 3166-1 alpha-2)"
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        help_text="Region/state"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City"
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal code"
    )
    coordinates = models.JSONField(null=True, blank=True, help_text="Geographic coordinates as {lat, lng}")
    timezone = models.CharField(
        max_length=50,
        blank=True,
        help_text="User timezone"
    )
    
    # Device Information
    device_type = models.CharField(
        max_length=50,
        choices=DeviceTypeEnum.choices,
        db_index=True,
        help_text="Device type"
    )
    os_family = models.CharField(
        max_length=50,
        choices=OSFamilyEnum.choices,
        db_index=True,
        help_text="Operating system family"
    )
    os_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Operating system version"
    )
    browser = models.CharField(
        max_length=50,
        choices=BrowserEnum.choices,
        db_index=True,
        help_text="Browser"
    )
    browser_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Browser version"
    )
    carrier = models.CharField(
        max_length=100,
        blank=True,
        help_text="Mobile carrier"
    )
    
    # Conversion Path Information
    landing_page = models.URLField(
        blank=True,
        help_text="Landing page URL"
    )
    conversion_page = models.URLField(
        blank=True,
        help_text="Conversion page URL"
    )
    referrer_url = models.URLField(
        blank=True,
        help_text="Referrer URL"
    )
    utm_source = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM source parameter"
    )
    utm_medium = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM medium parameter"
    )
    utm_campaign = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM campaign parameter"
    )
    utm_term = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM term parameter"
    )
    utm_content = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM content parameter"
    )
    
    # Product Information
    product_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Product identifier"
    )
    product_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Product name"
    )
    product_category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Product category"
    )
    product_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Product price"
    )
    quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Quantity purchased"
    )
    
    # Lead Information
    lead_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Lead name"
    )
    lead_email = models.EmailField(
        blank=True,
        help_text="Lead email"
    )
    lead_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Lead phone number"
    )
    lead_company = models.CharField(
        max_length=255,
        blank=True,
        help_text="Lead company"
    )
    lead_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Lead quality score (0-100)"
    )
    
    # Time-based Metrics
    time_to_convert = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Time to convert in seconds"
    )
    time_on_site = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Time on site in seconds"
    )
    pages_viewed = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Number of pages viewed"
    )
    
    # Quality and Validation
    is_valid = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether conversion is valid"
    )
    validation_score = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Validation score (0-100)"
    )
    duplicate_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates',
        help_text="Original conversion if this is a duplicate"
    )
    
    # External Integrations
    external_conversion_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External conversion ID"
    )
    integration_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration data"
    )
    
    # Status and Workflow
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('rejected', 'Rejected'),
            ('disputed', 'Disputed')
        ],
        default='pending',
        db_index=True,
        help_text="Conversion status"
    )
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_conversions'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Review timestamp"
    )
    notes = models.TextField(
        blank=True,
        help_text="Review notes"
    )
    
    # Custom Data
    custom_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom conversion data"
    )
    tracking_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party tracking data"
    )
    
    # Labels and Organization
    labels = models.JSONField(
        default=list,
        blank=True,
        help_text="Conversion labels"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Conversion tags"
    )
    
    class Meta:
        db_table = 'conversions'
        verbose_name = 'Conversion'
        verbose_name_plural = 'Conversions'
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['creative']),
            models.Index(fields=['click']),
            models.Index(fields=['conversion_type']),
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['user_id']),
            models.Index(fields=['session_id']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['country']),
            models.Index(fields=['device_type']),
            models.Index(fields=['os_family']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['is_valid']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self) -> str:
        return f"{self.conversion_id} ({self.conversion_type})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate timestamp
        if self.timestamp and self.date:
            if self.timestamp.date() != self.date:
                raise ValidationError("Date must match timestamp date")
        
        # Validate hour
        if self.hour is not None and (self.hour < 0 or self.hour > 23):
            raise ValidationError("Hour must be between 0 and 23")
        
        # Validate attribution score
        if self.attribution_score < 0 or self.attribution_score > 100:
            raise ValidationError("Attribution score must be between 0 and 100")
        
        # Validate lead score
        if self.lead_score is not None and (self.lead_score < 0 or self.lead_score > 100):
            raise ValidationError("Lead score must be between 0 and 100")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set date from timestamp if not set
        if self.timestamp and not self.date:
            self.date = self.timestamp.date()
        
        # Set hour from timestamp if not set
        if self.timestamp and self.hour is None:
            self.hour = self.timestamp.hour
        
        # Generate conversion ID if not set
        if not self.conversion_id:
            self.conversion_id = self.generate_conversion_id()
        
        # Calculate profit
        self.profit = self.revenue - self.cost
        
        # Calculate validation score
        self.validation_score = self.calculate_validation_score()
        
        # Check for duplicates
        if self.is_valid:
            duplicate = self.find_duplicate()
            if duplicate:
                self.duplicate_of = duplicate
        
        super().save(*args, **kwargs)
    
    def generate_conversion_id(self) -> str:
        """Generate unique conversion identifier."""
        import uuid
        return f"conv_{uuid.uuid4().hex}"
    
    def calculate_validation_score(self) -> int:
        """Calculate validation score for this conversion."""
        score = 100
        
        # Time-based validation
        if self.time_to_convert:
            if self.time_to_convert < 5:  # Very fast conversion
                score -= 30
            elif self.time_to_convert > 3600:  # Very slow conversion
                score -= 20
            elif self.time_to_convert > 1800:  # Slow conversion
                score -= 10
        
        # Geographic validation
        if self.ip_address and self.country:
            # Check if IP country matches declared country
            ip_country = self._get_country_from_ip(self.ip_address)
            if ip_country and ip_country != self.country:
                score -= 25
        
        # Device validation
        if self.device_type and self.os_family:
            # Unusual device-OS combinations
            if self.device_type == 'desktop' and self.os_family == 'ios':
                score -= 35
            if self.device_type == 'mobile' and self.os_family == 'windows':
                score -= 25
        
        # Referrer validation
        if self.referrer_url:
            # Suspicious referrers
            suspicious_refs = ['spam', 'bot', 'crawler', 'fake']
            for suspicious_ref in suspicious_refs:
                if suspicious_ref in self.referrer_url.lower():
                    score -= 40
                    break
        
        # Lead validation
        if self.lead_email:
            # Check email quality
            if self.lead_email.count('@') != 1:
                score -= 50
            if any(domain in self.lead_email.lower() for domain in ['spam', 'fake', 'temp']):
                score -= 30
        
        return max(0, score)
    
    def find_duplicate(self) -> Optional['Conversion']:
        """Find duplicate conversion."""
        # Look for conversions with same user within time window
        time_window = timezone.now() - timezone.timedelta(hours=24)
        
        duplicates = Conversion.objects.filter(
            user_id=self.user_id,
            conversion_type=self.conversion_type,
            campaign=self.campaign,
            timestamp__gte=time_window,
            is_valid=True
        ).exclude(id=self.id).order_by('-timestamp')
        
        # Check for exact matches
        for duplicate in duplicates:
            if (self.conversion_value == duplicate.conversion_value and
                self.product_id == duplicate.product_id and
                abs((self.timestamp - duplicate.timestamp).total_seconds()) < 300):  # 5 minutes
                return duplicate
        
        return None
    
    def _get_country_from_ip(self, ip_address: str) -> Optional[str]:
        """Get country from IP address."""
        try:
            from django.contrib.gis.geoip2 import GeoIP2
            from django.contrib.gis.geoip2.resources import GeoIP2Exception
            
            g = GeoIP2()
            country = g.country(ip_address)
            return country['country_code'] if country else None
        except (GeoIP2Exception, ImportError):
            return None
    
    def get_attribution_summary(self) -> Dict[str, Any]:
        """Get attribution summary for this conversion."""
        return {
            'model': self.attribution_model,
            'score': float(self.attribution_score),
            'touchpoints': self.touchpoints,
            'cost': float(self.cost),
            'revenue': float(self.revenue),
            'profit': float(self.profit),
            'roas': float(self.roas) if self.cost > 0 else 0,
            'roi': float(self.roi) if self.cost > 0 else 0
        }
    
    def get_conversion_path(self) -> List[Dict[str, Any]]:
        """Get conversion path details."""
        path = []
        
        # Add click information if available
        if self.click:
            path.append({
                'type': 'click',
                'timestamp': self.click.timestamp.isoformat(),
                'creative': self.click.creative.name if self.click.creative else None,
                'device': self.click.device_type,
                'cost': float(self.click.actual_cost)
            })
        
        # Add touchpoints
        for touchpoint in self.touchpoints:
            path.append(touchpoint)
        
        # Add conversion
        path.append({
            'type': 'conversion',
            'timestamp': self.timestamp.isoformat(),
            'conversion_type': self.conversion_type,
            'value': float(self.conversion_value),
            'revenue': float(self.revenue)
        })
        
        return path
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this conversion."""
        return {
            'basic_metrics': {
                'conversion_value': float(self.conversion_value),
                'revenue': float(self.revenue),
                'cost': float(self.cost),
                'profit': float(self.profit),
                'quantity': self.quantity
            },
            'efficiency_metrics': {
                'roas': float(self.roas) if self.cost > 0 else 0,
                'roi': float(self.roi) if self.cost > 0 else 0,
                'cpa': float(self.cpa) if self.conversions > 0 else 0,
                'attribution_score': float(self.attribution_score)
            },
            'time_metrics': {
                'time_to_convert': self.time_to_convert,
                'time_on_site': self.time_on_site,
                'pages_viewed': self.pages_viewed
            },
            'quality_metrics': {
                'is_valid': self.is_valid,
                'validation_score': self.validation_score,
                'is_duplicate': bool(self.duplicate_of)
            },
            'lead_metrics': {
                'lead_score': self.lead_score,
                'lead_name': self.lead_name,
                'lead_email': self.lead_email,
                'lead_phone': self.lead_phone
            } if self.conversion_type == 'lead' else None
        }
    
    @property
    def cpa(self) -> Decimal:
        """Calculate cost per acquisition."""
        return self.cost if self.conversions > 0 else Decimal('0')
    
    @property
    def conversions(self) -> int:
        """Return 1 for single conversion."""
        return 1
    
    @property
    def roas(self) -> Decimal:
        """Calculate return on ad spend."""
        return self.revenue / self.cost if self.cost > 0 else Decimal('0')
    
    @property
    def roi(self) -> Decimal:
        """Calculate return on investment."""
        return ((self.revenue - self.cost) / self.cost) if self.cost > 0 else Decimal('0')


class ConversionAggregation(AdvertiserPortalBaseModel):
    """
    Model for aggregated conversion statistics.
    
    This model stores pre-aggregated conversion data for
    efficient reporting and analytics.
    """
    
    # Aggregation Dimensions
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='aggregated_conversions'
    )
    creative = models.ForeignKey(
        'advertiser_portal.Creative',
        on_delete=models.CASCADE,
        related_name='aggregated_conversions',
        null=True,
        blank=True
    )
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='aggregated_conversions'
    )
    date = models.DateField(
        db_index=True,
        help_text="Aggregation date"
    )
    hour = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Hour of day (0-23)"
    )
    
    # Geographic Dimensions
    country = models.CharField(
        max_length=2,
        blank=True,
        db_index=True,
        help_text="Country code"
    )
    device_type = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Device type"
    )
    conversion_type = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Conversion type"
    )
    
    # Aggregated Metrics
    conversions = models.IntegerField(
        default=0,
        help_text="Number of conversions"
    )
    unique_conversions = models.IntegerField(
        default=0,
        help_text="Number of unique conversions"
    )
    total_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Total conversion value"
    )
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Total revenue"
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Total cost"
    )
    total_profit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Total profit"
    )
    
    # Performance Metrics
    avg_conversion_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Average conversion value"
    )
    avg_time_to_convert = models.IntegerField(
        default=0,
        help_text="Average time to convert in seconds"
    )
    validation_score = models.IntegerField(
        default=100,
        help_text="Average validation score"
    )
    
    class Meta:
        db_table = 'conversion_aggregations'
        verbose_name = 'Conversion Aggregation'
        verbose_name_plural = 'Conversion Aggregations'
        unique_together = [
            'campaign', 'date', 'hour', 'country', 'device_type', 'conversion_type'
        ]
        indexes = [
            models.Index(fields=['campaign', 'date']),
            models.Index(fields=['advertiser', 'date']),
            models.Index(fields=['date']),
            models.Index(fields=['country']),
            models.Index(fields=['device_type']),
            models.Index(fields=['conversion_type']),
        ]
    
    def __str__(self) -> str:
        return f"{self.campaign.name} - {self.date}"
    
    def calculate_derived_metrics(self) -> Dict[str, Any]:
        """Calculate derived metrics from aggregated data."""
        if self.conversions == 0:
            return {
                'cpa': 0,
                'roas': 0,
                'roi': 0,
                'profit_margin': 0,
                'conversion_rate': 0
            }
        
        cpa = self.total_cost / self.conversions
        roas = self.total_revenue / self.total_cost if self.total_cost > 0 else Decimal('0')
        roi = ((self.total_revenue - self.total_cost) / self.total_cost) if self.total_cost > 0 else Decimal('0')
        profit_margin = (self.total_profit / self.total_revenue) if self.total_revenue > 0 else Decimal('0')
        
        return {
            'cpa': float(cpa),
            'roas': float(roas),
            'roi': float(roi),
            'profit_margin': float(profit_margin),
            'avg_conversion_value': float(self.avg_conversion_value)
        }


class ConversionPath(AdvertiserPortalBaseModel):
    """
    Model for tracking detailed conversion paths.
    
    This model stores the complete path a user takes
    before converting, including all touchpoints.
    """
    
    conversion = models.ForeignKey(
        Conversion,
        on_delete=models.CASCADE,
        related_name='paths'
    )
    user_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Anonymous user identifier"
    )
    session_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="User session identifier"
    )
    path_data = models.JSONField(
        help_text="Detailed path data including all touchpoints"
    )
    path_length = models.IntegerField(
        default=0,
        help_text="Number of touchpoints in path"
    )
    path_duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total path duration in seconds"
    )
    first_touch = models.JSONField(
        default=dict,
        blank=True,
        help_text="First touchpoint data"
    )
    last_touch = models.JSONField(
        default=dict,
        blank=True,
        help_text="Last touchpoint data"
    )
    
    class Meta:
        db_table = 'conversion_paths'
        verbose_name = 'Conversion Path'
        verbose_name_plural = 'Conversion Paths'
        indexes = [
            models.Index(fields=['conversion']),
            models.Index(fields=['user_id']),
            models.Index(fields=['session_id']),
            models.Index(fields=['path_length']),
        ]
    
    def __str__(self) -> str:
        return f"Path for {self.conversion.conversion_id}"
