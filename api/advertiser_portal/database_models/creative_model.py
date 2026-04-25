from django.conf import settings
"""
Creative Database Model

This module contains the Creative model and related models
for managing ad creatives and creative assets.
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
from django.core.files.storage import default_storage

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class Creative(AdvertiserPortalBaseModel, StatusModel, AuditModel, TrackingModel):
    """
    Main creative model for managing ad creatives.
    
    This model stores all creative information including file details,
    approval status, performance metrics, and creative variations.
    """
    
    # Basic Information
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='creatives',
        help_text="Associated campaign"
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Creative name"
    )
    description = models.TextField(
        blank=True,
        help_text="Creative description"
    )
    
    # Creative Type and Format
    creative_type = models.CharField(
        max_length=50,
        choices=CreativeTypeEnum.choices,
        db_index=True,
        help_text="Type of creative"
    )
    format_type = models.CharField(
        max_length=50,
        choices=[
            ('standard', 'Standard'),
            ('responsive', 'Responsive'),
            ('interactive', 'Interactive'),
            ('video', 'Video'),
            ('rich_media', 'Rich Media')
        ],
        default='standard',
        help_text="Creative format type"
    )
    
    # Creative Content
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Creative title or headline"
    )
    body_text = models.TextField(
        blank=True,
        help_text="Creative body text"
    )
    call_to_action = models.CharField(
        max_length=100,
        blank=True,
        help_text="Call to action text"
    )
    display_url = models.URLField(
        blank=True,
        help_text="Display URL shown to users"
    )
    
    # Landing Pages and Tracking
    landing_page_url = models.URLField(
        help_text="Destination landing page URL"
    )
    tracking_url = models.URLField(
        blank=True,
        help_text="Third-party tracking URL"
    )
    click_tracking_url = models.URLField(
        blank=True,
        help_text="Click tracking URL"
    )
    impression_tracking_url = models.URLField(
        blank=True,
        help_text="Impression tracking URL"
    )
    
    # File Information
    creative_file = models.FileField(
        upload_to='creatives/%Y/%m/',
        null=True,
        blank=True,
        help_text="Creative file upload"
    )
    file_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original file name"
    )
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="File MIME type"
    )
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="File hash for deduplication"
    )
    
    # Creative Dimensions
    width = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Creative width in pixels"
    )
    height = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Creative height in pixels"
    )
    aspect_ratio = models.CharField(
        max_length=20,
        blank=True,
        help_text="Aspect ratio (e.g., 16:9, 1:1)"
    )
    
    # Video Specific Fields
    video_duration = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Video duration in seconds"
    )
    video_thumbnail = models.ImageField(
        upload_to='creative_thumbnails/%Y/%m/',
        null=True,
        blank=True,
        help_text="Video thumbnail image"
    )
    
    # HTML5 and Interactive Fields
    html_content = models.TextField(
        blank=True,
        help_text="HTML5 creative content"
    )
    javascript_code = models.TextField(
        blank=True,
        help_text="JavaScript code for interactive creatives"
    )
    css_code = models.TextField(
        blank=True,
        help_text="CSS code for creative styling"
    )
    
    # Dynamic Creative Fields
    is_dynamic = models.BooleanField(
        default=False,
        help_text="Whether creative is dynamic"
    )
    dynamic_template = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dynamic creative template configuration"
    )
    feed_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feed data for dynamic creatives"
    )
    
    # Approval and Review
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether creative is approved"
    )
    approval_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when creative was approved"
    )
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_creatives'
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection"
    )
    compliance_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Compliance score (0-100)"
    )
    
    # Quality and Performance
    quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Creative quality score (0-100)"
    )
    performance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Creative performance score (0-100)"
    )
    
    # Versioning and Variations
    version = models.IntegerField(
        default=1,
        help_text="Creative version number"
    )
    parent_creative = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='variations',
        help_text="Parent creative for variations"
    )
    variation_type = models.CharField(
        max_length=50,
        choices=[
            ('original', 'Original'),
            ('ab_test', 'A/B Test'),
            ('multivariate', 'Multivariate'),
            ('responsive', 'Responsive Variation')
        ],
        default='original',
        help_text="Type of variation"
    )
    
    # Targeting and Delivery
    device_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Device-specific targeting"
    )
    geo_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Geographic targeting"
    )
    time_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Time-based targeting"
    )
    audience_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Audience targeting"
    )
    
    # Delivery Settings
    weight = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Delivery weight (1-100)"
    )
    priority = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Delivery priority (1-10)"
    )
    delivery_caps = models.JSONField(
        default=dict,
        blank=True,
        help_text="Delivery caps and limits"
    )
    
    # Third-party Integrations
    external_creative_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External creative ID"
    )
    integration_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration settings"
    )
    
    # Labels and Organization
    labels = models.JSONField(
        default=list,
        blank=True,
        help_text="Creative labels for organization"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Creative tags"
    )
    
    class Meta:
        db_table = 'creatives'
        verbose_name = 'Creative'
        verbose_name_plural = 'Creatives'
        indexes = [
            models.Index(fields=['campaign', 'status'], name='idx_campaign_status_233'),
            models.Index(fields=['creative_type'], name='idx_creative_type_234'),
            models.Index(fields=['is_approved'], name='idx_is_approved_235'),
            models.Index(fields=['created_at'], name='idx_created_at_236'),
            models.Index(fields=['name'], name='idx_name_237'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.creative_type})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate URL formats
        if self.landing_page_url:
            from django.core.validators import URLValidator
            validator = URLValidator()
            validator(self.landing_page_url)
        
        if self.tracking_url:
            validator = URLValidator()
            validator(self.tracking_url)
        
        # Validate file requirements based on creative type
        if self.creative_type == CreativeTypeEnum.VIDEO.value:
            if not self.video_duration:
                raise ValidationError("Video duration is required for video creatives")
        
        if self.creative_type in [CreativeTypeEnum.BANNER.value, CreativeTypeEnum.HTML5.value]:
            if not self.width or not self.height:
                raise ValidationError("Width and height are required for banner and HTML5 creatives")
        
        # Validate dynamic creative requirements
        if self.is_dynamic and not self.dynamic_template:
            raise ValidationError("Dynamic template is required for dynamic creatives")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Generate file hash if file is uploaded
        if self.creative_file and not self.file_hash:
            self.file_hash = self.generate_file_hash()
        
        # Calculate aspect ratio
        if self.width and self.height:
            from math import gcd
            divisor = gcd(self.width, self.height)
            self.aspect_ratio = f"{self.width // divisor}:{self.height // divisor}"
        
        # Update performance metrics
        self.update_performance_metrics()
        
        # Set approval date if approved
        if self.is_approved and not self.approval_date:
            self.approval_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def generate_file_hash(self) -> str:
        """Generate hash for uploaded file."""
        if not self.creative_file:
            return ""
        
        import hashlib
        hash_md5 = hashlib.md5()
        
        # Read file in chunks to handle large files
        for chunk in self.creative_file.chunks():
            hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def is_active(self) -> bool:
        """Check if creative is currently active."""
        return (
            self.status == StatusEnum.ACTIVE.value and
            self.is_approved and
            self.campaign.status == StatusEnum.ACTIVE.value
        )
    
    def get_file_url(self) -> Optional[str]:
        """Get the URL of the creative file."""
        if self.creative_file:
            return self.creative_file.url
        return None
    
    def get_thumbnail_url(self) -> Optional[str]:
        """Get the URL of the creative thumbnail."""
        if self.video_thumbnail:
            return self.video_thumbnail.url
        return None
    
    def get_file_size_display(self) -> str:
        """Get human-readable file size."""
        if not self.file_size:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"
    
    def get_duration_display(self) -> str:
        """Get human-readable duration."""
        if not self.video_duration:
            return "N/A"
        
        minutes = self.video_duration // 60
        seconds = self.video_duration % 60
        return f"{minutes}:{seconds:02d}"
    
    def can_serve(self) -> bool:
        """Check if creative can be served."""
        return self.is_active()
    
    def get_targeting_summary(self) -> Dict[str, Any]:
        """Get summary of targeting settings."""
        return {
            'device_targeting': self.device_targeting,
            'geo_targeting': self.geo_targeting,
            'time_targeting': self.time_targeting,
            'audience_targeting': self.audience_targeting,
            'delivery_settings': {
                'weight': self.weight,
                'priority': self.priority,
                'delivery_caps': self.delivery_caps
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        return {
            'basic_metrics': {
                'impressions': self.impressions,
                'clicks': self.clicks,
                'conversions': self.conversions,
                'cost': float(self.cost),
                'revenue': float(self.revenue)
            },
            'calculated_metrics': {
                'ctr': float(self.ctr),
                'cpc': float(self.cpc),
                'cpm': float(self.cpm),
                'cpa': float(self.cpa),
                'conversion_rate': float(self.conversion_rate),
                'roas': float(self.roas),
                'roi': float(self.roi)
            },
            'quality_metrics': {
                'quality_score': float(self.quality_score),
                'performance_score': float(self.performance_score),
                'compliance_score': self.compliance_score
            }
        }
    
    def update_performance_metrics(self) -> None:
        """Update quality and performance scores."""
        # Calculate quality score based on various factors
        quality_score = 0
        
        # Approval status (30 points)
        if self.is_approved:
            quality_score += 30
        
        # Creative completeness (25 points)
        if self.title and self.body_text:
            quality_score += 10
        if self.creative_file:
            quality_score += 15
        
        # Technical compliance (25 points)
        if self.file_size and self.file_size <= 150 * 1024:  # 150KB limit for banners
            quality_score += 10
        if self.mime_type and self.mime_type in ['image/jpeg', 'image/png', 'image/gif']:
            quality_score += 15
        
        # Brand safety (20 points)
        if self.compliance_score >= 80:
            quality_score += 20
        elif self.compliance_score >= 60:
            quality_score += 10
        
        self.quality_score = Decimal(str(min(quality_score, 100)))
        
        # Calculate performance score based on KPIs
        performance_score = 0
        
        if self.clicks > 0:
            # CTR component (40 points)
            ctr_score = min(float(self.ctr) * 8, 40)  # CTR up to 5% gets full points
            performance_score += ctr_score
            
            # Conversion rate component (40 points)
            if self.conversions > 0:
                conversion_score = min(float(self.conversion_rate) * 8, 40)  # CR up to 5% gets full points
                performance_score += conversion_score
            
            # Cost efficiency (20 points)
            if self.campaign.target_cpa:
                if self.cpa <= self.campaign.target_cpa:
                    performance_score += 20
                else:
                    efficiency = self.campaign.target_cpa / max(self.cpa, Decimal('0.01'))
                    performance_score += min(efficiency * 20, 20)
        
        self.performance_score = Decimal(str(min(performance_score, 100)))
    
    def create_variation(self, variation_data: Dict[str, Any]) -> 'Creative':
        """Create a variation of this creative."""
        with transaction.atomic():
            # Increment version
            new_version = self.version + 1
            
            # Create variation
            variation = Creative.objects.create(
                campaign=self.campaign,
                name=f"{self.name} - Variation {new_version}",
                description=variation_data.get('description', self.description),
                creative_type=self.creative_type,
                format_type=self.format_type,
                title=variation_data.get('title', self.title),
                body_text=variation_data.get('body_text', self.body_text),
                call_to_action=variation_data.get('call_to_action', self.call_to_action),
                display_url=variation_data.get('display_url', self.display_url),
                landing_page_url=variation_data.get('landing_page_url', self.landing_page_url),
                tracking_url=variation_data.get('tracking_url', self.tracking_url),
                click_tracking_url=variation_data.get('click_tracking_url', self.click_tracking_url),
                impression_tracking_url=variation_data.get('impression_tracking_url', self.impression_tracking_url),
                width=variation_data.get('width', self.width),
                height=variation_data.get('height', self.height),
                html_content=variation_data.get('html_content', self.html_content),
                javascript_code=variation_data.get('javascript_code', self.javascript_code),
                css_code=variation_data.get('css_code', self.css_code),
                is_dynamic=variation_data.get('is_dynamic', self.is_dynamic),
                dynamic_template=variation_data.get('dynamic_template', self.dynamic_template),
                parent_creative=self,
                variation_type=variation_data.get('variation_type', 'ab_test'),
                version=new_version,
                weight=variation_data.get('weight', self.weight),
                priority=variation_data.get('priority', self.priority),
                labels=variation_data.get('labels', self.labels),
                tags=variation_data.get('tags', self.tags),
                status=StatusEnum.PENDING.value,
                created_by=getattr(self, 'modified_by', None)
            )
            
            return variation
    
    def duplicate(self, new_name: Optional[str] = None) -> 'Creative':
        """Create a duplicate of this creative."""
        duplicate_name = new_name or f"{self.name} (Copy)"
        
        with transaction.atomic():
            new_creative = Creative.objects.create(
                campaign=self.campaign,
                name=duplicate_name,
                description=self.description,
                creative_type=self.creative_type,
                format_type=self.format_type,
                title=self.title,
                body_text=self.body_text,
                call_to_action=self.call_to_action,
                display_url=self.display_url,
                landing_page_url=self.landing_page_url,
                tracking_url=self.tracking_url,
                click_tracking_url=self.click_tracking_url,
                impression_tracking_url=self.impression_tracking_url,
                width=self.width,
                height=self.height,
                video_duration=self.video_duration,
                html_content=self.html_content,
                javascript_code=self.javascript_code,
                css_code=self.css_code,
                is_dynamic=self.is_dynamic,
                dynamic_template=self.dynamic_template,
                weight=self.weight,
                priority=self.priority,
                device_targeting=self.device_targeting.copy(),
                geo_targeting=self.geo_targeting.copy(),
                time_targeting=self.time_targeting.copy(),
                audience_targeting=self.audience_targeting.copy(),
                delivery_caps=self.delivery_caps.copy(),
                labels=self.labels.copy(),
                tags=self.tags.copy(),
                integration_settings=self.integration_settings.copy(),
                status=StatusEnum.PENDING.value,
                created_by=getattr(self, 'modified_by', None)
            )
            
            return new_creative
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get optimization recommendations for this creative."""
        recommendations = []
        
        # Performance recommendations
        if self.ctr < 0.5:
            recommendations.append({
                'type': 'performance',
                'priority': 'high',
                'title': 'Low Click-Through Rate',
                'description': f'CTR of {self.ctr:.2f}% is below average. Consider improving creative design or messaging.',
                'action': 'optimize_design'
            })
        
        if self.conversion_rate < 1.0:
            recommendations.append({
                'type': 'performance',
                'priority': 'medium',
                'title': 'Low Conversion Rate',
                'description': f'Conversion rate of {self.conversion_rate:.2f}% needs improvement. Review landing page alignment.',
                'action': 'optimize_landing_page'
            })
        
        # Technical recommendations
        if self.file_size and self.file_size > 100 * 1024:  # 100KB
            recommendations.append({
                'type': 'technical',
                'priority': 'medium',
                'title': 'Large File Size',
                'description': f'File size of {self.get_file_size_display()} may impact load times.',
                'action': 'compress_file'
            })
        
        # Quality recommendations
        if self.quality_score < 70:
            recommendations.append({
                'type': 'quality',
                'priority': 'low',
                'title': 'Quality Score Low',
                'description': f'Quality score of {self.quality_score} indicates room for improvement.',
                'action': 'improve_quality'
            })
        
        return recommendations


class CreativeAsset(AdvertiserPortalBaseModel):
    """
    Model for managing creative assets and components.
    """
    
    creative = models.ForeignKey(
        Creative,
        on_delete=models.CASCADE,
        related_name='assets'
    )
    asset_type = models.CharField(
        max_length=50,
        choices=[
            ('image', 'Image'),
            ('video', 'Video'),
            ('audio', 'Audio'),
            ('font', 'Font'),
            ('icon', 'Icon'),
            ('logo', 'Logo')
        ],
        help_text="Type of asset"
    )
    asset_file = models.FileField(
        upload_to='creative_assets/%Y/%m/',
        help_text="Asset file"
    )
    asset_name = models.CharField(
        max_length=255,
        help_text="Asset name"
    )
    file_size = models.BigIntegerField(
        help_text="Asset file size in bytes"
    )
    mime_type = models.CharField(
        max_length=100,
        help_text="Asset MIME type"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Asset metadata"
    )
    
    class Meta:
        db_table = 'creative_assets'
        verbose_name = 'Creative Asset'
        verbose_name_plural = 'Creative Assets'
        indexes = [
            models.Index(fields=['creative', 'asset_type'], name='idx_creative_asset_type_238'),
        ]
    
    def __str__(self) -> str:
        return f"{self.creative.name} - {self.asset_name}"


class CreativeApprovalLog(AdvertiserPortalBaseModel):
    """
    Model for tracking creative approval history.
    """
    
    creative = models.ForeignKey(
        Creative,
        on_delete=models.CASCADE,
        related_name='approval_logs'
    )
    action = models.CharField(
        max_length=20,
        choices=[
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('resubmitted', 'Resubmitted')
        ],
        help_text="Approval action"
    )
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='creative_reviews'
    )
    notes = models.TextField(
        blank=True,
        help_text="Review notes"
    )
    compliance_issues = models.JSONField(
        default=list,
        blank=True,
        help_text="List of compliance issues found"
    )
    
    class Meta:
        db_table = 'creative_approval_logs'
        verbose_name = 'Creative Approval Log'
        verbose_name_plural = 'Creative Approval Logs'
        indexes = [
            models.Index(fields=['creative', 'created_at'], name='idx_creative_created_at_239'),
        ]
    
    def __str__(self) -> str:
        return f"{self.creative.name} - {self.action}"
