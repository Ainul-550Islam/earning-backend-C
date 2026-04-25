"""
A/B Test Tasks

Periodic tasks for evaluating A/B tests
and declaring winners.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.ab_test import ABTestService
from ..services.analytics import analytics_service
from ..models import RoutingABTest, ABTestAssignment, ABTestResult
from ..constants import AB_TEST_EVALUATION_INTERVAL, AB_TEST_MIN_SAMPLE_SIZE, STATISTICAL_SIGNIFICANCE_LEVEL
from ..exceptions import ABTestError

logger = logging.getLogger(__name__)

User = get_user_model()


class ABTestTask:
    """
    Task for evaluating A/B tests.
    
    Runs periodically to:
    - Evaluate statistical significance
    - Declare test winners
    - Generate test reports
    - Archive completed tests
    - Update test assignments
    """
    
    def __init__(self):
        self.ab_test_service = ABTestService()
        self.analytics_service = analytics_service
        self.task_stats = {
            'total_evaluations': 0,
            'successful_evaluations': 0,
            'failed_evaluations': 0,
            'tests_completed': 0,
            'winners_declared': 0,
            'avg_evaluation_time_ms': 0.0
        }
    
    def run_ab_test_evaluation(self) -> Dict[str, Any]:
        """
        Run the A/B test evaluation task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get tests that need evaluation
            tests_to_evaluate = self._get_tests_needing_evaluation()
            
            if not tests_to_evaluate:
                logger.info("No A/B tests need evaluation")
                return {
                    'success': True,
                    'message': 'No A/B tests need evaluation',
                    'tests_evaluated': 0,
                    'execution_time_ms': 0,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Evaluate each test
            evaluated_tests = 0
            completed_tests = 0
            failed_tests = 0
            
            for test in tests_to_evaluate:
                try:
                    # Evaluate test
                    result = self._evaluate_test(test)
                    
                    if result['should_complete']:
                        self._complete_test(test, result)
                        completed_tests += 1
                    else:
                        logger.info(f"Test {test.id} needs more time: {result['reason']}")
                    
                    evaluated_tests += 1
                    
                except Exception as e:
                    failed_tests += 1
                    logger.error(f"Error evaluating test {test.id}: {e}")
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            return {
                'success': True,
                'message': 'A/B test evaluation task completed',
                'tests_evaluated': evaluated_tests,
                'tests_completed': completed_tests,
                'tests_failed': failed_tests,
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in A/B test evaluation task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_tests_needing_evaluation(self) -> List[RoutingABTest]:
        """Get A/B tests that need evaluation."""
        try:
            # Get tests that are active and have sufficient data
            cutoff_time = timezone.now() - timezone.timedelta(days=AB_TEST_EVALUATION_INTERVAL)
            
            tests = RoutingABTest.objects.filter(
                is_active=True,
                start_date__lte=cutoff_time,
                end_date__gte=timezone.now()
            ).filter(
                # Has sufficient sample size
                assignments__count__gte=AB_TEST_MIN_SAMPLE_SIZE
            ).order_by('created_at')
            
            logger.info(f"Found {len(tests)} A/B tests needing evaluation")
            return tests
            
        except Exception as e:
            logger.error(f"Error getting tests needing evaluation: {e}")
            return []
    
    def _evaluate_test(self, test: RoutingABTest) -> Dict[str, Any]:
        """Evaluate a specific A/B test."""
        try:
            # Get test results
            test_results = self.ab_test_service.get_test_results(test.id)
            
            if not test_results:
                return {
                    'should_complete': False,
                    'reason': 'No test results available'
                }
            
            # Check if test has run long enough
            test_duration = timezone.now() - test.start_date
            min_duration = timezone.timedelta(days=7)  # Minimum 7 days
            
            if test_duration < min_duration:
                return {
                    'should_complete': False,
                    'reason': f'Test has not run long enough (needs at least {min_duration.days} days)'
                }
            
            # Perform statistical analysis
            statistical_analysis = test_results.get('statistical_analysis', {})
            
            # Check for statistical significance
            is_significant = self._check_statistical_significance(statistical_analysis)
            
            if is_significant:
                # Determine winner
                winner = self._determine_winner(statistical_analysis)
                
                return {
                    'should_complete': True,
                    'reason': 'Statistical significance achieved',
                    'winner': winner,
                    'statistical_analysis': statistical_analysis,
                    'is_significant': True
                }
            else:
                return {
                    'should_complete': False,
                    'reason': 'Statistical significance not achieved',
                    'statistical_analysis': statistical_analysis,
                    'is_significant': False
                }
                
        except Exception as e:
            logger.error(f"Error evaluating test {test.id}: {e}")
            return {
                'should_complete': False,
                'reason': str(e)
            }
    
    def _check_statistical_significance(self, analysis: Dict[str, Any]) -> bool:
        """Check if test results are statistically significant."""
        try:
            # Get primary metric
            primary_metric = analysis.get('primary_metric', 'conversion_rate')
            
            if primary_metric not in analysis:
                return False
            
            metric_data = analysis[primary_metric]
            
            # Check p-value
            p_value = metric_data.get('p_value', 1.0)
            if p_value <= STATISTICAL_SIGNIFICANCE_LEVEL:
                return True
            
            # Check confidence interval
            confidence_level = metric_data.get('confidence_level', 0.0)
            if confidence_level >= (1 - STATISTICAL_SIGNIFICANCE_LEVEL):
                return True
            
            # Check effect size
            effect_size = metric_data.get('effect_size', 0.0)
            if abs(effect_size) >= 0.1:  # Minimum 10% effect
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking statistical significance: {e}")
            return False
    
    def _determine_winner(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the winner of an A/B test."""
        try:
            # Get primary metric
            primary_metric = analysis.get('primary_metric', 'conversion_rate')
            
            if primary_metric not in analysis:
                return {
                    'variant': None,
                    'confidence': 0.0,
                    'lift': 0.0
                }
            
            metric_data = analysis[primary_metric]
            
            # Get variant results
            control_metric = metric_data.get('control', {})
            variant_metrics = metric_data.get('variants', {})
            
            # Find winning variant
            winner = None
            best_metric = control_metric.get('value', 0.0)
            
            # Check control
            if control_metric.get('value', 0.0) > best_metric:
                best_metric = control_metric.get('value', 0.0)
                winner = {
                    'variant': 'control',
                    'metric_value': best_metric,
                    'confidence': control_metric.get('confidence', 0.0)
                }
            
            # Check variants
            for variant_name, variant_data in variant_metrics.items():
                variant_value = variant_data.get('value', 0.0)
                
                if variant_value > best_metric:
                    best_metric = variant_value
                    winner = {
                        'variant': variant_name,
                        'metric_value': best_metric,
                        'confidence': variant_data.get('confidence', 0.0)
                    }
            
            # Calculate lift
            if winner and winner['variant'] != 'control':
                control_value = control_metric.get('value', 0.0)
                lift = ((best_metric - control_value) / max(0.001, control_value)) * 100
                winner['lift'] = lift
            
            return winner or {
                'variant': None,
                'metric_value': 0.0,
                'confidence': 0.0,
                'lift': 0.0
            }
            
        except Exception as e:
            logger.error(f"Error determining winner: {e}")
            return {
                'variant': None,
                'metric_value': 0.0,
                'confidence': 0.0,
                'lift': 0.0
            }
    
    def _complete_test(self, test: RoutingABTest, evaluation_result: Dict[str, Any]):
        """Complete an A/B test."""
        try:
            with transaction.atomic():
                # Update test status
                test.is_active = False
                test.end_date = timezone.now()
                test.status = 'completed'
                
                # Create test result record
                ABTestResult.objects.create(
                    test=test,
                    winner=evaluation_result.get('winner', {}).get('variant'),
                    confidence_level=evaluation_result.get('winner', {}).get('confidence', 0.0),
                    lift=evaluation_result.get('winner', {}).get('lift', 0.0),
                    statistical_significance=evaluation_result.get('is_significant', False),
                    primary_metric=evaluation_result.get('statistical_analysis', {}).get('primary_metric', 'conversion_rate'),
                    results_data=evaluation_result.get('statistical_analysis', {}),
                    completed_at=timezone.now()
                )
                
                # Save test
                test.save()
                
                logger.info(f"Completed A/B test {test.id} with winner: {evaluation_result.get('winner', {}).get('variant')}")
                
        except Exception as e:
            logger.error(f"Error completing test {test.id}: {e}")
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_evaluations'] += 1
            self.task_stats['successful_evaluations'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_evaluation_time_ms']
            total_evaluations = self.task_stats['total_evaluations']
            self.task_stats['avg_evaluation_time_ms'] = (
                (current_avg * (total_evaluations - 1) + execution_time) / total_evaluations
            )
            
        except Exception as e:
            logger.error(f"Error updating task stats: {e}")
    
    def get_task_stats(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        return self.task_stats
    
    def reset_task_stats(self) -> bool:
        """Reset task statistics."""
        try:
            self.task_stats = {
                'total_evaluations': 0,
                'successful_evaluations': 0,
                'failed_evaluations': 0,
                'tests_completed': 0,
                'winners_declared': 0,
                'avg_evaluation_time_ms': 0.0
            }
            
            logger.info("Reset A/B test evaluation task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on A/B test evaluation task."""
        try:
            # Test A/B test service
            test_health = self.ab_test_service.health_check()
            
            # Test analytics service
            analytics_health = self.analytics_service.health_check()
            
            # Test evaluation functionality
            test_test = RoutingABTest.objects.filter(is_active=True).first()
            if not test_test:
                test_test = RoutingABTest.objects.first()
            
            if test_test:
                test_result = self._evaluate_test(test_test)
                
                return {
                    'status': 'healthy' if all([
                        test_health.get('status') == 'healthy',
                        analytics_health.get('status') == 'healthy',
                        test_result.get('should_complete', False)  # Should not complete without sufficient data
                    ]) else 'unhealthy',
                    'ab_test_service_health': test_health,
                    'analytics_service_health': analytics_health,
                    'evaluation_test': test_result,
                    'task_stats': self.task_stats,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'status': 'unhealthy',
                'error': 'No tests available for testing',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in A/B test evaluation task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


# Task instance
ab_test_task = ABTestTask()
