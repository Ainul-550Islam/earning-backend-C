from django.conf import settings
"""
Bidding Database Model

This module contains the Bid model and related models
for managing bidding operations and strategies.
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


class Bid(AdvertiserPortalBaseModel, StatusModel, AuditModel, TrackingModel):
    """
    Main bid model for managing bidding operations.
    
    This model stores all bid information including amounts,
    strategies, targeting settings, and performance metrics.
    """
    
    # Campaign relationship
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='bids',
        help_text="Associated campaign"
    )
    
    # Bid details
    bid_type = models.CharField(
        max_length=50,
        choices=BidTypeEnum.choices(),
        default=BidTypeEnum.CPC,
        help_text="Type of bid (CPC, CPM, CPA, CPV)"
    )
    
    bid_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Bid amount in campaign currency"
    )
    
    bid_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Bid currency code"
    )
    
    # Bid strategy and optimization
    bid_strategy = models.CharField(
        max_length=50,
        choices=BidStrategyEnum.choices(),
        default=BidStrategyEnum.MANUAL,
        help_text="Bid strategy type"
    )
    
    max_bid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum bid amount"
    )
    
    min_bid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum bid amount"
    )
    
    # Targeting and creative
    targeting_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Targeting criteria in JSON format"
    )
    
    creative_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of creative IDs"
    )
    
    bid_adjustments = models.JSONField(
        default=dict,
        blank=True,
        help_text="Bid adjustments by device, location, etc."
    )
    
    # Performance tracking
    total_impressions = models.BigIntegerField(
        default=0,
        help_text="Total impressions served"
    )
    
    total_clicks = models.BigIntegerField(
        default=0,
        help_text="Total clicks received"
    )
    
    total_conversions = models.BigIntegerField(
        default=0,
        help_text="Total conversions generated"
    )
    
    total_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount spent"
    )
    
    avg_position = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.0'),
        help_text="Average ad position"
    )
    
    quality_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal('5.0'),
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('10.0'))],
        help_text="Quality score (1-10)"
    )
    
    # Optimization metadata
    optimized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last optimization timestamp"
    )
    
    optimized_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='optimized_bids',
        help_text="User who last optimized this bid"
    )
    
    optimization_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optimization metadata and history"
    )
    
    fraud_check_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Fraud check results and metadata"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_bids'
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['bid_type', 'bid_amount']),
            models.Index(fields=['created_at']),
            models.Index(fields=['optimized_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.campaign.name} - {self.bid_type} ${self.bid_amount}"
    
    def clean(self):
        """Validate bid data."""
        super().clean()
        
        if self.min_bid and self.max_bid and self.min_bid > self.max_bid:
            raise ValidationError("Minimum bid cannot be greater than maximum bid")
        
        if self.bid_amount < self.min_bid or (self.max_bid and self.bid_amount > self.max_bid):
            raise ValidationError("Bid amount must be within min/max bid range")
    
    def calculate_ctr(self) -> Decimal:
        """Calculate click-through rate."""
        if self.total_impressions == 0:
            return Decimal('0.00')
        return (Decimal(self.total_clicks) / Decimal(self.total_impressions)) * Decimal('100')
    
    def calculate_cpc(self) -> Decimal:
        """Calculate cost per click."""
        if self.total_clicks == 0:
            return Decimal('0.00')
        return self.total_spend / Decimal(self.total_clicks)
    
    def calculate_cpa(self) -> Decimal:
        """Calculate cost per acquisition."""
        if self.total_conversions == 0:
            return Decimal('0.00')
        return self.total_spend / Decimal(self.total_conversions)


class BidStrategy(AdvertiserPortalBaseModel, StatusModel, AuditModel):
    """
    Bid strategy configuration model.
    
    This model stores bid strategy settings and parameters
    for automated bidding optimization.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='bid_strategies',
        help_text="Associated advertiser"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Strategy name"
    )
    
    strategy_type = models.CharField(
        max_length=50,
        choices=BidStrategyEnum.choices(),
        help_text="Strategy type"
    )
    
    # Strategy parameters
    target_cpa = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target cost per acquisition"
    )
    
    target_roas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target return on ad spend"
    )
    
    max_cpc_bid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum cost per click bid"
    )
    
    daily_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Daily budget limit"
    )
    
    # Optimization settings
    optimization_goal = models.CharField(
        max_length=50,
        choices=OptimizationGoalEnum.choices(),
        default=OptimizationGoalEnum.CONVERSIONS,
        help_text="Optimization goal"
    )
    
    bid_adjustment_enabled = models.BooleanField(
        default=True,
        help_text="Enable automatic bid adjustments"
    )
    
    learning_enabled = models.BooleanField(
        default=True,
        help_text="Enable machine learning optimization"
    )
    
    strategy_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Strategy-specific configuration"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_bid_strategies'
        unique_together = [['advertiser', 'name']]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.advertiser.company_name} - {self.name}"


class BidOptimization(AdvertiserPortalBaseModel, AuditModel):
    """
    Bid optimization history model.
    
    This model tracks all bid optimization attempts and results.
    """
    
    bid = models.ForeignKey(
        Bid,
        on_delete=models.CASCADE,
        related_name='optimizations',
        help_text="Associated bid"
    )
    
    optimization_type = models.CharField(
        max_length=50,
        choices=OptimizationTypeEnum.choices(),
        help_text="Type of optimization performed"
    )
    
    old_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Previous bid amount"
    )
    
    new_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="New bid amount after optimization"
    )
    
    optimization_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optimization algorithm data and metrics"
    )
    
    performance_before = models.JSONField(
        default=dict,
        blank=True,
        help_text="Performance metrics before optimization"
    )
    
    performance_after = models.JSONField(
        default=dict,
        blank=True,
        help_text="Performance metrics after optimization"
    )
    
    reason = models.TextField(
        blank=True,
        help_text="Reason for optimization"
    )
    
    confidence_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('1.00'))],
        help_text="Confidence score for optimization (0-1)"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_bid_optimizations'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.bid} - {self.optimization_type}"


class BudgetAllocation(AdvertiserPortalBaseModel, StatusModel, AuditModel):
    """
    Budget allocation model for campaigns and bids.
    
    This model manages budget distribution across campaigns
    and individual bids.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='budget_allocations',
        help_text="Associated advertiser"
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='budget_allocations',
        help_text="Associated campaign (null for advertiser-level)"
    )
    
    bid = models.ForeignKey(
        Bid,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='budget_allocations',
        help_text="Associated bid (null for campaign-level)"
    )
    
    allocation_type = models.CharField(
        max_length=50,
        choices=BudgetAllocationTypeEnum.choices(),
        help_text="Type of budget allocation"
    )
    
    allocated_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Allocated budget amount"
    )
    
    spent_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount already spent"
    )
    
    remaining_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Remaining budget amount"
    )
    
    allocation_period = models.CharField(
        max_length=50,
        choices=BudgetPeriodEnum.choices(),
        default=BudgetPeriodEnum.DAILY,
        help_text="Budget allocation period"
    )
    
    start_date = models.DateTimeField(
        help_text="Allocation start date"
    )
    
    end_date = models.DateTimeField(
        help_text="Allocation end date"
    )
    
    auto_renew = models.BooleanField(
        default=False,
        help_text="Automatically renew allocation"
    )
    
    allocation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Budget allocation rules and conditions"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_budget_allocations'
        indexes = [
            models.Index(fields=['advertiser', 'allocation_type']),
            models.Index(fields=['campaign', 'allocation_period']),
            models.Index(fields=['bid', 'allocation_period']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        target = self.campaign or self.bid or self.advertiser
        return f"{target} - {self.allocation_type} ${self.allocated_amount}"
    
    def clean(self):
        """Validate budget allocation."""
        super().clean()
        
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date")
        
        if self.allocated_amount < 0:
            raise ValidationError("Allocated amount must be positive")
        
        # Ensure only one level of allocation is set
        allocation_count = sum([
            1 if self.campaign else 0,
            1 if self.bid else 0,
            1 if not self.campaign and not self.bid else 0
        ])
        
        if allocation_count != 1:
            raise ValidationError("Must specify exactly one: advertiser, campaign, or bid")
    
    def update_spent_amount(self, additional_spend: Decimal) -> None:
        """Update spent amount and remaining budget."""
        self.spent_amount += additional_spend
        self.remaining_amount = max(Decimal('0.00'), self.allocated_amount - self.spent_amount)
        self.save(update_fields=['spent_amount', 'remaining_amount'])
    
    def is_exhausted(self) -> bool:
        """Check if budget is exhausted."""
        return self.remaining_amount <= Decimal('0.00')
    
    def utilization_rate(self) -> Decimal:
        """Calculate budget utilization rate."""
        if self.allocated_amount == 0:
            return Decimal('0.00')
        return (self.spent_amount / self.allocated_amount) * Decimal('100')
