# earning_backend/api/notifications/viewsets/PushDeviceViewSet.py
"""
PushDeviceViewSet — register, update, and unregister push devices.

Endpoints:
  GET    /push-devices/             — list current user's devices
  POST   /push-devices/             — register a new device
  GET    /push-devices/{id}/        — retrieve device
  PUT    /push-devices/{id}/        — update device settings
  DELETE /push-devices/{id}/        — unregister device
  POST   /push-devices/{id}/deactivate/ — soft-deactivate
  POST   /push-devices/{id}/activate/   — re-activate
  POST   /push-devices/deactivate_all/  — deactivate all user devices
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone


class PushDeviceViewSet(viewsets.ModelViewSet):
    """ViewSet for PushDevice — register/manage push notification devices."""

    permission_classes = [IsAuthenticated]

    class _Pagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 50

    pagination_class = _Pagination

    def get_queryset(self):
        from api.notifications.models.channel import PushDevice
        qs = PushDevice.objects.filter(user=self.request.user)

        # Active filter
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')

        device_type = self.request.query_params.get('device_type')
        if device_type:
            qs = qs.filter(device_type=device_type)

        return qs.order_by('-last_used', '-created_at')

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.notifications.models.channel import PushDevice

        class PushDeviceSerializer(serializers.ModelSerializer):
            class Meta:
                model = PushDevice
                fields = [
                    'id', 'device_type', 'fcm_token', 'apns_token',
                    'web_push_subscription', 'device_name', 'device_model',
                    'os_version', 'app_version', 'is_active', 'last_used',
                    'created_at', 'updated_at',
                ]
                read_only_fields = ['id', 'last_used', 'created_at', 'updated_at']
                extra_kwargs = {
                    'fcm_token': {'required': False},
                    'apns_token': {'required': False},
                    'web_push_subscription': {'required': False},
                }

        return PushDeviceSerializer

    def perform_create(self, serializer):
        """Register device for current user. Update if same token exists."""
        from api.notifications.models.channel import PushDevice
        from django.conf import settings as dj_settings

        data = serializer.validated_data
        fcm_token = data.get('fcm_token', '')
        apns_token = data.get('apns_token', '')

        # Upsert: if token already exists, update it
        existing = None
        if fcm_token:
            existing = PushDevice.objects.filter(
                user=self.request.user, fcm_token=fcm_token
            ).first()
        elif apns_token:
            existing = PushDevice.objects.filter(
                user=self.request.user, apns_token=apns_token
            ).first()

        if existing:
            for field, value in data.items():
                setattr(existing, field, value)
            existing.is_active = True
            existing.last_used = timezone.now()
            existing.save()
            self._instance = existing
            return

        serializer.save(
            user=self.request.user,
            last_used=timezone.now(),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Return the saved instance (may be an existing one updated in place)
        instance = getattr(self, '_instance', None) or serializer.instance
        out = self.get_serializer(instance)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Soft-deactivate a device (stop receiving pushes without deleting)."""
        device = self.get_object()
        device.deactivate()
        return Response({'success': True, 'id': device.pk, 'is_active': False})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Re-activate a previously deactivated device."""
        device = self.get_object()
        device.activate()
        return Response({'success': True, 'id': device.pk, 'is_active': True})

    @action(detail=False, methods=['post'])
    def deactivate_all(self, request):
        """Deactivate all push devices for the current user."""
        updated = self.get_queryset().filter(is_active=True).update(
            is_active=False, updated_at=timezone.now()
        )
        return Response({'success': True, 'deactivated': updated})

    @action(detail=True, methods=['post'])
    def update_token(self, request, pk=None):
        """Update FCM / APNs token for a device."""
        device = self.get_object()
        fcm_token = request.data.get('fcm_token', '')
        apns_token = request.data.get('apns_token', '')
        web_push = request.data.get('web_push_subscription', {})

        if fcm_token:
            device.fcm_token = fcm_token
        if apns_token:
            device.apns_token = apns_token
        if web_push:
            device.web_push_subscription = web_push

        device.last_used = timezone.now()
        device.is_active = True
        device.save(update_fields=['fcm_token', 'apns_token', 'web_push_subscription',
                                    'last_used', 'is_active', 'updated_at'])
        return Response({'success': True, 'id': device.pk})
