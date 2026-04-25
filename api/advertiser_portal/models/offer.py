"""
Offer Models for Advertiser Portal

This module contains models for managing advertising offers,
including requirements, creatives, and blacklists.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserOffer(models.Model):
    """
    Model for managing advertiser offers.
    
    Stores offer information including payout types,
    requirements, and tracking details.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='offers',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this offer belongs to')
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal_v2.AdCampaign',
        on_delete=models.CASCADE,
        related_name='offers',
        null=True,
        blank=True,
        verbose_name=_('Campaign'),
        help_text=_('Campaign this offer belongs to')
    )
    
    # Offer details
    title = models.CharField(
        _('Offer Title'),
        max_length=200,
        db_index=True,
        help_text=_('Offer title for display')
    )
    
    description = models.TextField(
        _('Description'),
        help_text=_('Detailed description of the offer')
    )
    
    # Payout configuration
    payout_type = models.CharField(
        _('Payout Type'),
        max_length=20,
        choices=[
            ('cpi', _('Cost Per Install')),
            ('cpa', _('Cost Per Action')),
            ('cpe', _('Cost Per Engagement')),
            ('cpl', _('Cost Per Lead')),
            ('cps', _('Cost Per Sale')),
            ('cpm', _('Cost Per Mille')),
            ('cpc', _('Cost Per Click')),
            ('revenue_share', _('Revenue Share')),
            ('hybrid', _('Hybrid')),
        ],
        default='cpa',
        db_index=True,
        help_text=_('Type of payout structure')
    )
    
    payout_amount = models.DecimalField(
        _('Payout Amount'),
        max_digits=8,
        decimal_places=2,
        help_text=_('Amount paid per conversion')
    )
    
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    
    # Tracking configuration
    tracking_url = models.URLField(
        _('Tracking URL'),
        max_length=500,
        help_text=_('Postback URL for conversion tracking')
    )
    
    preview_url = models.URLField(
        _('Preview URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('URL for offer preview')
    )
    
    test_mode = models.BooleanField(
        _('Test Mode'),
        default=False,
        help_text=_('Whether offer is in test mode')
    )
    
    deduplication_window = models.IntegerField(
        _('Deduplication Window'),
        default=24,
        help_text=_('Hours to deduplicate conversions')
    )
    
    # Offer status
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('pending_review', _('Pending Review')),
            ('active', _('Active')),
            ('paused', _('Paused')),
            ('expired', _('Expired')),
            ('suspended', _('Suspended')),
            ('rejected', _('Rejected')),
        ],
        default='draft',
        db_index=True,
        help_text=_('Current offer status')
    )
    
    is_private = models.BooleanField(
        _('Is Private'),
        default=False,
        help_text=_('Whether offer is private (invite only)')
    )
    
    # Geographic targeting
    allowed_countries = models.JSONField(
        _('Allowed Countries'),
        default=list,
        blank=True,
        help_text=_('List of allowed country codes')
    )
    
    blocked_countries = models.JSONField(
        _('Blocked Countries'),
        default=list,
        blank=True,
        help_text=_('List of blocked country codes')
    )
    
    # Device targeting
    allowed_devices = models.JSONField(
        _('Allowed Devices'),
        default=list,
        blank=True,
        help_text=_('List of allowed device types')
    )
    
    blocked_devices = models.JSONField(
        _('Blocked Devices'),
        default=list,
        blank=True,
        help_text=_('List of blocked device types')
    )
    
    # Quality and performance
    quality_score = models.DecimalField(
        _('Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score (0-100)')
    )
    
    conversion_rate = models.DecimalField(
        _('Conversion Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Conversion rate percentage')
    )
    
    # Financial limits
    daily_budget = models.DecimalField(
        _('Daily Budget'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Daily budget limit')
    )
    
    total_budget = models.DecimalField(
        _('Total Budget'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Total budget limit')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this offer was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this offer was last updated')
    )
    
    start_date = models.DateTimeField(
        _('Start Date'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When offer becomes active')
    )
    
    end_date = models.DateTimeField(
        _('End Date'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When offer expires')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_offer'
        verbose_name = _('Advertiser Offer')
        verbose_name_plural = _('Advertiser Offers')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_506'),
            models.Index(fields=['campaign', 'status'], name='idx_campaign_status_507'),
            models.Index(fields=['payout_type', 'status'], name='idx_payout_type_status_508'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_509'),
            models.Index(fields=['start_date', 'end_date'], name='idx_start_date_end_date_510'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate payout amount
        if self.payout_amount <= 0:
            raise ValidationError(_('Payout amount must be positive'))
        
        # Validate deduplication window
        if self.deduplication_window < 1:
            raise ValidationError(_('Deduplication window must be at least 1 hour'))
        
        # Validate budget amounts
        if self.daily_budget and self.daily_budget <= 0:
            raise ValidationError(_('Daily budget must be positive'))
        
        if self.total_budget and self.total_budget <= 0:
            raise ValidationError(_('Total budget must be positive'))
        
        # Validate dates
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_('Start date must be before end date'))
    
    @property
    def is_active(self) -> bool:
        """Check if offer is currently active."""
        now = timezone.now()
        return (
            self.status == 'active' and
            (not self.start_date or self.start_date <= now) and
            (not self.end_date or self.end_date >= now)
        )
    
    @property
    def is_expired(self) -> bool:
        """Check if offer has expired."""
        if self.end_date:
            return timezone.now() > self.end_date
        return False
    
    @property
    def days_remaining(self) -> int:
        """Get days remaining until offer expires."""
        if self.end_date:
            delta = self.end_date - timezone.now()
            return max(delta.days, 0)
        return 0
    
    @property
    def payout_display(self) -> str:
        """Get human-readable payout type."""
        payout_types = {
            'cpi': _('CPI - Cost Per Install'),
            'cpa': _('CPA - Cost Per Action'),
            'cpe': _('CPE - Cost Per Engagement'),
            'cpl': _('CPL - Cost Per Lead'),
            'cps': _('CPS - Cost Per Sale'),
            'cpm': _('CPM - Cost Per Mille'),
            'cpc': _('CPC - Cost Per Click'),
            'revenue_share': _('Revenue Share'),
            'hybrid': _('Hybrid'),
        }
        return payout_types.get(self.payout_type, self.payout_type)
    
    def get_active_requirements(self):
        """Get active offer requirements."""
        return self.requirements.filter(
            status='active',
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        )
    
    def get_active_creatives(self):
        """Get active creatives for this offer."""
        return self.creatives.filter(
            status='active',
            is_approved=True
        )
    
    def get_performance_metrics(self, days: int = 30):
        """Get performance metrics for this offer."""
        from .tracking import ConversionEvent
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        conversions = ConversionEvent.objects.filter(
            offer=self,
            event_date__gte=cutoff_date
        ).count()
        
        # Calculate metrics (placeholder implementation)
        return {
            'conversions': conversions,
            'conversion_rate': float(self.conversion_rate),
            'quality_score': float(self.quality_score),
            'payout_type': self.payout_type,
            'payout_amount': float(self.payout_amount),
            'is_active': self.is_active,
            'days_remaining': self.days_remaining,
        }


class OfferRequirement(models.Model):
    """
    Model for managing offer requirements.
    
    Stores requirements users must complete to get
    credit for the offer.
    """
    
    # Core relationships
    offer = models.ForeignKey(
        AdvertiserOffer,
        on_delete=models.CASCADE,
        related_name='requirements',
        verbose_name=_('Offer'),
        help_text=_('Offer this requirement belongs to')
    )
    
    # Requirement details
    requirement_type = models.CharField(
        _('Requirement Type'),
        max_length=50,
        choices=[
            ('app_install', _('App Install')),
            ('form_fill', _('Form Fill')),
            ('purchase', _('Purchase')),
            ('survey', _('Survey')),
            ('video_view', _('Video View')),
            ('email_submit', _('Email Submit')),
            ('social_share', _('Social Share')),
            ('account_creation', _('Account Creation')),
            ('trial_signup', _('Trial Signup')),
            ('subscription', _('Subscription')),
            ('other', _('Other')),
        ],
        help_text=_('Type of requirement')
    )
    
    instructions = models.TextField(
        _('Instructions'),
        help_text=_('Detailed instructions for completing the requirement')
    )
    
    # Status and timing
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('active', _('Active')),
            ('paused', _('Paused')),
            ('expired', _('Expired')),
        ],
        default='draft',
        help_text=_('Current requirement status')
    )
    
    proof_required = models.BooleanField(
        _('Proof Required'),
        default=True,
        help_text=_('Whether proof of completion is required')
    )
    
    proof_instructions = models.TextField(
        _('Proof Instructions'),
        null=True,
        blank=True,
        help_text=_('Instructions for providing proof')
    )
    
    # Validation rules
    validation_rules = models.JSONField(
        _('Validation Rules'),
        default=dict,
        blank=True,
        help_text=_('Rules for validating requirement completion')
    )
    
    # Time constraints
    completion_time_limit = models.IntegerField(
        _('Completion Time Limit'),
        null=True,
        blank=True,
        help_text=_('Time limit in minutes for completion')
    )
    
    retry_attempts = models.IntegerField(
        _('Retry Attempts'),
        default=3,
        help_text=_('Number of retry attempts allowed')
    )
    
    cooldown_period = models.IntegerField(
        _('Cooldown Period'),
        default=0,
        help_text=_('Cooldown period in hours between attempts')
    )
    
    # Reward configuration
    reward_amount = models.DecimalField(
        _('Reward Amount'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Additional reward amount for completion')
    )
    
    reward_type = models.CharField(
        _('Reward Type'),
        max_length=20,
        choices=[
            ('fixed', _('Fixed')),
            ('percentage', _('Percentage')),
            ('tiered', _('Tiered')),
        ],
        default='fixed',
        help_text=_('Type of reward calculation')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this requirement was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this requirement was last updated')
    )
    
    start_date = models.DateTimeField(
        _('Start Date'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When requirement becomes active')
    )
    
    end_date = models.DateTimeField(
        _('End Date'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When requirement expires')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_offer_requirement'
        verbose_name = _('Offer Requirement')
        verbose_name_plural = _('Offer Requirements')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['offer', 'status'], name='idx_offer_status_511'),
            models.Index(fields=['requirement_type', 'status'], name='idx_requirement_type_statu_bc8'),
            models.Index(fields=['status', 'start_date', 'end_date'], name='idx_status_start_date_end__3b4'),
        ]
    
    def __str__(self):
        return f"{self.requirement_type} ({self.offer.title})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate time limit
        if self.completion_time_limit and self.completion_time_limit <= 0:
            raise ValidationError(_('Completion time limit must be positive'))
        
        # Validate retry attempts
        if self.retry_attempts < 0:
            raise ValidationError(_('Retry attempts cannot be negative'))
        
        # Validate cooldown period
        if self.cooldown_period < 0:
            raise ValidationError(_('Cooldown period cannot be negative'))
        
        # Validate reward amount
        if self.reward_amount and self.reward_amount < 0:
            raise ValidationError(_('Reward amount cannot be negative'))
        
        # Validate dates
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_('Start date must be before end date'))
    
    @property
    def is_active(self) -> bool:
        """Check if requirement is currently active."""
        now = timezone.now()
        return (
            self.status == 'active' and
            (not self.start_date or self.start_date <= now) and
            (not self.end_date or self.end_date >= now)
        )
    
    @property
    def is_expired(self) -> bool:
        """Check if requirement has expired."""
        if self.end_date:
            return timezone.now() > self.end_date
        return False
    
    @property
    def time_remaining(self) -> int:
        """Get time remaining in minutes."""
        if self.completion_time_limit:
            return max(self.completion_time_limit, 0)
        return 0
    
    @property
    def requirement_type_display(self) -> str:
        """Get human-readable requirement type."""
        type_names = {
            'app_install': _('App Install'),
            'form_fill': _('Form Fill'),
            'purchase': _('Purchase'),
            'survey': _('Survey'),
            'video_view': _('Video View'),
            'email_submit': _('Email Submit'),
            'social_share': _('Social Share'),
            'account_creation': _('Account Creation'),
            'trial_signup': _('Trial Signup'),
            'subscription': _('Subscription'),
            'other': _('Other'),
        }
        return type_names.get(self.requirement_type, self.requirement_type)
    
    def get_validation_summary(self) -> dict:
        """Get summary of validation rules."""
        if not self.validation_rules:
            return {'rules': [], 'has_rules': False}
        
        return {
            'rules': self.validation_rules,
            'has_rules': True,
            'rule_count': len(self.validation_rules),
            'has_time_limit': bool(self.completion_time_limit),
            'has_retry_limit': bool(self.retry_attempts),
            'has_cooldown': bool(self.cooldown_period),
        }


class OfferCreative(models.Model):
    """
    Model for managing offer creatives.
    
    Stores creative assets including banners, videos,
    and native ad content.
    """
    
    # Core relationships
    offer = models.ForeignKey(
        AdvertiserOffer,
        on_delete=models.CASCADE,
        related_name='creatives',
        verbose_name=_('Offer'),
        help_text=_('Offer this creative belongs to')
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
        help_text=_('Type of creative')
    )
    
    # Creative assets
    file = models.FileField(
        _('Creative File'),
        upload_to='offer_creatives/',
        null=True,
        blank=True,
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
        db_table = 'advertiser_portal_offer_creative'
        verbose_name = _('Offer Creative')
        verbose_name_plural = _('Offer Creatives')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['offer', 'status'], name='idx_offer_status_514'),
            models.Index(fields=['creative_type', 'status'], name='idx_creative_type_status_515'),
            models.Index(fields=['is_approved', 'status'], name='idx_is_approved_status_516'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_517'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.offer.title})"
    
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


class OfferBlacklist(models.Model):
    """
    Model for managing offer blacklists.
    
    Stores blacklist entries for publishers, geography,
    devices, and other criteria.
    """
    
    # Core relationships
    offer = models.ForeignKey(
        AdvertiserOffer,
        on_delete=models.CASCADE,
        related_name='blacklists',
        verbose_name=_('Offer'),
        help_text=_('Offer this blacklist belongs to')
    )
    
    # Blacklist details
    blacklist_type = models.CharField(
        _('Blacklist Type'),
        max_length=50,
        choices=[
            ('publisher', _('Publisher')),
            ('geo', _('Geography')),
            ('device', _('Device')),
            ('ip', _('IP Address')),
            ('domain', _('Domain')),
            ('user_agent', _('User Agent')),
            ('keyword', _('Keyword')),
            ('category', _('Category')),
            ('custom', _('Custom')),
        ],
        help_text=_('Type of blacklist entry')
    )
    
    value = models.CharField(
        _('Value'),
        max_length=500,
        help_text=_('Blacklist value (publisher ID, country code, etc.)')
    )
    
    # Status and configuration
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('active', _('Active')),
            ('inactive', _('Inactive')),
            ('pending', _('Pending')),
            ('expired', _('Expired')),
        ],
        default='active',
        help_text=_('Current blacklist status')
    )
    
    reason = models.TextField(
        _('Reason'),
        help_text=_('Reason for blacklisting')
    )
    
    # Matching configuration
    match_type = models.CharField(
        _('Match Type'),
        max_length=20,
        choices=[
            ('exact', _('Exact Match')),
            ('contains', _('Contains')),
            ('starts_with', _('Starts With')),
            ('ends_with', _('Ends With')),
            ('regex', _('Regular Expression')),
            ('wildcard', _('Wildcard')),
            ('cidr', _('CIDR Range')),
            ('range', _('Range')),
        ],
        default='exact',
        help_text=_('How to match blacklist value')
    )
    
    case_sensitive = models.BooleanField(
        _('Case Sensitive'),
        default=True,
        help_text=_('Whether matching is case sensitive')
    )
    
    # Expiration
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this blacklist entry expires')
    )
    
    # Metadata
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional metadata about blacklist entry')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this blacklist entry was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this blacklist entry was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_offer_blacklist'
        verbose_name = _('Offer Blacklist')
        verbose_name_plural = _('Offer Blacklists')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['offer', 'status'], name='idx_offer_status_518'),
            models.Index(fields=['blacklist_type', 'status'], name='idx_blacklist_type_status_519'),
            models.Index(fields=['status', 'expires_at'], name='idx_status_expires_at_520'),
            models.Index(fields=['value', 'blacklist_type'], name='idx_value_blacklist_type_521'),
        ]
        unique_together = [
            ['offer', 'blacklist_type', 'value'],
        ]
    
    def __str__(self):
        return f"{self.blacklist_type}: {self.value}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate value
        if not self.value.strip():
            raise ValidationError(_('Blacklist value cannot be empty'))
        
        # Validate CIDR range
        if self.match_type == 'cidr':
            import ipaddress
            try:
                ipaddress.ip_network(self.value)
            except ValueError:
                raise ValidationError(_('Invalid CIDR range format'))
    
    @property
    def is_expired(self) -> bool:
        """Check if blacklist entry is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_active(self) -> bool:
        """Check if blacklist entry is active."""
        return self.status == 'active' and not self.is_expired
    
    @property
    def blacklist_type_display(self) -> str:
        """Get human-readable blacklist type."""
        type_names = {
            'publisher': _('Publisher'),
            'geo': _('Geography'),
            'device': _('Device'),
            'ip': _('IP Address'),
            'domain': _('Domain'),
            'user_agent': _('User Agent'),
            'keyword': _('Keyword'),
            'category': _('Category'),
            'custom': _('Custom'),
        }
        return type_names.get(self.blacklist_type, self.blacklist_type)
    
    def matches(self, test_value: str, context: dict = None) -> bool:
        """Check if test value matches this blacklist entry."""
        if not self.is_active:
            return False
        
        try:
            # Apply case sensitivity
            value_to_check = self.value
            test_value_to_check = test_value
            
            if not self.case_sensitive:
                value_to_check = value_to_check.lower()
                test_value_to_check = test_value.lower()
            
            # Apply matching logic
            if self.match_type == 'exact':
                return value_to_check == test_value_to_check
            elif self.match_type == 'contains':
                return value_to_check in test_value_to_check
            elif self.match_type == 'starts_with':
                return test_value_to_check.startswith(value_to_check)
            elif self.match_type == 'ends_with':
                return test_value_to_check.endswith(value_to_check)
            elif self.match_type == 'regex':
                import re
                return bool(re.search(value_to_check, test_value_to_check))
            elif self.match_type == 'wildcard':
                import fnmatch
                return fnmatch.fnmatch(test_value_to_check, value_to_check)
            elif self.match_type == 'cidr':
                import ipaddress
                try:
                    network = ipaddress.ip_network(value_to_check)
                    ip = ipaddress.ip_address(test_value_to_check)
                    return ip in network
                except ValueError:
                    return False
            elif self.match_type == 'range':
                # Simple range matching (would need more context)
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching blacklist entry: {e}")
            return False


# Signal handlers for offer models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=AdvertiserOffer)
def offer_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for offers."""
    if created:
        logger.info(f"New offer created: {instance.title}")
        
        # Send notification to advertiser
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance.advertiser,
            type='offer_created',
            title=_('New Offer Created'),
            message=_('Your offer "{instance.title}" has been created successfully.'),
        )

@receiver(post_save, sender=OfferCreative)
def creative_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for creatives."""
    if created:
        logger.info(f"New creative created: {instance.name}")
        
        # Auto-approve if offer is active
        if instance.offer.is_active:
            instance.status = 'active'
            instance.is_approved = True
            instance.save(update_fields=['status', 'is_approved'])

@receiver(post_delete, sender=AdvertiserOffer)
def offer_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for offers."""
    logger.info(f"Offer deleted: {instance.title}")

@receiver(post_delete, sender=OfferCreative)
def creative_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for creatives."""
    logger.info(f"Creative deleted: {instance.name}")
