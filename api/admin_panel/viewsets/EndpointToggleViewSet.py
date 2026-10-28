# api/admin_panel/viewsets/EndpointToggleViewSet.py
"""
EndpointToggleViewSet — migrated from views.py.
All original logic (bulk-toggle, by_group) preserved.
"""
from rest_framework import viewsets, permissions, status, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache

from ..endpoint_toggle import EndpointToggle
from ..pagination import AdminPagination


class EndpointToggleSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = EndpointToggle
        fields = '__all__'


class EndpointToggleViewSet(viewsets.ModelViewSet):
    """ViewSet for EndpointToggle — migrated from views.py (all logic kept)."""
    queryset = EndpointToggle.objects.all().order_by('group', 'path')
    serializer_class = EndpointToggleSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = AdminPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        group = self.request.query_params.get('group')
        if group:
            queryset = queryset.filter(group=group)
        is_enabled = self.request.query_params.get('is_enabled')
        if is_enabled is not None:
            queryset = queryset.filter(is_enabled=is_enabled.lower() == 'true')
        return queryset

    @action(detail=False, methods=['post'], url_path='bulk-toggle')
    def bulk_toggle(self, request):
        """Toggle multiple endpoints at once."""
        toggles = request.data.get('toggles', [])
        updated = 0
        errors = []
        for item in toggles:
            try:
                path = item['path']
                method = item.get('method', 'ALL')
                obj, created = EndpointToggle.objects.get_or_create(
                    path=path,
                    method=method,
                    defaults={
                        'is_enabled': item['is_enabled'],
                        'group': item.get('group', 'other'),
                        'label': item.get('label', ''),
                        'disabled_message': item.get(
                            'disabled_message',
                            item.get('message', 'Feature temporarily disabled.')
                        ),
                    }
                )
                if not created:
                    obj.is_enabled = item['is_enabled']
                    if 'disabled_message' in item:
                        obj.disabled_message = item['disabled_message']
                    obj.save(update_fields=['is_enabled', 'disabled_message', 'updated_at'])
                    cache.delete(f'endpoint_toggle_{path}_{method}')
                    cache.delete(f'endpoint_toggle_{path}_ALL')
                updated += 1
            except Exception as e:
                errors.append({'item': item.get('path', '?'), 'error': str(e)})
        cache.delete('admin_panel:endpoint_toggles')
        return Response({'success': True, 'updated': updated, 'errors': errors})

    @action(detail=False, methods=['get'])
    def by_group(self, request):
        """Get toggles grouped by category."""
        toggles = EndpointToggle.objects.all().order_by('group', 'path')
        grouped = {}
        for toggle in toggles:
            grp = toggle.group or 'other'
            if grp not in grouped:
                grouped[grp] = []
            serializer = self.get_serializer(toggle)
            grouped[grp].append(serializer.data)
        return Response({'groups': grouped, 'total': toggles.count()})

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """Enable a specific endpoint toggle."""
        toggle = self.get_object()
        toggle.is_enabled = True
        toggle.save(update_fields=['is_enabled', 'updated_at'])
        return Response({'success': True, 'is_enabled': True})

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """Disable a specific endpoint toggle."""
        toggle = self.get_object()
        toggle.is_enabled = False
        toggle.save(update_fields=['is_enabled', 'updated_at'])
        return Response({'success': True, 'is_enabled': False})

    @action(detail=False, methods=['get'])
    def status_summary(self, request):
        """Summary of enabled vs disabled endpoints."""
        total = EndpointToggle.objects.count()
        enabled = EndpointToggle.objects.filter(is_enabled=True).count()
        disabled = total - enabled
        return Response({
            'total': total,
            'enabled': enabled,
            'disabled': disabled,
        })