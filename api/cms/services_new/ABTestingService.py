# api/cms/services_new/ABTestingService.py
"""
Service layer for Advanced A/B Testing
Handles test management, statistical analysis, and user assignment
"""
import json
import logging
import hashlib
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, F, Count, Sum, Avg, StdDev

from ..models_new.ab_testing import (
    ABTest, ABTestVariant, ABTestParticipant, ABTestResult
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ABTestingManager:
    """
    High-level manager for A/B testing operations
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def create_test(self, test_config: dict) -> ABTest:
        """Create a new A/B test with validation"""
        required_fields = ['name', 'test_type', 'variants']
        for field in required_fields:
            if field not in test_config:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate variants
        variants = test_config['variants']
        if len(variants) < 2:
            raise ValueError("At least 2 variants required for A/B test")
        
        total_traffic = sum(v.get('traffic_split', 0) for v in variants)
        if total_traffic != 100:
            raise ValueError(f"Traffic splits must sum to 100%, got {total_traffic}%")
        
        # Create test
        test = ABTest.objects.create(
            name=test_config['name'],
            description=test_config.get('description', ''),
            test_type=test_config['test_type'],
            target_percentage=test_config.get('target_percentage', 50),
            target_countries=test_config.get('target_countries', []),
            target_devices=test_config.get('target_devices', []),
            min_age=test_config.get('min_age'),
            max_age=test_config.get('max_age'),
            min_duration_hours=test_config.get('min_duration_hours', 24),
            confidence_level=Decimal(str(test_config.get('confidence_level', 95.00))),
            min_sample_size=test_config.get('min_sample_size', 1000),
            primary_metric=test_config.get('primary_metric', 'conversion_rate'),
            secondary_metrics=test_config.get('secondary_metrics', []),
        )
        
        # Create variants
        for i, variant_data in enumerate(variants):
            ABTestVariant.objects.create(
                test=test,
                name=variant_data['name'],
                description=variant_data.get('description', ''),
                is_control=variant_data.get('is_control', i == 0),
                traffic_split=variant_data['traffic_split'],
                configuration=variant_data.get('configuration', {}),
                offer_id=variant_data.get('offer_id', ''),
                payout_multiplier=Decimal(str(variant_data.get('payout_multiplier', 1.00))),
            )
        
        logger.info(f"Created A/B test: {test.name} with {len(variants)} variants")
        return test
    
    def start_test(self, test_uuid: str) -> bool:
        """Start an A/B test with validation"""
        try:
            test = ABTest.objects.get(uuid=test_uuid, status='draft')
        except ABTest.DoesNotExist:
            raise ValueError(f"Test {test_uuid} not found or not in draft status")
        
        # Validate test setup
        variants = test.variants.all()
        if variants.count() < 2:
            raise ValueError("Test must have at least 2 variants")
        
        total_traffic = variants.aggregate(total=Sum('traffic_split'))['total'] or 0
        if total_traffic != 100:
            raise ValueError(f"Variant traffic splits must sum to 100%, got {total_traffic}%")
        
        # Start test
        test.status = 'running'
        test.start_time = timezone.now()
        test.save(update_fields=['status', 'start_time'])
        
        # Clear cache
        self._clear_test_cache(test_uuid)
        
        logger.info(f"Started A/B test: {test.name}")
        return True
    
    def get_user_variant(self, test_uuid: str, user) -> Optional[ABTestVariant]:
        """Get or assign variant for user with caching"""
        cache_key = f"ab_test_variant_{test_uuid}_{user.id}"
        
        # Check cache first
        cached_variant = cache.get(cache_key)
        if cached_variant:
            return cached_variant
        
        try:
            test = ABTest.objects.get(uuid=test_uuid)
        except ABTest.DoesNotExist:
            return None
        
        # Check if user should be included
        if not test.should_include_user(user):
            cache.set(cache_key, None, self.cache_timeout)
            return None
        
        # Get or create participant
        try:
            participant = ABTestParticipant.objects.get(test=test, user=user)
            variant = participant.variant
        except ABTestParticipant.DoesNotExist:
            # Assign to variant
            variant = test.get_user_variant(user)
            if variant:
                participant = ABTestParticipant.objects.create(
                    test=test,
                    variant=variant,
                    user=user,
                    first_seen_at=timezone.now()
                )
                logger.info(f"Assigned user {user.id} to variant {variant.name} in test {test.name}")
        
        # Cache result
        cache.set(cache_key, variant, self.cache_timeout)
        return variant
    
    def track_conversion(self, test_uuid: str, user, value: Decimal = None, 
                      metadata: dict = None) -> bool:
        """Track conversion for user in test"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
            participant = ABTestParticipant.objects.get(test=test, user=user)
            
            # Record conversion
            participant.record_conversion(value)
            
            # Update participant metadata
            if metadata:
                # Store additional metadata if needed
                pass
            
            # Clear cache
            self._clear_test_cache(test_uuid)
            
            logger.info(f"Recorded conversion for user {user.id} in test {test.name}")
            return True
            
        except (ABTest.DoesNotExist, ABTestParticipant.DoesNotExist):
            logger.warning(f"Failed to record conversion for test {test_uuid}, user {user.id}")
            return False
    
    def track_engagement(self, test_uuid: str, user, engagement_type: str, 
                       value: int = 1) -> bool:
        """Track user engagement (clicks, page views, time)"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
            participant = ABTestParticipant.objects.get(test=test, user=user)
            
            # Update engagement metrics
            if engagement_type == 'click':
                participant.clicks = F('clicks') + value
            elif engagement_type == 'page_view':
                participant.page_views = F('page_views') + value
            elif engagement_type == 'time_spent':
                participant.time_spent_seconds = F('time_spent_seconds') + value
            
            participant.last_seen_at = timezone.now()
            participant.save(update_fields=[engagement_type, 'last_seen_at'])
            
            return True
            
        except (ABTest.DoesNotExist, ABTestParticipant.DoesNotExist):
            return False
    
    def calculate_results(self, test_uuid: str, force_recalculate: bool = False) -> Dict[str, Any]:
        """Calculate comprehensive test results with statistical analysis"""
        cache_key = f"ab_test_results_{test_uuid}"
        
        # Check cache
        if not force_recalculate:
            cached_results = cache.get(cache_key)
            if cached_results:
                return cached_results
        
        try:
            test = ABTest.objects.get(uuid=test_uuid)
        except ABTest.DoesNotExist:
            return {}
        
        # Get all variants with participants
        variants = test.variants.all().prefetch_related('participants')
        results = {}
        
        # Calculate metrics for each variant
        for variant in variants:
            variant_results = self._calculate_variant_metrics(variant)
            results[str(variant.uuid)] = variant_results
        
        # Calculate statistical significance
        results = self._calculate_statistical_significance(results)
        
        # Determine winner
        winner = self._determine_winner(results, test.primary_metric)
        if winner:
            results[winner]['is_winner'] = True
        
        # Cache results
        cache.set(cache_key, results, self.cache_timeout)
        
        return {
            'test_uuid': str(test.uuid),
            'test_name': test.name,
            'test_type': test.test_type,
            'status': test.status,
            'primary_metric': test.primary_metric,
            'confidence_level': float(test.confidence_level),
            'min_sample_size': test.min_sample_size,
            'results': results,
            'calculated_at': timezone.now().isoformat(),
            'has_winner': bool(winner)
        }
    
    def _calculate_variant_metrics(self, variant: ABTestVariant) -> Dict[str, Any]:
        """Calculate metrics for a single variant"""
        participants = variant.participants.all()
        
        # Basic counts
        total_participants = participants.count()
        active_participants = participants.filter(
            last_seen_at__isnull=False
        ).count()
        
        # Conversion metrics
        conversions = participants.filter(has_converted=True)
        conversion_count = conversions.count()
        conversion_rate = (conversion_count / total_participants * 100) if total_participants > 0 else 0
        
        # Value metrics
        total_value = conversions.aggregate(
            total=Sum('conversion_value')
        )['total'] or Decimal('0')
        
        avg_value_per_conversion = (total_value / conversion_count) if conversion_count > 0 else Decimal('0')
        avg_value_per_participant = (total_value / total_participants) if total_participants > 0 else Decimal('0')
        
        # Engagement metrics
        total_clicks = participants.aggregate(total=Sum('clicks'))['total'] or 0
        total_page_views = participants.aggregate(total=Sum('page_views'))['total'] or 0
        avg_time_spent = participants.aggregate(avg=Avg('time_spent_seconds'))['avg'] or 0
        
        return {
            'variant_name': variant.name,
            'is_control': variant.is_control,
            'total_participants': total_participants,
            'active_participants': active_participants,
            'conversions': conversion_count,
            'conversion_rate': round(conversion_rate, 4),
            'total_value': float(total_value),
            'avg_value_per_conversion': float(avg_value_per_conversion),
            'avg_value_per_participant': float(avg_value_per_participant),
            'total_clicks': total_clicks,
            'total_page_views': total_page_views,
            'avg_time_spent': round(float(avg_time_spent), 2),
            'click_through_rate': round((total_clicks / total_page_views * 100), 2) if total_page_views > 0 else 0,
        }
    
    def _calculate_statistical_significance(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistical significance between variants"""
        # Find control variant
        control_uuid = None
        control_data = None
        
        for uuid, data in results.items():
            if data['is_control']:
                control_uuid = uuid
                control_data = data
                break
        
        if not control_data or control_data['total_participants'] < 30:
            return results  # Not enough data for significance testing
        
        # Calculate significance for each variant vs control
        for uuid, data in results.items():
            if uuid == control_uuid:
                continue
            
            # Two-proportion z-test for conversion rates
            p1 = control_data['conversion_rate'] / 100
            p2 = data['conversion_rate'] / 100
            n1 = control_data['total_participants']
            n2 = data['total_participants']
            
            if n1 < 30 or n2 < 30:
                data['p_value'] = None
                data['is_statistically_significant'] = False
                continue
            
            # Pooled proportion
            p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
            
            # Standard error
            se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
            
            if se == 0:
                data['p_value'] = None
                data['is_statistically_significant'] = False
                continue
            
            # Z-score
            z_score = (p2 - p1) / se
            
            # P-value (two-tailed)
            from scipy import stats
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
            
            # Confidence interval
            confidence_level = 0.95  # Could be configurable
            z_critical = stats.norm.ppf((1 + confidence_level) / 2)
            margin = z_critical * math.sqrt(p2 * (1 - p2) / n2)
            
            ci_lower = max(0, (p2 - margin) * 100)
            ci_upper = min(100, (p2 + margin) * 100)
            
            # Update results
            data['p_value'] = round(p_value, 6)
            data['is_statistically_significant'] = p_value < 0.05
            data['confidence_interval_lower'] = round(ci_lower, 4)
            data['confidence_interval_upper'] = round(ci_upper, 4)
            
            # Calculate improvement
            if control_data['conversion_rate'] > 0:
                improvement = ((data['conversion_rate'] - control_data['conversion_rate']) / 
                             control_data['conversion_rate']) * 100
                data['improvement_percentage'] = round(improvement, 2)
            else:
                data['improvement_percentage'] = None
        
        return results
    
    def _determine_winner(self, results: Dict[str, Any], primary_metric: str) -> Optional[str]:
        """Determine winning variant based on primary metric"""
        winner = None
        best_value = None
        
        for uuid, data in results.items():
            if not data['is_statistically_significant']:
                continue
            
            if primary_metric == 'conversion_rate':
                value = data['conversion_rate']
            elif primary_metric == 'avg_value_per_participant':
                value = data['avg_value_per_participant']
            elif primary_metric == 'total_value':
                value = data['total_value']
            else:
                value = data['conversion_rate']  # Default
            
            if best_value is None or value > best_value:
                best_value = value
                winner = uuid
        
        return winner
    
    def get_running_tests(self) -> List[ABTest]:
        """Get all currently running tests"""
        return ABTest.objects.filter(status='running').select_related('variants').prefetch_related('participants')
    
    def pause_test(self, test_uuid: str) -> bool:
        """Pause a running test"""
        try:
            test = ABTest.objects.get(uuid=test_uuid, status='running')
            test.status = 'paused'
            test.save(update_fields=['status'])
            
            # Clear cache
            self._clear_test_cache(test_uuid)
            
            logger.info(f"Paused A/B test: {test.name}")
            return True
        except ABTest.DoesNotExist:
            return False
    
    def complete_test(self, test_uuid: str, force: bool = False) -> bool:
        """Complete a test with validation"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
        except ABTest.DoesNotExist:
            return False
        
        # Check minimum duration
        if not force and test.start_time:
            duration = timezone.now() - test.start_time
            min_duration = timedelta(hours=test.min_duration_hours)
            if duration < min_duration:
                raise ValueError(f"Test must run at least {test.min_duration_hours} hours")
        
        # Check minimum sample size
        if not force:
            for variant in test.variants.all():
                participant_count = variant.participants.count()
                if participant_count < test.min_sample_size:
                    raise ValueError(f"Variant {variant.name} needs at least {test.min_sample_size} participants")
        
        # Complete test
        test.status = 'completed'
        test.end_time = timezone.now()
        test.save(update_fields=['status', 'end_time'])
        
        # Calculate final results
        self.calculate_results(test_uuid, force_recalculate=True)
        
        # Clear cache
        self._clear_test_cache(test_uuid)
        
        logger.info(f"Completed A/B test: {test.name}")
        return True
    
    def _clear_test_cache(self, test_uuid: str):
        """Clear cache for a specific test"""
        cache_keys = [
            f"ab_test_results_{test_uuid}",
            f"ab_test_variants_{test_uuid}",
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        # Clear user assignment cache
        # This would require tracking all users in the test
        # For now, we'll let them expire naturally


class ABTestingAnalytics:
    """
    Analytics service for A/B testing insights
    """
    
    @staticmethod
    def get_test_overview(days: int = 30) -> Dict[str, Any]:
        """Get overview of all A/B tests"""
        from django.db.models import Count, Avg, Sum
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        tests = ABTest.objects.filter(
            created_at__gte=cutoff_date
        ).aggregate(
            total_tests=Count('id'),
            running_tests=Count('id', filter=Q(status='running')),
            completed_tests=Count('id', filter=Q(status='completed')),
            avg_duration=Avg('end_time') - Avg('start_time'),
        )
        
        return {
            'period_days': days,
            'total_tests': tests['total_tests'] or 0,
            'running_tests': tests['running_tests'] or 0,
            'completed_tests': tests['completed_tests'] or 0,
            'completion_rate': round((tests['completed_tests'] or 0) / max(tests['total_tests'] or 1, 1) * 100, 2),
        }
    
    @staticmethod
    def get_variant_performance(test_uuid: str) -> Dict[str, Any]:
        """Get detailed performance analysis for test variants"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
        except ABTest.DoesNotExist:
            return {}
        
        variants = test.variants.all().prefetch_related('participants')
        performance_data = {}
        
        for variant in variants:
            participants = variant.participants.all()
            
            # Cohort analysis
            daily_stats = {}
            for participant in participants:
                day = participant.assigned_at.date()
                if day not in daily_stats:
                    daily_stats[day] = {'assigned': 0, 'converted': 0}
                daily_stats[day]['assigned'] += 1
                if participant.has_converted:
                    daily_stats[day]['converted'] += 1
            
            # Calculate daily conversion rates
            daily_conversion_rates = {}
            for day, stats in daily_stats.items():
                if stats['assigned'] > 0:
                    daily_conversion_rates[day.isoformat()] = (
                        stats['converted'] / stats['assigned'] * 100
                    )
            
            performance_data[str(variant.uuid)] = {
                'variant_name': variant.name,
                'daily_conversion_rates': daily_conversion_rates,
                'cumulative_conversions': list(
                    participants.filter(has_converted=True)
                    .order_by('converted_at')
                    .values_list('converted_at', 'conversion_value')
                )
            }
        
        return performance_data
    
    @staticmethod
    def get_user_journey(test_uuid: str, user_id: int) -> Dict[str, Any]:
        """Get user's journey through A/B test"""
        try:
            test = ABTest.objects.get(uuid=test_uuid)
            user = User.objects.get(id=user_id)
            participant = ABTestParticipant.objects.get(test=test, user=user)
        except (ABTest.DoesNotExist, User.DoesNotExist, ABTestParticipant.DoesNotExist):
            return {}
        
        return {
            'test_name': test.name,
            'variant_name': participant.variant.name,
            'assigned_at': participant.assigned_at.isoformat(),
            'first_seen_at': participant.first_seen_at.isoformat() if participant.first_seen_at else None,
            'last_seen_at': participant.last_seen_at.isoformat() if participant.last_seen_at else None,
            'has_converted': participant.has_converted,
            'converted_at': participant.converted_at.isoformat() if participant.converted_at else None,
            'conversion_value': float(participant.conversion_value),
            'clicks': participant.clicks,
            'page_views': participant.page_views,
            'time_spent_seconds': participant.time_spent_seconds,
            'engagement_score': min(
                (participant.clicks + participant.page_views * 2 + participant.time_spent_seconds / 60) / 100, 1.0
            )
        }
