"""
A/B Test Service for Offer Routing System

This module provides A/B testing functionality for comparing
different routing strategies and offer variations.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Avg, Count, Sum
from ..models import (
    RoutingABTest, ABTestAssignment, ABTestResult
)
from ..utils import calculate_statistical_significance
from ..constants import (
    DEFAULT_AB_TEST_SPLIT_PERCENTAGE, MIN_AB_TEST_DURATION_HOURS,
    STATISTICAL_SIGNIFICANCE_THRESHOLD
)
from ..exceptions import ABTestError

User = get_user_model()
logger = logging.getLogger(__name__)


class ABTestService:
    """
    Service for managing A/B tests in offer routing.
    
    Provides test creation, assignment, evaluation, and winner declaration.
    """
    
    def __init__(self):
        self.cache_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize A/B test services."""
        try:
            from .cache import RoutingCacheService
            self.cache_service = RoutingCacheService()
        except ImportError as e:
            logger.error(f"Failed to initialize A/B test services: {e}")
    
    def is_enabled(self, user: User) -> bool:
        """Check if A/B testing is enabled for user."""
        try:
            from ..models import PersonalizationConfig
            config = PersonalizationConfig.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if not config:
                return False
            
            return config.ab_testing_enabled
            
        except Exception as e:
            logger.error(f"Error checking A/B test enabled: {e}")
            return False
    
    def assign_user_to_test(self, user: User, offer: Any) -> Optional[Dict[str, Any]]:
        """
        Assign user to an A/B test for an offer.
        
        Args:
            user: User object
            offer: Offer object
            
        Returns:
            Dictionary with assignment details or None
        """
        try:
            # Get active tests for this offer
            active_tests = self._get_active_tests_for_offer(offer)
            
            if not active_tests:
                return None
            
            # Check if user is already assigned to any test
            existing_assignment = self._get_existing_assignment(user, active_tests)
            if existing_assignment:
                return existing_assignment
            
            # Assign to highest priority test
            test = max(active_tests, key=lambda x: x.priority)
            
            # Determine variant based on split percentage
            variant = self._determine_variant(test)
            
            # Create assignment
            assignment = ABTestAssignment.objects.create(
                test=test,
                user=user,
                variant=variant
            )
            
            result = {
                'test_id': test.id,
                'test_name': test.name,
                'variant': variant,
                'control_route_id': test.control_route.id,
                'variant_route_id': test.variant_route.id,
                'split_percentage': test.split_percentage,
                'assigned_at': assignment.assigned_at
            }
            
            # Cache assignment
            self._cache_assignment(user.id, offer.id, result)
            
            logger.info(f"Assigned user {user.id} to A/B test {test.name} as {variant}")
            return result
            
        except Exception as e:
            logger.error(f"Error assigning user to A/B test: {e}")
            return None
    
    def _get_active_tests_for_offer(self, offer: Any) -> List[RoutingABTest]:
        """Get active A/B tests for an offer."""
        try:
            # Get tests where this offer is either control or variant
            tests = RoutingABTest.objects.filter(
                is_active=True,
                started_at__isnull=False,
                ended_at__isnull=True
            ).filter(
                models.Q(control_route=offer) | models.Q(variant_route=offer)
            )
            
            return list(tests)
            
        except Exception as e:
            logger.error(f"Error getting active tests for offer: {e}")
            return []
    
    def _get_existing_assignment(self, user: User, tests: List[RoutingABTest]) -> Optional[Dict[str, Any]]:
        """Get existing assignment for user."""
        try:
            test_ids = [test.id for test in tests]
            
            assignment = ABTestAssignment.objects.filter(
                user=user,
                test_id__in=test_ids
            ).first()
            
            if assignment:
                return {
                    'test_id': assignment.test.id,
                    'test_name': assignment.test.name,
                    'variant': assignment.variant,
                    'control_route_id': assignment.test.control_route.id,
                    'variant_route_id': assignment.test.variant_route.id,
                    'split_percentage': assignment.test.split_percentage,
                    'assigned_at': assignment.assigned_at
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting existing assignment: {e}")
            return None
    
    def _determine_variant(self, test: RoutingABTest) -> str:
        """Determine which variant user should be assigned to."""
        try:
            import random
            
            # Use user ID for consistent assignment
            user_hash = hash(str(test.id)) % 100
            
            if user_hash < test.split_percentage:
                return 'variant'
            else:
                return 'control'
                
        except Exception as e:
            logger.error(f"Error determining variant: {e}")
            return 'control'
    
    def _cache_assignment(self, user_id: int, offer_id: int, assignment: Dict[str, Any]):
        """Cache A/B test assignment."""
        try:
            if self.cache_service:
                cache_key = f"ab_test_assignment:{user_id}:{offer_id}"
                self.cache_service.set(cache_key, assignment, timeout=3600)
        except Exception as e:
            logger.warning(f"Error caching A/B test assignment: {e}")
    
    def record_assignment_event(self, user: User, offer: Any, event_type: str, 
                             event_value: float = 0.0):
        """Record an event for A/B test assignment."""
        try:
            # Get assignment
            assignment = ABTestAssignment.objects.filter(
                user=user,
                test__control_route=offer
            ).first()
            
            if not assignment:
                assignment = ABTestAssignment.objects.filter(
                    user=user,
                    test__variant_route=offer
                ).first()
            
            if not assignment:
                return
            
            # Update assignment based on event type
            if event_type == 'impression':
                assignment.impressions += 1
            elif event_type == 'click':
                assignment.clicks += 1
            elif event_type == 'conversion':
                assignment.conversions += 1
                assignment.revenue += event_value
            
            assignment.save()
            
        except Exception as e:
            logger.error(f"Error recording assignment event: {e}")
    
    def evaluate_active_tests(self) -> int:
        """Evaluate all active A/B tests for statistical significance."""
        try:
            evaluated_count = 0
            
            # Get tests that have been running long enough
            from datetime import timedelta
            min_start_time = timezone.now() - timedelta(hours=MIN_AB_TEST_DURATION_HOURS)
            
            eligible_tests = RoutingABTest.objects.filter(
                is_active=True,
                started_at__lte=min_start_time,
                ended_at__isnull=True
            )
            
            for test in eligible_tests:
                if self._evaluate_test(test):
                    evaluated_count += 1
            
            logger.info(f"Evaluated {evaluated_count} A/B tests")
            return evaluated_count
            
        except Exception as e:
            logger.error(f"Error evaluating active tests: {e}")
            return 0
    
    def _evaluate_test(self, test: RoutingABTest) -> bool:
        """Evaluate a single A/B test."""
        try:
            # Get test statistics
            control_stats = test.get_control_stats()
            variant_stats = test.get_variant_stats()
            
            # Check minimum sample size
            total_sample = (control_stats['total_assignments'] + 
                          variant_stats['total_assignments'])
            
            if total_sample < test.min_sample_size:
                return False
            
            # Calculate statistical significance
            significance_result = calculate_statistical_significance(
                control_conversions=control_stats['total_conversions'],
                control_impressions=control_stats['total_impressions'],
                variant_conversions=variant_stats['total_conversions'],
                variant_impressions=variant_stats['total_impressions'],
                confidence_level=test.confidence_level
            )
            
            # Create or update test result
            result, created = ABTestResult.objects.update_or_create(
                test=test,
                defaults={
                    'control_impressions': control_stats['total_impressions'],
                    'control_clicks': control_stats['total_clicks'],
                    'control_conversions': control_stats['total_conversions'],
                    'control_revenue': control_stats['total_revenue'],
                    'variant_impressions': variant_stats['total_impressions'],
                    'variant_clicks': variant_stats['total_clicks'],
                    'variant_conversions': variant_stats['total_conversions'],
                    'variant_revenue': variant_stats['total_revenue'],
                    'control_cr': significance_result['control_cr'],
                    'variant_cr': significance_result['variant_cr'],
                    'cr_difference': significance_result['difference'],
                    'z_score': significance_result['z_score'],
                    'p_value': significance_result['p_value'],
                    'is_significant': significance_result['is_significant'],
                    'confidence_level': test.confidence_level,
                    'effect_size': significance_result.get('effect_size', 0.0),
                    'analyzed_at': timezone.now()
                }
            )
            
            # Determine winner if significant
            if significance_result['is_significant']:
                self._declare_winner(test, significance_result)
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating test {test.id}: {e}")
            return False
    
    def _declare_winner(self, test: RoutingABTest, significance_result: Dict[str, Any]):
        """Declare winner for A/B test."""
        try:
            if significance_result['variant_cr'] > significance_result['control_cr']:
                winner = 'variant'
                confidence = significance_result['confidence']
            else:
                winner = 'control'
                confidence = significance_result['confidence']
            
            # Update test
            test.winner = winner
            test.confidence = confidence
            test.p_value = significance_result['p_value']
            test.effect_size = significance_result.get('effect_size', 0.0)
            test.save()
            
            # Update result
            result = ABTestResult.objects.filter(test=test).first()
            if result:
                result.winner = winner
                result.winner_confidence = confidence
                result.save()
            
            logger.info(f"A/B test {test.name} winner: {winner} (confidence: {confidence:.2f})")
            
        except Exception as e:
            logger.error(f"Error declaring winner for test {test.id}: {e}")
    
    def stop_test(self, test_id: int) -> bool:
        """Stop an active A/B test."""
        try:
            test = RoutingABTest.objects.get(id=test_id)
            test.is_active = False
            test.ended_at = timezone.now()
            test.save()
            
            logger.info(f"Stopped A/B test: {test.name}")
            return True
            
        except RoutingABTest.DoesNotExist:
            logger.error(f"A/B test not found: {test_id}")
            return False
        except Exception as e:
            logger.error(f"Error stopping test: {e}")
            return False
    
    def create_ab_test(self, user: User, test_data: Dict[str, Any]) -> Optional[RoutingABTest]:
        """Create a new A/B test."""
        try:
            from ..models import OfferRoute
            
            test = RoutingABTest.objects.create(
                name=test_data.get('name'),
                description=test_data.get('description', ''),
                tenant=user.tenant,
                control_route=OfferRoute.objects.get(id=test_data['control_route_id']),
                variant_route=OfferRoute.objects.get(id=test_data['variant_route_id']),
                split_percentage=test_data.get('split_percentage', DEFAULT_AB_TEST_SPLIT_PERCENTAGE),
                duration_hours=test_data.get('duration_hours'),
                success_metric=test_data.get('success_metric', 'conversion_rate'),
                min_sample_size=test_data.get('min_sample_size', 1000),
                confidence_level=test_data.get('confidence_level', STATISTICAL_SIGNIFICANCE_THRESHOLD),
                created_by=user
            )
            
            logger.info(f"Created A/B test: {test.name}")
            return test
            
        except Exception as e:
            logger.error(f"Error creating A/B test: {e}")
            return None
    
    def start_test(self, test_id: int) -> bool:
        """Start an A/B test."""
        try:
            test = RoutingABTest.objects.get(id=test_id)
            test.is_active = True
            test.started_at = timezone.now()
            test.save()
            
            logger.info(f"Started A/B test: {test.name}")
            return True
            
        except RoutingABTest.DoesNotExist:
            logger.error(f"A/B test not found: {test_id}")
            return False
        except Exception as e:
            logger.error(f"Error starting test: {e}")
            return False
    
    def get_test_results(self, test_id: int) -> Optional[Dict[str, Any]]:
        """Get results for an A/B test."""
        try:
            test = RoutingABTest.objects.get(id=test_id)
            
            # Get test statistics
            control_stats = test.get_control_stats()
            variant_stats = test.get_variant_stats()
            
            # Get detailed results
            result = ABTestResult.objects.filter(test=test).first()
            
            return {
                'test': {
                    'id': test.id,
                    'name': test.name,
                    'description': test.description,
                    'is_active': test.is_active,
                    'started_at': test.started_at,
                    'ended_at': test.ended_at,
                    'winner': test.winner,
                    'confidence': test.confidence,
                    'p_value': test.p_value,
                    'effect_size': test.effect_size
                },
                'control_stats': control_stats,
                'variant_stats': variant_stats,
                'detailed_results': result
            }
            
        except RoutingABTest.DoesNotExist:
            logger.error(f"A/B test not found: {test_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting test results: {e}")
            return None
    
    def get_test_analytics(self, user: User, days: int = 30) -> Dict[str, Any]:
        """Get A/B test analytics for user."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get test statistics
            test_stats = RoutingABTest.objects.filter(
                tenant=user.tenant,
                created_at__gte=cutoff_date
            ).aggregate(
                total_tests=Count('id'),
                active_tests=Count('id', filter=Q(is_active=True)),
                completed_tests=Count('id', filter=Q(ended_at__isnull=False))
            )
            
            # Get winner distribution
            winner_distribution = RoutingABTest.objects.filter(
                tenant=user.tenant,
                winner__isnull=False
            ).values('winner').annotate(
                count=Count('id')
            )
            
            # Get performance metrics
            performance_metrics = ABTestResult.objects.filter(
                test__tenant=user.tenant,
                analyzed_at__gte=cutoff_date
            ).aggregate(
                avg_confidence=Avg('winner_confidence'),
                avg_effect_size=Avg('effect_size'),
                significant_tests=Count('id', filter=Q(is_significant=True))
            )
            
            return {
                'test_stats': test_stats,
                'winner_distribution': list(winner_distribution),
                'performance_metrics': performance_metrics,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting A/B test analytics: {e}")
            return {}
    
    def optimize_test_configuration(self, user: User) -> Dict[str, Any]:
        """Optimize A/B test configuration based on historical data."""
        try:
            # This would implement optimization logic
            # For now, return placeholder
            
            return {
                'optimal_split_percentage': DEFAULT_AB_TEST_SPLIT_PERCENTAGE,
                'optimal_sample_size': 1000,
                'optimal_confidence_level': STATISTICAL_SIGNIFICANCE_THRESHOLD,
                'recommendations': []
            }
            
        except Exception as e:
            logger.error(f"Error optimizing test configuration: {e}")
            return {}


# Singleton instance
ab_test_service = ABTestService()
