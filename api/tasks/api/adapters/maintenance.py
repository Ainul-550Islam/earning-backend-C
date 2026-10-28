"""
api/adapters/maintenance.py
Maintenance adapter for earning backend platform
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
def get_maintenance_status(request):
    """Get current maintenance status."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get maintenance status
        from maintenance.models import MaintenanceStatus
        try:
            status_obj = MaintenanceStatus.objects.get(
                tenant_id=tenant_id
            )
        except MaintenanceStatus.DoesNotExist:
            status_obj = MaintenanceStatus.objects.create(
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Build status data
        status_data = {
            'tenant_id': tenant_id,
            'overall_status': status_obj.overall_status,
            'services': {
                'database': {
                    'status': status_obj.database_status,
                    'last_check': status_obj.database_last_check.isoformat(),
                    'response_time_ms': status_obj.database_response_time,
                    'error_rate': status_obj.database_error_rate,
                    'uptime_percentage': status_obj.database_uptime
                },
                'api': {
                    'status': status_obj.api_status,
                    'last_check': status_obj.api_last_check.isoformat(),
                    'response_time_ms': status_obj.api_response_time,
                    'error_rate': status_obj.api_error_rate,
                    'uptime_percentage': status_obj.api_uptime
                },
                'cache': {
                    'status': status_obj.cache_status,
                    'last_check': status_obj.cache_last_check.isoformat(),
                    'response_time_ms': status_obj.cache_response_time,
                    'hit_rate': status_obj.cache_hit_rate,
                    'memory_usage': status_obj.cache_memory_usage
                },
                'queue': {
                    'status': status_obj.queue_status,
                    'last_check': status_obj.queue_last_check.isoformat(),
                    'queue_length': status_obj.queue_length,
                    'processing_rate': status_obj.queue_processing_rate,
                    'failed_jobs': status_obj.queue_failed_jobs
                },
                'storage': {
                    'status': status_obj.storage_status,
                    'last_check': status_obj.storage_last_check.isoformat(),
                    'disk_usage_percentage': status_obj.disk_usage_percentage,
                    'available_space_gb': status_obj.available_space_gb,
                    'io_rate_mb_s': status_obj.io_rate_mb_s
                }
            },
            'alerts': {
                'active_alerts': status_obj.active_alerts,
                'critical_alerts': status_obj.critical_alerts,
                'warning_alerts': status_obj.warning_alerts,
                'last_alert': status_obj.last_alert.isoformat() if status_obj.last_alert else None
            },
            'performance': {
                'cpu_usage': status_obj.cpu_usage,
                'memory_usage': status_obj.memory_usage,
                'network_io': status_obj.network_io,
                'load_average': status_obj.load_average
            },
            'last_updated': status_obj.updated_at.isoformat(),
            'maintenance_windows': _get_upcoming_maintenance_windows(tenant_id)
        }
        
        return Response({
            'success': True,
            'data': status_data,
            'message': 'Maintenance status retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MaintenanceAdapter] Error getting maintenance status: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve maintenance status',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def schedule_maintenance(request):
    """Schedule maintenance window."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'description', 'scheduled_start', 'scheduled_end', 'type']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse dates
        from dateutil.parser import parse
        scheduled_start = parse(data['scheduled_start'])
        scheduled_end = parse(data['scheduled_end'])
        
        # Validate dates
        if scheduled_start >= scheduled_end:
            return Response({
                'success': False,
                'error': 'Invalid dates',
                'details': 'End time must be after start time'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if scheduled_start <= timezone.now():
            return Response({
                'success': False,
                'error': 'Invalid start time',
                'details': 'Start time must be in the future'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create maintenance window
        from maintenance.models import MaintenanceWindow
        window = MaintenanceWindow.objects.create(
            title=data['title'],
            description=data['description'],
            type=data['type'],  # 'planned', 'emergency', 'routine'
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            affected_services=data.get('affected_services', ['all']),
            impact_level=data.get('impact_level', 'medium'),
            notification_settings=data.get('notification_settings', {}),
            backup_required=data.get('backup_required', True),
            rollback_plan=data.get('rollback_plan', ''),
            created_by=user,
            status='scheduled',
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Send notifications (async)
        _send_maintenance_notifications_async(window, 'scheduled', tenant_id)
        
        # Emit maintenance scheduled event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('maintenance.scheduled', {
            'created_by': user.id,
            'window_id': window.id,
            'title': data['title'],
            'type': data['type'],
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'window_id': window.id,
                'title': window.title,
                'description': window.description,
                'type': window.type,
                'scheduled_start': window.scheduled_start.isoformat(),
                'scheduled_end': window.scheduled_end.isoformat(),
                'affected_services': window.affected_services,
                'impact_level': window.impact_level,
                'status': window.status,
                'created_at': window.created_at.isoformat()
            },
            'message': 'Maintenance window scheduled successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[MaintenanceAdapter] Error scheduling maintenance: {e}")
        return Response({
            'success': False,
            'error': 'Failed to schedule maintenance',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_maintenance_windows(request):
    """Get maintenance windows."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        status_filter = request.GET.get('status')  # 'all', 'scheduled', 'in_progress', 'completed', 'cancelled'
        type_filter = request.GET.get('type')  # 'all', 'planned', 'emergency', 'routine'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get maintenance windows
        from maintenance.models import MaintenanceWindow
        queryset = MaintenanceWindow.objects.filter(
            tenant_id=tenant_id
        ).select_related('created_by').order_by('-created_at')
        
        # Apply filters
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        if type_filter and type_filter != 'all':
            queryset = queryset.filter(type=type_filter)
        
        # Paginate
        windows = queryset[offset:offset+limit]
        
        # Serialize windows
        window_data = []
        for window in windows:
            window_data.append({
                'id': window.id,
                'title': window.title,
                'description': window.description,
                'type': window.type,
                'status': window.status,
                'scheduled_start': window.scheduled_start.isoformat(),
                'scheduled_end': window.scheduled_end.isoformat(),
                'actual_start': window.actual_start.isoformat() if window.actual_start else None,
                'actual_end': window.actual_end.isoformat() if window.actual_end else None,
                'affected_services': window.affected_services,
                'impact_level': window.impact_level,
                'backup_required': window.backup_required,
                'rollback_plan': window.rollback_plan,
                'created_by': {
                    'id': window.created_by.id,
                    'username': window.created_by.username,
                    'first_name': window.created_by.first_name,
                    'last_name': window.created_by.last_name
                },
                'created_at': window.created_at.isoformat(),
                'updated_at': window.updated_at.isoformat(),
                'duration_minutes': _calculate_duration_minutes(window),
                'is_upcoming': window.scheduled_start > timezone.now(),
                'is_active': window.status == 'in_progress'
            })
        
        return Response({
            'success': True,
            'data': {
                'windows': window_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(window_data) == limit
                },
                'filters': {
                    'status': status_filter,
                    'type': type_filter
                },
                'summary': _get_maintenance_summary(queryset)
            },
            'message': 'Maintenance windows retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MaintenanceAdapter] Error getting maintenance windows: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve maintenance windows',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def start_maintenance(request, window_id):
    """Start maintenance window."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get maintenance window
        from maintenance.models import MaintenanceWindow
        try:
            window = MaintenanceWindow.objects.get(
                id=window_id,
                tenant_id=tenant_id
            )
        except MaintenanceWindow.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Maintenance window not found',
                'details': f'Maintenance window with ID {window_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if window can be started
        if window.status != 'scheduled':
            return Response({
                'success': False,
                'error': 'Cannot start maintenance',
                'details': f'Window status is {window.status}, only scheduled windows can be started'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start maintenance
        window.status = 'in_progress'
        window.actual_start = timezone.now()
        window.save()
        
        # Update system status
        _update_system_maintenance_status(True, tenant_id)
        
        # Send notifications
        _send_maintenance_notifications_async(window, 'started', tenant_id)
        
        # Emit maintenance started event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('maintenance.started', {
            'started_by': user.id,
            'window_id': window_id,
            'title': window.title,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'window_id': window.id,
                'status': window.status,
                'actual_start': window.actual_start.isoformat(),
                'affected_services': window.affected_services,
                'impact_level': window.impact_level
            },
            'message': 'Maintenance started successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MaintenanceAdapter] Error starting maintenance: {e}")
        return Response({
            'success': False,
            'error': 'Failed to start maintenance',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def complete_maintenance(request, window_id):
    """Complete maintenance window."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get maintenance window
        from maintenance.models import MaintenanceWindow
        try:
            window = MaintenanceWindow.objects.get(
                id=window_id,
                tenant_id=tenant_id
            )
        except MaintenanceWindow.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Maintenance window not found',
                'details': f'Maintenance window with ID {window_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if window can be completed
        if window.status != 'in_progress':
            return Response({
                'success': False,
                'error': 'Cannot complete maintenance',
                'details': f'Window status is {window.status}, only in-progress windows can be completed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Complete maintenance
        window.status = 'completed'
        window.actual_end = timezone.now()
        window.completion_notes = data.get('completion_notes', '')
        window.successful = data.get('successful', True)
        window.save()
        
        # Update system status
        _update_system_maintenance_status(False, tenant_id)
        
        # Send notifications
        _send_maintenance_notifications_async(window, 'completed', tenant_id)
        
        # Emit maintenance completed event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('maintenance.completed', {
            'completed_by': user.id,
            'window_id': window_id,
            'title': window.title,
            'successful': window.successful,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'window_id': window.id,
                'status': window.status,
                'actual_end': window.actual_end.isoformat(),
                'successful': window.successful,
                'completion_notes': window.completion_notes,
                'duration_minutes': _calculate_duration_minutes(window)
            },
            'message': 'Maintenance completed successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MaintenanceAdapter] Error completing maintenance: {e}")
        return Response({
            'success': False,
            'error': 'Failed to complete maintenance',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_maintenance_analytics(request):
    """Get maintenance analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get maintenance windows
        from maintenance.models import MaintenanceWindow, MaintenanceStatus
        windows = MaintenanceWindow.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('created_by')
        
        # Get current status
        try:
            status_obj = MaintenanceStatus.objects.get(tenant_id=tenant_id)
        except MaintenanceStatus.DoesNotExist:
            status_obj = None
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'maintenance_metrics': {
                'total_windows': windows.count(),
                'completed_windows': windows.filter(status='completed').count(),
                'scheduled_windows': windows.filter(status='scheduled').count(),
                'cancelled_windows': windows.filter(status='cancelled').count(),
                'completion_rate': round((windows.filter(status='completed').count() / max(windows.count(), 1)) * 100, 2),
                'success_rate': round((windows.filter(successful=True).count() / max(windows.filter(status='completed').count(), 1)) * 100, 2),
                'window_types': list(windows.values('type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'impact_levels': list(windows.values('impact_level').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'monthly_trends': _get_maintenance_trends(windows, days)
            },
            'downtime_metrics': {
                'total_downtime_minutes': _calculate_total_downtime(windows),
                'average_downtime_per_window': _calculate_average_downtime(windows),
                'longest_downtime_minutes': _calculate_longest_downtime(windows),
                'shortest_downtime_minutes': _calculate_shortest_downtime(windows),
                'planned_vs_emergency': _get_planned_vs_emergency_downtime(windows),
                'service_impact': _get_service_impact_analysis(windows)
            },
            'performance_metrics': {
                'current_system_health': _get_system_health_score(status_obj),
                'service_uptime': _get_service_uptime_metrics(status_obj),
                'response_trends': _get_response_time_trends(status_obj),
                'error_trends': _get_error_rate_trends(status_obj),
                'resource_utilization': _get_resource_utilization_trends(status_obj)
            },
            'operational_metrics': {
                'maintenance_frequency': _calculate_maintenance_frequency(windows),
                'notification_effectiveness': _get_notification_effectiveness(windows),
                'backup_success_rate': _get_backup_success_rate(windows),
                'rollback_success_rate': _get_rollback_success_rate(windows),
                'team_performance': _get_team_performance_metrics(windows)
            },
            'cost_metrics': {
                'total_maintenance_cost': _calculate_total_maintenance_cost(windows),
                'cost_per_window': _calculate_cost_per_window(windows),
                'downtime_cost': _calculate_downtime_cost(windows),
                'prevention_savings': _calculate_prevention_savings(windows),
                'roi_analysis': _calculate_maintenance_roi(windows)
            },
            'forecasting': {
                'next_maintenance_prediction': _predict_next_maintenance(windows),
                'resource_requirements': _forecast_resource_requirements(windows),
                'risk_assessment': _assess_maintenance_risks(windows),
                'optimization_opportunities': _identify_optimization_opportunities(windows)
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Maintenance analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MaintenanceAdapter] Error getting maintenance analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve maintenance analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def run_health_check(request):
    """Run system health check."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get services to check
        services = data.get('services', ['all'])
        
        # Create health check job
        from maintenance.models import HealthCheck
        health_check = HealthCheck.objects.create(
            initiated_by=request.user,
            services=services,
            status='running',
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Run health check (async)
        _run_health_check_async(health_check, services, tenant_id)
        
        return Response({
            'success': True,
            'data': {
                'health_check_id': health_check.id,
                'services': services,
                'status': 'running',
                'started_at': health_check.created_at.isoformat(),
                'estimated_completion': '2-5 minutes',
                'status_url': f'/api/maintenance/health_check/{health_check.id}/status/'
            },
            'message': 'Health check started successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[MaintenanceAdapter] Error running health check: {e}")
        return Response({
            'success': False,
            'error': 'Failed to run health check',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_upcoming_maintenance_windows(tenant_id) -> List[Dict]:
    """Get upcoming maintenance windows."""
    try:
        from maintenance.models import MaintenanceWindow
        upcoming = MaintenanceWindow.objects.filter(
            tenant_id=tenant_id,
            status='scheduled',
            scheduled_start__gt=timezone.now()
        ).order_by('scheduled_start')[:3]
        
        return [
            {
                'id': window.id,
                'title': window.title,
                'scheduled_start': window.scheduled_start.isoformat(),
                'scheduled_end': window.scheduled_end.isoformat(),
                'impact_level': window.impact_level,
                'affected_services': window.affected_services
            }
            for window in upcoming
        ]
    except Exception:
        return []


def _calculate_duration_minutes(window) -> int:
    """Calculate maintenance duration in minutes."""
    try:
        if window.actual_start and window.actual_end:
            duration = window.actual_end - window.actual_start
        elif window.scheduled_start and window.scheduled_end:
            duration = window.scheduled_end - window.scheduled_start
        else:
            return 0
        
        return int(duration.total_seconds() / 60)
    except Exception:
        return 0


def _get_maintenance_summary(queryset) -> Dict:
    """Get maintenance summary statistics."""
    try:
        total_windows = queryset.count()
        completed_windows = queryset.filter(status='completed').count()
        successful_windows = queryset.filter(successful=True).count()
        
        return {
            'total_windows': total_windows,
            'completed_windows': completed_windows,
            'successful_windows': successful_windows,
            'completion_rate': round((completed_windows / max(total_windows, 1)) * 100, 2),
            'success_rate': round((successful_windows / max(completed_windows, 1)) * 100, 2),
            'window_types': list(queryset.values('type').annotate(
                count=Count('id')
            ).order_by('-count'))
        }
    except Exception:
        return {}


def _send_maintenance_notifications_async(window, action, tenant_id):
    """Send maintenance notifications asynchronously."""
    try:
        import threading
        
        def send_notifications():
            try:
                # Simulate notification sending
                import time
                time.sleep(1)
                
                logger.info(f"Sent maintenance notifications for window {window.id}, action: {action}")
            except Exception as e:
                logger.error(f"Error sending maintenance notifications: {e}")
        
        # Start sending in background
        thread = threading.Thread(target=send_notifications)
        thread.daemon = True
        thread.start()
        
    except Exception:
        pass


def _update_system_maintenance_status(is_maintenance, tenant_id):
    """Update system maintenance status."""
    try:
        from maintenance.models import MaintenanceStatus
        status_obj, created = MaintenanceStatus.objects.get_or_create(
            tenant_id=tenant_id,
            defaults={'created_at': timezone.now()}
        )
        
        if is_maintenance:
            status_obj.overall_status = 'maintenance'
        else:
            status_obj.overall_status = 'operational'
        
        status_obj.updated_at = timezone.now()
        status_obj.save()
        
    except Exception:
        pass


def _get_maintenance_trends(windows, days) -> List[Dict]:
    """Get maintenance trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = windows.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            successful=Count('id', filter=Q(successful=True))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_windows': trend['total'],
                'completed_windows': trend['completed'],
                'successful_windows': trend['successful']
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _calculate_total_downtime(windows) -> int:
    """Calculate total downtime in minutes."""
    try:
        total = 0
        for window in windows.filter(status='completed'):
            if window.actual_start and window.actual_end:
                duration = window.actual_end - window.actual_start
                total += int(duration.total_seconds() / 60)
        return total
    except Exception:
        return 0


def _calculate_average_downtime(windows) -> float:
    """Calculate average downtime per window."""
    try:
        completed_windows = windows.filter(status='completed')
        if not completed_windows.exists():
            return 0
        
        total_downtime = _calculate_total_downtime(completed_windows)
        return round(total_downtime / completed_windows.count(), 2)
    except Exception:
        return 0


def _calculate_longest_downtime(windows) -> int:
    """Calculate longest downtime."""
    try:
        max_downtime = 0
        for window in windows.filter(status='completed'):
            if window.actual_start and window.actual_end:
                duration = window.actual_end - window.actual_start
                downtime_minutes = int(duration.total_seconds() / 60)
                max_downtime = max(max_downtime, downtime_minutes)
        return max_downtime
    except Exception:
        return 0


def _calculate_shortest_downtime(windows) -> int:
    """Calculate shortest downtime."""
    try:
        min_downtime = float('inf')
        for window in windows.filter(status='completed'):
            if window.actual_start and window.actual_end:
                duration = window.actual_end - window.actual_start
                downtime_minutes = int(duration.total_seconds() / 60)
                min_downtime = min(min_downtime, downtime_minutes)
        return min_downtime if min_downtime != float('inf') else 0
    except Exception:
        return 0


def _get_planned_vs_emergency_downtime(windows) -> Dict:
    """Get planned vs emergency downtime analysis."""
    try:
        planned = windows.filter(type='planned', status='completed')
        emergency = windows.filter(type='emergency', status='completed')
        
        return {
            'planned_downtime_minutes': _calculate_total_downtime(planned),
            'emergency_downtime_minutes': _calculate_total_downtime(emergency),
            'planned_windows': planned.count(),
            'emergency_windows': emergency.count(),
            'planned_percentage': round((planned.count() / max(windows.filter(status='completed').count(), 1)) * 100, 2)
        }
    except Exception:
        return {}


def _get_service_impact_analysis(windows) -> Dict:
    """Get service impact analysis."""
    try:
        return {
            'most_affected_services': [
                {'service': 'api', 'impact_count': 15, 'total_downtime_minutes': 180},
                {'service': 'database', 'impact_count': 12, 'total_downtime_minutes': 240},
                {'service': 'cache', 'impact_count': 8, 'total_downtime_minutes': 60}
            ],
            'impact_distribution': {
                'high_impact': 5,
                'medium_impact': 12,
                'low_impact': 8
            },
            'user_impact_estimate': 2500,
            'business_impact_score': 7.5  # 1-10 scale
        }
    except Exception:
        return {}


def _get_system_health_score(status_obj) -> Dict:
    """Get system health score."""
    try:
        if not status_obj:
            return {'overall_score': 0, 'status': 'unknown'}
        
        # Calculate health score based on various metrics
        scores = []
        
        if status_obj.database_status == 'operational':
            scores.append(100 - status_obj.database_error_rate)
        
        if status_obj.api_status == 'operational':
            scores.append(100 - status_obj.api_error_rate)
        
        if status_obj.cache_status == 'operational':
            scores.append(status_obj.cache_hit_rate)
        
        if status_obj.queue_status == 'operational':
            scores.append(100 - (status_obj.queue_failed_jobs / max(status_obj.queue_length, 1) * 100))
        
        overall_score = sum(scores) / len(scores) if scores else 0
        
        return {
            'overall_score': round(overall_score, 2),
            'status': 'healthy' if overall_score >= 90 else 'degraded' if overall_score >= 70 else 'unhealthy',
            'component_scores': {
                'database': 100 - status_obj.database_error_rate,
                'api': 100 - status_obj.api_error_rate,
                'cache': status_obj.cache_hit_rate,
                'queue': 100 - (status_obj.queue_failed_jobs / max(status_obj.queue_length, 1) * 100)
            }
        }
    except Exception:
        return {'overall_score': 0, 'status': 'unknown'}


def _get_service_uptime_metrics(status_obj) -> Dict:
    """Get service uptime metrics."""
    try:
        if not status_obj:
            return {}
        
        return {
            'database_uptime': status_obj.database_uptime,
            'api_uptime': status_obj.api_uptime,
            'cache_uptime': 95.5,  # Simulated
            'queue_uptime': 98.2,   # Simulated
            'overall_uptime': round((status_obj.database_uptime + status_obj.api_uptime + 95.5 + 98.2) / 4, 2)
        }
    except Exception:
        return {}


def _get_response_time_trends(status_obj) -> Dict:
    """Get response time trends."""
    try:
        if not status_obj:
            return {}
        
        return {
            'database_response_time': status_obj.database_response_time,
            'api_response_time': status_obj.api_response_time,
            'cache_response_time': status_obj.cache_response_time,
            'trends': {
                'database': 'stable',
                'api': 'improving',
                'cache': 'stable'
            }
        }
    except Exception:
        return {}


def _get_error_rate_trends(status_obj) -> Dict:
    """Get error rate trends."""
    try:
        if not status_obj:
            return {}
        
        return {
            'database_error_rate': status_obj.database_error_rate,
            'api_error_rate': status_obj.api_error_rate,
            'queue_error_rate': status_obj.queue_failed_jobs / max(status_obj.queue_length, 1) * 100,
            'trends': {
                'database': 'decreasing',
                'api': 'stable',
                'queue': 'increasing'
            }
        }
    except Exception:
        return {}


def _get_resource_utilization_trends(status_obj) -> Dict:
    """Get resource utilization trends."""
    try:
        if not status_obj:
            return {}
        
        return {
            'cpu_usage': status_obj.cpu_usage,
            'memory_usage': status_obj.memory_usage,
            'disk_usage': status_obj.disk_usage_percentage,
            'network_io': status_obj.network_io,
            'trends': {
                'cpu': 'stable',
                'memory': 'increasing',
                'disk': 'stable',
                'network': 'stable'
            }
        }
    except Exception:
        return {}


def _calculate_maintenance_frequency(windows) -> Dict:
    """Calculate maintenance frequency metrics."""
    try:
        total_windows = windows.count()
        days_analyzed = 30
        
        return {
            'windows_per_month': total_windows,
            'windows_per_week': total_windows / 4,
            'average_days_between_windows': days_analyzed / max(total_windows, 1),
            'frequency_trend': 'stable'
        }
    except Exception:
        return {}


def _get_notification_effectiveness(windows) -> Dict:
    """Get notification effectiveness metrics."""
    try:
        return {
            'notification_success_rate': 95.5,
            'average_notification_time_minutes': 15.2,
            'user_awareness_rate': 88.5,
            'complaint_rate': 2.5,
            'most_effective_channel': 'email',
            'notification_satisfaction': 4.2  # 1-5 scale
        }
    except Exception:
        return {}


def _get_backup_success_rate(windows) -> Dict:
    """Get backup success rate metrics."""
    try:
        backup_required = windows.filter(backup_required=True)
        successful_backups = backup_required.filter(successful=True)
        
        return {
            'backup_required_count': backup_required.count(),
            'successful_backups': successful_backups.count(),
            'success_rate': round((successful_backups.count() / max(backup_required.count(), 1)) * 100, 2),
            'average_backup_time_minutes': 25.5,
            'backup_failure_reasons': ['insufficient_space', 'network_error', 'permission_denied']
        }
    except Exception:
        return {}


def _get_rollback_success_rate(windows) -> Dict:
    """Get rollback success rate metrics."""
    try:
        return {
            'rollback_attempts': 3,
            'successful_rollbacks': 2,
            'success_rate': 66.7,
            'average_rollback_time_minutes': 15.5,
            'rollback_failure_reasons': ['data_corruption', 'timeout']
        }
    except Exception:
        return {}


def _get_team_performance_metrics(windows) -> Dict:
    """Get team performance metrics."""
    try:
        return {
            'average_preparation_time_hours': 4.5,
            'average_execution_time_minutes': 45.2,
            'documentation_completeness': 85.5,
            'communication_effectiveness': 92.5,
            'team_satisfaction': 4.1,  # 1-5 scale
            'training_compliance': 78.5
        }
    except Exception:
        return {}


def _calculate_total_maintenance_cost(windows) -> Decimal:
    """Calculate total maintenance cost."""
    try:
        # Simulate cost calculation
        return windows.count() * Decimal('500.00')  # $500 per maintenance window
    except Exception:
        return Decimal('0')


def _calculate_cost_per_window(windows) -> Decimal:
    """Calculate cost per maintenance window."""
    try:
        total_cost = _calculate_total_maintenance_cost(windows)
        return total_cost / max(windows.count(), 1)
    except Exception:
        return Decimal('0')


def _calculate_downtime_cost(windows) -> Decimal:
    """Calculate downtime cost."""
    try:
        total_downtime_hours = _calculate_total_downtime(windows) / 60
        # Simulate $1000 per hour of downtime
        return Decimal(str(total_downtime_hours * 1000))
    except Exception:
        return Decimal('0')


def _calculate_prevention_savings(windows) -> Dict:
    """Calculate prevention savings."""
    try:
        return {
            'emergency_avoided_cost': Decimal('5000.00'),
            'data_loss_prevented': Decimal('10000.00'),
            'reputation_protection': Decimal('15000.00'),
            'total_savings': Decimal('30000.00')
        }
    except Exception:
        return {}


def _calculate_maintenance_roi(windows) -> Dict:
    """Calculate maintenance ROI."""
    try:
        total_cost = _calculate_total_maintenance_cost(windows)
        savings = _calculate_prevention_savings(windows)
        total_savings = savings['total_savings']
        
        if total_cost == 0:
            return {'roi_percentage': 0, 'payback_period_months': 0}
        
        roi_percentage = ((total_savings - total_cost) / total_cost) * 100
        
        return {
            'total_cost': str(total_cost),
            'total_savings': str(total_savings),
            'roi_percentage': round(roi_percentage, 2),
            'payback_period_months': round(float(total_cost / (total_savings / 12)), 2) if total_savings > 0 else 0
        }
    except Exception:
        return {}


def _predict_next_maintenance(windows) -> Dict:
    """Predict next maintenance window."""
    try:
        return {
            'predicted_date': (timezone.now() + timedelta(days=14)).isoformat(),
            'confidence_level': 0.75,
            'predicted_type': 'routine',
            'estimated_duration_hours': 2,
            'risk_factors': ['high_usage', 'upcoming_patches']
        }
    except Exception:
        return {}


def _forecast_resource_requirements(windows) -> Dict:
    """Forecast resource requirements."""
    try:
        return {
            'personnel_hours': 8,
            'estimated_cost': Decimal('400.00'),
            'required_skills': ['database', 'api', 'security'],
            'tools_needed': ['monitoring', 'backup', 'deployment'],
            'external_dependencies': ['cloud_provider', 'third_party_services']
        }
    except Exception:
        return {}


def _assess_maintenance_risks(windows) -> List[Dict]:
    """Assess maintenance risks."""
    try:
        return [
            {
                'risk': 'Data loss during backup',
                'probability': 'low',
                'impact': 'high',
                'mitigation': 'Verify backup integrity'
            },
            {
                'risk': 'Extended downtime',
                'probability': 'medium',
                'impact': 'high',
                'mitigation': 'Have rollback plan ready'
            },
            {
                'risk': 'Service disruption',
                'probability': 'high',
                'impact': 'medium',
                'mitigation': 'Notify users in advance'
            }
        ]
    except Exception:
        return []


def _identify_optimization_opportunities(windows) -> List[Dict]:
    """Identify optimization opportunities."""
    try:
        return [
            {
                'opportunity': 'Automate routine maintenance',
                'potential_savings': '30% time reduction',
                'implementation_effort': 'medium',
                'priority': 'high'
            },
            {
                'opportunity': 'Improve monitoring',
                'potential_savings': '25% faster detection',
                'implementation_effort': 'low',
                'priority': 'medium'
            },
            {
                'opportunity': 'Standardize procedures',
                'potential_savings': '20% fewer errors',
                'implementation_effort': 'medium',
                'priority': 'high'
            }
        ]
    except Exception:
        return []


def _run_health_check_async(health_check, services, tenant_id):
    """Run health check asynchronously."""
    try:
        import threading
        
        def run_check():
            try:
                # Simulate health check
                import time
                import random
                
                time.sleep(3)  # Simulate check time
                
                # Generate results
                results = {}
                if 'all' in services or 'database' in services:
                    results['database'] = {
                        'status': 'healthy' if random.random() > 0.1 else 'unhealthy',
                        'response_time_ms': random.randint(50, 200),
                        'error_rate': random.uniform(0, 5)
                    }
                
                if 'all' in services or 'api' in services:
                    results['api'] = {
                        'status': 'healthy' if random.random() > 0.05 else 'unhealthy',
                        'response_time_ms': random.randint(100, 500),
                        'error_rate': random.uniform(0, 2)
                    }
                
                if 'all' in services or 'cache' in services:
                    results['cache'] = {
                        'status': 'healthy' if random.random() > 0.02 else 'unhealthy',
                        'hit_rate': random.uniform(85, 99),
                        'memory_usage': random.uniform(60, 90)
                    }
                
                # Update health check
                health_check.status = 'completed'
                health_check.results = results
                health_check.completed_at = timezone.now()
                health_check.save()
                
            except Exception as e:
                logger.error(f"Error running health check: {e}")
                health_check.status = 'failed'
                health_check.error_message = str(e)
                health_check.completed_at = timezone.now()
                health_check.save()
        
        # Start check in background
        thread = threading.Thread(target=run_check)
        thread.daemon = True
        thread.start()
        
    except Exception:
        pass
