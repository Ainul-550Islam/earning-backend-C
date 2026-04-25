"""
User Journey Step Model for Offer Routing System

This module provides comprehensive user journey tracking,
including step-by-step interaction tracking, funnel analysis,
and journey optimization.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class UserJourneyStep(models.Model):
    """
    Model for tracking user journey steps.
    
    Tracks each step in the user's journey through
    the offer routing system, including interactions,
    decisions, and conversions.
    """
    
    # Core relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='journey_steps',
        verbose_name=_('User'),
        help_text=_('User this journey step belongs to')
    )
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='journey_steps',
        verbose_name=_('tenants.Tenant'),
        help_text=_('Tenant this journey step belongs to')
    )
    
    session_id = models.CharField(
        _('Session ID'),
        max_length=255,
        db_index=True,
        help_text=_('Session identifier for tracking')
    )
    
    # Journey step details
    step_type = models.CharField(
        _('Step Type'),
        max_length=50,
        choices=[
            ('page_view', _('Page View')),
            ('offer_impression', _('Offer Impression')),
            ('offer_click', _('Offer Click')),
            ('offer_interaction', _('Offer Interaction')),
            ('form_submit', _('Form Submit')),
            ('conversion', _('Conversion')),
            ('postback', _('Postback')),
            ('redirect', _('Redirect')),
            ('error', _('Error')),
            ('abandonment', _('Abandonment')),
            ('timeout', _('Timeout')),
        ],
        db_index=True,
        help_text=_('Type of journey step')
    )
    
    step_name = models.CharField(
        _('Step Name'),
        max_length=100,
        help_text=_('Name of the journey step')
    )
    
    step_number = models.IntegerField(
        _('Step Number'),
        help_text=_('Sequential number in journey')
    )
    
    # Offer and route information
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journey_steps',
        verbose_name=_('Offer'),
        help_text=_('Offer involved in this step')
    )
    
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journey_route_steps',
        verbose_name=_('Route'),
        help_text=_('Route involved in this step')
    )
    
    network = models.ForeignKey(
        'offer_inventory.OfferNetwork',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journey_steps',
        verbose_name=_('Network'),
        help_text=_('Network involved in this step')
    )
    
    # Timing information
    timestamp = models.DateTimeField(
        _('Timestamp'),
        db_index=True,
        help_text=_('When this journey step occurred')
    )
    
    duration_ms = models.IntegerField(
        _('Duration (ms)'),
        null=True,
        blank=True,
        help_text=_('Duration of this step in milliseconds')
    )
    
    # Geographic and device context
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('IP address of user')
    )
    
    country = models.CharField(
        _('Country'),
        max_length=2,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Country code (ISO 3166-1 alpha-2)')
    )
    
    region = models.CharField(
        _('Region'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Region or state')
    )
    
    city = models.CharField(
        _('City'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('City name')
    )
    
    device_type = models.CharField(
        _('Device Type'),
        max_length=50,
        choices=[
            ('desktop', _('Desktop')),
            ('mobile', _('Mobile')),
            ('tablet', _('Tablet')),
            ('smart_tv', _('Smart TV')),
            ('wearable', _('Wearable')),
            ('unknown', _('Unknown')),
        ],
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Type of device used')
    )
    
    os_type = models.CharField(
        _('OS Type'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Operating system type')
    )
    
    browser = models.CharField(
        _('Browser'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Browser type')
    )
    
    # User agent and referrer
    user_agent = models.TextField(
        _('User Agent'),
        null=True,
        blank=True,
        help_text=_('User agent string')
    )
    
    referrer = models.URLField(
        _('Referrer'),
        null=True,
        blank=True,
        help_text=_('Referrer URL')
    )
    
    # Step-specific data
    page_url = models.URLField(
        _('Page URL'),
        null=True,
        blank=True,
        help_text=_('URL of the page')
    )
    
    conversion_value = models.DecimalField(
        _('Conversion Value'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Value of conversion (revenue, points, etc.)')
    )
    
    # Context and metadata
    context = models.JSONField(
        _('Context'),
        default=dict,
        blank=True,
        help_text=_('Additional context information')
    )
    
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional metadata about the step')
    )
    
    # Journey analysis fields
    is_conversion_step = models.BooleanField(
        _('Is Conversion Step'),
        default=False,
        db_index=True,
        help_text=_('Whether this step resulted in a conversion')
    )
    
    is_funnel_entry = models.BooleanField(
        _('Is Funnel Entry'),
        default=False,
        help_text=_('Whether this is an entry point to the funnel')
    )
    
    is_funnel_exit = models.BooleanField(
        _('Is Funnel Exit'),
        default=False,
        help_text=_('Whether this is an exit point from the funnel')
    )
    
    funnel_stage = models.CharField(
        _('Funnel Stage'),
        max_length=50,
        choices=[
            ('awareness', _('Awareness')),
            ('interest', _('Interest')),
            ('consideration', _('Consideration')),
            ('intent', _('Intent')),
            ('evaluation', _('Evaluation')),
            ('purchase', _('Purchase')),
            ('post_purchase', _('Post Purchase')),
            ('retention', _('Retention')),
            ('advocacy', _('Advocacy')),
        ],
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Funnel stage this step belongs to')
    )
    
    # Performance metrics
    response_time_ms = models.IntegerField(
        _('Response Time (ms)'),
        null=True,
        blank=True,
        help_text=_('Response time for this step')
    )
    
    error_code = models.CharField(
        _('Error Code'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Error code if step failed')
    )
    
    error_message = models.TextField(
        _('Error Message'),
        null=True,
        blank=True,
        help_text=_('Error message if step failed')
    )
    
    # A/B testing information
    ab_test_id = models.IntegerField(
        _('A/B Test ID'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('A/B test ID if applicable')
    )
    
    ab_test_variant = models.CharField(
        _('A/B Test Variant'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('A/B test variant if applicable')
    )
    
    # Quality and scoring
    step_quality_score = models.DecimalField(
        _('Step Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score for this step (0-100)')
    )
    
    user_satisfaction = models.IntegerField(
        _('User Satisfaction'),
        null=True,
        blank=True,
        help_text=_('User satisfaction score (1-5)')
    )
    
    # Journey completion
    is_completed = models.BooleanField(
        _('Is Completed'),
        default=True,
        help_text=_('Whether this step was completed successfully')
    )
    
    completion_rate = models.DecimalField(
        _('Completion Rate'),
        max_digits=5,
        decimal_places=2,
        default=100.00,
        help_text=_('Completion rate percentage')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('Timestamp when this journey step was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('Timestamp when this journey step was last updated')
    )
    
    class Meta:
        db_table = 'offer_routing_user_journey_step'
        verbose_name = _('User Journey Step')
        verbose_name_plural = _('User Journey Steps')
        ordering = ['user', 'session_id', 'step_number']
        indexes = [
            models.Index(fields=['user', 'session_id'], name='idx_user_session_id_1346'),
            models.Index(fields=['user', 'timestamp'], name='idx_user_timestamp_1347'),
            models.Index(fields=['session_id', 'timestamp'], name='idx_session_id_timestamp_1348'),
            models.Index(fields=['step_type', 'timestamp'], name='idx_step_type_timestamp_1349'),
            models.Index(fields=['offer', 'timestamp'], name='idx_offer_timestamp_1350'),
            models.Index(fields=['is_conversion_step', 'timestamp'], name='idx_is_conversion_step_tim_f0f'),
            models.Index(fields=['funnel_stage', 'timestamp'], name='idx_funnel_stage_timestamp_2f4'),
            models.Index(fields=['country', 'timestamp'], name='idx_country_timestamp_1353'),
            models.Index(fields=['device_type', 'timestamp'], name='idx_device_type_timestamp_1354'),
            models.Index(fields=['created_at'], name='idx_created_at_1355'),
        ]
        unique_together = [
            ['session_id', 'step_number'],
        ]
    
    def __str__(self):
        return f"Journey Step: {self.user.username} - {self.step_type} - {self.step_number}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate step number
        if self.step_number < 0:
            raise ValidationError(_('Step number cannot be negative'))
        
        # Validate duration
        if self.duration_ms and self.duration_ms < 0:
            raise ValidationError(_('Duration cannot be negative'))
        
        # Validate completion rate
        if self.completion_rate < 0 or self.completion_rate > 100:
            raise ValidationError(_('Completion rate must be between 0 and 100'))
        
        # Validate quality score
        if self.step_quality_score < 0 or self.step_quality_score > 100:
            raise ValidationError(_('Quality score must be between 0 and 100'))
        
        # Validate user satisfaction
        if self.user_satisfaction and (self.user_satisfaction < 1 or self.user_satisfaction > 5):
            raise ValidationError(_('User satisfaction must be between 1 and 5'))
        
        # Validate country code
        if self.country and len(self.country) != 2:
            raise ValidationError(_('Country code must be 2 characters'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Set timestamp if not provided
        if not self.timestamp:
            self.timestamp = timezone.now()
        
        # Auto-detect funnel stage based on step type
        if not self.funnel_stage:
            self.funnel_stage = self._detect_funnel_stage()
        
        # Auto-set conversion step flag
        if not self.is_conversion_step:
            self.is_conversion_step = self.step_type in ['conversion', 'postback']
        
        # Auto-set funnel entry/exit flags
        if not self.is_funnel_entry and not self.is_funnel_exit:
            self._detect_funnel_entry_exit()
        
        super().save(*args, **kwargs)
    
    def _detect_funnel_stage(self) -> str:
        """Detect funnel stage based on step type."""
        stage_mapping = {
            'page_view': 'awareness',
            'offer_impression': 'interest',
            'offer_click': 'consideration',
            'offer_interaction': 'intent',
            'form_submit': 'evaluation',
            'conversion': 'purchase',
            'postback': 'post_purchase',
        }
        
        return stage_mapping.get(self.step_type, 'consideration')
    
    def _detect_funnel_entry_exit(self):
        """Detect if this is a funnel entry or exit point."""
        # Entry points
        if self.step_type in ['page_view', 'offer_impression']:
            self.is_funnel_entry = True
        
        # Exit points
        if self.step_type in ['error', 'abandonment', 'timeout']:
            self.is_funnel_exit = True
    
    @property
    def is_recent(self) -> bool:
        """Check if this step is recent (within last 24 hours)."""
        return self.timestamp >= timezone.now() - timedelta(hours=24)
    
    @property
    def is_high_value(self) -> bool:
        """Check if this is a high-value step."""
        return (
            self.is_conversion_step or
            (self.conversion_value and self.conversion_value > 10) or
            self.step_quality_score >= 80
        )
    
    @property
    def step_duration_seconds(self) -> float:
        """Get step duration in seconds."""
        if self.duration_ms:
            return self.duration_ms / 1000
        return 0.0
    
    @property
    def age_hours(self) -> int:
        """Get age of this step in hours."""
        if self.timestamp:
            return int((timezone.now() - self.timestamp).total_seconds() / 3600)
        return 0
    
    @property
    def device_category(self) -> str:
        """Get device category."""
        if self.device_type in ['desktop']:
            return 'computer'
        elif self.device_type in ['mobile', 'tablet']:
            return 'mobile'
        elif self.device_type in ['smart_tv']:
            return 'tv'
        elif self.device_type in ['wearable']:
            return 'wearable'
        else:
            return 'unknown'
    
    def get_journey_context(self) -> dict:
        """Get journey context for analysis."""
        return {
            'session_id': self.session_id,
            'step_number': self.step_number,
            'step_type': self.step_type,
            'step_name': self.step_name,
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': self.duration_ms,
            'device_info': {
                'type': self.device_type,
                'category': self.device_category,
                'os': self.os_type,
                'browser': self.browser,
            },
            'geo_info': {
                'ip_address': self.ip_address,
                'country': self.country,
                'region': self.region,
                'city': self.city,
            },
            'offer_info': {
                'offer_id': self.offer.id if self.offer else None,
                'route_id': self.route.id if self.route else None,
                'network_id': self.network.id if self.network else None,
            },
            'funnel_info': {
                'stage': self.funnel_stage,
                'is_entry': self.is_funnel_entry,
                'is_exit': self.is_funnel_exit,
                'is_conversion': self.is_conversion_step,
            },
            'performance_info': {
                'response_time_ms': self.response_time_ms,
                'quality_score': float(self.step_quality_score),
                'completion_rate': float(self.completion_rate),
                'is_completed': self.is_completed,
                'user_satisfaction': self.user_satisfaction,
            },
            'conversion_info': {
                'conversion_value': float(self.conversion_value) if self.conversion_value else None,
                'is_high_value': self.is_high_value,
            },
            'ab_test_info': {
                'test_id': self.ab_test_id,
                'variant': self.ab_test_variant,
            },
            'error_info': {
                'error_code': self.error_code,
                'error_message': self.error_message,
                'has_error': bool(self.error_code),
            }
        }
    
    def get_previous_step(self) -> Optional['UserJourneyStep']:
        """Get previous step in the journey."""
        try:
            return UserJourneyStep.objects.filter(
                user=self.user,
                session_id=self.session_id,
                step_number=self.step_number - 1
            ).first()
        except Exception as e:
            logger.error(f"Error getting previous step: {e}")
            return None
    
    def get_next_step(self) -> Optional['UserJourneyStep']:
        """Get next step in the journey."""
        try:
            return UserJourneyStep.objects.filter(
                user=self.user,
                session_id=self.session_id,
                step_number=self.step_number + 1
            ).first()
        except Exception as e:
            logger.error(f"Error getting next step: {e}")
            return None
    
    def get_session_steps(self) -> models.QuerySet:
        """Get all steps in this session."""
        return UserJourneyStep.objects.filter(
            session_id=self.session_id
        ).order_by('step_number')
    
    def get_user_journey(self, limit: int = 50) -> models.QuerySet:
        """Get user's recent journey steps."""
        return UserJourneyStep.objects.filter(
            user=self.user
        ).order_by('-timestamp')[:limit]
    
    def analyze_step_performance(self) -> dict:
        """Analyze performance of this step."""
        return {
            'efficiency_score': self._calculate_efficiency_score(),
            'engagement_score': self._calculate_engagement_score(),
            'conversion_probability': self._calculate_conversion_probability(),
            'bounce_risk': self._calculate_bounce_risk(),
            'quality_indicators': self._get_quality_indicators(),
            'optimization_suggestions': self._get_optimization_suggestions()
        }
    
    def _calculate_efficiency_score(self) -> float:
        """Calculate efficiency score for this step."""
        if not self.duration_ms:
            return 50.0  # Neutral score
        
        # Efficiency based on step type and duration
        efficiency_scores = {
            'page_view': 80.0,  # Fast loading is good
            'offer_impression': 70.0,  # Quick impression is good
            'offer_click': 90.0,  # Fast click response is excellent
            'offer_interaction': 85.0,  # Quick interaction is good
            'form_submit': 75.0,  # Reasonable form submission time
            'conversion': 95.0,  # Fast conversion is excellent
            'postback': 90.0,  # Fast postback is good
        }
        
        base_score = efficiency_scores.get(self.step_type, 70.0)
        
        # Adjust based on duration (lower is better for most steps)
        if self.duration_ms <= 1000:  # 1 second
            return min(base_score + 10, 100.0)
        elif self.duration_ms <= 3000:  # 3 seconds
            return base_score
        elif self.duration_ms <= 10000:  # 10 seconds
            return max(base_score - 10, 0.0)
        else:  # > 10 seconds
            return max(base_score - 20, 0.0)
    
    def _calculate_engagement_score(self) -> float:
        """Calculate engagement score for this step."""
        engagement_score = 0.0
        
        # Base score from step type
        step_weights = {
            'page_view': 10.0,
            'offer_impression': 20.0,
            'offer_click': 40.0,
            'offer_interaction': 50.0,
            'form_submit': 60.0,
            'conversion': 100.0,
            'postback': 30.0,
        }
        
        engagement_score += step_weights.get(self.step_type, 10.0)
        
        # Adjust for quality score
        engagement_score += self.step_quality_score * 0.3
        
        # Adjust for completion
        if self.is_completed:
            engagement_score += 20.0
        
        # Adjust for user satisfaction
        if self.user_satisfaction:
            satisfaction_score = (self.user_satisfaction - 3) * 10  # Convert 1-5 to -20 to 20
            engagement_score += satisfaction_score
        
        return min(engagement_score, 100.0)
    
    def _calculate_conversion_probability(self) -> float:
        """Calculate conversion probability based on step."""
        if self.step_type == 'conversion':
            return 100.0
        
        # Base probabilities by step type
        base_probabilities = {
            'page_view': 5.0,
            'offer_impression': 10.0,
            'offer_click': 25.0,
            'offer_interaction': 40.0,
            'form_submit': 60.0,
            'postback': 15.0,
        }
        
        probability = base_probabilities.get(self.step_type, 5.0)
        
        # Adjust for quality score
        probability += self.step_quality_score * 0.2
        
        # Adjust for funnel stage
        stage_multipliers = {
            'awareness': 0.5,
            'interest': 0.7,
            'consideration': 1.0,
            'intent': 1.5,
            'evaluation': 2.0,
            'purchase': 5.0,
        }
        
        if self.funnel_stage in stage_multipliers:
            probability *= stage_multipliers[self.funnel_stage]
        
        return min(probability, 100.0)
    
    def _calculate_bounce_risk(self) -> float:
        """Calculate bounce risk for this step."""
        if self.step_type in ['conversion', 'postback']:
            return 0.0  # No bounce risk
        
        bounce_risk = 0.0
        
        # High bounce risk indicators
        if self.step_type == 'page_view' and self.duration_ms and self.duration_ms < 3000:  # < 3 seconds
            bounce_risk += 30.0
        
        if self.step_type == 'offer_impression' and not self.offer_click:
            bounce_risk += 40.0
        
        if self.step_type == 'error':
            bounce_risk += 50.0
        
        if self.step_type == 'abandonment':
            bounce_risk += 60.0
        
        if self.step_type == 'timeout':
            bounce_risk += 70.0
        
        # Adjust for quality score
        bounce_risk -= self.step_quality_score * 0.2
        
        return max(min(bounce_risk, 100.0), 0.0)
    
    def _get_quality_indicators(self) -> dict:
        """Get quality indicators for this step."""
        indicators = {
            'has_error': bool(self.error_code),
            'is_slow': self.duration_ms and self.duration_ms > 5000,  # > 5 seconds
            'is_high_quality': self.step_quality_score >= 80,
            'is_low_quality': self.step_quality_score < 50,
            'is_completed': self.is_completed,
            'is_conversion': self.is_conversion_step,
        }
        
        # Add specific quality issues
        quality_issues = []
        
        if self.duration_ms and self.duration_ms > 10000:  # > 10 seconds
            quality_issues.append('slow_response')
        
        if self.step_quality_score < 60:
            quality_issues.append('low_quality_score')
        
        if not self.is_completed:
            quality_issues.append('incomplete_step')
        
        if self.error_code:
            quality_issues.append('error_occurred')
        
        indicators['quality_issues'] = quality_issues
        
        return indicators
    
    def _get_optimization_suggestions(self) -> list:
        """Get optimization suggestions for this step."""
        suggestions = []
        
        # Performance suggestions
        if self.duration_ms and self.duration_ms > 5000:
            suggestions.append("Consider optimizing page load time")
        
        if self.response_time_ms and self.response_time_ms > 2000:
            suggestions.append("Consider improving server response time")
        
        # Quality suggestions
        if self.step_quality_score < 70:
            suggestions.append("Improve step quality and user experience")
        
        # Conversion suggestions
        if self.step_type == 'form_submit' and not self.is_conversion_step:
            suggestions.append("Optimize form to improve conversion rate")
        
        if self.step_type == 'offer_click' and self.bounce_risk > 50:
            suggestions.append("Improve offer relevance and landing page")
        
        # Error suggestions
        if self.error_code:
            suggestions.append(f"Fix error: {self.error_code} - {self.error_message}")
        
        return suggestions
    
    @classmethod
    def get_user_journey_summary(cls, user_id: int, days: int = 30) -> dict:
        """Get summary of user's journey."""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            steps = cls.objects.filter(
                user_id=user_id,
                timestamp__gte=cutoff_date
            ).order_by('timestamp')
            
            if not steps.exists():
                return {
                    'total_steps': 0,
                    'conversion_steps': 0,
                    'conversion_rate': 0,
                    'avg_quality_score': 0,
                    'most_common_step_type': None,
                    'journey_duration_hours': 0,
                }
            
            # Calculate metrics
            total_steps = steps.count()
            conversion_steps = steps.filter(is_conversion_step=True).count()
            conversion_rate = (conversion_steps / total_steps * 100) if total_steps > 0 else 0
            
            avg_quality_score = steps.aggregate(
                avg_quality=models.Avg('step_quality_score')
            )['avg_quality'] or 0
            
            # Most common step type
            most_common = steps.values('step_type').annotate(
                count=models.Count('step_type')
            ).order_by('-count').first()
            
            # Journey duration
            first_step = steps.first()
            last_step = steps.last()
            journey_duration = 0
            
            if first_step and last_step:
                journey_duration = (last_step.timestamp - first_step.timestamp).total_seconds() / 3600
            
            return {
                'total_steps': total_steps,
                'conversion_steps': conversion_steps,
                'conversion_rate': conversion_rate,
                'avg_quality_score': float(avg_quality_score),
                'most_common_step_type': most_common['step_type'] if most_common else None,
                'journey_duration_hours': journey_duration,
                'steps_by_type': dict(
                    steps.values('step_type').annotate(
                        count=models.Count('step_type')
                    ).values_list('step_type', 'count')
                ),
                'quality_distribution': cls._get_quality_distribution(steps),
                'funnel_analysis': cls._analyze_funnel_progression(steps),
            }
            
        except Exception as e:
            logger.error(f"Error getting user journey summary: {e}")
            return {}
    
    @classmethod
    def _get_quality_distribution(cls, steps) -> dict:
        """Get quality score distribution."""
        distribution = {
            'excellent': 0,  # 90-100
            'good': 0,        # 80-89
            'average': 0,      # 70-79
            'below_average': 0, # 60-69
            'poor': 0,         # < 60
        }
        
        for step in steps:
            score = step.step_quality_score
            
            if score >= 90:
                distribution['excellent'] += 1
            elif score >= 80:
                distribution['good'] += 1
            elif score >= 70:
                distribution['average'] += 1
            elif score >= 60:
                distribution['below_average'] += 1
            else:
                distribution['poor'] += 1
        
        return distribution
    
    @classmethod
    def _analyze_funnel_progression(cls, steps) -> dict:
        """Analyze funnel progression."""
        funnel_stages = ['awareness', 'interest', 'consideration', 'intent', 'evaluation', 'purchase']
        
        stage_counts = {}
        for stage in funnel_stages:
            stage_counts[stage] = steps.filter(funnel_stage=stage).count()
        
        # Calculate drop-off rates
        total_users = stage_counts.get('awareness', 0)
        
        drop_off_rates = {}
        for i, stage in enumerate(funnel_stages[1:], 1):
            previous_stage = funnel_stages[i-1]
            previous_count = stage_counts.get(previous_stage, 0)
            current_count = stage_counts.get(stage, 0)
            
            if previous_count > 0:
                drop_off_rate = ((previous_count - current_count) / previous_count) * 100
                drop_off_rates[stage] = drop_off_rate
        
        return {
            'stage_counts': stage_counts,
            'drop_off_rates': drop_off_rates,
            'bottleneck_stage': max(drop_off_rates.items(), key=lambda x: x[1])[0] if drop_off_rates else None,
            'conversion_rate': (stage_counts.get('purchase', 0) / total_users * 100) if total_users > 0 else 0,
        }
    
    @classmethod
    def cleanup_old_steps(cls, days: int = 90):
        """Clean up old journey steps."""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            deleted_count = cls.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} old journey steps")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old journey steps: {e}")
            return 0


# Signal handlers for journey steps
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=UserJourneyStep)
def journey_step_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for journey steps."""
    if created:
        logger.info(f"New journey step created: {instance.step_type} - {instance.user.username}")
        
        # Trigger journey analysis tasks
        from ..tasks.journey import analyze_journey_step
        analyze_journey_step.delay(instance.id)

@receiver(post_delete, sender=UserJourneyStep)
def journey_step_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for journey steps."""
    logger.info(f"Journey step deleted: {instance.step_type} - {instance.user.username}")
