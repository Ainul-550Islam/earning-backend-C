# api/support/viewsets/SupportSettingsViewSet.py  — WORLD #1
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.utils import timezone

logger = logging.getLogger(__name__)


class SupportSettingsViewSet(viewsets.ViewSet):
    """
    GET    /api/support/settings/        — public (all)
    PUT    /api/support/settings/        — admin only
    PATCH  /api/support/settings/        — admin only
    GET    /api/support/settings/status/ — is support online?
    """

    def list(self, request):
        from api.support.models import SupportSettings
        from api.support.serializers import SupportSettingsSerializer
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        version_code = int(request.query_params.get('version_code', 1))
        data = SupportSettingsSerializer(obj).data
        data['needs_update']  = version_code < obj.latest_version_code
        data['support_online'] = obj.is_support_online and not obj.maintenance_mode
        return Response(data)

    def partial_update(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=403)
        from api.support.models import SupportSettings
        from api.support.serializers import SupportSettingsSerializer
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        serializer = SupportSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def status(self, request):
        from api.support.models import SupportSettings, SupportAgent
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        agents_online = SupportAgent.objects.filter(is_active=True, is_available=True).count()
        return Response({
            'is_online':     obj.is_support_online,
            'maintenance':   obj.maintenance_mode,
            'message':       obj.maintenance_message if obj.maintenance_mode else '',
            'agents_online': agents_online,
            'hours_start':   str(obj.support_hours_start),
            'hours_end':     str(obj.support_hours_end),
        })