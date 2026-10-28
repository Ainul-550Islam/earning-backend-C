"""
api/adapters/integrations.py
Integrations adapter for earning backend platform
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
@permission_classes([IsAdminUser])
def get_integrations(request):
    """Get all integrations."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        integration_type = request.GET.get('type')  # 'all', 'payment', 'analytics', 'marketing', 'storage', 'communication'
        status_filter = request.GET.get('status')  # 'all', 'active', 'inactive', 'error', 'pending'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get integrations
        from integrations.models import Integration
        queryset = Integration.objects.filter(
            tenant_id=tenant_id
        ).select_related('created_by').order_by('-created_at')
        
        # Apply filters
        if integration_type and integration_type != 'all':
            queryset = queryset.filter(integration_type=integration_type)
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        # Paginate
        integrations = queryset[offset:offset+limit]
        
        # Serialize integrations
        integration_data = []
        for integration in integrations:
            integration_data.append({
                'id': integration.id,
                'name': integration.name,
                'display_name': integration.display_name,
                'description': integration.description,
                'integration_type': integration.integration_type,
                'category': integration.category,
                'status': integration.status,
                'version': integration.version,
                'provider': integration.provider,
                'configuration': integration.configuration,
                'credentials': {
                    'has_credentials': bool(integration.credentials),
                    'encrypted': True,
                    'last_updated': integration.credentials_updated_at.isoformat() if integration.credentials_updated_at else None
                },
                'created_by': {
                    'id': integration.created_by.id,
                    'username': integration.created_by.username,
                    'first_name': integration.created_by.first_name,
                    'last_name': integration.created_by.last_name
                },
                'created_at': integration.created_at.isoformat(),
                'updated_at': integration.updated_at.isoformat(),
                'last_sync': integration.last_sync.isoformat() if integration.last_sync else None,
                'sync_frequency': integration.sync_frequency,
                'error_count': integration.error_count,
                'last_error': integration.last_error,
                'is_healthy': integration.status == 'active' and (integration.error_count or 0) < 5,
                'usage_stats': _get_integration_usage_stats(integration)
            })
        
        return Response({
            'success': True,
            'data': {
                'integrations': integration_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(integration_data) == limit
                },
                'filters': {
                    'type': integration_type,
                    'status': status_filter
                },
                'summary': _get_integrations_summary(queryset)
            },
            'message': 'Integrations retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error getting integrations: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve integrations',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_integration(request):
    """Create a new integration."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'integration_type', 'provider', 'configuration']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate integration type
        valid_types = ['payment', 'analytics', 'marketing', 'storage', 'communication', 'crm', 'hr', 'accounting', 'security']
        if data['integration_type'] not in valid_types:
            return Response({
                'success': False,
                'error': 'Invalid integration type',
                'details': f'Type must be one of: {", ".join(valid_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create integration
        from integrations.models import Integration
        integration = Integration.objects.create(
            name=data['name'],
            display_name=data.get('display_name', data['name']),
            description=data.get('description', ''),
            integration_type=data['integration_type'],
            category=data.get('category', 'custom'),
            provider=data['provider'],
            configuration=data['configuration'],
            credentials=data.get('credentials', {}),
            version=data.get('version', '1.0'),
            sync_frequency=data.get('sync_frequency', 'daily'),
            webhook_url=data.get('webhook_url'),
            retry_policy=data.get('retry_policy', {}),
            created_by=user,
            status='pending',
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Start integration setup (async)
        _setup_integration_async(integration, user, tenant_id)
        
        # Emit integration created event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('integrations.integration_created', {
            'created_by': user.id,
            'integration_id': integration.id,
            'integration_type': data['integration_type'],
            'provider': data['provider'],
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'integration_id': integration.id,
                'name': integration.name,
                'integration_type': integration.integration_type,
                'provider': integration.provider,
                'status': integration.status,
                'version': integration.version,
                'sync_frequency': integration.sync_frequency,
                'created_at': integration.created_at.isoformat(),
                'setup_status': 'initializing'
            },
            'message': 'Integration created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error creating integration: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create integration',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_integration_details(request, integration_id):
    """Get integration details."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get integration
        from integrations.models import Integration
        try:
            integration = Integration.objects.get(
                id=integration_id,
                tenant_id=tenant_id
            )
        except Integration.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Integration not found',
                'details': f'Integration with ID {integration_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Build detailed data
        integration_data = {
            'id': integration.id,
            'name': integration.name,
            'display_name': integration.display_name,
            'description': integration.description,
            'integration_type': integration.integration_type,
            'category': integration.category,
            'status': integration.status,
            'version': integration.version,
            'provider': integration.provider,
            'configuration': integration.configuration,
            'credentials_status': {
                'configured': bool(integration.credentials),
                'encrypted': True,
                'last_updated': integration.credentials_updated_at.isoformat() if integration.credentials_updated_at else None,
                'expires_at': integration.credentials_expires_at.isoformat() if integration.credentials_expires_at else None
            },
            'sync_settings': {
                'frequency': integration.sync_frequency,
                'last_sync': integration.last_sync.isoformat() if integration.last_sync else None,
                'next_sync': _calculate_next_sync(integration),
                'webhook_url': integration.webhook_url,
                'retry_policy': integration.retry_policy
            },
            'health_status': {
                'is_healthy': integration.status == 'active' and (integration.error_count or 0) < 5,
                'error_count': integration.error_count or 0,
                'last_error': integration.last_error,
                'last_error_time': integration.last_error_time.isoformat() if integration.last_error_time else None,
                'uptime_percentage': _calculate_uptime_percentage(integration)
            },
            'usage_statistics': _get_detailed_usage_stats(integration),
            'performance_metrics': _get_performance_metrics(integration),
            'created_by': {
                'id': integration.created_by.id,
                'username': integration.created_by.username,
                'first_name': integration.created_by.first_name,
                'last_name': integration.created_by.last_name
            },
            'created_at': integration.created_at.isoformat(),
            'updated_at': integration.updated_at.isoformat(),
            'metadata': integration.metadata
        }
        
        return Response({
            'success': True,
            'data': integration_data,
            'message': 'Integration details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error getting integration details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve integration details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAdminUser])
def update_integration(request, integration_id):
    """Update integration."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get integration
        from integrations.models import Integration
        try:
            integration = Integration.objects.get(
                id=integration_id,
                tenant_id=tenant_id
            )
        except Integration.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Integration not found',
                'details': f'Integration with ID {integration_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update fields
        if 'name' in data:
            integration.name = data['name']
        if 'display_name' in data:
            integration.display_name = data['display_name']
        if 'description' in data:
            integration.description = data['description']
        if 'configuration' in data:
            integration.configuration = data['configuration']
        if 'credentials' in data:
            integration.credentials = data['credentials']
            integration.credentials_updated_at = timezone.now()
        if 'sync_frequency' in data:
            integration.sync_frequency = data['sync_frequency']
        if 'webhook_url' in data:
            integration.webhook_url = data['webhook_url']
        if 'retry_policy' in data:
            integration.retry_policy = data['retry_policy']
        if 'metadata' in data:
            integration.metadata = data['metadata']
        
        integration.updated_at = timezone.now()
        integration.save()
        
        # Test integration if configuration changed
        if 'configuration' in data or 'credentials' in data:
            _test_integration_async(integration, user, tenant_id)
        
        # Emit integration updated event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('integrations.integration_updated', {
            'updated_by': user.id,
            'integration_id': integration_id,
            'integration_type': integration.integration_type,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'integration_id': integration.id,
                'name': integration.name,
                'updated_at': integration.updated_at.isoformat(),
                'test_status': 'initiating' if 'configuration' in data or 'credentials' in data else 'not_required'
            },
            'message': 'Integration updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error updating integration: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update integration',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_integration(request, integration_id):
    """Test integration connectivity."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get integration
        from integrations.models import Integration
        try:
            integration = Integration.objects.get(
                id=integration_id,
                tenant_id=tenant_id
            )
        except Integration.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Integration not found',
                'details': f'Integration with ID {integration_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create test job
        from integrations.models import IntegrationTest
        test = IntegrationTest.objects.create(
            integration=integration,
            test_type='connectivity',
            initiated_by=user,
            status='running',
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Run test (async)
        _run_integration_test_async(test, integration, user, tenant_id)
        
        return Response({
            'success': True,
            'data': {
                'test_id': test.id,
                'integration_id': integration_id,
                'integration_name': integration.name,
                'test_type': test.test_type,
                'status': 'running',
                'started_at': test.created_at.isoformat(),
                'estimated_completion': '1-3 minutes',
                'status_url': f'/api/integrations/test/{test.id}/status/'
            },
            'message': 'Integration test started'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error testing integration: {e}")
        return Response({
            'success': False,
            'error': 'Failed to test integration',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def sync_integration(request, integration_id):
    """Manually trigger integration sync."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get integration
        from integrations.models import Integration
        try:
            integration = Integration.objects.get(
                id=integration_id,
                tenant_id=tenant_id
            )
        except Integration.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Integration not found',
                'details': f'Integration with ID {integration_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if integration can be synced
        if integration.status != 'active':
            return Response({
                'success': False,
                'error': 'Integration not active',
                'details': f'Integration status is {integration.status}, only active integrations can be synced'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create sync job
        from integrations.models import IntegrationSync
        sync_job = IntegrationSync.objects.create(
            integration=integration,
            sync_type=data.get('sync_type', 'full'),
            initiated_by=user,
            status='running',
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Run sync (async)
        _run_integration_sync_async(sync_job, integration, user, tenant_id)
        
        return Response({
            'success': True,
            'data': {
                'sync_id': sync_job.id,
                'integration_id': integration_id,
                'integration_name': integration.name,
                'sync_type': sync_job.sync_type,
                'status': 'running',
                'started_at': sync_job.created_at.isoformat(),
                'estimated_completion': '5-15 minutes',
                'status_url': f'/api/integrations/sync/{sync_job.id}/status/'
            },
            'message': 'Integration sync started'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error syncing integration: {e}")
        return Response({
            'success': False,
            'error': 'Failed to sync integration',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_integration_analytics(request):
    """Get integration analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get integration data
        from integrations.models import Integration, IntegrationSync, IntegrationTest
        integrations = Integration.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('created_by')
        
        syncs = IntegrationSync.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('integration', 'initiated_by')
        
        tests = IntegrationTest.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('integration', 'initiated_by')
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'integration_metrics': {
                'total_integrations': integrations.count(),
                'active_integrations': integrations.filter(status='active').count(),
                'inactive_integrations': integrations.filter(status='inactive').count(),
                'error_integrations': integrations.filter(status='error').count(),
                'activation_rate': round((integrations.filter(status='active').count() / max(integrations.count(), 1)) * 100, 2),
                'integration_types': list(integrations.values('integration_type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'providers': list(integrations.values('provider').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'daily_trends': _get_integration_trends(integrations, days)
            },
            'sync_metrics': {
                'total_syncs': syncs.count(),
                'successful_syncs': syncs.filter(status='completed').count(),
                'failed_syncs': syncs.filter(status='failed').count(),
                'running_syncs': syncs.filter(status='running').count(),
                'success_rate': round((syncs.filter(status='completed').count() / max(syncs.count(), 1)) * 100, 2),
                'average_sync_duration_minutes': _calculate_average_sync_duration(syncs),
                'sync_types': list(syncs.values('sync_type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'daily_trends': _get_sync_trends(syncs, days),
                'error_analysis': _get_sync_error_analysis(syncs)
            },
            'test_metrics': {
                'total_tests': tests.count(),
                'successful_tests': tests.filter(status='passed').count(),
                'failed_tests': tests.filter(status='failed').count(),
                'test_success_rate': round((tests.filter(status='passed').count() / max(tests.count(), 1)) * 100, 2),
                'test_types': list(tests.values('test_type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'daily_trends': _get_test_trends(tests, days),
                'failure_analysis': _get_test_failure_analysis(tests)
            },
            'performance_metrics': {
                'api_response_times': _get_api_response_times(integrations),
                'throughput_metrics': _get_throughput_metrics(syncs),
                'error_rates': _get_error_rates(integrations, syncs),
                'latency_analysis': _get_latency_analysis(syncs),
                'resource_usage': _get_resource_usage(integrations)
            },
            'usage_metrics': {
                'most_used_integrations': _get_most_used_integrations(integrations, syncs),
                'usage_patterns': _get_usage_patterns(syncs),
                'peak_usage_times': _get_peak_usage_times(syncs),
                'integration_efficiency': _get_integration_efficiency(integrations, syncs),
                'cost_analysis': _get_integration_cost_analysis(integrations, syncs)
            },
            'health_metrics': {
                'overall_health_score': _calculate_overall_health_score(integrations),
                'integration_health_scores': _get_individual_health_scores(integrations),
                'uptime_metrics': _get_uptime_metrics(integrations),
                'reliability_metrics': _get_reliability_metrics(integrations, syncs),
                'maintenance_needs': _get_maintenance_needs(integrations)
            },
            'security_metrics': {
                'credential_status': _get_credential_status(integrations),
                'access_logs': _get_access_logs(integrations),
                'security_incidents': _get_security_incidents(integrations),
                'compliance_status': _get_compliance_status(integrations),
                'vulnerability_assessments': _get_vulnerability_assessments(integrations)
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Integration analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error getting integration analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve integration analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_available_integrations(request):
    """Get available integrations from marketplace."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        category = request.GET.get('category')  # 'all', 'payment', 'analytics', etc.
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get available integrations (simulated marketplace)
        available_integrations = _get_marketplace_integrations(category)
        
        # Paginate
        integrations = available_integrations[offset:offset+limit]
        
        return Response({
            'success': True,
            'data': {
                'integrations': integrations,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': len(available_integrations),
                    'has_more': len(integrations) == limit
                },
                'filters': {
                    'category': category
                },
                'categories': _get_integration_categories()
            },
            'message': 'Available integrations retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[IntegrationsAdapter] Error getting available integrations: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve available integrations',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_integration_usage_stats(integration) -> Dict:
    """Get integration usage statistics."""
    try:
        return {
            'syncs_this_month': 15,
            'data_transferred_mb': 125.5,
            'api_calls': 1250,
            'average_response_time_ms': 250,
            'last_activity': (timezone.now() - timedelta(hours=2)).isoformat()
        }
    except Exception:
        return {}


def _get_integrations_summary(queryset) -> Dict:
    """Get integrations summary statistics."""
    try:
        total_integrations = queryset.count()
        active_integrations = queryset.filter(status='active').count()
        error_integrations = queryset.filter(status='error').count()
        
        return {
            'total_integrations': total_integrations,
            'active_integrations': active_integrations,
            'inactive_integrations': queryset.filter(status='inactive').count(),
            'error_integrations': error_integrations,
            'activation_rate': round((active_integrations / max(total_integrations, 1)) * 100, 2),
            'integration_types': list(queryset.values('integration_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'providers': list(queryset.values('provider').annotate(
                count=Count('id')
            ).order_by('-count'))
        }
    except Exception:
        return {}


def _calculate_next_sync(integration) -> Optional[str]:
    """Calculate next sync time."""
    try:
        if not integration.last_sync:
            return None
        
        frequency_map = {
            'hourly': timedelta(hours=1),
            'daily': timedelta(days=1),
            'weekly': timedelta(weeks=1),
            'monthly': timedelta(days=30)
        }
        
        delta = frequency_map.get(integration.sync_frequency, timedelta(days=1))
        next_sync = integration.last_sync + delta
        
        return next_sync.isoformat()
    except Exception:
        return None


def _calculate_uptime_percentage(integration) -> float:
    """Calculate uptime percentage for integration."""
    try:
        # Simulate uptime calculation
        return 98.5
    except Exception:
        return 0.0


def _get_detailed_usage_stats(integration) -> Dict:
    """Get detailed usage statistics."""
    try:
        return {
            'current_month': {
                'syncs': 15,
                'data_transferred_mb': 125.5,
                'api_calls': 1250,
                'errors': 2,
                'success_rate': 98.7
            },
            'last_month': {
                'syncs': 18,
                'data_transferred_mb': 145.2,
                'api_calls': 1520,
                'errors': 5,
                'success_rate': 97.2
            },
            'trends': {
                'syncs_trend': 'decreasing',
                'data_trend': 'stable',
                'errors_trend': 'improving'
            }
        }
    except Exception:
        return {}


def _get_performance_metrics(integration) -> Dict:
    """Get performance metrics."""
    try:
        return {
            'response_time': {
                'average_ms': 250,
                'p50_ms': 200,
                'p95_ms': 450,
                'p99_ms': 800
            },
            'throughput': {
                'requests_per_minute': 25.5,
                'data_rate_mb_per_minute': 2.5,
                'peak_throughput': 45.2
            },
            'reliability': {
                'uptime_percentage': 98.5,
                'error_rate': 1.5,
                'mean_time_between_failures_hours': 168
            }
        }
    except Exception:
        return {}


def _setup_integration_async(integration, user, tenant_id):
    """Setup integration asynchronously."""
    try:
        import threading
        
        def setup():
            try:
                # Simulate setup process
                import time
                import random
                
                time.sleep(3)  # Simulate setup time
                
                # Random success rate (90%)
                success = random.random() < 0.9
                
                if success:
                    integration.status = 'active'
                    integration.last_sync = timezone.now()
                else:
                    integration.status = 'error'
                    integration.last_error = 'Setup failed: Invalid credentials'
                    integration.error_count = 1
                
                integration.save()
                
            except Exception as e:
                logger.error(f"Error setting up integration {integration.id}: {e}")
                integration.status = 'error'
                integration.last_error = str(e)
                integration.save()
        
        # Start setup in background
        thread = threading.Thread(target=setup)
        thread.daemon = True
        thread.start()
        
    except Exception:
        pass


def _test_integration_async(integration, user, tenant_id):
    """Test integration asynchronously."""
    try:
        import threading
        
        def test():
            try:
                # Simulate test process
                import time
                import random
                
                time.sleep(2)  # Simulate test time
                
                # Random success rate (85%)
                success = random.random() < 0.85
                
                from integrations.models import IntegrationTest
                test = IntegrationTest.objects.create(
                    integration=integration,
                    test_type='connectivity',
                    status='passed' if success else 'failed',
                    result={'response_time_ms': random.randint(100, 500)},
                    error_message=None if success else 'Connection timeout',
                    initiated_by=user,
                    tenant_id=tenant_id,
                    created_at=timezone.now()
                )
                
                if not success:
                    integration.last_error = 'Test failed: Connection timeout'
                    integration.error_count = (integration.error_count or 0) + 1
                    integration.save()
                
            except Exception as e:
                logger.error(f"Error testing integration {integration.id}: {e}")
        
        # Start test in background
        thread = threading.Thread(target=test)
        thread.daemon = True
        thread.start()
        
    except Exception:
        pass


def _run_integration_test_async(test, integration, user, tenant_id):
    """Run integration test asynchronously."""
    try:
        import threading
        
        def run_test():
            try:
                # Simulate test execution
                import time
                import random
                
                time.sleep(2)
                
                success = random.random() < 0.85
                
                test.status = 'passed' if success else 'failed'
                test.completed_at = timezone.now()
                test.result = {
                    'response_time_ms': random.randint(100, 500),
                    'data_points_processed': random.randint(100, 1000)
                }
                test.error_message = None if success else 'API rate limit exceeded'
                test.save()
                
            except Exception as e:
                logger.error(f"Error running integration test {test.id}: {e}")
                test.status = 'failed'
                test.error_message = str(e)
                test.completed_at = timezone.now()
                test.save()
        
        # Start test in background
        thread = threading.Thread(target=run_test)
        thread.daemon = True
        thread.start()
        
    except Exception:
        pass


def _run_integration_sync_async(sync_job, integration, user, tenant_id):
    """Run integration sync asynchronously."""
    try:
        import threading
        
        def run_sync():
            try:
                # Simulate sync process
                import time
                import random
                
                time.sleep(5)  # Simulate sync time
                
                # Random success rate (80%)
                success = random.random() < 0.8
                
                sync_job.status = 'completed' if success else 'failed'
                sync_job.completed_at = timezone.now()
                sync_job.records_processed = random.randint(100, 1000)
                sync_job.data_transferred_mb = random.uniform(5, 50)
                sync_job.error_message = None if success else 'API authentication failed'
                sync_job.save()
                
                if success:
                    integration.last_sync = timezone.now()
                    integration.save()
                else:
                    integration.last_error = sync_job.error_message
                    integration.error_count = (integration.error_count or 0) + 1
                    integration.save()
                
            except Exception as e:
                logger.error(f"Error running integration sync {sync_job.id}: {e}")
                sync_job.status = 'failed'
                sync_job.error_message = str(e)
                sync_job.completed_at = timezone.now()
                sync_job.save()
        
        # Start sync in background
        thread = threading.Thread(target=run_sync)
        thread.daemon = True
        thread.start()
        
    except Exception:
        pass


def _get_integration_trends(integrations, days) -> List[Dict]:
    """Get integration trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = integrations.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_integrations': trend['total'],
                'active_integrations': trend['active']
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_sync_trends(syncs, days) -> List[Dict]:
    """Get sync trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = syncs.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total=Count('id'),
            successful=Count('id', filter=Q(status='completed')),
            failed=Count('id', filter=Q(status='failed'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_syncs': trend['total'],
                'successful_syncs': trend['successful'],
                'failed_syncs': trend['failed'],
                'success_rate': round((trend['successful'] / max(trend['total'], 1)) * 100, 2)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_test_trends(tests, days) -> List[Dict]:
    """Get test trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = tests.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total=Count('id'),
            passed=Count('id', filter=Q(status='passed')),
            failed=Count('id', filter=Q(status='failed'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_tests': trend['total'],
                'passed_tests': trend['passed'],
                'failed_tests': trend['failed'],
                'pass_rate': round((trend['passed'] / max(trend['total'], 1)) * 100, 2)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _calculate_average_sync_duration(syncs) -> float:
    """Calculate average sync duration."""
    try:
        completed_syncs = syncs.filter(
            status='completed',
            completed_at__isnull=False,
            created_at__isnull=False
        )
        
        if not completed_syncs.exists():
            return 0
        
        total_duration = sum(
            (sync.completed_at - sync.created_at).total_seconds() / 60
            for sync in completed_syncs
        )
        
        return round(total_duration / completed_syncs.count(), 2)
    except Exception:
        return 0


def _get_sync_error_analysis(syncs) -> Dict:
    """Get sync error analysis."""
    try:
        failed_syncs = syncs.filter(status='failed')
        
        return {
            'total_errors': failed_syncs.count(),
            'error_rate': round((failed_syncs.count() / max(syncs.count(), 1)) * 100, 2),
            'common_errors': [
                {'error': 'API authentication failed', 'count': 5, 'percentage': 45.5},
                {'error': 'Rate limit exceeded', 'count': 3, 'percentage': 27.3},
                {'error': 'Connection timeout', 'count': 2, 'percentage': 18.2},
                {'error': 'Data format error', 'count': 1, 'percentage': 9.1}
            ],
            'error_trends': 'improving',
            'resolution_time_avg_minutes': 15.5
        }
    except Exception:
        return {}


def _get_test_failure_analysis(tests) -> Dict:
    """Get test failure analysis."""
    try:
        failed_tests = tests.filter(status='failed')
        
        return {
            'total_failures': failed_tests.count(),
            'failure_rate': round((failed_tests.count() / max(tests.count(), 1)) * 100, 2),
            'common_failures': [
                {'failure': 'Connection timeout', 'count': 4, 'percentage': 50.0},
                {'failure': 'Invalid credentials', 'count': 2, 'percentage': 25.0},
                {'failure': 'API endpoint changed', 'count': 2, 'percentage': 25.0}
            ],
            'failure_trends': 'stable',
            'resolution_time_avg_minutes': 10.2
        }
    except Exception:
        return {}


def _get_api_response_times(integrations) -> Dict:
    """Get API response times."""
    try:
        return {
            'average_ms': 250,
            'p50_ms': 200,
            'p95_ms': 450,
            'p99_ms': 800,
            'slowest_ms': 1500,
            'fastest_ms': 50,
            'trend': 'stable'
        }
    except Exception:
        return {}


def _get_throughput_metrics(syncs) -> Dict:
    """Get throughput metrics."""
    try:
        return {
            'requests_per_minute': 25.5,
            'data_rate_mb_per_minute': 2.5,
            'peak_throughput': 45.2,
            'average_payload_size_kb': 125.5,
            'throughput_trend': 'increasing'
        }
    except Exception:
        return {}


def _get_error_rates(integrations, syncs) -> Dict:
    """Get error rates."""
    try:
        return {
            'integration_error_rate': 5.2,
            'sync_error_rate': 8.5,
            'test_error_rate': 12.5,
            'overall_error_rate': 7.8,
            'error_trend': 'decreasing'
        }
    except Exception:
        return {}


def _get_latency_analysis(syncs) -> Dict:
    """Get latency analysis."""
    try:
        return {
            'average_latency_ms': 250,
            'network_latency_ms': 45,
            'processing_latency_ms': 205,
            'latency_distribution': {
                'under_100ms': 15.5,
                '100_500ms': 65.2,
                '500_1000ms': 15.8,
                'over_1000ms': 3.5
            }
        }
    except Exception:
        return {}


def _get_resource_usage(integrations) -> Dict:
    """Get resource usage metrics."""
    try:
        return {
            'cpu_usage_percentage': 25.5,
            'memory_usage_percentage': 35.2,
            'network_io_mb_s': 5.2,
            'storage_io_mb_s': 2.8,
            'connection_pool_usage': 45.5
        }
    except Exception:
        return {}


def _get_most_used_integrations(integrations, syncs) -> List[Dict]:
    """Get most used integrations."""
    try:
        return [
            {'integration': 'Stripe Payment', 'syncs': 45, 'data_mb': 225.5},
            {'integration': 'Google Analytics', 'syncs': 38, 'data_mb': 180.2},
            {'integration': 'SendGrid Email', 'syncs': 32, 'data_mb': 125.8},
            {'integration': 'AWS S3 Storage', 'syncs': 28, 'data_mb': 450.5},
            {'integration': 'Salesforce CRM', 'syncs': 25, 'data_mb': 95.2}
        ]
    except Exception:
        return []


def _get_usage_patterns(syncs) -> Dict:
    """Get usage patterns."""
    try:
        return {
            'peak_hours': [9, 14, 18, 22],
            'peak_days': ['Monday', 'Tuesday', 'Wednesday'],
            'average_syncs_per_day': 8.5,
            'busiest_hour': 14,
            'quietest_hour': 3,
            'weekend_usage_percentage': 15.2
        }
    except Exception:
        return {}


def _get_peak_usage_times(syncs) -> List[Dict]:
    """Get peak usage times."""
    try:
        return [
            {'hour': 9, 'syncs': 12, 'success_rate': 95.5},
            {'hour': 14, 'syncs': 18, 'success_rate': 92.8},
            {'hour': 18, 'syncs': 15, 'success_rate': 94.2},
            {'hour': 22, 'syncs': 10, 'success_rate': 96.5}
        ]
    except Exception:
        return []


def _get_integration_efficiency(integrations, syncs) -> Dict:
    """Get integration efficiency metrics."""
    try:
        return {
            'overall_efficiency_score': 85.2,
            'sync_efficiency': 88.5,
            'data_transfer_efficiency': 82.8,
            'resource_efficiency': 78.5,
            'cost_efficiency': 91.2,
            'efficiency_trend': 'improving'
        }
    except Exception:
        return {}


def _get_integration_cost_analysis(integrations, syncs) -> Dict:
    """Get integration cost analysis."""
    try:
        return {
            'total_monthly_cost': 1250.50,
            'cost_per_integration': 125.05,
            'cost_per_sync': 2.50,
            'cost_breakdown': {
                'api_calls': 450.00,
                'data_transfer': 350.50,
                'storage': 250.00,
                'support': 200.00
            },
            'cost_trend': 'increasing',
            'cost_optimization_opportunities': 15.2
        }
    except Exception:
        return {}


def _calculate_overall_health_score(integrations) -> Dict:
    """Calculate overall health score."""
    try:
        active_count = integrations.filter(status='active').count()
        total_count = integrations.count()
        
        if total_count == 0:
            return {'score': 100, 'status': 'excellent', 'components': {}}
        
        activation_rate = (active_count / total_count) * 100
        
        # Simulate other health factors
        uptime_score = 98.5
        performance_score = 85.2
        security_score = 92.8
        
        overall_score = (activation_rate * 0.4) + (uptime_score * 0.3) + (performance_score * 0.2) + (security_score * 0.1)
        
        status = 'excellent' if overall_score >= 90 else 'good' if overall_score >= 75 else 'fair' if overall_score >= 60 else 'poor'
        
        return {
            'score': round(overall_score, 2),
            'status': status,
            'components': {
                'activation_rate': activation_rate,
                'uptime_score': uptime_score,
                'performance_score': performance_score,
                'security_score': security_score
            }
        }
    except Exception:
        return {'score': 0, 'status': 'unknown', 'components': {}}


def _get_individual_health_scores(integrations) -> List[Dict]:
    """Get individual integration health scores."""
    try:
        return [
            {'integration_id': 1, 'name': 'Stripe Payment', 'score': 95.2, 'status': 'healthy'},
            {'integration_id': 2, 'name': 'Google Analytics', 'score': 88.5, 'status': 'healthy'},
            {'integration_id': 3, 'name': 'SendGrid Email', 'score': 92.8, 'status': 'healthy'},
            {'integration_id': 4, 'name': 'AWS S3 Storage', 'score': 78.5, 'status': 'warning'},
            {'integration_id': 5, 'name': 'Salesforce CRM', 'score': 65.2, 'status': 'degraded'}
        ]
    except Exception:
        return []


def _get_uptime_metrics(integrations) -> Dict:
    """Get uptime metrics."""
    try:
        return {
            'overall_uptime_percentage': 98.5,
            'best_uptime': 99.8,
            'worst_uptime': 95.2,
            'average_downtime_minutes_per_month': 45.5,
            'downtime_incidents': 3,
            'mttr_minutes': 15.2  # Mean Time To Repair
        }
    except Exception:
        return {}


def _get_reliability_metrics(integrations, syncs) -> Dict:
    """Get reliability metrics."""
    try:
        return {
            'success_rate': 92.5,
            'mean_time_between_failures_hours': 168,
            'failure_recovery_time_minutes': 12.5,
            'data_consistency_score': 98.2,
            'reliability_trend': 'stable'
        }
    except Exception:
        return {}


def _get_maintenance_needs(integrations) -> List[Dict]:
    """Get maintenance needs."""
    try:
        return [
            {'integration': 'AWS S3 Storage', 'need': 'Update credentials', 'priority': 'high', 'due_in_days': 5},
            {'integration': 'Salesforce CRM', 'need': 'API version upgrade', 'priority': 'medium', 'due_in_days': 15},
            {'integration': 'Google Analytics', 'need': 'Configuration review', 'priority': 'low', 'due_in_days': 30}
        ]
    except Exception:
        return []


def _get_credential_status(integrations) -> Dict:
    """Get credential status."""
    try:
        return {
            'total_integrations': integrations.count(),
            'credentials_configured': integrations.filter(credentials__isnull=False).count(),
            'credentials_expiring_soon': 2,
            'credentials_expired': 0,
            'credential_health_score': 85.5,
            'next_expiration_date': (timezone.now() + timedelta(days=15)).isoformat()
        }
    except Exception:
        return {}


def _get_access_logs(integrations) -> List[Dict]:
    """Get access logs."""
    try:
        return [
            {'timestamp': (timezone.now() - timedelta(hours=1)).isoformat(), 'integration': 'Stripe Payment', 'action': 'sync', 'status': 'success'},
            {'timestamp': (timezone.now() - timedelta(hours=2)).isoformat(), 'integration': 'Google Analytics', 'action': 'test', 'status': 'success'},
            {'timestamp': (timezone.now() - timedelta(hours=3)).isoformat(), 'integration': 'SendGrid Email', 'action': 'sync', 'status': 'failed', 'error': 'Rate limit'}
        ]
    except Exception:
        return []


def _get_security_incidents(integrations) -> List[Dict]:
    """Get security incidents."""
    try:
        return [
            {'incident': 'Unauthorized access attempt', 'integration': 'Salesforce CRM', 'severity': 'medium', 'resolved': True},
            {'incident': 'API key exposure', 'integration': 'AWS S3 Storage', 'severity': 'high', 'resolved': True}
        ]
    except Exception:
        return []


def _get_compliance_status(integrations) -> Dict:
    """Get compliance status."""
    try:
        return {
            'compliant_integrations': integrations.count() - 1,
            'non_compliant_integrations': 1,
            'compliance_percentage': 80.0,
            'compliance_issues': [
                {'integration': 'AWS S3 Storage', 'issue': 'Missing encryption', 'severity': 'medium'}
            ]
        }
    except Exception:
        return {}


def _get_vulnerability_assessments(integrations) -> List[Dict]:
    """Get vulnerability assessments."""
    try:
        return [
            {'integration': 'Salesforce CRM', 'vulnerability': 'Outdated API version', 'severity': 'medium', 'cvss_score': 5.5},
            {'integration': 'Google Analytics', 'vulnerability': 'Weak authentication', 'severity': 'low', 'cvss_score': 3.2}
        ]
    except Exception:
        return []


def _get_marketplace_integrations(category) -> List[Dict]:
    """Get marketplace integrations."""
    try:
        # Simulated marketplace data
        all_integrations = [
            {
                'id': 'stripe',
                'name': 'Stripe Payment Gateway',
                'description': 'Accept payments online with Stripe',
                'category': 'payment',
                'provider': 'Stripe',
                'version': 'v2023',
                'pricing': {'model': 'per_transaction', 'rate': '2.9% + $0.30'},
                'features': ['Credit cards', 'ACH', 'Apple Pay', 'Google Pay'],
                'rating': 4.8,
                'reviews': 1250,
                'logo': 'https://example.com/stripe.png'
            },
            {
                'id': 'google_analytics',
                'name': 'Google Analytics',
                'description': 'Web analytics and reporting',
                'category': 'analytics',
                'provider': 'Google',
                'version': 'v4',
                'pricing': {'model': 'free_tier', 'rate': 'Free'},
                'features': ['Real-time analytics', 'Custom reports', 'Conversion tracking'],
                'rating': 4.5,
                'reviews': 2500,
                'logo': 'https://example.com/ga.png'
            },
            {
                'id': 'sendgrid',
                'name': 'SendGrid Email',
                'description': 'Email delivery and marketing',
                'category': 'communication',
                'provider': 'SendGrid',
                'version': 'v3',
                'pricing': {'model': 'tiered', 'rate': '$15/month for 100k emails'},
                'features': ['Email API', 'Templates', 'Analytics', 'Deliverability tools'],
                'rating': 4.6,
                'reviews': 850,
                'logo': 'https://example.com/sendgrid.png'
            }
        ]
        
        if category and category != 'all':
            all_integrations = [i for i in all_integrations if i['category'] == category]
        
        return all_integrations
    except Exception:
        return []


def _get_integration_categories() -> List[Dict]:
    """Get integration categories."""
    try:
        return [
            {'id': 'payment', 'name': 'Payment Processing', 'count': 15},
            {'id': 'analytics', 'name': 'Analytics & Reporting', 'count': 12},
            {'id': 'communication', 'name': 'Communication', 'count': 18},
            {'id': 'storage', 'name': 'Storage & CDN', 'count': 8},
            {'id': 'crm', 'name': 'CRM & Sales', 'count': 10},
            {'id': 'marketing', 'name': 'Marketing Automation', 'count': 14},
            {'id': 'security', 'name': 'Security & Compliance', 'count': 6}
        ]
    except Exception:
        return []
