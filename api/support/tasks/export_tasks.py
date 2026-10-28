# api/support/tasks/export_tasks.py  — WORLD #1 COMPLETE
"""Async CSV/PDF export generation tasks."""
import logging
from celery import shared_task
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.export_tasks.export_tickets_csv")
def export_tickets_csv(days: int = 30, filters: dict = None, email_to: str = None):
    """Generate ticket CSV export and optionally email it."""
    try:
        from api.support.reports.export_manager import export_manager
        filename, csv_bytes = export_manager.export_tickets_csv(days, filters or {})
        if email_to and csv_bytes:
            from api.support.services import notification_service
            notification_service._send_email(
                to      = email_to,
                subject = f"Support Ticket Export — {filename}",
                body    = f"Please find attached the ticket export ({len(csv_bytes)//1024}KB).",
            )
        return {"filename": filename, "size_bytes": len(csv_bytes) if csv_bytes else 0}
    except Exception as e:
        logger.error(f"Export CSV failed: {e}")
        return {"error": str(e)}

@shared_task(name="support.tasks.export_tasks.export_report_excel")
def export_report_excel(report_type: str, days: int = 30, email_to: str = None):
    """Generate Excel report."""
    try:
        from api.support.reports.export_manager import export_manager
        filename, data = export_manager.export_excel(report_type, days)
        if email_to and data:
            from api.support.services import notification_service
            notification_service._send_email(
                to      = email_to,
                subject = f"Support {report_type.title()} Report — {filename}",
                body    = f"Your {report_type} report ({len(data)//1024}KB) is attached.",
            )
        return {"filename": filename, "size_bytes": len(data) if data else 0}
    except Exception as e:
        logger.error(f"Export Excel failed: {e}")
        return {"error": str(e)}