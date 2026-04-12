"""
Click Database Model

This module contains the Click model and related models
for tracking ad clicks and user interactions.
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


class Click(AdvertiserPortalBaseModel):
    """
    Main click model for tracking ad clicks and user interactions.
    
    This model stores detailed information about each click
    including user context, click details, and conversion tracking.
    """
    
    # Basic Information
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='click_records',
        help_text="Associated campaign"
    )
    creative = models.ForeignKey(
        'advertiser_portal.Creative',
        on_delete=models.CASCADE,
        related_name='click_set_creative',
        help_text="Associated creative"
    )
    impression = models.ForeignKey(
        'advertiser_portal.Impression',
        on_delete=models.CASCADE,
        related_name='click_set_creative',
        null=True,
        blank=True,
        help_text="Associated impression"
    )
    click_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique click identifier"
    )
    
    # Timestamp Information
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Click timestamp"
    )
    date = models.DateField(
        db_index=True,
        help_text="Click date (for partitioning)"
    )
    hour = models.IntegerField(
        db_index=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Hour of day (0-23)"
    )
    
    # User and Context Information
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
        db_index=True,
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
        db_index=True,
        help_text="Region/state"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
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
    device_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Device model"
    )
    screen_resolution = models.CharField(
        max_length=20,
        blank=True,
        help_text="Screen resolution (e.g., 1920x1080)"
    )
    
    # Click Details
    click_type = models.CharField(
        max_length=50,
        choices=[
            ('click', 'Click'),
            ('view', 'View'),
            ('tap', 'Tap'),
            ('swipe', 'Swipe'),
            ('hover', 'Hover'),
            ('right_click', 'Right Click')
        ],
        default='click',
        help_text="Type of click interaction"
    )
    click_position = models.JSONField(
        default=dict,
        blank=True,
        help_text="Click position coordinates"
    )
    click_element = models.CharField(
        max_length=100,
        blank=True,
        help_text="Element that was clicked"
    )
    landing_page = models.URLField(
        help_text="Landing page URL"
    )
    final_url = models.URLField(
        blank=True,
        help_text="Final URL after redirects"
    )
    
    # Bidding and Cost Information
    bid_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0'),
        help_text="Winning bid price"
    )
    bid_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Bid currency"
    )
    actual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0'),
        help_text="Actual cost to advertiser"
    )
    cost_model = models.CharField(
        max_length=50,
        choices=[
            ('cpc', 'Cost Per Click'),
            ('cpa', 'Cost Per Action'),
            ('cpm', 'Cost Per Mille'),
            ('cpv', 'Cost Per View'),
            ('cpe', 'Cost Per Engagement')
        ],
        default='cpc',
        help_text="Cost model"
    )
    
    # Conversion Tracking
    conversion_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Conversion identifier"
    )
    conversion_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Conversion value"
    )
    conversion_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Conversion currency"
    )
    conversion_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Conversion timestamp"
    )
    
    # Performance Metrics
    time_to_conversion = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Time to conversion in seconds"
    )
    bounce_rate = models.BooleanField(
        default=False,
        help_text="Whether click resulted in bounce"
    )
    dwell_time = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Dwell time in milliseconds"
    )
    pages_viewed = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of pages viewed after click"
    )
    
    # Fraud and Quality Indicators
    fraud_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Fraud risk score (0-100)"
    )
    is_suspicious = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether click is flagged as suspicious"
    )
    is_invalid = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether click is invalid"
    )
    invalid_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reason for invalid click"
    )
    
    # Technical Information
    latency = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Response latency in milliseconds"
    )
    redirect_chain = models.JSONField(
        default=list,
        blank=True,
        help_text="Redirect chain URLs"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    referer = models.URLField(
        blank=True,
        help_text="Referer URL"
    )
    
    # Custom Data
    custom_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom click data"
    )
    tracking_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party tracking data"
    )
    
    class Meta:
        db_table = 'clicks'
        verbose_name = 'Click'
        verbose_name_plural = 'Clicks'
        indexes = [
            models.Index(fields=['campaign', 'date']),
            models.Index(fields=['creative', 'date']),
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['country']),
            models.Index(fields=['device_type']),
            models.Index(fields=['os_family']),
            models.Index(fields=['user_id']),
            models.Index(fields=['session_id']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['conversion_id']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['is_invalid']),
        ]
    
    def __str__(self) -> str:
        return f"{self.click_id} ({self.campaign.name})"
    
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
        
        # Validate costs
        if self.bid_price < 0:
            raise ValidationError("Bid price cannot be negative")
        
        if self.actual_cost < 0:
            raise ValidationError("Actual cost cannot be negative")
        
        # Validate fraud score
        if self.fraud_score is not None and (self.fraud_score < 0 or self.fraud_score > 100):
            raise ValidationError("Fraud score must be between 0 and 100")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set date from timestamp if not set
        if self.timestamp and not self.date:
            self.date = self.timestamp.date()
        
        # Set hour from timestamp if not set
        if self.timestamp and self.hour is None:
            self.hour = self.timestamp.hour
        
        # Generate click ID if not set
        if not self.click_id:
            self.click_id = self.generate_click_id()
        
        # Calculate fraud score
        self.fraud_score = self.calculate_fraud_score()
        
        # Determine if suspicious
        self.is_suspicious = self.fraud_score >= 80
        
        # Set actual cost if not set
        if self.actual_cost == 0 and self.bid_price > 0:
            self.actual_cost = self.bid_price
        
        super().save(*args, **kwargs)
    
    def generate_click_id(self) -> str:
        """Generate unique click identifier."""
        import uuid
        return f"clk_{uuid.uuid4().hex}"
    
    def calculate_fraud_score(self) -> Decimal:
        """Calculate fraud risk score for this click."""
        score = 0
        
        # Geographic anomalies
        if self.country and self.ip_address:
            # Check if IP country matches declared country
            ip_country = self._get_country_from_ip(self.ip_address)
            if ip_country and ip_country != self.country:
                score += 25
        
        # Time-based anomalies
        if self.hour:
            # Suspicious hours (e.g., 2-4 AM)
            if self.hour >= 2 and self.hour <= 4:
                score += 15
        
        # Device anomalies
        if self.device_type and self.os_family:
            # Unusual device-OS combinations
            if self.device_type == 'desktop' and self.os_family == 'ios':
                score += 30
            if self.device_type == 'mobile' and self.os_family == 'windows':
                score += 20
        
        # Click velocity anomalies
        # Check click frequency for this user
        if self.user_id:
            recent_clicks = Click.objects.filter(
                user_id=self.user_id,
                timestamp__gte=timezone.now() - timezone.timedelta(minutes=5)
            ).count()
            
            if recent_clicks > 10:
                score += 30
            elif recent_clicks > 5:
                score += 15
        
        # Conversion anomalies
        if self.conversion_timestamp:
            # Very fast conversion (suspicious)
            time_diff = (self.conversion_timestamp - self.timestamp).total_seconds()
            if time_diff < 2:
                score += 20
            # Very slow conversion (might be delayed)
            elif time_diff > 3600:  # 1 hour
                score += 10
        
        # Technical anomalies
        if self.latency and self.latency < 5:
            score += 15  # Suspiciously fast response
        
        # Referer anomalies
        if self.referer and not self.referer.startswith('http'):
            score += 10
        
        return Decimal(str(min(score, 100)))
    
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
    
    def is_converted(self) -> bool:
        """Check if click resulted in conversion."""
        return bool(self.conversion_id and self.conversion_timestamp)
    
    def get_conversion_rate(self) -> float:
        """Get conversion rate for this click."""
        return 1.0 if self.is_converted() else 0.0
    
    def get_revenue(self) -> Decimal:
        """Calculate revenue from this click."""
        # Simple revenue calculation based on conversion value
        return self.conversion_value
    
    def get_cost(self) -> Decimal:
        """Get cost to advertiser for this click."""
        return self.actual_cost
    
    def get_roi(self) -> float:
        """Calculate ROI for this click."""
        if self.actual_cost == 0:
            return 0.0
        return float(((self.conversion_value - self.actual_cost) / self.actual_cost) * 100)
    
    def get_click_summary(self) -> Dict[str, Any]:
        """Get summary of click details."""
        return {
            'basic': {
                'click_id': self.click_id,
                'timestamp': self.timestamp.isoformat(),
                'click_type': self.click_type,
                'landing_page': self.landing_page,
                'final_url': self.final_url
            },
            'user': {
                'user_id': self.user_id,
                'session_id': self.session_id,
                'device_id': self.device_id
            },
            'geographic': {
                'ip_address': str(self.ip_address),
                'country': self.country,
                'region': self.region,
                'city': self.city,
                'postal_code': self.postal_code,
                'coordinates': str(self.coordinates) if self.coordinates else None,
                'timezone': self.timezone
            },
            'device': {
                'device_type': self.device_type,
                'os_family': self.os_family,
                'os_version': self.os_version,
                'browser': self.browser,
                'browser_version': self.browser_version,
                'carrier': self.carrier,
                'device_model': self.device_model,
                'screen_resolution': self.screen_resolution
            },
            'financial': {
                'bid_price': float(self.bid_price),
                'actual_cost': float(self.actual_cost),
                'cost_model': self.cost_model,
                'conversion_value': float(self.conversion_value),
                'roi': self.get_roi()
            },
            'conversion': {
                'conversion_id': self.conversion_id,
                'conversion_value': float(self.conversion_value),
                'conversion_timestamp': self.conversion_timestamp.isoformat() if self.conversion_timestamp else None,
                'time_to_conversion': self.time_to_conversion,
                'is_converted': self.is_converted()
            },
            'performance': {
                'bounce_rate': self.bounce_rate,
                'dwell_time': self.dwell_time,
                'pages_viewed': self.pages_viewed
            },
            'fraud': {
                'fraud_score': float(self.fraud_score),
                'is_suspicious': self.is_suspicious,
                'is_invalid': self.is_invalid,
                'invalid_reason': self.invalid_reason
            },
            'technical': {
                'latency': self.latency,
                'redirect_chain': self.redirect_chain,
                'user_agent': self.user_agent,
                'referer': self.referer
            }
        }


class ClickAggregation(AdvertiserPortalBaseModel):
    """
    Model for aggregated click statistics.
    
    This model stores pre-aggregated click data for
    efficient reporting and analytics.
    """
    
    # Aggregation Dimensions
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='aggregated_clicks'
    )
    creative = models.ForeignKey(
        'advertiser_portal.Creative',
        on_delete=models.CASCADE,
        related_name='aggregated_clicks',
        null=True,
        blank=True
    )
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='aggregated_clicks'
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
    os_family = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Operating system family"
    )
    
    # Aggregated Metrics
    clicks = models.BigIntegerField(
        default=0,
        help_text="Number of clicks"
    )
    unique_clicks = models.BigIntegerField(
        default=0,
        help_text="Number of unique clicks"
    )
    conversions = models.BigIntegerField(
        default=0,
        help_text="Number of conversions"
    )
    
    # Financial Metrics
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Total cost"
    )
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Total revenue"
    )
    avg_bid_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0'),
        help_text="Average bid price"
    )
    avg_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0'),
        help_text="Average cost per click"
    )
    
    # Performance Metrics
    avg_conversion_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Average conversion value"
    )
    avg_time_to_conversion = models.IntegerField(
        default=0,
        help_text="Average time to conversion in seconds"
    )
    bounce_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Bounce rate percentage"
    )
    avg_dwell_time = models.IntegerField(
        default=0,
        help_text="Average dwell time in milliseconds"
    )
    
    # Quality Metrics
    fraud_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Average fraud score"
    )
    suspicious_clicks = models.BigIntegerField(
        default=0,
        help_text="Number of suspicious clicks"
    )
    invalid_clicks = models.BigIntegerField(
        default=0,
        help_text="Number of invalid clicks"
    )
    
    class Meta:
        db_table = 'click_aggregations'
        verbose_name = 'Click Aggregation'
        verbose_name_plural = 'Click Aggregations'
        unique_together = [
            'campaign', 'date', 'hour', 'country', 'device_type', 'os_family'
        ]
        indexes = [
            models.Index(fields=['campaign', 'date']),
            models.Index(fields=['advertiser', 'date']),
            models.Index(fields=['date']),
            models.Index(fields=['country']),
            models.Index(fields=['device_type']),
            models.Index(fields=['os_family']),
        ]
    
    def __str__(self) -> str:
        return f"{self.campaign.name} - {self.date}"
    
    def calculate_derived_metrics(self) -> Dict[str, Any]:
        """Calculate derived metrics from aggregated data."""
        if self.clicks == 0:
            return {
                'ctr': 0,
                'cpc': 0,
                'cpa': 0,
                'conversion_rate': 0,
                'roi': 0,
                'roas': 0,
                'avg_conversion_value': 0,
                'bounce_rate': 0,
                'suspicious_rate': 0,
                'invalid_rate': 0
            }
        
        # Click metrics
        cpc = self.total_cost / self.clicks
        cpa = self.total_cost / self.conversions if self.conversions > 0 else 0
        
        # Conversion metrics
        conversion_rate = (self.conversions / self.clicks) * 100
        avg_conversion_value = self.total_revenue / self.conversions if self.conversions > 0 else 0
        
        # ROI metrics
        roi = ((self.total_revenue - self.total_cost) / self.total_cost * 100) if self.total_cost > 0 else 0
        roas = (self.total_revenue / self.total_cost) if self.total_cost > 0 else 0
        
        # Quality metrics
        suspicious_rate = (self.suspicious_clicks / self.clicks) * 100
        invalid_rate = (self.invalid_clicks / self.clicks) * 100
        
        return {
            'cpc': float(cpc),
            'cpa': float(cpa),
            'conversion_rate': float(conversion_rate),
            'roi': float(roi),
            'roas': float(roas),
            'avg_conversion_value': float(avg_conversion_value),
            'bounce_rate': float(self.bounce_rate),
            'suspicious_rate': float(suspicious_rate),
            'invalid_rate': float(invalid_rate)
        }


class ClickPixel(AdvertiserPortalBaseModel):
    """
    Model for tracking click pixels and tracking beacons.
    """
    
    click = models.ForeignKey(
        Click,
        on_delete=models.CASCADE,
        related_name='pixels'
    )
    pixel_type = models.CharField(
        max_length=50,
        choices=[
            ('landing', 'Landing Page'),
            ('conversion', 'Conversion'),
            ('retargeting', 'Retargeting'),
            ('analytics', 'Analytics'),
            ('custom', 'Custom')
        ],
        help_text="Type of pixel"
    )
    pixel_url = models.URLField(
        help_text="Pixel URL"
    )
    fired_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When pixel was fired"
    )
    success = models.BooleanField(
        default=False,
        help_text="Whether pixel fired successfully"
    )
    response_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP response code"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if any"
    )
    
    class Meta:
        db_table = 'click_pixels'
        verbose_name = 'Click Pixel'
        verbose_name_plural = 'Click Pixels'
        indexes = [
            models.Index(fields=['click', 'pixel_type']),
            models.Index(fields=['fired_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.pixel_type} - {self.click.click_id}"
