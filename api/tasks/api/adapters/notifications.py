"""
api/adapters/notifications.py
Notifications adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """Get user's notifications."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        notification_type = request.GET.get('type')  # 'all', 'unread', 'system', 'task', 'payment'
        is_read = request.GET.get('read')  # 'all', 'read', 'unread'
        
        # Get notifications
        from notifications.models import Notification
        queryset = Notification.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if notification_type and notification_type != 'all':
            queryset = queryset.filter(notification_type=notification_type)
        
        if is_read == 'read':
            queryset = queryset.filter(is_read=True)
        elif is_read == 'unread':
            queryset = queryset.filter(is_read=False)
        
        # Paginate
        notifications = queryset[offset:offset+limit]
        
        # Serialize notifications
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'data': notification.data,
                'is_read': notification.is_read,
                'priority': notification.priority,
                'created_at': notification.created_at.isoformat(),
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'expires_at': notification.expires_at.isoformat() if notification.expires_at else None,
                'action_required': notification.action_required,
                'action_url': notification.action_url,
                'metadata': notification.metadata
            })
        
        # Get counts
        unread_count = Notification.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_read=False
        ).count()
        
        return Response({
            'success': True,
            'data': {
                'notifications': notification_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(notification_data) == limit
                },
                'counts': {
                    'total': queryset.count(),
                    'unread': unread_count,
                    'read': queryset.count() - unread_count,
                    'by_type': _get_notification_counts(user, tenant_id)
                },
                'filters': {
                    'type': notification_type,
                    'read': is_read
                }
            },
            'message': 'Notifications retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[NotificationsAdapter] Error getting notifications: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve notifications',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark notification as read."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get notification
        from notifications.models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=user,
                tenant_id=tenant_id
            )
        except Notification.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Notification not found',
                'details': f'Notification with ID {notification_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Mark as read
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            
            # Emit notification read event
            from api.tasks.integration.event_bus import EventBus
            EventBus.emit('notification.read', {
                'user_id': user.id,
                'notification_id': notification.id,
                'notification_type': notification.notification_type,
                'tenant_id': tenant_id
            })
        
        return Response({
            'success': True,
            'data': {
                'notification_id': notification.id,
                'is_read': notification.is_read,
                'read_at': notification.read_at.isoformat() if notification.read_at else None
            },
            'message': 'Notification marked as read successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[NotificationsAdapter] Error marking notification read: {e}")
        return Response({
            'success': False,
            'error': 'Failed to mark notification as read',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """Mark all notifications as read."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get unread notifications
        from notifications.models import Notification
        unread_notifications = Notification.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_read=False
        )
        
        # Mark all as read
        updated_count = unread_notifications.update(
            is_read=True,
            read_at=timezone.now()
        )
        
        # Emit bulk read event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('notifications.bulk_read', {
            'user_id': user.id,
            'count': updated_count,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'updated_count': updated_count,
                'message': f'{updated_count} notifications marked as read'
            },
            'message': 'All notifications marked as read successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[NotificationsAdapter] Error marking all notifications read: {e}")
        return Response({
            'success': False,
            'error': 'Failed to mark all notifications as read',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_notification(request):
    """Create a custom notification (for testing/admin)."""
    try:
        user = request.user
        data = request.data
        
        title = data.get('title')
        message = data.get('message')
        notification_type = data.get('type', 'custom')
        priority = data.get('priority', 'normal')
        
        if not title or not message:
            return Response({
                'success': False,
                'error': 'Title and message required',
                'details': 'Please provide title and message'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create notification
        from notifications.models import Notification
        notification = Notification.objects.create(
            user=user,
            tenant_id=getattr(request, 'tenant_id', None),
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            created_at=timezone.now()
        )
        
        return Response({
            'success': True,
            'data': {
                'notification_id': notification.id,
                'title': title,
                'message': message,
                'type': notification_type,
                'priority': priority,
                'created_at': notification.created_at.isoformat()
            },
            'message': 'Notification created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[NotificationsAdapter] Error creating notification: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create notification',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a notification."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get notification
        from notifications.models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=user,
                tenant_id=tenant_id
            )
        except Notification.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Notification not found',
                'details': f'Notification with ID {notification_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Delete notification
        notification.delete()
        
        return Response({
            'success': True,
            'data': {
                'notification_id': notification_id,
                'deleted_at': timezone.now().isoformat()
            },
            'message': 'Notification deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[NotificationsAdapter] Error deleting notification: {e}")
        return Response({
            'success': False,
            'error': 'Failed to delete notification',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_settings(request):
    """Get user's notification settings."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's notification preferences
        settings = cache.get(f'notification_settings_{user.id}', {
            'email_notifications': True,
            'push_notifications': True,
            'sms_notifications': False,
            'in_app_notifications': True,
            'task_notifications': True,
            'payment_notifications': True,
            'referral_notifications': True,
            'security_notifications': True,
            'marketing_notifications': False,
            'quiet_hours': {
                'enabled': False,
                'start': '22:00',
                'end': '08:00'
            },
            'frequency': {
                'max_per_hour': 10,
                'max_per_day': 100,
                'cooldown_minutes': 5
            }
        })
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'tenant_id': tenant_id,
                'settings': settings,
                'available_channels': [
                    {
                        'channel': 'email',
                        'name': 'Email Notifications',
                        'enabled': settings['email_notifications'],
                        'description': 'Receive notifications via email'
                    },
                    {
                        'channel': 'push',
                        'name': 'Push Notifications',
                        'enabled': settings['push_notifications'],
                        'description': 'Receive push notifications on mobile devices'
                    },
                    {
                        'channel': 'sms',
                        'name': 'SMS Notifications',
                        'enabled': settings['sms_notifications'],
                        'description': 'Receive notifications via SMS'
                    },
                    {
                        'channel': 'in_app',
                        'name': 'In-App Notifications',
                        'enabled': settings['in_app_notifications'],
                        'description': 'Receive notifications within the app'
                    }
                ],
                'notification_types': [
                    {
                        'type': 'task',
                        'name': 'Task Notifications',
                        'enabled': settings['task_notifications'],
                        'description': 'Notifications about task completions and updates'
                    },
                    {
                        'type': 'payment',
                        'name': 'Payment Notifications',
                        'enabled': settings['payment_notifications'],
                        'description': 'Notifications about payments, withdrawals, and earnings'
                    },
                    {
                        'type': 'referral',
                        'name': 'Referral Notifications',
                        'enabled': settings['referral_notifications'],
                        'description': 'Notifications about referral activities and rewards'
                    },
                    {
                        'type': 'security',
                        'name': 'Security Notifications',
                        'enabled': settings['security_notifications'],
                        'description': 'Important security alerts and account updates'
                    },
                    {
                        'type': 'marketing',
                        'name': 'Marketing Notifications',
                        'enabled': settings['marketing_notifications'],
                        'description': 'Promotional and marketing messages'
                    }
                ]
            },
            'message': 'Notification settings retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[NotificationsAdapter] Error getting notification settings: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve notification settings',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_notification_settings(request):
    """Update user's notification settings."""
    try:
        user = request.user
        data = request.data
        
        # Get current settings
        current_settings = cache.get(f'notification_settings_{user.id}', {})
        
        # Update settings
        updated_settings = current_settings.copy()
        
        if 'email_notifications' in data:
            updated_settings['email_notifications'] = data['email_notifications']
        if 'push_notifications' in data:
            updated_settings['push_notifications'] = data['push_notifications']
        if 'sms_notifications' in data:
            updated_settings['sms_notifications'] = data['sms_notifications']
        if 'in_app_notifications' in data:
            updated_settings['in_app_notifications'] = data['in_app_notifications']
        
        # Update notification type settings
        if 'task_notifications' in data:
            updated_settings['task_notifications'] = data['task_notifications']
        if 'payment_notifications' in data:
            updated_settings['payment_notifications'] = data['payment_notifications']
        if 'referral_notifications' in data:
            updated_settings['referral_notifications'] = data['referral_notifications']
        if 'security_notifications' in data:
            updated_settings['security_notifications'] = data['security_notifications']
        if 'marketing_notifications' in data:
            updated_settings['marketing_notifications'] = data['marketing_notifications']
        
        # Update quiet hours
        if 'quiet_hours' in data:
            updated_settings['quiet_hours'] = data['quiet_hours']
        
        # Cache updated settings
        cache.set(f'notification_settings_{user.id}', updated_settings, timeout=86400)
        
        return Response({
            'success': True,
            'data': {
                'updated_settings': updated_settings,
                'updated_at': timezone.now().isoformat()
            },
            'message': 'Notification settings updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[NotificationsAdapter] Error updating notification settings: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update notification settings',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_notification_counts(user, tenant_id) -> Dict:
    """Get notification counts by type."""
    try:
        from notifications.models import Notification
        counts = {}
        
        notification_types = ['task', 'payment', 'referral', 'security', 'marketing', 'system']
        
        for notification_type in notification_types:
            counts[notification_type] = Notification.objects.filter(
                user=user,
                tenant_id=tenant_id,
                notification_type=notification_type,
                is_read=False
            ).count()
        
        return counts
        
    except Exception:
        return {}
