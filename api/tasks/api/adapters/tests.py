"""
api/adapters/tests.py
Tests adapter for earning backend platform
"""
from django.db.models import Q
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_test_suites(request):
    """Get available test suites."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        category = request.GET.get('category')  # 'all', 'api', 'ui', 'integration', 'performance'
        status = request.GET.get('status')  # 'all', 'active', 'archived'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get test suites
        from tests.models import TestSuite
        queryset = TestSuite.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if category and category != 'all':
            queryset = queryset.filter(category=category)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        # Paginate
        test_suites = queryset[offset:offset+limit]
        
        # Serialize test suites
        suite_data = []
        for suite in test_suites:
            suite_data.append({
                'id': suite.id,
                'name': suite.name,
                'description': suite.description,
                'category': suite.category,
                'status': suite.status,
                'created_at': suite.created_at.isoformat(),
                'updated_at': suite.updated_at.isoformat() if suite.updated_at else None,
                'test_count': suite.test_count,
                'pass_rate': suite.pass_rate,
                'last_run_at': suite.last_run_at.isoformat() if suite.last_run_at else None,
                'last_run_status': suite.last_run_status,
                'created_by': {
                    'id': suite.created_by.id,
                    'username': suite.created_by.username,
                    'first_name': suite.created_by.first_name,
                    'last_name': suite.created_by.last_name,
                } if suite.created_by else None,
                'metadata': suite.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'test_suites': suite_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(suite_data) == limit
                },
                'filters': {
                    'category': category,
                    'status': status
                },
                'summary': _get_test_suite_summary(queryset)
            },
            'message': 'Test suites retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TestsAdapter] Error getting test suites: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve test suites',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_test_suite_details(request, suite_id):
    """Get detailed test suite information."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get test suite
        from tests.models import TestSuite
        try:
            suite = TestSuite.objects.get(
                id=suite_id,
                tenant_id=tenant_id
            )
        except TestSuite.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test suite not found',
                'details': f'Test suite with ID {suite_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get test cases
        from tests.models import TestCase
        test_cases = TestCase.objects.filter(
            test_suite=suite
        ).order_by('order', 'name')
        
        # Get recent test runs
        from tests.models import TestRun
        recent_runs = TestRun.objects.filter(
            test_suite=suite
        ).order_by('-created_at')[:10]
        
        # Build detailed suite data
        suite_data = {
            'id': suite.id,
            'name': suite.name,
            'description': suite.description,
            'category': suite.category,
            'status': suite.status,
            'created_at': suite.created_at.isoformat(),
            'updated_at': suite.updated_at.isoformat() if suite.updated_at else None,
            'test_count': suite.test_count,
            'pass_rate': suite.pass_rate,
            'last_run_at': suite.last_run_at.isoformat() if suite.last_run_at else None,
            'last_run_status': suite.last_run_status,
            'created_by': {
                'id': suite.created_by.id,
                'username': suite.created_by.username,
                'first_name': suite.created_by.first_name,
                'last_name': suite.created_by.last_name,
            } if suite.created_by else None,
            'configuration': suite.configuration,
            'environment': suite.environment,
            'test_cases': [
                {
                    'id': test_case.id,
                    'name': test_case.name,
                    'description': test_case.description,
                    'test_type': test_case.test_type,
                    'priority': test_case.priority,
                    'status': test_case.status,
                    'order': test_case.order,
                    'dependencies': test_case.dependencies,
                    'estimated_duration_ms': test_case.estimated_duration_ms,
                    'tags': test_case.tags,
                    'metadata': test_case.metadata
                }
                for test_case in test_cases
            ],
            'recent_runs': [
                {
                    'id': run.id,
                    'status': run.status,
                    'created_at': run.created_at.isoformat(),
                    'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                    'duration_ms': run.duration_ms,
                    'passed_tests': run.passed_tests,
                    'failed_tests': run.failed_tests,
                    'skipped_tests': run.skipped_tests,
                    'total_tests': run.total_tests,
                    'pass_rate': run.pass_rate,
                    'triggered_by': {
                        'id': run.triggered_by.id,
                        'username': run.triggered_by.username,
                    } if run.triggered_by else None,
                    'environment': run.environment,
                    'configuration': run.configuration
                }
                for run in recent_runs
            ],
            'statistics': _get_suite_statistics(suite, tenant_id),
            'can_run': _can_run_test_suite(user, suite),
            'next_run_time': _get_next_run_time(suite)
        }
        
        return Response({
            'success': True,
            'data': suite_data,
            'message': 'Test suite details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TestsAdapter] Error getting test suite details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve test suite details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def run_test_suite(request, suite_id):
    """Run a test suite."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get test suite
        from tests.models import TestSuite
        try:
            suite = TestSuite.objects.get(
                id=suite_id,
                tenant_id=tenant_id
            )
        except TestSuite.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test suite not found',
                'details': f'Test suite with ID {suite_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user can run test suite
        if not _can_run_test_suite(user, suite):
            return Response({
                'success': False,
                'error': 'Cannot run test suite',
                'details': 'You do not have permission to run this test suite'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if test suite is already running
        if _is_test_suite_running(suite, tenant_id):
            return Response({
                'success': False,
                'error': 'Test suite already running',
                'details': 'This test suite is currently running'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create test run
        from tests.models import TestRun
        test_run = TestRun.objects.create(
            test_suite=suite,
            triggered_by=user,
            status='running',
            environment=data.get('environment', suite.environment),
            configuration=data.get('configuration', suite.configuration),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Start test execution (async)
        _execute_test_suite_async(test_run, suite, user, tenant_id)
        
        # Emit test run started event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('tests.test_run_started', {
            'user_id': user.id,
            'suite_id': suite_id,
            'test_run_id': test_run.id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'test_run_id': test_run.id,
                'suite_id': suite_id,
                'status': 'running',
                'started_at': test_run.created_at.isoformat(),
                'environment': test_run.environment,
                'estimated_duration_ms': suite.estimated_duration_ms,
                'test_count': suite.test_count,
                'progress_url': f'/api/tests/test_runs/{test_run.id}/progress/'
            },
            'message': 'Test suite execution started successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[TestsAdapter] Error running test suite: {e}")
        return Response({
            'success': False,
            'error': 'Failed to run test suite',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_test_run_progress(request, run_id):
    """Get test run progress."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get test run
        from tests.models import TestRun
        try:
            test_run = TestRun.objects.get(
                id=run_id,
                tenant_id=tenant_id
            )
        except TestRun.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test run not found',
                'details': f'Test run with ID {run_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get test results
        from tests.models import TestResult
        test_results = TestResult.objects.filter(
            test_run=test_run
        ).order_by('created_at')
        
        # Calculate progress
        progress_data = {
            'test_run_id': run_id,
            'suite_id': test_run.test_suite.id,
            'suite_name': test_run.test_suite.name,
            'status': test_run.status,
            'started_at': test_run.created_at.isoformat(),
            'completed_at': test_run.completed_at.isoformat() if test_run.completed_at else None,
            'duration_ms': test_run.duration_ms,
            'progress': {
                'total_tests': test_run.total_tests,
                'completed_tests': test_results.count(),
                'passed_tests': test_run.passed_tests,
                'failed_tests': test_run.failed_tests,
                'skipped_tests': test_run.skipped_tests,
                'running_tests': test_results.filter(status='running').count(),
                'percentage': round((test_results.count() / max(test_run.total_tests, 1)) * 100, 2),
                'estimated_completion': _get_estimated_completion(test_run, test_results.count())
            },
            'test_results': [
                {
                    'id': result.id,
                    'test_case_id': result.test_case.id,
                    'test_case_name': result.test_case.name,
                    'status': result.status,
                    'started_at': result.started_at.isoformat() if result.started_at else None,
                    'completed_at': result.completed_at.isoformat() if result.completed_at else None,
                    'duration_ms': result.duration_ms,
                    'error_message': result.error_message,
                    'assertions': result.assertions,
                    'logs': result.logs,
                    'attachments': result.attachments,
                    'metadata': result.metadata
                }
                for result in test_results
            ],
            'environment': test_run.environment,
            'configuration': test_run.configuration,
            'performance_metrics': _get_run_performance_metrics(test_run, test_results)
        }
        
        return Response({
            'success': True,
            'data': progress_data,
            'message': 'Test run progress retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TestsAdapter] Error getting test run progress: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve test run progress',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_test_history(request):
    """Get user's test history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        suite_id = request.GET.get('suite_id')
        status = request.GET.get('status')  # 'all', 'running', 'completed', 'failed', 'cancelled'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get test runs
        from tests.models import TestRun
        queryset = TestRun.objects.filter(
            triggered_by=user,
            tenant_id=tenant_id
        ).select_related('test_suite').order_by('-created_at')
        
        # Apply filters
        if suite_id:
            queryset = queryset.filter(test_suite_id=suite_id)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        # Paginate
        test_runs = queryset[offset:offset+limit]
        
        # Serialize test runs
        run_data = []
        for run in test_runs:
            run_data.append({
                'id': run.id,
                'test_suite': {
                    'id': run.test_suite.id,
                    'name': run.test_suite.name,
                    'category': run.test_suite.category,
                },
                'status': run.status,
                'created_at': run.created_at.isoformat(),
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'duration_ms': run.duration_ms,
                'passed_tests': run.passed_tests,
                'failed_tests': run.failed_tests,
                'skipped_tests': run.skipped_tests,
                'total_tests': run.total_tests,
                'pass_rate': run.pass_rate,
                'environment': run.environment,
                'configuration': run.configuration,
                'triggered_by': {
                    'id': run.triggered_by.id,
                    'username': run.triggered_by.username,
                },
                'metadata': run.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'test_runs': run_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(run_data) == limit
                },
                'filters': {
                    'suite_id': suite_id,
                    'status': status
                },
                'summary': _get_test_history_summary(queryset)
            },
            'message': 'Test history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TestsAdapter] Error getting test history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve test history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_test_analytics(request):
    """Get test analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get test analytics
        from tests.models import TestSuite, TestRun, TestResult
        test_suites = TestSuite.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        test_runs = TestRun.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('test_suite', 'triggered_by')
        
        test_results = TestResult.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('test_case', 'test_run')
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'suite_metrics': {
                'total_suites': test_suites.count(),
                'active_suites': test_suites.filter(status='active').count(),
                'category_distribution': list(test_suites.values('category').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'average_test_count': test_suites.aggregate(
                    avg_tests=Avg(F('test_count'))
                )['avg_tests'] or 0,
                'average_pass_rate': test_suites.aggregate(
                    avg_pass_rate=Avg(F('pass_rate'))
                )['avg_pass_rate'] or 0,
                'total_tests': test_suites.aggregate(
                    total=Sum(F('test_count'))
                )['total'] or 0
            },
            'run_metrics': {
                'total_runs': test_runs.count(),
                'completed_runs': test_runs.filter(status='completed').count(),
                'failed_runs': test_runs.filter(status='failed').count(),
                'running_runs': test_runs.filter(status='running').count(),
                'success_rate': round((test_runs.filter(status='completed').count() / max(test_runs.count(), 1)) * 100, 2),
                'average_duration_ms': test_runs.filter(
                    status='completed'
                ).aggregate(
                    avg_duration=Avg(F('duration_ms'))
                )['avg_duration'] or 0,
                'total_test_executions': test_runs.aggregate(
                    total=Sum(F('total_tests'))
                )['total'] or 0,
                'total_passes': test_runs.aggregate(
                    total=Sum(F('passed_tests'))
                )['total'] or 0,
                'total_failures': test_runs.aggregate(
                    total=Sum(F('failed_tests'))
                )['total'] or 0,
                'daily_trends': _get_test_run_trends(test_runs, days),
                'top_performers': _get_top_test_performers(test_runs, days),
                'most_run_suites': _get_most_run_suites(test_runs, days)
            },
            'result_metrics': {
                'total_results': test_results.count(),
                'passed_results': test_results.filter(status='passed').count(),
                'failed_results': test_results.filter(status='failed').count(),
                'skipped_results': test_results.filter(status='skipped').count(),
                'average_result_duration': test_results.aggregate(
                    avg_duration=Avg(F('duration_ms'))
                )['avg_duration'] or 0,
                'failure_rate': round((test_results.filter(status='failed').count() / max(test_results.count(), 1)) * 100, 2),
                'test_types': list(test_results.values('test_case__test_type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'priority_distribution': list(test_results.values('test_case__priority').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'common_failures': _get_common_failure_patterns(test_results),
                'performance_issues': _get_performance_issues(test_results)
            },
            'environment_metrics': {
                'environments': list(test_runs.values('environment').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'environment_success_rates': list(test_runs.values('environment').annotate(
                    total=Count('id'),
                    passes=Count('id', filter=Q(status='completed'))
                ).annotate(
                    success_rate=Avg(F('passes')) * 100
                ).order_by('-count')),
                'environment_performance': list(test_runs.values('environment').annotate(
                    avg_duration=Avg(F('duration_ms'))
                ).order_by('avg_duration'))
            },
            'quality_metrics': {
                'code_coverage': _get_code_coverage_metrics(tenant_id, start_date),
                'test_reliability': _get_test_reliability_score(test_runs),
                'automation_score': _get_automation_score(test_suites),
                'maintenance_score': _get_maintenance_score(test_suites),
                'quality_trends': _get_quality_trends(test_runs, days)
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Test analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TestsAdapter] Error getting test analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve test analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def schedule_test_run(request):
    """Schedule a test run."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['suite_id', 'schedule_time', 'schedule_type']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get test suite
        from tests.models import TestSuite
        try:
            suite = TestSuite.objects.get(
                id=data['suite_id'],
                tenant_id=tenant_id
            )
        except TestSuite.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test suite not found',
                'details': f'Test suite with ID {data["suite_id"]} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create scheduled test run
        from tests.models import ScheduledTestRun
        scheduled_run = ScheduledTestRun.objects.create(
            test_suite=suite,
            scheduled_by=user,
            schedule_time=data['schedule_time'],
            schedule_type=data['schedule_type'],  # 'once', 'daily', 'weekly', 'monthly'
            environment=data.get('environment', suite.environment),
            configuration=data.get('configuration', suite.configuration),
            is_active=True,
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Emit test run scheduled event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('tests.test_run_scheduled', {
            'user_id': user.id,
            'suite_id': data['suite_id'],
            'scheduled_run_id': scheduled_run.id,
            'schedule_time': data['schedule_time'],
            'schedule_type': data['schedule_type'],
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'scheduled_run_id': scheduled_run.id,
                'suite_id': data['suite_id'],
                'suite_name': suite.name,
                'schedule_time': data['schedule_time'],
                'schedule_type': data['schedule_type'],
                'environment': scheduled_run.environment,
                'is_active': scheduled_run.is_active,
                'created_at': scheduled_run.created_at.isoformat(),
                'next_run_time': _get_next_scheduled_run_time(scheduled_run)
            },
            'message': 'Test run scheduled successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[TestsAdapter] Error scheduling test run: {e}")
        return Response({
            'success': False,
            'error': 'Failed to schedule test run',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_test_suite_summary(queryset) -> Dict:
    """Get test suite summary statistics."""
    try:
        total_suites = queryset.count()
        active_suites = queryset.filter(status='active').count()
        
        return {
            'total_suites': total_suites,
            'active_suites': active_suites,
            'inactive_suites': queryset.filter(status='inactive').count(),
            'total_tests': queryset.aggregate(
                total=Sum(F('test_count'))
            )['total'] or 0,
            'average_pass_rate': queryset.aggregate(
                avg_pass_rate=Avg(F('pass_rate'))
            )['avg_pass_rate'] or 0,
            'categories': list(queryset.values('category').annotate(
                count=Count('id')
            ).order_by('-count'))
        }
    except Exception:
        return {}


def _can_run_test_suite(user, suite) -> bool:
    """Check if user can run test suite."""
    try:
        # Admin users can run all suites
        if user.is_staff:
            return True
        
        # Check user permissions
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if ctx.user_level >= 3:
            return True
        
        # Check if user has specific permission
        if suite.category == 'api' and ctx.user_level >= 2:
            return True
        
        return False
    except Exception:
        return False


def _is_test_suite_running(suite, tenant_id) -> bool:
    """Check if test suite is currently running."""
    try:
        from tests.models import TestRun
        return TestRun.objects.filter(
            test_suite=suite,
            tenant_id=tenant_id,
            status='running'
        ).exists()
    except Exception:
        return False


def _execute_test_suite_async(test_run, suite, user, tenant_id):
    """Execute test suite asynchronously."""
    try:
        # In real implementation, this would use Celery or similar
        # For now, simulate async execution
        import threading
        
        def execute_tests():
            try:
                # Simulate test execution
                import time
                time.sleep(2)  # Simulate 2 second execution
                
                # Update test run status
                test_run.status = 'completed'
                test_run.completed_at = timezone.now()
                test_run.duration_ms = 2000
                test_run.passed_tests = int(suite.test_count * 0.85)
                test_run.failed_tests = int(suite.test_count * 0.15)
                test_run.total_tests = suite.test_count
                test_run.pass_rate = 85.0
                test_run.save()
                
                # Create test results
                _create_test_results(test_run, suite, tenant_id)
                
                # Update suite statistics
                suite.last_run_at = test_run.completed_at
                suite.last_run_status = test_run.status
                suite.pass_rate = test_run.pass_rate
                suite.save()
                
            except Exception as e:
                logger.error(f"Error executing test suite: {e}")
                test_run.status = 'failed'
                test_run.completed_at = timezone.now()
                test_run.save()
        
        # Start execution in background
        thread = threading.Thread(target=execute_tests)
        thread.daemon = True
        thread.start()
        
    except Exception:
        pass


def _create_test_results(test_run, suite, tenant_id):
    """Create test results for test run."""
    try:
        from tests.models import TestCase, TestResult
        
        test_cases = TestCase.objects.filter(test_suite=suite)
        
        for i, test_case in enumerate(test_cases):
            # Simulate test result
            import random
            status = 'passed' if random.random() > 0.15 else 'failed'
            
            TestResult.objects.create(
                test_run=test_run,
                test_case=test_case,
                status=status,
                started_at=test_run.created_at,
                completed_at=test_run.completed_at,
                duration_ms=random.randint(100, 2000),
                error_message='Test assertion failed' if status == 'failed' else None,
                assertions={'passed': random.randint(5, 10), 'failed': 0 if status == 'passed' else 1},
                logs=[f'Test case {test_case.name} execution log'],
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
    except Exception:
        pass


def _get_suite_statistics(suite, tenant_id) -> Dict:
    """Get suite statistics."""
    try:
        from tests.models import TestRun
        runs = TestRun.objects.filter(
            test_suite=suite,
            tenant_id=tenant_id
        )
        
        return {
            'total_runs': runs.count(),
            'completed_runs': runs.filter(status='completed').count(),
            'failed_runs': runs.filter(status='failed').count(),
            'success_rate': round((runs.filter(status='completed').count() / max(runs.count(), 1)) * 100, 2),
            'average_duration_ms': runs.filter(
                status='completed'
            ).aggregate(
                avg_duration=Avg(F('duration_ms'))
            )['avg_duration'] or 0,
            'last_run_at': runs.order_by('-created_at').first().created_at.isoformat() if runs.exists() else None,
            'best_run': runs.filter(status='completed').order_by('-pass_rate').first().pass_rate if runs.filter(status='completed').exists() else 0
        }
    except Exception:
        return {}


def _get_next_run_time(suite) -> Optional[str]:
    """Get next scheduled run time."""
    try:
        # In real implementation, this would check scheduled runs
        # For now, return None
        return None
    except Exception:
        return None


def _get_estimated_completion(test_run, completed_tests) -> Optional[str]:
    """Get estimated completion time."""
    try:
        if test_run.status == 'completed':
            return None
        
        if completed_tests == 0:
            return None
        
        # Calculate average time per test
        if test_run.total_tests > 0:
            avg_time_per_test = 2000  # 2 seconds per test
            remaining_tests = test_run.total_tests - completed_tests
            estimated_remaining_ms = remaining_tests * avg_time_per_test
            estimated_completion = timezone.now() + timedelta(milliseconds=estimated_remaining_ms)
            return estimated_completion.isoformat()
        
        return None
    except Exception:
        return None


def _get_run_performance_metrics(test_run, test_results) -> Dict:
    """Get performance metrics for test run."""
    try:
        return {
            'average_test_duration': test_results.aggregate(
                avg_duration=Avg(F('duration_ms'))
            )['avg_duration'] or 0,
            'slowest_test': test_results.order_by('-duration_ms').first().duration_ms if test_results.exists() else 0,
            'fastest_test': test_results.order_by('duration_ms').first().duration_ms if test_results.exists() else 0,
            'memory_usage_mb': 125.5,  # Simulated
            'cpu_usage_percentage': 45.2,  # Simulated
            'network_requests': 150,  # Simulated
            'database_queries': 75  # Simulated
        }
    except Exception:
        return {}


def _get_test_history_summary(queryset) -> Dict:
    """Get test history summary statistics."""
    try:
        total_runs = queryset.count()
        completed_runs = queryset.filter(status='completed').count()
        failed_runs = queryset.filter(status='failed').count()
        
        return {
            'total_runs': total_runs,
            'completed_runs': completed_runs,
            'failed_runs': failed_runs,
            'success_rate': round((completed_runs / max(total_runs, 1)) * 100, 2),
            'average_duration_ms': queryset.filter(
                status='completed'
            ).aggregate(
                avg_duration=Avg(F('duration_ms'))
            )['avg_duration'] or 0,
            'total_tests_executed': queryset.aggregate(
                total=Sum(F('total_tests'))
            )['total'] or 0,
            'total_passes': queryset.aggregate(
                total=Sum(F('passed_tests'))
            )['total'] or 0,
            'total_failures': queryset.aggregate(
                total=Sum(F('failed_tests'))
            )['total'] or 0
        }
    except Exception:
        return {}


def _get_test_run_trends(test_runs, days) -> List[Dict]:
    """Get test run trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = test_runs.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            failed=Count('id', filter=Q(status='failed'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_runs': trend['total'],
                'completed_runs': trend['completed'],
                'failed_runs': trend['failed'],
                'success_rate': round((trend['completed'] / max(trend['total'], 1)) * 100, 2)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_top_test_performers(test_runs, days) -> List[Dict]:
    """Get top test performers."""
    try:
        performers = test_runs.filter(
            status='completed'
        ).values(
            'triggered_by__username',
            'triggered_by__first_name',
            'triggered_by__last_name'
        ).annotate(
            run_count=Count('id'),
            total_passes=Sum(F('passed_tests')),
            average_pass_rate=Avg(F('pass_rate'))
        ).order_by('-average_pass_rate')[:10]
        
        return [
            {
                'username': performer['triggered_by__username'],
                'name': f"{performer['triggered_by__first_name']} {performer['triggered_by__last_name']}".strip(),
                'run_count': performer['run_count'],
                'total_passes': performer['total_passes'],
                'average_pass_rate': performer['average_pass_rate']
            }
            for performer in performers
        ]
    except Exception:
        return []


def _get_most_run_suites(test_runs, days) -> List[Dict]:
    """Get most run test suites."""
    try:
        suites = test_runs.values(
            'test_suite__name',
            'test_suite__category'
        ).annotate(
            run_count=Count('id'),
            success_rate=Avg(F('pass_rate'))
        ).order_by('-run_count')[:10]
        
        return [
            {
                'suite_name': suite['test_suite__name'],
                'category': suite['test_suite__category'],
                'run_count': suite['run_count'],
                'success_rate': suite['success_rate']
            }
            for suite in suites
        ]
    except Exception:
        return []


def _get_common_failure_patterns(test_results) -> List[Dict]:
    """Get common failure patterns."""
    try:
        failures = test_results.filter(status='failed')
        
        patterns = []
        
        # Group by error message
        error_patterns = failures.values('error_message').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        for pattern in error_patterns:
            patterns.append({
                'error_message': pattern['error_message'],
                'count': pattern['count'],
                'percentage': round((pattern['count'] / max(failures.count(), 1)) * 100, 2)
            })
        
        return patterns
    except Exception:
        return []


def _get_performance_issues(test_results) -> List[Dict]:
    """Get performance issues."""
    try:
        # Get slow tests
        slow_tests = test_results.filter(
            duration_ms__gt=5000
        ).order_by('-duration_ms')[:10]
        
        issues = []
        for test in slow_tests:
            issues.append({
                'test_case_name': test.test_case.name,
                'duration_ms': test.duration_ms,
                'issue_type': 'slow_execution',
                'severity': 'medium' if test.duration_ms < 10000 else 'high'
            })
        
        return issues
    except Exception:
        return []


def _get_code_coverage_metrics(tenant_id, start_date) -> Dict:
    """Get code coverage metrics."""
    try:
        # In real implementation, this would integrate with coverage tools
        return {
            'line_coverage': 78.5,
            'branch_coverage': 65.2,
            'function_coverage': 82.1,
            'statement_coverage': 79.8,
            'overall_coverage': 76.4,
            'trend': 'improving',
            'last_updated': timezone.now().isoformat()
        }
    except Exception:
        return {}


def _get_test_reliability_score(test_runs) -> float:
    """Get test reliability score."""
    try:
        total_runs = test_runs.count()
        completed_runs = test_runs.filter(status='completed').count()
        
        if total_runs == 0:
            return 0
        
        # Calculate reliability score (0-100)
        reliability = (completed_runs / total_runs) * 100
        
        # Factor in pass rates
        avg_pass_rate = test_runs.filter(status='completed').aggregate(
            avg_rate=Avg(F('pass_rate'))
        )['avg_rate'] or 0
        
        final_score = (reliability * 0.7) + (avg_pass_rate * 0.3)
        
        return round(final_score, 2)
    except Exception:
        return 0


def _get_automation_score(test_suites) -> float:
    """Get automation score."""
    try:
        total_suites = test_suites.count()
        automated_suites = test_suites.filter(
            category__in=['api', 'integration']
        ).count()
        
        if total_suites == 0:
            return 0
        
        return round((automated_suites / total_suites) * 100, 2)
    except Exception:
        return 0


def _get_maintenance_score(test_suites) -> float:
    """Get maintenance score."""
    try:
        # Calculate based on recent activity and pass rates
        recent_suites = test_suites.filter(
            last_run_at__gte=timezone.now() - timedelta(days=30)
        )
        
        if test_suites.count() == 0:
            return 0
        
        recent_activity_rate = (recent_suites.count() / test_suites.count()) * 100
        avg_pass_rate = test_suites.aggregate(
            avg_rate=Avg(F('pass_rate'))
        )['avg_rate'] or 0
        
        maintenance_score = (recent_activity_rate * 0.6) + (avg_pass_rate * 0.4)
        
        return round(maintenance_score, 2)
    except Exception:
        return 0


def _get_quality_trends(test_runs, days) -> List[Dict]:
    """Get quality trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = test_runs.filter(
            created_at__gte=start_date,
            status='completed'
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            avg_pass_rate=Avg(F('pass_rate')),
            avg_duration=Avg(F('duration_ms')),
            total_runs=Count('id')
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'average_pass_rate': trend['avg_pass_rate'] or 0,
                'average_duration_ms': trend['avg_duration_ms'] or 0,
                'total_runs': trend['total_runs']
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_next_scheduled_run_time(scheduled_run) -> str:
    """Get next scheduled run time."""
    try:
        if scheduled_run.schedule_type == 'once':
            return scheduled_run.schedule_time.isoformat()
        elif scheduled_run.schedule_type == 'daily':
            return scheduled_run.schedule_time.isoformat()  # Simplified
        elif scheduled_run.schedule_type == 'weekly':
            return scheduled_run.schedule_time.isoformat()  # Simplified
        elif scheduled_run.schedule_type == 'monthly':
            return scheduled_run.schedule_time.isoformat()  # Simplified
        else:
            return scheduled_run.schedule_time.isoformat()
    except Exception:
        return scheduled_run.schedule_time.isoformat()
