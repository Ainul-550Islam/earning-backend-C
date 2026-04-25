"""
A/B Test Tasks for Offer Routing System

This module contains background tasks for A/B testing,
including test evaluation, winner declaration, and analytics.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from ..services.ab_test import ab_test_service
from ..constants import MIN_AB_TEST_DURATION_HOURS, STATISTICAL_SIGNIFICANCE_THRESHOLD

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='offer_routing.tasks.ab_test.evaluate_active_tests')
def evaluate_active_tests(self):
    """
    Evaluate all active A/B tests for statistical significance.
    
    This task checks active tests and evaluates them
    to determine if they have reached statistical significance.
    """
    try:
        logger.info("Starting active A/B test evaluation")
        
        if not ab_test_service:
            logger.warning("A/B test service not available")
            return {'success': False, 'error': 'A/B test service not available'}
        
        # Evaluate active tests
        evaluated_count = ab_test_service.evaluate_active_tests()
        
        logger.info(f"Active A/B test evaluation completed: {evaluated_count} tests evaluated")
        return {
            'success': True,
            'evaluated_tests': evaluated_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Active A/B test evaluation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.ab_test.check_test_duration')
def check_test_duration(self):
    """
    Check if tests have exceeded maximum duration.
    
    This task checks if any tests have exceeded their
    maximum duration and stops them if necessary.
    """
    try:
        logger.info("Starting A/B test duration check")
        
        # Get active tests
        from ..models import RoutingABTest
        
        active_tests = RoutingABTest.objects.filter(
            is_active=True,
            started_at__isnull=False
        )
        
        stopped_tests = 0
        failed_checks = 0
        
        for test in active_tests:
            try:
                # Check if test has exceeded duration
                if test.duration_hours:
                    duration_elapsed = (timezone.now() - test.started_at).total_seconds() / 3600
                    
                    if duration_elapsed > test.duration_hours:
                        # Stop the test
                        success = ab_test_service.stop_test(test.id)
                        if success:
                            stopped_tests += 1
                            logger.info(f"Stopped test {test.id} due to duration limit")
                        else:
                            failed_checks += 1
                            logger.error(f"Failed to stop test {test.id}")
                
            except Exception as e:
                logger.error(f"Failed to check duration for test {test.id}: {e}")
                failed_checks += 1
        
        logger.info(f"A/B test duration check completed: {stopped_tests} stopped, {failed_checks} failed")
        return {
            'success': True,
            'stopped_tests': stopped_tests,
            'failed_checks': failed_checks,
            'active_tests_checked': active_tests.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"A/B test duration check failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.ab_test.update_test_assignments')
def update_test_assignments(self):
    """
    Update A/B test assignments and record events.
    
    This task processes recent routing decisions and updates
    test assignments with interaction data.
    """
    try:
        logger.info("Starting A/B test assignment update")
        
        # Get recent routing decisions with A/B test assignments
        from ..models import RoutingDecisionLog, ABTestAssignment
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_decisions = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date
        ).select_related('user', 'offer')
        
        updated_assignments = 0
        failed_updates = 0
        
        for decision in recent_decisions:
            try:
                # Check if this decision is part of an A/B test
                assignment = ABTestAssignment.objects.filter(
                    user=decision.user,
                    test__control_route=decision.offer
                ).first()
                
                if not assignment:
                    assignment = ABTestAssignment.objects.filter(
                        user=decision.user,
                        test__variant_route=decision.offer
                    ).first()
                
                if assignment:
                    # Update assignment based on decision
                    if decision.score > 80:  # Assume high score indicates conversion
                        assignment.conversions += 1
                        assignment.revenue += decision.score  # Use score as revenue proxy
                    elif decision.score > 50:  # Assume medium score indicates click
                        assignment.clicks += 1
                    
                    assignment.impressions += 1
                    assignment.save()
                    updated_assignments += 1
                
            except Exception as e:
                logger.error(f"Failed to update assignment for decision {decision.id}: {e}")
                failed_updates += 1
        
        logger.info(f"A/B test assignment update completed: {updated_assignments} updated, {failed_updates} failed")
        return {
            'success': True,
            'updated_assignments': updated_assignments,
            'failed_updates': failed_updates,
            'total_decisions': recent_decisions.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"A/B test assignment update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.ab_test.generate_test_reports')
def generate_test_reports(self):
    """
    Generate comprehensive A/B test reports.
    
    This task generates reports on A/B test performance,
    winner analysis, and recommendations.
    """
    try:
        logger.info("Starting A/B test report generation")
        
        # Get all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        generated_reports = 0
        failed_tenants = []
        
        for tenant in tenants:
            try:
                # Get A/B test analytics for this tenant
                analytics = ab_test_service.get_test_analytics(user_id=tenant.id, days=30)
                
                # Generate report data
                report_data = {
                    'tenant_id': tenant.id,
                    'generated_at': timezone.now().isoformat(),
                    'period_days': 30,
                    'test_stats': analytics.get('test_stats', {}),
                    'winner_distribution': analytics.get('winner_distribution', []),
                    'performance_metrics': analytics.get('performance_metrics', {})
                }
                
                # Store report (placeholder)
                # This would save the report to database or file
                
                generated_reports += 1
                
            except Exception as e:
                logger.error(f"Failed to generate A/B test report for tenant {tenant.id}: {e}")
                failed_tenants.append(tenant.id)
        
        logger.info(f"A/B test report generation completed: {generated_reports} reports generated, {len(failed_tenants)} failed")
        return {
            'success': True,
            'generated_reports': generated_reports,
            'failed_tenants': failed_tenants,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"A/B test report generation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.ab_test.cleanup_completed_tests')
def cleanup_completed_tests(self):
    """
    Clean up completed A/B test data.
    
    This task cleans up old test data and archives
    completed tests for storage optimization.
    """
    try:
        logger.info("Starting A/B test cleanup")
        
        from datetime import timedelta
        
        # Archive old completed tests
        from ..models import RoutingABTest
        
        cutoff_date = timezone.now() - timedelta(days=90)
        completed_tests = RoutingABTest.objects.filter(
            ended_at__lt=cutoff_date
        )
        
        archived_count = 0
        failed_archives = 0
        
        for test in completed_tests:
            try:
                # Archive test data (placeholder)
                # This would move test data to archive storage
                
                # Delete test and related data
                test.delete()
                archived_count += 1
                
            except Exception as e:
                logger.error(f"Failed to archive test {test.id}: {e}")
                failed_archives += 1
        
        logger.info(f"A/B test cleanup completed: {archived_count} archived, {failed_archives} failed")
        return {
            'success': True,
            'archived_tests': archived_count,
            'failed_archives': failed_archives,
            'total_completed_tests': completed_tests.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"A/B test cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.ab_test.optimize_test_configuration')
def optimize_test_configuration(self):
    """
    Optimize A/B test configurations based on performance.
    
    This task analyzes test performance and suggests
    optimizations for future tests.
    """
    try:
        logger.info("Starting A/B test configuration optimization")
        
        # Get test results for analysis
        from ..models import ABTestResult
        
        results = ABTestResult.objects.filter(
            analyzed_at__gte=timezone.now() - timedelta(days=30)
        )
        
        optimizations = []
        
        # Analyze test performance
        if results.exists():
            # Calculate average confidence levels
            avg_confidence = results.aggregate(
                avg_confidence=Avg('winner_confidence')
            )['avg_confidence'] or 0
            
            # Calculate average effect sizes
            avg_effect_size = results.aggregate(
                avg_effect_size=Avg('effect_size')
            )['avg_effect_size'] or 0
            
            # Generate optimization recommendations
            if avg_confidence < STATISTICAL_SIGNIFICANCE_THRESHOLD:
                optimizations.append({
                    'type': 'increase_sample_size',
                    'message': f'Low average confidence ({avg_confidence:.2f}) - consider increasing sample size',
                    'recommendation': 'Increase minimum sample size for better statistical significance'
                })
            
            if avg_effect_size < 0.05:
                optimizations.append({
                    'type': 'improve_test_design',
                    'message': f'Low average effect size ({avg_effect_size:.3f}) - consider improving test design',
                    'recommendation': 'Create more significant variations between control and variant'
                })
            
            # Analyze winner distribution
            winner_stats = results.values('winner').annotate(
                count=Count('id')
            )
            
            if winner_stats:
                total_results = results.count()
                control_wins = winner_stats.filter(winner='control').aggregate(
                    count=Count('id')
                )['count'] or 0
                
                variant_wins = winner_stats.filter(winner='variant').aggregate(
                    count=Count('id')
                )['count'] or 0
                
                if control_wins > variant_wins * 2:
                    optimizations.append({
                        'type': 'variant_improvement',
                        'message': f'Control wins significantly more often ({control_wins} vs {variant_wins})',
                        'recommendation': 'Focus on improving variant designs or test different variations'
                    })
        
        logger.info(f"A/B test configuration optimization completed: {len(optimizations)} optimizations suggested")
        return {
            'success': True,
            'optimizations': optimizations,
            'results_analyzed': results.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"A/B test configuration optimization failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.ab_test.update_test_metrics')
def update_test_metrics(self):
    """
    Update A/B test metrics for monitoring.
    
    This task updates metrics tables for A/B test
    monitoring and analytics.
    """
    try:
        logger.info("Starting A/B test metrics update")
        
        # Get current test metrics
        from ..models import RoutingABTest, ABTestAssignment, ABTestResult
        
        # Update test statistics
        active_tests = RoutingABTest.objects.filter(is_active=True)
        
        test_metrics = {
            'total_tests': RoutingABTest.objects.count(),
            'active_tests': active_tests.count(),
            'completed_tests': RoutingABTest.objects.filter(ended_at__isnull=False).count(),
            'tests_with_winners': RoutingABTest.objects.filter(winner__isnull=False).count()
        }
        
        # Update assignment statistics
        assignment_metrics = {
            'total_assignments': ABTestAssignment.objects.count(),
            'control_assignments': ABTestAssignment.objects.filter(variant='control').count(),
            'variant_assignments': ABTestAssignment.objects.filter(variant='variant').count(),
            'total_impressions': ABTestAssignment.objects.aggregate(
                total=Sum('impressions')
            )['total'] or 0,
            'total_conversions': ABTestAssignment.objects.aggregate(
                total=Sum('conversions')
            )['total'] or 0
        }
        
        # Update result statistics
        result_metrics = {
            'total_results': ABTestResult.objects.count(),
            'significant_results': ABTestResult.objects.filter(is_significant=True).count(),
            'avg_confidence': ABTestResult.objects.aggregate(
                avg=Avg('winner_confidence')
            )['avg'] or 0,
            'avg_effect_size': ABTestResult.objects.aggregate(
                avg=Avg('effect_size')
            )['avg'] or 0
        }
        
        # Store metrics (placeholder)
        # This would save the metrics to database or cache
        
        logger.info("A/B test metrics update completed")
        return {
            'success': True,
            'test_metrics': test_metrics,
            'assignment_metrics': assignment_metrics,
            'result_metrics': result_metrics,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"A/B test metrics update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.ab_test.check_test_health')
def check_test_health(self):
    """
    Check health of A/B test configurations.
    
    This task validates test configurations and checks
    for potential issues.
    """
    try:
        logger.info("Starting A/B test health check")
        
        # Get all tests
        from ..models import RoutingABTest
        
        tests = RoutingABTest.objects.all()
        
        health_issues = []
        
        for test in tests:
            try:
                # Check for tests without control or variant
                if not test.control_route or not test.variant_route:
                    health_issues.append({
                        'type': 'missing_routes',
                        'test_id': test.id,
                        'message': f"Test {test.id} missing control or variant route"
                    })
                
                # Check for invalid split percentage
                if test.split_percentage < 1 or test.split_percentage > 99:
                    health_issues.append({
                        'type': 'invalid_split',
                        'test_id': test.id,
                        'message': f"Test {test.id} has invalid split percentage: {test.split_percentage}"
                    })
                
                # Check for very low minimum sample size
                if test.min_sample_size < 100:
                    health_issues.append({
                        'type': 'low_sample_size',
                        'test_id': test.id,
                        'message': f"Test {test.id} has very low minimum sample size: {test.min_sample_size}"
                    })
                
                # Check for tests running too long without results
                if test.is_active and test.started_at:
                    duration_hours = (timezone.now() - test.started_at).total_seconds() / 3600
                    if duration_hours > test.duration_hours * 2:
                        health_issues.append({
                            'type': 'long_running_test',
                            'test_id': test.id,
                            'message': f"Test {test.id} running for {duration_hours:.1f} hours (duration: {test.duration_hours})"
                        })
                
            except Exception as e:
                logger.error(f"Failed to check health for test {test.id}: {e}")
        
        logger.info(f"A/B test health check completed: {len(health_issues)} issues found")
        return {
            'success': True,
            'health_issues': health_issues,
            'total_tests': tests.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"A/B test health check failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
