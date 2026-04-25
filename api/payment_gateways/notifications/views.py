# api/payment_gateways/notifications/views.py
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from core.views import BaseViewSet
from .models import InAppNotification, DeviceToken
from .serializers import InAppNotificationSerializer, InAppNotificationListSerializer, DeviceTokenSerializer

class InAppNotificationViewSet(BaseViewSet):
    """User in-app notifications."""
    queryset           = InAppNotification.objects.all().order_by('-created_at')
    serializer_class   = InAppNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['is_read', 'notification_type']

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return InAppNotificationListSerializer
        return InAppNotificationSerializer

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notif         = self.get_object()
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save()
        return self.success_response(message='Marked as read')

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return self.success_response(message='All notifications marked as read')

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return self.success_response(data={'unread_count': count})


class DeviceTokenViewSet(BaseViewSet):
    """User device tokens for push notifications."""
    queryset           = DeviceToken.objects.all()
    serializer_class   = DeviceTokenSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['platform', 'is_active']

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        token            = self.get_object()
        token.is_active  = False
        token.save()
        return self.success_response(message='Device token deactivated')
