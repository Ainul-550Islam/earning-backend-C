"""
Analytics Models for Offer Routing System

This module contains models for tracking routing decisions,
insights, performance metrics, and offer exposure statistics.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import (
    RoutingDecisionReason, EventType, LogLevel,
    AggregationType, ComparisonOperator, SortOrder
)
from ..constants import (
    DECISION_LOG_RETENTION_DAYS, INSIGHT_AGGREGATION_HOURS,
    PERFORMANCE_STATS_RETENTION_DAYS, MAX_DECISION_LOGS_PER_BATCH
)

User = get_user_model()


class RoutingDecisionLog(models.Model):
    """
    Log of routing decisions made by the system.
    
    Tracks every routing decision for analytics, debugging,
    and compliance purposes.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='routing_decisions',
        verbose_name=_('User')
    )
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='routing_decisions_offer',
        verbose_name=_('Route')
    )
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='routing_decisions_user',
        verbose_name=_('Offer')
    )
    
    # Decision details
    reason = models.CharField(
        _('Decision Reason'),
        max_length=50,
        choices=RoutingDecisionReason.CHOICES,
        help_text=_('Why this routing decision was made')
    )
    score = models.DecimalField(_('Score'), max_digits=8, decimal_places=4, default=0.0)
    rank = models.IntegerField(_('Rank'), default=0)
    
    # Performance metrics
    response_time_ms = models.IntegerField(_('Response Time (ms)'), default=0)
    cache_hit = models.BooleanField(_('Cache Hit'), default=False)
    
    # Context data
    context_data = models.JSONField(_('Context Data'), default=dict, blank=True)
    personalization_applied = models.BooleanField(_('Personalization Applied'), default=False)
    caps_checked = models.BooleanField(_('Caps Checked'), default=False)
    fallback_used = models.BooleanField(_('Fallback Used'), default=False)
    
    # A/B test data
    ab_test_id = models.IntegerField(_('A/B Test ID'), null=True, blank=True)
    ab_test_variant = models.CharField(
        _('A/B Test Variant'),
        max_length=20,
        blank=True,
        help_text=_('Which variant the user was assigned to')
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    class Meta:
        db_table = 'offer_routing_decision_logs'
        verbose_name = _('Routing Decision Log')
        verbose_name_plural = _('Routing Decision Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at'], name='idx_user_created_at_1201'),
            models.Index(fields=['route', 'created_at'], name='idx_route_created_at_1202'),
            models.Index(fields=['offer', 'created_at'], name='idx_offer_created_at_1203'),
            models.Index(fields=['reason'], name='idx_reason_1204'),
            models.Index(fields=['cache_hit'], name='idx_cache_hit_1205'),
            models.Index(fields=['created_at'], name='idx_created_at_1206'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.offer.name} ({self.reason})"
    
    def clean(self):
        """Validate model data."""
        if self.response_time_ms < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Response time cannot be negative'))
        
        if self.rank < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Rank cannot be negative'))
    
    def get_decision_summary(self):
        """Get summary of this routing decision."""
        return {
            'user_id': self.user_id,
            'route_id': self.route_id,
            'offer_id': self.offer_id,
            'reason': self.reason,
            'score': float(self.score),
            'rank': self.rank,
            'response_time_ms': self.response_time_ms,
            'cache_hit': self.cache_hit,
            'personalization_applied': self.personalization_applied,
            'caps_checked': self.caps_checked,
            'fallback_used': self.fallback_used,
            'created_at': self.created_at.isoformat()
        }


class RoutingInsight(models.Model):
    """
    Insights and recommendations from routing analytics.
    
    Stores automated insights about routing performance,
    user behavior patterns, and optimization opportunities.
    """
    
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='routing_insights',
        verbose_name=_('tenants.Tenant')
    )
    
    # Insight details
    title = models.CharField(_('Title'), max_length=200)
    description = models.TextField(_('Description'))
    insight_type = models.CharField(
        _('Insight Type'),
        max_length=50,
        choices=[
            ('performance', _('Performance')),
            ('optimization', _('Optimization')),
            ('anomaly', _('Anomaly')),
            ('trend', _('Trend')),
            ('recommendation', _('Recommendation'))
        ]
    )
    severity = models.CharField(
        _('Severity'),
        max_length=20,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('critical', _('Critical'))
        ],
        default='medium'
    )
    
    # Data and metrics
    data = models.JSONField(_('Data'), default=dict, blank=True)
    metrics = models.JSONField(_('Metrics'), default=dict, blank=True)
    confidence = models.DecimalField(_('Confidence'), max_digits=5, decimal_places=2, default=0.0)
    
    # Actionability
    is_actionable = models.BooleanField(_('Is Actionable'), default=True)
    action_suggestion = models.TextField(_('Action Suggestion'), blank=True)
    action_taken = models.BooleanField(_('Action Taken'), default=False)
    
    # Timing
    period_start = models.DateTimeField(_('Period Start'))
    period_end = models.DateTimeField(_('Period End'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_insights'
        verbose_name = _('Routing Insight')
        verbose_name_plural = _('Routing Insights')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant'], name='idx_tenant_1207'),
            models.Index(fields=['insight_type'], name='idx_insight_type_1208'),
            models.Index(fields=['severity'], name='idx_severity_1209'),
            models.Index(fields=['is_actionable'], name='idx_is_actionable_1210'),
            models.Index(fields=['created_at'], name='idx_created_at_1211'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.insight_type})"
    
    def clean(self):
        """Validate model data."""
        if self.confidence < 0 or self.confidence > 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Confidence must be between 0 and 1'))
        
        if self.period_start and self.period_end and self.period_start > self.period_end:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Period start must be before period end'))
    
    def get_insight_summary(self):
        """Get summary of this insight."""
        return {
            'id': self.id,
            'title': self.title,
            'insight_type': self.insight_type,
            'severity': self.severity,
            'confidence': float(self.confidence),
            'is_actionable': self.is_actionable,
            'action_taken': self.action_taken,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'created_at': self.created_at.isoformat()
        }


class RoutePerformanceStat(models.Model):
    """
    Performance statistics for routes.
    
    Tracks key metrics like impressions, clicks, conversions,
    revenue, and performance indicators for each route.
    """
    
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='performance_stats',
        verbose_name=_('Route')
    )
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='performance_stats',
        verbose_name=_('tenants.Tenant')
    )
    
    # Date aggregation
    date = models.DateField(_('Date'))
    aggregation_type = models.CharField(
        _('Aggregation Type'),
        max_length=20,
        choices=AggregationType.CHOICES,
        default=AggregationType.DAILY
    )
    
    # Performance metrics
    impressions = models.BigIntegerField(_('Impressions'), default=0)
    unique_users = models.IntegerField(_('Unique Users'), default=0)
    clicks = models.BigIntegerField(_('Clicks'), default=0)
    conversions = models.BigIntegerField(_('Conversions'), default=0)
    revenue = models.DecimalField(_('Revenue'), max_digits=12, decimal_places=2, default=0.0)
    
    # Calculated metrics
    click_through_rate = models.DecimalField(_('Click Through Rate'), max_digits=5, decimal_places=2, default=0.0)
    conversion_rate = models.DecimalField(_('Conversion Rate'), max_digits=5, decimal_places=2, default=0.0)
    revenue_per_impression = models.DecimalField(_('Revenue Per Impression'), max_digits=8, decimal_places=4, default=0.0)
    revenue_per_user = models.DecimalField(_('Revenue Per User'), max_digits=10, decimal_places=2, default=0.0)
    
    # Performance indicators
    avg_response_time_ms = models.DecimalField(_('Avg Response Time (ms)'), max_digits=8, decimal_places=2, default=0.0)
    cache_hit_rate = models.DecimalField(_('Cache Hit Rate'), max_digits=5, decimal_places=2, default=0.0)
    error_rate = models.DecimalField(_('Error Rate'), max_digits=5, decimal_places=2, default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_performance_stats'
        verbose_name = _('Route Performance Stat')
        verbose_name_plural = _('Route Performance Stats')
        ordering = ['-date', 'route']
        indexes = [
            models.Index(fields=['route', 'date'], name='idx_route_date_1212'),
            models.Index(fields=['tenant', 'date'], name='idx_tenant_date_1213'),
            models.Index(fields=['date'], name='idx_date_1214'),
            models.Index(fields=['aggregation_type'], name='idx_aggregation_type_1215'),
            models.Index(fields=['created_at'], name='idx_created_at_1216'),
        ]
    
    def __str__(self):
        return f"{self.route.name} - {self.date} ({self.aggregation_type})"
    
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
        
        if self.click_through_rate < 0 or self.click_through_rate > 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Click through rate must be between 0 and 100'))
        
        if self.conversion_rate < 0 or self.conversion_rate > 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Conversion rate must be between 0 and 100'))
    
    def calculate_metrics(self):
        """Calculate derived metrics from raw data."""
        if self.impressions > 0:
            self.click_through_rate = (self.clicks / self.impressions) * 100
            self.conversion_rate = (self.conversions / self.impressions) * 100
            self.revenue_per_impression = self.revenue / self.impressions
        
        if self.unique_users > 0:
            self.revenue_per_user = self.revenue / self.unique_users
    
    def get_performance_summary(self):
        """Get performance summary for this stat."""
        return {
            'route_id': self.route_id,
            'date': self.date.isoformat(),
            'aggregation_type': self.aggregation_type,
            'impressions': self.impressions,
            'unique_users': self.unique_users,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'revenue': float(self.revenue),
            'click_through_rate': float(self.click_through_rate),
            'conversion_rate': float(self.conversion_rate),
            'revenue_per_impression': float(self.revenue_per_impression),
            'revenue_per_user': float(self.revenue_per_user),
            'avg_response_time_ms': float(self.avg_response_time_ms),
            'cache_hit_rate': float(self.cache_hit_rate),
            'error_rate': float(self.error_rate)
        }


class OfferExposureStat(models.Model):
    """
    Statistics about offer exposure to users.
    
    Tracks how many unique users have seen each offer,
    frequency of exposure, and exposure patterns.
    """
    
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='exposure_stats',
        verbose_name=_('Offer')
    )
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='exposure_stats',
        verbose_name=_('tenants.Tenant')
    )
    
    # Date aggregation
    date = models.DateField(_('Date'))
    aggregation_type = models.CharField(
        _('Aggregation Type'),
        max_length=20,
        choices=AggregationType.CHOICES,
        default=AggregationType.DAILY
    )
    
    # Exposure metrics
    unique_users_exposed = models.IntegerField(_('Unique Users Exposed'), default=0)
    total_exposures = models.BigIntegerField(_('Total Exposures'), default=0)
    repeat_exposures = models.BigIntegerField(_('Repeat Exposures'), default=0)
    
    # Frequency metrics
    avg_exposures_per_user = models.DecimalField(_('Avg Exposures Per User'), max_digits=5, decimal_places=2, default=0.0)
    max_exposures_per_user = models.IntegerField(_('Max Exposures Per User'), default=0)
    
    # Geographic distribution
    geographic_distribution = models.JSONField(_('Geographic Distribution'), default=dict, blank=True)
    
    # Device distribution
    device_distribution = models.JSONField(_('Device Distribution'), default=dict, blank=True)
    
    # Time distribution
    hourly_distribution = models.JSONField(_('Hourly Distribution'), default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_exposure_stats'
        verbose_name = _('Offer Exposure Stat')
        verbose_name_plural = _('Offer Exposure Stats')
        ordering = ['-date', 'offer']
        indexes = [
            models.Index(fields=['offer', 'date'], name='idx_offer_date_1217'),
            models.Index(fields=['tenant', 'date'], name='idx_tenant_date_1218'),
            models.Index(fields=['date'], name='idx_date_1219'),
            models.Index(fields=['aggregation_type'], name='idx_aggregation_type_1220'),
            models.Index(fields=['created_at'], name='idx_created_at_1221'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} - {self.date} ({self.aggregation_type})"
    
    def clean(self):
        """Validate model data."""
        if self.unique_users_exposed < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Unique users exposed cannot be negative'))
        
        if self.total_exposures < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Total exposures cannot be negative'))
        
        if self.repeat_exposures < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Repeat exposures cannot be negative'))
        
        if self.max_exposures_per_user < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Max exposures per user cannot be negative'))
    
    def calculate_frequency_metrics(self):
        """Calculate frequency metrics from exposure data."""
        if self.unique_users_exposed > 0:
            self.avg_exposures_per_user = self.total_exposures / self.unique_users_exposed
    
    def get_exposure_summary(self):
        """Get exposure summary for this stat."""
        return {
            'offer_id': self.offer_id,
            'date': self.date.isoformat(),
            'aggregation_type': self.aggregation_type,
            'unique_users_exposed': self.unique_users_exposed,
            'total_exposures': self.total_exposures,
            'repeat_exposures': self.repeat_exposures,
            'avg_exposures_per_user': float(self.avg_exposures_per_user),
            'max_exposures_per_user': self.max_exposures_per_user,
            'geographic_distribution': self.geographic_distribution,
            'device_distribution': self.device_distribution,
            'hourly_distribution': self.hourly_distribution
        }


# Custom managers for analytics models
class RoutingDecisionLogManager(models.Manager):
    """Custom manager for RoutingDecisionLog."""
    
    def get_decisions_by_user(self, user_id, limit=100):
        """Get routing decisions for a specific user."""
        return self.filter(user_id=user_id).order_by('-created_at')[:limit]
    
    def get_decisions_by_route(self, route_id, limit=100):
        """Get routing decisions for a specific route."""
        return self.filter(route_id=route_id).order_by('-created_at')[:limit]
    
    def get_decisions_by_reason(self, reason, limit=100):
        """Get routing decisions by reason."""
        return self.filter(reason=reason).order_by('-created_at')[:limit]
    
    def get_cache_hit_stats(self, date_from=None, date_to=None):
        """Get cache hit statistics."""
        queryset = self.all()
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.aggregate(
            total_decisions=models.Count('id'),
            cache_hits=models.Count('id', filter=models.Q(cache_hit=True)),
            cache_misses=models.Count('id', filter=models.Q(cache_hit=False)),
            cache_hit_rate=models.Avg('cache_hit')
        )
    
    def get_performance_stats(self, date_from=None, date_to=None):
        """Get performance statistics."""
        queryset = self.all()
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.aggregate(
            total_decisions=models.Count('id'),
            avg_response_time=models.Avg('response_time_ms'),
            min_response_time=models.Min('response_time_ms'),
            max_response_time=models.Max('response_time_ms'),
            median_response_time=models.Avg('response_time_ms'),  # Would use actual median calculation
            personalization_rate=models.Avg('personalization_applied'),
            caps_check_rate=models.Avg('caps_checked'),
            fallback_rate=models.Avg('fallback_used')
        )
    
    def cleanup_old_logs(self, retention_days=DECISION_LOG_RETENTION_DAYS):
        """Clean up old routing decision logs."""
        cutoff_date = timezone.now() - timezone.timedelta(days=retention_days)
        deleted_count = self.filter(created_at__lt=cutoff_date).delete()[0]
        return deleted_count


class RoutingInsightManager(models.Manager):
    """Custom manager for RoutingInsight."""
    
    def get_insights_by_tenant(self, tenant_id):
        """Get insights for a specific tenant."""
        return self.filter(tenant_id=tenant_id).order_by('-created_at')
    
    def get_insights_by_type(self, insight_type):
        """Get insights by type."""
        return self.filter(insight_type=insight_type).order_by('-created_at')
    
    def get_actionable_insights(self, tenant_id=None):
        """Get actionable insights."""
        queryset = self.filter(is_actionable=True, action_taken=False)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by('-created_at')
    
    def get_insights_by_severity(self, severity):
        """Get insights by severity."""
        return self.filter(severity=severity).order_by('-created_at')
    
    def generate_insights(self, tenant_id, period_start, period_end):
        """Generate insights for a tenant for a specific period."""
        # This would implement insight generation logic
        # For now, return placeholder
        return []
    
    def mark_insight_action_taken(self, insight_id):
        """Mark an insight as action taken."""
        insight = self.get(id=insight_id)
        insight.action_taken = True
        insight.save()
        return insight


class RoutePerformanceStatManager(models.Manager):
    """Custom manager for RoutePerformanceStat."""
    
    def get_stats_by_route(self, route_id, limit=30):
        """Get performance stats for a specific route."""
        return self.filter(route_id=route_id).order_by('-date')[:limit]
    
    def get_stats_by_tenant(self, tenant_id, limit=100):
        """Get performance stats for a specific tenant."""
        return self.filter(tenant_id=tenant_id).order_by('-date')[:limit]
    
    def get_stats_by_date_range(self, date_from, date_to):
        """Get performance stats for a date range."""
        return self.filter(date__gte=date_from, date__lte=date_to).order_by('-date')
    
    def get_top_performing_routes(self, limit=10, metric='revenue'):
        """Get top performing routes by metric."""
        return self.all().order_by(f'-{metric}')[:limit]
    
    def get_underperforming_routes(self, limit=10, metric='revenue', threshold=0.01):
        """Get underperforming routes below threshold."""
        return self.filter(**{f'{metric}__lt': threshold}).order_by(metric)[:limit]
    
    def aggregate_stats(self, route_id, aggregation_type=AggregationType.WEEKLY):
        """Aggregate stats for a route."""
        # This would implement aggregation logic
        # For now, return placeholder
        return []
    
    def calculate_trend(self, route_id, days=30):
        """Calculate performance trend for a route."""
        # This would implement trend calculation
        # For now, return placeholder
        return {}


class OfferExposureStatManager(models.Manager):
    """Custom manager for OfferExposureStat."""
    
    def get_stats_by_offer(self, offer_id, limit=30):
        """Get exposure stats for a specific offer."""
        return self.filter(offer_id=offer_id).order_by('-date')[:limit]
    
    def get_stats_by_tenant(self, tenant_id, limit=100):
        """Get exposure stats for a specific tenant."""
        return self.filter(tenant_id=tenant_id).order_by('-date')[:limit]
    
    def get_most_exposed_offers(self, limit=10):
        """Get most exposed offers."""
        return self.all().order_by('-unique_users_exposed')[:limit]
    
    def get_least_exposed_offers(self, limit=10):
        """Get least exposed offers."""
        return self.all().order_by('unique_users_exposed')[:limit]
    
    def get_exposure_patterns(self, offer_id, days=30):
        """Get exposure patterns for an offer."""
        # This would implement pattern analysis
        # For now, return placeholder
        return {}
    
    def calculate_geographic_distribution(self, offer_id):
        """Calculate geographic distribution for an offer."""
        # This would implement geographic distribution calculation
        # For now, return placeholder
        return {}
    
    def calculate_device_distribution(self, offer_id):
        """Calculate device distribution for an offer."""
        # This would implement device distribution calculation
        # For now, return placeholder
        return {}


# Add custom managers to models
RoutingDecisionLog.add_manager_class = RoutingDecisionLogManager
RoutingInsight.add_manager_class = RoutingInsightManager
RoutePerformanceStat.add_manager_class = RoutePerformanceStatManager
OfferExposureStat.add_manager_class = OfferExposureStatManager
