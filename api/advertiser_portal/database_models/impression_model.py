"""
Impression Database Model

This module contains the Impression model and related models
for tracking ad impressions and delivery metrics.
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


class Impression(AdvertiserPortalBaseModel):
    """
    Main impression model for tracking ad impressions.
    
    This model stores detailed information about each ad impression
    including user context, delivery details, and performance metrics.
    """
    
    # Basic Information
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='impression_set',
        help_text="Associated campaign"
    )
    creative = models.ForeignKey(
        'advertiser_portal.Creative',
        on_delete=models.CASCADE,
        related_name='impression_set',
        help_text="Associated creative"
    )
    impression_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique impression identifier"
    )
    request_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Ad request identifier"
    )
    
    # Timestamp Information
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Impression timestamp"
    )
    date = models.DateField(
        db_index=True,
        help_text="Impression date (for partitioning)"
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
    
    # Ad and Placement Information
    ad_unit = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Ad unit identifier"
    )
    placement = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Placement identifier"
    )
    position = models.IntegerField(
        null=True,
        blank=True,
        help_text="Ad position in placement"
    )
    size = models.CharField(
        max_length=20,
        blank=True,
        help_text="Ad size (e.g., 300x250)"
    )
    format_type = models.CharField(
        max_length=50,
        choices=[
            ('banner', 'Banner'),
            ('video', 'Video'),
            ('native', 'Native'),
            ('interstitial', 'Interstitial'),
            ('rewarded', 'Rewarded')
        ],
        db_index=True,
        help_text="Ad format type"
    )
    
    # Bidding and Auction Information
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
    auction_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Auction identifier"
    )
    auction_type = models.CharField(
        max_length=50,
        choices=[
            ('first_price', 'First Price'),
            ('second_price', 'Second Price'),
            ('fixed', 'Fixed Price')
        ],
        default='second_price',
        help_text="Auction type"
    )
    competition_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of competing bids"
    )
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Win rate percentage"
    )
    
    # Quality and Performance
    viewability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Viewability percentage"
    )
    visibility = models.CharField(
        max_length=50,
        choices=[
            ('visible', 'Visible'),
            ('partially_visible', 'Partially Visible'),
            ('not_visible', 'Not Visible'),
            ('unknown', 'Unknown')
        ],
        default='unknown',
        help_text="Visibility status"
    )
    dwell_time = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Dwell time in milliseconds"
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
        help_text="Whether impression is flagged as suspicious"
    )
    is_invalid = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether impression is invalid"
    )
    invalid_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reason for invalid impression"
    )
    
    # Technical Information
    latency = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Response latency in milliseconds"
    )
    error_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Error code if any"
    )
    server_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Server identifier"
    )
    partner_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Partner identifier"
    )
    
    # Contextual Information
    page_url = models.URLField(
        blank=True,
        help_text="Page URL where ad was shown"
    )
    referrer_url = models.URLField(
        blank=True,
        help_text="Referrer URL"
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Page keywords"
    )
    categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Page categories"
    )
    
    # Custom Data
    custom_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom impression data"
    )
    tracking_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party tracking data"
    )
    
    class Meta:
        db_table = 'impressions'
        verbose_name = 'Impression'
        verbose_name_plural = 'Impressions'
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
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['is_invalid']),
        ]
    
    def __str__(self) -> str:
        return f"{self.impression_id} ({self.campaign.name})"
    
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
        
        # Validate bid price
        if self.bid_price < 0:
            raise ValidationError("Bid price cannot be negative")
        
        # Validate viewability
        if self.viewability is not None and (self.viewability < 0 or self.viewability > 100):
            raise ValidationError("Viewability must be between 0 and 100")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set date from timestamp if not set
        if self.timestamp and not self.date:
            self.date = self.timestamp.date()
        
        # Set hour from timestamp if not set
        if self.timestamp and self.hour is None:
            self.hour = self.timestamp.hour
        
        # Generate impression ID if not set
        if not self.impression_id:
            self.impression_id = self.generate_impression_id()
        
        # Calculate fraud score
        self.fraud_score = self.calculate_fraud_score()
        
        # Determine if suspicious
        self.is_suspicious = self.fraud_score >= 80
        
        super().save(*args, **kwargs)
    
    def generate_impression_id(self) -> str:
        """Generate unique impression identifier."""
        import uuid
        return f"imp_{uuid.uuid4().hex}"
    
    def calculate_fraud_score(self) -> Decimal:
        """Calculate fraud risk score for this impression."""
        score = 0
        
        # Geographic anomalies
        if self.country and self.ip_address:
            # Check if IP country matches declared country
            ip_country = self._get_country_from_ip(self.ip_address)
            if ip_country and ip_country != self.country:
                score += 30
        
        # Time-based anomalies
        if self.hour:
            # Suspicious hours (e.g., 2-4 AM)
            if self.hour >= 2 and self.hour <= 4:
                score += 20
        
        # Device anomalies
        if self.device_type and self.os_family:
            # Unusual device-OS combinations
            if self.device_type == 'desktop' and self.os_family == 'ios':
                score += 25
            if self.device_type == 'mobile' and self.os_family == 'windows':
                score += 15
        
        # Frequency anomalies
        # Check impression frequency for this user
        if self.user_id:
            recent_impressions = Impression.objects.filter(
                user_id=self.user_id,
                timestamp__gte=timezone.now() - timezone.timedelta(minutes=5)
            ).count()
            
            if recent_impressions > 10:
                score += 20
            elif recent_impressions > 5:
                score += 10
        
        # Technical anomalies
        if self.latency and self.latency < 10:
            score += 10  # Suspiciously fast response
        
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
    
    def is_viewable(self) -> bool:
        """Check if impression is considered viewable."""
        return (
            self.visibility == 'visible' and
            self.viewability is not None and
            self.viewability >= 50
        )
    
    def get_revenue(self) -> Decimal:
        """Calculate revenue from this impression."""
        # Simple revenue calculation based on bid price
        # In practice, this would involve more complex pricing models
        return self.bid_price
    
    def get_cost(self) -> Decimal:
        """Get cost to advertiser for this impression."""
        # For now, cost equals bid price
        # In practice, this might differ based on auction model
        return self.bid_price
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of impression context."""
        return {
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
            'placement': {
                'ad_unit': self.ad_unit,
                'placement': self.placement,
                'position': self.position,
                'size': self.size,
                'format_type': self.format_type
            },
            'auction': {
                'bid_price': float(self.bid_price),
                'bid_currency': self.bid_currency,
                'auction_id': self.auction_id,
                'auction_type': self.auction_type,
                'competition_level': self.competition_level,
                'win_rate': float(self.win_rate)
            },
            'quality': {
                'viewability': float(self.viewability) if self.viewability else None,
                'visibility': self.visibility,
                'dwell_time': self.dwell_time,
                'latency': self.latency
            },
            'fraud': {
                'fraud_score': float(self.fraud_score),
                'is_suspicious': self.is_suspicious,
                'is_invalid': self.is_invalid,
                'invalid_reason': self.invalid_reason
            }
        }


class ImpressionAggregation(AdvertiserPortalBaseModel):
    """
    Model for aggregated impression statistics.
    
    This model stores pre-aggregated impression data for
    efficient reporting and analytics.
    """
    
    # Aggregation Dimensions
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='aggregated_impressions'
    )
    creative = models.ForeignKey(
        'advertiser_portal.Creative',
        on_delete=models.CASCADE,
        related_name='aggregated_impressions',
        null=True,
        blank=True
    )
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='aggregated_impressions'
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
    region = models.CharField(
        max_length=100,
        blank=True,
        help_text="Region"
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
    impressions = models.BigIntegerField(
        default=0,
        help_text="Number of impressions"
    )
    unique_impressions = models.BigIntegerField(
        default=0,
        help_text="Number of unique impressions"
    )
    viewable_impressions = models.BigIntegerField(
        default=0,
        help_text="Number of viewable impressions"
    )
    clicks = models.BigIntegerField(
        default=0,
        help_text="Number of clicks"
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
    
    # Performance Metrics
    avg_viewability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Average viewability percentage"
    )
    avg_dwell_time = models.IntegerField(
        default=0,
        help_text="Average dwell time in milliseconds"
    )
    fraud_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Average fraud score"
    )
    
    # Quality Metrics
    invalid_impressions = models.BigIntegerField(
        default=0,
        help_text="Number of invalid impressions"
    )
    suspicious_impressions = models.BigIntegerField(
        default=0,
        help_text="Number of suspicious impressions"
    )
    
    class Meta:
        db_table = 'impression_aggregations'
        verbose_name = 'Impression Aggregation'
        verbose_name_plural = 'Impression Aggregations'
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
        if self.impressions == 0:
            return {
                'ctr': 0,
                'cpc': 0,
                'cpm': 0,
                'conversion_rate': 0,
                'viewability_rate': 0,
                'invalid_rate': 0,
                'suspicious_rate': 0,
                'roi': 0,
                'roas': 0
            }
        
        # Click metrics
        ctr = (self.clicks / self.impressions) * 100
        cpc = self.total_cost / self.clicks if self.clicks > 0 else 0
        cpm = (self.total_cost / self.impressions) * 1000
        
        # Conversion metrics
        conversion_rate = (self.conversions / self.clicks) * 100 if self.clicks > 0 else 0
        cpa = self.total_cost / self.conversions if self.conversions > 0 else 0
        
        # Viewability metrics
        viewability_rate = (self.viewable_impressions / self.impressions) * 100
        invalid_rate = (self.invalid_impressions / self.impressions) * 100
        suspicious_rate = (self.suspicious_impressions / self.impressions) * 100
        
        # ROI metrics
        roi = ((self.total_revenue - self.total_cost) / self.total_cost * 100) if self.total_cost > 0 else 0
        roas = (self.total_revenue / self.total_cost) if self.total_cost > 0 else 0
        
        return {
            'ctr': float(ctr),
            'cpc': float(cpc),
            'cpm': float(cpm),
            'cpa': float(cpa),
            'conversion_rate': float(conversion_rate),
            'viewability_rate': float(viewability_rate),
            'invalid_rate': float(invalid_rate),
            'suspicious_rate': float(suspicious_rate),
            'roi': float(roi),
            'roas': float(roas)
        }


class ImpressionPixel(AdvertiserPortalBaseModel):
    """
    Model for tracking impression pixels and beacons.
    """
    
    impression = models.ForeignKey(
        Impression,
        on_delete=models.CASCADE,
        related_name='pixels'
    )
    pixel_type = models.CharField(
        max_length=50,
        choices=[
            ('viewable', 'Viewable'),
            ('click', 'Click'),
            ('conversion', 'Conversion'),
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
        db_table = 'impression_pixels'
        verbose_name = 'Impression Pixel'
        verbose_name_plural = 'Impression Pixels'
        indexes = [
            models.Index(fields=['impression', 'pixel_type']),
            models.Index(fields=['fired_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.pixel_type} - {self.impression.impression_id}"
