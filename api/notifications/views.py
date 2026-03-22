# earning_backend/api/notifications/views.py
from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, generics, status, filters, permissions
from rest_framework import decorators
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from datetime import datetime, timedelta
# from rest_framework.decorators import action  # এটি নিশ্চিত করুন
import json
import csv
from io import StringIO

from .models import (
    Notification, NotificationTemplate, NotificationPreference,
    DeviceToken, NotificationCampaign, NotificationRule,
    NotificationFeedback, NotificationAnalytics, NotificationLog
)
from .serializers import (
    NotificationSerializer, CreateNotificationSerializer,
    UpdateNotificationSerializer, BulkNotificationSerializer,
    NotificationTemplateSerializer, CreateTemplateSerializer,
    UpdateTemplateSerializer, TemplateRenderSerializer,
    NotificationPreferenceSerializer, UpdatePreferenceSerializer,
    DeviceTokenSerializer, RegisterDeviceSerializer,
    UpdateDeviceSettingsSerializer, NotificationCampaignSerializer,
    CreateCampaignSerializer, CampaignActionSerializer,
    NotificationRuleSerializer, CreateRuleSerializer,
    RuleActionSerializer, NotificationFeedbackSerializer,
    SubmitFeedbackSerializer, NotificationAnalyticsSerializer,
    AnalyticsRequestSerializer, NotificationLogSerializer,
    LogFilterSerializer, SystemStatusSerializer,
    TestNotificationSerializer, ExportPreferencesSerializer,
    ImportPreferencesSerializer, MarkAllAsReadSerializer,
    BulkDeleteSerializer, NotificationStatsSerializer,
    UserEngagementSerializer, CampaignPerformanceSerializer,
    NotificationSummarySerializer, PaginationSerializer,
    FilterSerializer, SuccessResponseSerializer,
    ErrorResponseSerializer, PaginatedResponseSerializer,
    NotificationActionSerializer, BatchActionSerializer
)
from .services import (
    notification_service, template_service, rule_service,
    analytics_service, preferences_service, device_service,
    feedback_service
)


# ==================== PERMISSION CLASSES ====================

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow owners or admins to access object
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        # Check if object has user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object has created_by attribute
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsTemplateOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for template access
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        if obj.is_public:
            return True
        
        if obj.created_by == request.user:
            return True
        
        # Check allowed groups
        if obj.allowed_groups and request.user.groups.filter(name__in=obj.allowed_groups).exists():
            return True
        
        # Check allowed roles (custom implementation)
        # This would depend on your role system
        
        return False


class CanCreateForOthers(permissions.BasePermission):
    """
    Permission to create notifications for other users
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            user_id = request.data.get('user_id')
            if user_id and str(user_id) != str(request.user.id):
                return request.user.is_staff
        return True


# ==================== PAGINATION CLASSES ====================

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class LargePagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


# ==================== NOTIFICATION VIEWSETS ====================

class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Notification model
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'priority', 'channel', 'status', 'is_read', 'is_archived']
    search_fields = ['title', 'message', 'tags']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'is_read']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return notifications for current user
        """
        user = self.request.user
        
        queryset = Notification.objects.filter(
            user=user,
            is_deleted=False
        )
        
        # Apply filters from query params
        filters = {}
        
        # Read status filter
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            filters['is_read'] = is_read.lower() == 'true'
        
        # Archived status filter
        is_archived = self.request.query_params.get('is_archived')
        if is_archived is not None:
            filters['is_archived'] = is_archived.lower() == 'true'
        
        # Pinned status filter
        is_pinned = self.request.query_params.get('is_pinned')
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned.lower() == 'true'
        
        # Type filter
        notification_type = self.request.query_params.get('notification_type')
        if notification_type:
            filters['notification_type'] = notification_type
        
        # Priority filter
        priority = self.request.query_params.get('priority')
        if priority:
            filters['priority'] = priority
        
        # Channel filter
        channel = self.request.query_params.get('channel')
        if channel:
            filters['channel'] = channel
        
        # Status filter
        status = self.request.query_params.get('status')
        if status:
            filters['status'] = status
        
        # Date range filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=start_date)
            except:
                pass
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=end_date)
            except:
                pass
        
        # Tag filter
        tags = self.request.query_params.getlist('tags')
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])
        
        # Campaign filter
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        # Group filter
        group_id = self.request.query_params.get('group_id')
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        
        # Apply filters
        if filters:
            queryset = queryset.filter(**filters)
        
        # Exclude expired notifications unless explicitly requested
        include_expired = self.request.query_params.get('include_expired', 'false').lower() == 'true'
        if not include_expired:
            queryset = queryset.filter(
                Q(expire_date__isnull=True) | Q(expire_date__gt=timezone.now())
            )
        
        return queryset
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action == 'create':
            return CreateNotificationSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateNotificationSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        """
        Create notification with current user as creator
        """
        if self.request.user.is_staff:
            # Admin can create notifications for other users
            serializer.save(created_by=self.request.user)
        else:
            # Regular users can only create notifications for themselves
            serializer.save(user=self.request.user, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """
        Get unread notifications
        """
        queryset = self.get_queryset().filter(is_read=False)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def count_unread(self, request):
        """
        Get count of unread notifications
        """
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})
    
    @action(detail=False, methods=['get'])
    def pinned(self, request):
        """
        Get pinned notifications
        """
        queryset = self.get_queryset().filter(is_pinned=True)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def archived(self, request):
        """
        Get archived notifications
        """
        queryset = self.get_queryset().filter(is_archived=True)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Mark all notifications as read
        """
        serializer = MarkAllAsReadSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    @action(detail=False, methods=['post'], url_path='send-bulk')
    def send_bulk(self, request):
        """Bulk send notifications to multiple users"""
        from .serializers import BulkNotificationSerializer
        serializer = BulkNotificationSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """
        Bulk delete notifications
        """
        serializer = BulkDeleteSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """
        Bulk action on notifications
        """
        serializer = BatchActionSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    @action(detail=True, methods=['post'], url_path='feedback')
    def feedback(self, request, pk=None):
        """Submit feedback for a notification"""
        notification = self.get_object()
        from .serializers import NotificationFeedbackSerializer
        data = request.data.copy()
        serializer = NotificationFeedbackSerializer(
            data=data, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save(user=request.user, notification=notification)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='track-impression')
    def track_impression(self, request, pk=None):
        """Record notification impression (view)"""
        notification = self.get_object()
        if hasattr(notification, 'increment_impression_count'):
            notification.increment_impression_count()
        elif hasattr(notification, 'impression_count'):
            from django.db.models import F
            type(notification).objects.filter(pk=notification.pk).update(
                impression_count=F('impression_count') + 1
            )
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Mark notification as read
        """
        notification = self.get_object()
        notification.mark_as_read()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='mark-unread')
    def mark_unread(self, request, pk=None):
        """
        Mark notification as unread
        """
        notification = self.get_object()
        notification.mark_as_unread()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """
        Pin notification
        """
        notification = self.get_object()
        notification.pin()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """
        Unpin notification
        """
        notification = self.get_object()
        notification.unpin()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """
        Archive notification
        """
        notification = self.get_object()
        notification.archive()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """
        Unarchive notification
        """
        notification = self.get_object()
        notification.unarchive()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='track-click')
    def click(self, request, pk=None):
        """
        Record notification click
        """
        notification = self.get_object()
        notification.increment_click_count()
        
        # Log the click
        NotificationLog.log_click(notification)
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        """
        Get replies to notification
        """
        notification = self.get_object()
        replies = notification.get_replies()
        
        page = self.paginate_queryset(replies)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(replies, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """
        Add reply to notification
        """
        notification = self.get_object()
        
        serializer = CreateNotificationSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            reply_notification = notification.add_reply(
                title=serializer.validated_data['title'],
                message=serializer.validated_data['message'],
                user=request.user,
                **serializer.validated_data
            )
            
            reply_serializer = self.get_serializer(reply_notification)
            return Response(reply_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def thread(self, request, pk=None):
        """
        Get complete notification thread
        """
        notification = self.get_object()
        
        # Get ancestors (parents)
        ancestors = notification.get_thread_ancestors()
        
        # Get descendants (replies)
        descendants = notification.get_thread_descendants()
        
        # Combine all notifications in thread
        thread_notifications = list(ancestors) + [notification] + list(descendants)
        
        # Sort by created_at
        thread_notifications.sort(key=lambda x: x.created_at)
        
        serializer = self.get_serializer(thread_notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """
        Get notification analytics
        """
        notification = self.get_object()
        analytics = notification.get_analytics_summary()
        
        return Response(analytics)
    
    @action(detail=True, methods=['post'])
    def action(self, request, pk=None):
        """
        Perform action on notification
        """
        notification = self.get_object()
        
        serializer = NotificationActionSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            notification = serializer.update(notification, serializer.validated_data)
            
            result_serializer = self.get_serializer(notification)
            return Response(result_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @decorators.action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get notification summary for current user
        """
        queryset = self.get_queryset()
        
        summary = {
            'total': queryset.count(),
            'unread': queryset.filter(is_read=False).count(),
            'pinned': queryset.filter(is_pinned=True).count(),
            'archived': queryset.filter(is_archived=True).count(),
            
            'by_type': list(queryset.values('notification_type').annotate(
                count=Count('id'),
                unread=Count('id', filter=Q(is_read=False))
            ).order_by('-count')),
            
            'by_priority': list(queryset.values('priority').annotate(
                count=Count('id'),
                unread=Count('id', filter=Q(is_read=False))
            ).order_by('-count')),
            
            'by_channel': list(queryset.values('channel').annotate(
                count=Count('id'),
                unread=Count('id', filter=Q(is_read=False))
            ).order_by('-count')),
            
            'recent_activity': list(queryset.order_by('-created_at')[:5].values(
                'id', 'title', 'notification_type', 'is_read', 'created_at'
            )),
        }
        
        return Response(summary)


class AdminNotificationViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for Notification model (for staff users)
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'notification_type', 'priority', 'channel', 'status', 'is_read']
    search_fields = ['title', 'message', 'user__username', 'user__email']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return all notifications (admin only)
        """
        queryset = Notification.objects.filter(is_deleted=False)
        
        # Apply filters
        user_id = self.request.query_params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Create bulk notifications (admin only)
        """
        serializer = BulkNotificationSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def send_test(self, request):
        """
        Send test notification (admin only)
        """
        serializer = TestNotificationSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get system notification statistics (admin only)
        """
        serializer = NotificationStatsSerializer(
            context={'request': request}
        )
        
        return Response(serializer.data)


# ==================== TEMPLATE VIEWSETS ====================

class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationTemplate model
    """
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsTemplateOwnerOrAdmin]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['template_type', 'category', 'is_active', 'is_public']
    search_fields = ['name', 'description', 'title_en', 'title_bn', 'message_en', 'message_bn']
    ordering_fields = ['name', 'created_at', 'updated_at', 'usage_count']
    ordering = ['name']
    
    def get_queryset(self):
        """
        Return templates based on user permissions
        """
        user = self.request.user
        
        if user.is_staff:
            # Staff can see all templates
            queryset = NotificationTemplate.objects.all()
        else:
            # Regular users can see public templates and their own templates
            queryset = NotificationTemplate.objects.filter(
                Q(is_public=True) |
                Q(created_by=user) |
                Q(allowed_groups__contains=[group.name for group in user.groups.all()])
            ).distinct()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=(is_active.lower() == 'true'))
        
        # Filter by template type
        template_type = self.request.query_params.get('template_type')
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action == 'create':
            return CreateTemplateSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateTemplateSerializer
        elif self.action == 'render':
            return TemplateRenderSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        """
        Create template with current user as creator
        """
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'], url_path='preview')
    def render(self, request, pk=None):
        """
        Render/preview template with context
        """
        template = self.get_object()
        
        serializer = TemplateRenderSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """
        Clone template
        """
        template = self.get_object()
        
        new_name = request.data.get('name', f"{template.name} (Copy)")
        
        # Check if name already exists
        if NotificationTemplate.objects.filter(name=new_name).exists():
            return Response(
                {'error': 'A template with this name already exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Clone template
        clone = template.clone(new_name=new_name, created_by=request.user)
        
        serializer = self.get_serializer(clone)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def create_notification(self, request, pk=None):
        """
        Create notification from template
        """
        template = self.get_object()
        
        # Check if user can use template
        if not template.is_public and template.created_by != request.user:
            # Check group permissions
            user_groups = [group.name for group in request.user.groups.all()]
            if not any(group in template.allowed_groups for group in user_groups):
                return Response(
                    {'error': 'You do not have permission to use this template.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Get context from request
        context = request.data.get('context', {})
        language = request.data.get('language', 'en')
        
        # Create notification from template
        notification = template_service.create_from_template(
            template_name=template.name,
            user=request.user,
            context=context,
            language=language
        )
        
        if not notification:
            return Response(
                {'error': 'Failed to create notification from template.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification_serializer = NotificationSerializer(notification)
        return Response(notification_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Get list of template categories
        """
        categories = NotificationTemplate.objects.values_list(
            'category', flat=True
        ).distinct().order_by('category')
        
        return Response(list(categories))
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """
        Get list of template types
        """
        types = NotificationTemplate.objects.values_list(
            'template_type', flat=True
        ).distinct().order_by('template_type')
        
        return Response(list(types))


# ==================== PREFERENCE VIEWSETS ====================

class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationPreference model
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        """
        Return preferences for current user
        """
        return NotificationPreference.objects.filter(user=self.request.user)
    
    def get_object(self):
        """
        Get or create preferences for current user
        """
        obj, created = NotificationPreference.objects.get_or_create(user=self.request.user)
        return obj
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action in ['update', 'partial_update']:
            return UpdatePreferenceSerializer
        return super().get_serializer_class()
    

    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def me(self, request):
        """Get or update current user's notification preferences"""
        pref, _ = self.get_queryset().model.objects.get_or_create(user=request.user)
        if request.method == 'PATCH':
            serializer = self.get_serializer(pref, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(self.get_serializer(pref).data)

    @action(detail=False, methods=['post'])
    def export(self, request):
        """
        Export preferences
        """
        serializer = ExportPreferencesSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            
            if result['success']:
                return Response(result)
            else:
                return Response(
                    {'error': result['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def import_prefs(self, request):
        """
        Import preferences
        """
        serializer = ImportPreferencesSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            
            if result['success']:
                return Response(result)
            else:
                return Response(
                    {'error': result.get('error', 'Import failed')},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def reset(self, request):
        """
        Reset preferences to defaults
        """
        success = preferences_service.reset_to_defaults(request.user)
        
        if success:
            return Response({'success': True, 'message': 'Preferences reset to defaults.'})
        else:
            return Response(
                {'error': 'Failed to reset preferences.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def channels(self, request):
        """
        Get available notification channels
        """
        channels = [
            {'id': 'in_app', 'name': 'In-App', 'description': 'Notifications within the application'},
            {'id': 'push', 'name': 'Push', 'description': 'Mobile push notifications'},
            {'id': 'email', 'name': 'Email', 'description': 'Email notifications'},
            {'id': 'sms', 'name': 'SMS', 'description': 'Text message notifications'},
            {'id': 'telegram', 'name': 'Telegram', 'description': 'Telegram messages'},
            {'id': 'whatsapp', 'name': 'WhatsApp', 'description': 'WhatsApp messages'},
            {'id': 'browser', 'name': 'Browser', 'description': 'Browser push notifications'},
        ]
        
        return Response(channels)
    
    @action(detail=False, methods=['get'])
    def notification_types(self, request):
        """
        Get available notification types
        """
        types = []
        
        for type_id, type_name in Notification.NOTIFICATION_TYPES:
            # Categorize notification types
            category = 'other'
            
            if type_id.startswith('system'):
                category = 'system'
            elif type_id.startswith('payment') or type_id.startswith('withdrawal') or type_id.startswith('wallet'):
                category = 'financial'
            elif 'task' in type_id:
                category = 'task'
            elif 'security' in type_id or 'login' in type_id or 'fraud' in type_id:
                category = 'security'
            elif 'promotion' in type_id or 'offer' in type_id or 'sale' in type_id:
                category = 'marketing'
            elif 'friend' in type_id or 'message' in type_id or 'comment' in type_id:
                category = 'social'
            elif 'support' in type_id or 'ticket' in type_id:
                category = 'support'
            elif 'achievement' in type_id or 'badge' in type_id or 'level' in type_id:
                category = 'achievement'
            elif 'reward' in type_id or 'game' in type_id:
                category = 'gamification'
            
            types.append({
                'id': type_id,
                'name': type_name,
                'category': category
            })
        
        return Response(types)


# ==================== DEVICE TOKEN VIEWSETS ====================

class DeviceTokenViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DeviceToken model
    """
    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        """
        Return device tokens for current user
        """
        return DeviceToken.objects.filter(user=self.request.user, is_active=True)
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action == 'create':
            return RegisterDeviceSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateDeviceSettingsSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        """
        Create device token with current user
        """
        serializer.save()
    

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """Get current user's registered device tokens"""
        tokens = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(tokens, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate device token
        """
        device_token = self.get_object()
        device_token.deactivate()
        
        serializer = self.get_serializer(device_token)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def platforms(self, request):
        """
        Get available platforms
        """
        platforms = [
            {'id': 'web', 'name': 'Web Browser'},
            {'id': 'android_app', 'name': 'Android App'},
            {'id': 'ios_app', 'name': 'iOS App'},
            {'id': 'windows_app', 'name': 'Windows App'},
            {'id': 'mac_app', 'name': 'macOS App'},
            {'id': 'progressive_web_app', 'name': 'Progressive Web App'},
        ]
        
        return Response(platforms)
    
    @action(detail=False, methods=['get'])
    def device_types(self, request):
        """
        Get available device types
        """
        device_types = [
            {'id': 'web', 'name': 'Web Browser'},
            {'id': 'android', 'name': 'Android'},
            {'id': 'ios', 'name': 'iOS'},
            {'id': 'windows', 'name': 'Windows'},
            {'id': 'mac', 'name': 'macOS'},
            {'id': 'linux', 'name': 'Linux'},
            {'id': 'smart_tv', 'name': 'Smart TV'},
            {'id': 'smart_watch', 'name': 'Smart Watch'},
            {'id': 'tablet', 'name': 'Tablet'},
            {'id': 'desktop', 'name': 'Desktop'},
            {'id': 'mobile', 'name': 'Mobile'},
        ]
        
        return Response(device_types)


# ==================== CAMPAIGN VIEWSETS ====================

class NotificationCampaignViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationCampaign model
    """
    serializer_class = NotificationCampaignSerializer
    permission_classes = [IsAdminUser]  # Only admin can manage campaigns
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign_type', 'channel', 'status']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'total_sent']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return campaigns
        """
        return NotificationCampaign.objects.all()
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action == 'create':
            return CreateCampaignSerializer
        elif self.action == 'action':
            return CampaignActionSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        """
        Create campaign with current user as creator
        """
        serializer.save(created_by=self.request.user)
    

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """Start a campaign"""
        campaign = self.get_object()
        campaign.status = 'running'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """Pause a running campaign"""
        campaign = self.get_object()
        campaign.status = 'paused'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['post'], url_path='resume')
    def resume(self, request, pk=None):
        """Resume a paused campaign"""
        campaign = self.get_object()
        campaign.status = 'running'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel a campaign"""
        campaign = self.get_object()
        campaign.status = 'cancelled'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        """Get campaign stats (alias for performance)"""
        return self.performance(request, pk=pk)

    @action(detail=True, methods=['post'])
    def user_action(self, request, pk=None):
        """
        Perform action on campaign
        """
        campaign = self.get_object()
        
        serializer = CampaignActionSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            campaign = serializer.update(campaign, serializer.validated_data)
            
            result_serializer = self.get_serializer(campaign)
            return Response(result_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        Get campaign performance report
        """
        serializer = CampaignPerformanceSerializer(
            data={'campaign_id': pk},
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def notifications(self, request, pk=None):
        """
        Get notifications for campaign
        """
        campaign = self.get_object()
        
        notifications = Notification.objects.filter(
            campaign_id=str(campaign.id)
        ).order_by('-created_at')
        
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = NotificationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def campaign_types(self, request):
        """
        Get available campaign types
        """
        campaign_types = [
            {'id': 'promotional', 'name': 'Promotional', 'description': 'Marketing promotions'},
            {'id': 'transactional', 'name': 'Transactional', 'description': 'Transaction notifications'},
            {'id': 'educational', 'name': 'Educational', 'description': 'Educational content'},
            {'id': 'alert', 'name': 'Alert', 'description': 'Important alerts'},
            {'id': 'reminder', 'name': 'Reminder', 'description': 'Reminder notifications'},
            {'id': 'welcome', 'name': 'Welcome', 'description': 'Welcome messages'},
            {'id': 'abandoned_cart', 'name': 'Abandoned Cart', 'description': 'Cart abandonment'},
            {'id': 're_engagement', 'name': 'Re-engagement', 'description': 'User re-engagement'},
            {'id': 'birthday', 'name': 'Birthday', 'description': 'Birthday messages'},
            {'id': 'anniversary', 'name': 'Anniversary', 'description': 'Anniversary messages'},
            {'id': 'holiday', 'name': 'Holiday', 'description': 'Holiday greetings'},
            {'id': 'seasonal', 'name': 'Seasonal', 'description': 'Seasonal promotions'},
            {'id': 'event', 'name': 'Event', 'description': 'Event notifications'},
            {'id': 'survey', 'name': 'Survey', 'description': 'Survey invitations'},
            {'id': 'feedback', 'name': 'Feedback', 'description': 'Feedback requests'},
            {'id': 'update', 'name': 'Update', 'description': 'System updates'},
        ]
        
        return Response(campaign_types)


# ==================== RULE VIEWSETS ====================

class NotificationRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationRule model
    """
    serializer_class = NotificationRuleSerializer
    permission_classes = [IsAdminUser]  # Only admin can manage rules
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['trigger_type', 'action_type', 'target_type', 'is_active', 'is_enabled']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at', 'trigger_count']
    ordering = ['name']
    
    def get_queryset(self):
        """
        Return rules
        """
        return NotificationRule.objects.all()
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action == 'create':
            return CreateRuleSerializer
        elif self.action == 'action':
            return RuleActionSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        """
        Create rule with current user as creator
        """
        serializer.save(created_by=self.request.user)
    

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """Start a campaign"""
        campaign = self.get_object()
        campaign.status = 'running'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """Pause a running campaign"""
        campaign = self.get_object()
        campaign.status = 'paused'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['post'], url_path='resume')
    def resume(self, request, pk=None):
        """Resume a paused campaign"""
        campaign = self.get_object()
        campaign.status = 'running'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel a campaign"""
        campaign = self.get_object()
        campaign.status = 'cancelled'
        campaign.save(update_fields=['status'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        """Get campaign stats (alias for performance)"""
        return self.performance(request, pk=pk)

    @action(detail=True, methods=['post'])
    def user_action(self, request, pk=None):
        """
        Perform action on rule
        """
        rule = self.get_object()
        
        serializer = RuleActionSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            rule = serializer.update(rule, serializer.validated_data)
            
            result_serializer = self.get_serializer(rule)
            return Response(result_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def test(self, request, pk=None):
        """
        Test rule execution
        """
        rule = self.get_object()
        
        context = request.query_params.get('context')
        if context:
            try:
                context = json.loads(context)
            except:
                context = {}
        
        result = rule_service.test_rule(rule, context)
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def trigger_types(self, request):
        """
        Get available trigger types
        """
        trigger_types = [
            {'id': 'event', 'name': 'Event', 'description': 'Triggered by system events'},
            {'id': 'schedule', 'name': 'Schedule', 'description': 'Triggered on schedule'},
            {'id': 'condition', 'name': 'Condition', 'description': 'Triggered when conditions are met'},
            {'id': 'webhook', 'name': 'Webhook', 'description': 'Triggered by webhook calls'},
        ]
        
        return Response(trigger_types)
    
    # @action(detail=False, methods=['get'])
    # def action_types(self, request):
    @action(detail=False, methods=['get'], url_path='action-types') # url_path যোগ করলাম
    def get_notification_action_types(self, request): # নাম বদলে দিলাম
        """
        Get available action types
        """
        action_types = [
            {'id': 'send_notification', 'name': 'Send Notification', 'description': 'Send a notification'},
            {'id': 'update_notification', 'name': 'Update Notification', 'description': 'Update existing notification'},
            {'id': 'delete_notification', 'name': 'Delete Notification', 'description': 'Delete notification'},
            {'id': 'archive_notification', 'name': 'Archive Notification', 'description': 'Archive notification'},
            {'id': 'send_email', 'name': 'Send Email', 'description': 'Send email'},
            {'id': 'call_webhook', 'name': 'Call Webhook', 'description': 'Call webhook'},
        ]
        
        return Response(action_types)
    
    @action(detail=False, methods=['get'])
    def target_types(self, request):
        """
        Get available target types
        """
        target_types = [
            {'id': 'user', 'name': 'Specific User', 'description': 'Target specific user'},
            {'id': 'user_group', 'name': 'User Group', 'description': 'Target user group'},
            {'id': 'all_users', 'name': 'All Users', 'description': 'Target all users'},
            {'id': 'dynamic', 'name': 'Dynamic', 'description': 'Dynamic targeting based on conditions'},
        ]
        
        return Response(target_types)


# ==================== FEEDBACK VIEWSETS ====================

class NotificationFeedbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationFeedback model
    """
    serializer_class = NotificationFeedbackSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        """
        Return feedback for current user's notifications
        """
        return NotificationFeedback.objects.filter(
            notification__user=self.request.user
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action == 'create':
            return SubmitFeedbackSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        """
        Create feedback
        """
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get feedback statistics
        """
        feedbacks = self.get_queryset()
        
        stats = {
            'total': feedbacks.count(),
            'average_rating': feedbacks.filter(rating__isnull=False).aggregate(
                avg=Avg('rating')
            )['avg'] or 0,
            
            'by_type': list(feedbacks.values('feedback_type').annotate(
                count=Count('id'),
                avg_rating=Avg('rating')
            ).order_by('-count')),
            
            'by_notification_type': list(feedbacks.values(
                'notification__notification_type'
            ).annotate(
                count=Count('id'),
                avg_rating=Avg('rating')
            ).order_by('-count')),
            
            'helpful_count': feedbacks.filter(is_helpful=True).count(),
            'would_like_more_count': feedbacks.filter(would_like_more=True).count(),
        }
        
        return Response(stats)


# ==================== ANALYTICS VIEWS ====================

class NotificationAnalyticsView(generics.ListAPIView):
    """
    View for notification analytics
    """
    serializer_class = NotificationAnalyticsSerializer
    permission_classes = [IsAdminUser]  # Only admin can view analytics
    pagination_class = StandardPagination
    
    def get_queryset(self):
        """
        Return analytics data
        """
        queryset = NotificationAnalytics.objects.all()
        
        # Apply date filters
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
                queryset = queryset.filter(date__gte=start_date)
            except:
                pass
        
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
                queryset = queryset.filter(date__lte=end_date)
            except:
                pass
        
        return queryset.order_by('-date')
    
    @action(detail=False, methods=['post'])
    def generate_report(self, request):
        """
        Generate analytics report
        """
        serializer = AnalyticsRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            report = analytics_service.generate_analytics_report(
                start_date=serializer.validated_data.get('start_date'),
                end_date=serializer.validated_data.get('end_date'),
                group_by=serializer.validated_data.get('group_by', 'day')
            )
            
            return Response(report)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """
        Get performance metrics
        """
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except:
                start_date = None
        
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except:
                end_date = None
        
        metrics = analytics_service.get_performance_metrics(start_date, end_date)
        
        return Response(metrics)
    
    @action(detail=False, methods=['get'])
    def user_engagement(self, request):
        """
        Get user engagement report
        """
        serializer = UserEngagementSerializer(
            data=request.query_params,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== LOG VIEWS ====================

class NotificationLogView(generics.ListAPIView):
    """
    View for notification logs
    """
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAdminUser]  # Only admin can view logs
    pagination_class = LargePagination
    
    def get_queryset(self):
        """
        Return logs with filters
        """
        queryset = NotificationLog.objects.all()
        
        # Apply filters
        serializer = LogFilterSerializer(data=self.request.query_params)
        
        if serializer.is_valid():
            data = serializer.validated_data
            
            if data.get('start_date'):
                queryset = queryset.filter(created_at__gte=data['start_date'])
            
            if data.get('end_date'):
                queryset = queryset.filter(created_at__lte=data['end_date'])
            
            if data.get('log_type'):
                queryset = queryset.filter(log_type=data['log_type'])
            
            if data.get('log_level'):
                queryset = queryset.filter(log_level=data['log_level'])
            
            if data.get('notification_id'):
                queryset = queryset.filter(notification_id=data['notification_id'])
            
            if data.get('user_id'):
                queryset = queryset.filter(user_id=data['user_id'])
            
            if data.get('source'):
                queryset = queryset.filter(source__icontains=data['source'])
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def log_types(self, request):
        """
        Get available log types
        """
        log_types = [
            {'id': 'delivery', 'name': 'Delivery', 'description': 'Delivery events'},
            {'id': 'read', 'name': 'Read', 'description': 'Read events'},
            {'id': 'click', 'name': 'Click', 'description': 'Click events'},
            {'id': 'dismiss', 'name': 'Dismiss', 'description': 'Dismiss events'},
            {'id': 'archive', 'name': 'Archive', 'description': 'Archive events'},
            {'id': 'delete', 'name': 'Delete', 'description': 'Delete events'},
            {'id': 'error', 'name': 'Error', 'description': 'Error events'},
            {'id': 'warning', 'name': 'Warning', 'description': 'Warning events'},
            {'id': 'info', 'name': 'Info', 'description': 'Info events'},
            {'id': 'debug', 'name': 'Debug', 'description': 'Debug events'},
        ]
        
        return Response(log_types)
    
    @action(detail=False, methods=['get'])
    def log_levels(self, request):
        """
        Get available log levels
        """
        log_levels = [
            {'id': 'debug', 'name': 'Debug', 'level': 10},
            {'id': 'info', 'name': 'Info', 'level': 20},
            {'id': 'warning', 'name': 'Warning', 'level': 30},
            {'id': 'error', 'name': 'Error', 'level': 40},
            {'id': 'critical', 'name': 'Critical', 'level': 50},
        ]
        
        return Response(log_levels)


# ==================== SYSTEM VIEWS ====================

class SystemStatusView(APIView):
    """
    View for system status
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """
        Get system status
        """
        serializer = SystemStatusSerializer(context={'request': request})
        return Response(serializer.data)


class HealthCheckView(APIView):
    """
    View for health check
    """
    permission_classes = []  # Public endpoint
    
    def get(self, request):
        """
        Health check endpoint
        """
        try:
            # Check database
            Notification.objects.count()
            
            # Check cache
            cache.set('health_check', 'ok', 10)
            cache.get('health_check')
            
            return Response({
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'services': {
                    'database': 'connected',
                    'cache': 'connected',
                }
            })
        except Exception as e:
            return Response({
                'status': 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'error': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ==================== UTILITY VIEWS ====================

class SendTestNotificationView(APIView):
    """
    View for sending test notifications
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Send test notification
        """
        serializer = TestNotificationSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MarkAllAsReadView(APIView):
    """
    View for marking all notifications as read
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Mark all notifications as read
        """
        serializer = MarkAllAsReadSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserStatsView(APIView):
    """
    View for user statistics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get user notification statistics
        """
        serializer = NotificationStatsSerializer(context={'request': request})
        return Response(serializer.data)


class ExportDataView(APIView):
    """
    View for exporting notification data
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Export notification data
        """
        format_type = request.data.get('format', 'json')
        
        if format_type == 'json':
            return self._export_json(request)
        elif format_type == 'csv':
            return self._export_csv(request)
        else:
            return Response(
                {'error': 'Unsupported format. Use json or csv.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _export_json(self, request):
        """
        Export data as JSON
        """
        user = request.user
        
        # Get notifications
        notifications = Notification.objects.filter(
            user=user,
            is_deleted=False
        ).order_by('-created_at')
        
        # Get preferences
        preferences = NotificationPreference.objects.filter(user=user).first()
        
        # Get device tokens
        device_tokens = DeviceToken.objects.filter(user=user)
        
        # Get feedback
        feedbacks = NotificationFeedback.objects.filter(user=user)
        
        data = {
            'export_date': timezone.now().isoformat(),
            'user_id': user.id,
            'username': user.username,
            'notifications': [
                {
                    'id': str(n.id),
                    'title': n.title,
                    'message': n.message,
                    'type': n.notification_type,
                    'priority': n.priority,
                    'channel': n.channel,
                    'is_read': n.is_read,
                    'created_at': n.created_at.isoformat(),
                    'read_at': n.read_at.isoformat() if n.read_at else None,
                }
                for n in notifications[:1000]  # Limit to 1000 notifications
            ],
            'preferences': preferences.export_preferences() if preferences else {},
            'device_tokens': [
                {
                    'device_type': dt.device_type,
                    'platform': dt.platform,
                    'created_at': dt.created_at.isoformat(),
                    'last_active': dt.last_active.isoformat() if dt.last_active else None,
                }
                for dt in device_tokens
            ],
            'feedbacks': [
                {
                    'notification_id': str(fb.notification_id),
                    'rating': fb.rating,
                    'feedback': fb.feedback,
                    'feedback_type': fb.feedback_type,
                    'created_at': fb.created_at.isoformat(),
                }
                for fb in feedbacks
            ]
        }
        
        response = JsonResponse(data, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = f'attachment; filename="notifications_export_{timezone.now().date()}.json"'
        
        return response
    
    def _export_csv(self, request):
        """
        Export data as CSV
        """
        user = request.user
        
        # Get notifications
        notifications = Notification.objects.filter(
            user=user,
            is_deleted=False
        ).order_by('-created_at')[:1000]  # Limit to 1000 notifications
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Title', 'Message', 'Type', 'Priority', 'Channel',
            'Is Read', 'Created At', 'Read At', 'Tags'
        ])
        
        # Write data
        for notification in notifications:
            writer.writerow([
                str(notification.id),
                notification.title,
                notification.message,
                notification.notification_type,
                notification.priority,
                notification.channel,
                notification.is_read,
                notification.created_at.isoformat(),
                notification.read_at.isoformat() if notification.read_at else '',
                ','.join(notification.tags) if notification.tags else ''
            ])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="notifications_export_{timezone.now().date()}.csv"'
        
        return response


# ==================== API VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """
    Get unread notification count
    """
    count = Notification.objects.filter(
        user=request.user,
        is_read=False,
        is_deleted=False
    ).exclude(
        Q(expire_date__isnull=False) & Q(expire_date__lt=timezone.now())
    ).count()
    
    return Response({'unread_count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """
    Mark notification as read
    """
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user,
            is_deleted=False
        )
        
        notification.mark_as_read()
        
        return Response({
            'success': True,
            'message': 'Notification marked as read.'
        })
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_summary(request):
    """
    Get notification summary
    """
    notifications = Notification.objects.filter(
        user=request.user,
        is_deleted=False
    ).exclude(
        Q(expire_date__isnull=False) & Q(expire_date__lt=timezone.now())
    )
    
    summary = {
        'total': notifications.count(),
        'unread': notifications.filter(is_read=False).count(),
        'pinned': notifications.filter(is_pinned=True).count(),
        'archived': notifications.filter(is_archived=True).count(),
        
        'by_type': list(notifications.values('notification_type').annotate(
            count=Count('id'),
            unread=Count('id', filter=Q(is_read=False))
        ).order_by('-count')[:10]),
        
        'recent': list(notifications.order_by('-created_at')[:5].values(
            'id', 'title', 'notification_type', 'is_read', 'created_at'
        )),
    }
    
    return Response(summary)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_device(request):
    """
    Register device for push notifications
    """
    serializer = RegisterDeviceSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        device_token = serializer.save()
        
        return Response({
            'success': True,
            'device_id': str(device_token.id),
            'message': 'Device registered successfully.'
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unregister_device(request, token):
    """
    Unregister device
    """
    success = device_service.unregister_device(token)
    
    if success:
        return Response({
            'success': True,
            'message': 'Device unregistered successfully.'
        })
    else:
        return Response(
            {'error': 'Device not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def preferences(request):
    """
    Get notification preferences
    """
    preferences, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    serializer = NotificationPreferenceSerializer(preferences)
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_preferences(request):
    """
    Update notification preferences
    """
    preferences, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    serializer = UpdatePreferenceSerializer(
        preferences,
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        preferences = serializer.save()
        
        result_serializer = NotificationPreferenceSerializer(preferences)
        return Response(result_serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== ADMIN API VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_send_notification(request):
    """
    Admin endpoint to send notification
    """
    serializer = CreateNotificationSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        notification = serializer.save()
        
        return Response({
            'success': True,
            'notification_id': str(notification.id),
            'message': 'Notification sent successfully.'
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_bulk_send(request):
    """
    Admin endpoint for bulk sending
    """
    serializer = BulkNotificationSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        result = serializer.save()
        
        return Response(result, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_stats(request):
    """
    Admin endpoint for system statistics
    """
    stats = notification_service.get_system_stats()
    
    return Response(stats)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_cleanup(request):
    """
    Admin endpoint for cleanup operations
    """
    action = request.data.get('action', 'expired')
    
    if action == 'expired':
        result = notification_service.delete_expired_notifications()
    elif action == 'old':
        days = request.data.get('days', 90)
        result = notification_service.cleanup_old_notifications(days)
    elif action == 'failed':
        result = notification_service.retry_failed_notifications()
    else:
        return Response(
            {'error': 'Invalid action. Use: expired, old, failed'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics(request):
    """
    Admin endpoint for analytics
    """
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if start_date:
        try:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            start_date = None
    
    if end_date:
        try:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            end_date = None
    
    report = analytics_service.generate_analytics_report(start_date, end_date)
    
    return Response(report)


# ==================== PUBLIC API VIEWS ====================

@api_view(['GET'])
@permission_classes([])  # Public endpoint
def public_health(request):
    """
    Public health check endpoint
    """
    view = HealthCheckView()
    return view.get(request)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def feedback(request):
    """
    Submit feedback for notification
    """
    serializer = SubmitFeedbackSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        feedback = serializer.save()
        
        return Response({
            'success': True,
            'feedback_id': str(feedback.id),
            'message': 'Feedback submitted successfully.'
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== WEBHOOK VIEWS ====================

@api_view(['POST'])
@permission_classes([])  # Public endpoint with token authentication
def webhook_receiver(request, provider):
    """
    Webhook receiver for external services
    """
    # Verify webhook signature (implementation depends on provider)
    # This is a placeholder implementation
    
    provider = provider.lower()
    
    if provider == 'firebase':
        # Handle Firebase webhook
        data = request.data
        
        # Extract notification status updates
        if 'message' in data:
            message_id = data['message'].get('message_id')
            status = data.get('status', 'unknown')
            
            # Update notification status in database
            # This would require storing Firebase message IDs in metadata
            
            return Response({'success': True})
    
    elif provider == 'twilio':
        # Handle Twilio webhook
        pass
    
    elif provider == 'sendgrid':
        # Handle SendGrid webhook
        pass
    
    return Response(
        {'error': 'Unsupported provider'},
        status=status.HTTP_400_BAD_REQUEST
    )


# ==================== BATCH PROCESSING VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAdminUser])
def process_scheduled(request):
    """
    Process scheduled notifications
    """
    # Get scheduled notifications that are due
    now = timezone.now()
    scheduled_notifications = Notification.objects.filter(
        status='scheduled',
        scheduled_for__lte=now,
        is_deleted=False
    )
    
    processed_count = 0
    failed_count = 0
    
    for notification in scheduled_notifications:
        try:
            notification.status = 'pending'
            notification.save()
            
            success = notification_service.send_notification(notification)
            
            if success:
                processed_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            notification.mark_as_failed(str(e))
    
    return Response({
        'success': True,
        'processed': processed_count,
        'failed': failed_count,
        'total': scheduled_notifications.count()
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def process_campaign(request, campaign_id):
    """
    Process campaign
    """
    result = notification_service.process_campaign(campaign_id)
    
    if result['success']:
        return Response(result)
    else:
        return Response(
            {'error': result.get('error', 'Campaign processing failed')},
            status=status.HTTP_400_BAD_REQUEST
        )


# ==================== REAL-TIME VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def real_time_updates(request):
    """
    Get real-time updates for notifications
    """
    # Get last update timestamp from request
    last_update = request.query_params.get('last_update')
    
    if last_update:
        try:
            last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
        except:
            last_update = None
    
    # Get new notifications since last update
    if last_update:
        new_notifications = Notification.objects.filter(
            user=request.user,
            is_deleted=False,
            created_at__gt=last_update
        ).exclude(
            Q(expire_date__isnull=False) & Q(expire_date__lt=timezone.now())
        ).order_by('-created_at')[:50]
    else:
        new_notifications = Notification.objects.filter(
            user=request.user,
            is_deleted=False
        ).exclude(
            Q(expire_date__isnull=False) & Q(expire_date__lt=timezone.now())
        ).order_by('-created_at')[:50]
    
    # Get unread count
    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
        is_deleted=False
    ).exclude(
        Q(expire_date__isnull=False) & Q(expire_date__lt=timezone.now())
    ).count()
    
    serializer = NotificationSerializer(new_notifications, many=True)
    
    return Response({
        'timestamp': timezone.now().isoformat(),
        'unread_count': unread_count,
        'new_notifications': serializer.data,
        'has_more': new_notifications.count() == 50
    })


# ==================== TEST VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def test_system(request):
    """
    Test the notification system
    """
    result = notification_service.validate_notification_system()
    
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_all_channels(request):
    """
    Test all notification channels
    """
    user = request.user
    channels = ['in_app', 'email']  # Add more channels as configured
    
    results = {}
    
    for channel in channels:
        result = notification_service.send_test_notification(user, channel)
        results[channel] = result
    
    return Response(results)


# ==================== DASHBOARD VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def dashboard_stats(request):
    """
    Get dashboard statistics
    """
    # Today's stats
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    today_stats = {
        'notifications': Notification.objects.filter(
            created_at__range=[today_start, today_end]
        ).count(),
        
        'delivered': Notification.objects.filter(
            is_delivered=True,
            created_at__range=[today_start, today_end]
        ).count(),
        
        'read': Notification.objects.filter(
            is_read=True,
            created_at__range=[today_start, today_end]
        ).count(),
        
        'failed': Notification.objects.filter(
            status='failed',
            created_at__range=[today_start, today_end]
        ).count(),
    }
    
    # Weekly stats
    week_start = today_start - timedelta(days=7)
    
    weekly_stats = {
        'notifications': Notification.objects.filter(
            created_at__range=[week_start, today_end]
        ).count(),
        
        'delivered': Notification.objects.filter(
            is_delivered=True,
            created_at__range=[week_start, today_end]
        ).count(),
        
        'read': Notification.objects.filter(
            is_read=True,
            created_at__range=[week_start, today_end]
        ).count(),
        
        'failed': Notification.objects.filter(
            status='failed',
            created_at__range=[week_start, today_end]
        ).count(),
    }
    
    # Monthly stats
    month_start = today_start - timedelta(days=30)
    
    monthly_stats = {
        'notifications': Notification.objects.filter(
            created_at__range=[month_start, today_end]
        ).count(),
        
        'delivered': Notification.objects.filter(
            is_delivered=True,
            created_at__range=[month_start, today_end]
        ).count(),
        
        'read': Notification.objects.filter(
            is_read=True,
            created_at__range=[month_start, today_end]
        ).count(),
        
        'failed': Notification.objects.filter(
            status='failed',
            created_at__range=[month_start, today_end]
        ).count(),
    }
    
    # Top notification types
    top_types = Notification.objects.values('notification_type').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Recent activity
    recent_activity = Notification.objects.select_related('user').order_by('-created_at')[:10].values(
        'id', 'title', 'notification_type', 'user__username', 'created_at'
    )
    
    # Active campaigns
    active_campaigns = NotificationCampaign.objects.filter(
        status__in=['running', 'scheduled']
    ).order_by('-created_at')[:5]
    
    return Response({
        'today': today_stats,
        'weekly': weekly_stats,
        'monthly': monthly_stats,
        'top_types': list(top_types),
        'recent_activity': list(recent_activity),
        'active_campaigns': NotificationCampaignSerializer(active_campaigns, many=True).data,
    })


# ==================== ERROR HANDLING ====================

class NotificationAPIError(Exception):
    """
    Custom exception for notification API errors
    """
    pass


def handle_notification_error(exc, context):
    """
    Custom error handler for notification API
    """
    from rest_framework.views import exception_handler
    
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data = {
            'success': False,
            'error': str(exc),
            'error_code': getattr(exc, 'code', 'unknown_error'),
            'details': response.data if isinstance(response.data, dict) else {}
        }
    
    return response


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing notification logs (Read-only)
    """
    queryset = NotificationLog.objects.all().order_by('-created_at')
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAdminUser]  # শুধু অ্যাডমিনরা লগ দেখতে পারবে
    pagination_class = LargePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['message', 'source', 'notification__title']
    ordering_fields = ['created_at', 'log_level']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # ফিল্টারিং লজিক
        log_type = self.request.query_params.get('log_type')
        if log_type:
            queryset = queryset.filter(log_type=log_type)
            
        log_level = self.request.query_params.get('log_level')
        if log_level:
            queryset = queryset.filter(log_level=log_level)
            
        return queryset
    
class NotificationReplyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification replies (threaded notifications)
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        """
        Get replies for a specific notification or user's replies
        """
        # Get parent notification ID from URL
        parent_notification_id = self.kwargs.get('notification_pk')
        user = self.request.user
        
        if parent_notification_id:
            # Get replies for specific notification
            parent_notification = get_object_or_404(
                Notification.objects.filter(
                    id=parent_notification_id,
                    is_deleted=False
                )
            )
            
            # Check permission (user must be involved in the thread)
            if (not self.request.user.is_staff and 
                parent_notification.user != user and 
                not parent_notification.get_replies().filter(user=user).exists()):
                raise PermissionDenied("You don't have permission to view these replies.")
            
            queryset = parent_notification.get_replies()
        else:
            # Get all replies by current user
            queryset = Notification.objects.filter(
                parent_notification__isnull=False,
                user=user,
                is_deleted=False
            )
        
        # Apply filters
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('created_at')
    
    def get_serializer_class(self):
        """
        Use different serializer for creation
        """
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer
    
    def perform_create(self, serializer):
        """
        Create a reply to a notification
        """
        parent_notification_id = self.kwargs.get('notification_pk')
        
        if not parent_notification_id:
            raise ValidationError("Parent notification ID is required")
        
        parent_notification = get_object_or_404(
            Notification.objects.filter(
                id=parent_notification_id,
                is_deleted=False
            )
        )
        
        # Check if user can reply
        if not self.can_user_reply(parent_notification):
            raise PermissionDenied("You cannot reply to this notification")
        
        # Create the reply
        reply = parent_notification.add_reply(
            title=serializer.validated_data.get('title', f"Re: {parent_notification.title}"),
            message=serializer.validated_data['message'],
            user=self.request.user,
            notification_type=serializer.validated_data.get('notification_type', 'message'),
            priority=serializer.validated_data.get('priority', 'medium'),
            channel=serializer.validated_data.get('channel', 'in_app'),
            metadata=serializer.validated_data.get('metadata', {})
        )
        
        # Set serializer instance
        serializer.instance = reply
        
        # Send notification about the reply
        self.notify_about_reply(parent_notification, reply)
    
    def can_user_reply(self, parent_notification):
        """
        Check if user can reply to notification
        """
        user = self.request.user
        
        # Admin can always reply
        if user.is_staff:
            return True
        
        # Original recipient can reply
        if parent_notification.user == user:
            return True
        
        # Users who are part of the thread can reply
        if parent_notification.get_replies().filter(user=user).exists():
            return True
        
        # Check if notification allows replies
        if hasattr(parent_notification, 'allow_replies'):
            return parent_notification.allow_replies
        
        # Default: only original recipient can reply
        return parent_notification.user == user
    
    def notify_about_reply(self, parent_notification, reply):
        """
        Send notifications about the reply
        """
        # Notify the parent notification owner (if different from replier)
        if parent_notification.user != reply.user:
            Notification.objects.create(
                user=parent_notification.user,
                title=f"New reply to: {parent_notification.title}",
                message=f"{reply.user.username} replied: {reply.message[:100]}...",
                notification_type='message',
                priority='medium',
                channel='in_app',
                action_url=f"/notifications/{parent_notification.id}/",
                parent_notification=parent_notification
            )
        
        # Notify other participants in the thread
        participants = set()
        
        # Add all users who have replied
        for previous_reply in parent_notification.get_replies():
            if previous_reply.user != reply.user and previous_reply.user != parent_notification.user:
                participants.add(previous_reply.user)
        
        # Notify each participant
        for participant in participants:
            Notification.objects.create(
                user=participant,
                title=f"New reply in thread: {parent_notification.title}",
                message=f"{reply.user.username} replied: {reply.message[:100]}...",
                notification_type='message',
                priority='low',
                channel='in_app',
                action_url=f"/notifications/{parent_notification.id}/",
                parent_notification=parent_notification
            )
    
    @action(detail=False, methods=['get'])
    def thread(self, request, notification_pk=None):
        """
        Get complete thread for a notification
        """
        parent_notification = get_object_or_404(
            Notification.objects.filter(
                id=notification_pk,
                is_deleted=False
            )
        )
        
        # Check permission
        if not self.request.user.is_staff and parent_notification.user != self.request.user:
            raise PermissionDenied("You don't have permission to view this thread")
        
        # Get all ancestors (older messages)
        ancestors = parent_notification.get_thread_ancestors()
        
        # Get all descendants (replies)
        descendants = parent_notification.get_thread_descendants()
        
        # Combine all messages in chronological order
        all_messages = list(ancestors) + [parent_notification] + list(descendants)
        all_messages.sort(key=lambda x: x.created_at)
        
        # Serialize
        serializer = self.get_serializer(all_messages, many=True)
        
        return Response({
            'thread_id': notification_pk,
            'messages': serializer.data,
            'participants': self.get_thread_participants(all_messages),
            'depth': parent_notification.get_thread_depth(),
            'message_count': len(all_messages)
        })
    
    def get_thread_participants(self, messages):
        """
        Get unique participants in a thread
        """
        participants = set()
        for message in messages:
            participants.add({
                'id': message.user.id,
                'username': message.user.username,
                'email': message.user.email,
                'is_original_sender': message.user == messages[0].user
            })
        return list(participants)
    
    @action(detail=True, methods=['post'])
    def mark_thread_read(self, request, pk=None):
        """
        Mark entire thread as read
        """
        notification = self.get_object()
        
        if not self.request.user.is_staff and notification.user != self.request.user:
            raise PermissionDenied("You don't have permission to mark this thread as read")
        
        # Get all messages in thread
        all_messages = list(notification.get_thread_ancestors()) + [notification] + list(notification.get_thread_descendants())
        
        # Mark all as read for current user
        count = 0
        for msg in all_messages:
            if msg.user == self.request.user and not msg.is_read:
                msg.mark_as_read()
                count += 1
        
        return Response({
            'success': True,
            'message': f'{count} messages marked as read',
            'thread_id': str(notification.id)
        })
    
    @action(detail=True, methods=['get'])
    def participants(self, request, pk=None):
        """
        Get all participants in a thread
        """
        notification = self.get_object()
        
        if not self.request.user.is_staff and notification.user != self.request.user:
            raise PermissionDenied("You don't have permission to view participants")
        
        participants = self.get_thread_participants(
            list(notification.get_thread_ancestors()) + [notification] + list(notification.get_thread_descendants())
        )
        
        return Response({
            'thread_id': str(notification.id),
            'participants': participants,
            'participant_count': len(participants)
        })
    
    @action(detail=False, methods=['get'])
    def my_threads(self, request):
        """
        Get all threads where current user is participating
        """
        user = self.request.user
        
        # Get notifications that are part of threads where user is involved
        user_notifications = Notification.objects.filter(
            user=user,
            is_deleted=False
        ).exclude(
            Q(parent_notification__isnull=True) & ~Q(replies__isnull=False)
        )
        
        # Get unique threads
        threads = set()
        for notification in user_notifications:
            # Get root of thread
            root = notification
            while root.parent_notification:
                root = root.parent_notification
            threads.add(root)
        
        # Get thread summaries
        thread_summaries = []
        for thread in threads:
            # Get latest message
            all_messages = list(thread.get_thread_descendants()) + [thread]
            latest_message = max(all_messages, key=lambda x: x.created_at)
            
            # Get unread count for user
            unread_count = sum(1 for msg in all_messages if msg.user == user and not msg.is_read)
            
            # Get participants
            participants = set(msg.user.username for msg in all_messages)
            
            thread_summaries.append({
                'thread_id': str(thread.id),
                'title': thread.title,
                'latest_message': {
                    'content': latest_message.message[:100] + '...' if len(latest_message.message) > 100 else latest_message.message,
                    'sender': latest_message.user.username,
                    'time': latest_message.created_at
                },
                'unread_count': unread_count,
                'message_count': len(all_messages),
                'participant_count': len(participants),
                'participants': list(participants)[:3],  # First 3 participants
                'created_at': thread.created_at,
                'updated_at': latest_message.created_at
            })
        
        # Sort by latest activity
        thread_summaries.sort(key=lambda x: x['updated_at'], reverse=True)
        
        return Response({
            'threads': thread_summaries,
            'total_threads': len(thread_summaries),
            'total_unread': sum(t['unread_count'] for t in thread_summaries)
        })
    
    @action(detail=True, methods=['post'])
    def close_thread(self, request, pk=None):
        """
        Close a thread (mark as resolved)
        """
        notification = self.get_object()
        
        # Check permission (only thread starter or admin can close)
        if not self.request.user.is_staff and notification.user != self.request.user:
            raise PermissionDenied("Only thread starter or admin can close the thread")
        
        # Update metadata to mark as closed
        notification.metadata['thread_status'] = 'closed'
        notification.metadata['closed_by'] = self.request.user.username
        notification.metadata['closed_at'] = timezone.now().isoformat()
        notification.metadata['close_reason'] = request.data.get('reason', 'Resolved by user')
        notification.save()
        
        # Notify all participants
        all_messages = list(notification.get_thread_descendants()) + [notification]
        participants = set(msg.user for msg in all_messages)
        
        for participant in participants:
            if participant != self.request.user:
                Notification.objects.create(
                    user=participant,
                    title=f"Thread closed: {notification.title}",
                    message=f"The thread has been marked as resolved by {self.request.user.username}.",
                    notification_type='info',
                    priority='low',
                    channel='in_app',
                    action_url=f"/notifications/{notification.id}/",
                    metadata={'thread_id': str(notification.id)}
                )
        
        return Response({
            'success': True,
            'message': 'Thread marked as closed',
            'thread_id': str(notification.id),
            'closed_by': self.request.user.username,
            'closed_at': timezone.now().isoformat()
        })
    
    @action(detail=True, methods=['post'])
    def reopen_thread(self, request, pk=None):
        """
        Reopen a closed thread
        """
        notification = self.get_object()
        
        # Check permission
        if not self.request.user.is_staff and notification.user != self.request.user:
            raise PermissionDenied("Only thread starter or admin can reopen the thread")
        
        # Update metadata
        notification.metadata['thread_status'] = 'open'
        notification.metadata.pop('closed_by', None)
        notification.metadata.pop('closed_at', None)
        notification.metadata.pop('close_reason', None)
        notification.save()
        
        return Response({
            'success': True,
            'message': 'Thread reopened',
            'thread_id': str(notification.id)
        })
    
    @action(detail=False, methods=['get'])
    def search_threads(self, request):
        """
        Search through threads
        """
        user = self.request.user
        query = request.query_params.get('q', '')
        
        if not query:
            return Response({'error': 'Search query required'}, status=400)
        
        # Get user's threads
        user_notifications = Notification.objects.filter(
            user=user,
            is_deleted=False
        ).exclude(
            Q(parent_notification__isnull=True) & ~Q(replies__isnull=False)
        )
        
        # Search in thread contents
        matching_messages = Notification.objects.filter(
            Q(title__icontains=query) | Q(message__icontains=query),
            is_deleted=False
        )
        
        # Get unique threads from matching messages
        threads = set()
        for message in matching_messages:
            # Get root of thread
            root = message
            while root.parent_notification:
                root = root.parent_notification
            threads.add(root)
        
        # Filter threads where user is a participant
        user_threads = []
        for thread in threads:
            all_messages = list(thread.get_thread_descendants()) + [thread]
            if any(msg.user == user for msg in all_messages):
                user_threads.append(thread)
        
        # Prepare results
        results = []
        for thread in user_threads:
            # Find matching message in thread
            matching_in_thread = Notification.objects.filter(
                Q(title__icontains=query) | Q(message__icontains=query),
                id__in=[msg.id for msg in (list(thread.get_thread_descendants()) + [thread])]
            ).first()
            
            results.append({
                'thread_id': str(thread.id),
                'title': thread.title,
                'matching_preview': matching_in_thread.message[:200] + '...' if matching_in_thread else '',
                'message_count': len(list(thread.get_thread_descendants())) + 1,
                'last_activity': max([msg.created_at for msg in (list(thread.get_thread_descendants()) + [thread])]),
                'participants': list(set(msg.user.username for msg in (list(thread.get_thread_descendants()) + [thread])))[:3]
            })
        
        # Sort by relevance (could be improved with search ranking)
        results.sort(key=lambda x: x['last_activity'], reverse=True)
        
        return Response({
            'query': query,
            'results': results,
            'count': len(results)
        })    
    

# ============================================================
# BULLETPROOF SIMPLE VIEWS
# ============================================================

class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            count = Notification.objects.filter(
                user=request.user,
                is_read=False,
                is_deleted=False
            ).count()
            return Response({'unread_count': count})
        except Exception as e:
            return Response({'unread_count': 0})


class NotificationStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            qs = Notification.objects.filter(user=request.user)
            stats = {
                'total': qs.count(),
                'unread': qs.filter(is_read=False).count(),
                'delivered': qs.filter(status="delivered").count(),
                'failed': qs.filter(status="failed").count(),
            }
            return Response(stats)
        except Exception as e:
            return Response({'total': 0, 'unread': 0, 'delivered': 0, 'failed': 0})


# ============================================================
# NOTICE VIEWSET
# ============================================================
from .models import Notice

class NoticeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notice.objects.all().order_by("-created_at")
    
    def get_serializer_class(self):
        from rest_framework import serializers
        class NoticeSerializer(serializers.ModelSerializer):
            class Meta:
                model = Notice
                fields = "__all__"
        return NoticeSerializer
    
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        notice = self.get_object()
        notice.is_published = True
        notice.status = "published"
        notice.save()
        return Response({"status": "published"})
    
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        notice = self.get_object()
        notice.is_published = False
        notice.status = "draft"
        notice.save()
        return Response({"status": "unpublished"})
    
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        notice = self.get_object()
        notice.status = "archived"
        notice.save()
        return Response({"status": "archived"})


# Fix 13: Standalone view for POST /notifications/analytics/generate/
class GenerateDailyReportView(APIView):
    """POST /notifications/analytics/generate/ — Generate daily analytics report"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        from django.utils.dateparse import parse_date
        date_str = request.data.get('date')
        date = parse_date(date_str) if date_str else None
        try:
            from .tasks import generate_daily_analytics
            generate_daily_analytics.delay(str(date) if date else None)
            return Response({'success': True, 'message': 'Daily report generation queued',
                             'date': str(date or 'today')})
        except Exception as e:
            return Response({'success': False, 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)