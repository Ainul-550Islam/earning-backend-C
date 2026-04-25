"""
A/B Testing Database Model

This module contains A/B Testing model and related models
for managing A/B tests and experiments.
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


class ABTest(AdvertiserPortalBaseModel, AuditModel):
    """
    Main A/B test model for managing experiments.
    
    This model stores test configurations, variants,
    and statistical analysis results.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='ab_tests',
        help_text="Associated advertiser"
    )
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='ab_tests',
        help_text="Associated campaign"
    )
    name = models.CharField(
        max_length=255,
        help_text="Test name"
    )
    description = models.TextField(
        blank=True,
        help_text="Test description"
    )
    
    # Test Configuration
    test_type = models.CharField(
        max_length=50,
        choices=[
            ('creative', 'Creative Test'),
            ('landing_page', 'Landing Page Test'),
            ('offer', 'Offer Test'),
            ('pricing', 'Pricing Test'),
            ('copy', 'Copy Test'),
            ('layout', 'Layout Test'),
            ('targeting', 'Targeting Test'),
            ('multivariate', 'Multivariate Test')
        ],
        db_index=True,
        help_text="Type of A/B test"
    )
    
    # Hypothesis and Goals
    hypothesis = models.TextField(
        help_text="Test hypothesis"
    )
    primary_metric = models.CharField(
        max_length=100,
        choices=[
            ('ctr', 'Click-Through Rate'),
            ('conversion_rate', 'Conversion Rate'),
            ('cpa', 'Cost Per Acquisition'),
            ('roas', 'Return on Ad Spend'),
            ('revenue_per_user', 'Revenue Per User'),
            ('engagement', 'Engagement Rate'),
            ('custom', 'Custom Metric')
        ],
        help_text="Primary success metric"
    )
    secondary_metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="Secondary metrics"
    )
    expected_improvement = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Expected improvement percentage"
    )
    
    # Traffic Configuration
    traffic_allocation = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100'),
        validators=[MinValueValidator(Decimal('1')), MaxValueValidator(Decimal('100'))],
        help_text="Percentage of traffic to allocate to test"
    )
    allocation_method = models.CharField(
        max_length=50,
        choices=[
            ('equal', 'Equal Distribution'),
            ('weighted', 'Weighted Distribution'),
            ('adaptive', 'Adaptive Allocation')
        ],
        default='equal',
        help_text="Traffic allocation method"
    )
    
    # Statistical Configuration
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95'),
        validators=[MinValueValidator(Decimal('80')), MaxValueValidator(Decimal('99.99'))],
        help_text="Statistical confidence level"
    )
    power_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('80'),
        validators=[MinValueValidator(Decimal('50')), MaxValueValidator(Decimal('99.99'))],
        help_text="Statistical power level"
    )
    minimum_sample_size = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(100)],
        help_text="Minimum sample size per variant"
    )
    maximum_duration = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum test duration in days"
    )
    
    # Schedule Configuration
    start_date = models.DateTimeField(
        db_index=True,
        help_text="Test start date and time"
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Test end date and time"
    )
    auto_start = models.BooleanField(
        default=False,
        help_text="Automatically start test"
    )
    auto_stop = models.BooleanField(
        default=True,
        help_text="Automatically stop test when statistically significant"
    )
    
    # Status and Control
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('running', 'Running'),
            ('paused', 'Paused'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('inconclusive', 'Inconclusive')
        ],
        default='draft',
        db_index=True,
        help_text="Test status"
    )
    
    # Results and Analysis
    winner_variant = models.CharField(
        max_length=100,
        blank=True,
        help_text="Winning variant identifier"
    )
    statistical_significance = models.BooleanField(
        default=False,
        help_text="Whether test achieved statistical significance"
    )
    confidence_interval = models.JSONField(
        default=dict,
        blank=True,
        help_text="Confidence intervals for results"
    )
    effect_size = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Effect size"
    )
    p_value = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="P-value"
    )
    
    # Business Impact
    projected_lift = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Projected lift in primary metric"
    )
    projected_revenue_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Projected revenue impact"
    )
    actual_lift = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual lift achieved"
    )
    actual_revenue_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual revenue impact"
    )
    
    # Learning and Insights
    insights = models.TextField(
        blank=True,
        help_text="Key insights from test"
    )
    recommendations = models.TextField(
        blank=True,
        help_text="Recommendations based on test results"
    )
    lessons_learned = models.TextField(
        blank=True,
        help_text="Lessons learned from test"
    )
    
    # External References
    external_test_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External test ID"
    )
    integration_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration data"
    )
    
    class Meta:
        db_table = 'ab_tests'
        verbose_name = 'A/B Test'
        verbose_name_plural = 'A/B Tests'
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_047'),
            models.Index(fields=['campaign', 'status'], name='idx_campaign_status_048'),
            models.Index(fields=['test_type'], name='idx_test_type_049'),
            models.Index(fields=['start_date'], name='idx_start_date_050'),
            models.Index(fields=['status'], name='idx_status_051'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.campaign.name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate date range
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError("Start date must be before end date")
        
        # Validate traffic allocation
        if self.traffic_allocation <= 0 or self.traffic_allocation > 100:
            raise ValidationError("Traffic allocation must be between 1 and 100")
        
        # Validate statistical parameters
        if self.confidence_level < 80 or self.confidence_level > 99.99:
            raise ValidationError("Confidence level must be between 80 and 99.99")
        
        if self.power_level < 50 or self.power_level > 99.99:
            raise ValidationError("Power level must be between 50 and 99.99")
        
        # Validate expected improvement
        if self.expected_improvement is not None and self.expected_improvement <= 0:
            raise ValidationError("Expected improvement must be positive")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Calculate minimum sample size if not set
        if not self.minimum_sample_size:
            self.minimum_sample_size = self.calculate_minimum_sample_size()
        
        super().save(*args, **kwargs)
    
    def calculate_minimum_sample_size(self) -> int:
        """Calculate minimum sample size required for statistical significance."""
        # Simplified sample size calculation
        # In practice, this would use more sophisticated statistical formulas
        
        baseline_rate = 0.02  # Assume 2% baseline conversion rate
        expected_rate = baseline_rate * (1 + (self.expected_improvement or 0.10) / 100)
        
        # Simplified formula for sample size calculation
        z_alpha = 1.96  # For 95% confidence
        z_beta = 0.84   # For 80% power
        
        pooled_rate = (baseline_rate + expected_rate) / 2
        sample_size = (2 * pooled_rate * (1 - pooled_rate) * (z_alpha + z_beta) ** 2) / ((expected_rate - baseline_rate) ** 2)
        
        return max(100, int(sample_size))
    
    def is_running(self) -> bool:
        """Check if test is currently running."""
        if self.status != 'running':
            return False
        
        now = timezone.now()
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True
    
    def get_duration_days(self) -> int:
        """Get test duration in days."""
        if not self.start_date:
            return 0
        
        end_date = self.end_date or timezone.now()
        return (end_date - self.start_date).days
    
    def get_remaining_days(self) -> int:
        """Get remaining days until test ends."""
        if not self.end_date:
            return 0
        
        remaining = self.end_date - timezone.now()
        return max(0, remaining.days)
    
    def get_variant_allocation(self, variant_count: int) -> List[float]:
        """Get traffic allocation for variants."""
        if self.allocation_method == 'equal':
            allocation = 100 / variant_count
            return [allocation] * variant_count
        
        elif self.allocation_method == 'weighted':
            # Would need to get weights from variants
            allocation = 100 / variant_count
            return [allocation] * variant_count
        
        elif self.allocation_method == 'adaptive':
            # Would need to implement adaptive allocation logic
            allocation = 100 / variant_count
            return [allocation] * variant_count
        
        return [100 / variant_count] * variant_count
    
    def can_start(self) -> bool:
        """Check if test can be started."""
        if self.status != 'draft':
            return False
        
        # Check if campaign is active
        if self.campaign.status != 'active':
            return False
        
        # Check if we have at least 2 variants
        if self.variants.count() < 2:
            return False
        
        return True
    
    def start_test(self) -> bool:
        """Start the A/B test."""
        if not self.can_start():
            return False
        
        try:
            with transaction.atomic():
                self.status = 'running'
                if not self.start_date:
                    self.start_date = timezone.now()
                self.save(update_fields=['status', 'start_date'])
                
                # Activate all variants
                self.variants.update(is_active=True)
                
                return True
        except Exception as e:
            logger.error(f"Error starting A/B test {self.id}: {str(e)}")
            return False
    
    def pause_test(self) -> bool:
        """Pause the A/B test."""
        if self.status != 'running':
            return False
        
        try:
            self.status = 'paused'
            self.save(update_fields=['status'])
            
            # Deactivate all variants
            self.variants.update(is_active=False)
            
            return True
        except Exception as e:
            logger.error(f"Error pausing A/B test {self.id}: {str(e)}")
            return False
    
    def resume_test(self) -> bool:
        """Resume the A/B test."""
        if self.status != 'paused':
            return False
        
        try:
            self.status = 'running'
            self.save(update_fields=['status'])
            
            # Reactivate all variants
            self.variants.update(is_active=True)
            
            return True
        except Exception as e:
            logger.error(f"Error resuming A/B test {self.id}: {str(e)}")
            return False
    
    def stop_test(self) -> bool:
        """Stop the A/B test."""
        if self.status not in ['running', 'paused']:
            return False
        
        try:
            with transaction.atomic():
                self.status = 'completed'
                self.end_date = timezone.now()
                
                # Analyze results
                self.analyze_results()
                
                self.save(update_fields=['status', 'end_date', 'winner_variant', 
                                       'statistical_significance', 'confidence_interval',
                                       'effect_size', 'p_value'])
                
                # Deactivate all variants
                self.variants.update(is_active=False)
                
                return True
        except Exception as e:
            logger.error(f"Error stopping A/B test {self.id}: {str(e)}")
            return False
    
    def analyze_results(self) -> None:
        """Analyze test results and determine winner."""
        variants = self.variants.all()
        
        if len(variants) < 2:
            return
        
        # Get metrics for each variant
        variant_metrics = {}
        for variant in variants:
            metrics = variant.get_metrics()
            variant_metrics[variant.variant_id] = metrics
        
        # Perform statistical analysis
        results = self._perform_statistical_analysis(variant_metrics)
        
        # Update test with results
        self.winner_variant = results.get('winner')
        self.statistical_significance = results.get('significant', False)
        self.confidence_interval = results.get('confidence_intervals', {})
        self.effect_size = results.get('effect_size')
        self.p_value = results.get('p_value')
    
    def _perform_statistical_analysis(self, variant_metrics: Dict[str, Dict]) -> Dict[str, Any]:
        """Perform statistical analysis on variant metrics."""
        # Simplified statistical analysis
        # In practice, this would use proper statistical tests
        
        results = {}
        
        # Get primary metric values
        metric_values = {}
        for variant_id, metrics in variant_metrics.items():
            metric_values[variant_id] = metrics.get(self.primary_metric, 0)
        
        if len(metric_values) < 2:
            return results
        
        # Find winner (highest value for most metrics)
        winner = max(metric_values, key=metric_values.get)
        results['winner'] = winner
        
        # Calculate effect size (simplified)
        winner_value = metric_values[winner]
        control_value = metric_values.get('control', 0)
        
        if control_value > 0:
            effect_size = (winner_value - control_value) / control_value
            results['effect_size'] = Decimal(str(effect_size))
        
        # Determine statistical significance (simplified)
        # In practice, this would use proper statistical tests
        sample_size = sum(variant.get('sample_size', 0) for variant in variant_metrics.values())
        
        if sample_size >= self.minimum_sample_size:
            # Simplified significance test
            results['significant'] = True
            results['p_value'] = Decimal('0.05')  # Placeholder
            results['confidence_intervals'] = {
                variant_id: {
                    'lower': value * 0.9,
                    'upper': value * 1.1
                }
                for variant_id, value in metric_values.items()
            }
        
        return results
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        variants = self.variants.all()
        
        return {
            'basic_info': {
                'name': self.name,
                'description': self.description,
                'test_type': self.test_type,
                'campaign': self.campaign.name,
                'status': self.status
            },
            'configuration': {
                'hypothesis': self.hypothesis,
                'primary_metric': self.primary_metric,
                'secondary_metrics': self.secondary_metrics,
                'expected_improvement': float(self.expected_improvement) if self.expected_improvement else None,
                'traffic_allocation': float(self.traffic_allocation),
                'allocation_method': self.allocation_method,
                'confidence_level': float(self.confidence_level),
                'power_level': float(self.power_level),
                'minimum_sample_size': self.minimum_sample_size
            },
            'schedule': {
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None,
                'duration_days': self.get_duration_days(),
                'remaining_days': self.get_remaining_days()
            },
            'results': {
                'winner_variant': self.winner_variant,
                'statistical_significance': self.statistical_significance,
                'effect_size': float(self.effect_size) if self.effect_size else None,
                'p_value': float(self.p_value) if self.p_value else None,
                'confidence_interval': self.confidence_interval
            },
            'variants': [
                {
                    'variant_id': variant.variant_id,
                    'name': variant.name,
                    'is_control': variant.is_control,
                    'traffic_weight': float(variant.traffic_weight),
                    'metrics': variant.get_metrics()
                }
                for variant in variants
            ],
            'business_impact': {
                'projected_lift': float(self.projected_lift) if self.projected_lift else None,
                'projected_revenue_impact': float(self.projected_revenue_impact) if self.projected_revenue_impact else None,
                'actual_lift': float(self.actual_lift) if self.actual_lift else None,
                'actual_revenue_impact': float(self.actual_revenue_impact) if self.actual_revenue_impact else None
            },
            'insights': {
                'insights': self.insights,
                'recommendations': self.recommendations,
                'lessons_learned': self.lessons_learned
            }
        }


class ABTestVariant(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing A/B test variants.
    """
    
    # Basic Information
    test = models.ForeignKey(
        ABTest,
        on_delete=models.CASCADE,
        related_name='variants',
        help_text="Associated A/B test"
    )
    variant_id = models.CharField(
        max_length=100,
        help_text="Variant identifier"
    )
    name = models.CharField(
        max_length=255,
        help_text="Variant name"
    )
    description = models.TextField(
        blank=True,
        help_text="Variant description"
    )
    
    # Variant Configuration
    variant_type = models.CharField(
        max_length=50,
        choices=[
            ('control', 'Control'),
            ('treatment', 'Treatment'),
            ('multivariate', 'Multivariate')
        ],
        help_text="Type of variant"
    )
    is_control = models.BooleanField(
        default=False,
        help_text="Whether this is the control variant"
    )
    
    # Traffic Configuration
    traffic_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('50'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))],
        help_text="Traffic weight percentage"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether variant is active"
    )
    
    # Variant Content
    creative = models.ForeignKey(
        'advertiser_portal.Creative',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ab_test_variants',
        help_text="Associated creative (for creative tests)"
    )
    landing_page_url = models.URLField(
        blank=True,
        help_text="Landing page URL (for landing page tests)"
    )
    copy_content = models.TextField(
        blank=True,
        help_text="Copy content (for copy tests)"
    )
    offer_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Offer details (for offer tests)"
    )
    pricing_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pricing details (for pricing tests)"
    )
    
    # Variant Configuration
    configuration = models.JSONField(
        default=dict,
        blank=True,
        help_text="Variant configuration settings"
    )
    custom_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom variant settings"
    )
    
    class Meta:
        db_table = 'ab_test_variants'
        verbose_name = 'A/B Test Variant'
        verbose_name_plural = 'A/B Test Variants'
        unique_together = ['test', 'variant_id']
        indexes = [
            models.Index(fields=['test', 'is_control'], name='idx_test_is_control_052'),
            models.Index(fields=['is_active'], name='idx_is_active_053'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.test.name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate traffic weight
        if self.traffic_weight <= 0 or self.traffic_weight > 100:
            raise ValidationError("Traffic weight must be between 0.01 and 100")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this variant."""
        # Get aggregated metrics from impressions, clicks, conversions
        from django.db.models import Sum, Count, Avg
        
        # Get impressions
        impressions = 0
        if self.creative:
            impressions = self.creative.impressions or 0
        
        # Get clicks
        clicks = 0
        if self.creative:
            clicks = self.creative.clicks or 0
        
        # Get conversions
        conversions = 0
        if self.creative:
            conversions = self.creative.conversions or 0
        
        # Get cost and revenue
        cost = self.creative.cost if self.creative else 0
        revenue = self.creative.revenue if self.creative else 0
        
        # Calculate derived metrics
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
        cpa = cost / conversions if conversions > 0 else 0
        roas = revenue / cost if cost > 0 else 0
        
        return {
            'sample_size': impressions,
            'impressions': impressions,
            'clicks': clicks,
            'conversions': conversions,
            'cost': float(cost),
            'revenue': float(revenue),
            'ctr': ctr,
            'conversion_rate': conversion_rate,
            'cpa': float(cpa),
            'roas': float(roas),
            'traffic_weight': float(self.traffic_weight)
        }


class ABTestResult(AdvertiserPortalBaseModel):
    """
    Model for storing A/B test results and analysis.
    """
    
    # Basic Information
    test = models.ForeignKey(
        ABTest,
        on_delete=models.CASCADE,
        related_name='results',
        help_text="Associated A/B test"
    )
    variant = models.ForeignKey(
        ABTestVariant,
        on_delete=models.CASCADE,
        related_name='results',
        help_text="Associated variant"
    )
    
    # Result Data
    metric_name = models.CharField(
        max_length=100,
        help_text="Metric name"
    )
    metric_value = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        help_text="Metric value"
    )
    sample_size = models.IntegerField(
        help_text="Sample size for this result"
    )
    
    # Statistical Measures
    standard_error = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Standard error"
    )
    confidence_interval_lower = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Lower bound of confidence interval"
    )
    confidence_interval_upper = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Upper bound of confidence interval"
    )
    
    # Comparison Measures
    lift_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Lift percentage compared to control"
    )
    p_value = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="P-value for statistical significance"
    )
    is_significant = models.BooleanField(
        default=False,
        help_text="Whether result is statistically significant"
    )
    
    # Timestamp
    result_date = models.DateField(
        help_text="Date of result calculation"
    )
    
    class Meta:
        db_table = 'ab_test_results'
        verbose_name = 'A/B Test Result'
        verbose_name_plural = 'A/B Test Results'
        unique_together = ['test', 'variant', 'metric_name', 'result_date']
        indexes = [
            models.Index(fields=['test', 'result_date'], name='idx_test_result_date_054'),
            models.Index(fields=['variant', 'metric_name'], name='idx_variant_metric_name_055'),
            models.Index(fields=['metric_name'], name='idx_metric_name_056'),
            models.Index(fields=['is_significant'], name='idx_is_significant_057'),
        ]
    
    def __str__(self) -> str:
        return f"{self.test.name} - {self.variant.name} - {self.metric_name}"


class ABTestInsight(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for storing A/B test insights and learnings.
    """
    
    # Basic Information
    test = models.ForeignKey(
        ABTest,
        on_delete=models.CASCADE,
        related_name='test_insights',
        help_text="Associated A/B test"
    )
    
    # Insight Content
    insight_type = models.CharField(
        max_length=50,
        choices=[
            ('performance', 'Performance Insight'),
            ('behavioral', 'Behavioral Insight'),
            ('demographic', 'Demographic Insight'),
            ('technical', 'Technical Insight'),
            ('business', 'Business Insight')
        ],
        help_text="Type of insight"
    )
    title = models.CharField(
        max_length=255,
        help_text="Insight title"
    )
    description = models.TextField(
        help_text="Insight description"
    )
    
    # Insight Data
    supporting_data = models.JSONField(
        default=dict,
        help_text="Supporting data for insight"
    )
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Confidence level in insight (0-100)"
    )
    
    # Action Items
    actionable = models.BooleanField(
        default=True,
        help_text="Whether insight is actionable"
    )
    action_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Recommended action items"
    )
    
    class Meta:
        db_table = 'ab_test_insights'
        verbose_name = 'A/B Test Insight'
        verbose_name_plural = 'A/B Test Insights'
        indexes = [
            models.Index(fields=['test', 'insight_type'], name='idx_test_insight_type_058'),
            models.Index(fields=['actionable'], name='idx_actionable_059'),
        ]
    
    def __str__(self) -> str:
        return f"{self.title} ({self.test.name})"

# Aliases for backward-compatible imports
TestVariant = ABTestVariant
TestResult = ABTestResult
TestMetrics = ABTestInsight
