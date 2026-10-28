# api/admin_panel/signals/report_signals.py
"""Signals: on ReportExport completed → email requester."""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='admin_panel.ReportExport')
def on_report_export_status_change(sender, instance, created, **kwargs):
    """When a ReportExport is completed, notify the user who requested it."""
    if created:
        return
    if instance.status == 'completed' and instance.generated_by and instance.generated_by.email:
        try:
            from ..utils import send_admin_email_notification
            subject = f"[Report Ready] {instance.title or 'Your report is ready'}"
            body = (
                f"Hello {instance.generated_by.get_full_name() or instance.generated_by.username},\n\n"
                f"Your report export is ready.\n"
                f"Rows: {instance.row_count}\n"
                f"Format: {instance.format.upper()}\n"
                f"Download: {instance.file_url}\n\n"
                f"This link expires in 7 days.\n"
            )
            send_admin_email_notification(subject, body, [instance.generated_by.email])
        except Exception as e:
            logger.error(f"ReportExport notification failed: {e}")

    if instance.status == 'failed':
        logger.error(f"ReportExport {instance.export_id} failed: {instance.error_message}")