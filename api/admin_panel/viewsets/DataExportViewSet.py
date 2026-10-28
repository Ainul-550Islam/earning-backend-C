# api/admin_panel/viewsets/DataExportViewSet.py
"""DataExportViewSet — async export + download."""
import os
import uuid
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.http import FileResponse

from ..models.reports import DataExport
from ..pagination import ExportPagination
from ..filters import DataExportFilter, get_filter_for_model


class DataExportViewSet(viewsets.ReadOnlyModelViewSet):
    """Manage async data exports. Request → process → download."""
    permission_classes = [IsAdminUser]
    pagination_class = ExportPagination
    filterset_class = get_filter_for_model(DataExport, DataExportFilter)

    def get_serializer_class(self):
        from ..serializers.DataExportSerializer import DataExportSerializer
        return DataExportSerializer

    def get_queryset(self):
        qs = DataExport.objects.select_related('requested_by').order_by('-created_at')
        # Non-superadmins see only their own exports
        if not self.request.user.is_superuser:
            qs = qs.filter(requested_by=self.request.user)
        return qs

    @action(detail=False, methods=['post'])
    def request_export(self, request):
        """Request a new async data export."""
        model_name = request.data.get('model_name', '')
        fmt = request.data.get('format', 'csv')
        filters = request.data.get('filters', {})
        selected_fields = request.data.get('selected_fields', [])
        label = request.data.get('label', f'Export {model_name}')

        if not model_name:
            return Response({'error': 'model_name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        export = DataExport.objects.create(
            model_name=model_name,
            format=fmt,
            filters=filters,
            selected_fields=selected_fields,
            label=label,
            status='queued',
            requested_by=request.user,
        )

        try:
            from ..tasks import process_data_export
            task = process_data_export.delay(str(export.export_id))
            export.task_id = str(task.id) if task else ''
            export.save(update_fields=['task_id'])
        except Exception:
            # Sync fallback
            from ..tasks.data_export_tasks import process_export
            process_export(str(export.export_id))

        return Response({
            'success': True,
            'export_id': str(export.export_id),
            'status': export.status,
            'message': 'Export queued. Poll /status/ for progress.',
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download a ready export file."""
        export = self.get_object()
        if export.status != 'ready':
            return Response({'error': f'Export not ready. Current status: {export.status}'}, status=400)
        if export.is_expired:
            return Response({'error': 'Export has expired. Please request a new one.'}, status=410)
        if not export.file_path or not os.path.exists(export.file_path):
            return Response({'error': 'Export file not found on disk.'}, status=404)

        response = FileResponse(open(export.file_path, 'rb'))
        filename = os.path.basename(export.file_path)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['get'])
    def poll_status(self, request, pk=None):
        """Poll export status."""
        export = self.get_object()
        return Response({
            'export_id': str(export.export_id),
            'status': export.status,
            'row_count': export.row_count,
            'file_size': export.file_size_human,
            'error_message': export.error_message,
            'created_at': export.created_at.isoformat(),
            'completed_at': export.completed_at.isoformat() if export.completed_at else None,
            'expires_at': export.expires_at.isoformat() if export.expires_at else None,
            'download_url': f'/api/admin-panel/data-exports/{export.pk}/download/' if export.status == 'ready' else None,
        })

    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Manually trigger expired export cleanup."""
        from ..tasks.data_export_tasks import cleanup_expired_exports
        result = cleanup_expired_exports()
        return Response({'success': True, 'data': result})