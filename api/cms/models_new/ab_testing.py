# api/cms/models_new/ab_testing.py
"""
Advanced A/B Testing Framework
Provides comprehensive A/B testing for offers, content, and user experience
"""
import uuid
import json
import logging
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Q, F, Count, Sum, Avg, StdDev
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db.models.functions import Cast
from django.db.models.expressions import RawSQL

logger = logging.getLogger(__name__)
User = get_user_model()


class ABTest(models.Model):
    """
    Main A/B test configuration
    """
    TEST_TYPES = [
        ('offer', _('Offer Test')),
        ('content', _('Content Test')),
        ('ui', _('UI/UX Test')),
        ('pricing', _('Pricing Test')),
        ('feature', _('Feature Test')),
    ]
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('running', _('Running')),
        ('paused', _('Paused')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Test Name"), max_length=200)
    description = models.TextField(_("Description"), blank=True)
    test_type = models.CharField(_("Test Type"), max_length=20, choices=TEST_TYPES)
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Targeting
    target_percentage = models.PositiveIntegerField(
        _("Target Percentage"), default=50,
        help_text=_("Percentage of users to include in test")
    )
    target_countries = models.JSONField(_("Target Countries"), default=list, blank=True)
    target_devices = models.JSONField(_("Target Devices"), default=list, blank=True)
    min_age = models.PositiveIntegerField(_("Min Age"), null=True, blank=True)
    max_age = models.PositiveIntegerField(_("Max Age"), null=True, blank=True)
    
    # Timing
    start_time = models.DateTimeField(_("Start Time"), null=True, blank=True)
    end_time = models.DateTimeField(_("End Time"), null=True, blank=True)
    min_duration_hours = models.PositiveIntegerField(
        _("Min Duration (hours)"), default=24,
        help_text=_("Minimum duration before test can be completed")
    )
    
    # Statistical settings
    confidence_level = models.DecimalField(
        _("Confidence Level"), max_digits=5, decimal_places=2, default=95.00,
        help_text=_("Statistical confidence level (e.g., 95.00)")
    )
    min_sample_size = models.PositiveIntegerField(
        _("Min Sample Size"), default=1000,
        help_text=_("Minimum participants per variant")
    )
    
    # Success metrics
    primary_metric = models.CharField(_("Primary Metric"), max_length=50, default='conversion_rate')
    secondary_metrics = models.JSONField(_("Secondary Metrics"), default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("A/B Test")
        verbose_name_plural = _("A/B Tests")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_time']),
            models.Index(fields=['test_type', 'status']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    def is_running(self) -> bool:
        """Check if test is currently running"""
        if self.status != 'running':
            return False
        
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        
        return True
    
    def should_include_user(self, user) -> bool:
        """Check if user should be included in this test"""
        if not self.is_running():
            return False
        
        # Check age targeting
        if self.min_age or self.max_age:
            if not hasattr(user, 'profile') or not user.profile.age:
                return False
            age = user.profile.age
            if self.min_age and age < self.min_age:
                return False
            if self.max_age and age > self.max_age:
                return False
        
        # Check country targeting
        if self.target_countries:
            user_country = getattr(user.profile, 'country', '') if hasattr(user, 'profile') else ''
            if not user_country or user_country not in self.target_countries:
                return False
        
        # Check device targeting (simplified)
        if self.target_devices:
            # Would need to check user's device from session
            pass
        
        # Hash-based user assignment for consistent split
        user_hash = hashlib.md5(f"{self.uuid}_{user.id}".encode()).hexdigest()
        hash_int = int(user_hash, 16)
        return (hash_int % 100) < self.target_percentage
    
    def get_user_variant(self, user):
        """Get which variant a user should see"""
        if not self.should_include_user(user):
            return None
        
        variants = self.variants.filter(is_active=True).order_by('traffic_split')
        if not variants.exists():
            return None
        
        # Consistent hash-based assignment
        user_hash = hashlib.md5(f"{self.uuid}_{user.id}".encode()).hexdigest()
        hash_int = int(user_hash, 16)
        user_percentage = (hash_int % 100) + 1
        
        # Find variant based on traffic split
        cumulative = 0
        for variant in variants:
            cumulative += variant.traffic_split
            if user_percentage <= cumulative:
                return variant
        
        # Fallback to first variant
        return variants.first()


class ABTestVariant(models.Model):
    """
    Individual test variant (A, B, C, etc.)
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(_("Variant Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    
    # Configuration
    is_control = models.BooleanField(_("Is Control Group"), default=False)
    traffic_split = models.PositiveIntegerField(
        _("Traffic Split"), default=50,
        help_text=_("Percentage of traffic to assign to this variant")
    )
    is_active = models.BooleanField(_("Active"), default=True)
    
    # Configuration data (JSON)
    configuration = models.JSONField(
        _("Configuration"), default=dict,
        help_text=_("Variant-specific configuration")
    )
    
    # Offer-specific fields
    offer_id = models.CharField(_("Offer ID"), max_length=100, blank=True)
    payout_multiplier = models.DecimalField(
        _("Payout Multiplier"), max_digits=5, decimal_places=2, default=1.00
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("A/B Test Variant")
        verbose_name_plural = _("A/B Test Variants")
        ordering = ['traffic_split']
        indexes = [
            models.Index(fields=['test', 'is_active', 'traffic_split']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.test.name} - {self.name}"


class ABTestParticipant(models.Model):
    """
    Track user participation in A/B tests
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE, related_name='participants')
    variant = models.ForeignKey(ABTestVariant, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ab_test_participations')
    
    # Participation tracking
    assigned_at = models.DateTimeField(_("Assigned At"), auto_now_add=True)
    first_seen_at = models.DateTimeField(_("First Seen At"), null=True, blank=True)
    last_seen_at = models.DateTimeField(_("Last Seen At"), null=True, blank=True)
    
    # Conversion tracking
    has_converted = models.BooleanField(_("Has Converted"), default=False)
    converted_at = models.DateTimeField(_("Converted At"), null=True, blank=True)
    conversion_value = models.DecimalField(
        _("Conversion Value"), max_digits=10, decimal_places=2, default=0
    )
    
    # Additional metrics
    clicks = models.PositiveIntegerField(_("Clicks"), default=0)
    page_views = models.PositiveIntegerField(_("Page Views"), default=0)
    time_spent_seconds = models.PositiveIntegerField(_("Time Spent (seconds)"), default=0)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("A/B Test Participant")
        verbose_name_plural = _("A/B Test Participants")
        unique_together = ['test', 'user']
        indexes = [
            models.Index(fields=['test', 'variant', 'has_converted']),
            models.Index(fields=['user', 'assigned_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.test.name} ({self.variant.name})"
    
    def record_conversion(self, value: Decimal = None):
        """Record conversion for this participant"""
        self.has_converted = True
        self.converted_at = timezone.now()
        if value is not None:
            self.conversion_value = value
        self.save(update_fields=['has_converted', 'converted_at', 'conversion_value'])


class ABTestResult(models.Model):
    """
    Aggregated test results and statistical analysis
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE, related_name='results')
    variant = models.ForeignKey(ABTestVariant, on_delete=models.CASCADE, related_name='results')
    
    # Participant counts
    total_participants = models.PositiveIntegerField(_("Total Participants"), default=0)
    active_participants = models.PositiveIntegerField(_("Active Participants"), default=0)
    
    # Conversion metrics
    conversions = models.PositiveIntegerField(_("Conversions"), default=0)
    conversion_rate = models.DecimalField(
        _("Conversion Rate"), max_digits=8, decimal_places=4, default=0
    )
    
    # Value metrics
    total_value = models.DecimalField(_("Total Value"), max_digits=12, decimal_places=2, default=0)
    avg_value_per_conversion = models.DecimalField(
        _("Avg Value per Conversion"), max_digits=10, decimal_places=2, default=0
    )
    avg_value_per_participant = models.DecimalField(
        _("Avg Value per Participant"), max_digits=10, decimal_places=2, default=0
    )
    
    # Engagement metrics
    total_clicks = models.PositiveIntegerField(_("Total Clicks"), default=0)
    total_page_views = models.PositiveIntegerField(_("Total Page Views"), default=0)
    avg_time_spent = models.DecimalField(
        _("Avg Time Spent"), max_digits=8, decimal_places=2, default=0
    )
    
    # Statistical significance
    confidence_interval_lower = models.DecimalField(
        _("Confidence Interval Lower"), max_digits=8, decimal_places=4, null=True, blank=True
    )
    confidence_interval_upper = models.DecimalField(
        _("Confidence Interval Upper"), max_digits=8, decimal_places=4, null=True, blank=True
    )
    p_value = models.DecimalField(_("P-Value"), max_digits=8, decimal_places=6, null=True, blank=True)
    is_statistically_significant = models.BooleanField(
        _("Statistically Significant"), default=False
    )
    
    # Comparison with control
    improvement_percentage = models.DecimalField(
        _("Improvement %"), max_digits=8, decimal_places=2, null=True, blank=True
    )
    is_winner = models.BooleanField(_("Is Winner"), default=False)
    
    calculated_at = models.DateTimeField(_("Calculated At"), auto_now_add=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("A/B Test Result")
        verbose_name_plural = _("A/B Test Results")
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['test', 'variant']),
            models.Index(fields=['is_winner']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.test.name} - {self.variant.name} Results"


# Service class for A/B testing
class ABTestingService:
    """
    Service for managing A/B tests and statistical analysis
    """
    
    @staticmethod
    def create_test(name: str, test_type: str, variants: list, **kwargs) -> ABTest:
        """Create a new A/B test with variants"""
        test = ABTest.objects.create(
            name=name,
            test_type=test_type,
            **kwargs
        )
        
        # Create variants
        for i, variant_data in enumerate(variants):
            ABTestVariant.objects.create(
                test=test,
                name=variant_data.get('name', f'Variant {chr(65 + i)}'),
                description=variant_data.get('description', ''),
                is_control=variant_data.get('is_control', i == 0),
                traffic_split=variant_data.get('traffic_split', 100 // len(variants)),
                configuration=variant_data.get('configuration', {}),
                **{k: v for k, v in variant_data.items() 
                   if k not in ['name', 'description', 'is_control', 'traffic_split', 'configuration']}
            )
        
        return test
    
    @staticmethod
    def start_test(test_uuid: str) -> bool:
        """Start an A/B test"""
        try:
            test = ABTest.objects.get(uuid=test_uuid, status='draft')
            test.status = 'running'
            test.start_time = timezone.now()
            test.save(update_fields=['status', 'start_time'])
            return True
        except ABTest.DoesNotExist:
            return False
    
    @staticmethod
    def get_user_variant(test_uuid: str, user) -> ABTestVariant:
        """Get or create user's variant assignment"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
        except ABTest.DoesNotExist:
            return None
        
        # Check if user already assigned
        try:
            participant = ABTestParticipant.objects.get(test=test, user=user)
            return participant.variant
        except ABTestParticipant.DoesNotExist:
            # Assign user to variant
            variant = test.get_user_variant(user)
            if variant:
                ABTestParticipant.objects.create(
                    test=test,
                    variant=variant,
                    user=user
                )
                return variant
        
        return None
    
    @staticmethod
    def record_conversion(test_uuid: str, user, value: Decimal = None):
        """Record conversion for user in test"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
            participant = ABTestParticipant.objects.get(test=test, user=user)
            participant.record_conversion(value)
        except (ABTest.DoesNotExist, ABTestParticipant.DoesNotExist):
            logger.warning(f"Failed to record conversion for test {test_uuid}, user {user.id}")
    
    @staticmethod
    def calculate_results(test_uuid: str) -> dict:
        """Calculate statistical results for A/B test"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
        except ABTest.DoesNotExist:
            return {}
        
        results = {}
        variants = test.variants.all()
        
        for variant in variants:
            participants = ABTestParticipant.objects.filter(variant=variant)
            
            # Basic metrics
            total_participants = participants.count()
            conversions = participants.filter(has_converted=True).count()
            conversion_rate = (conversions / total_participants * 100) if total_participants > 0 else 0
            
            # Value metrics
            total_value = participants.aggregate(
                total=Sum('conversion_value')
            )['total'] or Decimal('0')
            
            avg_value_per_conversion = (total_value / conversions) if conversions > 0 else Decimal('0')
            avg_value_per_participant = (total_value / total_participants) if total_participants > 0 else Decimal('0')
            
            # Engagement metrics
            total_clicks = participants.aggregate(total=Sum('clicks'))['total'] or 0
            total_page_views = participants.aggregate(total=Sum('page_views'))['total'] or 0
            avg_time_spent = participants.aggregate(avg=Avg('time_spent_seconds'))['avg'] or 0
            
            # Calculate confidence interval (simplified normal approximation)
            if total_participants > 30 and conversions > 0:
                import math
                p = conversion_rate / 100
                se = math.sqrt((p * (1 - p)) / total_participants)
                z_score = 1.96  # 95% confidence
                margin = z_score * se
                
                ci_lower = max(0, (p - margin) * 100)
                ci_upper = min(100, (p + margin) * 100)
            else:
                ci_lower = ci_upper = None
            
            # Store results
            result_data = {
                'variant_name': variant.name,
                'is_control': variant.is_control,
                'total_participants': total_participants,
                'conversions': conversions,
                'conversion_rate': round(conversion_rate, 4),
                'total_value': float(total_value),
                'avg_value_per_conversion': float(avg_value_per_conversion),
                'avg_value_per_participant': float(avg_value_per_participant),
                'total_clicks': total_clicks,
                'total_page_views': total_page_views,
                'avg_time_spent': round(float(avg_time_spent), 2),
                'confidence_interval_lower': round(ci_lower, 4) if ci_lower else None,
                'confidence_interval_upper': round(ci_upper, 4) if ci_upper else None,
            }
            
            results[str(variant.uuid)] = result_data
            
            # Save to database
            ABTestResult.objects.update_or_create(
                test=test,
                variant=variant,
                defaults={
                    'total_participants': total_participants,
                    'conversions': conversions,
                    'conversion_rate': conversion_rate,
                    'total_value': total_value,
                    'avg_value_per_conversion': avg_value_per_conversion,
                    'avg_value_per_participant': avg_value_per_participant,
                    'total_clicks': total_clicks,
                    'total_page_views': total_page_views,
                    'avg_time_spent': avg_time_spent,
                    'confidence_interval_lower': ci_lower,
                    'confidence_interval_upper': ci_upper,
                }
            )
        
        # Calculate improvements vs control
        control_result = None
        for result in results.values():
            if result['is_control']:
                control_result = result
                break
        
        if control_result:
            for result in results.values():
                if not result['is_control']:
                    if control_result['conversion_rate'] > 0:
                        improvement = ((result['conversion_rate'] - control_result['conversion_rate']) / 
                                     control_result['conversion_rate']) * 100
                        result['improvement_percentage'] = round(improvement, 2)
                    else:
                        result['improvement_percentage'] = None
        
        return {
            'test_uuid': str(test.uuid),
            'test_name': test.name,
            'test_type': test.test_type,
            'status': test.status,
            'results': results,
            'calculated_at': timezone.now().isoformat()
        }
    
    @staticmethod
    def get_running_tests() -> list:
        """Get all currently running A/B tests"""
        return ABTest.objects.filter(status='running').select_related('variants').prefetch_related('participants')
    
    @staticmethod
    def cleanup_old_tests():
        """Clean up completed tests older than 90 days"""
        cutoff_date = timezone.now() - timedelta(days=90)
        deleted_count = ABTest.objects.filter(
            status='completed',
            updated_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old A/B tests")
        return deleted_count
