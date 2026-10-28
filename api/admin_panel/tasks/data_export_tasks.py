# api/admin_panel/tasks/data_export_tasks.py
"""Async data export processing tasks."""
import logging
import os
import json
import csv
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def process_export(export_id: str):
    """Core export processing logic."""
    try:
        from ..models.reports import DataExport
        import uuid
        export = DataExport.objects.get(export_id=uuid.UUID(export_id))
    except Exception as e:
        logger.error(f"DataExport {export_id} not found: {e}")
        return {'success': False, 'error': str(e)}

    export.mark_processing()

    try:
        from django.apps import apps
        from django.conf import settings

        # Parse model
        parts = export.model_name.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid model_name format: {export.model_name}")
        Model = apps.get_model(parts[0], parts[1])

        # Build queryset
        qs = Model.objects.filter(**export.filters)
        if export.selected_fields:
            rows = list(qs.values(*export.selected_fields)[:100_000])
        else:
            rows = list(qs.values()[:100_000])

        # Write file
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        filename = f"export_{export.export_id}.{export.format}"
        filepath = os.path.join(export_dir, filename)

        if export.format == 'csv':
            _write_csv(filepath, rows)
        elif export.format == 'xlsx':
            _write_xlsx(filepath, rows)
        elif export.format == 'json':
            _write_json(filepath, rows)
        else:
            _write_csv(filepath, rows)

        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        file_url = f"/media/exports/{filename}"

        export.mark_ready(filepath, file_url, file_size, len(rows))
        logger.info(f"DataExport {export_id} ready: {len(rows)} rows.")
        return {'success': True, 'export_id': export_id, 'rows': len(rows)}

    except Exception as e:
        export.mark_failed(str(e))
        logger.error(f"DataExport {export_id} failed: {e}")
        return {'success': False, 'error': str(e)}


def _write_csv(filepath, rows):
    if not rows:
        open(filepath, 'w').close()
        return
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def _write_xlsx(filepath, rows):
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        if rows:
            ws.append(list(rows[0].keys()))
            for row in rows:
                ws.append([str(v) for v in row.values()])
        wb.save(filepath)
    except ImportError:
        _write_csv(filepath.replace('.xlsx', '.csv'), rows)


def _write_json(filepath, rows):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, default=str)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='admin_panel.tasks.data_export_tasks.process_data_export_task'
)
def process_data_export_task(self, export_id: str):
    """Celery task wrapper for data export processing."""
    try:
        return process_export(export_id)
    except Exception as exc:
        logger.error(f"process_data_export_task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(name='admin_panel.tasks.data_export_tasks.cleanup_expired_exports')
def cleanup_expired_exports():
    """Delete expired export files and mark records as expired."""
    try:
        from ..models.reports import DataExport, ReportExport
        now = timezone.now()
        expired_data = DataExport.objects.filter(expires_at__lt=now, status='ready')
        expired_report = ReportExport.objects.filter(expires_at__lt=now, status='completed')
        for export in expired_data:
            if export.file_path and os.path.exists(export.file_path):
                try:
                    os.remove(export.file_path)
                except OSError:
                    pass
            export.status = 'expired'
            export.save(update_fields=['status'])
        for export in expired_report:
            if export.file_path and os.path.exists(export.file_path):
                try:
                    os.remove(export.file_path)
                except OSError:
                    pass
            export.status = 'expired'
            export.save(update_fields=['status'])
        count = expired_data.count() + expired_report.count()
        logger.info(f"Cleaned up {count} expired exports.")
        return {'cleaned': count}
    except Exception as e:
        logger.error(f"cleanup_expired_exports failed: {e}")
        return {'error': str(e)}