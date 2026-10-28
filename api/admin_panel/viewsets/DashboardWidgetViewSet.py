# api/admin_panel/viewsets/DashboardWidgetViewSet.py
"""DashboardWidgetViewSet — CRUD + drag-drop position save."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..models.dashboard import DashboardWidget, DashboardLayout
from ..pagination import SmallListPagination
from ..filters import DashboardWidgetFilter
from ..constants import MAX_DASHBOARD_WIDGETS


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    """CRUD for DashboardWidget + bulk position save (drag-and-drop)."""
    permission_classes = [IsAdminUser]
    pagination_class = SmallListPagination
    filterset_class = DashboardWidgetFilter

    def get_serializer_class(self):
        from ..serializers.DashboardWidgetSerializer import DashboardWidgetSerializer
        return DashboardWidgetSerializer

    def get_queryset(self):
        return DashboardWidget.objects.filter(
            user=self.request.user
        ).order_by('position')

    def perform_create(self, serializer):
        # Enforce max widget limit
        current_count = DashboardWidget.objects.filter(user=self.request.user).count()
        if current_count >= MAX_DASHBOARD_WIDGETS:
            from ..exceptions import MaxWidgetsExceeded
            raise MaxWidgetsExceeded(
                detail=f"Maximum {MAX_DASHBOARD_WIDGETS} widgets allowed per user."
            )
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def save_positions(self, request):
        """
        Bulk update widget positions after drag-and-drop.
        Body: { positions: [{id: int, position: {x, y, w, h}}] }
        """
        positions = request.data.get('positions', [])
        updated = 0
        errors = []
        for item in positions:
            try:
                widget = DashboardWidget.objects.get(
                    pk=item['id'], user=request.user
                )
                widget.position = item['position']
                widget.save(update_fields=['position', 'updated_at'])
                updated += 1
            except DashboardWidget.DoesNotExist:
                errors.append({'id': item.get('id'), 'error': 'Not found'})
            except Exception as e:
                errors.append({'id': item.get('id'), 'error': str(e)})

        return Response({
            'success': True,
            'updated': updated,
            'errors': errors,
        })

    @action(detail=True, methods=['post'])
    def toggle_visibility(self, request, pk=None):
        """Toggle widget visibility."""
        widget = self.get_object()
        widget.is_visible = not widget.is_visible
        widget.save(update_fields=['is_visible', 'updated_at'])
        return Response({'success': True, 'is_visible': widget.is_visible})

    @action(detail=False, methods=['get'])
    def layout(self, request):
        """Get user's default dashboard layout."""
        try:
            layout = DashboardLayout.objects.get(user=request.user, is_default=True)
            return Response({
                'success': True,
                'layout': layout.layout,
                'name': layout.name,
            })
        except DashboardLayout.DoesNotExist:
            return Response({'success': True, 'layout': {}, 'name': 'Default'})

    @action(detail=False, methods=['post'])
    def save_layout(self, request):
        """Save or update dashboard layout."""
        layout_data = request.data.get('layout', {})
        name = request.data.get('name', 'Default Layout')
        is_default = request.data.get('is_default', True)

        layout, created = DashboardLayout.objects.get_or_create(
            user=request.user,
            name=name,
            defaults={'layout': layout_data, 'is_default': is_default}
        )
        if not created:
            layout.layout = layout_data
            layout.is_default = is_default
            layout.save(update_fields=['layout', 'is_default', 'updated_at'])

        return Response({
            'success': True,
            'created': created,
            'name': name,
        })