# api/admin_panel/viewsets/SystemConfigViewSet.py
"""SystemConfigViewSet — CRUD + cache clear + bulk update."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache

from ..models.config import SystemConfig
from ..pagination import AdminPagination
from ..filters import SystemConfigFilter


class SystemConfigViewSet(viewsets.ModelViewSet):
    """Manage SystemConfig key-value store. CRUD + cache management."""
    permission_classes = [IsAdminUser]
    pagination_class = AdminPagination
    filterset_class = SystemConfigFilter

    def get_serializer_class(self):
        from ..serializers.SystemConfigSerializer import SystemConfigSerializer
        return SystemConfigSerializer

    def get_queryset(self):
        return SystemConfig.objects.all().order_by('group', 'key')

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['get'])
    def by_group(self, request):
        """Get all config grouped by group name."""
        configs = SystemConfig.objects.all().order_by('group', 'key')
        grouped = {}
        for config in configs:
            grp = config.group or 'general'
            if grp not in grouped:
                grouped[grp] = []
            grouped[grp].append({
                'key': config.key,
                'value': config.get_typed_value(),
                'value_type': config.value_type,
                'label': config.label,
                'description': config.description,
                'is_public': config.is_public,
                'is_readonly': config.is_readonly,
            })
        return Response({'groups': grouped})

    @action(detail=False, methods=['get'])
    def public(self, request):
        """Get all public configs (no auth required)."""
        configs = SystemConfig.objects.filter(is_public=True)
        data = {c.key: c.get_typed_value() for c in configs}
        return Response({'success': True, 'data': data})

    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """Clear all SystemConfig cache entries."""
        cache.delete('admin_panel:config_all')
        configs = SystemConfig.objects.all()
        for config in configs:
            cache.delete(f'admin_panel:config:{config.key}')
        return Response({'success': True, 'message': 'Config cache cleared.'})

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update multiple config values.
        Body: { configs: [{key: ..., value: ...}] }
        """
        items = request.data.get('configs', [])
        updated = 0
        errors = []
        for item in items:
            try:
                key = item['key']
                value = item['value']
                SystemConfig.set(key, value, user=request.user)
                updated += 1
            except Exception as e:
                errors.append({'key': item.get('key', '?'), 'error': str(e)})
        return Response({'success': True, 'updated': updated, 'errors': errors})

    @action(detail=False, methods=['get'])
    def get_value(self, request):
        """Get a single config value by key."""
        key = request.query_params.get('key')
        if not key:
            return Response({'error': 'key parameter required.'}, status=status.HTTP_400_BAD_REQUEST)
        value = SystemConfig.get(key)
        if value is None:
            return Response({'error': f'Config key "{key}" not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'key': key, 'value': value})