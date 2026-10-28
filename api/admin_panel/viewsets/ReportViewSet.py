# api/admin_panel/viewsets/ReportViewSet.py
"""
ReportViewSet — migrated from views.py + new actions.
All original logic (download, regenerate, generate_report) preserved.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..models.core import Report
from ..models.reports import ReportDefinition, ReportSchedule, ReportExport
from ..pagination import ReportPagination
from ..filters import ReportFilter, ReportDefinitionFilter, ReportExportFilter, get_filter_for_model


class ReportViewSet(viewsets.ModelViewSet):
    """
    Report management viewset.
    Keeps all original views.py logic: download, regenerate, generate_report.
    Adds: ReportDefinition, ReportSchedule, ReportExport sub-actions.
    """
    permission_classes = [IsAdminUser]
    pagination_class = ReportPagination
    filterset_class = get_filter_for_model(Report, ReportFilter)

    def get_serializer_class(self):
        from ..serializers.ReportDefinitionSerializer import ReportDefinitionSerializer
        return ReportDefinitionSerializer

    def get_queryset(self):
        return Report.objects.all().order_by('-created_at')

    # ==================== ORIGINAL actions (from views.py) ====================

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download report file (original action)."""
        from django.http import FileResponse
        import os
        report = self.get_object()
        if not report.report_file:
            return Response({'error': 'No file available for this report'}, status=404)
        file_path = report.report_file.path
        if not os.path.exists(file_path):
            return Response({'error': 'Report file not found on disk'}, status=404)
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        """Re-generate report data and file (original action)."""
        report = self.get_object()
        report.status = 'processing'
        report.save(update_fields=['status'])
        from ..tasks import generate_report_task
        generate_report_task.delay(report.id)
        return Response({
            'success': True,
            'message': 'Report regeneration started',
            'report_id': str(report.id),
        })

    @action(detail=False, methods=['post'])
    def generate_report(self, request):
        """Generate a new report async (original action)."""
        report_type = request.data.get('report_type')
        parameters = request.data.get('parameters', {})

        report = Report.objects.create(
            report_type=report_type,
            generated_by=request.user,
            status='PROCESSING',
        )
        from ..tasks import generate_report_task
        generate_report_task.delay(report.id)
        return Response({
            'success': True,
            'data': {'report_id': str(report.id)},
            'message': 'Report generation started',
        })

    # ==================== NEW actions ====================

    @action(detail=False, methods=['get'], url_path='definitions')
    def list_definitions(self, request):
        """List all ReportDefinition templates."""
        qs = ReportDefinition.objects.filter(is_active=True).order_by('name')
        page = self.paginate_queryset(qs)
        if page is not None:
            from ..serializers.ReportDefinitionSerializer import ReportDefinitionSerializer
            serializer = ReportDefinitionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        from ..serializers.ReportDefinitionSerializer import ReportDefinitionSerializer
        return Response({'success': True, 'data': ReportDefinitionSerializer(qs, many=True).data})

    @action(detail=False, methods=['post'], url_path='definitions/create')
    def create_definition(self, request):
        """Create a new ReportDefinition."""
        from ..serializers.ReportDefinitionSerializer import ReportDefinitionSerializer
        serializer = ReportDefinitionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({'success': True, 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='exports')
    def list_exports(self, request):
        """List report exports for the current user."""
        qs = ReportExport.objects.filter(
            generated_by=request.user
        ).order_by('-created_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            from ..serializers.DataExportSerializer import ReportExportSerializer
            serializer = ReportExportSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        from ..serializers.DataExportSerializer import ReportExportSerializer
        return Response({'success': True, 'data': ReportExportSerializer(qs, many=True).data})

    @action(detail=False, methods=['post'], url_path='exports/generate')
    def generate_export(self, request):
        """Generate a new ReportExport on demand."""
        definition_id = request.data.get('definition_id')
        fmt = request.data.get('format', 'csv')
        filters = request.data.get('filters', {})

        try:
            definition = ReportDefinition.objects.get(pk=definition_id)
        except ReportDefinition.DoesNotExist:
            return Response({'error': 'ReportDefinition not found.'}, status=status.HTTP_404_NOT_FOUND)

        export = ReportExport.objects.create(
            report=definition,
            title=f"{definition.name} — {__import__('django.utils.timezone', fromlist=['timezone']).timezone.now().strftime('%Y-%m-%d')}",
            format=fmt,
            status='PROCESSING',
            generated_by=request.user,
            applied_filters=filters,
        )

        try:
            from ..tasks.report_generation_tasks import generate_report_export_task
            generate_report_export_task.delay(str(export.export_id))
        except Exception:
            from ..tasks.report_generation_tasks import _generate_export_file
            _generate_export_file(export)

        return Response({
            'success': True,
            'export_id': str(export.export_id),
            'status': export.status,
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path='exports/(?P<export_id>[^/.]+)/download')
    def download_export(self, request, export_id=None):
        """Download a completed ReportExport file."""
        import uuid, os
        from django.http import FileResponse
        try:
            export = ReportExport.objects.get(
                export_id=uuid.UUID(export_id),
                generated_by=request.user
            )
        except ReportExport.DoesNotExist:
            return Response({'error': 'Export not found.'}, status=status.HTTP_404_NOT_FOUND)
        if export.status != 'completed':
            return Response({'error': f'Export not ready. Status: {export.status}'}, status=status.HTTP_400_BAD_REQUEST)
        if export.is_expired:
            return Response({'error': 'Export has expired. Please generate a new one.'}, status=status.HTTP_410_GONE)
        if not export.file_path or not os.path.exists(export.file_path):
            return Response({'error': 'Export file not found on disk.'}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(open(export.file_path, 'rb'))
        filename = os.path.basename(export.file_path)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'], url_path='schedules')
    def list_schedules(self, request):
        """List report schedules."""
        qs = ReportSchedule.objects.select_related('report', 'created_by').order_by('-is_active', 'name')
        from ..serializers.ReportScheduleSerializer import ReportScheduleSerializer
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(ReportScheduleSerializer(page, many=True).data)
        return Response({'success': True, 'data': ReportScheduleSerializer(qs, many=True).data})

    @action(detail=False, methods=['post'], url_path='schedules/create')
    def create_schedule(self, request):
        """Create a new ReportSchedule."""
        from ..serializers.ReportScheduleSerializer import ReportScheduleSerializer
        serializer = ReportScheduleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({'success': True, 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)