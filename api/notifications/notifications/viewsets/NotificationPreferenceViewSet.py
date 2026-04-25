# earning_backend/api/notifications/viewsets/NotificationPreferenceViewSet.py
"""
NotificationPreferenceViewSet — split from views.py (lines 851-1009).
Full code preserved exactly as in views.py.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from notifications.models import NotificationPreference
from notifications.serializers import (
    NotificationPreferenceSerializer,
    UpdatePreferenceSerializer,
    ExportPreferencesSerializer,
)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NotificationPreference model — per-user channel preferences.

    Endpoints:
      GET    /preferences/me/         — get current user's preferences
      PATCH  /preferences/me/         — update preferences
      POST   /preferences/reset/      — reset to defaults
      POST   /preferences/export/     — export preferences data
      POST   /preferences/import/     — import/restore preferences
      POST   /preferences/dnd/        — set Do Not Disturb schedule
      GET    /preferences/channels/   — get per-channel status
    """

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def get_object(self):
        obj, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return obj

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return UpdatePreferenceSerializer
        return NotificationPreferenceSerializer

    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def me(self, request):
        """Get or update current user's notification preferences."""
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        if request.method == 'PATCH':
            serializer = self.get_serializer(pref, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(self.get_serializer(pref).data)

    @action(detail=False, methods=['post'])
    def reset(self, request):
        """Reset all notification preferences to system defaults."""
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        try:
            pref.reset_to_defaults()
        except AttributeError:
            # Fallback: delete and recreate
            pref.delete()
            pref = NotificationPreference.objects.create(user=request.user)
        return Response(NotificationPreferenceSerializer(pref).data)

    @action(detail=False, methods=['post'])
    def export(self, request):
        """Export notification preferences as JSON."""
        serializer = ExportPreferencesSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def channels(self, request):
        """Get per-channel enabled/disabled status for current user."""
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        from notifications.services.OptOutService import opt_out_service
        opted_out = opt_out_service.get_opted_out_channels(request.user)
        channels = ['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser']
        result = {}
        for ch in channels:
            enabled_attr = f'{ch}_enabled'
            result[ch] = {
                'enabled': getattr(pref, enabled_attr, True),
                'opted_out': ch in opted_out,
                'can_receive': ch not in opted_out,
            }
        return Response(result)

    @action(detail=False, methods=['post'])
    def dnd(self, request):
        """Set Do Not Disturb schedule (quiet hours)."""
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        dnd_start = request.data.get('dnd_start')
        dnd_end = request.data.get('dnd_end')
        dnd_enabled = request.data.get('dnd_enabled', True)
        dnd_timezone = request.data.get('timezone', 'Asia/Dhaka')

        update_fields = []
        if hasattr(pref, 'dnd_enabled'):
            pref.dnd_enabled = dnd_enabled
            update_fields.append('dnd_enabled')
        if dnd_start and hasattr(pref, 'dnd_start'):
            pref.dnd_start = dnd_start
            update_fields.append('dnd_start')
        if dnd_end and hasattr(pref, 'dnd_end'):
            pref.dnd_end = dnd_end
            update_fields.append('dnd_end')
        if dnd_timezone and hasattr(pref, 'dnd_timezone'):
            pref.dnd_timezone = dnd_timezone
            update_fields.append('dnd_timezone')

        if update_fields:
            pref.save(update_fields=update_fields)

        return Response({
            'success': True,
            'dnd_enabled': dnd_enabled,
            'dnd_start': dnd_start,
            'dnd_end': dnd_end,
            'timezone': dnd_timezone,
        })
