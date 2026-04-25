"""
A/B Test Service

Manages A/B testing for offer routing
system with statistical analysis.
"""

import logging
import math
import statistics
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, F
from django.core.cache import cache
from django.db import transaction
from ....models import (
    OfferRoute, RoutingABTest, ABTestAssignment, ABTestResult,
    UserOfferHistory, RoutingDecisionLog
)
from ....constants import (
    AB_TEST_CACHE_TIMEOUT, ASSIGNMENT_CACHE_TIMEOUT,
    MIN_AB_TEST_SAMPLE_SIZE, STATISTICAL_SIGNIFICANCE_LEVEL,
    DEFAULT_TRAFFIC_SPLIT, AB_TEST_DURATION_DAYS,
    AB_TEST_WARMUP_DAYS, MIN_VARIANTS_PER_TEST
)
from ....exceptions import ABTestError, ABTestAssignmentError
from ....utils import get_ab_test_key, calculate_ab_test_stats

User = get_user_model()
logger = logging.getLogger(__name__)


class ABTestService:
    """
    Service for managing A/B tests in offer routing.
    
    Manages A/B testing functionality:
    - Test creation and configuration
    - User assignment and traffic splitting
    - Statistical analysis and winner determination
    - Test monitoring and reporting
    - Test lifecycle management
    
    Performance targets:
    - User assignment: <5ms per assignment
    - Statistical analysis: <50ms per test
    - Cache hit rate: >95%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.ab_test_stats = {
            'total_assignments': 0,
            'total_tests': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_assignment_time_ms': 0.0
        }
        
        # Statistical test methods
        self.statistical_methods = {
            'z_test': self._z_test_analysis,
            't_test': self._t_test_analysis,
            'chi_square': self._chi_square_analysis,
            'mann_whitney': self._mann_whitney_analysis,
            'bootstrap': self._bootstrap_analysis
        }
        
        # Assignment strategies
        self.assignment_strategies = {
            'random': self._random_assignment,
            'hash_based': self._hash_based_assignment,
            'weighted': self._weighted_assignment,
            'sequential': self._sequential_assignment
        }
    
    def assign_user_to_test(self, user: User, context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Assign user to appropriate A/B test.
        
        Args:
            user: User object
            context: Additional context
            
        Returns:
            Assignment information or None
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = get_ab_test_key(user.id)
            cached_assignment = self.cache_service.get(cache_key)
            
            if cached_assignment:
                self.ab_test_stats['cache_hits'] += 1
                return cached_assignment
            
            # Get active tests for user
            active_tests = self._get_active_tests_for_user(user, context)
            
            if not active_tests:
                return None
            
            # Assign user to tests
            assignments = []
            
            for test in active_tests:
                assignment = self._assign_user_to_test(user, test, context)
                if assignment:
                    assignments.append(assignment)
            
            if not assignments:
                return None
            
            # Get primary assignment (highest priority)
            primary_assignment = max(assignments, key=lambda x: x['test_priority'])
            
            # Cache assignment
            self.cache_service.set(cache_key, primary_assignment, ASSIGNMENT_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_assignment_stats(elapsed_ms)
            
            logger.info(f"Assigned user {user.id} to test {primary_assignment['test_id']}")
            
            return primary_assignment
            
        except Exception as e:
            logger.error(f"Error assigning user {user.id} to A/B test: {e}")
            self.ab_test_stats['errors'] += 1
            return None
    
    def _get_active_tests_for_user(self, user: User, context: Dict[str, Any]) -> List[RoutingABTest]:
        """Get active A/B tests that apply to this user."""
        try:
            # Get all active tests
            active_tests = RoutingABTest.objects.filter(
                is_active=True,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            ).order_by('-priority')
            
            # Filter tests based on user eligibility
            eligible_tests = []
            
            for test in active_tests:
                if self._is_user_eligible_for_test(user, test, context):
                    eligible_tests.append(test)
            
            return eligible_tests
            
        except Exception as e:
            logger.error(f"Error getting active tests for user {user.id}: {e}")
            return []
    
    def _is_user_eligible_for_test(self, user: User, test: RoutingABTest, 
                                   context: Dict[str, Any]) -> bool:
        """Check if user is eligible for a specific test."""
        try:
            # Check if user is already assigned
            existing_assignment = ABTestAssignment.objects.filter(
                user=user,
                test=test
            ).first()
            
            if existing_assignment:
                return False  # User already assigned
            
            # Check test targeting criteria
            if test.targeting_criteria:
                if not self._evaluate_targeting_criteria(user, test.targeting_criteria, context):
                    return False
            
            # Check test sample size requirements
            if not self._check_sample_size_requirements(test):
                return False
            
            # Check test warmup period
            if not self._check_warmup_period(test, user):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking user eligibility for test {test.id}: {e}")
            return False
    
    def _evaluate_targeting_criteria(self, user: User, criteria: Dict[str, Any], 
                                    context: Dict[str, Any]) -> bool:
        """Evaluate targeting criteria for test eligibility."""
        try:
            # User segment criteria
            if 'user_segments' in criteria:
                required_segments = criteria['user_segments']
                user_segments = self._get_user_segments(user)
                
                if not any(segment in required_segments for segment in user_segments):
                    return False
            
            # Geographic criteria
            if 'geography' in criteria:
                geo_criteria = criteria['geography']
                user_location = context.get('location', {})
                
                if 'countries' in geo_criteria:
                    required_countries = geo_criteria['countries']
                    user_country = user_location.get('country')
                    
                    if user_country not in required_countries:
                        return False
            
            # Device criteria
            if 'devices' in criteria:
                device_criteria = criteria['devices']
                user_device = context.get('device', {})
                
                if 'device_types' in device_criteria:
                    required_devices = device_criteria['device_types']
                    user_device_type = user_device.get('type')
                    
                    if user_device_type not in required_devices:
                        return False
            
            # Time criteria
            if 'time' in criteria:
                time_criteria = criteria['time']
                current_time = timezone.now()
                
                if 'hours' in time_criteria:
                    required_hours = time_criteria['hours']
                    current_hour = current_time.hour
                    
                    if current_hour not in required_hours:
                        return False
            
            # Custom criteria
            if 'custom' in criteria:
                custom_criteria = criteria['custom']
                # This would evaluate custom business rules
                # For now, return True
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating targeting criteria: {e}")
            return False
    
    def _check_sample_size_requirements(self, test: RoutingABTest) -> bool:
        """Check if test has sufficient sample size."""
        try:
            # Get current sample size
            current_assignments = ABTestAssignment.objects.filter(
                test=test
            ).count()
            
            # Check minimum sample size
            if current_assignments >= MIN_AB_TEST_SAMPLE_SIZE:
                return True
            
            # Check if test is still in warmup period
            warmup_end = test.start_date + timezone.timedelta(days=AB_TEST_WARMUP_DAYS)
            if timezone.now() < warmup_end:
                return True  # Still in warmup
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking sample size requirements: {e}")
            return False
    
    def _check_warmup_period(self, test: RoutingABTest, user: User) -> bool:
        """Check if user is eligible considering warmup period."""
        try:
            # Check if test is in warmup
            warmup_end = test.start_date + timezone.timedelta(days=AB_TEST_WARMUP_DAYS)
            if timezone.now() < warmup_end:
                return True  # Allow new users during warmup
            
            # Check user registration date
            user_registration = user.date_joined
            test_start = test.start_date
            
            # User must be registered before test start
            if user_registration > test_start:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking warmup period: {e}")
            return False
    
    def _assign_user_to_test(self, user: User, test: RoutingABTest, 
                             context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Assign user to a specific test."""
        try:
            # Get assignment strategy
            strategy = test.assignment_strategy or 'random'
            
            # Get variant assignment
            variant = self._assign_variant(user, test, strategy)
            
            if not variant:
                return None
            
            # Create assignment record
            with transaction.atomic():
                assignment = ABTestAssignment.objects.create(
                    user=user,
                    test=test,
                    variant=variant['name'],
                    assigned_at=timezone.now(),
                    assignment_context=context or {}
                )
                
                # Update test assignment count
                test.assignment_count = F('assignment_count') + 1
                test.save()
            
            return {
                'test_id': test.id,
                'test_name': test.name,
                'variant': variant['name'],
                'variant_config': variant['config'],
                'test_priority': test.priority,
                'assignment_id': assignment.id,
                'assigned_at': assignment.assigned_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error assigning user {user.id} to test {test.id}: {e}")
            return None
    
    def _assign_variant(self, user: User, test: RoutingABTest, strategy: str) -> Optional[Dict[str, Any]]:
        """Assign user to a test variant."""
        try:
            # Get assignment function
            assign_func = self.assignment_strategies.get(strategy)
            
            if not assign_func:
                assign_func = self._random_assignment
            
            # Get variants
            variants = self._get_test_variants(test)
            
            if not variants:
                return None
            
            # Assign variant
            variant_name = assign_func(user, test, variants)
            
            # Get variant configuration
            variant_config = next((v['config'] for v in variants if v['name'] == variant_name), None)
            
            if not variant_config:
                return None
            
            return {
                'name': variant_name,
                'config': variant_config
            }
            
        except Exception as e:
            logger.error(f"Error assigning variant: {e}")
            return None
    
    def _get_test_variants(self, test: RoutingABTest) -> List[Dict[str, Any]]:
        """Get all variants for a test."""
        try:
            variants = []
            
            # Add control variant
            variants.append({
                'name': 'control',
                'config': test.control_config or {},
                'traffic_split': test.control_traffic_split or DEFAULT_TRAFFIC_SPLIT
            })
            
            # Add variant A
            if test.variant_a_config:
                variants.append({
                    'name': 'variant_a',
                    'config': test.variant_a_config,
                    'traffic_split': test.variant_a_traffic_split or DEFAULT_TRAFFIC_SPLIT
                })
            
            # Add variant B
            if test.variant_b_config:
                variants.append({
                    'name': 'variant_b',
                    'config': test.variant_b_config,
                    'traffic_split': test.variant_b_traffic_split or DEFAULT_TRAFFIC_SPLIT
                })
            
            # Add additional variants
            if test.additional_variants:
                for variant_data in test.additional_variants:
                    variants.append({
                        'name': variant_data['name'],
                        'config': variant_data['config'],
                        'traffic_split': variant_data.get('traffic_split', DEFAULT_TRAFFIC_SPLIT)
                    })
            
            return variants
            
        except Exception as e:
            logger.error(f"Error getting test variants: {e}")
            return []
    
    def _random_assignment(self, user: User, test: RoutingABTest, 
                         variants: List[Dict[str, Any]]) -> str:
        """Random assignment strategy."""
        try:
            import random
            
            # Calculate cumulative traffic splits
            total_split = sum(v['traffic_split'] for v in variants)
            
            # Normalize splits
            normalized_variants = []
            cumulative = 0.0
            
            for variant in variants:
                normalized_split = variant['traffic_split'] / total_split
                cumulative += normalized_split
                normalized_variants.append({
                    'name': variant['name'],
                    'cumulative': cumulative
                })
            
            # Random selection
            random_value = random.random()
            
            for variant in normalized_variants:
                if random_value <= variant['cumulative']:
                    return variant['name']
            
            # Fallback to first variant
            return variants[0]['name']
            
        except Exception as e:
            logger.error(f"Error in random assignment: {e}")
            return 'control'
    
    def _hash_based_assignment(self, user: User, test: RoutingABTest, 
                              variants: List[Dict[str, Any]]) -> str:
        """Hash-based assignment strategy."""
        try:
            import hashlib
            
            # Create hash from user ID and test ID
            hash_input = f"{user.id}:{test.id}"
            hash_value = hashlib.md5(hash_input.encode()).hexdigest()
            
            # Convert to number
            hash_number = int(hash_value[:8], 16)
            
            # Calculate variant based on hash
            total_split = sum(v['traffic_split'] for v in variants)
            hash_percentage = (hash_number % 10000) / 10000.0
            
            cumulative = 0.0
            for variant in variants:
                normalized_split = variant['traffic_split'] / total_split
                cumulative += normalized_split
                
                if hash_percentage <= cumulative:
                    return variant['name']
            
            # Fallback to first variant
            return variants[0]['name']
            
        except Exception as e:
            logger.error(f"Error in hash-based assignment: {e}")
            return 'control'
    
    def _weighted_assignment(self, user: User, test: RoutingABTest, 
                           variants: List[Dict[str, Any]]) -> str:
        """Weighted assignment strategy."""
        try:
            # This would consider user characteristics for weighted assignment
            # For now, fall back to random assignment
            return self._random_assignment(user, test, variants)
            
        except Exception as e:
            logger.error(f"Error in weighted assignment: {e}")
            return 'control'
    
    def _sequential_assignment(self, user: User, test: RoutingABTest, 
                             variants: List[Dict[str, Any]]) -> str:
        """Sequential assignment strategy."""
        try:
            # Get current assignment count
            current_count = test.assignment_count or 0
            
            # Calculate variant based on count
            total_split = sum(v['traffic_split'] for v in variants)
            
            cumulative = 0.0
            count_mod = current_count % total_split
            
            for variant in variants:
                cumulative += variant['traffic_split']
                
                if count_mod < cumulative:
                    return variant['name']
            
            # Fallback to first variant
            return variants[0]['name']
            
        except Exception as e:
            logger.error(f"Error in sequential assignment: {e}")
            return 'control'
    
    def get_test_results(self, test_id: int) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive results for an A/B test.
        
        Args:
            test_id: Test ID
            
        Returns:
            Test results or None
        """
        try:
            # Get test
            test = RoutingABTest.objects.filter(id=test_id).first()
            
            if not test:
                return None
            
            # Get assignments
            assignments = ABTestAssignment.objects.filter(test=test)
            
            # Get performance data
            performance_data = self._get_test_performance_data(test)
            
            # Calculate statistical analysis
            statistical_analysis = self._calculate_statistical_analysis(test, performance_data)
            
            # Determine winner
            winner = self._determine_test_winner(test, statistical_analysis)
            
            return {
                'test_id': test.id,
                'test_name': test.name,
                'test_description': test.description,
                'start_date': test.start_date.isoformat(),
                'end_date': test.end_date.isoformat(),
                'status': test.status,
                'assignments': {
                    'total': assignments.count(),
                    'by_variant': self._get_assignment_counts_by_variant(assignments)
                },
                'performance': performance_data,
                'statistical_analysis': statistical_analysis,
                'winner': winner,
                'confidence_level': STATISTICAL_SIGNIFICANCE_LEVEL,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting test results for {test_id}: {e}")
            return None
    
    def _get_test_performance_data(self, test: RoutingABTest) -> Dict[str, Any]:
        """Get performance data for a test."""
        try:
            # Get variants
            variants = self._get_test_variants(test)
            
            performance_by_variant = {}
            
            for variant in variants:
                variant_name = variant['name']
                
                # Get performance metrics for this variant
                variant_performance = self._get_variant_performance(test, variant_name)
                
                performance_by_variant[variant_name] = variant_performance
            
            return performance_by_variant
            
        except Exception as e:
            logger.error(f"Error getting test performance data: {e}")
            return {}
    
    def _get_variant_performance(self, test: RoutingABTest, variant: str) -> Dict[str, Any]:
        """Get performance metrics for a specific variant."""
        try:
            # Get assignments for this variant
            assignments = ABTestAssignment.objects.filter(
                test=test,
                variant=variant
            )
            
            # Get users in this variant
            user_ids = list(assignments.values_list('user_id', flat=True))
            
            if not user_ids:
                return self._get_empty_performance_metrics()
            
            # Get offer history for these users
            test_start = test.start_date
            test_end = min(test.end_date, timezone.now())
            
            performance_data = UserOfferHistory.objects.filter(
                user_id__in=user_ids,
                created_at__gte=test_start,
                created_at__lte=test_end
            ).aggregate(
                total_views=Count('id'),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False)),
                total_revenue=Sum('conversion_value'),
                avg_score=Avg('score_at_time')
            )
            
            # Calculate derived metrics
            total_views = performance_data['total_views'] or 0
            total_clicks = performance_data['total_clicks'] or 0
            total_conversions = performance_data['total_conversions'] or 0
            total_revenue = float(performance_data['total_revenue'] or 0.0)
            
            click_rate = total_clicks / max(1, total_views)
            conversion_rate = total_conversions / max(1, total_views)
            revenue_per_user = total_revenue / max(1, len(user_ids))
            avg_revenue_per_conversion = total_revenue / max(1, total_conversions)
            
            return {
                'user_count': len(user_ids),
                'total_views': total_views,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'total_revenue': total_revenue,
                'click_rate': click_rate,
                'conversion_rate': conversion_rate,
                'revenue_per_user': revenue_per_user,
                'avg_revenue_per_conversion': avg_revenue_per_conversion,
                'avg_score': float(performance_data['avg_score'] or 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error getting variant performance: {e}")
            return self._get_empty_performance_metrics()
    
    def _get_empty_performance_metrics(self) -> Dict[str, Any]:
        """Get empty performance metrics structure."""
        return {
            'user_count': 0,
            'total_views': 0,
            'total_clicks': 0,
            'total_conversions': 0,
            'total_revenue': 0.0,
            'click_rate': 0.0,
            'conversion_rate': 0.0,
            'revenue_per_user': 0.0,
            'avg_revenue_per_conversion': 0.0,
            'avg_score': 0.0
        }
    
    def _get_assignment_counts_by_variant(self, assignments) -> Dict[str, int]:
        """Get assignment counts grouped by variant."""
        try:
            counts = {}
            
            for assignment in assignments:
                variant = assignment.variant
                counts[variant] = counts.get(variant, 0) + 1
            
            return counts
            
        except Exception as e:
            logger.error(f"Error getting assignment counts: {e}")
            return {}
    
    def _calculate_statistical_analysis(self, test: RoutingABTest, 
                                    performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistical analysis for test results."""
        try:
            # Get primary metric
            primary_metric = test.primary_metric or 'conversion_rate'
            
            # Get variant data
            control_data = performance_data.get('control', self._get_empty_performance_metrics())
            variant_data = {}
            
            for variant, data in performance_data.items():
                if variant != 'control':
                    variant_data[variant] = data
            
            if not variant_data:
                return {'error': 'No variant data available'}
            
            # Calculate statistical tests
            analysis_results = {}
            
            for variant_name, variant_perf in variant_data.items():
                # Get metric values
                control_value = control_data.get(primary_metric, 0.0)
                variant_value = variant_perf.get(primary_metric, 0.0)
                
                # Get sample sizes
                control_sample = control_data.get('user_count', 0)
                variant_sample = variant_perf.get('user_count', 0)
                
                # Calculate statistical tests
                statistical_tests = {}
                
                for test_name, test_func in self.statistical_methods.items():
                    try:
                        test_result = test_func(
                            control_value, variant_value,
                            control_sample, variant_sample,
                            primary_metric
                        )
                        statistical_tests[test_name] = test_result
                    except Exception as e:
                        logger.warning(f"Statistical test {test_name} failed: {e}")
                        statistical_tests[test_name] = {'error': str(e)}
                
                analysis_results[variant_name] = {
                    'control_value': control_value,
                    'variant_value': variant_value,
                    'lift': ((variant_value - control_value) / max(0.001, control_value)) * 100,
                    'control_sample': control_sample,
                    'variant_sample': variant_sample,
                    'statistical_tests': statistical_tests
                }
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error calculating statistical analysis: {e}")
            return {'error': str(e)}
    
    def _z_test_analysis(self, control_value: float, variant_value: float,
                        control_sample: int, variant_sample: int,
                        metric: str) -> Dict[str, Any]:
        """Perform Z-test statistical analysis."""
        try:
            if control_sample < 30 or variant_sample < 30:
                return {'error': 'Sample size too small for Z-test'}
            
            # Calculate pooled standard error
            if metric in ['conversion_rate', 'click_rate']:
                # For rates, use proportion standard error
                pooled_rate = (control_value * control_sample + variant_value * variant_sample) / (control_sample + variant_sample)
                se = math.sqrt(pooled_rate * (1 - pooled_rate) * (1/control_sample + 1/variant_sample))
            else:
                # For other metrics, calculate standard deviation
                # This would need actual data points, for now use approximation
                se = 0.1  # Placeholder
            
            # Calculate Z-score
            if se == 0:
                return {'error': 'Standard error is zero'}
            
            z_score = (variant_value - control_value) / se
            
            # Calculate p-value (two-tailed)
            from scipy import stats
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
            
            # Check significance
            is_significant = p_value < STATISTICAL_SIGNIFICANCE_LEVEL
            
            return {
                'z_score': z_score,
                'p_value': p_value,
                'is_significant': is_significant,
                'confidence_level': (1 - p_value) * 100
            }
            
        except Exception as e:
            logger.error(f"Error in Z-test analysis: {e}")
            return {'error': str(e)}
    
    def _t_test_analysis(self, control_value: float, variant_value: float,
                         control_sample: int, variant_sample: int,
                         metric: str) -> Dict[str, Any]:
        """Perform T-test statistical analysis."""
        try:
            # This would need actual data points for proper T-test
            # For now, return simplified analysis
            return {
                'error': 'T-test requires individual data points'
            }
            
        except Exception as e:
            logger.error(f"Error in T-test analysis: {e}")
            return {'error': str(e)}
    
    def _chi_square_analysis(self, control_value: float, variant_value: float,
                           control_sample: int, variant_sample: int,
                           metric: str) -> Dict[str, Any]:
        """Perform Chi-square statistical analysis."""
        try:
            if metric not in ['conversion_rate', 'click_rate']:
                return {'error': 'Chi-square test only applicable to rates'}
            
            # Calculate observed and expected values
            control_conversions = int(control_value * control_sample)
            variant_conversions = int(variant_value * variant_sample)
            
            total_conversions = control_conversions + variant_conversions
            total_sample = control_sample + variant_sample
            
            expected_control = total_conversions * control_sample / total_sample
            expected_variant = total_conversions * variant_sample / total_sample
            
            # Calculate Chi-square statistic
            chi_square = (
                ((control_conversions - expected_control) ** 2 / expected_control) +
                ((variant_conversions - expected_variant) ** 2 / expected_variant)
            )
            
            # Calculate p-value
            from scipy import stats
            p_value = 1 - stats.chi2.cdf(chi_square, df=1)
            
            # Check significance
            is_significant = p_value < STATISTICAL_SIGNIFICANCE_LEVEL
            
            return {
                'chi_square': chi_square,
                'p_value': p_value,
                'is_significant': is_significant,
                'confidence_level': (1 - p_value) * 100
            }
            
        except Exception as e:
            logger.error(f"Error in Chi-square analysis: {e}")
            return {'error': str(e)}
    
    def _mann_whitney_analysis(self, control_value: float, variant_value: float,
                              control_sample: int, variant_sample: int,
                              metric: str) -> Dict[str, Any]:
        """Perform Mann-Whitney U test."""
        try:
            # This would need actual data points for proper Mann-Whitney test
            # For now, return simplified analysis
            return {
                'error': 'Mann-Whitney test requires individual data points'
            }
            
        except Exception as e:
            logger.error(f"Error in Mann-Whitney analysis: {e}")
            return {'error': str(e)}
    
    def _bootstrap_analysis(self, control_value: float, variant_value: float,
                         control_sample: int, variant_sample: int,
                         metric: str) -> Dict[str, Any]:
        """Perform bootstrap statistical analysis."""
        try:
            # This would need actual data points for proper bootstrap
            # For now, return simplified analysis
            return {
                'error': 'Bootstrap analysis requires individual data points'
            }
            
        except Exception as e:
            logger.error(f"Error in bootstrap analysis: {e}")
            return {'error': str(e)}
    
    def _determine_test_winner(self, test: RoutingABTest, 
                               statistical_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Determine the winner of an A/B test."""
        try:
            if 'error' in statistical_analysis:
                return None
            
            # Check if test has reached statistical significance
            has_significant_result = False
            best_variant = None
            best_lift = 0.0
            
            for variant_name, analysis in statistical_analysis.items():
                # Check if any statistical test shows significance
                for test_name, test_result in analysis['statistical_tests'].items():
                    if test_result.get('is_significant', False):
                        has_significant_result = True
                        
                        # Check if this is the best result
                        lift = analysis['lift']
                        if lift > best_lift:
                            best_lift = lift
                            best_variant = variant_name
                        break
            
            if not has_significant_result:
                return None
            
            # Create winner result
            return {
                'variant': best_variant,
                'lift': best_lift,
                'confidence': statistical_analysis[best_variant]['statistical_tests'].get('z_test', {}).get('confidence_level', 0.0),
                'determined_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error determining test winner: {e}")
            return None
    
    def _get_user_segments(self, user: User) -> List[str]:
        """Get user segments for targeting."""
        try:
            segments = []
            
            # Basic segments
            if getattr(user, 'is_premium', False):
                segments.append('premium')
            
            days_since_registration = (timezone.now() - user.date_joined).days
            if days_since_registration <= 30:
                segments.append('new_user')
            elif days_since_registration <= 90:
                segments.append('active_user')
            
            return segments
            
        except Exception as e:
            logger.error(f"Error getting user segments: {e}")
            return []
    
    def _update_assignment_stats(self, elapsed_ms: float):
        """Update assignment performance statistics."""
        self.ab_test_stats['total_assignments'] += 1
        
        # Update average time
        current_avg = self.ab_test_stats['avg_assignment_time_ms']
        total_assignments = self.ab_test_stats['total_assignments']
        self.ab_test_stats['avg_assignment_time_ms'] = (
            (current_avg * (total_assignments - 1) + elapsed_ms) / total_assignments
        )
    
    def get_ab_test_stats(self) -> Dict[str, Any]:
        """Get A/B test service statistics."""
        total_requests = self.ab_test_stats['total_assignments']
        cache_hit_rate = (
            self.ab_test_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_assignments': total_requests,
            'total_tests': self.ab_test_stats['total_tests'],
            'cache_hits': self.ab_test_stats['cache_hits'],
            'cache_misses': total_requests - self.ab_test_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.ab_test_stats['errors'],
            'error_rate': self.ab_test_stats['errors'] / max(1, total_requests),
            'avg_assignment_time_ms': self.ab_test_stats['avg_assignment_time_ms'],
            'supported_methods': list(self.statistical_methods.keys()),
            'supported_strategies': list(self.assignment_strategies.keys())
        }
    
    def clear_cache(self, user_id: int = None, test_id: int = None):
        """Clear A/B test cache."""
        try:
            if user_id:
                # Clear specific user cache
                cache_key = get_ab_test_key(user_id)
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared A/B test cache for user {user_id}")
            elif test_id:
                # Clear test-specific cache
                # This would need pattern deletion support
                logger.info(f"Cache clearing for test {test_id} not implemented")
            else:
                # Clear all A/B test cache
                logger.info("Cache clearing for all A/B tests not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing A/B test cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on A/B test service."""
        try:
            # Test user assignment
            test_user = User(id=1, username='test')
            test_context = {'device': {'type': 'mobile'}, 'location': {'country': 'US'}}
            
            assignment = self.assign_user_to_test(test_user, test_context)
            
            # Test statistical analysis
            test_performance = {
                'control': self._get_empty_performance_metrics(),
                'variant_a': self._get_empty_performance_metrics()
            }
            
            test_performance['variant_a']['conversion_rate'] = 0.05
            test_performance['variant_a']['user_count'] = 1000
            
            mock_test = type('MockTest', (), {
                'primary_metric': 'conversion_rate'
            })()
            
            statistical_analysis = self._calculate_statistical_analysis(mock_test, test_performance)
            
            return {
                'status': 'healthy',
                'test_user_assignment': assignment is not None,
                'test_statistical_analysis': 'error' not in statistical_analysis,
                'stats': self.get_ab_test_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
