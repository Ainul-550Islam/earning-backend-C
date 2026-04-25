"""
Scoring Models for Offer Routing System

This module contains models for offer scoring, configuration,
and ranking calculations.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import PersonalizationAlgorithm, RoutingDecisionReason
from ..constants import DEFAULT_EPC_WEIGHT, DEFAULT_CR_WEIGHT, DEFAULT_RELEVANCE_WEIGHT, DEFAULT_FRESHNESS_WEIGHT

User = get_user_model()


class OfferScore(models.Model):
    """
    Individual offer scores for specific users.
    
    Tracks how likely a user is to engage with each offer based on
    various factors like EPC, conversion rate, relevance, and freshness.
    """
    
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='scores',
        verbose_name=_('Offer')
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='scores',
        verbose_name=_('User')
    )
    score = models.DecimalField(_('Score'), max_digits=5, decimal_places=2)
    epc = models.DecimalField(_('EPC'), max_digits=8, decimal_places=4)
    cr = models.DecimalField(_('Conversion Rate'), max_digits=5, decimal_places=2)
    relevance = models.DecimalField(_('Relevance'), max_digits=5, decimal_places=2)
    freshness = models.DecimalField(_('Freshness'), max_digits=5, decimal_places=2)
    personalization_score = models.DecimalField(_('Personalization Score'), max_digits=5, decimal_places=2)
    
    # Score components
    epc_component = models.DecimalField(_('EPC Component'), max_digits=8, decimal_places=4, default=DEFAULT_EPC_WEIGHT)
    cr_component = models.DecimalField(_('CR Component'), max_digits=5, decimal_places=2, default=DEFAULT_CR_WEIGHT)
    relevance_component = models.DecimalField(_('Relevance Component'), max_digits=5, decimal_places=2, default=DEFAULT_RELEVANCE_WEIGHT)
    freshness_component = models.DecimalField(_('Freshness Component'), max_digits=5, decimal_places=2, default=DEFAULT_FRESHNESS_WEIGHT)
    
    # Metadata
    scored_at = models.DateTimeField(_('Scored At'), auto_now_add=True)
    expires_at = models.DateTimeField(_('Expires At'), null=True, blank=True)
    score_version = models.IntegerField(_('Score Version'), default=1)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_offer_scores'
        verbose_name = _('Offer Score')
        verbose_name_plural = _('Offer Scores')
        ordering = ['-scored_at', '-score']
        indexes = [
            models.Index(fields=['offer', 'user'], name='idx_offer_user_1309'),
            models.Index(fields=['user', 'score'], name='idx_user_score_1310'),
            models.Index(fields=['scored_at'], name='idx_scored_at_1311'),
            models.Index(fields=['expires_at'], name='idx_expires_at_1312'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} - {self.user.username} ({self.score})"
    
    def is_expired(self):
        """Check if score has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def calculate_total_score(self):
        """Calculate total score from components."""
        return (
            (self.epc_component * self.epc) +
            (self.cr_component * self.cr) +
            (self.relevance_component * self.relevance) +
            (self.freshness_component * self.freshness)
        ) / 100.0
    
    def clean(self):
        """Validate model data."""
        if self.score < 0 or self.score > 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Score must be between 0 and 100'))
        
        if self.epc < 0 or self.cr < 0 or self.relevance < 0 or self.freshness < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Score components must be positive'))
        
        if self.epc_component + self.cr_component + self.relevance_component + self.freshness_component != 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Score components must sum to 100'))


class OfferScoreConfig(models.Model):
    """
    Configuration for offer scoring algorithms.
    
    Defines weights and parameters for calculating offer scores
    based on EPC, conversion rate, relevance, and freshness.
    """
    
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='score_configs',
        verbose_name=_('tenants.Tenant')
    )
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='score_configs',
        verbose_name=_('Offer')
    )
    algorithm = models.CharField(
        _('Algorithm'),
        max_length=50,
        choices=[
            ('weighted', _('Weighted Score')),
            ('machine_learning', _('Machine Learning')),
            ('hybrid', _('Hybrid')),
        ],
        default='weighted'
    )
    
    # Scoring weights
    epc_weight = models.DecimalField(_('EPC Weight'), max_digits=5, decimal_places=2, default=DEFAULT_EPC_WEIGHT)
    cr_weight = models.DecimalField(_('CR Weight'), max_digits=5, decimal_places=2, default=DEFAULT_CR_WEIGHT)
    relevance_weight = models.DecimalField(_('Relevance Weight'), max_digits=5, decimal_places=2, default=DEFAULT_RELEVANCE_WEIGHT)
    freshness_weight = models.DecimalField(_('Freshness Weight'), max_digits=5, decimal_places=2, default=DEFAULT_FRESHNESS_WEIGHT)
    freshness_decay_days = models.IntegerField(_('Freshness Decay Days'), default=30)
    
    # Scoring parameters
    min_epc = models.DecimalField(_('Min EPC'), max_digits=8, decimal_places=4, default=0.0)
    max_epc = models.DecimalField(_('Max EPC'), max_digits=8, decimal_places=4, default=10.0)
    min_cr = models.DecimalField(_('Min CR'), max_digits=5, decimal_places=2, default=0.0)
    max_cr = models.DecimalField(_('Max CR'), max_digits=5, decimal_places=2, default=1.0)
    min_relevance = models.DecimalField(_('Min Relevance'), max_digits=5, decimal_places=2, default=0.0)
    max_relevance = models.DecimalField(_('Max Relevance'), max_digits=5, decimal_places=2, default=1.0)
    
    # Personalization settings
    personalization_enabled = models.BooleanField(_('Personalization Enabled'), default=True)
    personalization_weight = models.DecimalField(_('Personalization Weight'), max_digits=5, decimal_places=2, default=0.2)
    
    # Advanced settings
    use_historical_data = models.BooleanField(_('Use Historical Data'), default=True)
    historical_weight_days = models.IntegerField(_('Historical Weight Days'), default=90)
    boost_new_offers = models.BooleanField(_('Boost New Offers'), default=True)
    new_offer_boost_days = models.IntegerField(_('New Offer Boost Days'), default=7)
    new_offer_boost_factor = models.DecimalField(_('New Offer Boost Factor'), max_digits=5, decimal_places=2, default=1.5)
    
    is_active = models.BooleanField(_('Is Active'), default=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_score_configs'
        verbose_name = _('Offer Score Config')
        verbose_name_plural = _('Offer Score Configs')
        ordering = ['tenant', 'offer']
        indexes = [
            models.Index(fields=['tenant', 'offer'], name='idx_tenant_offer_1313'),
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1314'),
            models.Index(fields=['created_at'], name='idx_created_at_1315'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} - {self.tenant.username}"
    
    def clean(self):
        """Validate model data."""
        total_weight = (
            self.epc_weight + self.cr_weight + 
            self.relevance_weight + self.freshness_weight + 
            self.personalization_weight
        )
        
        if abs(total_weight - 1.0) > 0.1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Weights must sum to 1.0 (current: {})').format(total_weight))
        
        if self.freshness_decay_days < 1 or self.freshness_decay_days > 365:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Freshness decay days must be between 1 and 365'))
        
        if self.new_offer_boost_days < 1 or self.new_offer_boost_days > 30:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('New offer boost days must be between 1 and 30'))


class GlobalOfferRank(models.Model):
    """
    Global ranking of offers across all users.
    
    Maintains overall offer performance metrics and rankings
    for global optimization and analytics.
    """
    
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='global_ranks',
        verbose_name=_('Offer')
    )
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='global_ranks',
        verbose_name=_('tenants.Tenant')
    )
    
    # Ranking metrics
    global_rank = models.IntegerField(_('Global Rank'))
    rank_score = models.DecimalField(_('Rank Score'), max_digits=5, decimal_places=2)
    rank_percentile = models.DecimalField(_('Rank Percentile'), max_digits=5, decimal_places=2)
    
    # Performance metrics
    total_impressions = models.BigIntegerField(_('Total Impressions'), default=0)
    total_clicks = models.BigIntegerField(_('Total Clicks'), default=0)
    total_conversions = models.BigIntegerField(_('Total Conversions'), default=0)
    total_revenue = models.DecimalField(_('Total Revenue'), max_digits=12, decimal_places=2, default=0.0)
    
    # Calculated metrics
    click_through_rate = models.DecimalField(_('Click Through Rate'), max_digits=5, decimal_places=2, default=0.0)
    conversion_rate = models.DecimalField(_('Conversion Rate'), max_digits=5, decimal_places=2, default=0.0)
    average_order_value = models.DecimalField(_('Average Order Value'), max_digits=10, decimal_places=2, default=0.0)
    epc = models.DecimalField(_('EPC'), max_digits=8, decimal_places=4, default=0.0)
    
    # Ranking date
    rank_date = models.DateField(_('Rank Date'))
    rank_period_start = models.DateField(_('Rank Period Start'))
    rank_period_end = models.DateField(_('Rank Period End'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_global_ranks'
        verbose_name = _('Global Offer Rank')
        verbose_name_plural = _('Global Offer Ranks')
        ordering = ['global_rank', 'rank_score']
        indexes = [
            models.Index(fields=['offer'], name='idx_offer_1316'),
            models.Index(fields=['tenant'], name='idx_tenant_1317'),
            models.Index(fields=['global_rank'], name='idx_global_rank_1318'),
            models.Index(fields=['rank_date'], name='idx_rank_date_1319'),
            models.Index(fields=['created_at'], name='idx_created_at_1320'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} - Rank {self.global_rank} ({self.tenant.username})"
    
    def clean(self):
        """Validate model data."""
        if self.global_rank < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Global rank must be at least 1'))
        
        if self.rank_score < 0 or self.rank_score > 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Rank score must be between 0 and 100'))
        
        if self.rank_percentile < 0 or self.rank_percentile > 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Rank percentile must be between 0 and 100'))
        
        if self.rank_period_start and self.rank_period_end and self.rank_period_start > self.rank_period_end:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Rank period start must be before or equal to end'))


class UserOfferHistory(models.Model):
    """
    Historical record of offers shown to users.
    
    Tracks user interactions with offers for analytics,
    personalization, and compliance.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='offer_history',
        verbose_name=_('User')
    )
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='offer_history_as_offer',
        verbose_name=_('Offer')
    )
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='offer_history_as_route',
        verbose_name=_('Route')
    )
    
    # Interaction timestamps
    viewed_at = models.DateTimeField(_('Viewed At'), null=True, blank=True)
    clicked_at = models.DateTimeField(_('Clicked At'), null=True, blank=True)
    completed_at = models.DateTimeField(_('Completed At'), null=True, blank=True)
    
    # Interaction details
    view_count = models.IntegerField(_('View Count'), default=0)
    click_count = models.IntegerField(_('Click Count'), default=0)
    conversion_value = models.DecimalField(_('Conversion Value'), max_digits=10, decimal_places=2, default=0.0)
    
    # Context
    context_data = models.JSONField(_('Context Data'), default=dict, blank=True)
    personalization_applied = models.BooleanField(_('Personalization Applied'), default=False)
    score_at_time = models.DecimalField(_('Score at Time'), max_digits=8, decimal_places=4, default=0.0)
    
    # Decision reason
    decision_reason = models.CharField(
        _('Decision Reason'),
        max_length=50,
        choices=RoutingDecisionReason.CHOICES,
        blank=True
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_user_offer_history'
        verbose_name = _('User Offer History')
        verbose_name_plural = _('User Offer Histories')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'offer'], name='idx_user_offer_1321'),
            models.Index(fields=['user', 'viewed_at'], name='idx_user_viewed_at_1322'),
            models.Index(fields=['user', 'clicked_at'], name='idx_user_clicked_at_1323'),
            models.Index(fields=['user', 'completed_at'], name='idx_user_completed_at_1324'),
            models.Index(fields=['decision_reason'], name='idx_decision_reason_1325'),
            models.Index(fields=['created_at'], name='idx_created_at_1326'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} - {self.user.username}"


class OfferAffinityScore(models.Model):
    """
    User affinity scores for offer categories.
    
    Tracks user preferences and historical behavior to calculate
    affinity scores for different offer categories (electronics, fashion, travel, etc.).
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='affinity_scores',
        verbose_name=_('User')
    )
    category = models.CharField(_('Category'), max_length=50)
    score = models.DecimalField(_('Affinity Score'), max_digits=5, decimal_places=2)
    confidence = models.DecimalField(_('Confidence'), max_digits=5, decimal_places=2)
    
    # Score components
    implicit_score = models.DecimalField(_('Implicit Score'), max_digits=5, decimal_places=2, default=0.0)
    explicit_score = models.DecimalField(_('Explicit Score'), max_digits=5, decimal_places=2, default=0.0)
    collaborative_score = models.DecimalField(_('Collaborative Score'), max_digits=5, decimal_places=2, default=0.0)
    content_based_score = models.DecimalField(_('Content-Based Score'), max_digits=5, decimal_places=2, default=0.0)
    
    # Metadata
    last_updated = models.DateTimeField(_('Last Updated'), auto_now=True)
    sample_size = models.IntegerField(_('Sample Size'), default=0)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_affinity_scores'
        verbose_name = _('Offer Affinity Score')
        verbose_name_plural = _('Offer Affinity Scores')
        ordering = ['-last_updated']
        indexes = [
            models.Index(fields=['user', 'category'], name='idx_user_category_1327'),
            models.Index(fields=['user', 'score'], name='idx_user_score_1328'),
            models.Index(fields=['category', 'score'], name='idx_category_score_1329'),
            models.Index(fields=['last_updated'], name='idx_last_updated_1330'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.category} ({self.score})"
    
    def clean(self):
        """Validate model data."""
        if self.score < 0 or self.score > 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Affinity score must be between 0 and 100'))
        
        if self.confidence < 0 or self.confidence > 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Confidence must be between 0 and 1'))
        
        if self.sample_size < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Sample size must be positive'))


# Custom managers for scoring models
class OfferScoreManager(models.Manager):
    """Custom manager for OfferScore with utility methods."""
    
    def get_user_scores(self, user_id, offer_ids=None):
        """Get scores for a user across multiple offers."""
        queryset = self.filter(user_id=user_id)
        if offer_ids:
            queryset = queryset.filter(offer_id__in=offer_ids)
        return queryset.order_by('-scored_at')
    
    def get_top_scoring_offers(self, user_id, limit=10):
        """Get top scoring offers for a user."""
        return self.filter(
            user_id=user_id
        ).order_by('-score')[:limit]
    
    def get_expired_scores(self):
        """Get all expired scores."""
        return self.filter(
            expires_at__lt=timezone.now()
        )
    
    def delete_expired_scores(self):
        """Delete all expired scores."""
        return self.filter(
            expires_at__lt=timezone.now()
        ).delete()


class GlobalOfferRankManager(models.Manager):
    """Custom manager for GlobalOfferRank with utility methods."""
    
    def get_top_offers(self, limit=100):
        """Get top ranking offers globally."""
        return self.order_by('global_rank')[:limit]
    
    def get_offers_by_tenant(self, tenant_id):
        """Get rankings for a specific tenant."""
        return self.filter(tenant_id=tenant_id).order_by('global_rank')
    
    def update_global_rankings(self, offer_data):
        """Update global rankings based on performance data."""
        # This would implement complex ranking logic
        pass
    
    def get_ranking_stats(self, date_from=None, date_to=None):
        """Get ranking statistics for a date range."""
        queryset = self.all()
        
        if date_from:
            queryset = queryset.filter(rank_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(rank_date__lte=date_to)
        
        return queryset.aggregate(
            total_offers=models.Count('id'),
            avg_rank=models.Avg('global_rank'),
            top_10_avg_rank=models.Avg('global_rank', filter=models.Q(global_rank__lte=10))
        )


# Add custom managers to models
OfferScore.add_manager_class = OfferScoreManager
GlobalOfferRank.add_manager_class = GlobalOfferRankManager
