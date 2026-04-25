"""
A/B Test Models for Offer Routing System

This module contains models for A/B testing functionality,
including test configuration, assignments, and results tracking.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import ABTestVariant, RoutingDecisionReason
from ..constants import (
    DEFAULT_AB_TEST_SPLIT_PERCENTAGE, MIN_AB_TEST_DURATION_HOURS,
    MAX_AB_TEST_DURATION_DAYS, STATISTICAL_SIGNIFICANCE_THRESHOLD
)

User = get_user_model()


class RoutingABTest(models.Model):
    """
    A/B test configuration for offer routing.
    
    Defines experiments to test different routing strategies,
    offer variations, or personalization approaches.
    """
    
    name = models.CharField(_('Test Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ab_tests',
        verbose_name=_('tenants.Tenant')
    )
    
    # Test configuration
    control_route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='ab_tests_control',
        verbose_name=_('Control Route')
    )
    variant_route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='ab_tests_variant',
        verbose_name=_('Variant Route')
    )
    split_percentage = models.IntegerField(
        _('Split Percentage'),
        default=DEFAULT_AB_TEST_SPLIT_PERCENTAGE,
        help_text=_('Percentage of traffic to send to variant (0-100)')
    )
    
    # Test status and timing
    is_active = models.BooleanField(_('Is Active'), default=True)
    started_at = models.DateTimeField(_('Started At'), null=True, blank=True)
    ended_at = models.DateTimeField(_('Ended At'), null=True, blank=True)
    duration_hours = models.IntegerField(
        _('Duration (Hours)'),
        null=True,
        blank=True,
        help_text=_('Planned duration in hours')
    )
    
    # Success criteria
    success_metric = models.CharField(
        _('Success Metric'),
        max_length=50,
        choices=[
            ('conversion_rate', _('Conversion Rate')),
            ('revenue_per_user', _('Revenue Per User')),
            ('click_through_rate', _('Click Through Rate')),
            ('engagement_rate', _('Engagement Rate'))
        ],
        default='conversion_rate'
    )
    min_sample_size = models.IntegerField(
        _('Min Sample Size'),
        default=1000,
        help_text=_('Minimum sample size for statistical significance')
    )
    confidence_level = models.DecimalField(
        _('Confidence Level'),
        max_digits=3,
        decimal_places=2,
        default=STATISTICAL_SIGNIFICANCE_THRESHOLD,
        help_text=_('Statistical confidence level (0.0-1.0)')
    )
    
    # Results
    winner = models.CharField(
        _('Winner'),
        max_length=20,
        choices=[
            ('control', _('Control')),
            ('variant', _('Variant')),
            ('inconclusive', _('Inconclusive'))
        ],
        null=True,
        blank=True
    )
    confidence = models.DecimalField(
        _('Confidence'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Statistical confidence in winner declaration')
    )
    p_value = models.DecimalField(
        _('P-Value'),
        max_digits=8,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_('Statistical p-value for winner declaration')
    )
    effect_size = models.DecimalField(
        _('Effect Size'),
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_('Effect size for winner declaration')
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ab_tests_created_by',
        verbose_name=_('Created By')
    )
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_ab_tests'
        verbose_name = _('A/B Test')
        verbose_name_plural = _('A/B Tests')
        ordering = ['-created_at', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1186'),
            models.Index(fields=['started_at'], name='idx_started_at_1187'),
            models.Index(fields=['ended_at'], name='idx_ended_at_1188'),
            models.Index(fields=['created_at'], name='idx_created_at_1189'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.username})"
    
    def clean(self):
        """Validate model data."""
        if self.split_percentage < 1 or self.split_percentage > 99:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Split percentage must be between 1 and 99'))
        
        if self.min_sample_size < 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Min sample size must be at least 100'))
        
        if self.confidence_level < 0.8 or self.confidence_level > 0.99:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Confidence level must be between 0.8 and 0.99'))
    
    def is_running(self):
        """Check if test is currently running."""
        return self.is_active and self.started_at and not self.ended_at
    
    def is_completed(self):
        """Check if test has completed."""
        return self.ended_at is not None
    
    def duration_hours_actual(self):
        """Calculate actual duration in hours."""
        if self.started_at and self.ended_at:
            duration = self.ended_at - self.started_at
            return duration.total_seconds() / 3600
        return None
    
    def get_control_stats(self):
        """Get statistics for control group."""
        return self.assignments.filter(variant='control').aggregate(
            total_assignments=models.Count('id'),
            total_impressions=models.Sum('impressions'),
            total_clicks=models.Sum('clicks'),
            total_conversions=models.Sum('conversions'),
            total_revenue=models.Sum('revenue')
        )
    
    def get_variant_stats(self):
        """Get statistics for variant group."""
        return self.assignments.filter(variant='variant').aggregate(
            total_assignments=models.Count('id'),
            total_impressions=models.Sum('impressions'),
            total_clicks=models.Sum('clicks'),
            total_conversions=models.Sum('conversions'),
            total_revenue=models.Sum('revenue')
        )
    
    def calculate_sample_size(self):
        """Calculate required sample size for statistical significance."""
        # This would use statistical power calculation
        # For now, return default
        return self.min_sample_size


class ABTestAssignment(models.Model):
    """
    Assignment of users to A/B test variants.
    
    Tracks which users are in control group vs variant group
    for each running A/B test.
    """
    
    test = models.ForeignKey(
        RoutingABTest,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_('A/B Test')
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_('User')
    )
    variant = models.CharField(
        _('Variant'),
        max_length=20,
        choices=ABTestVariant.CHOICES,
        default=ABTestVariant.CONTROL
    )
    
    # Assignment details
    assigned_at = models.DateTimeField(_('Assigned At'), auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assignments_assigned_by',
        verbose_name=_('Assigned By')
    )
    
    # Participation tracking
    impressions = models.BigIntegerField(_('Impressions'), default=0)
    clicks = models.BigIntegerField(_('Clicks'), default=0)
    conversions = models.BigIntegerField(_('Conversions'), default=0)
    revenue = models.DecimalField(_('Revenue'), max_digits=12, decimal_places=2, default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_ab_test_assignments'
        verbose_name = _('A/B Test Assignment')
        verbose_name_plural = _('A/B Test Assignments')
        ordering = ['-assigned_at']
        unique_together = ['user', 'test']  # Prevent duplicate assignments
        indexes = [
            models.Index(fields=['test', 'user'], name='idx_test_user_1190'),
            models.Index(fields=['test', 'variant'], name='idx_test_variant_1191'),
            models.Index(fields=['assigned_at'], name='idx_assigned_at_1192'),
            models.Index(fields=['user', 'impressions'], name='idx_user_impressions_1193'),
            models.Index(fields=['user', 'conversions'], name='idx_user_conversions_1194'),
            models.Index(fields=['user', 'revenue'], name='idx_user_revenue_1195'),
            models.Index(fields=['created_at'], name='idx_created_at_1196'),
        ]
    
    def __str__(self):
        return f"{self.test.name} - {self.user.username} ({self.variant})"
    
    def clean(self):
        """Validate model data."""
        if self.impressions < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Impressions cannot be negative'))
        
        if self.clicks < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Clicks cannot be negative'))
        
        if self.conversions < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Conversions cannot be negative'))
        
        if self.revenue < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Revenue cannot be negative'))
        
        # Check for existing assignment to prevent duplicates
        if self.pk is None:  # Only check for new assignments
            existing = ABTestAssignment.objects.filter(
                user=self.user,
                test=self.test
            ).first()
            
            if existing:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    _('User {user} is already assigned to test {test}').format(
                        user=self.user.username,
                        test=self.test.name
                    )
                )
        
        # Validate test is active
        if self.test and not self.test.is_active:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Cannot assign users to inactive test'))
        
        # Validate variant is valid for this test
        if self.test and self.variant not in ['control', 'variant']:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Invalid variant: must be "control" or "variant"'))
    
    def calculate_conversion_rate(self):
        """Calculate conversion rate."""
        if self.impressions == 0:
            return 0.0
        return (self.conversions / self.impressions) * 100
    
    def calculate_revenue_per_impression(self):
        """Calculate revenue per impression."""
        if self.impressions == 0:
            return 0.0
        return float(self.revenue) / self.impressions


class ABTestResult(models.Model):
    """
    Final results and analysis for A/B tests.
    
    Stores statistical analysis, winner declaration,
    and performance metrics for completed tests.
    """
    
    test = models.OneToOneField(
        RoutingABTest,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name=_('A/B Test')
    )
    
    # Statistical results
    control_impressions = models.BigIntegerField(_('Control Impressions'), default=0)
    control_clicks = models.BigIntegerField(_('Control Clicks'), default=0)
    control_conversions = models.BigIntegerField(_('Control Conversions'), default=0)
    control_revenue = models.DecimalField(_('Control Revenue'), max_digits=12, decimal_places=2, default=0.0)
    
    variant_impressions = models.BigIntegerField(_('Variant Impressions'), default=0)
    variant_clicks = models.BigIntegerField(_('Variant Clicks'), default=0)
    variant_conversions = models.BigIntegerField(_('Variant Conversions'), default=0)
    variant_revenue = models.DecimalField(_('Variant Revenue'), max_digits=12, decimal_places=2, default=0.0)
    
    # Statistical analysis
    control_cr = models.DecimalField(_('Control CR'), max_digits=5, decimal_places=2, default=0.0)
    variant_cr = models.DecimalField(_('Variant CR'), max_digits=5, decimal_places=2, default=0.0)
    cr_difference = models.DecimalField(_('CR Difference'), max_digits=5, decimal_places=2, default=0.0)
    
    # Statistical significance
    z_score = models.DecimalField(_('Z-Score'), max_digits=8, decimal_places=4, default=0.0)
    p_value = models.DecimalField(_('P-Value'), max_digits=8, decimal_places=6, default=1.0)
    is_significant = models.BooleanField(_('Is Significant'), default=False)
    confidence_level = models.DecimalField(_('Confidence Level'), max_digits=3, decimal_places=2, default=0.95)
    
    # Effect size
    effect_size = models.DecimalField(_('Effect Size'), max_digits=8, decimal_places=4, default=0.0)
    effect_type = models.CharField(
        _('Effect Type'),
        max_length=20,
        choices=[
            ('small', _('Small')),
            ('medium', _('Medium')),
            ('large', _('Large'))
        ],
        default='small'
    )
    
    # Winner declaration
    winner = models.CharField(
        _('Winner'),
        max_length=20,
        choices=[
            ('control', _('Control')),
            ('variant', _('Variant')),
            ('inconclusive', _('Inconclusive')),
            ('no_winner', _('No Winner'))
        ],
        default='no_winner'
    )
    winner_confidence = models.DecimalField(_('Winner Confidence'), max_digits=3, decimal_places=2, default=0.0)
    justification = models.TextField(_('Justification'), blank=True)
    
    # Metadata
    analyzed_at = models.DateTimeField(_('Analyzed At'), null=True, blank=True)
    analyzed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='results_analyzed_by',
        verbose_name=_('Analyzed By')
    )
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_ab_test_results'
        verbose_name = _('A/B Test Result')
        verbose_name_plural = _('A/B Test Results')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['test'], name='idx_test_1197'),
            models.Index(fields=['analyzed_at'], name='idx_analyzed_at_1198'),
            models.Index(fields=['is_significant'], name='idx_is_significant_1199'),
            models.Index(fields=['created_at'], name='idx_created_at_1200'),
        ]
    
    def __str__(self):
        return f"{self.test.name} Result"
    
    def clean(self):
        """Validate model data."""
        if self.control_impressions < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Control impressions cannot be negative'))
        
        if self.control_clicks < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Control clicks cannot be negative'))
        
        if self.control_conversions < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Control conversions cannot be negative'))
        
        if self.control_revenue < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Control revenue cannot be negative'))
        
        if self.variant_impressions < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Variant impressions cannot be negative'))
        
        if self.variant_clicks < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Variant clicks cannot be negative'))
        
        if self.variant_conversions < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Variant conversions cannot be negative'))
        
        if self.variant_revenue < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Variant revenue cannot be negative'))
    
    def calculate_control_cr(self):
        """Calculate control conversion rate."""
        if self.control_impressions == 0:
            return 0.0
        return (self.control_conversions / self.control_impressions) * 100
    
    def calculate_variant_cr(self):
        """Calculate variant conversion rate."""
        if self.variant_impressions == 0:
            return 0.0
        return (self.variant_conversions / self.variant_impressions) * 100
    
    def calculate_cr_difference(self):
        """Calculate difference in conversion rates."""
        return self.variant_cr - self.control_cr
    
    def calculate_sample_size_required(self):
        """Calculate required sample size for observed effect."""
        # This would use statistical power calculation
        # For now, return placeholder
        return 1000
    
    def is_statistically_significant(self):
        """Check if result is statistically significant."""
        return self.is_significant and self.p_value < (1 - self.confidence_level)
    
    def get_effect_size_interpretation(self):
        """Get human-readable interpretation of effect size."""
        if abs(self.effect_size) < 0.2:
            return 'small'
        elif abs(self.effect_size) < 0.5:
            return 'medium'
        else:
            return 'large'


# Custom managers for A/B test models
class ABTestManager(models.Manager):
    """Custom manager for RoutingABTest with utility methods."""
    
    def get_active_tests(self):
        """Get all currently active A/B tests."""
        return self.filter(is_active=True)
    
    def get_tests_by_tenant(self, tenant_id):
        """Get all tests for a specific tenant."""
        return self.filter(tenant_id=tenant_id)
    
    def get_completed_tests(self):
        """Get all completed A/B tests."""
        return self.filter(ended_at__isnull=False)
    
    def get_tests_needing_analysis(self):
        """Get tests that need statistical analysis."""
        return self.filter(
            is_active=False,
            ended_at__isnull=False,
            results__isnull=True
        )
    
    def get_recent_tests(self, days=30):
        """Get tests started in the last N days."""
        from django.utils import timezone
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.filter(started_at__gte=cutoff_date)
    
    def create_test(self, name, tenant, control_route, variant_route, **kwargs):
        """Create a new A/B test."""
        return self.create(
            name=name,
            tenant=tenant,
            control_route=control_route,
            variant_route=variant_route,
            **kwargs
        )
    
    def stop_test(self, test_id):
        """Stop an active A/B test."""
        test = self.get(id=test_id)
        test.is_active = False
        test.ended_at = timezone.now()
        test.save()
        return test


class ABTestAssignmentManager(models.Manager):
    """Custom manager for ABTestAssignment with utility methods."""
    
    def get_user_assignments(self, user_id):
        """Get all assignments for a specific user."""
        return self.filter(user_id=user_id)
    
    def get_test_assignments(self, test_id):
        """Get all assignments for a specific test."""
        return self.filter(test_id=test_id)
    
    def get_variant_assignments(self, test_id, variant):
        """Get all assignments for a specific variant."""
        return self.filter(test_id=test_id, variant=variant)
    
    def get_active_assignments(self):
        """Get all active assignments."""
        return self.filter(test__is_active=True)
    
    def calculate_test_stats(self, test_id):
        """Calculate comprehensive statistics for a test."""
        assignments = self.filter(test_id=test_id)
        
        return assignments.aggregate(
            total_assignments=models.Count('id'),
            control_assignments=models.Count('id', filter=models.Q(variant='control')),
            variant_assignments=models.Count('id', filter=models.Q(variant='variant')),
            total_impressions=models.Sum('impressions'),
            total_clicks=models.Sum('clicks'),
            total_conversions=models.Sum('conversions'),
            total_revenue=models.Sum('revenue'),
            control_cr=models.Avg('conversions', filter=models.Q(variant='control')),
            variant_cr=models.Avg('conversions', filter=models.Q(variant='variant')),
            control_revenue=models.Sum('revenue', filter=models.Q(variant='control')),
            variant_revenue=models.Sum('revenue', filter=models.Q(variant='variant')),
        )


class ABTestResultManager(models.Manager):
    """Custom manager for ABTestResult with utility methods."""
    
    def get_results_by_test(self, test_id):
        """Get all results for a specific test."""
        return self.filter(test_id=test_id)
    
    def get_significant_results(self):
        """Get all statistically significant results."""
        return self.filter(is_significant=True)
    
    def get_results_by_tenant(self, tenant_id):
        """Get all results for a specific tenant."""
        return self.filter(test__tenant_id=tenant_id)
    
    def get_recent_results(self, days=30):
        """Get results analyzed in the last N days."""
        from django.utils import timezone
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.filter(analyzed_at__gte=cutoff_date)
    
    def get_winner_distribution(self):
        """Get distribution of winners."""
        return self.values('winner').annotate(
            count=models.Count('id')
        )
    
    def calculate_overall_stats(self):
        """Calculate overall A/B testing statistics."""
        return self.aggregate(
            total_tests=models.Count('id'),
            significant_tests=models.Count('id', filter=models.Q(is_significant=True)),
            control_wins=models.Count('id', filter=models.Q(winner='control')),
            variant_wins=models.Count('id', filter=models.Q(winner='variant')),
            avg_confidence=models.Avg('winner_confidence'),
            avg_effect_size=models.Avg('effect_size'),
        )


# Add custom managers to models
RoutingABTest.add_manager_class = ABTestManager
ABTestAssignment.add_manager_class = ABTestAssignmentManager
ABTestResult.add_manager_class = ABTestResultManager
