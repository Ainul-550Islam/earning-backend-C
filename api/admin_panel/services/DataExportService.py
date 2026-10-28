# api/admin_panel/services/DataExportService.py
"""Service for async data exports."""
import logging
logger = logging.getLogger(__name__)


class DataExportService:
    @staticmethod
    def request(model_name: str, fmt: str, filters: dict, user, label: str = '', fields: list = None) -> str:
        """Queue a data export. Returns export_id string."""
        from ..models.reports import DataExport
        export = DataExport.objects.create(
            model_name=model_name, format=fmt, filters=filters,
            selected_fields=fields or [], label=label or f'Export {model_name}',
            status='queued', requested_by=user,
        )
        try:
            from ..tasks import process_data_export
            task = process_data_export.delay(str(export.export_id))
            if task:
                export.task_id = str(task.id)
                export.save(update_fields=['task_id'])
        except Exception:
            from ..tasks.data_export_tasks import process_export
            process_export(str(export.export_id))
        return str(export.export_id)

    @staticmethod
    def get_status(export_id: str) -> dict:
        """Get export status by UUID string."""
        import uuid
        from ..models.reports import DataExport
        try:
            export = DataExport.objects.get(export_id=uuid.UUID(export_id))
            return {
                'export_id': str(export.export_id),
                'status': export.status,
                'row_count': export.row_count,
                'file_size': export.file_size_human,
                'error': export.error_message,
                'is_expired': export.is_expired,
                'download_url': f'/api/admin-panel/data-exports/{export.pk}/download/'
                if export.status == 'ready' and not export.is_expired else '',
            }
        except Exception as e:
            return {'error': str(e)}