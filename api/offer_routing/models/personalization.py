"""
Personalization Models for Offer Routing System

This module contains models for user preference vectors,
contextual signals, and personalization configurations.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import (
    PersonalizationAlgorithm, SignalType, PersonalizationLevel
)
from ..constants import MAX_PREFERENCE_VECTOR_SIZE

User = get_user_model()


class UserPreferenceVector(models.Model):
    """
    User preference vector for collaborative filtering.
    
    Stores user preferences across different offer categories as a vector
    of weights that influence personalization decisions.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='preference_vectors',
        verbose_name=_('User')
    )
    vector = models.JSONField(_('Preference Vector'), default=dict)
    category_weights = models.JSONField(_('Category Weights'), default=dict)
    
    # Metadata
    last_updated = models.DateTimeField(_('Last Updated'), auto_now=True)
    version = models.IntegerField(_('Version'), default=1)
    
    # Performance tracking
    update_frequency = models.IntegerField(_('Update Frequency'), default=24)  # Hours
    accuracy_score = models.DecimalField(_('Accuracy Score'), max_digits=5, decimal_places=2, default=0.0)
    
    class Meta:
        db_table = 'offer_routing_user_preference_vectors'
        verbose_name = _('User Preference Vector')
        verbose_name_plural = _('User Preference Vectors')
        indexes = [
            models.Index(fields=['user'], name='idx_user_1290'),
            models.Index(fields=['last_updated'], name='idx_last_updated_1291'),
            models.Index(fields=['accuracy_score'], name='idx_accuracy_score_1292'),
        ]
    
    def __str__(self):
        return f"{self.user.username} Preferences (v{self.version})"
    
    def clean(self):
        """Validate model data."""
        if not isinstance(self.vector, dict):
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Preference vector must be a dictionary'))
        
        if len(self.vector) > MAX_PREFERENCE_VECTOR_SIZE:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Preference vector cannot exceed {} categories').format(MAX_PREFERENCE_VECTOR_SIZE))
        
        if not isinstance(self.category_weights, dict):
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Category weights must be a dictionary'))
        
        # Validate weights sum to 1.0
        total_weight = sum(self.category_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Category weights must sum to 1.0'))
    
    def get_category_weight(self, category):
        """Get weight for a specific category."""
        return self.category_weights.get(category, 0.1)
    
    def update_vector(self, new_vector):
        """Update preference vector with new data."""
        if isinstance(new_vector, dict):
            self.vector.update(new_vector)
            self.last_updated = timezone.now()
        self.save()
    
    def merge_vector(self, other_vector, weight=0.5):
        """Merge another vector into this one."""
        if not isinstance(other_vector, dict):
            return
        
        for category, weight in other_vector.items():
            current_weight = self.get_category_weight(category)
            merged_weight = (current_weight * (1 - weight)) + (weight * other_vector.get(category, 0))
            self.category_weights[category] = merged_weight
        
        self.last_updated = timezone.now()
        self.save()
    
    def calculate_similarity(self, other_vector):
        """Calculate cosine similarity with another preference vector."""
        if not isinstance(other_vector, dict):
            return 0.0
        
        # Calculate dot product
        dot_product = 0.0
        for category in set(self.vector.keys()) & set(other_vector.keys()):
            dot_product += self.vector.get(category, 0) * other_vector.get(category, 0)
        
        # Calculate magnitudes
        magnitude1 = sum((self.vector.get(cat, 0) ** 2) for cat in self.vector.values()) ** 0.5
        magnitude2 = sum((other_vector.get(cat, 0) ** 2) for cat in other_vector.values()) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)


class ContextualSignal(models.Model):
    """
    Real-time contextual signals for personalization.
    
    Captures user's current context like time of day, location,
    device, or behavior to influence offer selection.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='contextual_signals',
        verbose_name=_('User')
    )
    signal_type = models.CharField(
        _('Signal Type'),
        max_length=20,
        choices=SignalType.CHOICES
    )
    value = models.JSONField(_('Signal Value'))
    confidence = models.DecimalField(_('Confidence'), max_digits=5, decimal_places=2, default=1.0)
    expires_at = models.DateTimeField(_('Expires At'), null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_contextual_signals'
        verbose_name = _('Contextual Signal')
        verbose_name_plural = _('Contextual Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'signal_type'], name='idx_user_signal_type_1293'),
            models.Index(fields=['expires_at'], name='idx_expires_at_1294'),
            models.Index(fields=['created_at'], name='idx_created_at_1295'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.signal_type}: {self.value}"
    
    def is_expired(self):
        """Check if signal has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def clean(self):
        """Validate model data."""
        if self.confidence < 0 or self.confidence > 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Confidence must be between 0 and 1'))
    
    def create_signal(self, user, signal_type, value, expires_hours=24):
        """Create a new contextual signal."""
        from datetime import timedelta
        expires_at = timezone.now() + timedelta(hours=expires_hours) if expires_hours > 0 else None
        
        return self.objects.create(
            user=user,
            signal_type=signal_type,
            value=value,
            confidence=1.0,
            expires_at=expires_at
        )
    
    def create_time_signal(self, user, hour_of_day):
        """Create time-based signal."""
        return self.create_signal(
            user=user,
            signal_type=SignalType.TIME,
            value={'hour_of_day': hour_of_day},
            expires_hours=2  # Expire after 2 hours
        )
    
    def create_location_signal(self, user, country, region=None, city=None):
        """Create location-based signal."""
        return self.create_signal(
            user=user,
            signal_type=SignalType.LOCATION,
            value={'country': country, 'region': region, 'city': city},
            expires_hours=24  # Location signals expire after 24 hours
        )
    
    def create_device_signal(self, user, device_type, os_type=None, browser=None):
        """Create device-based signal."""
        value = {'device_type': device_type}
        if os_type:
            value['os_type'] = os_type
        if browser:
            value['browser'] = browser
        
        return self.create_signal(
            user=user,
            signal_type=SignalType.DEVICE,
            value=value,
            expires_hours=12  # Device signals expire after 12 hours
        )
    
    def create_behavior_signal(self, user, event_type, count=1, window_days=30):
        """Create behavior-based signal."""
        return self.create_signal(
            user=user,
            signal_type=SignalType.BEHAVIOR,
            value={
                'event_type': event_type,
                'count': count,
                'window_days': window_days
            },
            expires_hours=168  # Behavior signals expire after 7 days
        )
    
    def create_context_signal(self, user, context_data):
        """Create general context signal."""
        return self.create_signal(
            user=user,
            signal_type=SignalType.CONTEXT,
            value=context_data,
            expires_hours=6  # Context signals expire after 6 hours
        )


class PersonalizationConfig(models.Model):
    """
    Configuration for personalization algorithms and parameters.
    
    Defines which personalization methods to use, weights,
    and thresholds for different user segments.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='personalization_configs',
        verbose_name=_('User')
    )
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='personalization_configs_user',
        verbose_name=_('tenants.Tenant')
    )
    
    # Algorithm configuration
    algorithm = models.CharField(
        _('Algorithm'),
        max_length=50,
        choices=PersonalizationAlgorithm.CHOICES,
        default=PersonalizationAlgorithm.HYBRID
    )
    
    # Weight configuration
    collaborative_weight = models.DecimalField(
        _('Collaborative Weight'),
        max_digits=5,
        decimal_places=2,
        default=0.4,
        help_text=_('Weight for collaborative filtering (0.0-1.0)')
    )
    content_based_weight = models.DecimalField(
        _('Content-Based Weight'),
        max_digits=5,
        decimal_places=2,
        default=0.3,
        help_text=_('Weight for content-based filtering (0.0-1.0)')
    )
    hybrid_weight = models.DecimalField(
        _('Hybrid Weight'),
        max_digits=5,
        decimal_places=2,
        default=0.3,
        help_text=_('Weight for hybrid approach (0.0-1.0)')
    )
    
    # Thresholds and parameters
    min_affinity_score = models.DecimalField(
        _('Min Affinity Score'),
        max_digits=5,
        decimal_places=2,
        default=0.1,
        help_text=_('Minimum affinity score to use personalization (0.0-1.0)')
    )
    max_offers_per_user = models.IntegerField(
        _('Max Offers Per User'),
        default=50,
        help_text=_('Maximum personalized offers to show per user')
    )
    diversity_factor = models.DecimalField(
        _('Diversity Factor'),
        max_digits=5,
        decimal_places=2,
        default=0.2,
        help_text=_('Factor for offer diversity (0.0-1.0)')
    )
    freshness_weight = models.DecimalField(
        _('Freshness Weight'),
        max_digits=5,
        decimal_places=2,
        default=0.1,
        help_text=_('Weight for offer freshness (0.0-1.0)')
    )
    
    # User segment configuration
    new_user_days = models.IntegerField(
        _('New User Days'),
        default=7,
        help_text=_('Days to consider user as "new"')
    )
    active_user_days = models.IntegerField(
        _('Active User Days'),
        default=30,
        help_text=_('Days of activity to consider user as "active"')
    )
    premium_user_multiplier = models.DecimalField(
        _('Premium User Multiplier'),
        max_digits=5,
        decimal_places=2,
        default=1.5,
        help_text=_('Multiplier for premium users (1.0-10.0)')
    )
    
    # Real-time personalization settings
    real_time_enabled = models.BooleanField(_('Real-Time Personalization'), default=True)
    context_signals_enabled = models.BooleanField(_('Contextual Signals Enabled'), default=True)
    real_time_weight = models.DecimalField(
        _('Real-Time Weight'),
        max_digits=5,
        decimal_places=2,
        default=0.5,
        help_text=_('Weight for real-time signals in personalization (0.0-1.0)')
    )
    
    # Advanced settings
    machine_learning_enabled = models.BooleanField(_('Machine Learning Enabled'), default=False)
    ml_model_path = models.CharField(
        _('ML Model Path'),
        max_length=255,
        blank=True,
        help_text=_('Path to machine learning model file')
    )
    ml_update_frequency = models.IntegerField(
        _('ML Update Frequency'),
        default=24,
        help_text=_('Hours between ML model updates')
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_personalization_configs'
        verbose_name = _('Personalization Config')
        verbose_name_plural = _('Personalization Configs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant'], name='idx_tenant_1296'),
            models.Index(fields=['user'], name='idx_user_1297'),
            models.Index(fields=['algorithm'], name='idx_algorithm_1298'),
            models.Index(fields=['created_at'], name='idx_created_at_1299'),
        ]
    
    def __str__(self):
        if self.tenant:
            return f"{self.tenant.username} - {self.algorithm}"
        return f"{self.user.username} - {self.algorithm}"
    
    def clean(self):
        """Validate model data."""
        total_weight = (
            self.collaborative_weight + 
            self.content_based_weight + 
            self.hybrid_weight
        )
        
        if abs(total_weight - 1.0) > 0.01:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Weights must sum to 1.0'))
        
        if self.min_affinity_score < 0 or self.min_affinity_score > 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Min affinity score must be between 0 and 1'))
        
        if self.diversity_factor < 0 or self.diversity_factor > 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Diversity factor must be between 0 and 1'))
        
        if self.freshness_weight < 0 or self.freshness_weight > 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Freshness weight must be between 0 and 1'))
        
        if self.new_user_days < 1 or self.new_user_days > 30:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('New user days must be between 1 and 30'))
        
        if self.active_user_days < 1 or self.active_user_days > 90:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Active user days must be between 1 and 90'))
        
        if self.premium_user_multiplier < 0.1 or self.premium_user_multiplier > 10:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Premium user multiplier must be between 0.1 and 10'))
    
    def get_effective_weights(self):
        """Get normalized weights that sum to 1.0."""
        total_weight = (
            self.collaborative_weight + 
            self.content_based_weight + 
            self.hybrid_weight
        )
        
        if total_weight == 0:
            return {
                'collaborative': 0.0,
                'content_based': 0.0,
                'hybrid': 0.0
            }
        
        return {
            'collaborative': self.collaborative_weight / total_weight,
            'content_based': self.content_based_weight / total_weight,
            'hybrid': self.hybrid_weight / total_weight
        }
    
    def should_use_personalization(self, user):
        """Check if personalization should be applied to user."""
        if self.algorithm == PersonalizationAlgorithm.RULE_BASED:
            return False  # Rule-based doesn't need personalization
        
        # Check if user has sufficient affinity data
        preference_vector = user.preferencevector_set.first()
        if not preference_vector:
            return False
        
        # Check if user meets minimum affinity threshold
        if self.min_affinity_score > 0:
            # This would check actual affinity scores
            return True  # Placeholder - would check actual scores
        
        return True


# Custom managers for personalization models
class UserPreferenceVectorManager(models.Manager):
    """Custom manager for UserPreferenceVector."""
    
    def get_user_vector(self, user_id):
        """Get preference vector for a user."""
        try:
            return self.get(user=user_id)
        except self.model.DoesNotExist:
            return None
    
    def update_user_vectors(self, user_id, vector_data):
        """Update preference vector for a user."""
        try:
            vector = self.get(user=user_id)
            vector.update_vector(vector_data)
            vector.save()
            return vector
        except self.model.DoesNotExist:
            return None
    
    def get_users_with_affinity(self, category, min_score=0.1):
        """Get users who have affinity for a category."""
        return self.filter(
            category_weights__contains={category: str(min_score)},
            accuracy_score__gte=min_score
        )


class ContextualSignalManager(models.Manager):
    """Custom manager for ContextualSignal."""
    
    def get_active_signals(self, user_id):
        """Get all active signals for a user."""
        return self.filter(user_id=user_id, expires_at__gt=timezone.now())
    
    def get_signals_by_type(self, user_id, signal_type):
        """Get signals by type for a user."""
        return self.filter(user_id=user_id, signal_type=signal_type)
    
    def get_recent_signals(self, user_id, hours=24):
        """Get recent signals for a user."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(user_id=user_id, created_at__gte=cutoff)
    
    def create_user_signals(self, user_id, signal_data):
        """Create multiple signals for a user."""
        signals = []
        
        for signal_type, data in signal_data.items():
            signal = ContextualSignal(
                user_id=user_id,
                signal_type=signal_type,
                value=data,
                confidence=1.0
            )
            signals.append(signal)
        
        return ContextualSignal.objects.bulk_create(signals)


class PersonalizationConfigManager(models.Manager):
    """Custom manager for PersonalizationConfig."""
    
    def get_active_config(self, tenant_id=None):
        """Get active personalization configuration."""
        queryset = self.filter(is_active=True)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.first()
        return queryset.first()
    
    def get_config_for_user(self, user_id):
        """Get personalization configuration for a user."""
        try:
            # Try tenant-specific config first
            config = self.get_active_config(tenant_id=user.tenant.id)
            if config:
                return config
        except:
            # Fallback to global config
            return self.filter(user_id=user_id, tenant__isnull=True).first()
    
    def get_configs_by_algorithm(self, algorithm):
        """Get configurations using specific algorithm."""
        return self.filter(algorithm=algorithm, is_active=True)
    
    def get_real_time_configs(self):
        """Get all real-time personalization configurations."""
        return self.filter(real_time_enabled=True, is_active=True)
    
    def update_config_weights(self, config_id, weights):
        """Update weights in personalization configuration."""
        config = self.get(id=config_id)
        if config:
            config.collaborative_weight = weights.get('collaborative', config.collaborative_weight)
            config.content_based_weight = weights.get('content_based', config.content_based_weight)
            config.hybrid_weight = weights.get('hybrid', config.hybrid_weight)
            config.save()
    
    def create_default_config(self, user_id, tenant_id=None):
        """Create default personalization configuration."""
        return self.create(
            user_id=user_id,
            tenant_id=tenant_id,
            algorithm=PersonalizationAlgorithm.HYBRID,
            collaborative_weight=0.4,
            content_based_weight=0.3,
            hybrid_weight=0.3,
            min_affinity_score=0.1,
            max_offers_per_user=50,
            diversity_factor=0.2,
            freshness_weight=0.1,
            new_user_days=7,
            active_user_days=30,
            premium_user_multiplier=1.5,
            real_time_enabled=True,
            real_time_weight=0.5
        )


# Add custom managers to models
UserPreferenceVector.add_manager_class = UserPreferenceVectorManager
ContextualSignal.add_manager_class = ContextualSignalManager
PersonalizationConfig.add_manager_class = PersonalizationConfigManager
