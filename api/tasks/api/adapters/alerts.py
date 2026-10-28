"""
api/adapters/alerts.py
Alerts adapter for earning backend platform
"""
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
def get_user_alerts(request):
    """Get user's alerts."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        alert_type = request.GET.get('type')  # 'all', 'system', 'security', 'payment', 'task', 'account'
        status = request.GET.get('status')  # 'all', 'unread', 'read', 'archived'
        priority = request.GET.get('priority')  # 'all', 'low', 'medium', 'high', 'critical'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get alerts
        from alerts.models import UserAlert
        queryset = UserAlert.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if alert_type and alert_type != 'all':
            queryset = queryset.filter(alert_type=alert_type)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if priority and priority != 'all':
            queryset = queryset.filter(priority=priority)
        
        # Paginate
        alerts = queryset[offset:offset+limit]
        
        # Serialize alerts
        alert_data = []
        for alert in alerts:
            alert_data.append({
                'id': alert.id,
                'alert_type': alert.alert_type,
                'title': alert.title,
                'message': alert.message,
                'priority': alert.priority,
                'status': alert.status,
                'created_at': alert.created_at.isoformat(),
                'read_at': alert.read_at.isoformat() if alert.read_at else None,
                'expires_at': alert.expires_at.isoformat() if alert.expires_at else None,
                'action_required': alert.action_required,
                'action_url': alert.action_url,
                'action_data': alert.action_data,
                'metadata': alert.metadata,
                'is_critical': alert.priority == 'critical',
                'is_unread': alert.status == 'unread',
                'is_expired': alert.expires_at and alert.expires_at < timezone.now()
            })
        
        return Response({
            'success': True,
            'data': {
                'alerts': alert_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(alert_data) == limit
                },
                'filters': {
                    'type': alert_type,
                    'status': status,
                    'priority': priority
                },
                'summary': _get_alert_summary(queryset)
            },
            'message': 'Alerts retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error getting user alerts: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve alerts',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_alert_read(request, alert_id):
    """Mark alert as read."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get alert
        from alerts.models import UserAlert
        try:
            alert = UserAlert.objects.get(
                id=alert_id,
                user=user,
                tenant_id=tenant_id
            )
        except UserAlert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Alert not found',
                'details': f'Alert with ID {alert_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update alert status
        alert.status = 'read'
        alert.read_at = timezone.now()
        alert.save()
        
        # Update unread count cache
        _update_unread_count(user, tenant_id)
        
        # Emit alert read event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('alerts.alert_read', {
            'user_id': user.id,
            'alert_id': alert_id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'alert_id': alert_id,
                'status': 'read',
                'read_at': alert.read_at.isoformat(),
                'unread_count': _get_unread_count(user, tenant_id)
            },
            'message': 'Alert marked as read successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error marking alert read: {e}")
        return Response({
            'success': False,
            'error': 'Failed to mark alert as read',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_alerts_read(request):
    """Mark all alerts as read."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get unread alerts
        from alerts.models import UserAlert
        unread_alerts = UserAlert.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='unread'
        )
        
        # Mark all as read
        updated_count = unread_alerts.update(
            status='read',
            read_at=timezone.now()
        )
        
        # Update unread count cache
        _update_unread_count(user, tenant_id)
        
        # Emit alerts read event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('alerts.all_alerts_read', {
            'user_id': user.id,
            'alerts_count': updated_count,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'alerts_marked': updated_count,
                'unread_count': 0,
                'marked_at': timezone.now().isoformat()
            },
            'message': f'{updated_count} alerts marked as read successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error marking all alerts read: {e}")
        return Response({
            'success': False,
            'error': 'Failed to mark all alerts as read',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def archive_alert(request, alert_id):
    """Archive alert."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get alert
        from alerts.models import UserAlert
        try:
            alert = UserAlert.objects.get(
                id=alert_id,
                user=user,
                tenant_id=tenant_id
            )
        except UserAlert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Alert not found',
                'details': f'Alert with ID {alert_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update alert status
        alert.status = 'archived'
        alert.archived_at = timezone.now()
        alert.save()
        
        # Update unread count cache
        _update_unread_count(user, tenant_id)
        
        # Emit alert archived event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('alerts.alert_archived', {
            'user_id': user.id,
            'alert_id': alert_id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'alert_id': alert_id,
                'status': 'archived',
                'archived_at': alert.archived_at.isoformat(),
                'unread_count': _get_unread_count(user, tenant_id)
            },
            'message': 'Alert archived successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error archiving alert: {e}")
        return Response({
            'success': False,
            'error': 'Failed to archive alert',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_alert(request):
    """Create a new alert (for system/internal use)."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'message', 'alert_type']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check user permissions for creating alerts
        if not _can_create_alert(user):
            return Response({
                'success': False,
                'error': 'Permission denied',
                'details': 'You do not have permission to create alerts'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Create alert
        from alerts.models import UserAlert
        alert = UserAlert.objects.create(
            user=user,
            title=data['title'],
            message=data['message'],
            alert_type=data['alert_type'],
            priority=data.get('priority', 'medium'),
            status='unread',
            action_required=data.get('action_required', False),
            action_url=data.get('action_url', ''),
            action_data=data.get('action_data', {}),
            expires_at=timezone.now() + timedelta(days=30) if data.get('expires_in_days') else None,
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Update unread count cache
        _update_unread_count(user, tenant_id)
        
        # Emit alert created event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('alerts.alert_created', {
            'user_id': user.id,
            'alert_id': alert.id,
            'alert_type': data['alert_type'],
            'priority': data.get('priority', 'medium'),
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'alert_id': alert.id,
                'title': alert.title,
                'alert_type': alert.alert_type,
                'priority': alert.priority,
                'created_at': alert.created_at.isoformat(),
                'unread_count': _get_unread_count(user, tenant_id)
            },
            'message': 'Alert created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error creating alert: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create alert',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_alert_preferences(request):
    """Get user's alert preferences."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get alert preferences
        from alerts.models import AlertPreference
        try:
            preferences = AlertPreference.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except AlertPreference.DoesNotExist:
            # Create default preferences
            preferences = AlertPreference.objects.create(
                user=user,
                tenant_id=tenant_id,
                email_enabled=True,
                push_enabled=True,
                sms_enabled=False,
                in_app_enabled=True,
                preferences=_get_default_alert_preferences(),
                created_at=timezone.now()
            )
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'tenant_id': tenant_id,
                'email_enabled': preferences.email_enabled,
                'push_enabled': preferences.push_enabled,
                'sms_enabled': preferences.sms_enabled,
                'in_app_enabled': preferences.in_app_enabled,
                'preferences': preferences.preferences,
                'quiet_hours': {
                    'enabled': preferences.quiet_hours_enabled,
                    'start_time': preferences.quiet_hours_start,
                    'end_time': preferences.quiet_hours_end,
                },
                'frequency_limits': {
                    'max_per_hour': preferences.max_alerts_per_hour,
                    'max_per_day': preferences.max_alerts_per_day,
                }
            },
            'message': 'Alert preferences retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error getting alert preferences: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve alert preferences',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_alert_preferences(request):
    """Update user's alert preferences."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get alert preferences
        from alerts.models import AlertPreference
        try:
            preferences = AlertPreference.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except AlertPreference.DoesNotExist:
            # Create default preferences
            preferences = AlertPreference.objects.create(
                user=user,
                tenant_id=tenant_id,
                preferences=_get_default_alert_preferences(),
                created_at=timezone.now()
            )
        
        # Update preferences
        if 'email_enabled' in data:
            preferences.email_enabled = data['email_enabled']
        if 'push_enabled' in data:
            preferences.push_enabled = data['push_enabled']
        if 'sms_enabled' in data:
            preferences.sms_enabled = data['sms_enabled']
        if 'in_app_enabled' in data:
            preferences.in_app_enabled = data['in_app_enabled']
        if 'preferences' in data:
            preferences.preferences = data['preferences']
        if 'quiet_hours_enabled' in data:
            preferences.quiet_hours_enabled = data['quiet_hours_enabled']
        if 'quiet_hours_start' in data:
            preferences.quiet_hours_start = data['quiet_hours_start']
        if 'quiet_hours_end' in data:
            preferences.quiet_hours_end = data['quiet_hours_end']
        if 'max_alerts_per_hour' in data:
            preferences.max_alerts_per_hour = data['max_alerts_per_hour']
        if 'max_alerts_per_day' in data:
            preferences.max_alerts_per_day = data['max_alerts_per_day']
        
        preferences.updated_at = timezone.now()
        preferences.save()
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'updated_at': preferences.updated_at.isoformat(),
                'preferences': {
                    'email_enabled': preferences.email_enabled,
                    'push_enabled': preferences.push_enabled,
                    'sms_enabled': preferences.sms_enabled,
                    'in_app_enabled': preferences.in_app_enabled,
                    'preferences': preferences.preferences,
                    'quiet_hours': {
                        'enabled': preferences.quiet_hours_enabled,
                        'start_time': preferences.quiet_hours_start,
                        'end_time': preferences.quiet_hours_end,
                    }
                }
            },
            'message': 'Alert preferences updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error updating alert preferences: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update alert preferences',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_system_alerts(request):
    """Get system-wide alerts for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        alert_type = request.GET.get('type')  # 'all', 'system', 'security', 'payment', 'task'
        status = request.GET.get('status')  # 'all', 'active', 'resolved'
        priority = request.GET.get('priority')  # 'all', 'low', 'medium', 'high', 'critical'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get system alerts
        from alerts.models import SystemAlert
        queryset = SystemAlert.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if alert_type and alert_type != 'all':
            queryset = queryset.filter(alert_type=alert_type)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if priority and priority != 'all':
            queryset = queryset.filter(priority=priority)
        
        # Paginate
        alerts = queryset[offset:offset+limit]
        
        # Serialize alerts
        alert_data = []
        for alert in alerts:
            alert_data.append({
                'id': alert.id,
                'alert_type': alert.alert_type,
                'title': alert.title,
                'message': alert.message,
                'priority': alert.priority,
                'status': alert.status,
                'affected_users': alert.affected_users,
                'created_at': alert.created_at.isoformat(),
                'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                'resolved_by': {
                    'id': alert.resolved_by.id,
                    'username': alert.resolved_by.username,
                } if alert.resolved_by else None,
                'resolution_note': alert.resolution_note,
                'metadata': alert.metadata,
                'is_critical': alert.priority == 'critical',
                'is_active': alert.status == 'active'
            })
        
        return Response({
            'success': True,
            'data': {
                'alerts': alert_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(alert_data) == limit
                },
                'filters': {
                    'type': alert_type,
                    'status': status,
                    'priority': priority
                },
                'summary': _get_system_alert_summary(queryset)
            },
            'message': 'System alerts retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error getting system alerts: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve system alerts',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_system_alert(request):
    """Create a new system alert."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'message', 'alert_type']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create system alert
        from alerts.models import SystemAlert
        alert = SystemAlert.objects.create(
            title=data['title'],
            message=data['message'],
            alert_type=data['alert_type'],
            priority=data.get('priority', 'medium'),
            status='active',
            affected_users=data.get('affected_users', 'all'),
            created_by=user,
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Send notifications to affected users
        _send_system_alert_notifications(alert, tenant_id)
        
        # Emit system alert created event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('alerts.system_alert_created', {
            'user_id': user.id,
            'alert_id': alert.id,
            'alert_type': data['alert_type'],
            'priority': data.get('priority', 'medium'),
            'affected_users': data.get('affected_users', 'all'),
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'alert_id': alert.id,
                'title': alert.title,
                'alert_type': alert.alert_type,
                'priority': alert.priority,
                'affected_users': alert.affected_users,
                'created_at': alert.created_at.isoformat()
            },
            'message': 'System alert created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error creating system alert: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create system alert',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_alert_summary(queryset) -> Dict:
    """Get alert summary statistics."""
    try:
        total_alerts = queryset.count()
        unread_alerts = queryset.filter(status='unread').count()
        critical_alerts = queryset.filter(priority='critical', status='unread').count()
        
        return {
            'total_alerts': total_alerts,
            'unread_alerts': unread_alerts,
            'read_alerts': total_alerts - unread_alerts,
            'critical_unread': critical_alerts,
            'unread_percentage': round((unread_alerts / max(total_alerts, 1)) * 100, 2),
            'alert_types': list(queryset.values('alert_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'priority_breakdown': list(queryset.values('priority').annotate(
                count=Count('id')
            ).order_by('-count'))
        }
    except Exception:
        return {}


def _get_system_alert_summary(queryset) -> Dict:
    """Get system alert summary statistics."""
    try:
        total_alerts = queryset.count()
        active_alerts = queryset.filter(status='active').count()
        critical_alerts = queryset.filter(priority='critical', status='active').count()
        
        return {
            'total_alerts': total_alerts,
            'active_alerts': active_alerts,
            'resolved_alerts': queryset.filter(status='resolved').count(),
            'critical_active': critical_alerts,
            'active_percentage': round((active_alerts / max(total_alerts, 1)) * 100, 2),
            'alert_types': list(queryset.values('alert_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'priority_breakdown': list(queryset.values('priority').annotate(
                count=Count('id')
            ).order_by('-count')),
            'recent_resolutions': list(queryset.filter(
                status='resolved',
                resolved_at__isnull=False
            ).order_by('-resolved_at')[:5])
        }
    except Exception:
        return {}


def _get_unread_count(user, tenant_id) -> int:
    """Get unread alert count for user."""
    try:
        from alerts.models import UserAlert
        count = cache.get(f'unread_alerts_{user.id}')
        if count is None:
            count = UserAlert.objects.filter(
                user=user,
                tenant_id=tenant_id,
                status='unread'
            ).count()
            cache.set(f'unread_alerts_{user.id}', count, timeout=300)  # 5 minutes
        return count
    except Exception:
        return 0


def _update_unread_count(user, tenant_id):
    """Update unread alert count cache."""
    try:
        cache.delete(f'unread_alerts_{user.id}')
        _get_unread_count(user, tenant_id)  # Recalculate and cache
    except Exception:
        pass


def _can_create_alert(user) -> bool:
    """Check if user can create alerts."""
    try:
        # Admin users can always create alerts
        if user.is_staff:
            return True
        
        # Check user level and permissions
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if ctx.user_level >= 3:
            return True
        
        return False
    except Exception:
        return False


def _get_default_alert_preferences() -> Dict:
    """Get default alert preferences."""
    return {
        'system': {
            'enabled': True,
            'priority': ['high', 'critical'],
            'channels': ['in_app', 'email']
        },
        'security': {
            'enabled': True,
            'priority': ['medium', 'high', 'critical'],
            'channels': ['in_app', 'email', 'push']
        },
        'payment': {
            'enabled': True,
            'priority': ['medium', 'high'],
            'channels': ['in_app', 'email']
        },
        'task': {
            'enabled': True,
            'priority': ['low', 'medium', 'high'],
            'channels': ['in_app']
        },
        'account': {
            'enabled': True,
            'priority': ['medium', 'high'],
            'channels': ['in_app', 'email']
        }
    }


def _send_system_alert_notifications(alert, tenant_id):
    """Send notifications for system alert."""
    try:
        # Get affected users
        if alert.affected_users == 'all':
            from django.contrib.auth import get_user_model
            User = get_user_model()
            users = User.objects.filter(tenant_id=tenant_id, is_active=True)
        else:
            # Handle specific user groups or filters
            users = []
        
        # Create user alerts for each affected user
        from alerts.models import UserAlert
        for user in users:
            UserAlert.objects.create(
                user=user,
                title=alert.title,
                message=alert.message,
                alert_type='system',
                priority=alert.priority,
                status='unread',
                action_required=alert.metadata.get('action_required', False),
                action_url=alert.metadata.get('action_url', ''),
                action_data=alert.metadata,
                expires_at=timezone.now() + timedelta(days=30),
                metadata={'system_alert_id': alert.id},
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Log notification sending
        logger.info(f"System alert {alert.id} sent to {len(users)} users")
        
    except Exception as e:
        logger.error(f"[AlertsAdapter] Error sending system alert notifications: {e}")
        pass
