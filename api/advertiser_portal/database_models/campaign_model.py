"""
Campaign Database Model

This module contains the Campaign model and related models
for managing advertising campaigns.
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


class Campaign(AdvertiserPortalBaseModel, StatusModel, AuditModel, BudgetModel, TrackingModel):
    """
    Main campaign model for managing advertising campaigns.
    
    This model stores all campaign information including objectives,
    budgets, targeting settings, and performance metrics.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='campaigns',
        help_text="Associated advertiser"
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Campaign name"
    )
    description = models.TextField(
        blank=True,
        help_text="Campaign description"
    )
    
    # Campaign Objective and Strategy
    objective = models.CharField(
        max_length=50,
        choices=CampaignObjectiveEnum.choices,
        db_index=True,
        help_text="Campaign objective"
    )
    bidding_strategy = models.CharField(
        max_length=50,
        choices=BiddingStrategyEnum.choices,
        default=BiddingStrategyEnum.MANUAL_CPC.value,
        help_text="Bidding strategy"
    )
    target_cpa = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Target cost per acquisition"
    )
    target_roas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Target return on ad spend"
    )
    
    # Schedule and Duration
    start_date = models.DateField(
        db_index=True,
        help_text="Campaign start date"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Campaign end date"
    )
    delivery_method = models.CharField(
        max_length=20,
        choices=[
            ('standard', 'Standard'),
            ('accelerated', 'Accelerated')
        ],
        default='standard',
        help_text="Budget delivery method"
    )
    
    # Time and Day Targeting
    start_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily start time (HH:MM)"
    )
    end_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily end time (HH:MM)"
    )
    days_of_week = models.JSONField(
        default=list,
        blank=True,
        help_text="Days of week to run [1-7, where 1=Monday]"
    )
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="Campaign timezone"
    )
    
    # Frequency Capping
    frequency_cap = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum impressions per user"
    )
    frequency_cap_period = models.CharField(
        max_length=20,
        choices=[
            ('hourly', 'Per Hour'),
            ('daily', 'Per Day'),
            ('weekly', 'Per Week'),
            ('monthly', 'Per Month'),
            ('campaign', 'Per Campaign')
        ],
        null=True,
        blank=True,
        help_text="Frequency cap period"
    )
    
    # Device and Platform Targeting
    device_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Device targeting settings"
    )
    platform_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Platform targeting settings"
    )
    
    # Geographic Targeting
    geo_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Geographic targeting settings"
    )
    
    # Audience Targeting
    audience_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Audience targeting settings"
    )
    
    # Content and Language Targeting
    language_targeting = models.JSONField(
        default=list,
        blank=True,
        help_text="Language targeting settings"
    )
    content_targeting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Content targeting settings"
    )
    
    # Advanced Settings
    auto_optimize = models.BooleanField(
        default=False,
        help_text="Enable automatic optimization"
    )
    optimization_goals = models.JSONField(
        default=list,
        blank=True,
        help_text="Optimization goals"
    )
    learning_phase = models.BooleanField(
        default=True,
        help_text="Whether campaign is in learning phase"
    )
    
    # Budget and Bidding
    bid_adjustments = models.JSONField(
        default=dict,
        blank=True,
        help_text="Bid adjustments by dimension"
    )
    bid_floor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.01'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Minimum bid amount"
    )
    bid_ceiling = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Maximum bid amount"
    )
    
    # Conversion Tracking
    conversion_window = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(90)],
        help_text="Conversion tracking window in days"
    )
    attribution_model = models.CharField(
        max_length=20,
        choices=[
            ('last_click', 'Last Click'),
            ('first_click', 'First Click'),
            ('linear', 'Linear'),
            ('time_decay', 'Time Decay'),
            ('position_based', 'Position Based'),
            ('data_driven', 'Data Driven')
        ],
        default='last_click',
        help_text="Conversion attribution model"
    )
    
    # Quality and Performance
    quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Campaign quality score (0-100)"
    )
    performance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Campaign performance score (0-100)"
    )
    
    # Campaign Groups and Labels
    campaign_groups = models.JSONField(
        default=list,
        blank=True,
        help_text="Campaign group labels"
    )
    labels = models.JSONField(
        default=list,
        blank=True,
        help_text="Campaign labels for organization"
    )
    
    # External Integrations
    external_campaign_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External campaign ID (e.g., Google Ads, Facebook)"
    )
    integration_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration settings"
    )
    
    # Control Settings
    auto_pause_on_budget_exhaust = models.BooleanField(
        default=True,
        help_text="Auto-pause when budget is exhausted"
    )
    auto_restart_on_budget_refill = models.BooleanField(
        default=False,
        help_text="Auto-restart when budget is refilled"
    )
    require_approval = models.BooleanField(
        default=False,
        help_text="Require approval before activation"
    )
    
    # Creative Settings
    approved_creatives_count = models.IntegerField(
        default=0,
        help_text="Number of approved creatives"
    )
    creative_rotation = models.CharField(
        max_length=20,
        choices=[
            ('optimize', 'Optimize'),
            ('rotate_evenly', 'Rotate Evenly'),
            ('rotate_indefinitely', 'Rotate Indefinitely'),
            ('weighted', 'Weighted')
        ],
        default='optimize',
        help_text="Creative rotation method"
    )
    
    class Meta:
        db_table = 'campaigns'
        verbose_name = 'Campaign'
        verbose_name_plural = 'Campaigns'
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_149'),
            models.Index(fields=['objective'], name='idx_objective_150'),
            models.Index(fields=['start_date', 'end_date'], name='idx_start_date_end_date_151'),
            models.Index(fields=['created_at'], name='idx_created_at_152'),
            models.Index(fields=['name'], name='idx_name_153'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.advertiser.company_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate date range
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        
        # Validate time range
        if self.start_time and self.end_time:
            if self.start_time == self.end_time:
                raise ValidationError("Start time and end time cannot be the same")
        
        # Validate budget
        if self.total_budget and self.total_budget < self.daily_budget:
            raise ValidationError("Total budget must be greater than or equal to daily budget")
        
        # Validate frequency capping
        if self.frequency_cap and not self.frequency_cap_period:
            raise ValidationError("Frequency cap period is required when frequency cap is set")
        
        # Validate bidding strategy requirements
        if self.bidding_strategy == BiddingStrategyEnum.TARGET_CPA.value and not self.target_cpa:
            raise ValidationError("Target CPA is required for Target CPA bidding strategy")
        
        if self.bidding_strategy == BiddingStrategyEnum.TARGET_ROAS.value and not self.target_roas:
            raise ValidationError("Target ROAS is required for Target ROAS bidding strategy")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set default values
        if not self.days_of_week:
            self.days_of_week = [1, 2, 3, 4, 5, 6, 7]  # All days
        
        # Update performance metrics
        self.update_performance_metrics()
        
        super().save(*args, **kwargs)
    
    def is_active(self) -> bool:
        """Check if campaign is currently active."""
        now = timezone.now()
        
        # Check status
        if self.status != StatusEnum.ACTIVE.value:
            return False
        
        # Check date range
        today = now.date()
        if today < self.start_date:
            return False
        
        if self.end_date and today > self.end_date:
            return False
        
        # Check time range
        if self.start_time and self.end_time:
            current_time = now.time()
            if not (self.start_time <= current_time <= self.end_time):
                return False
        
        # Check day of week
        if self.days_of_week:
            current_day = now.isoweekday()  # 1=Monday, 7=Sunday
            if current_day not in self.days_of_week:
                return False
        
        # Check budget
        if self.current_spend >= self.total_budget:
            return False
        
        return True
    
    def get_remaining_days(self) -> int:
        """Get remaining days until campaign end."""
        if not self.end_date:
            return float('inf')
        
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        
        delta = self.end_date - today
        return delta.days
    
    def get_daily_budget_remaining(self) -> Decimal:
        """Get remaining daily budget."""
        # This would typically involve more complex logic
        # For now, return total remaining budget
        return self.remaining_budget
    
    def can_spend(self, amount: Decimal) -> bool:
        """Check if campaign can spend specified amount."""
        return (self.current_spend + amount) <= self.total_budget
    
    def add_spend(self, amount: Decimal) -> bool:
        """Add spend amount and update metrics."""
        if not self.can_spend(amount):
            return False
        
        with transaction.atomic():
            self.current_spend += amount
            self.save(update_fields=['current_spend'])
            
            # Create spend record
            CampaignSpend.objects.create(
                campaign=self,
                amount=amount,
                date=timezone.now().date()
            )
            
            # Check budget threshold
            utilization = self.budget_utilization
            if utilization >= 80:
                # Trigger budget alert
                from ..events import create_budget_threshold_reached_event
                event = create_budget_threshold_reached_event(
                    campaign_id=str(self.id),
                    advertiser_id=str(self.advertiser.id),
                    threshold=80,
                    current_utilization=float(utilization)
                )
                from ..events import publish_event
                publish_event(event)
            
            if utilization >= 100 and self.auto_pause_on_budget_exhaust:
                # Auto-pause campaign
                self.status = StatusEnum.PAUSED.value
                self.save(update_fields=['status'])
            
            return True
    
    def get_targeting_summary(self) -> Dict[str, Any]:
        """Get summary of targeting settings."""
        return {
            'geo_targeting': self.geo_targeting,
            'device_targeting': self.device_targeting,
            'audience_targeting': self.audience_targeting,
            'language_targeting': self.language_targeting,
            'content_targeting': self.content_targeting,
            'schedule': {
                'start_date': self.start_date,
                'end_date': self.end_date,
                'start_time': self.start_time,
                'end_time': self.end_time,
                'days_of_week': self.days_of_week,
                'timezone': self.timezone
            },
            'frequency_capping': {
                'cap': self.frequency_cap,
                'period': self.frequency_cap_period
            } if self.frequency_cap else None
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        return {
            'budget_metrics': {
                'daily_budget': float(self.daily_budget),
                'total_budget': float(self.total_budget),
                'current_spend': float(self.current_spend),
                'remaining_budget': float(self.remaining_budget),
                'budget_utilization': float(self.budget_utilization)
            },
            'performance_metrics': {
                'impressions': self.impressions,
                'clicks': self.clicks,
                'conversions': self.conversions,
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
                'learning_phase': self.learning_phase
            }
        }
    
    def update_performance_metrics(self) -> None:
        """Update quality and performance scores."""
        # Calculate quality score based on various factors
        quality_score = 0
        
        # Advertiser verification (20 points)
        if self.advertiser.is_verified:
            quality_score += 20
        
        # Campaign completeness (20 points)
        if self.description and self.geo_targeting:
            quality_score += 10
        if self.device_targeting and self.audience_targeting:
            quality_score += 10
        
        # Budget utilization (30 points)
        if self.total_budget > 0:
            utilization = float(self.budget_utilization)
            if utilization > 0:
                quality_score += min(utilization * 0.3, 30)
        
        # Performance (30 points)
        if self.clicks > 0:
            ctr_score = min(float(self.ctr) * 6, 20)  # CTR up to 3.33% gets full points
            quality_score += ctr_score
            
            if self.conversions > 0:
                conversion_score = min(float(self.conversion_rate) * 4, 10)  # CR up to 2.5% gets full points
                quality_score += conversion_score
        
        self.quality_score = Decimal(str(min(quality_score, 100)))
        
        # Calculate performance score based on KPIs
        performance_score = 0
        
        if self.objective == CampaignObjectiveEnum.LEADS.value:
            # Focus on conversions
            if self.conversions > 0:
                performance_score = min(float(self.conversion_rate) * 20, 100)
        elif self.objective == CampaignObjectiveEnum.TRAFFIC.value:
            # Focus on clicks and CTR
            if self.clicks > 0:
                performance_score = min(float(self.ctr) * 20, 100)
        elif self.objective == CampaignObjectiveEnum.SALES.value:
            # Focus on ROAS
            if self.revenue > 0:
                performance_score = min(float(self.roas) * 10, 100)
        else:
            # General performance
            if self.clicks > 0:
                performance_score = min(float(self.ctr) * 10 + float(self.conversion_rate) * 10, 100)
        
        self.performance_score = Decimal(str(min(performance_score, 100)))
    
    def duplicate(self, new_name: Optional[str] = None) -> 'Campaign':
        """Create a duplicate of this campaign."""
        duplicate_name = new_name or f"{self.name} (Copy)"
        
        with transaction.atomic():
            new_campaign = Campaign.objects.create(
                advertiser=self.advertiser,
                name=duplicate_name,
                description=self.description,
                objective=self.objective,
                bidding_strategy=self.bidding_strategy,
                target_cpa=self.target_cpa,
                target_roas=self.target_roas,
                daily_budget=self.daily_budget,
                total_budget=self.total_budget,
                start_date=self.start_date,
                end_date=self.end_date,
                delivery_method=self.delivery_method,
                start_time=self.start_time,
                end_time=self.end_time,
                days_of_week=self.days_of_week,
                timezone=self.timezone,
                frequency_cap=self.frequency_cap,
                frequency_cap_period=self.frequency_cap_period,
                device_targeting=self.device_targeting.copy(),
                platform_targeting=self.platform_targeting.copy(),
                geo_targeting=self.geo_targeting.copy(),
                audience_targeting=self.audience_targeting.copy(),
                language_targeting=self.language_targeting.copy(),
                content_targeting=self.content_targeting.copy(),
                auto_optimize=self.auto_optimize,
                optimization_goals=self.optimization_goals.copy(),
                bid_adjustments=self.bid_adjustments.copy(),
                bid_floor=self.bid_floor,
                bid_ceiling=self.bid_ceiling,
                conversion_window=self.conversion_window,
                attribution_model=self.attribution_model,
                campaign_groups=self.campaign_groups.copy(),
                labels=self.labels.copy(),
                integration_settings=self.integration_settings.copy(),
                auto_pause_on_budget_exhaust=self.auto_pause_on_budget_exhaust,
                auto_restart_on_budget_refill=self.auto_restart_on_budget_refill,
                require_approval=self.require_approval,
                creative_rotation=self.creative_rotation,
                status=StatusEnum.PENDING.value,
                created_by=getattr(self, 'modified_by', None)
            )
            
            return new_campaign
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get optimization recommendations for this campaign."""
        recommendations = []
        
        # Budget recommendations
        utilization = float(self.budget_utilization)
        if utilization > 90:
            recommendations.append({
                'type': 'budget',
                'priority': 'high',
                'title': 'High Budget Utilization',
                'description': f'Campaign has used {utilization:.1f}% of budget. Consider increasing budget.',
                'action': 'increase_budget'
            })
        elif utilization < 30 and self.status == StatusEnum.ACTIVE.value:
            recommendations.append({
                'type': 'budget',
                'priority': 'medium',
                'title': 'Low Budget Utilization',
                'description': f'Campaign has used only {utilization:.1f}% of budget. Check targeting or increase budget.',
                'action': 'review_targeting'
            })
        
        # Performance recommendations
        if self.ctr < 1.0:
            recommendations.append({
                'type': 'performance',
                'priority': 'high',
                'title': 'Low Click-Through Rate',
                'description': f'CTR of {self.ctr:.2f}% is below average. Consider improving creatives or targeting.',
                'action': 'optimize_creatives'
            })
        
        if self.conversion_rate < 1.0:
            recommendations.append({
                'type': 'performance',
                'priority': 'medium',
                'title': 'Low Conversion Rate',
                'description': f'Conversion rate of {self.conversion_rate:.2f}% needs improvement. Review landing page and offer.',
                'action': 'optimize_landing_page'
            })
        
        # Learning phase recommendations
        if self.learning_phase and self.impressions > 1000:
            recommendations.append({
                'type': 'optimization',
                'priority': 'low',
                'title': 'Exit Learning Phase',
                'description': 'Campaign has sufficient data to exit learning phase.',
                'action': 'exit_learning_phase'
            })
        
        return recommendations


class CampaignSpend(AdvertiserPortalBaseModel):
    """
    Model for tracking daily campaign spend.
    """
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='campaign_spend_records'
    )
    date = models.DateField(
        db_index=True,
        help_text="Spend date"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Amount spent on this date"
    )
    impressions = models.BigIntegerField(
        default=0,
        help_text="Number of impressions on this date"
    )
    clicks = models.BigIntegerField(
        default=0,
        help_text="Number of clicks on this date"
    )
    conversions = models.IntegerField(
        default=0,
        help_text="Number of conversions on this date"
    )
    
    class Meta:
        db_table = 'campaign_spend'
        verbose_name = 'Campaign Spend'
        verbose_name_plural = 'Campaign Spend'
        unique_together = ['campaign', 'date']
        indexes = [
            models.Index(fields=['campaign', 'date'], name='idx_campaign_date_154'),
            models.Index(fields=['date'], name='idx_date_155'),
        ]
    
    def __str__(self) -> str:
        return f"{self.campaign.name} - {self.date} - ${self.amount}"


class CampaignGroup(AdvertiserPortalBaseModel):
    """
    Model for organizing campaigns into groups.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='campaign_groups'
    )
    name = models.CharField(
        max_length=255,
        help_text="Group name"
    )
    description = models.TextField(
        blank=True,
        help_text="Group description"
    )
    color = models.CharField(
        max_length=7,
        default='#007bff',
        help_text="Group color for UI display"
    )
    campaigns = models.ManyToManyField(
        Campaign,
        related_name='groups',
        blank=True
    )
    
    class Meta:
        db_table = 'campaign_groups'
        verbose_name = 'Campaign Group'
        verbose_name_plural = 'Campaign Groups'
        unique_together = ['advertiser', 'name']
        indexes = [
            models.Index(fields=['advertiser', 'name'], name='idx_advertiser_name_156'),
        ]
    
    def __str__(self) -> str:
        return f"{self.advertiser.company_name} - {self.name}"
    
    def get_total_budget(self) -> Decimal:
        """Get total budget for all campaigns in group."""
        return self.campaigns.aggregate(
            total=Sum('total_budget')
        )['total'] or Decimal('0')
    
    def get_total_spend(self) -> Decimal:
        """Get total spend for all campaigns in group."""
        return self.campaigns.aggregate(
            total=Sum('current_spend')
        )['total'] or Decimal('0')
    
    def get_active_campaigns_count(self) -> int:
        """Get count of active campaigns in group."""
        return self.campaigns.filter(
            status=StatusEnum.ACTIVE.value
        ).count()
