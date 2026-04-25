"""
Campaign Models for Advertiser Portal

This module contains models for managing advertising campaigns,
including creatives, targeting, bidding, and scheduling.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class AdCampaign(models.Model):
    """
    Model for managing advertising campaigns.
    
    Stores campaign information including objectives,
    budgets, targeting, and performance data.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='campaigns',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this campaign belongs to')
    )
    
    # Campaign details
    name = models.CharField(
        _('Campaign Name'),
        max_length=200,
        db_index=True,
        help_text=_('Campaign name')
    )
    
    description = models.TextField(
        _('Description'),
        null=True,
        blank=True,
        help_text=_('Campaign description')
    )
    
    objective = models.CharField(
        _('Campaign Objective'),
        max_length=20,
        choices=[
            ('cpi', _('Cost Per Install')),
            ('cpa', _('Cost Per Action')),
            ('cpe', _('Cost Per Engagement')),
            ('cpl', _('Cost Per Lead')),
            ('cps', _('Cost Per Sale')),
            ('cpm', _('Cost Per Mille')),
            ('cpc', _('Cost Per Click')),
            ('brand_awareness', _('Brand Awareness')),
            ('reach', _('Reach')),
            ('engagement', _('Engagement')),
            ('conversions', _('Conversions')),
        ],
        default='cpa',
        db_index=True,
        help_text=_('Primary campaign objective')
    )
    
    # Budget information
    budget_total = models.DecimalField(
        _('Total Budget'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Total campaign budget')
    )
    
    budget_daily = models.DecimalField(
        _('Daily Budget'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Daily budget limit')
    )
    
    # Status and dates
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('pending', _('Pending')),
            ('active', _('Active')),
            ('paused', _('Paused')),
            ('completed', _('Completed')),
            ('cancelled', _('Cancelled')),
            ('suspended', _('Suspended')),
        ],
        default='draft',
        db_index=True,
        help_text=_('Current campaign status')
    )
    
    start_date = models.DateTimeField(
        _('Start Date'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Campaign start date and time')
    )
    
    end_date = models.DateTimeField(
        _('End Date'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Campaign end date and time')
    )
    
    # Campaign settings
    auto_optimize = models.BooleanField(
        _('Auto Optimize'),
        default=False,
        help_text=_('Whether to automatically optimize campaign')
    )
    
    frequency_capping = models.IntegerField(
        _('Frequency Capping'),
        null=True,
        blank=True,
        help_text=_('Maximum impressions per user per day')
    )
    
    delivery_method = models.CharField(
        _('Delivery Method'),
        max_length=20,
        choices=[
            ('standard', _('Standard')),
            ('accelerated', _('Accelerated')),
            ('even', _('Even')),
        ],
        default='standard',
        help_text=_('Campaign delivery method')
    )
    
    # Performance tracking
    total_impressions = models.IntegerField(
        _('Total Impressions'),
        default=0,
        help_text=_('Total impressions delivered')
    )
    
    total_clicks = models.IntegerField(
        _('Total Clicks'),
        default=0,
        help_text=_('Total clicks received')
    )
    
    total_conversions = models.IntegerField(
        _('Total Conversions'),
        default=0,
        help_text=_('Total conversions generated')
    )
    
    total_spend = models.DecimalField(
        _('Total Spend'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Total amount spent')
    )
    
    # Quality metrics
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
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this campaign was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this campaign was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_campaign'
        verbose_name = _('Ad Campaign')
        verbose_name_plural = _('Ad Campaigns')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_421'),
            models.Index(fields=['objective', 'status'], name='idx_objective_status_422'),
            models.Index(fields=['start_date', 'end_date'], name='idx_start_date_end_date_423'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_424'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate dates
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError(_('Start date must be before end date'))
        
        # Validate budget
        if self.budget_total and self.budget_total <= 0:
            raise ValidationError(_('Total budget must be positive'))
        
        if self.budget_daily and self.budget_daily <= 0:
            raise ValidationError(_('Daily budget must be positive'))
        
        if self.budget_daily and self.budget_total and self.budget_daily > self.budget_total:
            raise ValidationError(_('Daily budget cannot exceed total budget'))
        
        # Validate frequency capping
        if self.frequency_capping and self.frequency_capping < 1:
            raise ValidationError(_('Frequency capping must be at least 1'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Auto-calculate performance metrics
        self._calculate_performance_metrics()
        
        super().save(*args, **kwargs)
    
    def _calculate_performance_metrics(self):
        """Calculate performance metrics."""
        if self.total_impressions > 0:
            self.ctr = (self.total_clicks / self.total_impressions) * 100
        
        if self.total_clicks > 0:
            self.conversion_rate = (self.total_conversions / self.total_clicks) * 100
            self.cpa = self.total_spend / self.total_conversions if self.total_conversions > 0 else 0
        elif self.total_spend > 0:
            self.cpa = self.total_spend  # No conversions, CPA equals total spend
    
    @property
    def is_active(self) -> bool:
        """Check if campaign is currently active."""
        now = timezone.now()
        return (
            self.status == 'active' and
            self.start_date and self.start_date <= now and
            (not self.end_date or self.end_date >= now)
        )
    
    @property
    def is_expired(self) -> bool:
        """Check if campaign has expired."""
        if self.end_date:
            return timezone.now() > self.end_date
        return False
    
    @property
    def days_remaining(self) -> int:
        """Get days remaining until campaign ends."""
        if self.end_date:
            delta = self.end_date - timezone.now()
            return max(delta.days, 0)
        return 0
    
    @property
    def budget_remaining(self) -> float:
        """Get remaining budget."""
        return float(self.budget_total - self.total_spend)
    
    @property
    def daily_budget_remaining(self) -> float:
        """Get remaining daily budget."""
        return float(self.budget_daily - self.get_daily_spend())
    
    def get_daily_spend(self) -> float:
        """Get spend for today."""
        from django.db.models import Sum
        
        today = timezone.now().date()
        from .billing import CampaignSpend
        
        daily_spend = CampaignSpend.objects.filter(
            campaign=self,
            date=today
        ).aggregate(total=Sum('spend_amount'))['total'] or 0
        
        return float(daily_spend)
    
    def get_active_offers(self):
        """Get active offers for this campaign."""
        return self.offers.filter(
            status='active',
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        )
    
    def get_performance_summary(self) -> dict:
        """Get performance summary."""
        return {
            'total_impressions': self.total_impressions,
            'total_clicks': self.total_clicks,
            'total_conversions': self.total_conversions,
            'total_spend': float(self.total_spend),
            'ctr': float(self.ctr),
            'conversion_rate': float(self.conversion_rate),
            'cpa': float(self.cpa),
            'budget_remaining': self.budget_remaining,
            'budget_utilization': (self.total_spend / self.budget_total * 100) if self.budget_total > 0 else 0,
            'days_remaining': self.days_remaining,
            'is_active': self.is_active,
            'is_expired': self.is_expired,
        }


class CampaignCreative(models.Model):
    """
    Model for managing campaign creatives.
    
    Stores creative assets including banners, videos,
    and native ads.
    """
    
    # Core relationships
    campaign = models.ForeignKey(
        AdCampaign,
        on_delete=models.CASCADE,
        related_name='creatives',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this creative belongs to')
    )
    
    # Creative details
    name = models.CharField(
        _('Creative Name'),
        max_length=200,
        help_text=_('Creative name for identification')
    )
    
    creative_type = models.CharField(
        _('Creative Type'),
        max_length=20,
        choices=[
            ('banner', _('Banner')),
            ('video', _('Video')),
            ('native', _('Native')),
            ('interstitial', _('Interstitial')),
            ('rewarded', _('Rewarded')),
            ('playable', _('Playable')),
        ],
        default='banner',
        db_index=True,
        help_text=_('Type of creative')
    )
    
    # Creative assets
    file = models.FileField(
        _('Creative File'),
        upload_to='campaign_creatives/',
        help_text=_('Creative asset file')
    )
    
    file_url = models.URLField(
        _('File URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('External URL for creative file')
    )
    
    # Banner-specific fields
    width = models.IntegerField(
        _('Width'),
        null=True,
        blank=True,
        help_text=_('Creative width in pixels')
    )
    
    height = models.IntegerField(
        _('Height'),
        null=True,
        blank=True,
        help_text=_('Creative height in pixels')
    )
    
    # Video-specific fields
    video_duration = models.IntegerField(
        _('Video Duration'),
        null=True,
        blank=True,
        help_text=_('Video duration in seconds')
    )
    
    video_thumbnail = models.ImageField(
        _('Video Thumbnail'),
        upload_to='video_thumbnails/',
        null=True,
        blank=True,
        help_text=_('Video thumbnail image')
    )
    
    # Native ad fields
    headline = models.CharField(
        _('Headline'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Native ad headline')
    )
    
    description = models.TextField(
        _('Description'),
        null=True,
        blank=True,
        help_text=_('Native ad description')
    )
    
    cta_text = models.CharField(
        _('CTA Text'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Call to action text')
    )
    
    brand_name = models.CharField(
        _('Brand Name'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Brand name for native ads')
    )
    
    # Status and approval
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('pending_review', _('Pending Review')),
            ('approved', _('Approved')),
            ('rejected', _('Rejected')),
            ('active', _('Active')),
            ('paused', _('Paused')),
            ('archived', _('Archived')),
        ],
        default='draft',
        db_index=True,
        help_text=_('Current creative status')
    )
    
    is_approved = models.BooleanField(
        _('Is Approved'),
        default=False,
        db_index=True,
        help_text=_('Whether creative has been approved')
    )
    
    rejection_reason = models.TextField(
        _('Rejection Reason'),
        null=True,
        blank=True,
        help_text=_('Reason for rejection if applicable')
    )
    
    # Performance tracking
    impressions = models.IntegerField(
        _('Impressions'),
        default=0,
        help_text=_('Total impressions delivered')
    )
    
    clicks = models.IntegerField(
        _('Clicks'),
        default=0,
        help_text=_('Total clicks received')
    )
    
    conversions = models.IntegerField(
        _('Conversions'),
        default=0,
        help_text=_('Total conversions generated')
    )
    
    ctr = models.DecimalField(
        _('Click Through Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Click through rate percentage')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this creative was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this creative was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_campaign_creative'
        verbose_name = _('Campaign Creative')
        verbose_name_plural = _('Campaign Creatives')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', 'status'], name='idx_campaign_status_425'),
            models.Index(fields=['creative_type', 'status'], name='idx_creative_type_status_426'),
            models.Index(fields=['is_approved', 'status'], name='idx_is_approved_status_427'),
            models.Index(fields=['created_at'], name='idx_created_at_428'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.campaign.name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate dimensions
        if self.width and self.width <= 0:
            raise ValidationError(_('Width must be positive'))
        
        if self.height and self.height <= 0:
            raise ValidationError(_('Height must be positive'))
        
        # Validate video duration
        if self.video_duration and self.video_duration <= 0:
            raise ValidationError(_('Video duration must be positive'))
        
        # Validate file or URL
        if not self.file and not self.file_url:
            raise ValidationError(_('Either file or file URL must be provided'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Auto-calculate CTR
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        super().save(*args, **kwargs)
    
    @property
    def is_banner(self) -> bool:
        """Check if creative is a banner."""
        return self.creative_type == 'banner'
    
    @property
    def is_video(self) -> bool:
        """Check if creative is a video."""
        return self.creative_type == 'video'
    
    @property
    def is_native(self) -> bool:
        """Check if creative is a native ad."""
        return self.creative_type == 'native'
    
    @property
    def dimensions_display(self) -> str:
        """Get dimensions display string."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "N/A"
    
    @property
    def file_size_display(self) -> str:
        """Get human-readable file size."""
        if self.file:
            size = self.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "N/A"
    
    def get_performance_metrics(self) -> dict:
        """Get performance metrics."""
        return {
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'ctr': float(self.ctr),
            'conversion_rate': (self.conversions / self.clicks * 100) if self.clicks > 0 else 0,
            'is_active': self.status == 'active',
            'is_approved': self.is_approved,
        }


class CampaignTargeting(models.Model):
    """
    Model for managing campaign targeting criteria.
    
    Stores targeting rules for demographics, geography,
    devices, and interests.
    """
    
    # Core relationship
    campaign = models.OneToOneField(
        AdCampaign,
        on_delete=models.CASCADE,
        related_name='targeting',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this targeting belongs to')
    )
    
    # Geographic targeting
    countries = models.JSONField(
        _('Countries'),
        default=list,
        blank=True,
        help_text=_('Target countries (ISO 3166-1 alpha-2 codes)')
    )
    
    regions = models.JSONField(
        _('Regions'),
        default=list,
        blank=True,
        help_text=_('Target regions/states')
    )
    
    cities = models.JSONField(
        _('Cities'),
        default=list,
        blank=True,
        help_text=_('Target cities')
    )
    
    postal_codes = models.JSONField(
        _('Postal Codes'),
        default=list,
        blank=True,
        help_text=_('Target postal codes')
    )
    
    # Device targeting
    devices = models.JSONField(
        _('Devices'),
        default=list,
        blank=True,
        help_text=_('Target device types')
    )
    
    operating_systems = models.JSONField(
        _('Operating Systems'),
        default=list,
        blank=True,
        help_text=_('Target operating systems')
    )
    
    browsers = models.JSONField(
        _('Browsers'),
        default=list,
        blank=True,
        help_text=_('Target browsers')
    )
    
    # Demographic targeting
    min_age = models.IntegerField(
        _('Minimum Age'),
        null=True,
        blank=True,
        help_text=_('Minimum age for targeting')
    )
    
    max_age = models.IntegerField(
        _('Maximum Age'),
        null=True,
        blank=True,
        help_text=_('Maximum age for targeting')
    )
    
    genders = models.JSONField(
        _('Genders'),
        default=list,
        blank=True,
        help_text=_('Target genders')
    )
    
    languages = models.JSONField(
        _('Languages'),
        default=list,
        blank=True,
        help_text=_('Target languages')
    )
    
    # Interest and behavior targeting
    interests = models.JSONField(
        _('Interests'),
        default=list,
        blank=True,
        help_text=_('Target interests and categories')
    )
    
    keywords = models.JSONField(
        _('Keywords'),
        default=list,
        blank=True,
        help_text=_('Target keywords')
    )
    
    behaviors = models.JSONField(
        _('Behaviors'),
        default=list,
        blank=True,
        help_text=_('Target user behaviors')
    )
    
    # Placement targeting
    placements = models.JSONField(
        _('Placements'),
        default=list,
        blank=True,
        help_text=_('Target ad placements')
    )
    
    exclude_placements = models.JSONField(
        _('Exclude Placements'),
        default=list,
        blank=True,
        help_text=_('Placements to exclude')
    )
    
    # Time targeting
    schedule_hours = models.JSONField(
        _('Schedule Hours'),
        default=list,
        blank=True,
        help_text=_('Hours of day to run (0-23)')
    )
    
    schedule_days = models.JSONField(
        _('Schedule Days'),
        default=list,
        blank=True,
        help_text=_('Days of week to run (0-6, 0=Monday)')
    )
    
    timezone = models.CharField(
        _('Timezone'),
        max_length=50,
        default='UTC',
        help_text=_('Campaign timezone for scheduling')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this targeting was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this targeting was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_campaign_targeting'
        verbose_name = _('Campaign Targeting')
        verbose_name_plural = _('Campaign Targeting')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign'], name='idx_campaign_429'),
            models.Index(fields=['created_at'], name='idx_created_at_430'),
        ]
    
    def __str__(self):
        return f"Targeting: {self.campaign.name}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate age range
        if self.min_age and self.min_age < 13:
            raise ValidationError(_('Minimum age must be at least 13'))
        
        if self.max_age and self.max_age < 13:
            raise ValidationError(_('Maximum age must be at least 13'))
        
        if self.min_age and self.max_age and self.min_age > self.max_age:
            raise ValidationError(_('Minimum age cannot be greater than maximum age'))
        
        # Validate hours
        if self.schedule_hours:
            for hour in self.schedule_hours:
                if not isinstance(hour, int) or hour < 0 or hour > 23:
                    raise ValidationError(_('Schedule hours must be integers between 0 and 23'))
        
        # Validate days
        if self.schedule_days:
            for day in self.schedule_days:
                if not isinstance(day, int) or day < 0 or day > 6:
                    raise ValidationError(_('Schedule days must be integers between 0 and 6'))
    
    @property
    def has_geographic_targeting(self) -> bool:
        """Check if geographic targeting is configured."""
        return bool(self.countries or self.regions or self.cities or self.postal_codes)
    
    @property
    def has_device_targeting(self) -> bool:
        """Check if device targeting is configured."""
        return bool(self.devices or self.operating_systems or self.browsers)
    
    @property
    def has_demographic_targeting(self) -> bool:
        """Check if demographic targeting is configured."""
        return bool(self.min_age or self.max_age or self.genders or self.languages)
    
    @property
    def has_behavioral_targeting(self) -> bool:
        """Check if behavioral targeting is configured."""
        return bool(self.interests or self.keywords or self.behaviors)
    
    @property
    def has_time_targeting(self) -> bool:
        """Check if time-based targeting is configured."""
        return bool(self.schedule_hours or self.schedule_days)
    
    def matches_user(self, user_data: dict) -> bool:
        """Check if user matches targeting criteria."""
        # Geographic check
        if self.countries and user_data.get('country') not in self.countries:
            return False
        
        # Age check
        user_age = user_data.get('age')
        if user_age:
            if self.min_age and user_age < self.min_age:
                return False
            if self.max_age and user_age > self.max_age:
                return False
        
        # Device check
        if self.devices and user_data.get('device_type') not in self.devices:
            return False
        
        return True
    
    def get_targeting_summary(self) -> dict:
        """Get summary of targeting configuration."""
        return {
            'geographic': {
                'countries': self.countries or [],
                'regions': self.regions or [],
                'cities': self.cities or [],
                'postal_codes': self.postal_codes or [],
                'has_targeting': self.has_geographic_targeting,
            },
            'demographic': {
                'min_age': self.min_age,
                'max_age': self.max_age,
                'genders': self.genders or [],
                'languages': self.languages or [],
                'has_targeting': self.has_demographic_targeting,
            },
            'device': {
                'devices': self.devices or [],
                'operating_systems': self.operating_systems or [],
                'browsers': self.browsers or [],
                'has_targeting': self.has_device_targeting,
            },
            'behavioral': {
                'interests': self.interests or [],
                'keywords': self.keywords or [],
                'behaviors': self.behaviors or [],
                'has_targeting': self.has_behavioral_targeting,
            },
            'placement': {
                'placements': self.placements or [],
                'exclude_placements': self.exclude_placements or [],
            },
            'time': {
                'schedule_hours': self.schedule_hours or [],
                'schedule_days': self.schedule_days or [],
                'timezone': self.timezone,
                'has_targeting': self.has_time_targeting,
            },
        }


class CampaignBid(models.Model):
    """
    Model for managing campaign bidding strategy.
    
    Stores bidding configuration including bid types,
    amounts, and optimization settings.
    """
    
    # Core relationship
    campaign = models.OneToOneField(
        AdCampaign,
        on_delete=models.CASCADE,
        related_name='bidding',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this bidding belongs to')
    )
    
    # Bidding configuration
    bid_type = models.CharField(
        _('Bid Type'),
        max_length=20,
        choices=[
            ('cpc', _('Cost Per Click')),
            ('cpm', _('Cost Per Mille')),
            ('cpa', _('Cost Per Action')),
            ('cpi', _('Cost Per Install')),
            ('cpe', _('Cost Per Engagement')),
            ('cpl', _('Cost Per Lead')),
            ('cps', _('Cost Per Sale')),
            ('auto', _('Automatic')),
        ],
        default='cpc',
        help_text=_('Type of bidding')
    )
    
    bid_amount = models.DecimalField(
        _('Bid Amount'),
        max_digits=8,
        decimal_places=2,
        help_text=_('Bid amount')
    )
    
    max_bid = models.DecimalField(
        _('Maximum Bid'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum bid amount')
    )
    
    min_bid = models.DecimalField(
        _('Minimum Bid'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Minimum bid amount')
    )
    
    # Optimization settings
    auto_optimize = models.BooleanField(
        _('Auto Optimize'),
        default=False,
        help_text=_('Whether to automatically optimize bids')
    )
    
    optimization_goal = models.CharField(
        _('Optimization Goal'),
        max_length=20,
        choices=[
            ('conversions', _('Conversions')),
            ('clicks', _('Clicks')),
            ('impressions', _('Impressions')),
            ('revenue', _('Revenue')),
            ('roi', _('Return on Investment')),
        ],
        default='conversions',
        help_text=_('Optimization goal for auto-bidding')
    )
    
    target_cpa = models.DecimalField(
        _('Target CPA'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Target cost per action')
    )
    
    target_roas = models.DecimalField(
        _('Target ROAS'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Target return on ad spend')
    )
    
    # Budget pacing
    budget_pacing = models.BooleanField(
        _('Budget Pacing'),
        default=True,
        help_text=_('Whether to pace budget throughout campaign period')
    )
    
    pacing_type = models.CharField(
        _('Pacing Type'),
        max_length=20,
        choices=[
            ('even', _('Even')),
            ('front_loaded', _('Front Loaded')),
            ('back_loaded', _('Back Loaded')),
            ('accelerated', _('Accelerated')),
        ],
        default='even',
        help_text=_('Budget pacing type')
    )
    
    # Advanced settings
    bid_adjustments = models.JSONField(
        _('Bid Adjustments'),
        default=dict,
        blank=True,
        help_text=_('Bid adjustments by segment')
    )
    
    frequency_capping = models.IntegerField(
        _('Frequency Capping'),
        null=True,
        blank=True,
        help_text=_('Maximum bids per user per day')
    )
    
    dayparting = models.JSONField(
        _('Dayparting'),
        default=dict,
        blank=True,
        help_text=_('Bid adjustments by time of day')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this bidding was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this bidding was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_campaign_bid'
        verbose_name = _('Campaign Bid')
        verbose_name_plural = _('Campaign Bids')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign'], name='idx_campaign_431'),
            models.Index(fields=['bid_type'], name='idx_bid_type_432'),
            models.Index(fields=['auto_optimize', 'created_at'], name='idx_auto_optimize_created__de9'),
        ]
    
    def __str__(self):
        return f"Bidding: {self.campaign.name} ({self.bid_type})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate bid amounts
        if self.bid_amount <= 0:
            raise ValidationError(_('Bid amount must be positive'))
        
        if self.max_bid and self.max_bid <= 0:
            raise ValidationError(_('Maximum bid must be positive'))
        
        if self.min_bid and self.min_bid <= 0:
            raise ValidationError(_('Minimum bid must be positive'))
        
        # Validate bid range
        if self.min_bid and self.max_bid and self.min_bid > self.max_bid:
            raise ValidationError(_('Minimum bid cannot be greater than maximum bid'))
        
        if self.bid_amount:
            if self.min_bid and self.bid_amount < self.min_bid:
                raise ValidationError(_('Bid amount cannot be less than minimum bid'))
            
            if self.max_bid and self.bid_amount > self.max_bid:
                raise ValidationError(_('Bid amount cannot be greater than maximum bid'))
        
        # Validate target values
        if self.target_cpa and self.target_cpa <= 0:
            raise ValidationError(_('Target CPA must be positive'))
        
        if self.target_roas and self.target_roas <= 0:
            raise ValidationError(_('Target ROAS must be positive'))
    
    @property
    def is_cpc_bidding(self) -> bool:
        """Check if using CPC bidding."""
        return self.bid_type == 'cpc'
    
    @property
    def is_cpm_bidding(self) -> bool:
        """Check if using CPM bidding."""
        return self.bid_type == 'cpm'
    
    @property
    def is_cpa_bidding(self) -> bool:
        """Check if using CPA bidding."""
        return self.bid_type == 'cpa'
    
    @property
    def has_bid_range(self) -> bool:
        """Check if bid range is configured."""
        return bool(self.min_bid and self.max_bid)
    
    @property
    def bid_range_display(self) -> str:
        """Get bid range display."""
        if self.has_bid_range:
            return f"${self.min_bid} - ${self.max_bid}"
        return f"${self.bid_amount}"
    
    def get_effective_bid(self, context: dict = None) -> float:
        """Get effective bid based on context."""
        base_bid = float(self.bid_amount)
        
        # Apply bid adjustments if available
        if self.bid_adjustments and context:
            for segment, adjustment in self.bid_adjustments.items():
                if context.get(segment):
                    base_bid *= adjustment
        
        # Apply dayparting if available
        if self.dayparting and context:
            hour = context.get('hour')
            if hour and str(hour) in self.dayparting:
                base_bid *= self.dayparting[str(hour)]
        
        # Ensure bid is within range
        if self.min_bid and base_bid < float(self.min_bid):
            base_bid = float(self.min_bid)
        
        if self.max_bid and base_bid > float(self.max_bid):
            base_bid = float(self.max_bid)
        
        return base_bid
    
    def get_bidding_summary(self) -> dict:
        """Get bidding configuration summary."""
        return {
            'bid_type': self.bid_type,
            'bid_amount': float(self.bid_amount),
            'bid_range': {
                'has_range': self.has_bid_range,
                'min_bid': float(self.min_bid) if self.min_bid else None,
                'max_bid': float(self.max_bid) if self.max_bid else None,
                'display': self.bid_range_display,
            },
            'optimization': {
                'auto_optimize': self.auto_optimize,
                'goal': self.optimization_goal,
                'target_cpa': float(self.target_cpa) if self.target_cpa else None,
                'target_roas': float(self.target_roas) if self.target_roas else None,
            },
            'pacing': {
                'budget_pacing': self.budget_pacing,
                'pacing_type': self.pacing_type,
            },
            'advanced': {
                'bid_adjustments': self.bid_adjustments or {},
                'frequency_capping': self.frequency_capping,
                'dayparting': self.dayparting or {},
            },
        }


class CampaignSchedule(models.Model):
    """
    Model for managing campaign scheduling.
    
    Stores time-based scheduling rules for campaigns
    including daily schedules and timezone handling.
    """
    
    # Core relationship
    campaign = models.OneToOneField(
        AdCampaign,
        on_delete=models.CASCADE,
        related_name='schedule',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this schedule belongs to')
    )
    
    # Schedule configuration
    schedule_type = models.CharField(
        _('Schedule Type'),
        max_length=20,
        choices=[
            ('continuous', _('Continuous')),
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('custom', _('Custom')),
        ],
        default='continuous',
        help_text=_('Type of scheduling')
    )
    
    # Daily schedule
    hours = models.JSONField(
        _('Hours'),
        default=list,
        blank=True,
        help_text=_('Hours of day to run (0-23)')
    )
    
    # Weekly schedule
    days_of_week = models.JSONField(
        _('Days of Week'),
        default=list,
        blank=True,
        help_text=_('Days of week to run (0-6, 0=Monday)')
    )
    
    # Date ranges
    start_date = models.DateTimeField(
        _('Start Date'),
        null=True,
        blank=True,
        help_text=_('Schedule start date')
    )
    
    end_date = models.DateTimeField(
        _('End Date'),
        null=True,
        blank=True,
        help_text=_('Schedule end date')
    )
    
    # Timezone settings
    timezone = models.CharField(
        _('Timezone'),
        max_length=50,
        default='UTC',
        help_text=_('Campaign timezone for scheduling')
    )
    
    # Advanced scheduling
    blackout_dates = models.JSONField(
        _('Blackout Dates'),
        default=list,
        blank=True,
        help_text=_('Dates when campaign should not run')
    )
    
    special_dates = models.JSONField(
        _('Special Dates'),
        default=list,
        blank=True,
        help_text=_('Special dates with different scheduling rules')
    )
    
    # Delivery settings
    delivery_speed = models.CharField(
        _('Delivery Speed'),
        max_length=20,
        choices=[
            ('standard', _('Standard')),
            ('accelerated', _('Accelerated')),
            ('no_limit', _('No Limit')),
        ],
        default='standard',
        help_text=_('Campaign delivery speed')
    )
    
    # Budget allocation
    daily_budget = models.DecimalField(
        _('Daily Budget'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Daily budget allocation')
    )
    
    hourly_budget = models.DecimalField(
        _('Hourly Budget'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Hourly budget allocation')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this schedule was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this schedule was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_campaign_schedule'
        verbose_name = _('Campaign Schedule')
        verbose_name_plural = _('Campaign Schedules')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign'], name='idx_campaign_434'),
            models.Index(fields=['schedule_type'], name='idx_schedule_type_435'),
            models.Index(fields=['start_date', 'end_date'], name='idx_start_date_end_date_436'),
        ]
    
    def __str__(self):
        return f"Schedule: {self.campaign.name} ({self.schedule_type})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate hours
        if self.hours:
            for hour in self.hours:
                if not isinstance(hour, int) or hour < 0 or hour > 23:
                    raise ValidationError(_('Hours must be integers between 0 and 23'))
        
        # Validate days
        if self.days_of_week:
            for day in self.days_of_week:
                if not isinstance(day, int) or day < 0 or day > 6:
                    raise ValidationError(_('Days of week must be integers between 0 and 6'))
        
        # Validate dates
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_('Start date must be before end date'))
        
        # Validate budget
        if self.daily_budget and self.daily_budget <= 0:
            raise ValidationError(_('Daily budget must be positive'))
        
        if self.hourly_budget and self.hourly_budget <= 0:
            raise ValidationError(_('Hourly budget must be positive'))
    
    @property
    def is_active_now(self) -> bool:
        """Check if campaign should be active now."""
        from django.utils import timezone as tz_utils
        
        now = timezone.now()
        
        # Convert to campaign timezone
        try:
            campaign_now = now.astimezone(tz_utils.get_default_timezone(self.timezone))
        except:
            campaign_now = now
        
        # Check if within schedule hours
        if self.hours and campaign_now.hour not in self.hours:
            return False
        
        # Check if within schedule days
        if self.days_of_week and campaign_now.weekday() not in self.days_of_week:
            return False
        
        # Check blackout dates
        if self.blackout_dates:
            today_str = campaign_now.date().isoformat()
            if today_str in self.blackout_dates:
                return False
        
        return True
    
    @property
    def next_active_time(self):
        """Get next time when campaign will be active."""
        # This would implement logic to find next active time
        # For now, return None
        return None
    
    @property
    def schedule_summary(self) -> dict:
        """Get schedule configuration summary."""
        return {
            'schedule_type': self.schedule_type,
            'hours': self.hours or [],
            'days_of_week': self.days_of_week or [],
            'timezone': self.timezone,
            'date_range': {
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None,
            },
            'blackout_dates': self.blackout_dates or [],
            'special_dates': self.special_dates or [],
            'delivery_speed': self.delivery_speed,
            'budget_allocation': {
                'daily_budget': float(self.daily_budget) if self.daily_budget else None,
                'hourly_budget': float(self.hourly_budget) if self.hourly_budget else None,
            },
            'is_active_now': self.is_active_now,
        }


# Signal handlers for campaign models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=AdCampaign)
def campaign_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for campaigns."""
    if created:
        logger.info(f"New campaign created: {instance.name}")
        
        # Create default targeting if not exists
        if not hasattr(instance, 'targeting'):
            CampaignTargeting.objects.create(campaign=instance)
        
        # Create default bidding if not exists
        if not hasattr(instance, 'bidding'):
            CampaignBid.objects.create(campaign=instance)
        
        # Create default schedule if not exists
        if not hasattr(instance, 'schedule'):
            CampaignSchedule.objects.create(campaign=instance)

@receiver(post_save, sender=CampaignCreative)
def creative_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for creatives."""
    if created:
        logger.info(f"New creative created: {instance.name}")
        
        # Auto-approve if campaign is active
        if instance.campaign.is_active:
            instance.status = 'active'
            instance.is_approved = True
            instance.save(update_fields=['status', 'is_approved'])

@receiver(post_delete, sender=AdCampaign)
def campaign_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for campaigns."""
    logger.info(f"Campaign deleted: {instance.name}")

@receiver(post_delete, sender=CampaignCreative)
def creative_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for creatives."""
    logger.info(f"Creative deleted: {instance.name}")
