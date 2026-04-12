"""
Industry Database Model

This module contains industry and sub-industry classification models
for categorizing advertisers and campaigns.
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


class Industry(AdvertiserPortalBaseModel, StatusModel, AuditModel):
    """
    Main industry classification model.
    
    This model stores industry categories for classifying
    advertisers and their business activities.
    """
    
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Industry name"
    )
    
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-friendly industry identifier"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Industry description"
    )
    
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Industry classification code (e.g., NAICS code)"
    )
    
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
        help_text="Parent industry for hierarchical classification"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this industry is currently active"
    )
    
    sort_order = models.IntegerField(
        default=0,
        help_text="Order for displaying industries in lists"
    )
    
    # Business metrics
    estimated_market_size = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated market size in USD"
    )
    
    average_ad_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average advertising spend in USD"
    )
    
    growth_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Annual growth rate percentage"
    )
    
    # Regulatory information
    requires_special_approval = models.BooleanField(
        default=False,
        help_text="Whether this industry requires special approval"
    )
    
    restricted_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="List of restricted advertising categories"
    )
    
    compliance_requirements = models.JSONField(
        default=dict,
        blank=True,
        help_text="Industry-specific compliance requirements"
    )
    
    # Metadata
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon identifier for the industry"
    )
    
    color = models.CharField(
        max_length=7,
        blank=True,
        help_text="Hex color code for industry visualization"
    )
    
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for industry classification"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_industries'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'sort_order']),
            models.Index(fields=['parent']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['sort_order', 'name']
        verbose_name_plural = "Industries"
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate industry data."""
        super().clean()
        
        if self.parent and self.parent.parent:
            raise ValidationError("Industry hierarchy cannot be more than 2 levels deep")
        
        if self.growth_rate and (self.growth_rate < -100 or self.growth_rate > 1000):
            raise ValidationError("Growth rate must be between -100% and 1000%")
    
    def get_all_children(self) -> List['Industry']:
        """Get all child industries recursively."""
        children = list(self.children.all())
        for child in children:
            children.extend(child.get_all_children())
        return children
    
    def get_advertiser_count(self) -> int:
        """Get the number of advertisers in this industry."""
        from ..database_models.advertiser_model import Advertiser
        return Advertiser.objects.filter(industry=self).count()
    
    def get_total_ad_spend(self) -> Decimal:
        """Get total ad spend for this industry."""
        from ..database_models.advertiser_model import Advertiser
        result = Advertiser.objects.filter(industry=self).aggregate(
            total=Sum('total_spend')
        )
        return result['total'] or Decimal('0.00')


class SubIndustry(AdvertiserPortalBaseModel, StatusModel, AuditModel):
    """
    Sub-industry classification model.
    
    This model provides more granular classification within
    industries for better targeting and analytics.
    """
    
    industry = models.ForeignKey(
        Industry,
        on_delete=models.CASCADE,
        related_name='sub_industries',
        help_text="Parent industry"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Sub-industry name"
    )
    
    slug = models.SlugField(
        max_length=255,
        help_text="URL-friendly sub-industry identifier"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Sub-industry description"
    )
    
    code = models.CharField(
        max_length=10,
        help_text="Sub-industry classification code"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this sub-industry is currently active"
    )
    
    sort_order = models.IntegerField(
        default=0,
        help_text="Order for displaying sub-industries in lists"
    )
    
    # Business characteristics
    typical_company_size = models.CharField(
        max_length=50,
        choices=[
            ('micro', 'Micro (1-9)'),
            ('small', 'Small (10-49)'),
            ('medium', 'Medium (50-249)'),
            ('large', 'Large (250+)'),
            ('enterprise', 'Enterprise (1000+)'),
        ],
        blank=True,
        help_text="Typical company size in this sub-industry"
    )
    
    average_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average annual revenue in USD"
    )
    
    common_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Common keywords associated with this sub-industry"
    )
    
    # Advertising characteristics
    preferred_channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Preferred advertising channels"
    )
    
    typical_budget_range = models.JSONField(
        default=dict,
        blank=True,
        help_text="Typical budget range (min/max in USD)"
    )
    
    seasonal_patterns = models.JSONField(
        default=dict,
        blank=True,
        help_text="Seasonal advertising patterns"
    )
    
    # Target audience
    primary_audience = models.JSONField(
        default=dict,
        blank=True,
        help_text="Primary target audience demographics"
    )
    
    secondary_audience = models.JSONField(
        default=dict,
        blank=True,
        help_text="Secondary target audience demographics"
    )
    
    # Metadata
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon identifier for the sub-industry"
    )
    
    color = models.CharField(
        max_length=7,
        blank=True,
        help_text="Hex color code for sub-industry visualization"
    )
    
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for sub-industry classification"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_sub_industries'
        unique_together = [['industry', 'slug'], ['industry', 'code']]
        indexes = [
            models.Index(fields=['industry', 'is_active', 'sort_order']),
            models.Index(fields=['slug']),
            models.Index(fields=['code']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['industry', 'sort_order', 'name']
        verbose_name_plural = "Sub-industries"
    
    def __str__(self):
        return f"{self.industry.name} - {self.name}"
    
    def clean(self):
        """Validate sub-industry data."""
        super().clean()
        
        if self.typical_budget_range:
            min_budget = self.typical_budget_range.get('min', 0)
            max_budget = self.typical_budget_range.get('max', 0)
            
            if min_budget < 0 or max_budget < 0:
                raise ValidationError("Budget values cannot be negative")
            
            if max_budget > 0 and min_budget > max_budget:
                raise ValidationError("Minimum budget cannot be greater than maximum budget")
    
    def get_advertiser_count(self) -> int:
        """Get the number of advertisers in this sub-industry."""
        from ..database_models.advertiser_model import Advertiser
        return Advertiser.objects.filter(sub_industry=self).count()
    
    def get_total_ad_spend(self) -> Decimal:
        """Get total ad spend for this sub-industry."""
        from ..database_models.advertiser_model import Advertiser
        result = Advertiser.objects.filter(sub_industry=self).aggregate(
            total=Sum('total_spend')
        )
        return result['total'] or Decimal('0.00')


class IndustryTrend(AdvertiserPortalBaseModel, AuditModel):
    """
    Industry trend model for tracking industry performance over time.
    
    This model stores trend data and analytics for industries
    to help with market analysis and forecasting.
    """
    
    industry = models.ForeignKey(
        Industry,
        on_delete=models.CASCADE,
        related_name='trends',
        help_text="Associated industry"
    )
    
    sub_industry = models.ForeignKey(
        SubIndustry,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='trends',
        help_text="Associated sub-industry (optional)"
    )
    
    trend_date = models.DateField(
        help_text="Date for the trend data"
    )
    
    # Performance metrics
    total_advertisers = models.IntegerField(
        default=0,
        help_text="Total number of advertisers"
    )
    
    active_advertisers = models.IntegerField(
        default=0,
        help_text="Number of active advertisers"
    )
    
    total_ad_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total ad spend for the period"
    )
    
    average_cpc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average cost per click"
    )
    
    average_ctr = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average click-through rate percentage"
    )
    
    conversion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average conversion rate percentage"
    )
    
    # Market metrics
    market_share = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Market share percentage"
    )
    
    growth_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Growth rate percentage"
    )
    
    # Seasonal metrics
    seasonality_factor = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Seasonality factor (1.0 = normal, >1.0 = above average)"
    )
    
    # Additional metadata
    trend_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional trend data and metrics"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Notes about the trend period"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_industry_trends'
        unique_together = [['industry', 'sub_industry', 'trend_date']]
        indexes = [
            models.Index(fields=['industry', 'trend_date']),
            models.Index(fields=['sub_industry', 'trend_date']),
            models.Index(fields=['trend_date']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-trend_date']
    
    def __str__(self):
        target = self.sub_industry or self.industry
        return f"{target} - {self.trend_date}"
    
    def calculate_roi(self) -> Decimal:
        """Calculate return on investment for the trend period."""
        if self.total_ad_spend == 0:
            return Decimal('0.00')
        
        # This would need actual revenue data to calculate properly
        # For now, return a placeholder
        return Decimal('0.00')
    
    def get_performance_score(self) -> Decimal:
        """Calculate overall performance score (0-100)."""
        score = Decimal('50.0')  # Base score
        
        # Add points for positive metrics
        if self.growth_rate and self.growth_rate > 0:
            score += min(Decimal('20.0'), self.growth_rate / 5)
        
        if self.market_share and self.market_share > 5:
            score += min(Decimal('15.0'), self.market_share / 2)
        
        if self.seasonality_factor and self.seasonality_factor > 1.1:
            score += min(Decimal('10.0'), (self.seasonality_factor - 1) * 20)
        
        # Subtract points for negative metrics
        if self.growth_rate and self.growth_rate < -5:
            score -= min(Decimal('20.0'), abs(self.growth_rate) / 5)
        
        return max(Decimal('0.0'), min(Decimal('100.0'), score))
