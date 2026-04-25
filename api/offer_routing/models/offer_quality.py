"""
Offer Quality Score Model for Offer Routing System

This module provides comprehensive offer quality scoring and tracking,
including performance metrics, user feedback, and quality optimization.
"""

import logging
from typing import Dict, Any, List
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferQualityScore(models.Model):
    """
    Model for storing offer quality scores and metrics.
    
    Tracks various quality dimensions including:
    - Performance metrics
    - User engagement
    - Revenue generation
    - Fraud indicators
    - Network reliability
    """
    
    # Core relationships
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='quality_scores',
        verbose_name=_('Offer'),
        help_text=_('Offer route this quality score belongs to')
    )
    
    network = models.ForeignKey(
        'offer_inventory.OfferNetwork',
        on_delete=models.CASCADE,
        related_name='quality_scores',
        null=True,
        blank=True,
        verbose_name=_('Network'),
        help_text=_('Network this quality score belongs to')
    )
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='quality_scores',
        verbose_name=_('tenants.Tenant'),
        help_text=_('Tenant this quality score belongs to')
    )
    
    # Quality score components
    performance_score = models.DecimalField(
        _('Performance Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Performance score (0-100)')
    )
    
    engagement_score = models.DecimalField(
        _('Engagement Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('User engagement score (0-100)')
    )
    
    revenue_score = models.DecimalField(
        _('Revenue Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Revenue generation score (0-100)')
    )
    
    fraud_score = models.DecimalField(
        _('Fraud Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Fraud risk score (0-100, lower is better)')
    )
    
    reliability_score = models.DecimalField(
        _('Reliability Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Network reliability score (0-100)')
    )
    
    user_feedback_score = models.DecimalField(
        _('User Feedback Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('User feedback score (0-100)')
    )
    
    # Overall quality score
    overall_score = models.DecimalField(
        _('Overall Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        db_index=True,
        help_text=_('Overall quality score (0-100)')
    )
    
    quality_grade = models.CharField(
        _('Quality Grade'),
        max_length=2,
        choices=[
            ('A+', _('A+ (Excellent)')),
            ('A', _('A (Very Good)')),
            ('B+', _('B+ (Good)')),
            ('B', _('B (Average)')),
            ('C+', _('C+ (Below Average)')),
            ('C', _('C (Poor)')),
            ('D', _('D (Very Poor)')),
            ('F', _('F (Failing)')),
        ],
        default='C',
        db_index=True,
        help_text=_('Quality grade based on overall score')
    )
    
    # Performance metrics
    total_impressions = models.IntegerField(
        _('Total Impressions'),
        default=0,
        help_text=_('Total number of impressions')
    )
    
    total_clicks = models.IntegerField(
        _('Total Clicks'),
        default=0,
        help_text=_('Total number of clicks')
    )
    
    total_conversions = models.IntegerField(
        _('Total Conversions'),
        default=0,
        help_text=_('Total number of conversions')
    )
    
    total_revenue = models.DecimalField(
        _('Total Revenue'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Total revenue generated')
    )
    
    # Calculated metrics
    click_through_rate = models.DecimalField(
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
    
    epc = models.DecimalField(
        _('Earnings Per Click'),
        max_digits=8,
        decimal_places=4,
        default=0.0000,
        help_text=_('Earnings per click')
    )
    
    ecpm = models.DecimalField(
        _('Earnings Per Mille'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Earnings per 1000 impressions')
    )
    
    # Quality factors
    avg_response_time = models.DecimalField(
        _('Average Response Time'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Average response time in milliseconds')
    )
    
    uptime_percentage = models.DecimalField(
        _('Uptime Percentage'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Network uptime percentage')
    )
    
    error_rate = models.DecimalField(
        _('Error Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Error rate percentage')
    )
    
    # User engagement metrics
    avg_session_duration = models.DecimalField(
        _('Average Session Duration'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Average session duration in seconds')
    )
    
    bounce_rate = models.DecimalField(
        _('Bounce Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Bounce rate percentage')
    )
    
    return_user_rate = models.DecimalField(
        _('Return User Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Return user rate percentage')
    )
    
    # Time-based metrics
    score_calculation_date = models.DateTimeField(
        _('Score Calculation Date'),
        auto_now_add=True,
        help_text=_('Date when quality score was calculated')
    )
    
    data_period_start = models.DateTimeField(
        _('Data Period Start'),
        help_text=_('Start date of data period used for scoring')
    )
    
    data_period_end = models.DateTimeField(
        _('Data Period End'),
        help_text=_('End date of data period used for scoring')
    )
    
    # Quality trends
    score_trend = models.CharField(
        _('Score Trend'),
        max_length=10,
        choices=[
            ('improving', _('Improving')),
            ('stable', _('Stable')),
            ('declining', _('Declining')),
            ('volatile', _('Volatile')),
        ],
        default='stable',
        help_text=_('Trend of quality score over time')
    )
    
    trend_percentage = models.DecimalField(
        _('Trend Percentage'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Percentage change in quality score')
    )
    
    # Quality flags
    is_high_quality = models.BooleanField(
        _('Is High Quality'),
        default=False,
        db_index=True,
        help_text=_('Whether this offer is considered high quality')
    )
    
    is_recommended = models.BooleanField(
        _('Is Recommended'),
        default=False,
        db_index=True,
        help_text=_('Whether this offer is recommended for routing')
    )
    
    needs_review = models.BooleanField(
        _('Needs Review'),
        default=False,
        db_index=True,
        help_text=_('Whether this offer needs manual review')
    )
    
    has_quality_issues = models.BooleanField(
        _('Has Quality Issues'),
        default=False,
        help_text=_('Whether this offer has quality issues')
    )
    
    # Additional data
    quality_factors = models.JSONField(
        _('Quality Factors'),
        default=dict,
        blank=True,
        help_text=_('Additional quality factors and weights')
    )
    
    benchmark_comparison = models.JSONField(
        _('Benchmark Comparison'),
        default=dict,
        blank=True,
        help_text=_('Comparison with industry benchmarks')
    )
    
    improvement_suggestions = models.JSONField(
        _('Improvement Suggestions'),
        default=list,
        blank=True,
        help_text=_('Suggestions for improving quality score')
    )
    
    # Metadata
    calculation_method = models.CharField(
        _('Calculation Method'),
        max_length=50,
        choices=[
            ('automatic', _('Automatic')),
            ('manual', _('Manual')),
            ('hybrid', _('Hybrid')),
            ('ml_based', _('ML Based')),
        ],
        default='automatic',
        help_text=_('Method used to calculate quality score')
    )
    
    last_reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_quality_scores',
        verbose_name=_('Last Reviewed By'),
        help_text=_('User who last reviewed this quality score')
    )
    
    last_reviewed_at = models.DateTimeField(
        _('Last Reviewed At'),
        null=True,
        blank=True,
        help_text=_('Timestamp when this quality score was last reviewed')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('Timestamp when this quality score was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('Timestamp when this quality score was last updated')
    )
    
    class Meta:
        db_table = 'offer_routing_offer_quality_score'
        verbose_name = _('Offer Quality Score')
        verbose_name_plural = _('Offer Quality Scores')
        ordering = ['-overall_score', '-score_calculation_date']
        indexes = [
            models.Index(fields=['offer', 'overall_score'], name='idx_offer_overall_score_1283'),
            models.Index(fields=['network', 'overall_score'], name='idx_network_overall_score_1284'),
            models.Index(fields=['tenant', 'overall_score'], name='idx_tenant_overall_score_1285'),
            models.Index(fields=['quality_grade'], name='idx_quality_grade_1286'),
            models.Index(fields=['is_high_quality', 'is_recommended'], name='idx_is_high_quality_is_rec_226'),
            models.Index(fields=['score_calculation_date'], name='idx_score_calculation_date_c98'),
            models.Index(fields=['needs_review', 'has_quality_issues'], name='idx_needs_review_has_quali_de8'),
        ]
        unique_together = [
            ['offer', 'data_period_start', 'data_period_end'],
        ]
    
    def __str__(self):
        return f"Quality Score: {self.offer.name} - {self.overall_score} ({self.quality_grade})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate score ranges
        for field_name in ['performance_score', 'engagement_score', 'revenue_score', 'fraud_score', 'reliability_score', 'user_feedback_score', 'overall_score']:
            score = getattr(self, field_name)
            if score < 0 or score > 100:
                raise ValidationError(_(f'{field_name} must be between 0 and 100'))
        
        # Validate percentage fields
        for field_name in ['click_through_rate', 'conversion_rate', 'uptime_percentage', 'error_rate', 'bounce_rate', 'return_user_rate']:
            percentage = getattr(self, field_name)
            if percentage < 0 or percentage > 100:
                raise ValidationError(_(f'{field_name} must be between 0 and 100'))
        
        # Validate data period
        if self.data_period_start and self.data_period_end:
            if self.data_period_start >= self.data_period_end:
                raise ValidationError(_('Data period start must be before end'))
    
    def save(self, *args, **kwargs):
        """Override save to calculate derived fields."""
        # Set data period if not provided
        if not self.data_period_start or not self.data_period_end:
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=30)  # Default 30-day period
            self.data_period_start = start_date
            self.data_period_end = end_date
        
        # Calculate derived metrics
        self._calculate_derived_metrics()
        
        # Calculate overall score
        self._calculate_overall_score()
        
        # Set quality grade
        self._set_quality_grade()
        
        # Set quality flags
        self._set_quality_flags()
        
        super().save(*args, **kwargs)
    
    def _calculate_derived_metrics(self):
        """Calculate derived metrics from raw data."""
        # Calculate click through rate
        if self.total_impressions > 0:
            self.click_through_rate = (self.total_clicks / self.total_impressions) * 100
        
        # Calculate conversion rate
        if self.total_clicks > 0:
            self.conversion_rate = (self.total_conversions / self.total_clicks) * 100
        
        # Calculate EPC
        if self.total_clicks > 0:
            self.epc = self.total_revenue / self.total_clicks
        
        # Calculate eCPM
        if self.total_impressions > 0:
            self.ecpm = (self.total_revenue / self.total_impressions) * 1000
    
    def _calculate_overall_score(self):
        """Calculate overall quality score from component scores."""
        # Weight the different components
        weights = {
            'performance_score': 0.25,
            'engagement_score': 0.20,
            'revenue_score': 0.25,
            'fraud_score': 0.15,  # Lower fraud score is better, so we invert it
            'reliability_score': 0.10,
            'user_feedback_score': 0.05,
        }
        
        # Calculate weighted average
        weighted_sum = 0
        total_weight = 0
        
        for component, weight in weights.items():
            score = getattr(self, component)
            if component == 'fraud_score':
                # Invert fraud score (lower is better)
                score = 100 - score
            
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight > 0:
            self.overall_score = weighted_sum / total_weight
        else:
            self.overall_score = 0
    
    def _set_quality_grade(self):
        """Set quality grade based on overall score."""
        score = float(self.overall_score)
        
        if score >= 95:
            self.quality_grade = 'A+'
        elif score >= 90:
            self.quality_grade = 'A'
        elif score >= 85:
            self.quality_grade = 'B+'
        elif score >= 80:
            self.quality_grade = 'B'
        elif score >= 75:
            self.quality_grade = 'C+'
        elif score >= 70:
            self.quality_grade = 'C'
        elif score >= 60:
            self.quality_grade = 'D'
        else:
            self.quality_grade = 'F'
    
    def _set_quality_flags(self):
        """Set quality flags based on scores."""
        # High quality threshold
        self.is_high_quality = self.overall_score >= 85
        
        # Recommended threshold
        self.is_recommended = (
            self.overall_score >= 80 and
            self.fraud_score <= 20 and
            self.error_rate <= 5
        )
        
        # Needs review threshold
        self.needs_review = (
            self.overall_score < 60 or
            self.fraud_score > 50 or
            self.error_rate > 10
        )
        
        # Quality issues threshold
        self.has_quality_issues = (
            self.overall_score < 50 or
            self.fraud_score > 70 or
            self.error_rate > 15
        )
    
    @property
    def grade_color(self) -> str:
        """Get color code for quality grade."""
        colors = {
            'A+': '#00C851',  # Green
            'A': '#00C851',
            'B+': '#FFD600',  # Yellow
            'B': '#FFD600',
            'C+': '#FF8800',  # Orange
            'C': '#FF8800',
            'D': '#CC0000',  # Red
            'F': '#CC0000',
        }
        return colors.get(self.quality_grade, '#666666')
    
    @property
    def performance_level(self) -> str:
        """Get performance level description."""
        if self.overall_score >= 90:
            return 'Excellent'
        elif self.overall_score >= 80:
            return 'Very Good'
        elif self.overall_score >= 70:
            return 'Good'
        elif self.overall_score >= 60:
            return 'Average'
        elif self.overall_score >= 50:
            return 'Below Average'
        else:
            return 'Poor'
    
    @property
    def days_since_calculation(self) -> int:
        """Get days since score calculation."""
        if self.score_calculation_date:
            return (timezone.now() - self.score_calculation_date).days
        return 0
    
    @property
    def is_outdated(self) -> bool:
        """Check if quality score is outdated (older than 7 days)."""
        return self.days_since_calculation > 7
    
    def get_score_breakdown(self) -> Dict[str, any]:
        """Get detailed breakdown of quality score."""
        return {
            'overall_score': float(self.overall_score),
            'quality_grade': self.quality_grade,
            'performance_level': self.performance_level,
            'components': {
                'performance_score': float(self.performance_score),
                'engagement_score': float(self.engagement_score),
                'revenue_score': float(self.revenue_score),
                'fraud_score': float(self.fraud_score),
                'reliability_score': float(self.reliability_score),
                'user_feedback_score': float(self.user_feedback_score),
            },
            'metrics': {
                'total_impressions': self.total_impressions,
                'total_clicks': self.total_clicks,
                'total_conversions': self.total_conversions,
                'total_revenue': float(self.total_revenue),
                'click_through_rate': float(self.click_through_rate),
                'conversion_rate': float(self.conversion_rate),
                'epc': float(self.epc),
                'ecpm': float(self.ecpm),
            },
            'quality_flags': {
                'is_high_quality': self.is_high_quality,
                'is_recommended': self.is_recommended,
                'needs_review': self.needs_review,
                'has_quality_issues': self.has_quality_issues,
            },
            'trend': {
                'score_trend': self.score_trend,
                'trend_percentage': float(self.trend_percentage),
            }
        }
    
    def get_benchmark_comparison(self) -> Dict[str, any]:
        """Get comparison with industry benchmarks."""
        # Industry benchmarks (example values)
        benchmarks = {
            'click_through_rate': 2.5,
            'conversion_rate': 3.0,
            'epc': 0.05,
            'ecpm': 1.25,
            'uptime_percentage': 99.5,
            'error_rate': 2.0,
        }
        
        comparison = {}
        
        for metric, benchmark_value in benchmarks.items():
            current_value = getattr(self, metric, 0)
            comparison[metric] = {
                'current': float(current_value),
                'benchmark': benchmark_value,
                'performance': 'above' if current_value > benchmark_value else 'below',
                'percentage_diff': ((current_value - benchmark_value) / benchmark_value) * 100 if benchmark_value > 0 else 0
            }
        
        return comparison
    
    def get_improvement_suggestions(self) -> List[str]:
        """Get suggestions for improving quality score."""
        suggestions = []
        
        # Performance suggestions
        if self.performance_score < 70:
            suggestions.append("Improve offer performance by optimizing load times and response speeds")
        
        # Engagement suggestions
        if self.engagement_score < 70:
            suggestions.append("Increase user engagement through better targeting and creative optimization")
        
        # Revenue suggestions
        if self.revenue_score < 70:
            suggestions.append("Optimize revenue by focusing on higher-converting offers and better pricing")
        
        # Fraud suggestions
        if self.fraud_score > 30:
            suggestions.append("Reduce fraud risk by implementing better detection and filtering")
        
        # Reliability suggestions
        if self.reliability_score < 70:
            suggestions.append("Improve network reliability by increasing uptime and reducing errors")
        
        # User feedback suggestions
        if self.user_feedback_score < 70:
            suggestions.append("Enhance user experience based on feedback and behavior analysis")
        
        return suggestions
    
    def calculate_score_trend(self, previous_scores: List['OfferQualityScore']) -> str:
        """Calculate trend based on previous scores."""
        if not previous_scores:
            return 'stable'
        
        # Get recent scores
        recent_scores = [score.overall_score for score in previous_scores[:5]]  # Last 5 scores
        
        if len(recent_scores) < 2:
            return 'stable'
        
        # Calculate trend
        first_score = recent_scores[0]
        last_score = recent_scores[-1]
        
        if last_score > first_score * 1.05:  # 5% improvement
            return 'improving'
        elif last_score < first_score * 0.95:  # 5% decline
            return 'declining'
        else:
            # Check volatility
            variance = sum((score - sum(recent_scores) / len(recent_scores)) ** 2 for score in recent_scores) / len(recent_scores)
            if variance > 25:  # High variance
                return 'volatile'
            else:
                return 'stable'
    
    @classmethod
    def get_top_quality_offers(cls, tenant_id: int, limit: int = 10) -> models.QuerySet:
        """Get top quality offers for tenant."""
        return cls.objects.filter(
            tenant_id=tenant_id,
            is_high_quality=True
        ).order_by('-overall_score')[:limit]
    
    @classmethod
    def get_offers_needing_review(cls, tenant_id: int) -> models.QuerySet:
        """Get offers needing quality review."""
        return cls.objects.filter(
            tenant_id=tenant_id,
            needs_review=True
        ).order_by('overall_score')
    
    @classmethod
    def get_quality_distribution(cls, tenant_id: int) -> Dict[str, int]:
        """Get distribution of quality grades."""
        distribution = {}
        
        for grade, _ in cls._meta.get_field('quality_grade').choices:
            count = cls.objects.filter(
                tenant_id=tenant_id,
                quality_grade=grade
            ).count()
            
            if count > 0:
                distribution[grade] = count
        
        return distribution
    
    @classmethod
    def update_quality_scores(cls, offer_id: int, data_period_days: int = 30):
        """Update quality scores for offer."""
        try:
            from ..models import OfferRoute, RoutePerformanceStat, UserOfferHistory
            
            offer = OfferRoute.objects.get(id=offer_id)
            
            # Get performance data
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=data_period_days)
            
            performance_stats = RoutePerformanceStat.objects.filter(
                offer_id=offer_id,
                date__gte=start_date,
                date__lte=end_date
            )
            
            # Calculate metrics
            total_impressions = performance_stats.aggregate(
                total=models.Sum('impressions')
            )['total'] or 0
            
            total_clicks = performance_stats.aggregate(
                total=models.Sum('clicks')
            )['total'] or 0
            
            total_conversions = performance_stats.aggregate(
                total=models.Sum('conversions')
            )['total'] or 0
            
            total_revenue = performance_stats.aggregate(
                total=models.Sum('revenue')
            )['total'] or 0
            
            # Create or update quality score
            quality_score, created = cls.objects.update_or_create(
                offer=offer,
                data_period_start=start_date,
                data_period_end=end_date,
                defaults={
                    'network': offer.network,
                    'tenant': offer.tenant,
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_revenue': total_revenue,
                }
            )
            
            if not created:
                quality_score.total_impressions = total_impressions
                quality_score.total_clicks = total_clicks
                quality_score.total_conversions = total_conversions
                quality_score.total_revenue = total_revenue
                quality_score.save()
            
            logger.info(f"Updated quality score for offer {offer_id}")
            
        except Exception as e:
            logger.error(f"Error updating quality score for offer {offer_id}: {e}")


# Signal handlers for quality score updates
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=OfferQualityScore)
def quality_score_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for quality scores."""
    if created:
        logger.info(f"New quality score created: {instance.offer.name} - {instance.overall_score}")
        
        # Trigger quality analysis tasks
        from ..tasks.quality import analyze_quality_score
        analyze_quality_score.delay(instance.id)

@receiver(post_delete, sender=OfferQualityScore)
def quality_score_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for quality scores."""
    logger.info(f"Quality score deleted: {instance.offer.name} - {instance.overall_score}")
