# api/admin_panel/tasks/report_generation_tasks.py
"""
Report generation tasks.
Handles scheduled and on-demand report generation.
"""
import logging
import os
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def run_due_schedules():
    """Find and run all due ReportSchedules."""
    try:
        from ..models.reports import ReportSchedule
    except ImportError:
        logger.debug("ReportSchedule model not yet available.")
        return []

    now = timezone.now()
    due_schedules = ReportSchedule.objects.filter(
        is_active=True,
    ).filter(
        models.Q(next_run_at__isnull=True) |
        models.Q(next_run_at__lte=now)
    )

    results = []
    for schedule in due_schedules:
        try:
            run_scheduled_report_task.delay(schedule.pk)
            results.append({'schedule_id': schedule.pk, 'queued': True})
        except Exception as e:
            logger.error(f"Failed to queue schedule {schedule.pk}: {e}")
            results.append({'schedule_id': schedule.pk, 'queued': False, 'error': str(e)})

    logger.info(f"Queued {len(results)} due report schedules.")
    return results


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='admin_panel.tasks.report_generation_tasks.run_scheduled_report_task'
)
def run_scheduled_report_task(self, schedule_id: int):
    """Run a single ReportSchedule and send results to recipients."""
    try:
        from ..models.reports import ReportSchedule, ReportExport
        schedule = ReportSchedule.objects.get(pk=schedule_id)
    except Exception as e:
        logger.error(f"ReportSchedule {schedule_id} not found: {e}")
        return {'success': False, 'error': str(e)}

    try:
        # Create export record
        export = ReportExport.objects.create(
            report=schedule.report,
            report_schedule=schedule,
            title=f"{schedule.report.name} — {timezone.now().strftime('%Y-%m-%d')}",
            format=schedule.format,
            status='PROCESSING',
            generated_by=schedule.created_by,
            applied_filters=schedule.extra_filters,
        )

        # Generate the file
        _generate_export_file(export)

        # Send to recipients
        if export.status == 'completed' and schedule.recipients:
            _send_report_to_recipients(export, schedule.recipients)

        schedule.record_run(success=(export.status == 'completed'))
        logger.info(f"Scheduled report {schedule_id} completed. Export: {export.pk}")
        return {'success': True, 'export_id': str(export.export_id)}

    except Exception as exc:
        logger.error(f"Scheduled report {schedule_id} failed: {exc}")
        try:
            schedule.record_run(success=False)
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='admin_panel.tasks.report_generation_tasks.generate_report_export_task'
)
def generate_report_export_task(self, export_id: str):
    """Generate a single ReportExport on demand."""
    try:
        from ..models.reports import ReportExport
        import uuid
        export = ReportExport.objects.get(export_id=uuid.UUID(export_id))
    except Exception as e:
        logger.error(f"ReportExport {export_id} not found: {e}")
        return {'success': False, 'error': str(e)}

    try:
        export.status = 'processing'
        export.save(update_fields=['status'])
        _generate_export_file(export)
        return {'success': True, 'export_id': export_id, 'status': export.status}
    except Exception as exc:
        logger.error(f"Report export {export_id} failed: {exc}")
        try:
            export.status = 'failed'
            export.error_message = str(exc)
            export.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
        raise self.retry(exc=exc)


def _generate_export_file(export):
    """
    Core logic: run the report query and write to file.
    Supports CSV, XLSX, JSON formats.
    """
    import csv
    import json
    from django.conf import settings

    try:
        report_def = export.report
        query_config = report_def.query_config if report_def else {}
        columns = report_def.columns if report_def else []
        filters = {**query_config.get('filters', {}), **export.applied_filters}

        # Get data rows (placeholder implementation — override with real query)
        rows = _run_report_query(query_config, filters)

        # Determine file path
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        filename = f"report_{export.export_id}.{export.format}"
        filepath = os.path.join(export_dir, filename)

        if export.format == 'csv':
            _write_csv(filepath, columns, rows)
        elif export.format == 'xlsx':
            _write_xlsx(filepath, columns, rows)
        elif export.format == 'json':
            _write_json(filepath, rows)
        else:
            _write_csv(filepath, columns, rows)

        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        file_url = f"/media/exports/{filename}"

        export.file_path = filepath
        export.file_url = file_url
        export.file_size_bytes = file_size
        export.row_count = len(rows)
        export.status = 'completed'
        export.save()

    except Exception as e:
        export.status = 'failed'
        export.error_message = str(e)
        export.save(update_fields=['status', 'error_message'])
        logger.error(f"_generate_export_file failed: {e}")
        raise


def _run_report_query(query_config: dict, filters: dict) -> list:
    """Run the report query and return list of dicts."""
    model_path = query_config.get('model', '')
    if not model_path:
        return []
    try:
        from django.apps import apps
        parts = model_path.split('.')
        if len(parts) == 2:
            app_label, model_name = parts
            Model = apps.get_model(app_label, model_name)
            qs = Model.objects.filter(**filters)
            # Limit to 100k rows
            qs = qs[:100_000]
            return list(qs.values())
    except Exception as e:
        logger.error(f"Report query failed: {e}")
    return []


def _write_csv(filepath: str, columns: list, rows: list):
    import csv
    headers = [c.get('label', c.get('field', '')) for c in columns] if columns else (list(rows[0].keys()) if rows else [])
    fields = [c.get('field', c.get('label', '')) for c in columns] if columns else (list(rows[0].keys()) if rows else [])
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writerow(dict(zip(fields, headers)))
        writer.writerows(rows)


def _write_xlsx(filepath: str, columns: list, rows: list):
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        headers = [c.get('label', c.get('field', '')) for c in columns] if columns else (list(rows[0].keys()) if rows else [])
        fields = [c.get('field', '') for c in columns] if columns else (list(rows[0].keys()) if rows else [])
        ws.append(headers)
        for row in rows:
            ws.append([str(row.get(f, '')) for f in fields])
        wb.save(filepath)
    except ImportError:
        # Fallback to CSV if openpyxl not installed
        _write_csv(filepath.replace('.xlsx', '.csv'), columns, rows)


def _write_json(filepath: str, rows: list):
    import json
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, default=str)


def _send_report_to_recipients(export, recipients: list):
    """Send completed report to email recipients."""
    try:
        from ..utils import send_admin_email_notification
        report_name = export.report.name if export.report else 'Report'
        subject = f"[Report Ready] {report_name}"
        body = (
            f"Your scheduled report '{report_name}' is ready.\n\n"
            f"Rows: {export.row_count}\n"
            f"Format: {export.format.upper()}\n"
            f"Download: {export.file_url}\n\n"
            f"This link expires in 7 days."
        )
        send_admin_email_notification(subject, body, recipients)
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")


# Fix missing import in run_due_schedules
from django.db import models