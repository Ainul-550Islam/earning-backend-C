"""
Advertiser Notification ViewSet

ViewSet for advertiser notification management,
including listing and marking notifications as read.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from ..models.notification import AdvertiserNotification
from ..serializers import AdvertiserNotificationSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdvertiserNotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for advertiser notification management.
    
    Handles notification listing, reading,
    and notification preferences.
    """
    
    queryset = AdvertiserNotification.objects.all()
    serializer_class = AdvertiserNotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all notifications
            return AdvertiserNotification.objects.all()
        else:
            # Advertisers can only see their own notifications
            return AdvertiserNotification.objects.filter(advertiser__user=user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark notification as read.
        
        Updates notification read status.
        """
        notification = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or notification.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            
            return Response({
                'detail': 'Notification marked as read',
                'is_read': True,
                'read_at': notification.read_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return Response(
                {'detail': 'Failed to mark notification as read'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        """
        Mark notification as unread.
        
        Updates notification read status.
        """
        notification = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or notification.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            notification.is_read = False
            notification.read_at = None
            notification.save()
            
            return Response({
                'detail': 'Notification marked as unread',
                'is_read': False,
                'read_at': None
            })
            
        except Exception as e:
            logger.error(f"Error marking notification as unread: {e}")
            return Response(
                {'detail': 'Failed to mark notification as unread'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Mark all notifications as read.
        
        Updates read status for all unread notifications.
        """
        try:
            # Get unread notifications for user
            unread_notifications = AdvertiserNotification.objects.filter(
                advertiser=request.user.advertiser,
                is_read=False
            )
            
            # Mark all as read
            updated_count = unread_notifications.update(
                is_read=True,
                read_at=timezone.now()
            )
            
            return Response({
                'detail': f'Marked {updated_count} notifications as read',
                'updated_count': updated_count
            })
            
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return Response(
                {'detail': 'Failed to mark all notifications as read'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def mark_all_unread(self, request):
        """
        Mark all notifications as unread.
        
        Updates read status for all read notifications.
        """
        try:
            # Get read notifications for user
            read_notifications = AdvertiserNotification.objects.filter(
                advertiser=request.user.advertiser,
                is_read=True
            )
            
            # Mark all as unread
            updated_count = read_notifications.update(
                is_read=False,
                read_at=None
            )
            
            return Response({
                'detail': f'Marked {updated_count} notifications as unread',
                'updated_count': updated_count
            })
            
        except Exception as e:
            logger.error(f"Error marking all notifications as unread: {e}")
            return Response(
                {'detail': 'Failed to mark all notifications as unread'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def delete_read(self, request):
        """
        Delete read notifications.
        
        Removes all read notifications.
        """
        try:
            # Get read notifications for user
            read_notifications = AdvertiserNotification.objects.filter(
                advertiser=request.user.advertiser,
                is_read=True
            )
            
            # Count and delete
            deleted_count = read_notifications.count()
            read_notifications.delete()
            
            return Response({
                'detail': f'Deleted {deleted_count} read notifications',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            logger.error(f"Error deleting read notifications: {e}")
            return Response(
                {'detail': 'Failed to delete read notifications'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def delete_all(self, request):
        """
        Delete all notifications.
        
        Removes all notifications for the user.
        """
        try:
            # Get all notifications for user
            all_notifications = AdvertiserNotification.objects.filter(
                advertiser=request.user.advertiser
            )
            
            # Count and delete
            deleted_count = all_notifications.count()
            all_notifications.delete()
            
            return Response({
                'detail': f'Deleted {deleted_count} notifications',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            logger.error(f"Error deleting all notifications: {e}")
            return Response(
                {'detail': 'Failed to delete all notifications'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """
        Get unread notification count.
        
        Returns count of unread notifications.
        """
        try:
            unread_count = AdvertiserNotification.objects.filter(
                advertiser=request.user.advertiser,
                is_read=False
            ).count()
            
            return Response({
                'unread_count': unread_count,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return Response(
                {'detail': 'Failed to get unread count'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def notification_types(self, request):
        """
        Get notification types.
        
        Returns list of supported notification types.
        """
        try:
            notification_types = {
                'campaign': {
                    'name': 'Campaign Notifications',
                    'description': 'Notifications about campaign status, performance, and budget',
                    'enabled_by_default': True,
                },
                'billing': {
                    'name': 'Billing Notifications',
                    'description': 'Notifications about payments, invoices, and wallet balance',
                    'enabled_by_default': True,
                },
                'offer': {
                    'name': 'Offer Notifications',
                    'description': 'Notifications about offer approval, rejection, and performance',
                    'enabled_by_default': True,
                },
                'fraud': {
                    'name': 'Fraud Notifications',
                    'description': 'Notifications about fraud detection and quality issues',
                    'enabled_by_default': True,
                },
                'system': {
                    'name': 'System Notifications',
                    'description': 'Notifications about system updates and maintenance',
                    'enabled_by_default': True,
                },
                'marketing': {
                    'name': 'Marketing Notifications',
                    'description': 'Notifications about new features and promotions',
                    'enabled_by_default': False,
                },
            }
            
            return Response(notification_types)
            
        except Exception as e:
            logger.error(f"Error getting notification types: {e}")
            return Response(
                {'detail': 'Failed to get notification types'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def notification_preferences(self, request):
        """
        Get notification preferences.
        
        Returns user's notification settings.
        """
        try:
            # This would implement actual preference retrieval
            # For now, return default preferences
            preferences = {
                'email_enabled': True,
                'sms_enabled': False,
                'push_enabled': True,
                'in_app_enabled': True,
                'types': {
                    'campaign': True,
                    'billing': True,
                    'offer': True,
                    'fraud': True,
                    'system': True,
                    'marketing': False,
                },
                'quiet_hours': {
                    'enabled': False,
                    'start_time': '22:00',
                    'end_time': '08:00',
                },
                'frequency': {
                    'immediate': True,
                    'daily_digest': False,
                    'weekly_summary': True,
                }
            }
            
            return Response(preferences)
            
        except Exception as e:
            logger.error(f"Error getting notification preferences: {e}")
            return Response(
                {'detail': 'Failed to get notification preferences'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def update_preferences(self, request):
        """
        Update notification preferences.
        
        Updates user's notification settings.
        """
        try:
            preferences = request.data.get('preferences', {})
            
            # This would implement actual preference update
            # For now, just return success
            return Response({
                'detail': 'Notification preferences updated successfully',
                'preferences': preferences
            })
            
        except Exception as e:
            logger.error(f"Error updating notification preferences: {e}")
            return Response(
                {'detail': 'Failed to update notification preferences'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def notification_summary(self, request):
        """
        Get notification summary.
        
        Returns summary of recent notifications.
        """
        try:
            days = int(request.query_params.get('days', 7))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get notifications for the period
            notifications = AdvertiserNotification.objects.filter(
                advertiser=request.user.advertiser,
                created_at__gte=start_date,
                created_at__lte=end_date
            )
            
            # Aggregate data
            total_notifications = notifications.count()
            unread_notifications = notifications.filter(is_read=False).count()
            
            # Get type breakdown
            type_breakdown = notifications.values('notification_type').annotate(
                count=Count('id'),
                unread_count=Count(Case(When(is_read=False, then=1)))
            ).order_by('-count')
            
            # Get priority breakdown
            priority_breakdown = notifications.values('priority').annotate(
                count=Count('id'),
                unread_count=Count(Case(When(is_read=False, then=1)))
            ).order_by('-priority')
            
            # Get daily breakdown
            daily_breakdown = {}
            current_date = start_date.date()
            while current_date <= end_date:
                day_notifications = notifications.filter(
                    created_at__date=current_date
                )
                day_data = day_notifications.aggregate(
                    total=Count('id'),
                    unread=Count(Case(When(is_read=False, then=1)))
                )
                
                daily_breakdown[current_date.isoformat()] = {
                    'total': day_data['total'] or 0,
                    'unread': day_data['unread'] or 0,
                }
                
                current_date += timezone.timedelta(days=1)
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_notifications': total_notifications,
                    'unread_notifications': unread_notifications,
                    'read_rate': float(((total_notifications - unread_notifications) / total_notifications * 100) if total_notifications > 0 else 0),
                },
                'type_breakdown': [
                    {
                        'type': item['notification_type'],
                        'count': item['count'],
                        'unread_count': item['unread_count'],
                    }
                    for item in type_breakdown
                ],
                'priority_breakdown': [
                    {
                        'priority': item['priority'],
                        'count': item['count'],
                        'unread_count': item['unread_count'],
                    }
                    for item in priority_breakdown
                ],
                'daily_breakdown': daily_breakdown,
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting notification summary: {e}")
            return Response(
                {'detail': 'Failed to get notification summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def recent_notifications(self, request):
        """
        Get recent notifications.
        
        Returns most recent notifications.
        """
        try:
            limit = int(request.query_params.get('limit', 10))
            include_read = request.query_params.get('include_read', 'true').lower() == 'true'
            
            # Get recent notifications
            notifications = AdvertiserNotification.objects.filter(
                advertiser=request.user.advertiser
            )
            
            if not include_read:
                notifications = notifications.filter(is_read=False)
            
            notifications = notifications.order_by('-created_at')[:limit]
            
            serializer = self.get_serializer(notifications, many=True)
            
            return Response({
                'notifications': serializer.data,
                'count': len(serializer.data),
                'include_read': include_read,
                'limit': limit,
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting recent notifications: {e}")
            return Response(
                {'detail': 'Failed to get recent notifications'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def create_notification(self, request):
        """
        Create notification.
        
        Creates a new notification (admin only).
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            notification_data = request.data.copy()
            
            # Set advertiser if not provided
            if 'advertiser' not in notification_data:
                advertiser_id = request.data.get('advertiser_id')
                if advertiser_id:
                    notification_data['advertiser'] = advertiser_id
                else:
                    return Response(
                        {'detail': 'Advertiser ID is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            serializer = self.get_serializer(data=notification_data)
            if serializer.is_valid():
                notification = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return Response(
                {'detail': 'Failed to create notification'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        advertiser_id = request.query_params.get('advertiser_id')
        notification_type = request.query_params.get('notification_type')
        priority = request.query_params.get('priority')
        is_read = request.query_params.get('is_read')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        search = request.query_params.get('search')
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        if priority:
            queryset = queryset.filter(priority=priority)
        
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(message__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
